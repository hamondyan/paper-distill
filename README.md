# Paper Distill

Paper Distill 是一款面向 Obsidian 的、**人类审批 + LLM 维护** 的研究知识库工作流。

它的目标不是做一次性的论文问答，而是把论文发现、证据采集、阅读笔记、知识编译、查询沉淀、研究想法生成，统一到一个可持续增长的知识系统里。

- **用户角色**：编辑者、审稿人、研究负责人
- **LLM 角色**：知识维护者
- **知识资产**：不是聊天记录，而是持续更新的 Obsidian wiki

## English Summary

Paper Distill is a human-approved research knowledge workflow for Obsidian.
It packages one MCP-backed runtime for **Claude**, **Codex**, and **OpenClaw**, and turns paper discovery, ingestion, synthesis, querying, and idea generation into a maintained wiki rather than disposable chat output.

For English-side integration details, see [docs/integration/clients.md](docs/integration/clients.md).

## 它解决什么问题

大多数 LLM 文档工作流停留在 “上传文件 -> 检索 -> 回答”。

Paper Distill 走的是另一条路线：

1. 先发现或指定论文
2. 由人决定是否纳入知识库
3. 把原始论文转成稳定的证据层
4. 生成结构化阅读笔记
5. 再编译成可链接、可维护、可持续演化的 wiki
6. 之后的查询、综述、idea 结果也继续沉淀为知识资产

一句话说：**它把论文知识从“每次临时检索”变成“持续维护的研究系统”。**

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

## Knowledge Maintainer 心智模型

Paper Distill 最适合这样使用：

- **Obsidian** 是研究 IDE
- **wiki** 是长期维护的知识代码库
- **LLM** 是知识维护者
- **你** 决定纳入什么、强调什么、相信什么、继续追什么

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
