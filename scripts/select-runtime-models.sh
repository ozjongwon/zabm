#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=install-runtime.sh
source "${SCRIPT_DIR}/install-runtime.sh"

parse_args "$@"
validate_platform

if [[ "${DRY_RUN}" == true ]]; then
  prepare_dry_run_plan
  print_plan
  log "dry run complete; no changes made"
  exit 0
fi

require_installed_runtime
configure_provider
write_runtime_config
log "runtime provider and models saved to ${CONFIG_FILE}"
