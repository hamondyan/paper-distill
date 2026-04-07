# v1 初代发布说明

- 文档类型：发布文档
- 状态：当前
- 版本：v1 初代发布
- 更新日期：2026-04-07
- 适用对象：用户、集成方、维护者

## 本次发布是什么

这是 Paper Distill 的初代对外发布版。

目标不是把所有内部设计细节暴露给用户，而是提供一套可直接理解、可安装、可运行、可持续使用的产品文档和统一工作流。

## 本次发布包含什么

### 1. 发布版 README

仓库首页从内部开发说明升级为产品主页，重点强调：

- 产品定位
- 目标用户
- 核心工作流
- 客户端兼容性
- 文档入口

### 2. 文档体系重组

`docs/` 重新整理为：

- `product/`
- `integration/`
- `reference/`
- `releases/`
- `archive/`

### 3. 文档可追溯性增强

旧的计划、评审、superpowers 设计文档没有删除，而是归档到 `docs/archive/`。

这样可以同时满足：

- 首发用户看到清晰的产品文档
- 维护者仍能追溯历史设计演进

### 4. 多客户端兼容文档明确化

发布文档现在明确覆盖：

- Claude
- Codex
- OpenClaw

并统一说明共享 MCP runtime 的接入方式。

### 5. 与最新产品能力对齐

文档已纳入当前版本的重要能力：

- `index.md` / `log.md`
- query assets
- ideas 结果沉淀
- LLM maintainer 心智模型

## 不包含什么

这次发布主要是产品文档层与发布组织层整理，不改变核心运行时行为，不重构协议，不改变主工作流拓扑。

## 建议下一步

如果你准备继续推进正式发布，推荐下一步做：

1. 增加示例 vault 截图或 demo GIF
2. 增加一个最小可运行的 `settings.json` 示例
3. 增加一个端到端使用示例（discover -> inbox -> process -> compile -> query）
4. 增加 release tag 与 changelog 机制

## 相关文档

- [../../README.md](../../README.md)
- [../integration/clients.md](../integration/clients.md)
- [../integration/installation.md](../integration/installation.md)
- [../archive/README.md](../archive/README.md)
