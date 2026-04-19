#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$("${SCRIPT_DIR}/plugin-root.sh")"

exec uv --directory "${REPO_ROOT}" run paper-distill-server
