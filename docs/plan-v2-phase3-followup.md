# plan-v2 Phase 3 跟进审查

日期：2026-04-06

## 背景

本文件基于对以下内容的交叉检查形成：

- [docs/plan-v2-implementation.md](/Users/huang/Desktop/paper-distill-v2/docs/plan-v2-implementation.md)
- 当前仓库代码实现
- 当前测试覆盖

目标不是重复实施记录，而是回答两个更实际的问题：

1. Phase 1 和 Phase 2 是否已经足够完整，可以直接无脑进入 Phase 3？
2. 如果要继续推进，Phase 3 应该优先修什么，怎么改更稳？

## 当前结论

总体判断：

- **Phase 1 已基本成形，可视为核心目标已落地**
- **Phase 2 主骨架已落地，但还没有完全收口**
- **可以继续进入 Phase 3 设计与实现，但不建议跳过本文件列出的收口项**

验证依据：

- 新增相关测试：`uv run pytest -q tests/test_registry_maintenance.py tests/test_compile_ir.py`
- 全量测试：`uv run pytest -q tests/`
- 当前结果：`113 passed`

这意味着本轮升级不是“只有文档没有实现”，而是已经有相当实质的代码和测试基础。

## Phase 1 落地情况

已落实的部分：

- SQLite 持久化层已存在：`server/database.py`
- Concept Registry 已存在：`server/concept_registry.py`
- Maintenance Queue 已存在：`server/maintenance.py`
- 相关 MCP tools 已在 `server/server.py` 中暴露
- `vault_ops.py` 已创建 `compiled_ir/` 与 `.state/` 目录
- `lint_vault_sync()` 仍保持纯读，队列写入通过显式 `reconcile_maintenance_queue()` 完成

因此，**Phase 1 不再是“设计稿”，而是已经可用的状态层与工单层。**

## Phase 2 落地情况

已落实的部分：

- `Compile IR` 模块已存在：`server/compile_ir.py`
- 原始 IR / resolved IR 的写入与读取已实现
- Resolve 阶段已通过 Concept Registry 完成 entity linking
- `compile_state` / `compile_deps` 已从 `citekey` 泛化为 `page_id + page_type`
- `analyze_knowledge_graph_sync()` 已能够消费 IR 张力信号
- `idea-generator` skill 已更新，明确了 IR-based gap 来源

因此，**Phase 2 的核心骨架已经成立：IR 已经不是纸面概念，而是系统中的真实中间层。**

## 当前仍未收口的问题

下面这些问题不会推翻 plan-v2 的方向，但会直接影响 Phase 3 的稳定性与后续维护成本。

### 问题 1：Write 阶段还没有真正实现“手工编辑保护”

当前 `commit_compile_result()` 会：

- 计算 managed section 的 `content_hash`
- 写入 markdown
- 更新 `compile_state` / `compile_deps`

但它**不会**：

- 读取旧文件并比对历史 `content_hash`
- 检测当前页面是否被用户手改
- 保留 `## My Notes`
- 合并 managed / unmanaged 区块

换句话说，当前实现已经把“冲突检测”和“用户笔记保护”写进了文档与 skill，但代码本身仍然是**整文件覆盖写盘**。

这会带来两个风险：

- Obsidian 中的手工编辑可能被静默覆盖
- Phase 3 一旦开始自动 merge / promote / refresh，这种风险会放大

### 问题 2：IR schema 对 ideation 仍然偏窄

当前 `Compile IR` 已包含：

- `limitations`
- `assumptions`
- `open_questions`
- `negative_results`

这已经比旧系统强很多，但对最终的 Idea 生成目标来说，仍然不够。

当前仍缺少更强的结构化字段，例如：

- `failure_modes`
- `transfer_constraints`
- `benchmark_scope`
- `claimed_novelty`

此外，虽然设计上已经强调张力字段应保留 `source_ref`，但当前 schema 校验并未真正约束这些结构。

这意味着：

- 系统已经能做“更好的 recurring limitations / open questions”
- 但还不足以稳定支撑“更好的假设冲突、迁移机会、评价裂缝分析”

### 问题 3：wiki-compile skill 已要求消费 confirmed maintenance tasks，但执行接口尚未落地

当前 `skills/wiki-compile/SKILL.md` 已要求：

- compile 前检查 `get_maintenance_queue(status="confirmed")`
- 处理 pending merge / promote tasks

但 Phase 1 / 2 还没有真正落地这些执行入口：

- `execute_merge()`
- `execute_promote()`
- `execute_refresh()`

这意味着 skill 对 agent 提出了一个“当前无法真正完成的动作要求”。

现在的状态更像是：

- 队列存在
- 人工确认存在
- 但执行器仍在 Phase 3

因此在进入 Phase 3 之前，skill 需要避免给出“现在已经能执行”的错觉。

## 对 Phase 3 的建议

### 建议 1：Phase 3 的第一优先级不是 topic refresh，而是 Write 安全闭环

在真正做自动 merge / promote / refresh 前，先补齐 `commit_compile_result()` 的冲突保护逻辑。

建议落地顺序：

1. 读取目标页面现有内容
2. 提取旧版 managed sections
3. 比对数据库中的旧 `content_hash`
4. 如果 hash 一致：允许替换 managed sections
5. 如果 hash 不一致：
   - 不直接覆盖
   - 返回 `conflict_detected`
   - 记录 maintenance task 或显式冲突结果
6. 将 `## My Notes` 或其他未托管区块保留在 managed markers 外

只有这一步稳定了，后面的自动执行器才值得上线。

### 建议 2：Phase 3 应先补“执行器”，再补“高级触发器”

建议把 Phase 3 分成两个层次：

#### Phase 3A：执行闭环

先实现：

- `execute_merge(task)`
- `execute_promote(task)`
- `execute_refresh(task)`
- concept version 更新后基于 `compile_deps` 做受影响页面定位

这部分是“把 queue 从待办系统变成真正的维护闭环”。

#### Phase 3B：高级触发器

再实现：

- contradiction candidate
- recurring limitation spike
- cross-cluster bridge
- benchmark evaluation split

原因很简单：如果执行器还没稳定，就算触发器再聪明，系统也只会更会“发现问题”，不会更会“解决问题”。

### 建议 3：Phase 3 不应只修治理，还应继续补强 IR schema

进入 Phase 3 时，建议同步扩展 IR 的 ideation 相关字段，而不是把它推到更后面。

推荐至少增加：

- `failure_modes`
- `transfer_constraints`
- `benchmark_scope`
- `claimed_novelty`

同时给张力字段统一一个更明确的结构，例如：

```json
{
  "claim": "...",
  "source_ref": "...",
  "section": "...",
  "confidence": 0.0
}
```

这样后续：

- `query_tension_signals()`
- `analyze_knowledge_graph_sync()`
- `idea-generator`

都能更稳定地消费这些信号，而不是继续在 prose 上做二次启发式提取。

### 建议 4：调整 skill 文案，使其与 Phase 3 前的真实能力一致

在 Phase 3 执行器真正完成之前，建议把 `wiki-compile` skill 中这类表述改得更准确：

- 不要写成“process any pending merge/promote tasks”
- 改成“if execution tools are available, consume confirmed tasks; otherwise surface them before write”

理由：

- 现在 queue 已经存在，但执行器尚未完成
- skill 应准确反映系统能力，避免 agent 依据不存在的能力做错误假设

### 建议 5：把“Phase 2 完成标准”和“Phase 3 启动条件”明确区分

建议在后续计划中明确写出：

**Phase 2 完成标准：**

- IR 可写入、可读取、可 resolve
- compile_state / compile_deps 正确记录
- idea generator 能消费 IR 聚合信号

**Phase 3 启动条件：**

- Write 冲突保护已落地
- queue 执行器接口已定义清楚
- 页面 ID / page_type 覆盖 paper/concept/method/topic

这样能避免“Phase 2 核心功能可用”被误解成“已经足够安全自动改写知识库”。

## 建议的 Phase 3 任务清单

建议下一轮实现按这个顺序推进：

1. `commit_compile_result()` 冲突检测与 managed/unmanaged 分区保留
2. `execute_merge()`：更新 registry + 生成受影响页面列表 + 重跑 Resolve/Write
3. `execute_promote()`：concept → topic 的 type/version 演进与页面迁移
4. `execute_refresh()`：基础的 topic refresh（先不做高级语义触发）
5. IR schema 扩展：`failure_modes / transfer_constraints / benchmark_scope / claimed_novelty`
6. 高级触发器接入：contradiction / recurring limitation spike / cross-cluster bridge / evaluation split

## 最终判断

本轮 Phase 1 / Phase 2 **不是失败的半成品**，而是已经把计划中最难的骨架真正搭起来了：

- 状态层有了
- Registry 有了
- IR 有了
- idea backend 已开始消费 IR
- 测试也守住了

真正的问题在于：

- 写入安全还没闭环
- Phase 3 执行器还没落地
- ideation 所需的 IR 深度还可以继续加强

因此，后续最合理的策略不是回头重做，而是：

- 承认 Phase 1 / 2 已基本成立
- 用本文件列出的收口项把它们补稳
- 再进入 Phase 3 的自动治理与增量刷新
