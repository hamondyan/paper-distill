# 命令参考

- 文档类型：参考文档
- 状态：当前
- 版本：v1 初代发布
- 更新日期：2026-04-07
- 适用对象：用户、维护者

## 常用命令

### `/discover <query>`

作用：

- 发现候选论文并写入 `inbox/`

### `/add-paper <doi|arxiv|url>`

作用：

- 将用户已确认的论文直接纳入知识库主流程

### `/process-inbox`

作用：

- 处理 `status=approved` 的 inbox 候选

### `/compile`

作用：

- 把 `sources/notes/` 编译到 `wiki/`

### `/query <question>`

作用：

- 查询知识库
- 将高价值结果沉淀为 query assets

### `/ideas`

作用：

- 从知识图谱中提取 gap、tension 和研究想法

### `/lint`

作用：

- 体检知识库结构和维护状态

### `/summarize <doi|url>`

作用：

- 快速查看论文是否值得进入正式流程

## 推荐使用顺序

### 新论文发现

```text
/discover -> inbox approval -> /process-inbox -> /compile
```

### 用户已经确认某篇论文

```text
/add-paper -> /compile
```

### 围绕现有知识做研究

```text
/query -> /ideas -> /lint
```

## 命令与知识维护者角色

- `/discover`：发现候选证据
- `/process-inbox` / `/add-paper` / `/ingest`：执行 source ingest
- `/compile`：重编译知识结构
- `/query`：回答并沉淀新认知
- `/ideas`：从张力中生成假设
- `/lint`：检查系统健康

## 相关文档

- [../product/workflow.md](../product/workflow.md)
- [../product/overview.md](../product/overview.md)
