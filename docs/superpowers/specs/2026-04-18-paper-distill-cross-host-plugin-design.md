# Paper Distill Cross-Host Plugin Design

**Date:** 2026-04-18
**Status:** Approved for planning

## Goal

Make `paper-distill` a clearer, standard Codex plugin without losing Claude or OpenClaw compatibility.

The chosen direction is **root-as-plugin hardening**: the repository root remains the plugin root, while Codex, Claude, and OpenClaw each keep a thin host-specific discovery layer on top of one shared runtime.

## Why This Direction

The repository already has the core pieces of a multi-host plugin:

- `.codex-plugin/plugin.json`
- `.claude-plugin/plugin.json`
- `.mcp.json`
- `skills/`
- `hooks/`
- `scripts/run-mcp.sh`

Moving the project into `plugins/paper-distill/` would add packaging ceremony and compatibility risk without solving a real runtime problem. The real gaps are consistency, documentation, and host-neutral entrypoints.

## Chosen Architecture

### Plugin Root

The repository root is the canonical plugin root.

That means:

- Codex reads `.codex-plugin/plugin.json`
- Claude reads `.claude-plugin/plugin.json`
- shared runtime configuration lives in `.mcp.json`
- shared operational assets stay in `skills/`, `hooks/`, and `scripts/`

No duplicate plugin tree is introduced.

### Shared Runtime

All hosts continue to use one MCP runtime:

- `.mcp.json` resolves the plugin root by checking `CLAUDE_PLUGIN_ROOT`, `CODEX_PLUGIN_ROOT`, `OPENCLAW_PLUGIN_ROOT`, then `$PWD`
- `scripts/run-mcp.sh` remains the single MCP launch script

The design explicitly avoids per-host runtime copies.

### Host-Specific Layers

- `.codex-plugin/plugin.json` is the primary Codex manifest and keeps the richer plugin interface metadata
- `.claude-plugin/plugin.json` remains a thinner compatibility manifest
- host-specific differences are kept in manifests only, not in the runtime path

### Hooks

`hooks/hooks.json` is currently the main compatibility mismatch because it hardcodes `CLAUDE_PLUGIN_ROOT`.

This design requires hooks to become host-neutral, using the same root-resolution policy as `.mcp.json`, either:

1. by calling a shared wrapper script that resolves the plugin root, or
2. by inlining the same fallback chain safely inside the hook command

The wrapper-script approach is preferred because it keeps root resolution in one place.

## File Responsibilities After Refactor

- `.codex-plugin/plugin.json`: Codex discovery manifest and UI metadata
- `.claude-plugin/plugin.json`: Claude discovery manifest
- `.mcp.json`: shared MCP server registration for all hosts
- `scripts/run-mcp.sh`: shared MCP entrypoint
- `scripts/plugin-root.sh`: shared root-resolution helper for hooks and future install tooling
- `hooks/hooks.json`: host-neutral hook registration
- `docs/plugin-installation.md`: cross-host installation and uninstall documentation

## Installation Semantics

In this design, installation means **registering the repository root as a local plugin root**.

Uninstall means **removing that registration**.

Deleting the repository checkout is not part of uninstall semantics.

This is important because the repository is both:

- a development checkout, and
- the plugin root used by hosts

## Verification Requirements

The implementation must prove:

1. Codex can still recognize the plugin from `.codex-plugin/plugin.json`
2. Claude can still recognize the plugin from `.claude-plugin/plugin.json`
3. `.mcp.json` still launches correctly when any of `CLAUDE_PLUGIN_ROOT`, `CODEX_PLUGIN_ROOT`, or `OPENCLAW_PLUGIN_ROOT` is set
4. hooks no longer depend on Claude-only root resolution
5. the repository root can still serve directly as the plugin root
6. docs explain installation, uninstall, and compatibility boundaries clearly

## Non-Goals

- moving the plugin into `plugins/paper-distill/`
- introducing marketplace packaging as a prerequisite
- rewriting server runtime behavior
- duplicating skills, hooks, or scripts per host
- dropping Claude or OpenClaw compatibility to make Codex layout look more standard

## Open Decision Already Resolved

The user explicitly chose:

- **Option 1:** keep the repository root as the plugin root
- **Approach:** root-as-plugin hardening

That decision is locked for implementation planning.
