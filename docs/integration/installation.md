# 安装与启动

- 文档类型：集成文档
- 状态：当前
- 版本：v1 初代发布
- 更新日期：2026-04-07
- 适用对象：用户、集成方

## 推荐方式

推荐使用 `uv`，因为仓库自带的 MCP launcher 默认就是按 `uv` 运行的。

## 先决条件

- Python 3.10+
- `uv`
- 一个可写的 Obsidian Vault

## 安装

### 方式一：推荐，使用 uv

```bash
uv sync
```

运行服务：

```bash
uv run paper-distill-server
```

### 方式二：使用 conda

```bash
conda create -n paper-distill python=3.11
conda activate paper-distill
pip install -e .
paper-distill-server
```

如果你打算直接使用仓库自带的 launcher，仍建议同时安装 `uv`。

## 最小配置

最小可用配置只需要：

- `VAULT_PATH`

示例：

```bash
export VAULT_PATH="/absolute/path/to/your/obsidian/vault"
```

或者在本地创建 `settings.json`：

```json
{
  "paper_distill": {
    "vault_path": "/absolute/path/to/your/obsidian/vault"
  }
}
```

## 常用环境变量

- `VAULT_PATH`
- `OPENALEX_EMAIL`
- `S2_API_KEY`
- `ZOTERO_MODE`
- `ZOTERO_COLLECTION_NAME`
- `ZOTERO_LOCAL_EXPORT_DIR`
- `ZOTERO_LIBRARY_ID`
- `ZOTERO_API_KEY`

## 启动入口

统一 MCP 入口：

- [`.mcp.json`](../../.mcp.json)

默认 launcher：

- [`scripts/run-mcp.sh`](../../scripts/run-mcp.sh)

其行为本质上等价于：

```bash
uv --directory <repo-root> run paper-distill-server
```

## 相关文档

- [clients.md](clients.md)
- [../reference/configuration.md](../reference/configuration.md)
