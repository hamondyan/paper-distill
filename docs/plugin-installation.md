# Plugin Installation

Paper Distill uses the repository root as the plugin root.

Installing Paper Distill means registering this checkout as a local plugin root in the host, not copying the project into a separate plugin bundle.

## Install

- Codex can install Paper Distill from the repo-local marketplace entry at `.agents/plugins/marketplace.json`, where `paper-distill` intentionally points at `./` so Codex resolves the repository root as the plugin root. Direct local registration through `.codex-plugin/plugin.json` still works.
- Claude: register this checkout through `.claude-plugin/plugin.json`.
- OpenClaw: register this checkout through the shared `.mcp.json` runtime.

## Uninstall

- Codex: remove the local plugin registration that points at this checkout.
- Claude: remove the `.claude-plugin/plugin.json` registration for this checkout.
- OpenClaw: remove the `.mcp.json` registration that points at this checkout.

Uninstalling means removing the host registration. It does not mean deleting this checkout.
