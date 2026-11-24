#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=install-runtime.sh
source "${SCRIPT_DIR}/install-runtime.sh"

validate_platform
check_nvidia_prerequisites
require_installed_runtime
verify_ollama_service
fetch_models
