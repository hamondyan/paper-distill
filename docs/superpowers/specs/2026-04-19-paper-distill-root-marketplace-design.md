# Paper Distill Root-As-Plugin Marketplace Design

**Date:** 2026-04-19
**Status:** Approved for planning

## Goal

Add a repo-local Codex marketplace entry for `paper-distill` without changing the repository-root plugin layout.

The plugin root stays at the repository root. The new marketplace layer is only for Codex discovery, listing, and install/uninstall flow.

## Why This Direction

`paper-distill` already has a working root-as-plugin layout:

- `.codex-plugin/plugin.json`
- `.claude-plugin/plugin.json`
- `.mcp.json`
- `skills/`
- `hooks/`
- `scripts/`

The remaining gap is Codex marketplace discovery. The user explicitly chose to keep the repository root as the plugin root instead of moving the project into `plugins/paper-distill/`.

## Chosen Architecture

### Marketplace Location

Add a repo-local marketplace file at `.agents/plugins/marketplace.json`.

This marketplace belongs to the repository, not the user home directory.

### Marketplace Entry Shape

Add a `paper-distill` entry with Codex marketplace metadata:

- `name: "paper-distill"`
- `source.source: "local"`
- `source.path: "./"`
- `policy.installation: "AVAILABLE"`
- `policy.authentication: "ON_INSTALL"`
- `category: "Productivity"`

The important exception is `source.path: "./"`.

This is an intentional root-as-plugin override. It does not follow the default `plugin-creator` scaffold convention of `./plugins/<plugin-name>`.

### Plugin Root Contract

Codex marketplace discovery should resolve `paper-distill` to the repository root, where Codex then reads:

- `.codex-plugin/plugin.json`
- `.mcp.json`
- `hooks/hooks.json`
- `skills/`

No shim directory and no duplicate plugin tree are introduced.

## Documentation Changes

Update the user-facing docs so the marketplace exception is explicit:

- `README.md`: mention repo-local marketplace discovery for Codex
- `docs/plugin-installation.md`: explain that Codex can install from the repo-local marketplace entry and that the entry points to the repository root

The docs should be clear that this is still a local plugin, not a published remote marketplace package.

## Verification Requirements

The implementation must prove:

1. `.agents/plugins/marketplace.json` exists
2. the marketplace entry name matches `paper-distill`
3. the marketplace entry uses `source.path: "./"`
4. the marketplace entry sets installation and authentication policy explicitly
5. README and plugin installation docs describe the root-as-plugin marketplace behavior clearly
6. existing root-as-plugin manifests continue to point at repository-root assets

## Non-Goals

- moving the plugin into `plugins/paper-distill/`
- changing `.codex-plugin/plugin.json` to use a different root
- adding remote distribution or publish flows
- changing Claude or OpenClaw installation layout
- introducing a shim plugin directory just to satisfy the default scaffold pattern

## Decision Locked

The user explicitly chose:

- **Marketplace style:** repo-local marketplace
- **Plugin layout:** root-as-plugin custom marketplace entry

That decision is locked for the implementation plan.
