# 客户端兼容性

- 文档类型：集成文档
- 状态：当前
- 版本：v1 初代发布
- 更新日期：2026-04-07
- 适用对象：用户、集成方

## 总览

Paper Distill 当前以统一 MCP bundle 的形式兼容：

- **Claude**
- **Codex**
- **OpenClaw**

三者共享：

- 同一个 MCP 运行时
- 同一套 skills / commands / agents
- 同一份插件与启动约定

## 统一运行时

所有客户端都通过仓库根目录下的：

- [`.mcp.json`](../../.mcp.json)

启动服务。

实际 launcher：

- [`scripts/run-mcp.sh`](../../scripts/run-mcp.sh)

默认运行命令：

```bash
uv --directory <repo-root> run paper-distill-server
```

## Claude

相关文件：

- [`.claude-plugin/plugin.json`](../../.claude-plugin/plugin.json)
- [`.mcp.json`](../../.mcp.json)
- [`hooks/hooks.json`](../../hooks/hooks.json)

适合：

- 直接作为 Claude bundle 使用
- 使用内置 hooks 与命令协议

## Codex

相关文件：

- [`.codex-plugin/plugin.json`](../../.codex-plugin/plugin.json)
- [`.mcp.json`](../../.mcp.json)
- [`hooks/hooks.json`](../../hooks/hooks.json)
- [`skills/`](../../skills)

适合：

- 在 Codex 桌面端或兼容环境中使用
- 依赖 skills / commands / agents 的完整工作流

## OpenClaw

OpenClaw 当前通过兼容 bundle 布局接入。

关键点：

- 可以复用同一个 MCP 运行时
- 可以复用同一套 skills / commands / agents
- 可识别 Claude / Codex 兼容 bundle 标记

关键文件：

- [`.claude-plugin/plugin.json`](../../.claude-plugin/plugin.json)
- [`.codex-plugin/plugin.json`](../../.codex-plugin/plugin.json)

## 兼容性建议

### 推荐

- 使用 `uv`
- 保持 `.mcp.json` 为统一入口
- 不要为不同客户端维护多套 server 实现

### 不推荐

- 为 Claude / Codex / OpenClaw 各自 fork 一套插件逻辑
- 在文档层混淆“客户端差异”和“产品工作流”

## English Note

Paper Distill ships as a single MCP-backed bundle that works across Claude, Codex, and OpenClaw.
The shared runtime entrypoint is [`.mcp.json`](../../.mcp.json), and the default launcher is [`scripts/run-mcp.sh`](../../scripts/run-mcp.sh).

## 相关文档

- [installation.md](installation.md)
- [../reference/commands.md](../reference/commands.md)
