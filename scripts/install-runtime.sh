#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
readonly RUNTIME_CONFIG="${REPO_ROOT}/runtime/runtime-v1.conf"
readonly OS_RELEASE_FILE="${ZABM_OS_RELEASE_FILE:-/etc/os-release}"

# shellcheck source=../runtime/runtime-v1.conf
source "${RUNTIME_CONFIG}"

readonly RUNTIME_HOME="${ZABM_RUNTIME_HOME:-${XDG_DATA_HOME:-${HOME:?HOME must be set}/.local/share}/zabm-runtime}"
readonly RUNTIME_CONFIG_DIR="${ZABM_RUNTIME_CONFIG_DIR:-${XDG_CONFIG_HOME:-${HOME}/.config}/zabm}"
readonly MODEL_DIR="${RUNTIME_HOME}/models"
readonly SERVER_DIR="${RUNTIME_HOME}/server"
readonly STATE_DIR="${RUNTIME_HOME}/state"
readonly CONFIG_FILE="${RUNTIME_CONFIG_DIR}/runtime.env"
readonly DATA_DIR="${ZABM_DATA_DIR:-${REPO_ROOT}/.zabm}"
readonly BIN_DIR="${HOME}/.local/bin"
readonly SERVER_VERSION_DIR="${SERVER_DIR}/v${RUNTIME_SERVER_VERSION}"
readonly OLLAMA_BIN="${SERVER_VERSION_DIR}/bin/ollama"
readonly SERVER_PID_FILE="${STATE_DIR}/ollama.pid"
readonly SERVER_LOG_FILE="${STATE_DIR}/ollama.log"
readonly MODEL_STATE_FILE="${STATE_DIR}/models-v1.sha256"
readonly VENV_PYTHON="${REPO_ROOT}/.venv/bin/python"
readonly PROVIDER_URL="http://127.0.0.1:11434/v1"

DRY_RUN=false
TEMP_DIR=""
SMOKE_WEB_PID=""
SMOKE_TEMP_FILES=()

usage() {
  cat <<'EOF'
Usage: ./scripts/install-runtime.sh [--dry-run]

Installs the supported target runtime on Debian 13 or Ubuntu 24.04 x86_64:
the runtime Python environment, CLI, web chat, pinned Ollama server, external
models, generated evidence stores, and installed-target smoke checks.

Options:
  --dry-run    Validate and print the complete install plan without changes
  -h, --help   Show this help

Model weights are stored outside the repository. They can also be fetched
separately with ./scripts/fetch-runtime-models.sh.
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

cleanup() {
  local path

  if [[ -n "${SMOKE_WEB_PID}" ]] && kill -0 "${SMOKE_WEB_PID}" 2>/dev/null; then
    kill -TERM "${SMOKE_WEB_PID}" 2>/dev/null || true
    wait "${SMOKE_WEB_PID}" 2>/dev/null || true
  fi
  if [[ -n "${TEMP_DIR}" && -d "${TEMP_DIR}" ]]; then
    rm -rf -- "${TEMP_DIR}"
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
  [[ -x "${OLLAMA_BIN}" ]] ||
    die "pinned Ollama is missing; run ./scripts/install-runtime.sh first"
  [[ -f "${CONFIG_FILE}" ]] ||
    die "runtime configuration is missing; run ./scripts/install-runtime.sh first"
}

ollama_reports_pinned_version() {
  local reported

  [[ -x "${OLLAMA_BIN}" ]] || return 1
  reported="$(
    OLLAMA_LIBRARY_PATH="${SERVER_VERSION_DIR}/lib/ollama" \
      "${OLLAMA_BIN}" --version 2>/dev/null || true
  )"
  [[ "${reported}" =~ (^|[^0-9])${RUNTIME_SERVER_VERSION}([^0-9]|$) ]]
}

install_runtime_base() {
  log "installing the locked runtime environment and application"
  run env \
    ZABM_OS_RELEASE_FILE="${OS_RELEASE_FILE}" \
    "${REPO_ROOT}/scripts/install-dev.sh" --profile runtime
}

install_model_server() {
  local archive
  local extract_dir
  local staging_dir

  if ollama_reports_pinned_version; then
    log "using ${RUNTIME_SERVER_NAME} v${RUNTIME_SERVER_VERSION}"
    ln -sfn "${SERVER_VERSION_DIR}" "${SERVER_DIR}/current"
    return
  fi

  command -v curl >/dev/null 2>&1 || die "curl is required to install the model server"
  command -v sha256sum >/dev/null 2>&1 || die "sha256sum is required to verify the model server"
  command -v tar >/dev/null 2>&1 || die "tar is required to install the model server"
  command -v zstd >/dev/null 2>&1 || die "zstd is required to extract the model server archive"

  mkdir -p "${SERVER_DIR}" "${STATE_DIR}"
  TEMP_DIR="$(mktemp -d)"
  archive="${TEMP_DIR}/${RUNTIME_SERVER_ARCHIVE}"
  extract_dir="${TEMP_DIR}/extract"
  staging_dir="${SERVER_DIR}/.v${RUNTIME_SERVER_VERSION}.new.$$"

  log "downloading ${RUNTIME_SERVER_NAME} v${RUNTIME_SERVER_VERSION}"
  run curl \
    --fail \
    --location \
    --proto '=https' \
    --retry 3 \
    --show-error \
    --silent \
    --output "${archive}" \
    "${RUNTIME_SERVER_URL}"
  printf '%s  %s\n' "${RUNTIME_SERVER_SHA256}" "${archive}" | sha256sum --check --status ||
    die "model server archive checksum mismatch"

  mkdir -p "${extract_dir}"
  run tar --zstd --extract --file "${archive}" --directory "${extract_dir}"
  [[ -x "${extract_dir}/bin/ollama" ]] ||
    die "model server archive did not contain bin/ollama"
  [[ -d "${extract_dir}/lib/ollama" ]] ||
    die "model server archive did not contain lib/ollama"

  mv "${extract_dir}" "${staging_dir}"
  if [[ -e "${SERVER_VERSION_DIR}" ]]; then
    mv "${SERVER_VERSION_DIR}" "${SERVER_VERSION_DIR}.stale.$(date -u +%Y%m%dT%H%M%SZ)"
  fi
  mv "${staging_dir}" "${SERVER_VERSION_DIR}"
  ln -sfn "${SERVER_VERSION_DIR}" "${SERVER_DIR}/current"
  ollama_reports_pinned_version ||
    die "installed model server did not report version ${RUNTIME_SERVER_VERSION}"
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

  mkdir -p "${RUNTIME_CONFIG_DIR}"
  generated="$(mktemp)"
  {
    printf '# Generated by ./scripts/install-runtime.sh; re-running replaces this file.\n'
    printf 'ZABM_PROVIDER=openai-compatible\n'
    printf 'ZABM_PROVIDER_URL=%s\n' "${PROVIDER_URL}"
    printf 'ZABM_MODEL=%s\n' "${RUNTIME_CHAT_MODEL_NAME}"
    printf 'ZABM_EMBEDDING_MODEL=%s\n' "${RUNTIME_EMBEDDING_MODEL_NAME}"
    printf 'ZABM_PROVIDER_CONFIGURATION=%s\n' "${RUNTIME_PROVIDER_CONFIGURATION}"
    printf 'ZABM_DEBUG=0\n'
    printf 'OLLAMA_MODELS=%s\n' "${MODEL_DIR}"
  } > "${generated}"
  write_if_changed "${CONFIG_FILE}" 600 "${generated}"
}

write_runtime_launcher() {
  local generated

  mkdir -p "${BIN_DIR}"
  generated="$(mktemp)"
  {
    printf '#!/usr/bin/env bash\n'
    printf 'set -Eeuo pipefail\n'
    printf 'source %q\n' "${CONFIG_FILE}"
    printf 'if [[ "${ZABM_RUNTIME_AUTOSTART:-1}" != "0" ]]; then\n'
    printf '  %q >/dev/null\n' "${REPO_ROOT}/scripts/start-runtime-server.sh"
    printf 'fi\n'
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
    if [[ -f "${SERVER_PID_FILE}" ]] && ! kill -0 "$(sed -n '1p' "${SERVER_PID_FILE}")" 2>/dev/null; then
      break
    fi
    sleep 0.5
  done

  if [[ -f "${SERVER_LOG_FILE}" ]]; then
    tail -n 20 "${SERVER_LOG_FILE}" | redact_stream >&2
  fi
  die "model server did not become ready within 60 seconds"
}

start_model_server() {
  local existing_pid
  local response

  mkdir -p "${STATE_DIR}" "${MODEL_DIR}"
  response="$(server_version_response)"
  if response_reports_pinned_version "${response}"; then
    log "model server is already running"
    return
  fi
  if [[ -n "${response}" ]]; then
    die "port 11434 is occupied by a different model server version"
  fi

  if [[ -f "${SERVER_PID_FILE}" ]]; then
    existing_pid="$(sed -n '1p' "${SERVER_PID_FILE}")"
    if [[ -n "${existing_pid}" ]] && kill -0 "${existing_pid}" 2>/dev/null; then
      die "a stale model server process is holding ${SERVER_PID_FILE}"
    fi
    rm -f -- "${SERVER_PID_FILE}"
  fi

  log "starting ${RUNTIME_SERVER_NAME} v${RUNTIME_SERVER_VERSION}"
  OLLAMA_LIBRARY_PATH="${SERVER_VERSION_DIR}/lib/ollama" \
  OLLAMA_HOST="127.0.0.1:11434" \
  OLLAMA_MODELS="${MODEL_DIR}" \
  OLLAMA_KEEP_ALIVE="10m" \
    nohup "${OLLAMA_BIN}" serve >> "${SERVER_LOG_FILE}" 2>&1 < /dev/null &
  printf '%s\n' "$!" > "${SERVER_PID_FILE}"
  wait_for_server
}

download_verified_model() {
  local url="$1"
  local expected_sha256="$2"
  local destination="$3"

  if [[ -f "${destination}" ]] &&
    [[ "$(sha256sum "${destination}" | cut -d' ' -f1)" == "${expected_sha256}" ]]; then
    return
  fi

  mkdir -p "$(dirname -- "${destination}")"
  local partial
  partial="$(mktemp "${destination}.partial.XXXXXX")"
  log "downloading $(basename -- "${destination}")"
  run curl \
    --fail \
    --location \
    --proto '=https' \
    --retry 3 \
    --show-error \
    --silent \
    --output "${partial}" \
    "${url}"
  if ! printf '%s  %s\n' "${expected_sha256}" "${partial}" |
    sha256sum --check --status; then
    rm -f -- "${partial}"
    die "model checksum mismatch for $(basename -- "${destination}")"
  fi
  mv "${partial}" "${destination}"
}

model_is_imported() {
  OLLAMA_LIBRARY_PATH="${SERVER_VERSION_DIR}/lib/ollama" \
    "${OLLAMA_BIN}" list 2>/dev/null |
    awk 'NR > 1 {print $1}' |
    grep -Fxq -e "$1" -e "$1:latest"
}

import_model() {
  local model_name="$1"
  local model_file="$2"
  local modelfile

  if model_is_imported "${model_name}"; then
    return
  fi
  modelfile="$(mktemp)"
  printf 'FROM %s\n' "${model_file}" > "${modelfile}"
  run env \
    OLLAMA_LIBRARY_PATH="${SERVER_VERSION_DIR}/lib/ollama" \
    OLLAMA_HOST="127.0.0.1:11434" \
    "${OLLAMA_BIN}" create "${model_name}" --file "${modelfile}"
  rm -f -- "${modelfile}"
}

fetch_models() {
  local marker

  mkdir -p "${MODEL_DIR}" "${STATE_DIR}"
  marker="${RUNTIME_CHAT_MODEL_SHA256}:${RUNTIME_EMBEDDING_MODEL_SHA256}:${RUNTIME_PROVIDER_CONFIGURATION}"
  if [[ -f "${MODEL_STATE_FILE}" ]] &&
    [[ "$(sed -n '1p' "${MODEL_STATE_FILE}")" == "${marker}" ]] &&
    model_is_imported "${RUNTIME_CHAT_MODEL_NAME}" &&
    model_is_imported "${RUNTIME_EMBEDDING_MODEL_NAME}"; then
    log "pinned models are already imported"
    return
  fi

  download_verified_model \
    "${RUNTIME_CHAT_MODEL_URL}" \
    "${RUNTIME_CHAT_MODEL_SHA256}" \
    "${MODEL_DIR}/${RUNTIME_CHAT_MODEL_FILE}"
  download_verified_model \
    "${RUNTIME_EMBEDDING_MODEL_URL}" \
    "${RUNTIME_EMBEDDING_MODEL_SHA256}" \
    "${MODEL_DIR}/${RUNTIME_EMBEDDING_MODEL_FILE}"

  import_model \
    "${RUNTIME_CHAT_MODEL_NAME}" \
    "${MODEL_DIR}/${RUNTIME_CHAT_MODEL_FILE}"
  import_model \
    "${RUNTIME_EMBEDDING_MODEL_NAME}" \
    "${MODEL_DIR}/${RUNTIME_EMBEDDING_MODEL_FILE}"
  printf '%s\n' "${marker}" > "${MODEL_STATE_FILE}"
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
  export ZABM_RUNTIME_AUTOSTART=0
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
  log "platform: ${OS_PRETTY_NAME} (${OS_ID} ${OS_VERSION_ID}, x86_64)"
  log "runtime dependencies only; development, test, and evaluation dependencies are excluded"
  log "application: CLI and web chat in ${REPO_ROOT}/.venv"
  log "model server: ${RUNTIME_SERVER_NAME} v${RUNTIME_SERVER_VERSION}"
  log "model server sha256: ${RUNTIME_SERVER_SHA256}"
  log "chat model: ${RUNTIME_CHAT_MODEL_FILE} (${RUNTIME_CHAT_MODEL_SHA256})"
  log "embedding model: ${RUNTIME_EMBEDDING_MODEL_FILE} (${RUNTIME_EMBEDDING_MODEL_SHA256})"
  log "model weights: ${MODEL_DIR}"
  log "runtime configuration: ${CONFIG_FILE}"
  log "evidence stores: ${DATA_DIR}/generated"
  log "installed-target smoke: health, local provider, evidence stores, web chat, and one supported answer"
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

  install_runtime_base
  install_model_server
  write_runtime_config
  write_runtime_launcher
  start_model_server
  fetch_models
  prepare_evidence
  run_installed_smoke

  log "target runtime is ready"
  log "CLI: source ${CONFIG_FILE} && ./.venv/bin/python -m zabm ask \"...\""
  log "web: source ${CONFIG_FILE} && ./.venv/bin/python -m zabm web --data-dir ${DATA_DIR}"
  log "launcher: ${BIN_DIR}/zabm-runtime ask \"...\""
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
