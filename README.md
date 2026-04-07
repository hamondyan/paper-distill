# Paper Distill

Paper Distill 是一套面向 Obsidian 的、**人类审批 + LLM 维护** 的研究知识基础设施。

它的目标不是做一次性的论文问答，也不是把论文简单丢进 RAG 检索层，而是把论文发现、证据采集、结构化阅读、知识编译、查询沉淀与研究想法生成，统一进一个可持续增长的知识系统里。

它继承了 **LLM Wiki** 一类知识系统的核心理念：
**知识不应该在每次提问时被重新临时拼装，而应该被持续编译、持续维护、持续增值。**

在 Paper Distill 中，LLM 不是一次性回答问题的聊天接口，而是一个长期维护研究知识库的维护者；wiki 不是附件仓库，而是研究过程本身的工作界面。

- **用户角色**：编辑者、审稿人、研究负责人
- **LLM 角色**：知识维护者
- **知识资产**：不是聊天记录，而是持续更新的 Obsidian wiki

## English Summary

Paper Distill is a human-approved research knowledge infrastructure for Obsidian.
It packages one MCP-backed runtime for **Claude**, **Codex**, and **OpenClaw**, and turns paper discovery, ingestion, synthesis, querying, and idea generation into a maintained wiki rather than disposable chat output.

For English-side integration details, see [docs/integration/clients.md](docs/integration/clients.md).

## 它解决什么问题

大多数 LLM 文档工作流停留在：

```text
上传文件 -> 检索 -> 回答
```

这类模式当然有价值，但它天然偏向“按问题临时拼装知识”，而不是“把知识沉淀成可维护的长期资产”。

Paper Distill 走的是另一条路线：

1. 先发现或指定论文
2. 由人决定是否纳入知识库
3. 把原始论文转成稳定的证据层
4. 生成结构化阅读笔记
5. 再编译成可链接、可维护、可持续演化的 wiki
6. 之后的查询、综述、idea 结果也继续沉淀为知识资产

一句话说：**它把论文知识从“每次临时检索”升级为“持续维护、持续编译、持续复利的研究系统”。**

## 适合谁

- 做长期论文追踪、综述、选题和研究方向管理的研究者
- 已经使用 Obsidian，希望让 LLM 帮你维护 wiki 的个人研究工作流
- 需要同时兼容 Claude、Codex、OpenClaw 的 MCP / agent 工作流
- 希望保留 Zotero，但不想把知识组织完全交给 Zotero 的用户

## 核心特性

- **Human-in-the-loop**：论文发现先进入 `inbox/`，人工审批后才进入知识库
- **双层原始资产**：`raw/source/` 保存稳定证据，`raw/notes/` 保存结构化阅读理解
- **结构化知识编译**：把原始笔记编译到 `wiki/papers`、`wiki/concepts`、`wiki/methods`、`wiki/topics`
- **查询结果继续沉淀**：高价值 `/query` 和 `/ideas` 结果会进入 `queries/`
- **可见的知识增长**：`index.md` 提供内容地图，`log.md` 提供时间线
- **研究友好的维护层**：概念注册表、编译状态、维护队列、张力信号聚合
- **兼容 Zotero**：支持 `local_first`、`web_api`、`disabled`
- **多客户端兼容**：同一套 MCP bundle 支持 Claude、Codex、OpenClaw

从产品形态上看，Paper Distill 更接近：

- 一个研究知识操作系统
- 一个面向论文工作的 LLM-maintained wiki
- 一个以证据层为中心、以编译层为核心、以长期积累为目标的研究工作台

## 支持的客户端

Paper Distill 当前以统一 bundle 形式提供给：

- **Claude**
- **Codex**
- **OpenClaw**

三者共享同一个 MCP 入口：

- [`.mcp.json`](.mcp.json)
- [`scripts/run-mcp.sh`](scripts/run-mcp.sh)

详细兼容说明见：[docs/integration/clients.md](docs/integration/clients.md)

## 3 分钟上手

### 1. 安装依赖

推荐使用 `uv`：

```bash
uv sync
```

### 2. 配置你的 Obsidian Vault

复制并修改 [`settings.example.json`](settings.example.json) 的结构，在本地创建 `settings.json`：

```json
{
  "paper_distill": {
    "vault_path": "/absolute/path/to/your/obsidian/vault"
  }
}
```

也可以直接使用环境变量：

```bash
export VAULT_PATH="/absolute/path/to/your/obsidian/vault"
```

### 3. 启动 MCP Server

```bash
uv run paper-distill-server
```

如果你使用的是仓库自带 launcher，本质运行的是：

```bash
uv --directory <repo-root> run paper-distill-server
```

## 核心工作流

### 常规发现流

```text
discover -> inbox approval -> raw/source -> raw/notes -> Zotero handoff -> wiki
```

### 直接纳入流

```text
add-paper -> raw/source -> raw/notes -> Zotero handoff -> wiki
```

### 查询与复利流

```text
query / ideas -> queries -> promotion targets -> wiki updates
```

## 使用用例

### 用例 1：每周追踪一个研究方向的新论文

场景：

- 你正在持续追踪 `VLA`、`manipulation`、`embodied AI` 等方向
- 你不想每周重复手工搜索、筛选、记笔记

你会做什么：

- 配好 `topics`
- 运行 `/discover` 或 daily digest
- 在 `inbox/` 里审批候选论文

LLM 会做什么：

- 从多源检索论文
- 给出候选卡片和推荐理由
- 对批准论文生成 `raw/source/` 和 `raw/notes/`
- 在你需要时继续编译进 `wiki/`

最终产出：

- 一个持续增长、可审核的论文追踪系统

### 用例 2：你已经知道某篇论文值得纳入知识库

场景：

- 你刚看到一篇重要论文
- 你不想先走一遍 inbox 审批流程

你会做什么：

- 直接运行 `/add-paper <doi|arxiv|url>`

LLM 会做什么：

- 解析论文元数据
- 抓取并清洗正文
- 生成 `raw/source/` 和 `raw/notes/`
- 可选写入 Zotero
- 为后续 `/compile` 做准备

最终产出：

- 这篇论文快速进入正式知识流程，而不是只停留在聊天记录里

### 用例 3：基于已有论文做综述、比较和问答

场景：

- 你想问：“我库里有哪些 VLA 架构，它们怎么比较？”
- 或者：“哪些论文讨论了 sim-to-real transfer 的问题？”

你会做什么：

- 运行 `/query <question>`

LLM 会做什么：

- 遍历 `wiki/` 和必要的 `raw/`
- 给出基于已有知识层的回答
- 将高价值结果沉淀到 `queries/`
- 生成 promotion targets，供后续升格到 canonical wiki 页面

最终产出：

- 不只是一次回答，而是一份可以复用的比较笔记、topic synthesis 或 contradiction note

### 用例 4：从现有知识图谱里找研究想法

场景：

- 你不只是想“总结已有工作”
- 你更想知道“下一步可以做什么”

你会做什么：

- 运行 `/ideas`
- 必要时再配合 `/lint` 和 `/query`

LLM 会做什么：

- 分析现有 topic、concept、tension 和 gap
- 找 recurring limitations、cross-cluster bridges、evaluation gaps
- 形成 idea analysis 或 idea memo
- 把结果回链到相关 topic / concept

最终产出：

- 你的 wiki 不只是论文存档，而是一个可以持续支持选题和研究判断的思考界面

## Knowledge Maintainer 心智模型

Paper Distill 最适合这样使用：

- **Obsidian** 是研究 IDE
- **wiki** 是长期维护的知识代码库
- **LLM** 是知识维护者
- **你** 决定纳入什么、强调什么、相信什么、继续追什么

也就是说，你不是在“调用一个论文聊天机器人”，而是在“协同一个研究知识维护者”。

这意味着：

- `/discover` 是让维护者发现候选证据
- `/process-inbox` / `/add-paper` 是让维护者摄取新证据
- `/compile` 是让维护者重编译知识结构
- `/lint` 是让维护者体检知识图谱
- `/query` 是让维护者在现有结构上回答并沉淀新认知
- `/ideas` 是让维护者把张力、空白和桥接机会转成研究假设

## Vault 目录结构

Paper Distill 在你的 Obsidian Vault 中写入：

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

其中：

- `index.md`：当前知识版图
- `log.md`：知识维护时间线
- `queries/`：查询资产、比较笔记、topic synthesis、idea analysis

更详细的目录说明见：[docs/reference/vault-layout.md](docs/reference/vault-layout.md)

## 常用命令

Paper Distill 同时支持：

- **自然语言入口**：适合新用户和探索式使用
- **`/命令` 入口**：适合熟练用户和高确定性工作流

例如：

- “帮我找最近的 VLA 论文” ≈ `/discover`
- “把这篇 arXiv 论文加入知识库” ≈ `/add-paper`
- “总结一下我库里关于 diffusion policy 的内容” ≈ `/query`
- “基于我现有知识库给几个研究方向” ≈ `/ideas`

如果你希望行为更稳定、更可预测，推荐优先使用 `/命令`。

- `/discover <query>`：发现并写入候选 inbox
- `/add-paper <doi|arxiv|url>`：直接纳入用户已批准论文
- `/process-inbox`：处理 `approved` inbox 项
- `/compile`：把原始笔记编译为 wiki
- `/query <question>`：查询知识库并沉淀高价值结果
- `/ideas`：基于知识图谱生成研究思路
- `/lint`：体检知识库与维护状态
- `/summarize <doi|url>`：快速预览论文

完整命令说明见：[docs/reference/commands.md](docs/reference/commands.md)

## Zotero 模式

支持三种模式：

- `local_first`：写本地导入包到 `Paper Distill/zotero/imports/`
- `web_api`：通过 Zotero Web API 创建条目
- `disabled`：完全跳过 Zotero handoff

如果你的目标是“**不要把 PDF 保存到 Zotero 目录**”，优先使用：

- `local_first`
- 或 `disabled`

## 文档导航

- [docs/README.md](docs/README.md)：文档总入口
- [docs/product/overview.md](docs/product/overview.md)：产品概览
- [docs/product/workflow.md](docs/product/workflow.md)：核心工作流
- [docs/product/knowledge-model.md](docs/product/knowledge-model.md)：知识模型
- [docs/integration/installation.md](docs/integration/installation.md)：安装与启动
- [docs/integration/clients.md](docs/integration/clients.md)：Claude / Codex / OpenClaw 兼容性
- [docs/reference/configuration.md](docs/reference/configuration.md)：配置项说明
- [docs/reference/vault-layout.md](docs/reference/vault-layout.md)：目录结构与资产关系
- [docs/reference/commands.md](docs/reference/commands.md)：命令参考
- [docs/releases/v1-launch.md](docs/releases/v1-launch.md)：初代发布说明

## 文档版本与追溯

当前 `docs/` 已按“发布文档”和“历史文档”分层：

- 当前发布与使用文档：`docs/product`、`docs/integration`、`docs/reference`、`docs/releases`
- 历史计划与评审文档：`docs/archive`

这意味着：

- 新用户看到的是产品文档
- 历史架构演进仍然保留，可追溯

## License

MIT
