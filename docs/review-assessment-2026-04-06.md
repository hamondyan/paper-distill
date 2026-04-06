# Paper Distill v2 Review 采纳评估报告

日期：2026-04-06

## 结论概览

这份 review 命中了不少真实问题，尤其是 discovery 打分、arXiv 抓取容错、`query_vault` 对 Agent 的上下文负担，以及 prompt 体系的上限问题。

我的总体判断分成三类：

| 类别 | 条目 |
| --- | --- |
| 直接采纳 | 4.1, 4.2, 5.1, 5.3, 5.4, 7.1, 9.2 |
| 采纳问题意识，但改成更稳的方案 | 1.1, 1.2, 2.1, 2.2, 2.3, 3.1, 4.4, 5.2, 6.1, 6.2, 6.3, 7.2, 8.1, 9.1, 10, 11, 12 |
| 无需单独修改 | 4.3 |

建议优先级：

- P0：2.3, 4.1, 4.2, 5.1, 5.4
- P1：1.1, 1.2, 2.1, 2.2, 3.1, 4.4, 5.3, 9.2, 10
- P2：7.1, 7.2, 8.1, 11, 12
- P3：6.1, 6.2, 6.3

## 逐项评估

## 1. Discovery Pipeline

### 1.1 检索词生成缺乏语义转换

当前实现：
`server/server.py:1532-1536` 的 `_search_query_for_topic` 只是把 `keywords` 直接拼接成字符串；`agents/searcher.md:18-19` 也只是要求“用 topic keywords 构造 query”。

判断：
采纳问题意识，但改成更稳的方案。

原因：
你指出的问题是对的，当前 query 生成过于机械。  
但把 LLM 变成每次 discovery 的强制前置拦截器，会带来三个副作用：

1. 可复现性下降，同一 topic 多次运行可能得到不同搜索串。
2. 成本和延迟上升，而 discovery 是高频动作。
3. 容易把配置型 topic 搜索变成 prompt 工程问题。

更优方案：
先做“可配置、可复现”的 query expansion，而不是默认 LLM 改写：

- 在 topic 配置里增加 `aliases`, `must_include`, `must_exclude`, `source_overrides`。
- 针对 arXiv / Semantic Scholar / OpenAlex 分别渲染 source-aware query。
- 仅在“用户临时自然语言搜索”或“首轮结果明显跑偏”时，启用第二轮 LLM 重写。

优先级：
P1。


## 2. 打分算法

### 2.1 主题契合度依赖字面硬匹配

当前实现：
`server/server.py:1024-1035` 的 `_score_topic_fit` 只做 token overlap。

判断：
采纳问题意识，但改成更稳的方案。

原因：
你指出的语义盲区完全属实，`LLM` 与 `Large Language Models` 这类 acronym/full-name mismatch 现在确实会漏分。  
但直接引入本地 embedding 模型，会把当前“轻量 deterministic ranking”改造成带模型依赖的检索系统，工程复杂度会上升。

更优方案：
分两阶段做：

- 第一阶段：topic alias/synonym expansion，先解决 acronym、常见缩写、术语变体。
- 第二阶段：只对 top-K 候选做 embedding rerank，并放在 feature flag 后面。

优先级：
P1。

### 2.2 Impact 未做时间归一化

当前实现：
`server/server.py:1086-1091` 的 `_score_impact_v2` 只看绝对引用量并做 log cap；recency 在 `1050-1083` 单独算。

判断：
采纳问题意识，但改成更稳的方案。

原因：
问题真实存在。当前公式会偏好老论文的绝对引用数。  
但如果直接改成 Citation Velocity，也会出现两个新问题：

1. 新论文早期引用数噪声很大。
2. 当前多源数据里 `citation_count` 缺失并不少，纯 velocity 退化严重。

更优方案：
采用 hybrid impact：

- `impact = log(citations) + velocity_component`
- velocity 只在论文年龄超过一个最小月数时启用
- 同时重新调低 recency 权重，避免 recency 与 velocity 双重奖励新论文

优先级：
P1。

### 2.3 rejected_keywords 闭环缺失

当前实现：
`server/config.py:94-98` 已有 `rejected_keywords`。  
`agents/reviewer.md:36-40, 51-56` 也写了应当惩罚。  
但 `server/server.py:1110-1124` 的 `_score_author_preference_v2` 只处理 whitelist author 和 preferred venue，没有任何 rejected keyword 逻辑。

判断：
采纳问题意识，但改成更稳的方案。

原因：
这是 review 里最明确、最应该补齐的真实缺口之一。  
但我不建议直接“一票否决”或总分乘 `0.1`，因为 rejected keyword 可能出现在 related work、error analysis、baseline 描述中，直接 veto 会误杀。

更优方案：
新增显式的负偏好项，而不是魔法乘子：

- 对 title、abstract、venue 做 phrase-aware 匹配。
- 分级惩罚：title 命中 > abstract 命中 > 其他字段命中。
- 只对高置信 rejected phrase 做强惩罚，对弱命中做 soft penalty。

优先级：
P0。

## 3. 阅读笔记框架

### 3.1 CRGP-DNL 应向 DNL-v2 重构

当前实现：
`templates/raw-note.md.j2:1-22` 是 7 个平铺 section。  
`server/vault_ops.py` 的 `_RAW_NOTE_SECTIONS` 和 `build_crgp_dnl` 也都围绕这 7 个字段工作。  
`skills/using-paper-distill/SKILL.md` 里还把 CRGP-DNL 当作 mandatory 约束。

判断：
采纳问题意识，但改成更稳的方案。

原因：
你说的“故事线”和“实验硬通货”混在一起，这个判断是对的。  
但如果直接把 raw note 的 canonical schema 从 CRGP 改成另一套字段，会影响 capture、compile、prompt、模板、已有笔记兼容。

更优方案：
保持 machine-stable 的底层字段不变，重构呈现层：

- 底层继续保留 `Context / Related Work / Gap / Proposal / Key Results / Discussion / Next Steps`
- 模板层改成 grouped layout：
  - Metadata
  - Why Read
  - Core Logic Chain
  - Figures & Experiments
  - Insights & Next Steps
- compile 阶段仍消费旧字段，避免一次性重构全链路

优先级：
P1。

## 4. 原文抓取与清洗

### 4.1 process_inbox 缺少 PDF fallback

当前实现：
`server/server.py:1780-1789` 调 `_prepare_ingestion_candidate`。  
`server/server.py:485-512` 的 `_prepare_ingestion_candidate` 只走 `capture_arxiv_source`；异常直接返回 error。  
相比之下，`add_paper` 的 direct-add 路径在 `server/server.py:920-981` 已经具备 PDF recover 分支。

判断：
直接采纳。

原因：
这是一个明确的可靠性缺口，而且现有代码里已经有可复用的 PDF recover 路径，收益高、风险低。

建议实现：
不要只是在 `process_inbox` 里“缝一段 fallback”，而是抽成共享 helper：

- `capture_source_with_fallback(...)`
- 首选 `capture_arxiv_source`
- 失败后退回 `fetch_pdf_text` + `_source_doc_from_text`
- 保留 `capture_method` 与 `capture_fidelity`

优先级：
P0。

### 4.2 全量删除行内引用，破坏回溯能力

当前实现：
`server/arxiv_capture.py:32, 56-59` 会删掉 `[...]` citation token。  
`server/arxiv_capture.py:211-218` 还会把 `.ltx_ref` 直接 `decompose()`。

判断：
直接采纳。

原因：
这条判断非常准确。现在不仅 bibliographic noise 被删，连正文里承载语义的引用 token 也被删掉了，确实会造成句子断裂和来源痕迹丢失。

建议实现：

- `.ltx_ref` 不再 `decompose()`，改成保留文字内容。
- `_CITATION_NOISE_RE` 只清 bibliography context，不对正文全局清洗。
- figure/table/ref token 尽量以原文本或标准化 placeholder 形式保留下来。

优先级：
P0。

### 4.3 图表漂移、正文锚点遗失

当前实现：
`server/arxiv_capture.py:490-531` 会把正文段落和 `figcaption` 都留在原位置；  
`server/arxiv_capture.py:566-592` 只是额外在底部生成 `Figure/Table/Equation Snapshot`。

判断：
无需单独修改。

原因：
这条 review 部分属实，但不是一个独立问题。  
当前实现并没有把所有图表相关内容都“抽到底部后彻底脱节”，正文里的 caption 其实还在。真正导致 “See Figure 2” 失真的主因，还是 4.2 中对 `.ltx_ref` 和 `[...]` 的粗暴删除。

建议：
把 4.3 并入 4.2 处理即可。先修引用 token 保留，再观察是否还需要额外 anchor 占位符。

优先级：
不单独立项。

### 4.4 Gap 提取策略过于单薄

当前实现：
`server/arxiv_capture.py:776-785` 仅靠 `however/challenge/limited/bottleneck/hard/difficult` 这类关键词抓 gap。

判断：
采纳问题意识，但改成更稳的方案。

原因：
问题真实存在。  
但在 raw 层引入 `spaCy` dependency parsing，会明显增加依赖体积、启动成本和部署复杂度，而且未必比一套 section-aware heuristic 稳定。

更优方案：

- 只从 abstract + introduction 抽 gap，不从 result/evaluation 抽。
- 对 “limited dataset / limited benchmark” 这类 evaluation 描述加黑名单。
- 增加 discourse pattern：`however`, `despite`, `remains challenging`, `still fails to` 等模式。
- 用句子打分替代单 token 触发。

优先级：
P1。

## 5. Vault Query 与 Agent 交互

### 5.1 query_vault 下发字段过重

当前实现：
`server/vault_query.py:73-114` 会把 frontmatter 原样返回。  
`server/server.py:1482-1510` 的 `query_vault` tool 也没有 projection / detail level。

判断：
直接采纳。

原因：
这条判断成立。对 inbox / raw / wiki 混合检索时，直接把 `abstract`, `summary`, `why_recommended` 等长字段全部吐给 Agent，确实会造成 token 浪费和注意力偏移。

建议实现：

- `query_vault` 增加 `detail="compact|full"`，默认 `compact`
- compact 模式下按 section 保留最小寻址字段
- 长文本字段只在 `full` 或显式 `fields=` 请求时返回

优先级：
P0。

### 5.2 增加极短摘要字段 TLDR-Mini

当前实现：
系统已有 `tldr` / `summary`，但没有专门的极短 preview 字段。

判断：
采纳问题意识，但改成更稳的方案。

原因：
“瘦身后 Agent 失去最基本语境嗅觉”这个担心是合理的。  
但我不建议把 `tldr_mini` 作为一个新的持久化字段写进所有 note，因为这会扩大 schema 面。

更优方案：
优先做 query-time 派生字段，而不是 write-time 新 schema：

- 新增返回字段 `preview_text`
- 优先取 `tldr`
- 否则取 `summary` 首句
- 再否则从 `abstract` 截断 12-20 词

优先级：
P1。

### 5.3 status 枚举缺少语义说明

当前实现：
`server/server.py:1494-1499` 的 tool docstring 只说可以按 `status` 过滤；  
`vault_ops.py` 里的 inbox index 有状态列表，但没有进入 `query_vault` 的接口说明层。

判断：
直接采纳。

原因：
这是一个轻量但高收益的改动。当前状态值对人类是清晰的，对 Agent 并不总是清晰。

建议实现：

- 在 `query_vault` tool docstring 增加 status guide
- 返回结果里可附带 `status_help` 或统一文档说明

优先级：
P1。

### 5.4 引入时间窗口与 limit

当前实现：
`server/server.py:1482-1510` 和 `server/vault_query.py:73-114` 都没有 `limit`、`updated_after`、`modified_after` 一类参数。

判断：
直接采纳。

原因：
这条建议非常实用，而且直接解决大库情况下的上下文压垮问题。

建议实现：

- 增加 `limit`
- 增加 `sort_by`，至少支持 `updated_at` / `retrieved_at` / file mtime
- 增加 `updated_after` 或 `days_back`

优先级：
P0。

## 6. 知识库自愈与语义维护

### 6.1 Semantic Deduplication 后台巡查合并

当前实现：
`server/vault_lint.py` 和 `skills/wiki-lint/SKILL.md` 目前主要是 deterministic structural lint，不做语义近重复合并。

判断：
采纳问题意识，但改成更稳的方案。

原因：
方向是对的，但“后台自动合并 + 全局替换链接”对现阶段过重，误合并的代价很高。

更优方案：
先做 suggestion-first，而不是 auto-merge：

- 产出 semantic duplicate report
- 基于 alias、标题归一化、backlink overlap、概念共现度给出 merge candidates
- 只在用户确认后执行 rename / relink

优先级：
P3。

### 6.2 概念自动提权为 Topic

当前实现：
没有这类机制。

判断：
采纳问题意识，但改成更稳的方案。

原因：
完全自动提权会让 ontology 拓扑频繁震荡。  
对于研究知识库来说，“稳定命名 + 人工确认”通常比“自动晋升”更重要。

更优方案：

- 在 `vault_stats` / `wiki-lint` 中增加 promotion candidates 报告
- 依据 paper_count、topic coverage、recent growth 给出建议
- 最终由人确认是否升级为 topic

优先级：
P3。

### 6.3 Evergreen synthesis / 常青树更新触发器

当前实现：
`wiki-compile` 目前是手动或轻量 compile，没有 topic/article 的自动刷新调度。

判断：
采纳问题意识，但改成更稳的方案。

原因：
“旧综述逐渐过时”这个问题是真实的。  
但直接自动重写 landscape/article，容易覆盖用户已经形成的结构与措辞。

更优方案：

- 先做 stale-topic detection
- 触发条件只负责“生成更新队列”，不直接重写
- 更新采用 patch-style prompt，优先写 `Recent Developments`，避免全文覆盖

优先级：
P3。

## 7. Macro-Emergence

### 7.1 Idea Generation 增加边界条件约束校验

当前实现：
`skills/idea-generator/SKILL.md:21-38` 的 idea card 只有 gap type / evidence / feasibility / novelty / priority，没有显式的 assumption conflict 检查。

判断：
直接采纳。

原因：
这条建议很有价值，而且落地点非常清楚：就是在 idea card schema 里加入“先唱反调”的约束。

建议实现：
不要做隐藏式 CoT，直接把检查项显式化：

- `Assumptions`
- `Conflict`
- `Bridge / What must be invented`
- `Kill Criteria`

优先级：
P2。

### 7.2 Daily Digest 从 RSS 罗列升级为冲突雷达

当前实现：
`skills/daily-digest/SKILL.md:12-21` 和 `templates/daily-log.md.j2:1-20` 还是典型的静态清单式输出。

判断：
采纳问题意识，但改成更稳的方案。

原因：
你说得对，当前 digest 更像列表汇总，不像“知识冲突雷达”。  
但我不建议完全抛弃 deterministic list，因为那是 digest 的可审计基底。

更优方案：
保留现有候选列表，同时增设两个可选 LLM 区块：

- `Emerging Patterns`
- `Challenges to Existing Notes`

优先级：
P2。

## 8. MCP Server 与协议层

### 8.1 收缩并垂直化写库接口

当前实现：
review 这里有一半对，一半不对。  
不对的部分是：当前 server 并不是只有 `add_paper` 和 `query_vault` 两个宏观接口，也不是完全依赖泛型写文件。  
实际上已经存在多个意图级工具：`search_papers`, `score_papers`, `query_vault`, `discover_papers`, `process_inbox`, `add_paper`, `lint_vault`, `vault_stats`, `analyze_knowledge_graph`。

判断：
采纳问题意识，但改成更稳的方案。

原因：
真正的缺口不是“没有 intent API”，而是“少数高风险写操作还没有被业务 API 封装”。

更优方案：

- 新增 `update_learned_preferences(...)`
- 新增 `upsert_wiki_article(...)` 或 compile-only write API
- 对 settings / wiki 写入做 schema validation 与 path guard

优先级：
P2。

## 9. Agent Prompting Engine

### 9.1 注入 `<thought_process>` 式内部反思链

当前实现：
`agents/searcher.md`, `agents/reviewer.md`, `agents/compiler.md` 基本都是说明式 zero-shot prompt，没有明确的批判性推理 rubric。

判断：
采纳问题意识，但改成更稳的方案。

原因：
问题判断是对的，方案本身我不建议照搬。  
强制要求 hidden CoT / internal monologue，不利于维护、调试和安全边界，而且并不稳定提升结果质量。

更优方案：
把“反思链”改成显式 rubric，而不是隐藏推理标签：

- Reviewer：`Why ingest`, `Why skip`, `What evidence is missing`
- Compiler：`What is actually supported by raw/source`, `What is inference`, `What should stay conservative`

优先级：
P2。

### 9.2 增加 Golden Few-Shot Examples

当前实现：
`agents/searcher.md`, `agents/reviewer.md`, `agents/compiler.md` 都没有 example；确实是 zero-shot。

判断：
直接采纳。

原因：
这条建议和当前缺口高度一致，且落地成本低。  
对于 reviewer / compiler 这类质量上限依赖强模板的 agent，1-2 个高质量例子往往比继续堆空泛要求更有效。

建议实现：

- reviewer 增加一个“高分收录”和一个“高分但应跳过”的例子
- compiler 增加一个“好 paper page”和一个“好 concept linking”例子
- 例子要短，不要把 prompt 撑爆

优先级：
P1。

## 10. paper-discover 缺少 Exploration Loop

当前实现：
`server/server.py:1689-1701` 对每个 topic 只做一次 query -> search -> score -> cap，没有任何结果质量自检与第二轮改写。

判断：
采纳问题意识，但改成更稳的方案。

原因：
这是一个很值得做的升级。  
但不建议做无限自主循环，bounded 2-pass loop 更可控。

更优方案：

- Pass 1：正常搜索
- 诊断：统计题材漂移、医学词占比、非目标 venue 占比、arXiv bind 失败率
- Pass 2：只有在诊断越界时才追加 negative terms / alias rewrite

优先级：
P1。

## 11. 并发编译缺少 Reduce 阶段知识协商

当前实现：
`skills/wiki-compile/SKILL.md:75-77` 允许并行 subagent compile，但没有一个显式 concept reconciliation 阶段。

判断：
采纳问题意识，但改成更稳的方案。

原因：
问题本身成立。  
但让 subagent 之间“当场协商”概念归并，复杂度高且容易相互踩写。

更优方案：
把协调放在主线程 Reduce 阶段，而不是 worker 内部：

- worker 只产出 candidate concepts
- main agent 在合并时做 canonicalization
- 再统一决定 concept 新建、合并、别名登记

优先级：
P2。

## 12. paper-ingest 与 paper-add 结构性冗余

当前实现：
`skills/paper-add/SKILL.md` 与 `skills/paper-ingest/SKILL.md` 的流程高度重叠，只是在用户触发语义上做了区分。

判断：
采纳问题意识，但改成更稳的方案。

原因：
的确有冗余。  
但我不建议直接把两个用户可见命令合并成一个名字，因为它们代表的用户心智并不完全相同。

更优方案：

- 保留 `/add-paper` 和 `/ingest` 这两个入口
- 抽取共享底层协议文档或共享 helper skill
- 在 skill routing 层统一复用相同的 resolve/capture/zotero/write 流程

优先级：
P2。

## 推荐修改顺序

### 第一阶段：先补漏洞和高收益接口

1. 实现 rejected keyword 负反馈闭环
2. 为 `process_inbox` 加入与 `add_paper` 共用的 PDF fallback
3. 保留正文里的 inline refs / citation tokens
4. 给 `query_vault` 加 compact 模式
5. 给 `query_vault` 增加 `limit` 与时间窗口参数

### 第二阶段：把 discovery 和 raw note 做到更稳

1. query expansion 与 bounded exploration loop
2. 双层 diversity 约束
3. topic-fit 语义扩展
4. hybrid impact
5. raw note 的 grouped DNL-v2 呈现层
6. gap heuristic 升级
7. reviewer / compiler few-shot examples

### 第三阶段：做真正的 Agent-friendly 交互升级

1. idea generator 的 conflict-aware card
2. daily digest 的 pattern/conflict 双区块
3. 高风险写操作 intent APIs
4. compile reduce-stage reconciliation
5. `paper-add` / `paper-ingest` 的协议复用

### 第四阶段：路线图级能力

1. semantic dedup suggestions
2. concept promotion candidates
3. evergreen overview refresh queue

## 最后判断

这份 review 不是“全部照单全收”，但整体质量很高，尤其在以下四点上判断非常准：

1. 当前 deterministic ranking 对语义扩展和负反馈闭环支持不足。
2. arXiv capture 在容错与引用保真上仍有关键缺口。
3. `query_vault` 的 Agent-facing 契约还不够节制。
4. prompt 体系目前的确偏 zero-shot，缺少质量基线。

最需要明确 push back 的三点是：

1. 不建议默认把 LLM 放到 discovery query 生成主路径里。
2. 不建议引入 hidden chain-of-thought / `<thought_process>`。
3. 不建议一上来做自动语义合并和自动 ontology 提权。

整体上，这份 review 值得作为后续改造路线图的主输入，但实施方式应该保持 Paper Distill 现在最宝贵的特征：可复现、低幻觉、可调试。
