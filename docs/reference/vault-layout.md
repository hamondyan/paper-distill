# Vault 目录结构参考

- 文档类型：参考文档
- 状态：当前
- 版本：v1 初代发布
- 更新日期：2026-04-07
- 适用对象：用户、维护者

## 顶层结构

```text
{vault}/Paper Distill/
├── inbox/
├── index.md
├── log.md
├── raw/
│   ├── source/
│   └── notes/
├── zotero/
│   └── imports/
├── wiki/
│   ├── papers/
│   ├── concepts/
│   ├── methods/
│   └── topics/
├── daily-log/
└── queries/
```

## 各目录职责

### `inbox/`

- 存放 discovery 得到的候选论文
- 是人工审批边界

### `raw/source/`

- 存放清洗后的论文证据层
- 默认采用 inline evidence Markdown：图、表、公式尽量贴近正文位置
- 可能保留 `Appendix Snapshot` 与 `Captured Assets Index`
- 配套 `.assets.json` sidecar 是结构化证据主契约

### `raw/notes/`

- 存放结构化阅读理解
- 默认采用 `CRGP-DNL`

### `wiki/papers/`

- 编译后的单论文知识页

### `wiki/concepts/`

- 概念页

### `wiki/methods/`

- 方法比较页

### `wiki/topics/`

- topic / landscape 页

### `queries/`

- 保存 query assets、比较笔记、topic syntheses、idea analyses

### `daily-log/`

- 保存日级 digest

### `index.md`

- 内容型导航

### `log.md`

- 时间型导航

## 重要约束

- `inbox/` 不等于正式知识
- `raw/` 是证据与理解层，不是最终展示层
- `wiki/` 是编译层，不应直接跳过原始证据层生产
- `queries/` 是知识资产层，不是聊天记录垃圾箱

## 相关文档

- [commands.md](commands.md)
- [../product/knowledge-model.md](../product/knowledge-model.md)
