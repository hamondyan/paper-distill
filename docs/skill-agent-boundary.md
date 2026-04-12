# Skill / Agent / Tool Boundary

Paper Distill uses a three-layer architecture. Understanding the boundary between layers prevents incorrect tool use and makes agent behavior predictable.

---

## Three-Layer Architecture

```text
┌─────────────────────────────────────────────────────┐
│  Layer 1: User Intent                               │
│  Natural language, slash commands, questions        │
└──────────────────────┬──────────────────────────────┘
                       │  parsed by
┌──────────────────────▼──────────────────────────────┐
│  Layer 2: Skill / Agent                             │
│  Intent routing, editorial rules, tool sequencing  │
│  skills/paper-intake/SKILL.md                       │
│  skills/knowledge-workbench/SKILL.md                │
│  skills/idea-workbench/SKILL.md                     │
└──────────────────────┬──────────────────────────────┘
                       │  calls
┌──────────────────────▼──────────────────────────────┐
│  Layer 3: MCP Tool (Python)                         │
│  Deterministic I/O, schema validation, state writes │
│  server/library_tools.py                            │
│  server/source_tools.py                             │
│  server/knowledge_tools.py                          │
│  server/idea_tools.py                               │
└─────────────────────────────────────────────────────┘
```

---

## What Each Layer Owns

### Layer 1 — User Intent

- Expresses goals in natural language or via slash commands (`/compile`, `/ideas`)
- Has no knowledge of tool parameters or file layout
- Expects readable summaries and actionable follow-ups

### Layer 2 — Skill / Agent

The agent reading the SKILL.md instructions is responsible for:

| Decision | Layer 2 responsibility |
|----------|----------------------|
| Route to the correct tool and mode | Parse user intent before calling any tool |
| Enforce the approval gate | Check `query-library(status="approved")` before `source-ingest` |
| Apply the two-paper rule | Check `list_concepts_tool(min_paper_count=2)` before creating concept stubs |
| Preserve manual sections | Read existing file, copy `## My Notes` etc., append before calling `knowledge-compile-publish` |
| Sequence the EDC pipeline | Call Extract → Resolve → Write in order; never skip Resolve |
| Format results for the user | Produce readable summaries with clear follow-up options |
| Handle `manual_edit_conflict` | Stop, report to user; never overwrite |

### Layer 3 — MCP Tool (Python)

Tools are responsible for:

| Action | Layer 3 responsibility |
|--------|----------------------|
| Vault file I/O | All reads and writes go through tools |
| Schema validation | Reject malformed IR, enforce required fields |
| Path safety | Prevent directory traversal, normalize citekeys |
| State updates | `compile_state`, `concept_registry`, `maintenance_queue` in SQLite |
| API calls | Semantic Scholar, arXiv, Zotero, CrossRef |
| Reporting facts | Return structured data; never make editorial decisions |

---

## Decision Boundary Examples

| Decision | Correct layer | Wrong layer |
|----------|--------------|-------------|
| "Is this paper good enough to ingest?" | **Layer 1** (human inbox approval) | Tool should not filter by quality |
| "Has this paper been approved?" | **Layer 2** (check `status="approved"`) | Tool does not validate status |
| "Should I create a concept stub?" | **Layer 2** (two-paper rule check) | Tool does not enforce editorial rules |
| "Which wiki page is stale?" | **Layer 3** (`wiki-lint` reports facts) | Agent should not scan files directly |
| "Write this file to disk" | **Layer 3** (via tool) | Agent should not write files directly |
| "What does the user mean?" | **Layer 2** (intent routing) | Tool does not interpret language |
| "Is the compile hash valid?" | **Layer 3** (`knowledge-compile-publish` checks hash) | Agent should not compute hashes |

---

## Skill / Tool Contract

This contract applies to all three skills.

### Skill is responsible (prompt layer)

- Parse user intent and route to the correct tool and mode
- Enforce editorial rules (approval gate, status checks, two-paper rule)
- Sequence tool calls correctly (e.g., `idea-discover` before `idea-tension-signals`)
- Merge manual sections into generated content before calling write tools
- Present results in readable form and suggest follow-up actions
- Handle conflict responses — stop and report; never auto-resolve

### MCP Tool is responsible (Python layer)

- Perform deterministic I/O (vault read/write, API calls)
- Validate schema and path safety
- Update machine state (`compile_state`, `concept_registry`, `maintenance_queue`)
- Report facts and errors; never make editorial decisions
- Return `manual_edit_conflict: true` when hash mismatch detected — do not resolve it

### Neither layer does

- **Tools do not judge paper quality** — that is the human inbox decision
- **Skills do not write files directly** — all file writes go through tools
- **Tools do not read user intent** — they only execute the parameters they receive
- **Skills do not compute content hashes** — that is compile state logic
- **Tools do not create editorial content** — they store what they are given

---

## Skill Reference

| Skill file | Covers | Key tools |
|-----------|--------|-----------|
| `skills/paper-intake/SKILL.md` | Discovery, ingestion, direct add, daily digest, Zotero handoff | `source-discover`, `source-ingest`, `resolve_metadata`, `fetch_pdf_text`, `zotero_add` |
| `skills/knowledge-workbench/SKILL.md` | EDC compile, wiki queries, vault maintenance | `paper-distill-extract`, `knowledge-compile-resolve`, `knowledge-compile-publish`, `knowledge-compile-status`, `query-library`, `wiki-lint`, `reconcile_maintenance` |
| `skills/idea-workbench/SKILL.md` | Idea generation, gap analysis, idea note curation | `idea-discover`, `idea-tension-signals`, `idea-trigger-candidates` |

---

## Why This Matters

### Without the boundary

An agent that bypasses the skill layer can:
- Ingest `proposed` papers (skipping human approval)
- Use `upsert_wiki_article` on EDC-managed pages (silently breaking `content_hash`)
- Call `idea-trigger-candidates` without `idea-discover` (missing broader context)
- Overwrite `## My Notes` sections (destroying human-authored content)

### With the boundary enforced

- Every file write is auditable (goes through a named tool with known parameters)
- Human decisions (approval, rejection, merge adjudication) cannot be bypassed by the agent
- Compile state is always consistent with file content (hash-checked at write time)
- Knowledge accumulates correctly without silent data loss
