#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [[ -n "${CLAUDE_PLUGIN_ROOT:-}" ]]; then
  printf '%s\n' "${CLAUDE_PLUGIN_ROOT}"
elif [[ -n "${CODEX_PLUGIN_ROOT:-}" ]]; then
  printf '%s\n' "${CODEX_PLUGIN_ROOT}"
elif [[ -n "${OPENCLAW_PLUGIN_ROOT:-}" ]]; then
  printf '%s\n' "${OPENCLAW_PLUGIN_ROOT}"
else
  printf '%s\n' "${REPO_ROOT}"
fi
