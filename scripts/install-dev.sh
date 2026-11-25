#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
readonly UV_VERSION="0.8.22"
readonly PYTHON_VERSION="3.13.5"
readonly OS_RELEASE_FILE="${ZABM_OS_RELEASE_FILE:-/etc/os-release}"
readonly UV_INSTALL_DIR="${HOME:?HOME must be set}/.local/bin"
readonly VENV_DIR="${REPO_ROOT}/.venv"
readonly REQUIREMENTS_DIR="${REPO_ROOT}/requirements"

readonly RUNTIME_APT_PACKAGES=(
  acl
  ca-certificates
  curl
  libgomp1
  zstd
)

readonly DEVELOPMENT_APT_PACKAGES=(
  build-essential
  ca-certificates
  curl
  git
  libffi-dev
  libsqlite3-dev
  libssl-dev
  pkg-config
  zlib1g-dev
)

PROFILE="development"
DRY_RUN=false
UV_BIN=""
VENV_PYTHON=""
TEMP_DIR=""
APT_PACKAGES=()

usage() {
  cat <<'EOF'
Usage: ./scripts/install-dev.sh [--profile development|runtime] [--dry-run]

Installs the pinned development environment on Debian 13 or Ubuntu 24.04 x86_64.

Profiles:
  development  Runtime, development, test, and evaluation dependencies (default)
  runtime      Runtime dependencies only

Options:
  --dry-run    Validate the machine and print the install plan without changing it
  -h, --help   Show this help
EOF
}

log() {
  printf 'zabm bootstrap: %s\n' "$*"
}

warn() {
  printf 'zabm bootstrap: warning: %s\n' "$*" >&2
}

die() {
  printf 'zabm bootstrap: error: %s\n' "$*" >&2
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
  if [[ -n "${TEMP_DIR}" && -d "${TEMP_DIR}" ]]; then
    rm -rf -- "${TEMP_DIR}"
  fi
}
trap cleanup EXIT

parse_args() {
  while (( $# > 0 )); do
    case "$1" in
      --profile)
        (($# >= 2)) || die "--profile requires development or runtime"
        PROFILE="$2"
        shift 2
        ;;
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

  [[ "${PROFILE}" == "development" || "${PROFILE}" == "runtime" ]] ||
    die "--profile must be development or runtime"
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

check_inputs() {
  local path
  local required_inputs=(
    "${REPO_ROOT}/pyproject.toml"
    "${REPO_ROOT}/.python-version"
    "${REQUIREMENTS_DIR}/runtime.lock"
  )

  if [[ "${PROFILE}" == "development" ]]; then
    required_inputs+=(
      "${REQUIREMENTS_DIR}/development.lock"
      "${REQUIREMENTS_DIR}/test.lock"
      "${REQUIREMENTS_DIR}/evaluation.lock"
    )
  fi

  for path in "${required_inputs[@]}"; do
    [[ -f "${path}" ]] || die "required installer input is missing: ${path#"${REPO_ROOT}/"}"
  done
}

select_apt_packages() {
  if [[ "${PROFILE}" == "runtime" ]]; then
    APT_PACKAGES=("${RUNTIME_APT_PACKAGES[@]}")
  else
    APT_PACKAGES=("${DEVELOPMENT_APT_PACKAGES[@]}")
  fi
}

check_nvidia_prerequisites() {
  if command -v nvidia-smi >/dev/null 2>&1; then
    log "NVIDIA driver detected; the installer will not change GPU drivers"
    return
  fi

  warn "nvidia-smi was not found; CPU execution is not covered by the local acceptance claim"
  warn "install the NVIDIA kernel driver through the official Debian or Ubuntu distribution packages, reboot, and confirm 'nvidia-smi' works"
  warn "this installer intentionally does not install or replace the kernel GPU driver"
}

install_system_packages() {
  local sudo_command=()

  command -v apt-get >/dev/null 2>&1 ||
    die "apt-get is required on supported Debian and Ubuntu systems"

  if (( EUID == 0 )); then
    sudo_command=()
  elif command -v sudo >/dev/null 2>&1; then
    sudo_command=(sudo)
  else
    die "system package installation requires root or sudo"
  fi

  log "installing pinned system prerequisites with apt"
  run "${sudo_command[@]}" apt-get update
  run "${sudo_command[@]}" env DEBIAN_FRONTEND=noninteractive apt-get install \
    --yes \
    --no-install-recommends \
    "${APT_PACKAGES[@]}"
}

uv_reports_pinned_version() {
  local candidate="$1"
  local reported

  [[ -x "${candidate}" ]] || return 1
  reported="$("${candidate}" --version 2>/dev/null || true)"
  [[ "${reported}" == "uv ${UV_VERSION}" ]]
}

ensure_uv() {
  local candidate
  local installer

  if candidate="$(command -v uv 2>/dev/null || true)" &&
    uv_reports_pinned_version "${candidate}"; then
    UV_BIN="${candidate}"
    log "using uv ${UV_VERSION}"
    return
  fi

  candidate="${UV_INSTALL_DIR}/uv"
  if uv_reports_pinned_version "${candidate}"; then
    UV_BIN="${candidate}"
    export PATH="${UV_INSTALL_DIR}:${PATH}"
    log "using uv ${UV_VERSION}"
    return
  fi

  case "$(uname -m)" in
    x86_64) ;;
    *) die "the pinned uv installer supports x86_64 only" ;;
  esac

  TEMP_DIR="$(mktemp -d)"
  installer="${TEMP_DIR}/install-uv.sh"
  log "installing uv ${UV_VERSION} into ${UV_INSTALL_DIR}"
  run curl \
    --fail \
    --location \
    --proto '=https' \
    --show-error \
    --silent \
    --tlsv1.2 \
    --output "${installer}" \
    "https://astral.sh/uv/${UV_VERSION}/install.sh"
  bash -n "${installer}" ||
    die "downloaded uv installer failed its syntax check"
  run env \
    UV_INSTALL_DIR="${UV_INSTALL_DIR}" \
    UV_NO_MODIFY_PATH=1 \
    sh "${installer}"

  UV_BIN="${UV_INSTALL_DIR}/uv"
  uv_reports_pinned_version "${UV_BIN}" ||
    die "uv ${UV_VERSION} installation did not produce the expected binary"
  export PATH="${UV_INSTALL_DIR}:${PATH}"
}

ensure_python_environment() {
  log "installing managed Python ${PYTHON_VERSION}"
  run "${UV_BIN}" python install "${PYTHON_VERSION}"

  log "creating the pinned virtual environment"
  run "${UV_BIN}" venv \
    --clear \
    --python "${PYTHON_VERSION}" \
    "${VENV_DIR}"

  VENV_PYTHON="${VENV_DIR}/bin/python"
  [[ -x "${VENV_PYTHON}" ]] ||
    die "virtual environment Python was not created at .venv/bin/python"
  [[ "$("${VENV_PYTHON}" -c 'import platform; print(platform.python_version())')" == "${PYTHON_VERSION}" ]] ||
    die "virtual environment does not use Python ${PYTHON_VERSION}"
}

install_python_dependencies() {
  local dependency_files=(
    "${REQUIREMENTS_DIR}/runtime.lock"
  )

  if [[ "${PROFILE}" == "development" ]]; then
    dependency_files+=(
      "${REQUIREMENTS_DIR}/development.lock"
      "${REQUIREMENTS_DIR}/test.lock"
      "${REQUIREMENTS_DIR}/evaluation.lock"
    )
  fi

  log "installing ${PROFILE} Python dependencies from hash-locked files"
  local install_args=(
    pip
    install
    --python "${VENV_PYTHON}"
    --require-hashes
    --no-deps
  )
  local dependency_file
  for dependency_file in "${dependency_files[@]}"; do
    install_args+=(-r "${dependency_file}")
  done
  run "${UV_BIN}" "${install_args[@]}"
  run "${UV_BIN}" pip check --python "${VENV_PYTHON}"
}

install_application() {
  log "installing the zabm application and CLI into the virtual environment"
  run "${UV_BIN}" pip install \
    --python "${VENV_PYTHON}" \
    --no-deps \
    --no-build-isolation \
    --editable "${REPO_ROOT}"
  run "${UV_BIN}" pip check --python "${VENV_PYTHON}"
}

run_smoke_checks() {
  log "running the CLI health check"
  "${VENV_PYTHON}" -m zabm health

  if [[ "${PROFILE}" == "development" ]]; then
    log "running the automated test suite"
    "${VENV_PYTHON}" -m pytest -q
  fi
}

print_plan() {
  local package_list
  package_list="$(printf '%s ' "${APT_PACKAGES[@]}")"
  package_list="${package_list% }"

  log "platform: ${OS_PRETTY_NAME} (${OS_ID} ${OS_VERSION_ID}, x86_64)"
  log "profile: ${PROFILE}"
  log "uv: uv ${UV_VERSION}"
  log "python: Python ${PYTHON_VERSION}"
  log "system packages: ${package_list}"
  if [[ "${PROFILE}" == "development" ]]; then
    log "dependencies: runtime, development, test, and evaluation"
  else
    log "dependencies: runtime dependencies only"
  fi
}

main() {
  parse_args "$@"
  validate_platform
  select_apt_packages
  check_inputs
  check_nvidia_prerequisites

  if [[ "${DRY_RUN}" == true ]]; then
    print_plan
    log "dry run complete; no changes made"
    return
  fi

  install_system_packages
  ensure_uv
  ensure_python_environment
  install_python_dependencies
  install_application
  run_smoke_checks

  log "development environment is ready"
  log "health: ./.venv/bin/python -m zabm health"
  if [[ "${PROFILE}" == "development" ]]; then
    log "tests: ./.venv/bin/python -m pytest"
  fi
}

main "$@"
