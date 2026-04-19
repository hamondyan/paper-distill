#!/usr/bin/env bash
# Bootstrap the current Paper Distill v3 vault structure.
set -euo pipefail

VAULT_PATH="${1:-}"

if [[ -z "$VAULT_PATH" ]]; then
  echo "Usage: bootstrap.sh <obsidian-vault-path>"
  echo "  e.g.: bootstrap.sh /Users/you/Documents/knowledge_repo"
  exit 1
fi

echo "Creating Paper Distill v3 vault structure at: ${VAULT_PATH}"

mkdir -p "${VAULT_PATH}/raw/evidence"
mkdir -p "${VAULT_PATH}/wiki/papers"
mkdir -p "${VAULT_PATH}/wiki/concepts"
mkdir -p "${VAULT_PATH}/insights/ideas"
mkdir -p "${VAULT_PATH}/insights/conversations"
mkdir -p "${VAULT_PATH}/exports/presentations"
mkdir -p "${VAULT_PATH}/.state"

if [[ ! -f "${VAULT_PATH}/vault-log.md" ]]; then
  cat > "${VAULT_PATH}/vault-log.md" << 'EOF'
# Vault Operation Log

| Timestamp | Action | Resource ID | Status | Notes |
|-----------|--------|-------------|--------|-------|
EOF
fi

echo ""
echo "Bootstrap complete."
echo ""
echo "Vault root: ${VAULT_PATH}"
echo ""
echo "Directories created:"
echo "  raw/evidence/"
echo "  wiki/papers/"
echo "  wiki/concepts/"
echo "  insights/ideas/"
echo "  insights/conversations/"
echo "  exports/presentations/"
echo "  .state/"
echo "  vault-log.md"
