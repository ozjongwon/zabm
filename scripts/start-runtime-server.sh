#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=install-runtime.sh
source "${SCRIPT_DIR}/install-runtime.sh"

validate_platform
require_installed_runtime
if [[ "${PROVIDER_KIND}" != "local" && "${RUNTIME_EMBEDDING_PROVIDER_KIND}" != "local" ]]; then
  log "runtime uses the remote ${RUNTIME_PROVIDER_NAME} provider; there is no local model server"
  exit 0
fi
check_ollama_prerequisites
wait_for_server
log "${OLLAMA_SERVICE_NAME} is managed outside this script; use systemctl to start, stop, enable, or inspect it"
if [[ "${PROVIDER_KIND}" != "local" ]]; then
  log "chat uses ${RUNTIME_PROVIDER_NAME}; local Ollama provides embeddings"
fi
