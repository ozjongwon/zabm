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
PROVIDER_KIND="${ZABM_RUNTIME_PROVIDER:-}"
PROVIDER_URL_ARG=""
RUNTIME_PROVIDER_NAME=""
RUNTIME_PROVIDER_URL=""
RUNTIME_EMBEDDING_PROVIDER_KIND=""
RUNTIME_EMBEDDING_PROVIDER_URL=""
RUNTIME_API_KEY=""
AVAILABLE_MODELS=()
readonly VENV_PYTHON="${REPO_ROOT}/.venv/bin/python"
readonly LOCAL_PROVIDER_URL="http://127.0.0.1:11434/v1"
readonly OLLAMA_SERVICE_NAME="${ZABM_OLLAMA_SERVICE:-ollama.service}"

DRY_RUN=false
BASE_INSTALLED=false
RUNTIME_OWNER=""
RUNTIME_GROUP=""
SMOKE_WEB_PID=""
SMOKE_TEMP_FILES=()

usage() {
  cat <<'EOF'
Usage: ./scripts/install-runtime.sh [options]

Installs the supported target runtime on Debian 13 or Ubuntu 24.04 x86_64:
the runtime Python environment, CLI, web chat, generated evidence stores, and
installed-target smoke checks. The selected model provider can be local Ollama
or a remote OpenAI-compatible service.

Options:
  --dry-run            Validate and print the full plan without changing anything
  --runtime-home PATH  Store models and runtime state under PATH
                       (default: /home/ollama)
  --provider NAME      local, deepseek, openai, or openai-compatible
  --model NAME         Chat model to use
  --embedding-model NAME
                       Embedding model to use; omit for chat-only operation
  --provider-url URL   Base URL for a remote OpenAI-compatible provider
  -h, --help           Show this help

Without --provider, an interactive terminal is prompted to choose. Remote API
keys are read from DEEPSEEK_API_KEY, OPENAI_API_KEY, or
ZABM_PROVIDER_API_KEY, or prompted for without echoing. The selected provider
and models are saved in the runtime configuration with mode 600.
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
    -e 's#((OPENAI_API_KEY|DEEPSEEK_API_KEY|ZABM_PROVIDER_API_KEY|ANTHROPIC_API_KEY|LANGSMITH_API_KEY|HF_TOKEN|HUGGING_FACE_HUB_TOKEN|PASSWORD|TOKEN|SECRET)[A-Z0-9_]*[=:][[:space:]]*)[^[:space:]]+#\1<redacted>#Ig' \
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
      --provider)
        (($# >= 2)) || die "--provider requires a value"
        case "$2" in
          local|deepseek|openai|openai-compatible) PROVIDER_KIND="$2" ;;
          *) die "--provider must be local, deepseek, openai, or openai-compatible" ;;
        esac
        shift 2
        ;;
      --model)
        (($# >= 2)) || die "--model requires a value"
        RUNTIME_CHAT_MODEL_NAME="$2"
        shift 2
        ;;
      --embedding-model)
        (($# >= 2)) || die "--embedding-model requires a value"
        RUNTIME_EMBEDDING_MODEL_NAME="$2"
        shift 2
        ;;
      --provider-url)
        (($# >= 2)) || die "--provider-url requires a value"
        PROVIDER_URL_ARG="$2"
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

prompt_value() {
  local label="$1"
  local default="$2"
  local variable="$3"
  local answer=""

  if [[ ! -t 0 ]]; then
    printf -v "${variable}" '%s' "${default}"
    return
  fi
  if [[ -n "${default}" ]]; then
    read -r -p "${label} [${default}]: " answer ||
      die "input ended while reading ${label}"
  else
    read -r -p "${label}: " answer ||
      die "input ended while reading ${label}"
  fi
  printf -v "${variable}" '%s' "${answer:-${default}}"
}

prompt_required_value() {
  local label="$1"
  local variable="$2"
  local answer=""

  [[ -t 0 ]] ||
    die "${label} is required; pass the corresponding option or environment variable"
  read -r -p "${label}: " answer ||
    die "input ended while reading ${label}"
  [[ -n "${answer}" ]] || die "${label} is required"
  printf -v "${variable}" '%s' "${answer}"
}

prompt_secret() {
  local variable="$1"
  local environment_name="$2"
  local fallback_environment="${3:-}"

  if [[ -n "${!environment_name:-}" ]]; then
    printf -v "${variable}" '%s' "${!environment_name}"
    log "using ${environment_name} from the environment"
    return
  fi
  if [[ -n "${fallback_environment}" && -n "${!fallback_environment:-}" ]]; then
    printf -v "${variable}" '%s' "${!fallback_environment}"
    log "using ${fallback_environment} from the environment"
    return
  fi
  [[ -t 0 ]] ||
    die "${environment_name} is required; export it and rerun the installer"
  read -r -s -p "${environment_name}: " RUNTIME_API_KEY ||
    die "input ended while reading ${environment_name}"
  printf '\n'
  [[ -n "${RUNTIME_API_KEY}" ]] ||
    die "${environment_name} is required"
}

choose_provider_kind() {
  local choice=""

  if [[ -n "${PROVIDER_KIND}" ]]; then
    return
  fi
  if [[ ! -t 0 ]]; then
    PROVIDER_KIND=deepseek
    log "no provider option supplied in a non-interactive session; using DeepSeek chat with local Ollama embeddings"
    return
  fi
  printf '%s\n' \
    'Select the model provider:' \
    '  1) Local Ollama models' \
    '  2) DeepSeek chat with local Ollama embeddings (default)' \
    '  3) OpenAI' \
    '  4) Another OpenAI-compatible service'
  read -r -p 'Provider [2]: ' choice ||
    die "input ended while choosing a provider"
  case "${choice:-2}" in
    1) PROVIDER_KIND=local ;;
    2) PROVIDER_KIND=deepseek ;;
    3) PROVIDER_KIND=openai ;;
    4) PROVIDER_KIND=openai-compatible ;;
    *) die "provider must be 1, 2, 3, or 4" ;;
  esac
}

configure_local_embedding() {
  RUNTIME_EMBEDDING_PROVIDER_KIND=local
  RUNTIME_EMBEDDING_PROVIDER_URL="${LOCAL_PROVIDER_URL}"
  check_ollama_prerequisites
  verify_ollama_service
  load_installed_models
  print_available_models
  RUNTIME_EMBEDDING_MODEL_NAME="$(select_embedding_model)"
  [[ "${RUNTIME_EMBEDDING_MODEL_NAME}" != "not-configured" ]] ||
    die "DeepSeek chat requires a local Ollama embedding model; install or select one with ZABM_EMBEDDING_MODEL"
  log "selected local Ollama embedding model: ${RUNTIME_EMBEDDING_MODEL_NAME}"
}

configure_remote_provider() {
  local default_embedding=""
  local default_model=""
  local default_url=""
  local key_environment=""

  case "${PROVIDER_KIND}" in
    deepseek)
      RUNTIME_PROVIDER_NAME=deepseek
      default_url="${DEEPSEEK_BASE_URL:-https://api.deepseek.com}"
      default_model="${RUNTIME_CHAT_MODEL_NAME:-${DEEPSEEK_MODEL:-deepseek-flash}}"
      key_environment=DEEPSEEK_API_KEY
      ;;
    openai)
      RUNTIME_PROVIDER_NAME=openai
      default_url="${OPENAI_BASE_URL:-https://api.openai.com/v1}"
      default_model="${RUNTIME_CHAT_MODEL_NAME:-${OPENAI_MODEL:-}}"
      default_embedding="${RUNTIME_EMBEDDING_MODEL_NAME:-${OPENAI_EMBEDDING_MODEL:-text-embedding-3-small}}"
      key_environment=OPENAI_API_KEY
      ;;
    openai-compatible)
      RUNTIME_PROVIDER_NAME=openai-compatible
      default_url="${PROVIDER_URL_ARG:-${ZABM_PROVIDER_URL:-}}"
      default_model="${RUNTIME_CHAT_MODEL_NAME}"
      default_embedding="${RUNTIME_EMBEDDING_MODEL_NAME:-not-configured}"
      key_environment=ZABM_PROVIDER_API_KEY
      ;;
  esac

  if [[ "${PROVIDER_KIND}" != "openai-compatible" && -n "${PROVIDER_URL_ARG}" ]]; then
    default_url="${PROVIDER_URL_ARG}"
  fi
  prompt_value "${RUNTIME_PROVIDER_NAME} base URL" "${default_url}" RUNTIME_PROVIDER_URL
  [[ -n "${RUNTIME_PROVIDER_URL}" ]] ||
    die "a provider URL is required for ${RUNTIME_PROVIDER_NAME}"
  if [[ -n "${default_model}" ]]; then
    prompt_value "${RUNTIME_PROVIDER_NAME} chat model" "${default_model}" RUNTIME_CHAT_MODEL_NAME
  else
    prompt_required_value "${RUNTIME_PROVIDER_NAME} chat model" RUNTIME_CHAT_MODEL_NAME
  fi
  if [[ "${PROVIDER_KIND}" == "deepseek" ]]; then
    configure_local_embedding
  else
    prompt_value \
      "${RUNTIME_PROVIDER_NAME} embedding model (blank to skip)" \
      "${default_embedding}" \
      RUNTIME_EMBEDDING_MODEL_NAME
    case "${RUNTIME_EMBEDDING_MODEL_NAME}" in
      0|none) RUNTIME_EMBEDDING_MODEL_NAME=not-configured ;;
    esac
    RUNTIME_EMBEDDING_MODEL_NAME="${RUNTIME_EMBEDDING_MODEL_NAME:-not-configured}"
    RUNTIME_EMBEDDING_PROVIDER_KIND=remote
    RUNTIME_EMBEDDING_PROVIDER_URL="${RUNTIME_PROVIDER_URL}"
  fi
  if [[ "${key_environment}" == "ZABM_PROVIDER_API_KEY" ]]; then
    prompt_secret RUNTIME_API_KEY "${key_environment}"
  else
    prompt_secret RUNTIME_API_KEY "${key_environment}" ZABM_PROVIDER_API_KEY
  fi
}

configure_local_provider() {
  RUNTIME_PROVIDER_NAME=openai-compatible
  RUNTIME_PROVIDER_URL="${LOCAL_PROVIDER_URL}"
  RUNTIME_EMBEDDING_PROVIDER_KIND=local
  RUNTIME_EMBEDDING_PROVIDER_URL="${LOCAL_PROVIDER_URL}"
  check_ollama_prerequisites
  verify_ollama_service
  select_models
}

configure_provider() {
  choose_provider_kind
  case "${PROVIDER_KIND}" in
    local) configure_local_provider ;;
    deepseek|openai|openai-compatible) configure_remote_provider ;;
    *) die "unsupported runtime provider: ${PROVIDER_KIND}" ;;
  esac
}

prepare_dry_run_plan() {
  PROVIDER_KIND="${PROVIDER_KIND:-deepseek}"
  case "${PROVIDER_KIND}" in
    local)
      RUNTIME_PROVIDER_NAME=openai-compatible
      RUNTIME_PROVIDER_URL="${LOCAL_PROVIDER_URL}"
      RUNTIME_EMBEDDING_PROVIDER_KIND=local
      RUNTIME_EMBEDDING_PROVIDER_URL="${LOCAL_PROVIDER_URL}"
      ;;
    deepseek)
      RUNTIME_PROVIDER_NAME=deepseek
      RUNTIME_PROVIDER_URL="${PROVIDER_URL_ARG:-${DEEPSEEK_BASE_URL:-https://api.deepseek.com}}"
      RUNTIME_CHAT_MODEL_NAME="${RUNTIME_CHAT_MODEL_NAME:-${DEEPSEEK_MODEL:-deepseek-flash}}"
      RUNTIME_EMBEDDING_PROVIDER_KIND=local
      RUNTIME_EMBEDDING_PROVIDER_URL="${LOCAL_PROVIDER_URL}"
      ;;
    openai)
      RUNTIME_PROVIDER_NAME=openai
      RUNTIME_PROVIDER_URL="${PROVIDER_URL_ARG:-${OPENAI_BASE_URL:-https://api.openai.com/v1}}"
      RUNTIME_CHAT_MODEL_NAME="${RUNTIME_CHAT_MODEL_NAME:-${OPENAI_MODEL:-}}"
      RUNTIME_EMBEDDING_MODEL_NAME="${RUNTIME_EMBEDDING_MODEL_NAME:-${OPENAI_EMBEDDING_MODEL:-text-embedding-3-small}}"
      RUNTIME_EMBEDDING_PROVIDER_KIND=remote
      RUNTIME_EMBEDDING_PROVIDER_URL="${RUNTIME_PROVIDER_URL}"
      ;;
    openai-compatible)
      RUNTIME_PROVIDER_NAME=openai-compatible
      RUNTIME_PROVIDER_URL="${PROVIDER_URL_ARG:-${ZABM_PROVIDER_URL:-}}"
      RUNTIME_EMBEDDING_PROVIDER_KIND=remote
      RUNTIME_EMBEDDING_PROVIDER_URL="${RUNTIME_PROVIDER_URL}"
      ;;
    *)
      die "unsupported runtime provider: ${PROVIDER_KIND}"
      ;;
  esac
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
  source_runtime_config
  PROVIDER_KIND="${ZABM_RUNTIME_PROVIDER_KIND:-local}"
  RUNTIME_PROVIDER_NAME="${ZABM_PROVIDER:-${RUNTIME_PROVIDER_NAME}}"
  RUNTIME_PROVIDER_URL="${ZABM_PROVIDER_URL:-${RUNTIME_PROVIDER_URL}}"
  RUNTIME_EMBEDDING_PROVIDER_KIND="${ZABM_RUNTIME_EMBEDDING_PROVIDER_KIND:-}"
  RUNTIME_EMBEDDING_PROVIDER_URL="${ZABM_EMBEDDING_PROVIDER_URL:-${RUNTIME_EMBEDDING_PROVIDER_URL}}"
  if [[ -z "${RUNTIME_EMBEDDING_PROVIDER_KIND}" ]]; then
    if [[ "${PROVIDER_KIND}" == "local" ]]; then
      RUNTIME_EMBEDDING_PROVIDER_KIND=local
    else
      RUNTIME_EMBEDDING_PROVIDER_KIND=remote
    fi
  fi
  if [[ "${PROVIDER_KIND}" == "local" || "${RUNTIME_EMBEDDING_PROVIDER_KIND}" == "local" ]]; then
    resolve_ollama_bin ||
      fail_ollama_prerequisite "Ollama v${RUNTIME_SERVER_VERSION} was not found"
  fi
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
  case "${PROVIDER_KIND}" in
    local)
      provider_configuration="ollama-v${RUNTIME_SERVER_VERSION},${RUNTIME_CHAT_MODEL_NAME},${RUNTIME_EMBEDDING_MODEL_NAME},temperature=0,seed=0"
      ;;
    deepseek)
      provider_configuration="deepseek-v1,${RUNTIME_CHAT_MODEL_NAME},ollama,${RUNTIME_EMBEDDING_MODEL_NAME},temperature=0"
      ;;
    *)
      provider_configuration="${RUNTIME_PROVIDER_NAME}-v1,${RUNTIME_CHAT_MODEL_NAME},${RUNTIME_EMBEDDING_MODEL_NAME},temperature=0,seed=0"
      ;;
  esac

  mkdir -p "${RUNTIME_CONFIG_DIR}"
  generated="$(mktemp)"
  {
    printf '# Generated by ./scripts/install-runtime.sh; re-running replaces this file.\n'
    printf 'ZABM_RUNTIME_PROVIDER_KIND=%q\n' "${PROVIDER_KIND}"
    printf 'ZABM_PROVIDER=%q\n' "${RUNTIME_PROVIDER_NAME}"
    printf 'ZABM_PROVIDER_URL=%q\n' "${RUNTIME_PROVIDER_URL}"
    printf 'ZABM_RUNTIME_EMBEDDING_PROVIDER_KIND=%q\n' "${RUNTIME_EMBEDDING_PROVIDER_KIND}"
    printf 'ZABM_EMBEDDING_PROVIDER_URL=%q\n' "${RUNTIME_EMBEDDING_PROVIDER_URL}"
    printf 'ZABM_MODEL=%q\n' "${RUNTIME_CHAT_MODEL_NAME}"
    printf 'ZABM_EMBEDDING_MODEL=%q\n' "${RUNTIME_EMBEDDING_MODEL_NAME}"
    printf 'ZABM_PROVIDER_CONFIGURATION=%q\n' "${provider_configuration}"
    printf 'ZABM_DEBUG=0\n'
    case "${PROVIDER_KIND}" in
      local)
        printf 'ZABM_PROVIDER_API_KEY=\n'
        printf 'OLLAMA_MODELS=%q\n' "${MODEL_DIR}"
        ;;
      deepseek)
        printf 'DEEPSEEK_API_KEY=%q\n' "${RUNTIME_API_KEY}"
        ;;
      openai)
        printf 'OPENAI_API_KEY=%q\n' "${RUNTIME_API_KEY}"
        ;;
      openai-compatible)
        printf 'ZABM_PROVIDER_API_KEY=%q\n' "${RUNTIME_API_KEY}"
        ;;
    esac
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

print_available_models() {
  local index

  printf '%s\n' 'Installed Ollama models:'
  for index in "${!AVAILABLE_MODELS[@]}"; do
    printf '  %d) %s\n' "$((index + 1))" "${AVAILABLE_MODELS[index]}"
  done
}

model_from_choice() {
  local choice="$1"
  local index

  if [[ "${choice}" =~ ^[1-9][0-9]*$ ]]; then
    index=$((choice - 1))
    ((index < ${#AVAILABLE_MODELS[@]})) ||
      die "model selection ${choice} is out of range"
    printf '%s\n' "${AVAILABLE_MODELS[index]}"
    return
  fi
  lookup_available_model "${choice}" ||
    die "model '${choice}' is not installed; choose one of: $(available_models_csv)"
}

default_chat_model() {
  local model

  for model in "${AVAILABLE_MODELS[@]}"; do
    if ! model_looks_like_embedding "${model}"; then
      printf '%s\n' "${model}"
      return
    fi
  done
  printf '%s\n' "${AVAILABLE_MODELS[0]}"
}

default_embedding_model() {
  local model

  for model in "${AVAILABLE_MODELS[@]}"; do
    if model_looks_like_embedding "${model}"; then
      printf '%s\n' "${model}"
      return
    fi
  done
  printf '%s\n' "not-configured"
}

select_chat_model() {
  local requested="${RUNTIME_CHAT_MODEL_NAME}"
  local default_model
  local choice=""

  if [[ -n "${requested}" ]]; then
    lookup_available_model "${requested}" ||
      die "requested chat model '${requested}' is not installed; available models: $(available_models_csv)"
    return
  fi
  default_model="$(default_chat_model)"
  if [[ -t 0 ]]; then
    read -r -p "Chat model number or name [${default_model}]: " choice ||
      die "input ended while choosing the chat model"
  fi
  model_from_choice "${choice:-${default_model}}"
}

select_embedding_model() {
  local requested="${RUNTIME_EMBEDDING_MODEL_NAME}"
  local default_model
  local choice=""

  if [[ -n "${requested}" ]]; then
    if [[ "${requested}" == "not-configured" ]]; then
      printf '%s\n' "${requested}"
      return
    fi
    lookup_available_model "${requested}" ||
      die "requested embedding model '${requested}' is not installed; available models: $(available_models_csv)"
    return
  fi
  default_model="$(default_embedding_model)"
  if [[ -t 0 ]]; then
    read -r -p "Embedding model number/name, or 0 to skip [${default_model}]: " choice ||
      die "input ended while choosing the embedding model"
  fi
  choice="${choice:-${default_model}}"
  if [[ "${choice}" == "0" || "${choice}" == "none" || "${choice}" == "not-configured" ]]; then
    printf '%s\n' "not-configured"
    return
  fi
  model_from_choice "${choice}"
}

select_models() {
  load_installed_models
  print_available_models
  RUNTIME_CHAT_MODEL_NAME="$(select_chat_model)"
  RUNTIME_EMBEDDING_MODEL_NAME="$(select_embedding_model)"
  log "selected chat model: ${RUNTIME_CHAT_MODEL_NAME}"
  log "selected embedding model: ${RUNTIME_EMBEDDING_MODEL_NAME}"
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
  # Generated with mode 600; remote-provider credentials may be present.
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
if payload["status"] != "supported":
    failure = payload.get("failure") or {}
    routing = payload.get("routing") or {}
    print(
        f"{label}: expected supported, got {payload['status']}; "
        f"failure={failure.get('message', 'none')}; "
        f"intent={routing.get('intent', 'unknown')}; "
        f"normalized_question={routing.get('normalized_question', 'unknown')}",
        file=sys.stderr,
    )
    raise SystemExit(1)
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

  log "smoke: ${ZABM_PROVIDER} provider"
  if [[ -n "${ZABM_EMBEDDING_MODEL:-}" && "${ZABM_EMBEDDING_MODEL}" != "not-configured" ]]; then
    run "${VENV_PYTHON}" -m zabm provider-smoke
  else
    log "smoke: embeddings are not configured; checking chat only"
    run "${VENV_PYTHON}" -m zabm provider-smoke --skip-embeddings
  fi

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
  if [[ "${PROVIDER_KIND}" == "local" || "${RUNTIME_EMBEDDING_PROVIDER_KIND}" == "local" ]]; then
    log "runtime home: ${RUNTIME_HOME}"
    log "Ollama prerequisite: preinstalled ${RUNTIME_SERVER_NAME} v${RUNTIME_SERVER_VERSION} and active ${OLLAMA_SERVICE_NAME}"
    log "model selection: existing models reported by '${OLLAMA_BIN:-ollama} list'"
  fi
  if [[ "${PROVIDER_KIND}" == "local" ]]; then
    log "chat provider: local Ollama"
  else
    log "provider: ${RUNTIME_PROVIDER_NAME} at ${RUNTIME_PROVIDER_URL}"
    log "remote credentials: saved with runtime configuration, not printed"
  fi
  if [[ "${RUNTIME_EMBEDDING_PROVIDER_KIND}" == "local" ]]; then
    log "embedding provider: local Ollama at ${RUNTIME_EMBEDDING_PROVIDER_URL}"
  else
    log "embedding provider: ${RUNTIME_EMBEDDING_PROVIDER_URL:-${RUNTIME_PROVIDER_URL}}"
  fi
  log "chat model: ${RUNTIME_CHAT_MODEL_NAME:-selected during installation}"
  log "embedding model: ${RUNTIME_EMBEDDING_MODEL_NAME:-selected during installation}"
  log "model downloads and imports: none"
  log "runtime configuration: ${CONFIG_FILE}"
  log "evidence stores: ${DATA_DIR}/generated"
  log "installed-target smoke: health, selected provider, evidence stores, web chat, and one supported answer"
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

  if [[ "${DRY_RUN}" == true ]]; then
    prepare_dry_run_plan
    print_plan
    log "dry run complete; no changes made"
    return
  fi

  configure_provider
  if [[ "${PROVIDER_KIND}" == "local" || "${RUNTIME_EMBEDDING_PROVIDER_KIND}" == "local" ]]; then
    check_nvidia_prerequisites
  fi

  print_plan
  if [[ "${PROVIDER_KIND}" == "local" || "${RUNTIME_EMBEDDING_PROVIDER_KIND}" == "local" ]]; then
    prepare_runtime_directories
  fi
  log "starting installation; use --dry-run to inspect the plan without changes"
  install_runtime_base
  write_runtime_config
  write_runtime_launcher
  prepare_evidence
  run_installed_smoke

  log "target runtime is ready"
  log "CLI: ${BIN_DIR}/zabm-runtime ask \"...\""
  log "web: ${BIN_DIR}/zabm-runtime web --data-dir ${DATA_DIR}"
  if [[ "${PROVIDER_KIND}" == "local" || "${RUNTIME_EMBEDDING_PROVIDER_KIND}" == "local" ]]; then
    log "server: sudo systemctl status ${OLLAMA_SERVICE_NAME}"
  else
    log "provider: ${RUNTIME_PROVIDER_NAME}"
  fi
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
