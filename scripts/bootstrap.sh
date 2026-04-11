#!/usr/bin/env bash
# Bootstrap the current Paper Distill vault structure in Obsidian.
set -euo pipefail

VAULT_PATH="${1:-}"

if [[ -z "$VAULT_PATH" ]]; then
  echo "Usage: bootstrap.sh <obsidian-vault-path>"
  echo "  e.g.: bootstrap.sh /Users/you/Documents/knowledge_repo"
  exit 1
fi

PD_ROOT="${VAULT_PATH}/Paper Distill"

echo "Creating Paper Distill vault structure at: ${PD_ROOT}"

mkdir -p "${PD_ROOT}/inbox"
mkdir -p "${PD_ROOT}/sources/evidence"
mkdir -p "${PD_ROOT}/zotero/imports"
mkdir -p "${PD_ROOT}/wiki/papers"
mkdir -p "${PD_ROOT}/wiki/concepts"
mkdir -p "${PD_ROOT}/wiki/methods"
mkdir -p "${PD_ROOT}/wiki/topics"
mkdir -p "${PD_ROOT}/insights/queries"
mkdir -p "${PD_ROOT}/insights/ideas"
mkdir -p "${PD_ROOT}/insights/dialogues"
mkdir -p "${PD_ROOT}/insights/digests"
mkdir -p "${PD_ROOT}/insights/memory-promotions"
mkdir -p "${PD_ROOT}/memory"
mkdir -p "${PD_ROOT}/.state/ir"
mkdir -p "${PD_ROOT}/.state/memory"

write_index() {
  local path="$1"
  local section="$2"
  local title="$3"
  local body="$4"

  if [[ ! -f "$path" ]]; then
    cat > "$path" << EOF
---
type: index
section: ${section}
updated: ""
---

# ${title}

${body}
EOF
  fi
}

if [[ ! -f "${PD_ROOT}/index.md" ]]; then
cat > "${PD_ROOT}/index.md" << 'EOF'
# Paper Distill

Use the MCP tools for library state and queries. This note is only a human landing page.
EOF
fi

if [[ ! -f "${PD_ROOT}/log.md" ]]; then
cat > "${PD_ROOT}/log.md" << 'EOF'
# Paper Distill Log

Append-only timeline of ingest, query, compile, maintenance, and idea activity.
EOF
fi

write_index "${PD_ROOT}/_index.md" "master" "Paper Distill" "Minimal landing note. Use query-library for current state."
write_index "${PD_ROOT}/inbox/_index.md" "inbox" "Inbox" "Candidate papers awaiting human review."
write_index "${PD_ROOT}/sources/_index.md" "sources" "Sources" "Evidence-first source layer for approved papers."
write_index "${PD_ROOT}/sources/evidence/_index.md" "sources/evidence" "Source Evidence" "Cleaned source captures and sidecars."
write_index "${PD_ROOT}/zotero/_index.md" "zotero" "Zotero Handoff" "Local-first Zotero handoff files."
write_index "${PD_ROOT}/zotero/imports/_index.md" "zotero/imports" "Zotero Imports" "Import packs generated for local-first Zotero workflows."
write_index "${PD_ROOT}/wiki/_index.md" "wiki" "Wiki" "Knowledge pages derived from source evidence and hidden IR."
write_index "${PD_ROOT}/wiki/papers/_index.md" "wiki/papers" "Compiled Papers" "Canonical per-paper work pages."
write_index "${PD_ROOT}/wiki/concepts/_index.md" "wiki/concepts" "Concepts" "Concept encyclopedia pages."
write_index "${PD_ROOT}/wiki/methods/_index.md" "wiki/methods" "Methods" "Method comparison pages."
write_index "${PD_ROOT}/wiki/topics/_index.md" "wiki/topics" "Topics" "Topic landscape pages."
write_index "${PD_ROOT}/insights/_index.md" "insights" "Insights" "Research-facing outputs that are not canonical wiki pages."
write_index "${PD_ROOT}/insights/queries/_index.md" "insights/queries" "Query Assets" "Saved query answers, comparisons, and reports."
write_index "${PD_ROOT}/insights/ideas/_index.md" "insights/ideas" "Ideas" "Editable research idea notes."
write_index "${PD_ROOT}/insights/dialogues/_index.md" "insights/dialogues" "Dialogues" "Captured research dialogues."
write_index "${PD_ROOT}/insights/digests/_index.md" "insights/digests" "Digests" "Saved discovery digests."
write_index "${PD_ROOT}/insights/memory-promotions/_index.md" "insights/memory-promotions" "Memory Promotions" "Memory promotion audit notes."
write_index "${PD_ROOT}/memory/_index.md" "memory" "Memory" "Current advisory memory views."

echo ""
echo "Bootstrap complete."
echo ""
echo "Vault root: ${PD_ROOT}"
echo ""
echo "Directories created:"
echo "  inbox/                       - Candidate papers awaiting human approval"
echo "  sources/evidence/            - Source-grounded evidence captures"
echo "  wiki/papers/                 - Canonical paper work pages"
echo "  wiki/{concepts,methods,topics}/ - Reusable knowledge pages"
echo "  insights/{queries,ideas,digests}/ - Research outputs"
echo "  memory/                      - Advisory memory views"
echo "  .state/ir/                   - Hidden compile IR"
