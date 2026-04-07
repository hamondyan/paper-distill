> 基于 review-2-v2.md 的三轮讨论共识，将系统从"治理良好的 wiki 系统"升级为"治理良好且对 Idea 生成友好的知识系统"。

## 总体评估

review 报告识别了八个结构性缺陷，核心问题是：**所有规则停留在 prompt/skill 层，没有下沉为系统保证的硬协议**。本计划按 Phase 1 → Phase 2 → Phase 3 分批实施，每个 Phase 可独立验证。

---

## User Review Required

> [!IMPORTANT]
> 本次改动涉及 **新增 SQLite 数据库层**、**重构 compile 流程**、**新增 MCP tools**，是系统级架构升级。请审阅以下重点：

1. **SQLite 数据库位置**：.paper-distill.db 放在 vault 根目录下（与 Paper Distill/ 同级），方便 git 管理和备份
2. **Compile IR 路径**：Paper Distill/compiled_ir/ 放在 vault 内部，Obsidian 可以看到
3. **upsert_wiki_article 新增 topics section 支持**：当前只允许 papers/concepts/methods，需要扩展
4. **新 MCP 工具**：将新增 ~8 个 MCP tools，需要确认这些工具名是否合理

---

## Proposed Changes

### Phase 1: Concept Registry & Maintenance Queue (持久化状态层)

> **目标**：系统拥有持久化状态，从"靠 agent 自觉"变为"有注册表可查"

---

#### [NEW] database.py

SQLite 数据库初始化和管理模块。

- 初始化 .paper-distill.db，包含 6 张表
- concept_registry / concept_aliases / concept_merge_history (权威操作层)
- compile_state / compile_deps (可重建索引层，Phase 2 启用)
- maintenance_queue (权威操作层)
- 提供 get_db() 单例连接管理
- 提供 init_db(vault_path) 初始化函数

---

#### [NEW] concept_registry.py

Concept Canonical Registry 实现。

- register_concept(canonical, type, aliases=None) - 注册新概念
- resolve_concept(surface_form) - 查询概念（先精确匹配 alias，再 slug 归一化匹配）
- merge_concepts(from_id, to_id, reason) - 合并概念并记录历史
- list_concepts(type=None) - 列出所有概念
- get_concept(concept_id) - 获取单个概念详情 + 别名
- auto_merge_eligible(a, b) - 判断是否符合自动 merge 三种硬编码条件：
  1. 完全同 slug
  2. 缩写与全称在白名单中
  3. spelling variant (behavior/behaviour)

---

#### [NEW] maintenance.py

Maintenance Queue 管理。

- reconcile_maintenance_queue(lint_results, stats_results) - 从 lint 结果生成去重后的工单
- get_pending_tasks(task_type=None) - 查看待处理工单  
- confirm_task(task_id) / reject_task(task_id) - 人工确认/拒绝
- process_task(task_id) - 执行工单
- auto_confirm_eligible(task) - 判断是否符合自动确认条件

---

#### [MODIFY] server.py

新增 MCP tools：

- register_concept(canonical, type, aliases) - 注册概念到 registry
- resolve_concept(surface_form) - 解析概念名
- merge_concepts(from_id, to_id, reason) - 合并概念
- list_concepts(type) - 列出概念
- reconcile_maintenance(auto_confirm) - 运行 lint → 生成工单 → 自动确认符合条件的
- get_maintenance_queue(status, task_type) - 查看工单
- resolve_maintenance_task(task_id, action) - 处理工单

修改 bootstrap_vault() 以初始化 SQLite

---

#### [MODIFY] vault_lint.py

- lint_vault_sync() 和 vault_stats_sync() **保持纯读**，不直接写队列
- 增强 semantic_duplicates 检测：加入 embedding 候选对（临时计算，无需持久化）
- 增加 concept registry 一致性检查

---

### Phase 2: EDC 三阶段编译 & Compile IR (知识中间层)

> **目标**：compile 产出含张力信号的可审查中间层

---

#### [NEW] compile_ir.py

Compile IR (中间表示) 模块。

- CompileIR dataclass 定义完整 schema（含 tension_fields）
- extract_ir(citekey, raw_note_path, raw_source_path) → 产出 compiled_ir/{citekey}.json
- resolve_ir(citekey, ir_data, registry) → 对 candidate_concepts 做 entity linking → compiled_ir/{citekey}_resolved.json
- render_wiki(citekey, resolved_ir) → 渲染为 wiki markdown
- JSON Schema 验证

---

#### [MODIFY] vault_ops.py

- 新增 compiled_ir 目录到 _SECTION_DIRS 和 ensure_vault_structure
- 新增 compiled_ir_path(vault_path, citekey) 路径函数

---

#### [MODIFY] server.py

新增 MCP tools：

- extract_compile_ir(citekeys) - 批量 Extract（LLM 调用由 agent 完成，此工具负责接收结果并写入）
- resolve_compile_ir(citekeys) - 批量 Resolve（纯 Python，对 registry 做 entity linking）
- render_wiki_from_ir(citekeys) - 批量 Write（纯 Python，从 resolved IR 渲染 markdown）
- get_compile_state(citekey) - 查看编译状态

新增 compile_state / compile_deps 表内容管理。

---

#### [MODIFY] upsert_wiki_article

- 扩展支持 topics section
- 写入时同步更新 compile_state 和 compile_deps
- 支持 compile_version 管理

---

#### Frontmatter 精简

wiki page frontmatter 只保留人类可读元数据：
yaml
title: "..."
authors: ["..."]
year: 2024
tags: [robotics, imitation-learning]
compile_version: 3
last_compiled: 2024-06-15

依赖关系、版本追踪等机器状态进入 SQLite。

---

### Phase 3: Maintenance 闭环 & Topic Refresh (治理完整性)

> **目标**：maintenance 闭环运行；增量刷新逻辑上线

---

#### [MODIFY] maintenance.py

- 实现 execute_merge(task) - 执行概念合并 + 更新所有引用页面
- 实现 execute_promote(task) - 执行概念提升为 topic
- 实现 execute_refresh(task) - 触发 topic 刷新
- 增量刷新：concept version 更新后通过 compile_deps 定位受影响 pages

---

#### [MODIFY] vault_lint.py

- _compute_stale_topics() 加入三级刷新策略判断（Patch / Section Merge / Full Rewrite）
- 刷新建议写入结构化结果，由 reconcile_maintenance_queue() 消费

---

#### [MODIFY] Wiki compile skill

更新 SKILL.md：

- 编译流程从 "直接写 wiki" 改为 "Extract → Resolve → Write"
- 每次 compile 前先查 registry 做 entity linking
- 产出的 candidate concepts 提交回 registry
- compile 启动时先消费 maintenance_queue 中 status=confirmed 的工单

---

#### [MODIFY] Wiki lint skill

更新 SKILL.md：

- 增加 reconcile_maintenance 调用说明
- lint → reconcile → 人工确认 → execute 完整闭环

---

#### [MODIFY] Idea generator skill

更新 SKILL.md：

- 说明如何消费 Compile IR 中的 tension_fields
- 新增结构化查询能力说明

---

## Open Questions

> [!IMPORTANT]
> 1. **数据库文件位置**：.paper-distill.db 放在 vault 根目录还是 Paper Distill/ 内部？推荐放 vault 根目录，避免 Obsidian 索引 .db 文件。
> 2. **Compile IR 是否应被 git 管理**？IR 文件可从 raw 层重建（但需要 LLM），建议 git 管理以减少不必要的 LLM 调用。
> 3. **Phase 1 是否需要迁移已有 wiki 数据**？建议渐进式：新论文走新 pipeline，旧论文在增量刷新中逐步迁移。

---

## Verification Plan

### Phase 1 验证
- [ ] SQLite 数据库正确初始化，6 张表可用
- [ ] register_concept() → resolve_concept() 往返正确
- [ ] merge_concepts() 记录历史且别名重映射
- [ ] 自动 merge 三种条件正确判断
- [ ] lint 多次运行不产生重复工单
- [ ] 所有 MCP tools 可通过 server 正常调用

### Phase 2 验证
- [ ] Compile IR JSON 通过 schema 验证
- [ ] Extract → Resolve → Write 三阶段完整运行
- [ ] 修改 markdown 模板后能不调 LLM 重新生成
- [ ] compile_state / compile_deps 正确记录

### Phase 3 验证
- [ ] 合并概念后所有引用页面自动更新
- [ ] maintenance queue 完整闭环
- [ ] Topic refresh 三级策略正确触发

### 运行测试
bash
cd /Users/huang/Desktop/paper-distill-v2
python -m pytest tests/ -v


# Paper Distill: Wiki-Compile & Maintenance 架构升级实施计划 v2

> 基于 review-2-v2.md + 用户反馈修正 4 个 P1 + 4 个 P2 设计缺陷后的最终版本。

---

## P1 修正记录

### 修正 1: IR → Idea Backend 真实落地路径

**问题**：`analyze_knowledge_graph_sync` (vault_lint.py L477) 只读 wiki/papers frontmatter，不读 IR。最重要的价值链 "IR → 可聚合张力信号 → idea generator" 是断的。

**修正**：在 Phase 2 中新增 `query_tension_fields()` 聚合函数和对应 MCP tool，直接在 `analyze_knowledge_graph_sync` 中新增 IR 消费通路：

```python
# 新增到 vault_lint.py 或 compile_ir.py
def aggregate_tension_signals(vault_path: str) -> dict:
    """扫描 compiled_ir/ 下所有 _resolved.json，聚合 tension_fields。"""
    # 返回:
    # - recurring_limitations: [{claim, count, papers, source_refs}]
    # - assumption_conflicts: [{claim_a, claim_b, paper_a, paper_b}]
    # - open_question_clusters: [{theme, questions, papers}]
    # - negative_results: [{claim, paper, source_ref}]

# 修改 analyze_knowledge_graph_sync:
def analyze_knowledge_graph_sync(vault_path, user_topics=None):
    # ... 现有逻辑 ...
    # 新增: 消费 IR 张力信号
    tension = aggregate_tension_signals(vault_path)
    gaps["recurring_limitations"] = tension["recurring_limitations"]
    gaps["assumption_conflicts"] = tension["assumption_conflicts"]
    # ...
```

同时新增 MCP tool `query_tension_signals(min_occurrence=2, topic=None)`，让 idea-generator 可以直接发起结构化查询。

### 修正 2: compile_state/compile_deps 通用页面标识

**问题**：以 `citekey` 为主键只覆盖 paper pages，concept/topic pages 没有稳定 citekey。

**修正**：改为 `page_id (TEXT) + page_type (TEXT)` 复合逻辑键：

```sql
CREATE TABLE compile_state (
    page_id           TEXT NOT NULL,        -- "brohan2023rt2" 或 "diffusion-policy" 或 "robotics-manipulation"
    page_type         TEXT NOT NULL,        -- "paper" | "concept" | "method" | "topic"
    compile_version   INTEGER NOT NULL,
    schema_version    TEXT NOT NULL,
    compiled_at       TEXT NOT NULL,
    ir_path           TEXT,
    content_hash      TEXT,                 -- 内容哈希，用于冲突检测
    PRIMARY KEY (page_id, page_type)
);

CREATE TABLE compile_deps (
    page_id       TEXT NOT NULL,
    page_type     TEXT NOT NULL,
    dep_type      TEXT NOT NULL,            -- concept | method | topic
    dep_id        TEXT NOT NULL,
    dep_version   INTEGER NOT NULL,
    FOREIGN KEY (page_id, page_type) REFERENCES compile_state(page_id, page_type),
    FOREIGN KEY (dep_id) REFERENCES concept_registry(id)
);
```

### 修正 3: compile 元数据提交与内容写入分离

**问题**：`upsert_wiki_article` 是通用安全写盘接口，不应耦合 compile 元数据。

**修正**：保留 `upsert_wiki_article` 纯粹性，新增显式提交路径：

```python
# 新 MCP tool
@mcp.tool()
async def commit_compile_result(
    page_id: str,
    page_type: str,       # paper | concept | method | topic
    content: str,         # markdown body
    frontmatter: dict,
    ir_path: str | None = None,
    deps: list[dict] | None = None,  # [{dep_type, dep_id, dep_version}]
) -> dict:
    """写入编译产物 + 同步更新 compile_state/compile_deps。
    
    这是 EDC Write 阶段的唯一出口。与 upsert_wiki_article 的区别：
    - upsert_wiki_article: 通用写盘，不关心编译状态
    - commit_compile_result: 编译提交，原子性写盘 + 更新 DB
    """
```

### 修正 4: 数据库位置与管理策略

**问题**：SQLite 是二进制文件，放进 git 会带来噪声 diff 和合并问题。

**修正**：
- DB 路径：`Paper Distill/.state/paper-distill.db`
- 默认加入 `.gitignore`：`Paper Distill/.state/`
- 提供显式导出/导入机制：`export_db_state()` / `import_db_state()` 输出为 JSON
- DB 分两类管理：
  - **可重建索引层**（compile_state, compile_deps）：可从 vault + IR 重建，丢失无所谓
  - **权威操作层**（concept_registry, aliases, merge_history, maintenance_queue）：提供 JSON 导出备份

---

## P2 修正记录

### 修正 5: Extract tool 改名为 write_compile_ir

**问题**：`extract_compile_ir` 名字暗示工具自己做 Extract，但实际 LLM 调用由 agent 完成。

**修正**：改名为 `write_compile_ir(citekey, ir_json)` — 接收 agent 产出的 IR JSON，做 schema 验证后写入 `compiled_ir/{citekey}.json`。

### 修正 6: 手工编辑冲突策略细化

**修正**：引入三级冲突检测：

| 冲突类型 | 检测方式 | 处理策略 |
|---------|---------|---------|
| frontmatter 被手改 | `compile_version` 不一致 | 跳过，标记 `compile_conflict: true` |
| 正文 managed section 被手改 | `content_hash` 对比 `## Context` ~ `## Connections` 部分 | 跳过该 section，保留手工修改 |
| 正文 manual section (如 `## My Notes`) | 不在 managed 范围内 | 永远保留，compile 不触碰 |

managed sections 在 compile 模板中用注释标记：
```markdown
<!-- managed:start -->
## Context
...
<!-- managed:end -->

## My Notes  ← 永远不被覆盖
```

### 修正 7: Embedding dedup 移到 Phase 3

**修正**：Phase 1 的 vault_lint.py 只做 registry 一致性检查，不做 embedding。Embedding dedup 移到 Phase 3 与高优先级触发器一起上线。

### 修正 8: 最小 backfill 方案

**修正**：Phase 1 结束后执行一次性 backfill：

```python
async def backfill_registry_from_wiki(vault_path: str) -> dict:
    """从现有 wiki/papers frontmatter 回填 registry + compile_deps。
    
    不回填完整 IR（需要 LLM），只回填：
    - concepts frontmatter → concept_registry
    - methods frontmatter → concept_registry (type=method)  
    - paper → concept 引用关系 → compile_deps
    - compile_state 标记为 schema_version="legacy"
    """
```

---

## 最终实施方案

### Phase 1: Concept Registry + Maintenance Queue + 最小 Backfill

**新建文件：**

| 文件 | 职责 |
|------|------|
| `server/database.py` | SQLite 初始化、连接管理、表定义 |
| `server/concept_registry.py` | Concept Registry CRUD + 自动 merge 规则 |
| `server/maintenance.py` | Maintenance Queue + reconcile 逻辑 |

**修改文件：**

| 文件 | 改动 |
|------|------|
| `server/server.py` | 新增 7 个 MCP tools |
| `server/vault_ops.py` | `.state/` 目录 + compiled_ir 目录 |
| `server/vault_lint.py` | registry 一致性检查（纯读） |
| `pyproject.toml` | 无新依赖（sqlite3 是标准库） |
| `.gitignore` | 新增 `Paper Distill/.state/` |

**新增 MCP Tools：**

| 工具名 | 职责 |
|-------|------|
| `register_concept` | 注册概念到 registry |
| `resolve_concept` | 解析概念名 → canonical |
| `merge_concepts` | 合并概念 + 记录历史 |
| `list_concepts` | 查询概念列表 |
| `reconcile_maintenance` | lint → 工单生成 → auto-confirm |
| `get_maintenance_queue` | 查看工单状态 |
| `resolve_maintenance_task` | 处理/拒绝工单 |

---

### Phase 2: EDC 三阶段编译 + IR → Idea 消费链

**新建文件：**

| 文件 | 职责 |
|------|------|
| `server/compile_ir.py` | IR schema、validate、aggregate_tension_signals |

**修改文件：**

| 文件 | 改动 |
|------|------|
| `server/server.py` | 新增 write_compile_ir、resolve_compile_ir、commit_compile_result、query_tension_signals |
| `server/vault_lint.py` | analyze_knowledge_graph_sync 消费 IR 张力信号 |
| `skills/wiki-compile/SKILL.md` | Extract→Resolve→Write 流程 |
| `skills/idea-generator/SKILL.md` | tension_fields 消费方式 |

---

### Phase 3: Maintenance 闭环 + Topic Refresh + Embedding Dedup

（Phase 2 验证通过后再细化）

---

## 验证标准

### Phase 1
- `bootstrap_vault()` 后 `.state/paper-distill.db` 存在且 6 张表可用
- `register_concept() → resolve_concept()` 往返正确
- `merge_concepts()` 更新 alias 映射 + 写入 merge_history
- 自动 merge 三条件硬编码且边界准确
- lint 多次运行 → reconcile → 不产生重复工单
- backfill 后现有 wiki 概念全部进入 registry
- 现有测试不 break

### Phase 2
- IR JSON 通过 schema 验证
- Resolve 正确做 entity linking
- `commit_compile_result()` 原子写盘 + 更新 compile_state
- `query_tension_signals(min_occurrence=3)` 返回聚合结果
- `analyze_knowledge_graph_sync()` 包含 IR 来源的 gaps
- 修改 markdown 模板后能不调 LLM 重新生成
