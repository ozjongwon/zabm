#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if [[ ! -x .venv/bin/python ]]; then
  ./scripts/install-dev.sh
fi

exec .venv/bin/python -m zabm download "$@"
