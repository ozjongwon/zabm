#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=install-runtime.sh
source "${SCRIPT_DIR}/install-runtime.sh"

validate_platform
require_installed_runtime
verify_ollama_service
run_installed_smoke
