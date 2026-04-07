#!/usr/bin/env bash
# Bootstrap Paper Distill vault structure in Obsidian
set -euo pipefail

VAULT_PATH="${1:-}"

if [[ -z "$VAULT_PATH" ]]; then
  echo "Usage: bootstrap.sh <obsidian-vault-path>"
  echo "  e.g.: bootstrap.sh /Users/you/Documents/knowledge_repo"
  exit 1
fi

PD_ROOT="${VAULT_PATH}/Paper Distill"

echo "Creating Paper Distill vault structure at: ${PD_ROOT}"

mkdir -p "${PD_ROOT}/raw/source"
mkdir -p "${PD_ROOT}/raw/notes"
mkdir -p "${PD_ROOT}/inbox"
mkdir -p "${PD_ROOT}/wiki/concepts"
mkdir -p "${PD_ROOT}/wiki/methods"
mkdir -p "${PD_ROOT}/wiki/papers"
mkdir -p "${PD_ROOT}/wiki/topics"
mkdir -p "${PD_ROOT}/daily-log"
mkdir -p "${PD_ROOT}/queries"

if [[ ! -f "${PD_ROOT}/index.md" ]]; then
cat > "${PD_ROOT}/index.md" << 'EOF'
# Paper Distill Index

Knowledge map coming online. Run ingest, query, compile, or maintenance actions to refresh this overview.
EOF
fi

if [[ ! -f "${PD_ROOT}/log.md" ]]; then
cat > "${PD_ROOT}/log.md" << 'EOF'
# Paper Distill Log

Append-only timeline of ingest, query, compile, maintenance, and idea activity.
EOF
fi

# Master index
if [[ ! -f "${PD_ROOT}/_index.md" ]]; then
cat > "${PD_ROOT}/_index.md" << 'EOF'
---
type: index
updated: ""
---

# Paper Distill

Human-approved research knowledge base with Zotero grounding.

## Sections
- `inbox/` candidate papers awaiting approval
- `raw/source/` cleaned arXiv source captures
- `raw/notes/` CRGP-DNL structured reading notes
- `wiki/` compiled knowledge derived from approved raw notes
- `queries/` saved Q&A and idea analyses
EOF
fi

# inbox index
if [[ ! -f "${PD_ROOT}/inbox/_index.md" ]]; then
cat > "${PD_ROOT}/inbox/_index.md" << 'EOF'
---
type: index
section: inbox
updated: ""
---

# Inbox

Candidate papers discovered by AI. Update each note's `status` field to:
- `approved`
- `rejected`
- `deferred`
EOF
fi

# raw index
if [[ ! -f "${PD_ROOT}/raw/_index.md" ]]; then
cat > "${PD_ROOT}/raw/_index.md" << 'EOF'
---
type: index
section: raw
updated: ""
---

# Raw Layer

Dual-layer source capture for approved papers.

- `source/` holds cleaned arXiv captures
- `notes/` holds CRGP-DNL reading notes
EOF
fi

if [[ ! -f "${PD_ROOT}/raw/source/_index.md" ]]; then
cat > "${PD_ROOT}/raw/source/_index.md" << 'EOF'
---
type: index
section: raw/source
updated: ""
---

# Raw Source

Cleaned arXiv full-text captures. This is the stable evidence layer.
EOF
fi

if [[ ! -f "${PD_ROOT}/raw/notes/_index.md" ]]; then
cat > "${PD_ROOT}/raw/notes/_index.md" << 'EOF'
---
type: index
section: raw/notes
updated: ""
---

# Raw Notes

CRGP-DNL structured reading notes generated from `raw/source`.
EOF
fi

# wiki index
if [[ ! -f "${PD_ROOT}/wiki/_index.md" ]]; then
cat > "${PD_ROOT}/wiki/_index.md" << 'EOF'
---
type: index
section: wiki
updated: ""
---

# Wiki

Compiled knowledge derived only from approved raw notes.
EOF
fi

# Subdirectory indexes
for dir in concepts methods papers topics; do
  idx="${PD_ROOT}/wiki/${dir}/_index.md"
  title="$(printf '%s' "$dir" | awk '{print toupper(substr($0,1,1)) substr($0,2)}')"
  if [[ ! -f "$idx" ]]; then
cat > "$idx" << EOF
---
type: index
section: wiki/${dir}
updated: ""
---

# ${title}

_No ${dir} compiled yet._
EOF
  fi
done

# queries index
if [[ ! -f "${PD_ROOT}/queries/_index.md" ]]; then
cat > "${PD_ROOT}/queries/_index.md" << 'EOF'
---
type: index
section: queries
updated: ""
---

# Research Queries

Saved Q&A results. Knowledge compounds over time.

## Queries
_No queries saved yet._
EOF
fi

# daily log index
if [[ ! -f "${PD_ROOT}/daily-log/_index.md" ]]; then
cat > "${PD_ROOT}/daily-log/_index.md" << 'EOF'
---
type: index
section: daily-log
updated: ""
---

# Daily Log

Saved discovery digests and day-by-day research tracking.
EOF
fi

echo ""
echo "Bootstrap complete."
echo ""
echo "Vault root: ${PD_ROOT}"
echo ""
echo "Directories created:"
echo "  inbox/        — Candidate papers awaiting human approval"
echo "  raw/source/   — Cleaned arXiv source documents"
echo "  raw/notes/    — Structured CRGP-DNL reading notes"
echo "  wiki/         — LLM-compiled knowledge"
echo "  daily-log/    — Daily digest entries"
echo "  queries/      — Saved Q&A results"
echo ""
echo "Next: Configure vault_path in Paper Distill plugin settings."
