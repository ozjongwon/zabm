#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
readonly RUNTIME_CONFIG="${REPO_ROOT}/runtime/runtime-v1.conf"
readonly OS_RELEASE_FILE="${ZABM_OS_RELEASE_FILE:-/etc/os-release}"

# shellcheck source=../runtime/runtime-v1.conf
source "${RUNTIME_CONFIG}"

readonly DEFAULT_RUNTIME_HOME="/home/ollama"
RUNTIME_HOME="${ZABM_RUNTIME_HOME:-${DEFAULT_RUNTIME_HOME}}"
readonly RUNTIME_CONFIG_DIR="${ZABM_RUNTIME_CONFIG_DIR:-${XDG_CONFIG_HOME:-${HOME}/.config}/zabm}"
MODEL_DIR="${RUNTIME_HOME}/models"
STATE_DIR="${RUNTIME_HOME}/state"
readonly CONFIG_FILE="${RUNTIME_CONFIG_DIR}/runtime.env"
readonly DATA_DIR="${ZABM_DATA_DIR:-${REPO_ROOT}/.zabm}"
readonly BIN_DIR="${HOME}/.local/bin"
OLLAMA_BIN="${ZABM_OLLAMA_BIN:-}"
RUNTIME_CHAT_MODEL_NAME="${ZABM_MODEL:-}"
RUNTIME_EMBEDDING_MODEL_NAME="${ZABM_EMBEDDING_MODEL:-}"
AVAILABLE_MODELS=()
readonly VENV_PYTHON="${REPO_ROOT}/.venv/bin/python"
readonly PROVIDER_URL="http://127.0.0.1:11434/v1"
readonly OLLAMA_SERVICE_NAME="${ZABM_OLLAMA_SERVICE:-ollama.service}"

DRY_RUN=false
BASE_INSTALLED=false
RUNTIME_OWNER=""
RUNTIME_GROUP=""
SMOKE_WEB_PID=""
SMOKE_TEMP_FILES=()

usage() {
  cat <<'EOF'
Usage: ./scripts/install-runtime.sh [--dry-run] [--runtime-home PATH]

Installs the supported target runtime on Debian 13 or Ubuntu 24.04 x86_64:
the runtime Python environment, CLI, web chat, generated evidence stores, and
installed-target smoke checks. Ollama and its models must already be installed
and managed by systemd; this script selects existing models with 'ollama list'.

Options:
  --dry-run            Validate and print the full plan without changing anything
  --runtime-home PATH  Store models and runtime state under PATH
                       (default: /home/ollama)
  -h, --help           Show this help

Set ZABM_MODEL or ZABM_EMBEDDING_MODEL to choose specific installed models.
Existing models can also be selected again with
./scripts/select-runtime-models.sh.
EOF
}

log() {
  printf 'zabm runtime: %s\n' "$*"
}

warn() {
  printf 'zabm runtime: warning: %s\n' "$*" >&2
}

die() {
  printf 'zabm runtime: error: %s\n' "$*" >&2
  exit 1
}

redact_stream() {
  sed -E \
    -e 's#(https?://)[^/@[:space:]]+:[^/@[:space:]]+@#\1<redacted>@#g' \
    -e 's#((OPENAI_API_KEY|ANTHROPIC_API_KEY|LANGSMITH_API_KEY|HF_TOKEN|HUGGING_FACE_HUB_TOKEN|PASSWORD|TOKEN|SECRET)[A-Z0-9_]*[=:][[:space:]]*)[^[:space:]]+#\1<redacted>#Ig' \
    -e 's#(Bearer[[:space:]]+)[A-Za-z0-9._~+/=-]+#\1<redacted>#Ig'
}

run() {
  local output
  local status

  set +e
  output="$("$@" 2>&1)"
  status=$?
  set -e

  if [[ -n "${output}" ]]; then
    printf '%s\n' "${output}" | redact_stream
  fi
  return "${status}"
}

run_privileged() {
  if ((EUID == 0)); then
    run "$@"
  else
    run sudo "$@"
  fi
}

cleanup() {
  local path

  if [[ -n "${SMOKE_WEB_PID}" ]] && kill -0 "${SMOKE_WEB_PID}" 2>/dev/null; then
    kill -TERM "${SMOKE_WEB_PID}" 2>/dev/null || true
    wait "${SMOKE_WEB_PID}" 2>/dev/null || true
  fi
  for path in "${SMOKE_TEMP_FILES[@]}"; do
    rm -f -- "${path}"
  done
}
trap cleanup EXIT

parse_args() {
  while (( $# > 0 )); do
    case "$1" in
      --dry-run)
        DRY_RUN=true
        shift
        ;;
      --runtime-home)
        (($# >= 2)) || die "--runtime-home requires an absolute path"
        [[ "$2" == /* ]] || die "--runtime-home requires an absolute path"
        RUNTIME_HOME="${2%/}"
        [[ -n "${RUNTIME_HOME}" ]] || die "--runtime-home cannot be the filesystem root"
        MODEL_DIR="${RUNTIME_HOME}/models"
        STATE_DIR="${RUNTIME_HOME}/state"
        shift 2
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        die "unknown option: $1"
        ;;
    esac
  done
}

read_os_release() {
  local key
  local value

  OS_ID=""
  OS_VERSION_ID=""
  OS_PRETTY_NAME=""

  [[ -r "${OS_RELEASE_FILE}" ]] ||
    die "cannot read ${OS_RELEASE_FILE}"

  while IFS='=' read -r key value || [[ -n "${key}" ]]; do
    value="${value%\"}"
    value="${value#\"}"
    case "${key}" in
      ID) OS_ID="${value}" ;;
      VERSION_ID) OS_VERSION_ID="${value}" ;;
      PRETTY_NAME) OS_PRETTY_NAME="${value}" ;;
    esac
  done < "${OS_RELEASE_FILE}"
}

validate_platform() {
  local architecture

  read_os_release
  architecture="$(uname -m)"

  [[ "${architecture}" == "x86_64" ]] ||
    die "supports Debian 13 and Ubuntu 24.04 on x86_64; found ${architecture}"
  if [[ "${OS_ID}" == "debian" && "${OS_VERSION_ID}" == "13" ]]; then
    return
  fi
  if [[ "${OS_ID}" == "ubuntu" && "${OS_VERSION_ID}" == "24.04" ]]; then
    return
  fi

  die "supports Debian 13 and Ubuntu 24.04 on x86_64; found ${OS_PRETTY_NAME:-${OS_ID} ${OS_VERSION_ID}}"
}

check_nvidia_prerequisites() {
  local devices

  if ! command -v nvidia-smi >/dev/null 2>&1; then
    warn "nvidia-smi was not found; the local server can run on CPU, but GPU execution requires a working NVIDIA driver"
    warn "install the NVIDIA kernel driver through the official Debian or Ubuntu packages, reboot, and verify 'nvidia-smi'"
    warn "this installer does not install, upgrade, or replace the host GPU driver"
    return
  fi

  if ! devices="$(nvidia-smi -L 2>&1)" || [[ -z "${devices}" ]]; then
    warn "nvidia-smi exists but did not report a GPU: ${devices:-no output}"
    die "fix the NVIDIA kernel driver or GPU visibility, reboot, and confirm 'nvidia-smi -L' before retrying"
  fi
  log "NVIDIA driver detected; the installer will not change it"
}

require_installed_runtime() {
  [[ -x "${VENV_PYTHON}" ]] ||
    die "runtime Python is missing; run ./scripts/install-runtime.sh first"
  [[ -f "${CONFIG_FILE}" ]] ||
    die "runtime configuration is missing; run ./scripts/install-runtime.sh first"
  resolve_ollama_bin ||
    fail_ollama_prerequisite "Ollama v${RUNTIME_SERVER_VERSION} was not found"
}

resolve_ollama_bin() {
  local candidate

  if [[ -n "${OLLAMA_BIN}" && -x "${OLLAMA_BIN}" ]]; then
    return
  fi
  for candidate in "${RUNTIME_HOME}/bin/ollama" "$(command -v ollama 2>/dev/null || true)"; do
    if [[ -n "${candidate}" && -x "${candidate}" ]]; then
      OLLAMA_BIN="${candidate}"
      return
    fi
  done
  OLLAMA_BIN=""
  return 1
}

print_ollama_instructions() {
  cat >&2 <<EOF
Ollama is not installed or managed by this script.

Before rerunning, prepare it outside this repository:
  1. Install Ollama v${RUNTIME_SERVER_VERSION} under ${RUNTIME_HOME}.
  2. Make its server binary available at ${RUNTIME_HOME}/bin/ollama,
     on PATH, or through ZABM_OLLAMA_BIN.
  3. Configure ${OLLAMA_SERVICE_NAME} with OLLAMA_MODELS=${MODEL_DIR}.
  4. Enable and start the service:
       sudo systemctl enable --now ${OLLAMA_SERVICE_NAME}
  5. Verify the service:
       systemctl is-active --quiet ${OLLAMA_SERVICE_NAME}
       ${RUNTIME_HOME}/bin/ollama --version
  6. Rerun ./scripts/install-runtime.sh
EOF
}

fail_ollama_prerequisite() {
  local reason="$1"

  printf 'zabm runtime: error: %s\n' "${reason}" >&2
  print_ollama_instructions
  exit 1
}

check_ollama_prerequisites() {
  local reported

  [[ -d "${RUNTIME_HOME}" ]] ||
    fail_ollama_prerequisite "${RUNTIME_HOME} does not exist"
  command -v systemctl >/dev/null 2>&1 ||
    fail_ollama_prerequisite "systemctl is required to check ${OLLAMA_SERVICE_NAME}"
  resolve_ollama_bin ||
    fail_ollama_prerequisite "Ollama v${RUNTIME_SERVER_VERSION} was not found"
  reported="$("${OLLAMA_BIN}" --version 2>&1 || true)"
  [[ "${reported}" =~ (^|[^0-9])${RUNTIME_SERVER_VERSION}([^0-9]|$) ]] ||
    fail_ollama_prerequisite "expected Ollama v${RUNTIME_SERVER_VERSION}, found: ${reported:-no version output}"
  systemctl is-enabled --quiet "${OLLAMA_SERVICE_NAME}" ||
    fail_ollama_prerequisite "${OLLAMA_SERVICE_NAME} is not enabled at boot"
  systemctl is-active --quiet "${OLLAMA_SERVICE_NAME}" ||
    fail_ollama_prerequisite "${OLLAMA_SERVICE_NAME} is not active"
  log "using preinstalled ${RUNTIME_SERVER_NAME} v${RUNTIME_SERVER_VERSION} from ${OLLAMA_BIN}"
}

install_runtime_base() {
  if [[ "${BASE_INSTALLED}" == true ]]; then
    return
  fi
  log "installing the locked runtime environment and application"
  run env \
    ZABM_OS_RELEASE_FILE="${OS_RELEASE_FILE}" \
    "${REPO_ROOT}/scripts/install-dev.sh" --profile runtime
  BASE_INSTALLED=true
}

write_if_changed() {
  local destination="$1"
  local mode="$2"
  local source="$3"

  if [[ -f "${destination}" ]] && cmp --silent "${source}" "${destination}"; then
    chmod "${mode}" "${destination}"
    rm -f -- "${source}"
    return
  fi
  mkdir -p "$(dirname -- "${destination}")"
  mv "${source}" "${destination}"
  chmod "${mode}" "${destination}"
}

write_runtime_config() {
  local generated
  local provider_configuration

  [[ -n "${RUNTIME_CHAT_MODEL_NAME}" && -n "${RUNTIME_EMBEDDING_MODEL_NAME}" ]] ||
    die "runtime models have not been selected"
  provider_configuration="ollama-v${RUNTIME_SERVER_VERSION},${RUNTIME_CHAT_MODEL_NAME},${RUNTIME_EMBEDDING_MODEL_NAME},temperature=0,seed=0"

  mkdir -p "${RUNTIME_CONFIG_DIR}"
  generated="$(mktemp)"
  {
    printf '# Generated by ./scripts/install-runtime.sh; re-running replaces this file.\n'
    printf 'ZABM_PROVIDER=openai-compatible\n'
    printf 'ZABM_PROVIDER_URL=%s\n' "${PROVIDER_URL}"
    printf 'ZABM_MODEL=%s\n' "${RUNTIME_CHAT_MODEL_NAME}"
    printf 'ZABM_EMBEDDING_MODEL=%s\n' "${RUNTIME_EMBEDDING_MODEL_NAME}"
    printf 'ZABM_PROVIDER_CONFIGURATION=%q\n' "${provider_configuration}"
    printf 'ZABM_PROVIDER_API_KEY=\n'
    printf 'ZABM_DEBUG=0\n'
    printf 'OLLAMA_MODELS=%q\n' "${MODEL_DIR}"
  } > "${generated}"
  write_if_changed "${CONFIG_FILE}" 600 "${generated}"
}

resolve_runtime_ownership() {
  RUNTIME_OWNER=""
  RUNTIME_GROUP=""
  IFS=' ' read -r RUNTIME_OWNER RUNTIME_GROUP < <(stat -c '%U %G' "${RUNTIME_HOME}")
  if [[ -z "${RUNTIME_OWNER}" || -z "${RUNTIME_GROUP}" ||
    "${RUNTIME_OWNER}" == "UNKNOWN" || "${RUNTIME_GROUP}" == "UNKNOWN" ]]; then
    die "cannot determine the owner and group of ${RUNTIME_HOME}"
  fi
}

ensure_runtime_directory() {
  local directory="$1"
  local existing_group
  local existing_owner

  if [[ -d "${directory}" ]]; then
    IFS=' ' read -r existing_owner existing_group < <(stat -c '%U %G' "${directory}")
    if [[ "${existing_owner}" != "${RUNTIME_OWNER}" ||
      "${existing_group}" != "${RUNTIME_GROUP}" ]]; then
      log "preserving ${RUNTIME_OWNER}:${RUNTIME_GROUP} ownership for ${directory}"
      run_privileged chown "${RUNTIME_OWNER}:${RUNTIME_GROUP}" "${directory}" ||
        die "cannot assign ${directory} to ${RUNTIME_OWNER}:${RUNTIME_GROUP}"
    fi
    return
  fi
  if [[ "${RUNTIME_OWNER}" == "$(id -un)" && "${RUNTIME_GROUP}" == "$(id -gn)" ]]; then
    mkdir -p "${directory}" ||
      die "cannot create ${directory}"
    return
  fi
  run_privileged install -d -m 0755 -o "${RUNTIME_OWNER}" -g "${RUNTIME_GROUP}" "${directory}" ||
    die "cannot create ${directory} with owner ${RUNTIME_OWNER}:${RUNTIME_GROUP}"
}

write_runtime_launcher() {
  local generated

  mkdir -p "${BIN_DIR}"
  generated="$(mktemp)"
  {
    printf '#!/usr/bin/env bash\n'
    printf 'set -Eeuo pipefail\n'
    printf 'set -a\n'
    printf 'source %q\n' "${CONFIG_FILE}"
    printf 'set +a\n'
    printf 'exec %q -m zabm "$@"\n' "${VENV_PYTHON}"
  } > "${generated}"
  write_if_changed "${BIN_DIR}/zabm-runtime" 755 "${generated}"
}

server_version_response() {
  curl \
    --fail \
    --silent \
    --show-error \
    --max-time 2 \
    "http://127.0.0.1:11434/api/version" 2>/dev/null || true
}

response_reports_pinned_version() {
  local response="$1"

  printf '%s\n' "${response}" |
    grep -Eq "\"version\"[[:space:]]*:[[:space:]]*\"${RUNTIME_SERVER_VERSION//./\\.}\""
}

wait_for_server() {
  local attempt
  local response

  for attempt in $(seq 1 120); do
    response="$(server_version_response)"
    if response_reports_pinned_version "${response}"; then
      return
    fi
    sleep 0.5
  done

  die "${OLLAMA_SERVICE_NAME} is active but did not answer within 60 seconds; inspect it with 'sudo systemctl status ${OLLAMA_SERVICE_NAME}' and 'sudo journalctl --unit ${OLLAMA_SERVICE_NAME}'"
}

verify_ollama_service() {
  local response

  check_ollama_prerequisites
  response="$(server_version_response)"
  if [[ -n "${response}" ]] && ! response_reports_pinned_version "${response}"; then
    fail_ollama_prerequisite "port 11434 is answering with a different Ollama version"
  fi
  wait_for_server
}

list_installed_models() {
  "${OLLAMA_BIN}" list 2>/dev/null |
    awk 'NR > 1 && NF > 0 {print $1}'
}

load_installed_models() {
  mapfile -t AVAILABLE_MODELS < <(list_installed_models)
  ((${#AVAILABLE_MODELS[@]} > 0)) ||
    die "Ollama has no installed models; pull a model with '${OLLAMA_BIN} pull <model>' before retrying"
}

model_is_available() {
  local model

  for model in "${AVAILABLE_MODELS[@]}"; do
    [[ "${model}" == "$1" ]] && return
  done
  return 1
}

lookup_available_model() {
  if model_is_available "$1"; then
    printf '%s\n' "$1"
    return
  fi
  if [[ "$1" != *:* ]] && model_is_available "$1:latest"; then
    printf '%s\n' "$1:latest"
    return
  fi
  return 1
}

model_looks_like_embedding() {
  local model="${1,,}"

  [[ "${model}" =~ (embed|bge|e5|nomic|mxbai|minilm|gte|snowflake|arctic) ]]
}

available_models_csv() {
  local IFS=', '

  printf '%s' "${AVAILABLE_MODELS[*]}"
}

select_chat_model() {
  local requested="${RUNTIME_CHAT_MODEL_NAME}"
  local model
  local selected=""

  if [[ -n "${requested}" ]]; then
    lookup_available_model "${requested}" ||
      die "requested chat model '${requested}' is not installed; available models: $(available_models_csv)"
    return
  fi
  for model in "${AVAILABLE_MODELS[@]}"; do
    if ! model_looks_like_embedding "${model}"; then
      selected="${model}"
      break
    fi
  done
  printf '%s\n' "${selected:-${AVAILABLE_MODELS[0]}}"
}

select_embedding_model() {
  local requested="${RUNTIME_EMBEDDING_MODEL_NAME}"
  local model

  if [[ -n "${requested}" ]]; then
    lookup_available_model "${requested}" ||
      die "requested embedding model '${requested}' is not installed; available models: $(available_models_csv)"
    return
  fi
  for model in "${AVAILABLE_MODELS[@]}"; do
    if model_looks_like_embedding "${model}"; then
      printf '%s\n' "${model}"
      return
    fi
  done
  printf '%s\n' "${AVAILABLE_MODELS[0]}"
}

select_models() {
  load_installed_models
  RUNTIME_CHAT_MODEL_NAME="$(select_chat_model)"
  RUNTIME_EMBEDDING_MODEL_NAME="$(select_embedding_model)"
  log "using existing chat model: ${RUNTIME_CHAT_MODEL_NAME}"
  log "using existing embedding model: ${RUNTIME_EMBEDDING_MODEL_NAME}"
}

prepare_evidence() {
  log "downloading, verifying, and ingesting the frozen source pack"
  run "${VENV_PYTHON}" -m zabm download
  run "${VENV_PYTHON}" -m zabm ingest --data-dir "${DATA_DIR}"
  local artifact
  for artifact in specifications.json compatibility.json retrieval.json; do
    [[ -s "${DATA_DIR}/generated/${artifact}" ]] ||
      die "evidence store is missing: ${DATA_DIR}/generated/${artifact}"
  done
}

source_runtime_config() {
  [[ -f "${CONFIG_FILE}" ]] ||
    die "runtime configuration is missing: ${CONFIG_FILE}"
  # The file is generated by this installer and contains only non-secret values.
  set -a
  # shellcheck source=/dev/null
  source "${CONFIG_FILE}"
  set +a
}

validate_supported_response() {
  local response_file="$1"
  local label="$2"

  "${VENV_PYTHON}" - "${response_file}" "${label}" <<'PY'
import json
import sys

payload = json.loads(open(sys.argv[1], encoding="utf-8").read())
label = sys.argv[2]
assert payload["status"] == "supported", f"{label}: {payload['status']}"
assert payload["claims"], f"{label}: no supported claims"
assert payload["citations"], f"{label}: no citations"
PY
}

run_installed_smoke() {
  local response_file
  local web_log
  local web_payload
  local web_response
  local web_url=""
  local attempt

  source_runtime_config
  response_file="$(mktemp)"
  web_log="$(mktemp)"
  web_payload="$(mktemp)"
  SMOKE_TEMP_FILES+=("${response_file}" "${web_log}" "${web_payload}")

  log "smoke: application health"
  "${VENV_PYTHON}" -m zabm health >/dev/null

  log "smoke: local chat and embedding provider"
  run "${VENV_PYTHON}" -m zabm provider-smoke

  log "smoke: evidence stores and one supported answer"
  "${VENV_PYTHON}" -m zabm ask \
    "What torque should I use for the RockShox Reverb Standard Remote clamp bolt?" \
    --json > "${response_file}"
  validate_supported_response "${response_file}" "CLI"

  log "smoke: web chat over the canonical answer path"
  "${VENV_PYTHON}" -m zabm web --host 127.0.0.1 --port 0 > "${web_log}" 2>&1 &
  SMOKE_WEB_PID="$!"

  for attempt in $(seq 1 60); do
    web_url="$(sed -n 's/^zabm web: \(http[^ ]*\).*/\1/p' "${web_log}" | sed -n '1p')"
    [[ -n "${web_url}" ]] && break
    kill -0 "${SMOKE_WEB_PID}" 2>/dev/null || break
    sleep 0.5
  done
  [[ -n "${web_url}" ]] || {
    tail -n 20 "${web_log}" | redact_stream >&2
    die "web chat did not start"
  }

  printf '%s\n' \
    '{"question":"What torque should I use for the RockShox Reverb Standard Remote clamp bolt?"}' \
    > "${web_payload}"
  web_response="$(
    curl \
      --fail \
      --silent \
      --show-error \
      --header 'Content-Type: application/json' \
      --data-binary "@${web_payload}" \
      "${web_url}/api/ask"
  )"
  printf '%s\n' "${web_response}" > "${response_file}"
  validate_supported_response "${response_file}" "web"
  kill -TERM "${SMOKE_WEB_PID}" 2>/dev/null || true
  wait "${SMOKE_WEB_PID}" 2>/dev/null || true
  SMOKE_WEB_PID=""
}

print_plan() {
  log "install plan:"
  log "platform: ${OS_PRETTY_NAME} (${OS_ID} ${OS_VERSION_ID}, x86_64)"
  log "runtime dependencies only; development, test, and evaluation dependencies are excluded"
  log "application: CLI and web chat in ${REPO_ROOT}/.venv"
  log "runtime home: ${RUNTIME_HOME}"
  log "Ollama prerequisite: preinstalled ${RUNTIME_SERVER_NAME} v${RUNTIME_SERVER_VERSION} and active ${OLLAMA_SERVICE_NAME}"
  log "model selection: existing models reported by '${OLLAMA_BIN:-ollama} list'"
  log "chat model preference: ${RUNTIME_CHAT_MODEL_NAME:-an installed non-embedding model}"
  log "embedding model preference: ${RUNTIME_EMBEDDING_MODEL_NAME:-an installed embedding model, otherwise the chat model}"
  log "model downloads and imports: none"
  log "Ollama model store: ${MODEL_DIR}"
  log "runtime configuration: ${CONFIG_FILE}"
  log "evidence stores: ${DATA_DIR}/generated"
  log "installed-target smoke: health, local provider, evidence stores, web chat, and one supported answer"
}

prepare_runtime_directories() {
  local acl_path
  local current_user

  current_user="$(id -u)"
  if [[ ! -w "${RUNTIME_HOME}" ]]; then
    command -v setfacl >/dev/null 2>&1 || install_runtime_base
    command -v setfacl >/dev/null 2>&1 ||
      die "setfacl is required to grant access without changing ownership of ${RUNTIME_HOME}"
    log "granting $(id -un) access to ${RUNTIME_HOME} while preserving its owner and group"
    run_privileged setfacl -m "u:${current_user}:rwx" "${RUNTIME_HOME}" ||
      die "sudo could not update the access ACL for ${RUNTIME_HOME}"
    run_privileged setfacl -d -m "u:${current_user}:rwx" "${RUNTIME_HOME}" ||
      die "sudo could not set the default access ACL for ${RUNTIME_HOME}"
    for acl_path in "${MODEL_DIR}" "${STATE_DIR}"; do
      if [[ -e "${acl_path}" ]]; then
        run_privileged setfacl -R -m "u:${current_user}:rwx" "${acl_path}" ||
          die "sudo could not update the access ACL for ${acl_path}"
      fi
    done
  fi
  [[ -w "${RUNTIME_HOME}" ]] ||
    die "${RUNTIME_HOME} is still not writable after applying access control"
  resolve_runtime_ownership
  ensure_runtime_directory "${MODEL_DIR}"
  ensure_runtime_directory "${STATE_DIR}"
  [[ -w "${STATE_DIR}" ]] ||
    die "${STATE_DIR} must be writable by the user running the installer"
  log "runtime directories are ready under ${RUNTIME_HOME}"
}

main() {
  parse_args "$@"
  validate_platform
  check_nvidia_prerequisites

  if [[ "${DRY_RUN}" == true ]]; then
    print_plan
    log "dry run complete; no changes made"
    return
  fi

  print_plan
  check_ollama_prerequisites
  prepare_runtime_directories
  log "starting installation; use --dry-run to inspect the plan without changes"
  verify_ollama_service
  select_models
  install_runtime_base
  write_runtime_config
  write_runtime_launcher
  prepare_evidence
  run_installed_smoke

  log "target runtime is ready"
  log "CLI: ${BIN_DIR}/zabm-runtime ask \"...\""
  log "web: ${BIN_DIR}/zabm-runtime web --data-dir ${DATA_DIR}"
  log "server: sudo systemctl status ${OLLAMA_SERVICE_NAME}"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
