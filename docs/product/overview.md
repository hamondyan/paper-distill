# 产品概览

- 文档类型：产品文档
- 状态：当前
- 版本：v1 初代发布
- 更新日期：2026-04-07
- 适用对象：用户、评估者、集成方

## 产品定位

Paper Distill 是一套面向 Obsidian 的研究知识工作流，用来把论文发现、证据采集、阅读理解、知识编译、查询沉淀和研究想法生成，统一到一个由 LLM 持续维护的知识系统中。

它不是一次性的问答工具，也不是只做论文检索的脚本，而是一个**长期运行的研究知识维护器**。

## 核心理念

### 1. Human-in-the-loop

系统不会把发现到的论文直接写进正式知识库。

默认流程是：

- 先写入 `inbox/`
- 由人审核
- 审核通过后再进入 `raw/` 和 `wiki/`

### 2. 证据层与知识层分离

- `raw/source/`：稳定证据层
- `raw/notes/`：结构化阅读理解层
- `wiki/`：编译后的知识层

这保证了后续综述、比较和 ideas 有明确的上游依据。

### 3. 查询和想法也是知识增长的一部分

Paper Distill 不把 `/query` 和 `/ideas` 当作临时聊天。

高价值结果会进入：

- `queries/`
- `index.md`
- `log.md`

必要时还能继续升格进 `wiki/`。

### 4. LLM 是维护者，不是最终裁决者

系统默认角色划分是：

- 用户：编辑者 / 审稿人 / 研究负责人
- LLM：知识维护者

LLM 负责整理、更新、交叉链接、总结、发现张力；  
用户负责判断、批准、取舍、纠偏。

## 用户价值

Paper Distill 适合解决以下问题：

- “我读了很多论文，但知识没有沉淀成系统”
- “每次问 LLM 都要重新从原始论文开始检索”
- “我想把 Obsidian 变成长期维护的研究 wiki，而不是笔记堆”
- “我想保留 Zotero，但不想把研究思考完全困在 Zotero 里”
- “我需要一个同时兼容 Claude、Codex、OpenClaw 的统一 bundle”

## 当前首发范围

v1 首发阶段重点提供：

- 论文发现与 inbox 审批
- arXiv / ar5iv / PDF fallback 的证据采集
- `raw/source` + `raw/notes` 双层原始资产
- wiki 编译、概念维护、维护队列
- 查询资产沉淀与 idea analysis
- `index.md` / `log.md` 可见知识增长导航

## 相关文档

- [workflow.md](workflow.md)
- [knowledge-model.md](knowledge-model.md)
- [../integration/clients.md](../integration/clients.md)
- [../releases/v1-launch.md](../releases/v1-launch.md)
