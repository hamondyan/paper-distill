# 核心工作流

- 文档类型：产品文档
- 状态：当前
- 版本：v1 初代发布
- 更新日期：2026-04-07
- 适用对象：用户、维护者

## 总体流程

Paper Distill 的核心工作流是：

```text
discover -> inbox approval -> raw/source -> raw/notes -> wiki -> query / ideas -> promotion
```

## 1. 发现阶段

入口：

- `/discover <query>`
- 定时 / 批量发现（例如 daily digest）

行为：

- 从 arXiv、Semantic Scholar、OpenAlex、DBLP、Papers with Code 等来源检索
- 去重、打分、做 topic fit 判断
- 仅把候选写入 `inbox/`

目标：

- 给人一个可审核的候选列表，而不是直接污染正式知识库

## 2. 审批阶段

用户在 Obsidian 中修改 `inbox/` note 的 `status`：

- `approved`
- `rejected`
- `deferred`
- `proposed`

这是整个系统最重要的质量边界。

## 3. 摄取阶段

入口：

- `/process-inbox`
- `/add-paper <doi|arxiv|url>`

行为：

- 抓取 HTML 或 PDF
- 生成清洗后的 `raw/source/`
- 生成结构化的 `raw/notes/`
- 可选执行 Zotero handoff

结果：

- 论文从“候选”变成“已进入证据层”

## 4. 编译阶段

入口：

- `/compile`

行为：

- 从 `raw/notes/` 抽取结构化 IR
- 做 concept resolve / canonicalize
- 写入 `wiki/papers`、`wiki/concepts`、`wiki/methods`、`wiki/topics`
- 维护编译状态与依赖关系

结果：

- 从单篇阅读记录上升为跨论文知识组织

## 5. 查询与复利阶段

入口：

- `/query <question>`
- `/ideas`

行为：

- 基于现有 `wiki/` 和 `raw/` 回答问题
- 将高价值结果沉淀到 `queries/`
- 生成 promotion targets，必要时升格为 canonical wiki 内容

结果：

- 查询不再只是一次回答，而会成为知识库继续增长的一部分

## 6. 维护阶段

入口：

- `/lint`
- maintenance queue 相关操作

行为：

- 检查 orphaned pages、broken backlinks、missing concept stubs、stale topics
- reconcile 成维护任务
- 执行 merge / promote / refresh

结果：

- wiki 不只是增长，还会被持续整理

## 相关文档

- [overview.md](overview.md)
- [knowledge-model.md](knowledge-model.md)
- [../reference/commands.md](../reference/commands.md)
