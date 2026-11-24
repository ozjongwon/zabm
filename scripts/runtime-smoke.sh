#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=install-runtime.sh
source "${SCRIPT_DIR}/install-runtime.sh"

validate_platform
require_installed_runtime
if [[ "${PROVIDER_KIND}" == "local" ]]; then
  verify_ollama_service
fi
run_installed_smoke
