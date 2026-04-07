# 知识模型

- 文档类型：产品文档
- 状态：当前
- 版本：v1 初代发布
- 更新日期：2026-04-07
- 适用对象：用户、集成方、维护者

## 总体结构

Paper Distill 把知识拆成几层：

1. 候选层：`inbox/`
2. 证据层：`raw/source/`
3. 阅读理解层：`raw/notes/`
4. 编译知识层：`wiki/`
5. 查询资产层：`queries/`
6. 导航层：`index.md` + `log.md`

## inbox

`inbox/` 是候选证据池。

特点：

- 可被发现流程写入
- 不属于正式知识
- 必须经人工审批后才能继续向下游流动

## raw/source

`raw/source/` 是稳定证据层。

内容通常包括：

- 清洗后的正文 Markdown
- 结构化 sidecar
- capture provenance

它回答的是：**“这篇论文里实际说了什么？”**

## raw/notes

`raw/notes/` 是结构化阅读理解层。

默认使用 `CRGP-DNL`：

- Context
- Related Work
- Gap
- Proposal
- Key Results
- Discussion
- Next Steps

它回答的是：**“这篇论文对我当前研究语境意味着什么？”**

## wiki

`wiki/` 是编译后的长期知识层。

包括：

- `wiki/papers/`
- `wiki/concepts/`
- `wiki/methods/`
- `wiki/topics/`

它回答的是：**“跨论文来看，我现在知道什么？”**

## queries

`queries/` 不是聊天记录回收站，而是查询资产层。

这里保存：

- query note
- comparison note
- topic synthesis
- contradiction note
- idea analysis
- idea memo

它回答的是：**“我刚刚通过提问和比较新形成了什么认知？”**

## index.md 与 log.md

### index.md

内容型导航层。

用于展示：

- 当前知识版图
- 最近活跃 topic / concept
- 最近保存的 query assets
- 重要待处理事项

### log.md

时间型导航层。

用于记录：

- ingest
- compile
- maintenance
- query
- idea

它回答的是：**“这个知识系统最近发生了什么变化？”**

## 相关文档

- [overview.md](overview.md)
- [workflow.md](workflow.md)
- [../reference/vault-layout.md](../reference/vault-layout.md)
