# Paper Distill: Wiki-Compile & Maintenance 改进报告 v2

> 本报告综合了三轮 review 讨论的共识。核心立场：保留治理骨架，但将 compile 和 maintenance 的设计目标从"治理良好的 wiki 系统"升级为"治理良好且对 Idea 生成友好的知识系统"。

---

## 1. 现状评估

### 1.1 系统已经做对的事

- **raw / wiki 分层明确**：原文抓取层与知识蒸馏层职责清晰
- **concept canonicalize / dedup / alias 需求已被识别**：系统知道 concept 需要治理
- **并发编译已设计 Map → Reduce → Write 协议**：意识到多 subagent 不能各写各的
- **安全写接口已存在**：`upsert_wiki_article()` 而非裸写文件
- **维护信号已初步覆盖**：`stale_topics`、`promotion_candidates`、`semantic_duplicates` 等均有检测

### 1.2 核心问题总结

所有规则停留在 prompt / skill 层，没有下沉为系统保证的硬协议。具体表现为八个结构性缺陷：

| # | 问题 | 本质 |
|---|------|------|
| 1 | wiki-compile 是协议而非引擎 | 一致性依赖 agent 表现 |
| 2 | 缺少 concept canonical registry | 同一概念反复以不同名出现 |
| 3 | maintenance 只报警不闭环 | 发现问题后无后续动作链 |
| 4 | semantic duplicate 检测太弱 | 只有标题 token overlap |
| 5 | topic 生命周期管理缺失 | 信息化石或粗暴重写二选一 |
| 6 | 编译状态只有 compiled: true | 粒度太粗，不支持增量刷新 |
| 7 | 缺少知识中间表示 | 从单篇论文直接写终态 wiki |
| 8 | compile 和 maintenance 松耦合 | 系统知道哪里老化，但下次编译不自动修 |

此外，还存在一个方向性问题：**当前 compile 的信息抽取维度偏向"摘要式"（contributions / methods / results），缺少 Idea 生成最依赖的张力信号（limitations / failure modes / assumptions / open questions）**。

---

## 2. 架构原则

### 2.1 状态分层原则

**人读的元数据留 frontmatter，机器查的关系放 SQLite。**

Obsidian 是用户的主交互面，vault 必须在脱离后端时仍可自解释。但复杂的依赖图、版本追踪、工单状态不应塞进 markdown 文件。

SQLite 中的数据进一步区分为两类：

| 类别 | 示例 | 特点 |
|------|------|------|
| **可重建索引层** | dependency index、反向引用、派生统计 | 可从 vault + IR 文件重建 |
| **权威操作层** | maintenance queue、merge history、人工确认的 canonical mapping | 有时序语义，不可从静态文件重建 |

这意味着即使 DB 损坏，系统仍可回到一个可恢复状态（索引层重建），只丢失工单执行历史（操作层）。

### 2.2 职责分离原则

**Maintenance 管线和 Ideation 管线必须分开。**

- `maintenance_queue` 只处理 wiki 治理任务：merge、promote、refresh、orphan fix
- Idea 生成直接消费 wiki + Compile IR，不经由 maintenance queue 中转
- 两条管线的唯一交汇点是 wiki 本身：maintenance 让 wiki 更干净，idea generator 读更干净的 wiki

不要把 `assumption_conflict_candidate`、`method_transfer_candidate` 这类半成品 idea 混入 maintenance queue，否则队列职责会变模糊。

### 2.3 其他原则

- **最小可行方案先行**：先跑通核心流程，再根据实际瓶颈加固
- **中间层优于一步到位**：compile 应产出可审查、可重放的中间产物
- **渐进式迁移**：新论文走新 pipeline，旧论文在增量刷新中逐步迁移

---

## 3. 改进方案

### 3.1 Concept Canonical Registry

**问题**：同一概念以不同名称反复出现，alias 只在单次 compile 会话中临时处理。

**方案**：在后端引入持久化的概念主表（SQLite）。

```sql
CREATE TABLE concept_registry (
    id            TEXT PRIMARY KEY,       -- slug，如 "vision-language-action"
    canonical     TEXT NOT NULL,          -- 显示名，如 "Vision-Language-Action Models"
    type          TEXT NOT NULL,          -- concept | method | topic
    version       INTEGER DEFAULT 1,     -- 每次实质性更新递增
    promoted      BOOLEAN DEFAULT FALSE,
    paper_count   INTEGER DEFAULT 0,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE concept_aliases (
    alias         TEXT PRIMARY KEY,
    concept_id    TEXT NOT NULL,
    FOREIGN KEY (concept_id) REFERENCES concept_registry(id)
);

CREATE TABLE concept_merge_history (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    from_concept  TEXT NOT NULL,
    to_concept    TEXT NOT NULL,
    merged_at     TEXT NOT NULL,
    reason        TEXT
);
```

**关键行为**：

- 每次 compile 前，agent 先查 registry 做 entity linking
- compile 产出的 candidate concepts 提交回 registry，由后端决定是创建新条目还是映射到已有条目
- merge 记录在 `concept_merge_history` 中，保证可溯源
- promotion（concept → topic）更新 registry 的 type 和 version 字段，同时触发页面迁移

**自动 merge 的边界硬约束**：

自动 merge 只允许以下三种 case（在代码中硬编码，放宽边界需要改代码而非调参数）：

1. 完全同 slug（如 slug 归一化后一致）
2. 缩写与全称在人工维护的白名单中（如 VLA ↔ Vision-Language-Action）
3. 明确的 spelling variant（如 behavior ↔ behaviour）

其余所有 case（包括 embedding 相近但语义未证实的）只进人工确认队列。这是为了保护 Idea 生成所依赖的"近邻但不等价"概念边界。

---

### 3.2 EDC 三阶段编译与 Compile IR 中间层

**问题**：当前 compile 从单篇论文直接写终态 wiki，且信息抽取维度偏向摘要式，缺少张力信号。

**方案**：将 compile 拆分为 Extract → Resolve → Write 三阶段。

```
raw/notes/{citekey}.md  +  raw/source/{citekey}/（张力字段回看）
        │
        ▼
   ┌─────────────┐
   │   Extract    │  LLM 输出结构化 JSON
   └──────┬──────┘
          ▼
  compiled_ir/{citekey}.json   ← 可审查、可重放的中间产物
          │
          ▼
   ┌─────────────┐
   │   Resolve    │  Python 后端对 registry 做 entity linking
   └──────┬──────┘
          ▼
  compiled_ir/{citekey}_resolved.json
          │
          ▼
   ┌─────────────┐
   │    Write     │  Python 渲染为 wiki markdown
   └─────────────┘
```

**Compile IR 结构（面向 Idea 生成的完整 schema）**：

```json
{
  "citekey": "smith2024vla",
  "extract_version": 1,
  "sources_consulted": ["raw/notes/smith2024vla.md", "raw/source/smith2024vla/"],

  "paper_facts": {
    "title": "...",
    "authors": ["..."],
    "year": 2024,
    "venue": "..."
  },

  "contributions": ["..."],
  "methods_used": ["diffusion-policy", "transformer-backbone"],
  "key_results": ["..."],

  "tension_fields": {
    "assumptions": [
      {
        "claim": "Assumes access to dense reward signal",
        "source_ref": "raw/source/smith2024vla/section-3.2"
      }
    ],
    "limitations": [
      {
        "claim": "Only tested on tabletop manipulation; no mobile robot eval",
        "source_ref": "raw/source/smith2024vla/section-6"
      }
    ],
    "negative_results": [
      {
        "claim": "Performance degrades significantly with >3 objects",
        "source_ref": "raw/source/smith2024vla/table-4"
      }
    ],
    "failure_modes": ["..."],
    "open_questions": ["..."],
    "transfer_constraints": [
      {
        "claim": "Sim-to-real gap not addressed; all results in simulation",
        "source_ref": "raw/source/smith2024vla/section-7"
      }
    ],
    "benchmark_scope": "...",
    "claimed_novelty": "..."
  },

  "candidate_concepts": [
    {"surface_form": "VLA", "context": "..."},
    {"surface_form": "vision-language-action model", "context": "..."}
  ],
  "candidate_methods": ["..."],
  "candidate_topics": ["..."]
}
```

**关键设计决策**：

1. `tension_fields` 作为一等结构与 `contributions`/`methods_used`/`key_results` 并列，而不是散落在 prose 中
2. 张力字段中的每个条目保留 `source_ref`，指向 `raw/source` 中的具体 section/table/span，避免 raw/notes 压缩后的信息损耗被永久固化
3. Extract 阶段以 `raw/notes` 为主要输入，但对张力相关字段允许（且鼓励）回看 `raw/source`

**核心价值**：

- markdown 排版规则变了 → 只需重跑 Write，不需重调 LLM
- concept schema 更新了 → 只需重跑 Resolve + Write
- 中间产物可审查，降低 LLM 幻觉风险
- Idea generator 可以直接消费 IR 中的 `tension_fields`，获得比 wiki page prose 更结构化的张力信号

---

### 3.3 版本化编译状态

**问题**：`compiled: true` 粒度太粗，无法表达增量刷新需求。

**方案**：编译状态拆分为两层存储。

**Frontmatter（人读的轻量元数据）**：

```yaml
compile_version: 3
last_compiled: 2024-06-15
```

**SQLite（机器查的依赖关系，属于"可重建索引层"）**：

```sql
CREATE TABLE compile_state (
    citekey           TEXT PRIMARY KEY,
    compile_version   INTEGER NOT NULL,
    schema_version    TEXT NOT NULL,       -- 如 "2024-06"
    compiled_at       TEXT NOT NULL,
    ir_path           TEXT                 -- 指向 compiled_ir/ 下的 JSON
);

CREATE TABLE compile_deps (
    citekey       TEXT NOT NULL,
    dep_type      TEXT NOT NULL,           -- concept | method | topic
    dep_id        TEXT NOT NULL,
    dep_version   INTEGER NOT NULL,        -- 对应 concept_registry.version
    FOREIGN KEY (citekey) REFERENCES compile_state(citekey),
    FOREIGN KEY (dep_id) REFERENCES concept_registry(id)
);
```

**增量刷新逻辑**：当 `concept_registry` 中某个 concept 的 `version` 递增时（如因 merge 或 promotion），查询 `compile_deps` 可精确定位所有依赖该 concept 旧版本的 pages，触发 Resolve + Write 重编译。

**版本演进规则**：

| 事件 | version 变化 |
|------|-------------|
| alias 新增/修改 | 不变（alias 是 slug 的映射，不影响语义） |
| canonical name 修改 | +1 |
| merge（A 并入 B） | B.version +1 |
| promotion（concept → topic） | +1，同时 type 变更 |

---

### 3.4 Maintenance Queue 与 Lint 解耦

**问题**：lint 发现问题后只输出提示，没有衔接到后续动作。

**方案**：分三层设计，保持 lint 的纯读特性。

```
lint_vault() / vault_stats()        ← 纯读、纯分析、无副作用
        │
        ▼ 返回结构化结果
reconcile_maintenance_queue()       ← 显式步骤，负责去重、对齐、写入
        │
        ▼
  maintenance_queue (SQLite)        ← 权威操作层
        │
        ▼ compile 启动时消费
  执行 merge / promote / refresh
        │
        ▼
  maintenance_queue (status=done)
```

**为什么要解耦**：

- `lint_vault()` 和 `vault_stats()` 当前最宝贵的特征是"纯读、重复调用无副作用"
- 如果它们每运行一次就写工单，会导致同一问题被重复排队、测试不稳定、读写职责混淆
- `reconcile_maintenance_queue()` 负责将"当前发现"与"现有队列"做去重、对齐、升级或关闭

**Queue 表结构**：

```sql
CREATE TABLE maintenance_queue (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type   TEXT NOT NULL,     -- merge_candidate | promote_to_topic
                                   -- | stale_topic_refresh | orphan_fix
    payload     TEXT NOT NULL,     -- JSON，包含具体操作参数
    confidence  REAL,              -- 0.0-1.0
    status      TEXT DEFAULT 'pending',  -- pending | confirmed | processing
                                         -- | done | rejected
    created_at  TEXT NOT NULL,
    resolved_at TEXT
);
```

**自动确认规则**：仅限 3.1 节定义的三种硬编码 case。其余均需人工确认。

---

### 3.5 Topic Refresh 混合触发策略

**问题**：topic 要么长期不更新成为信息化石，要么被粗暴重写丢掉演化历史。

**方案**：采用基础触发 + 高优先级插队的混合模型。

**基础触发器（数量/时间/结构）**：

| 变更规模 | 策略 | 触发条件 |
|---------|------|---------|
| 小 | **Patch** | 新增 1-2 篇相关论文，无新 concept 引入 |
| 中 | **Section Merge** | 某 concept 被 promoted 为子章节，或新增 3-5 篇论文引入新视角 |
| 大 | **Full Rewrite** | 超过 6 个月未更新 且 相关论文数翻倍以上 |

**高优先级插队触发器（语义张力信号）**：

| 信号 | 来源 | 前置条件 |
|------|------|---------|
| contradiction candidate | IR 的 `tension_fields` 中出现与 topic 现有论断冲突的 claim | 需要 IR 张力字段先就位 |
| recurring limitation spike | 同一 limitation 在 ≥3 篇新 paper 的 IR 中重复出现 | 需要 IR 张力字段先就位 |
| cross-cluster bridge | 新 paper 同时链接两个此前不相交的 concept cluster | 需要 compile_deps 先就位 |
| benchmark evaluation split | 新 paper 引入 topic 内部尚未消化的评价维度 | 需要 IR 张力字段先就位 |

**实施顺序**：先上基础触发器（Phase 2 即可），高优先级触发器在 IR 张力字段和 compile_deps 稳定后再接入（Phase 3）。

**Changelog 机制**：

- Full Rewrite 时，旧版 summary 保留在 `## Changelog` 章节
- Patch 只追加 related papers 列表和微调具体数据点
- Section Merge 重组章节结构，但保留已有核心论述

```markdown
## Changelog

### 2024-06 (v3, Full Rewrite)
此次重写反映了 diffusion-based policy 方向的爆发式增长...
> 旧版摘要（v2）：Imitation learning 主要分为 BC 和 IRL 两大流派...

### 2024-01 (v2, Patch)
新增 3 篇 diffusion policy 相关工作。

### 2023-09 (v1, Initial)
初始编译，覆盖 12 篇核心论文。
```

---

### 3.6 Semantic Dedup 增强

**问题**：当前 `semantic_duplicates` 只做标题 token overlap。

**方案**：混合候选生成策略，当前规模下无需持久化向量。

```
              所有 concept names + aliases
                        │
            ┌───────────┴───────────┐
            ▼                       ▼
  Token Overlap Filter      Embedding 相似度
  (快速粗筛, 现有能力)    (临时计算, 余弦相似度)
            │                       │
            └───────────┬───────────┘
                        ▼
             Candidate Pairs (合并两个来源)
                        │
                        ▼
            LLM 判断 (仅对边界 case)
            "这两个概念是否指同一件事？"
                        │
                ┌───────┴───────┐
                ▼               ▼
          是同义词          高相似但不等价
                │               │
                ▼               ▼
      写入 maintenance    保留为独立 concept
      queue (merge)       （保护 ideation 边界）
```

**关键约束**：对于"高相似但不完全等价"的 case（如同一方法在 robotics 和 NLP 中的不同变体），宁可保留独立 concept 也不过早合并。Idea 生成最有价值的信号往往来自这些近邻概念的边界差异。

---

### 3.7 Idea 生成的消费接口

**本方案不改动 idea-generator 本身**，但通过治理改进让它的输入质量显著提升：

| 之前 idea-generator 消费的 | 改进后额外可消费的 |
|---------------------------|-------------------|
| wiki/papers 中的 prose 文本 | Compile IR 中结构化的 `tension_fields` |
| wiki/concepts 中的概述 | Registry 中经过 canonicalize 的 concept graph |
| concept-paper 的隐式关联 | `compile_deps` 中显式的依赖关系图 |
| 散落在 prose 中的 limitations | IR 中独立字段 + source evidence pointers |

Idea generator 可以直接查询：

- "哪些 limitation 在 ≥3 篇论文中重复出现？"→ 聚合 IR 的 `tension_fields.limitations`
- "哪些 concept 对之间有桥接论文但尚未合并？"→ 查 `compile_deps` 的交叉关系
- "某个 assumption 的原文证据是什么？"→ 通过 `source_ref` 回溯 `raw/source`

这些查询在当前系统中要么做不到，要么需要 LLM 从 prose 中重新提取。

---

## 4. 数据架构总览

### 4.1 SQLite 表一览

| 表名 | 类别 | 用途 |
|------|------|------|
| `concept_registry` | 权威操作层 | 概念主表，含 canonical name / type / version |
| `concept_aliases` | 权威操作层 | 别名映射 |
| `concept_merge_history` | 权威操作层 | merge 操作的溯源记录 |
| `compile_state` | 可重建索引层 | 每篇论文的编译版本和 schema 版本 |
| `compile_deps` | 可重建索引层 | paper → concept 的依赖关系（含版本） |
| `maintenance_queue` | 权威操作层 | 治理工单队列 |

### 4.2 文件系统新增

| 路径 | 用途 |
|------|------|
| `compiled_ir/{citekey}.json` | Extract 阶段产出的原始 IR |
| `compiled_ir/{citekey}_resolved.json` | Resolve 阶段产出的已链接 IR |
| `.paper-distill.db` | SQLite 数据库文件 |

### 4.3 Frontmatter 保留字段

wiki 页面的 frontmatter 只保留人类可读的元数据：

```yaml
# wiki/papers/{citekey}.md
title: "..."
authors: ["..."]
year: 2024
tags: [robotics, imitation-learning]
compile_version: 3
last_compiled: 2024-06-15
```

依赖关系、版本追踪、工单状态等机器状态不进入 frontmatter。

---

## 5. 实施路径

### Phase 1：

**目标**：系统拥有持久化状态，从"靠 agent 自觉"变为"有注册表可查"。

- [ ] 在 `server.py` 中初始化 SQLite（`.paper-distill.db`）
- [ ] 建立 `concept_registry` + `concept_aliases` + `concept_merge_history` 三张表
- [ ] 实现 `register_concept()`, `resolve_concept()`, `merge_concepts()` API
- [ ] 为 `merge_concepts()` 硬编码三种自动 merge 准入条件（slug match / 白名单缩写 / spelling variant）
- [ ] 建立 `maintenance_queue` 表
- [ ] 实现 `reconcile_maintenance_queue()`，从 lint 结果生成去重后的工单
- [ ] `lint_vault()` / `vault_stats()` 保持纯读，不直接写队列

**验证标准**：手动编译 5 篇论文后，所有 concept 能在 registry 中查到且无重复；lint 运行多次不产生重复工单。

### Phase 2：

**目标**：compile 产出含张力信号的可审查中间层。

- [ ] 定义 Compile IR 的 JSON Schema（含完整 `tension_fields`）
- [ ] 实现 Extract 阶段：LLM 以 `raw/notes` 为主输入，张力字段回看 `raw/source`，输出 IR JSON
- [ ] 实现 Resolve 阶段：Python 后端拿 IR 中的 candidate concepts 对 registry 做 entity linking
- [ ] 实现 Write 阶段：Python 将 resolved IR 渲染为 wiki markdown
- [ ] 建立 `compile_state` + `compile_deps` 表
- [ ] 上线基础触发器的 Topic Refresh（数量 / 时间 / 结构）

**验证标准**：修改 markdown 模板后能不调 LLM 重新生成所有 wiki 页面；IR 中 tension_fields 非空率 > 80%。

### Phase 3：

**目标**：maintenance 闭环运行；高优先级触发器上线。

- [ ] compile 启动时先消费 `maintenance_queue` 中 status=confirmed 的工单
- [ ] 实现 Patch / Section Merge / Full Rewrite 三级 Topic Refresh 策略
- [ ] 实现增量刷新：concept version 更新后通过 `compile_deps` 定位受影响 pages，重跑 Resolve + Write
- [ ] 增强 semantic dedup：加入 embedding 相似度候选对生成 + LLM 判断
- [ ] 接入高优先级触发器（contradiction candidate / recurring limitation spike / cross-cluster bridge）
- [ ] 验证 Idea generator 能直接消费 IR 中的 `tension_fields` 进行结构化查询

**验证标准**：合并两个 concept 后所有引用页面自动更新；Idea generator 能回答"哪些 limitation 在 ≥3 篇论文中重复出现"。

---

## 6. 风险与注意事项

**避免过度工程化**：当前论文规模（几十到几百篇）下，向量持久化、分布式队列等优化不必要。先跑通核心流程，再根据实际瓶颈加固。

**保持 Obsidian 的独立可用性**：SQLite 是后端加速层，vault 本身必须在无后端时仍然是一个有意义的 markdown 知识库。不要让 vault 退化为"数据库的渲染层"。

**LLM 成本控制**：引入 Compile IR 的核心价值之一是减少重复 LLM 调用。Schema 变更只需重跑 Resolve + Write（纯 Python），不需重跑 Extract（LLM 调用）。

**Source of truth 契约**：用户可以在 Obsidian 中手动编辑 wiki markdown。需要定义清楚：手动编辑后下一次 compile 是否覆盖？建议的默认策略是"如果 frontmatter 中 compile_version 与 DB 一致，则 compile 可覆盖；如果用户手改过导致不一致，则 compile 跳过该页并标记冲突"。

**张力字段的提取质量**：`tension_fields` 的价值完全取决于 Extract 阶段 LLM 的提取质量。建议在 Phase 2 初期对 10-20 篇论文做人工抽查，校准 prompt 后再大规模运行。

**自动 merge 的边界守护**：自动 merge 的三种准入条件必须在代码中硬编码为白名单/规则匹配。如果未来需要放宽（如加入 embedding 相似度自动合并），必须作为显式的代码变更提交，不能通过调参数滑过去。