"""Knowledge MCP tools — compilation, wiki writes, concepts, maintenance.

Registers:
    compile     — unified compile pipeline (CRGP + EDC)
    write-wiki  — non-compile wiki writes (concept stubs, method pages)
    concept     — concept registry operations (register / resolve / merge)
    maintain    — maintenance task lifecycle
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from server.config import get_vault_path
from server.qmd_runtime import qmd_reembed_force as _qmd_reembed_force, qmd_update as _qmd_update
from server.server_runtime import (
    # compile pipeline
    prepare_crgp_context as _prepare_crgp,
    save_crgp_sections as _save_crgp,
    write_compile_ir as _write_ir,
    resolve_compile_ir as _resolve_ir,
    commit_compile_result as _commit_compile,
    # wiki
    upsert_wiki_article as _upsert_wiki,
    upsert_wiki_page_v3 as _upsert_wiki_page_v3,
    # concepts
    register_concept_tool as _register_concept,
    resolve_concept_tool as _resolve_concept,
    merge_concepts_tool as _merge_concepts,
    check_concept_alias_v3 as _check_concept_alias_v3,
    merge_concept_v3 as _merge_concept_v3,
    # maintenance
    reconcile_maintenance as _reconcile,
    get_maintenance_queue as _get_queue,
    resolve_maintenance_task as _resolve_task,
    execute_maintenance_task as _execute_task,
    enqueue_maintenance_task as _enqueue_task,
)


# ------------------------------------------------------------------
# Tool 7: compile (unified pipeline)
# ------------------------------------------------------------------

async def compile(
    citekey: str,
    step: str = "prepare",
    sections: dict | None = None,
    confidence: float = 0.93,
    metadata: dict | None = None,
    ir_json: dict | None = None,
    page_type: str = "paper",
    content: str | None = None,
    frontmatter: dict | None = None,
    ir_path: str | None = None,
    deps: list[dict] | None = None,
) -> dict[str, Any]:
    """Compile a paper from source evidence into a wiki page.

    **Unified compile path (recommended — two steps):**

    1. ``compile(citekey, step="prepare")`` — loads paper metadata, source
       markdown (≤40 k chars), and any previously compiled sections so the
       LLM has full context.

    2. Agent generates:

       - 7 CRGP sections: Context, Related Work, Gap, Proposal, Key Results,
         Discussion, Next Steps.
       - Structured ``metadata`` dict (candidate_concepts + tension_fields)
         extracted while reading the paper.

    3. ``compile(citekey, step="save", sections={...}, metadata={...})`` —
       one call that atomically:

       - Validates and persists the IR to ``.state/ir/{citekey}.json``.
       - Runs concept resolution / auto-registration (``resolve_ir``).
       - Renders the wiki markdown (CRGP template).
       - Updates SQLite compile_state (version bump, ir_path, content_hash).

    ``metadata`` schema::

        {
          "candidate_concepts": [{"name": str, "type": str, "aliases"?: [str]}],
          "tension_fields": {
              "limitations":     [str | {"claim": str, "source_ref"?: str}],
              "assumptions":     [str | {"claim": str, "source_ref"?: str}],
              "open_questions":  [str | {"question": str, "source_ref"?: str}],
              "negative_results":[str | {"claim": str, "source_ref"?: str}],
              // optional:
              "failure_modes":        [...],
              "transfer_constraints": [...]
          },
          "benchmark_scope"?: str,
          "claimed_novelty"?: str,
          "topics"?: [str]
        }

    ``metadata`` is optional. Omitting it falls back to legacy CRGP behaviour
    (wiki page is written, but the paper will be invisible to idea-analyze /
    aggregate_tension_signals because no IR is produced).

    ---

    Internal steps (not part of the standard workflow — kept for programmatic
    pipelines only):

    - ``step="extract_ir"``  — write a raw IR JSON to .state/ir/.
    - ``step="resolve_ir"``  — entity-link candidate concepts.
    - ``step="publish"``     — write the compiled wiki page with explicit
                               content / frontmatter / ir_path / deps.

    Args:
        citekey:     Paper citekey (e.g. "brohan2023rt2").
        step:        Pipeline step — "prepare" | "save" | "extract_ir" |
                     "resolve_ir" | "publish".
        sections:    For step=save: dict with 7 CRGP section keys.
        confidence:  For step=save: LLM confidence score (default 0.93).
        metadata:    For step=save: structured IR metadata (see schema above).
        ir_json:     For step=extract_ir: the raw IR dict to persist.
        page_type:   For step=publish: "paper" | "concept" | "method".
        content:     For step=publish: compiled markdown body.
        frontmatter: For step=publish: frontmatter dict.
        ir_path:     For step=publish: optional path to resolved IR JSON.
        deps:        For step=publish: optional dependency list.
    """
    if step == "prepare":
        return await _prepare_crgp(citekey)

    if step == "save":
        if sections is None:
            return {"error": "sections is required for step='save'"}
        return await _save_crgp(citekey, sections, confidence, metadata)

    if step == "extract_ir":
        if ir_json is None:
            return {"error": "ir_json is required for step='extract_ir'"}
        return await _write_ir(citekey, ir_json)

    if step == "resolve_ir":
        return (await _resolve_ir([citekey]))[0] if True else {}

    if step == "publish":
        if content is None or frontmatter is None:
            return {"error": "content and frontmatter are required for step='publish'"}
        return await _commit_compile(
            page_id=citekey,
            page_type=page_type,
            content=content,
            frontmatter=frontmatter,
            ir_path=ir_path,
            deps=deps,
        )

    return {"error": f"Unknown step '{step}'. Expected: prepare, save, extract_ir, resolve_ir, publish"}


# ------------------------------------------------------------------
# Tool 8: write-wiki
# ------------------------------------------------------------------

async def write_wiki(
    citekey: str,
    section: str,
    content: str,
    frontmatter: dict | None = None,
) -> dict[str, Any]:
    """Create or update a wiki article outside the compile pipeline.

    Use this for concept stubs, method pages, and other non-compile
    writes.  **Never** use this on a page previously written by
    ``compile`` — it would corrupt the content_hash.

    Args:
        citekey: Page identifier (citekey or slug).
        section: Target section — "papers" | "concepts" | "methods".
        content: Markdown content.
        frontmatter: Optional frontmatter dict.
    """
    return await _upsert_wiki(
        citekey=citekey,
        section=section,
        content=content,
        frontmatter=frontmatter,
    )


async def upsert_wiki_page(
    page_type: str,
    target: str,
    frontmatter: dict,
    body: str,
) -> dict[str, Any]:
    return await _upsert_wiki_page_v3(
        page_type=page_type,
        target=target,
        frontmatter=frontmatter,
        body=body,
    )


# ------------------------------------------------------------------
# Tool 9: concept
# ------------------------------------------------------------------

async def concept(
    action: str,
    canonical: str | None = None,
    surface_form: str | None = None,
    concept_type: str = "concept",
    aliases: list[str] | None = None,
    from_id: str | None = None,
    to_id: str | None = None,
    reason: str = "",
) -> dict[str, Any]:
    """Manage the canonical concept registry.

    Actions:
    - ``register``: register a new concept (or return existing).
      Requires ``canonical``; optional ``concept_type``, ``aliases``.
    - ``resolve``: look up a surface form to find its canonical entry.
      Requires ``surface_form``.
    - ``merge``: merge one concept into another, re-mapping all aliases.
      Requires ``from_id`` and ``to_id``; optional ``reason``.

    Args:
        action: "register" | "resolve" | "merge".
        canonical: For register: display name (e.g. "Diffusion Policy").
        surface_form: For resolve: name to look up (e.g. "VLA").
        concept_type: For register: "concept" | "method" | "topic".
        aliases: For register: additional surface forms.
        from_id: For merge: slug of concept to merge away.
        to_id: For merge: slug of target concept.
        reason: For merge: human-readable merge reason.
    """
    if action == "register":
        if not canonical:
            return {"error": "canonical is required for action='register'"}
        return await _register_concept(
            canonical=canonical,
            concept_type=concept_type,
            aliases=aliases,
        )

    if action == "resolve":
        if not surface_form:
            return {"error": "surface_form is required for action='resolve'"}
        return await _resolve_concept(surface_form)

    if action == "merge":
        if not from_id or not to_id:
            return {"error": "from_id and to_id are required for action='merge'"}
        return await _merge_concepts(from_id=from_id, to_id=to_id, reason=reason)

    return {"error": f"Unknown action '{action}'. Expected: register, resolve, merge"}


async def check_concept_alias(name: str) -> dict[str, Any]:
    return await _check_concept_alias_v3(name)


async def merge_concept(old: str, new: str) -> dict[str, Any]:
    return await _merge_concept_v3(old=old, new=new)


async def kb_update_index() -> dict[str, Any]:
    vault_path = get_vault_path()
    if not vault_path:
        return {"ok": False, "error": "VAULT_PATH not configured."}
    return _qmd_update(Path(vault_path))


async def kb_reembed_force() -> dict[str, Any]:
    vault_path = get_vault_path()
    if not vault_path:
        return {"ok": False, "error": "VAULT_PATH not configured."}
    return _qmd_reembed_force(Path(vault_path))


# ------------------------------------------------------------------
# Tool 10: maintain
# ------------------------------------------------------------------

async def maintain(
    action: str = "reconcile",
    auto_confirm: bool = True,
    task_type: str | None = None,
    status: str | None = None,
    task_id: int | None = None,
    reason: str = "",
    payload: dict | None = None,
    confidence: float = 1.0,
) -> dict[str, Any]:
    """Manage vault maintenance tasks through their full lifecycle.

    Actions:
    - ``reconcile``: run lint + stats, generate deduplicated maintenance
      tasks, and optionally auto-confirm safe merges.
    - ``queue``: view current maintenance tasks (filter by type/status).
    - ``confirm``: confirm a pending task for execution.
    - ``reject``: reject a task with a reason.
    - ``execute``: execute a confirmed task (merge / promote / refresh).
    - ``enqueue``: manually create a new maintenance task.

    Args:
        action: "reconcile" | "queue" | "confirm" | "reject" |
                "execute" | "enqueue".
        auto_confirm: For reconcile: auto-confirm safe merges (default True).
        task_type: For queue/enqueue: filter or specify task type.
        status: For queue: filter by status.
        task_id: For confirm/reject/execute: the task ID.
        reason: For reject: rejection reason.
        payload: For enqueue: task payload dict.
        confidence: For enqueue: confidence score (default 1.0).
    """
    if action == "reconcile":
        return await _reconcile(auto_confirm=auto_confirm)

    if action == "queue":
        return {"tasks": await _get_queue(task_type=task_type, status=status)}

    if action == "confirm":
        if task_id is None:
            return {"error": "task_id is required for action='confirm'"}
        return await _resolve_task(task_id=task_id, action="confirm")

    if action == "reject":
        if task_id is None:
            return {"error": "task_id is required for action='reject'"}
        return await _resolve_task(task_id=task_id, action="reject", reason=reason)

    if action == "execute":
        if task_id is None:
            return {"error": "task_id is required for action='execute'"}
        return await _execute_task(task_id=task_id)

    if action == "enqueue":
        if not task_type or payload is None:
            return {"error": "task_type and payload are required for action='enqueue'"}
        return await _enqueue_task(
            task_type=task_type,
            payload=payload,
            confidence=confidence,
        )

    return {"error": f"Unknown action '{action}'. Expected: reconcile, queue, confirm, reject, execute, enqueue"}


# ------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------

def register_knowledge_tools(mcp: FastMCP) -> None:
    mcp.tool(name="compile")(compile)
    mcp.tool(name="write-wiki")(write_wiki)
    mcp.tool(name="upsert-wiki-page")(upsert_wiki_page)
    mcp.tool(name="concept")(concept)
    mcp.tool(name="check-concept-alias")(check_concept_alias)
    mcp.tool(name="merge_concept")(merge_concept)
    mcp.tool(name="kb_update_index")(kb_update_index)
    mcp.tool(name="kb_reembed_force")(kb_reembed_force)
    mcp.tool(name="maintain")(maintain)
