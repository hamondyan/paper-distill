# Plugin Installation

Paper Distill uses the repository root as the plugin root.

Installing Paper Distill means registering this checkout as a local plugin root in the host, not copying the project into a separate plugin bundle.

- Codex uses `.codex-plugin/plugin.json` for discovery.
- Claude uses `.claude-plugin/plugin.json` for discovery.
- OpenClaw uses the shared `.mcp.json` runtime.

Uninstalling means removing the host registration. It does not mean deleting this checkout.
