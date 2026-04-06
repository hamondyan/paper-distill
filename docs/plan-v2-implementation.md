# plan-v2 实施记录

> 对应计划：`docs/plan-v2.md`
> 实施日期：2026-04-06
> 覆盖范围：Phase 1（持久化状态层）+ Phase 2（EDC 编译中间层）

---

## 新增文件

### `server/database.py`

**目的**：为整个系统提供统一的 SQLite 持久化层，取代原来"所有规则停留在 prompt 层"的状态。

**主要内容**：
- 定义 6 张表的 schema：`concept_registry` / `concept_aliases` / `concept_merge_history`（权威层）、`compile_state` / `compile_deps`（可重建索引层）、`maintenance_queue`（权威层）
- `get_db(vault_path)` — 线程安全的单例连接管理，WAL 模式，外键约束开启
- `init_db(vault_path)` — 确保数据库文件和表结构存在，供 vault 初始化时调用
- `_now_iso()` — 统一的 ISO-8601 时间戳工具函数，供其他模块 import
- `export_authority_state()` / `import_authority_state()` — 权威层表的 JSON 导出/导入，作为 `.gitignore` 掉的 `.db` 文件的备份手段

**数据库位置**：`Paper Distill/.state/paper-distill.db`，通过 `.gitignore` 排除 git 追踪。

---

### `server/concept_registry.py`

**目的**：建立 Concept Canonical Registry，解决同一概念在 vault 中以多种形式出现（大小写、缩写、拼写变体）导致碎片化的问题。

**主要内容**：
- `slugify(text)` — 将任意表面形式归一化为稳定 slug（唯一 ID）
- `register_concept(vault_path, canonical, type, aliases)` — 注册新概念；遇到同 slug 或可自动合并的情况时直接返回已有条目，避免重复
- `resolve_concept(vault_path, surface_form)` — 三步解析：alias 精确匹配 → slug 直接匹配 → 缩写展开匹配
- `merge_concepts(vault_path, from_id, to_id, reason)` — 合并两个概念：重映射所有 alias、合并 paper_count、递增 version、记录 merge_history、删除源概念
- `list_concepts()` / `get_concept()` / `update_paper_count()` / `promote_concept()` — 基础 CRUD
- `auto_merge_eligible(a, b)` — 判断两个表面形式是否满足三条硬编码自动合并规则：
  1. 归一化后 slug 完全相同
  2. 缩写 ↔ 全称在白名单中（硬编码 20 个常见 AI/Robotics 缩写）
  3. 英美拼写变体（behavior/behaviour 等 20 对）
- `_expand_slug_candidates(slug)` — 注册新概念时生成候选 slug 列表，用于在 registry 中查找可合并的已有条目（修复了初始实现中 `_candidate_slugs` 未定义导致所有注册调用失败的 bug）
- `backfill_registry_from_wiki(vault_path)` — 一次性迁移工具，从现有 `wiki/concepts/`、`wiki/methods/` 的 frontmatter 和 `wiki/papers/` 的 wikilinks 反向填充 registry，标记 `compile_state.schema_version = "legacy"`

---

### `server/maintenance.py`

**目的**：实现 lint → 工单生成 → 人工确认 → 执行的完整维护闭环，并通过去重保证 lint 多次运行不产生重复工单。

**主要内容**：
- `reconcile_maintenance_queue(vault_path, lint_results, stats_results, auto_confirm)` — 核心函数：将 `lint_vault_sync()` 和 `vault_stats_sync()` 的纯读结果转换为去重后的工单。从 lint 结果提取 `semantic_duplicates`（→ merge_candidate）、`orphaned_articles`（→ orphan_fix）、`missing_concept_stubs`（→ missing_concept_stub）；从 stats 结果提取 `promotion_candidates`（→ promote_to_topic）和 `stale_topics`（→ stale_topic_refresh）
- `get_pending_tasks()` — 按 type/status 过滤查询工单，默认只返回非终态（pending/confirmed/processing）
- `confirm_task()` / `reject_task()` / `complete_task()` — 工单生命周期管理
- `_auto_confirm_eligible(task_type, payload)` — 对 merge_candidate 类型的工单，检查是否满足自动确认条件（复用 `auto_merge_eligible` 的三条规则）
- `_dedup_key(task_type, payload)` — 生成工单的去重键，只使用身份字段（如文件路径对、概念名），不含相似度分数等可变元数据，确保同一问题不重复入队

**关键设计**：`lint_vault_sync()` 保持纯读，不直接写队列，只有显式调用 `reconcile_maintenance_queue()` 才会写入。

---

### `server/compile_ir.py`

**目的**：实现 EDC 三阶段编译流程的中间层，使 wiki 内容可从结构化 IR 重新生成（无需重读 PDF），并提取张力信号供 idea-generator 使用。

**主要内容**：
- `validate_ir(ir_data)` — schema 验证，检查必需字段（citekey、title、authors、candidate_concepts、tension_fields）及 tension_fields 子键，返回错误列表（无外部依赖）
- `write_ir(vault_path, citekey, ir_data)` — 验证后写入 `compiled_ir/{citekey}.json`，注入 `schema_version`
- `read_ir(vault_path, citekey, resolved)` — 读取原始或 resolved IR
- `resolve_ir(vault_path, citekey)` — Resolve 阶段：读取原始 IR，对每个 `candidate_concept` 调用 `resolve_concept()` 或 `register_concept()`，写出 `compiled_ir/{citekey}_resolved.json`，附带 `_resolutions` 字段记录 entity linking 结果
- `aggregate_tension_signals(vault_path, min_occurrence, topic_filter)` — 扫描所有 `_resolved.json`，聚合：
  - `recurring_limitations`：出现在 ≥ min_occurrence 篇论文中的 limitation 关键词
  - `all_assumptions`：平铺的假设列表（供 LLM 检测矛盾）
  - `open_question_clusters`：按关键词聚类的开放问题
  - `negative_results`：负面结果列表
- `commit_compile_result(vault_path, page_id, page_type, content, frontmatter, ir_path, deps)` — EDC Write 阶段唯一出口：渲染 frontmatter block、计算 managed sections 的 content_hash（用于后续冲突检测）、写入 markdown 文件、原子更新 `compile_state` 和 `compile_deps`
- `get_compile_state(vault_path, page_id, page_type)` — 查询单个页面的编译状态
- `_TYPE_DIR` — 模块级常量，page_type → wiki 子目录路径映射

---

### `tests/test_registry_maintenance.py`

**目的**：覆盖 Phase 1 的所有核心路径，防止回归。

**测试类**：SlugifyTest / AutoMergeTest / RegisterConceptTest / ResolveConceptTest / MergeConceptsTest / ListConceptsTest / PromoteConceptTest / ReconcileTest / TaskLifecycleTest / ExportImportTest / BackfillTest，共 31 个测试。

---

### `tests/test_compile_ir.py`

**目的**：覆盖 Phase 2 的 EDC 完整流程。

**测试类**：ValidateIRTest / WriteIRTest / ResolveIRTest / AggregateTensionTest / CommitCompileResultTest，共 17 个测试。

---

## 修改文件

### `server/server.py`

新增 14 个 MCP tools（Tool 17–30）：

| Tool | 名称 | 阶段 | 职责 |
|------|------|------|------|
| 17 | `register_concept_tool` | Phase 1 | 注册概念到 registry |
| 18 | `resolve_concept_tool` | Phase 1 | 解析 surface form → canonical |
| 19 | `merge_concepts_tool` | Phase 1 | 合并概念，记录历史 |
| 20 | `list_concepts_tool` | Phase 1 | 查询概念列表（可按 type/paper_count 过滤） |
| 21 | `reconcile_maintenance` | Phase 1 | 运行 lint+stats → 生成去重工单 → auto-confirm |
| 22 | `get_maintenance_queue` | Phase 1 | 查看工单（可按 type/status 过滤） |
| 23 | `resolve_maintenance_task` | Phase 1 | 确认/拒绝/完成工单 |
| 24 | `export_db_state` | Phase 1 | 导出权威层表为 JSON（备份用） |
| 25 | `backfill_registry` | Phase 1 | 从现有 wiki frontmatter 反向填充 registry |
| 26 | `write_compile_ir` | Phase 2 | 接收 agent 产出的 IR JSON，验证后写盘 |
| 27 | `resolve_compile_ir` | Phase 2 | 批量 entity linking（纯 Python，无 LLM） |
| 28 | `commit_compile_result` | Phase 2 | Write 阶段：原子写盘 + 更新 compile_state |
| 29 | `query_tension_signals` | Phase 2 | 聚合 IR 张力信号，供 idea-generator 使用 |
| 30 | `get_compile_state` | Phase 2 | 查询页面编译状态 |

---

### `server/vault_ops.py`

**目的**：将 Phase 2 所需目录和路径函数纳入 vault 结构管理。

**改动**：
- `_SECTION_DIRS` 新增 `"compiled_ir": "compiled_ir"` 和 `"state": ".state"` — 确保 `ensure_vault_structure()` 创建这两个目录
- `ensure_vault_structure()` 末尾新增 `init_db(vault_path)` 调用 — vault bootstrap 时自动初始化 SQLite
- 新增三个路径函数：
  - `compiled_ir_path(vault_path, citekey)` → `compiled_ir/{citekey}.json`
  - `compiled_ir_resolved_path(vault_path, citekey)` → `compiled_ir/{citekey}_resolved.json`
  - `state_db_path(vault_path)` → `.state/paper-distill.db`

---

### `server/vault_lint.py`

**两处改动，各自独立：**

**改动 1：registry 一致性检查**（Phase 1）

在 `lint_vault_sync()` 末尾新增 `registry_unregistered` 检查：扫描 `wiki/concepts/` 下所有文件，对比 `concept_registry` 表，找出未注册的概念。如果数据库尚未初始化（`init_db` 未调用过）则静默跳过，不影响现有 lint 功能。

**目的**：使 lint 能发现 registry 与 wiki 文件系统的不一致，引导用户运行 `backfill_registry`。

**改动 2：IR 张力信号消费**（Phase 2）

在 `analyze_knowledge_graph_sync()` 末尾新增 IR 消费通路：调用 `aggregate_tension_signals(vault_path, min_occurrence=2)`，将结果中的 `recurring_limitations`、`open_question_clusters`、`negative_results` 合并到 `gaps` 字典，并在 `gap_summary` 中增加对应计数。

**目的**：使 idea-generator 从 `analyze_knowledge_graph` 一次调用中同时获得基于 wikilink 图的结构性 gap 和基于 IR 的精确张力信号，形成"wiki 层 + IR 层"双源分析。当 `compiled_ir/` 不存在或为空时静默降级，不影响无 IR 的 vault。

---

### `skills/wiki-compile/SKILL.md`

**目的**：将编译流程从"直接写 wiki"升级为 Extract → Resolve → Write 三阶段协议。

**改动**：
- 新增"EDC Compile Protocol"章节，说明三阶段的具体操作步骤和工具调用
- Extract 阶段：agent 负责 LLM 提取，产出含 `tension_fields` 和 `candidate_concepts` 的 IR，提交 `write_compile_ir`
- Resolve 阶段：调用 `resolve_compile_ir`（纯 Python，无 LLM），完成 entity linking
- Write 阶段：调用 `commit_compile_result`（取代直接调用 `upsert_wiki_article`），managed sections 用注释标记，`## My Notes` 永远不被覆盖
- 新增 Concept Registry 使用规则：编译前先 `resolve_concept`，编译后提交新 alias
- 保留原有 subagent 并行协议，改为 parallel Extract → batch Resolve → sequential Write

---

### `skills/idea-generator/SKILL.md`

**目的**：说明如何消费 IR 张力信号，使 idea 生成有更精确的结构化依据。

**改动**：
- Step 1 说明中区分"graph-based"（始终可用）和"IR-based"（需要 compiled_ir/）两类 gap 来源
- 新增 IR-based 来源说明：`ir_recurring_limitations`、`ir_open_question_clusters`、`ir_negative_results`
- 新增对 `query_tension_signals(min_occurrence=2)` 的调用说明，用于获取完整 `all_assumptions` 列表供 LLM 检测跨论文的假设矛盾

---

### `.gitignore`

新增 `Paper Distill/.state/` 排除规则，防止 SQLite 二进制文件进入版本控制。

---

## 简化优化

| 问题 | 改动 |
|------|------|
| `_now_iso()` 在 `concept_registry.py` 和 `maintenance.py` 中各定义一次 | 统一移入 `database.py`，两个模块改为 `from server.database import _now_iso` |
| `compile_ir.py` 的 `commit_compile_result` 内部重复 import `paper_distill_root` | 删除函数内 import，使用模块顶层已有的 import |
| `compile_ir.py` 的 `_TYPE_DIR` 字典每次调用时重新创建 | 提升为模块级常量 |
| `backfill_registry_from_wiki` 中概念和方法的入库循环逻辑几乎相同（~20 行 × 2） | 提取为内部辅助函数 `_backfill_entity(rel_dir, name_key, entity_type, count_key)` |

---

## 测试覆盖

| 测试文件 | 新增测试数 | 覆盖内容 |
|---------|----------|---------|
| `tests/test_registry_maintenance.py` | 31 | slugify、auto-merge 三条规则、registry CRUD、merge 历史、maintenance 去重、工单生命周期、export/import、backfill |
| `tests/test_compile_ir.py` | 17 | schema 验证、write/read、resolve entity linking、tension 信号聚合、commit 原子写盘 + DB 更新 |

全套测试：**113 个**，全部通过。

---

## 未实施部分（Phase 3，待后续）

- `maintenance.py` 中 `execute_merge()` / `execute_promote()` / `execute_refresh()` — 自动执行合并/提升/刷新操作并更新 vault 文件
- `vault_lint.py` 中三级刷新策略判断（Patch / Section Merge / Full Rewrite）
- Embedding-based semantic dedup（Phase 1 修正 7 中已推迟）
