# Paper Distill - 系统整体审查与优化诊断书 (Review & Roadmap)

基于对系统代码流转的全盘审查，当前系统在执行效率和确定性上表现出色，但在“精细度”与“大模型交互友好度（Agent-Friendly）”方面，存在以下优化空间：

## 1. 发现环节 (Discovery Pipeline) 优化点

*   **1.1 检索词生成缺乏语义转换**
    *   **现状**：目前 `_search_query_for_topic` 仅将配置文件中的 keywords 用空格机械拼接作为 Query 发往各个论文 API。
    *   **优化建议**：在发起 `search_papers` 前，利大语言模型作为拦截器，将用户的自然语言“研究意图”发散并转化为该 API 专用的布尔逻辑搜索串（如将宽泛词转为 `(VLM OR Vision Language Models)`），以大幅提升高质量文献的召回率。
*   **1.2 多样性过滤过于依赖字符串哈希**
    *   **现状**：`_limit_by_diversity` 方法通过对论文标题进分词后拼接的哈希（`cluster_key`）来进行聚类去重。
    *   **优化建议**：单纯的标题分词无法过滤同作者在不同会议发表的“注水/微调”变种文章。建议引入“同一第一作者最多曝光 N 篇”的惩罚/截断机制，强制推介列表拓宽研究圈视野。

## 2. 打分算法 (Scoring Formula) 优化点

*   **2.1 “主题契合度”依赖字面量硬匹配，存在语义盲区**
    *   **现状**：`_score_topic_fit` 是基于 Keyword 与论文标题/摘要分词后的 Jaccard 交集重叠度来算分（权重高达 40%）。假如配置词为 `LLM`，而论文全篇只用全称 `Large Language Models`，其在该项会得 0 分。
    *   **优化建议**：引入近义词字典（Synonym Expansion），或考虑接入超轻量级本地词向量/句向量模型（如 `SentenceTransformers` 的极小版本），使用余弦相似度计算研究基准与摘要的语义相似度。
*   **2.2 “学术影响力”未考虑时间归一化 (年龄惩罚)**
    *   **现状**：Impact 算分公式只看绝对引用量，且在 200 引附近达到软封顶满分。
    *   **优化建议**：将绝对引用量改为**“引文速度”（Citation Velocity = 被引量 / 已发表月数）**。因为一篇上个月刚出且拿到 10 引用的顶会论文，在学术价值上往往远大于一篇 4 年前发表并攒满 200 引用的过气论文。
*   **2.3 负向反馈闭环缺失，排斥关键字形同虚设**
    *   **现状**：数据结构中预留了 `learned_preferences` -> `rejected_keywords`，但算分函数 `_score_author_preference_v2` 中只针对白名单作者（`whitelist_authors`）进行了加分，完全没有实现减分逻辑。
    *   **优化建议**：补充实现一票否决/降权机制。即在遍历论文文本时，若命中 `rejected_keywords` 列表，直接将该篇论文总分乘以惩罚系数（如 `0.1`），过滤掉带有明显非偏好特征（如医学应用、某些已被自己淘汰的旧方法）的无效推介。

## 3. 阅读笔记框架 (Note Generation Framework) 优化点

> **架构设计准则探讨：Raw 层的“客观骨架” vs Wiki 层的“主观蒸馏”**
> 
> 在讨论应修改 Python 脚本还是引入 LLM 时，明确了系统核心设计哲学：**入库爬取阶段 (`raw`) 应坚持纯 Python 零幻觉抽取，以最低成本保留论文的“无滤镜客观原句”；高昂的 LLM 阅读推理计算仅留给后期沉淀阶段 (`wiki-compile`)。** 因此，修改大纲结构是在“骨架容器”层面的重构，不应对其注入 LLM 调用。

*   **3.1 笔记结构应向“人类科研心智”重构 (CRGP -> DNL-v2)**
    *   **现状**：当前的 CRGP-DNL 是一个 7 项平铺的词袋分桶结构（Context, Related Work, Gap, Proposal, Key Results, Discussion, Next Steps），缺乏视觉层次，理据混合。
    *   **优化建议**：重构为嵌套与流程式的 **DNL 框架**（`Metadata` -> `Why-read` -> `CRGP核心逻辑链` -> `Figures & Experiments 实证库` -> `Insights & Next steps`）。这种结构完美剥离了“故事线”与“实验硬通货”，极大降低科研人员做 Skimming（扫读）和后续 LLM 提炼的概念阻力，且该调整**完全可通过重制纯 Python 模板实现，不需要 LLM 介入**。

## 4. 原文抓取与清洗 (arXiv Capture) 优化点

*   **4.1 批量入库缺失 PDF 容错降级机制机制**
    *   **现状**：核心环节 `/process-inbox` 抓取时重度且唯一依赖 `ar5iv.labs.arxiv.org` (HTML 渲染版)。如果某篇论文由于 LaTeX 错误导致 ar5iv 生成失败，处理流会直接报错并将论文标记为 `failed`，且**不会自动降级**去尝试下载对应的 PDF 并抽取文本。
    *   **优化建议**：在 `process_inbox` 中缝合 `fetch_pdf_text` 已有的 PyMuPDF 降级逻辑。当 `capture_arxiv_source` 遭遇异常捕获时，自动作为 Fallback 进行基于 PDF 的后备文本抓取。
*   **4.2 全量清洗导致“引文断语”，彻底破坏 Agent 知识回溯能力**
    *   **现状**：清洗代码粗暴地删除了所有的行内引用（`.ltx_ref`）。原文的语境（如 *"Based on Transformer [12]"*）会被洗成残缺的 *"Based on Transformer "*。
    *   **核心危害**：一旦失去完整的引标 Token 结构，后续在 `/query` 发动大模型检索（RAG）时，不仅句法崩盘，Agent 会由于丢失溯源标记而产生严重幻觉。
    *   **优化建议**：处理引注标签时，坚决弃用 `decompose()`，改为保留文字（`.unwrap()`）或替换为显式的特定占位符。
*   **4.3 “图表/公式”漂移，引文锚点遗失导致 Agent 产生图文脱节幻觉**
    *   **现状**：系统极其聪明地抽走了所有图表到底部，但连带把正文中指向它的 *"See Figure 2"* 这句话也干掉了。
    *   **核心危害**：当 Agent 试图结合图片解释正文某段硬核原理时，找不到正文任何链接底部的线索，产生上下文断层的看图幻觉。
    *   **优化建议**：保留原文由于图表抽离留下的缺口处的指示性 Markdown Anchor。
*   **4.4 大纲痛点 (Gap) 特征词提取策略过于单薄极易误判**
    *   **现状**：通过简单的句子关键词穷举 (`However, challenge, limited`) 来判断痛点。比如只是说了 *"we evaluated on limited dataset"* 就被误认为是 Gap。
    *   **优化建议**：引入基于纯 Python NLP 框架 `spaCy` 的 Dependency Parsing 依赖依存树分析，保证转折词作为句子主引导且具有负极性时才认定为立意突破口。

## 5. 本地数据检索与 Agent 交互 (Vault Query) 优化点

> **核心矛盾：丰富的 Metadata 索引与 LLM 脆弱的上下文容量之间的碰撞。**

*   **5.1 Index 污染导致 Token 暴涨与注意力偏移**
    *   **现状**：`query_vault` 工具在读取 YAML 时，全盘吐出了 `abstract`, `summary`, `why_recommended` 等千字长文本（且针对搜索列表每一条都吐出）。
    *   **优化建议**：在返回前端前应用 **"Field Stripping (瘦身下发)"**。即默认从字典中剔除长文本字段，仅下发寻址索引。迫使 Agent 获得粗筛列表后，再调用精确阅读工具，节约大量 Token 且消除检索期的注意力涣散。
*   **5.2 信息损耗补偿：极短摘要字段 (TLDR-Mini)**
    *   **现状**：如果剥夺了摘要，Agent 面对一个莫名其妙的论文 Title 可能会失去基本的语境嗅觉。
    *   **优化建议**：写入新字段 `tldr_mini`（严格限制在 15 个单词/1 句话以内，由入库时截断生成）。在下发检索树时保留此字段。
*   **5.3 状态机定义缺失导致逻辑混乱**
    *   **现状**：库里的 `status` 存在多种枚举（deferred, failed, approved等），但检索工具并没有通过 Prompt 教导 Agent 这些机器状态代表什么人类含义。
    *   **优化建议**：在系统级 Prompt 或工具 Docstring 中写入“枚举指引表”，锁死大模型瞎猜的余地。
*   **5.4 预防资料滚雪球：引入“时间窗口滤网”**
    *   **现状**：当前检索扫库规模太大，千篇论文时会压垮 AI。
    *   **优化建议**：在检索入参中增加 `modified_after` 或 `limit` 的强制时间窗切断器选项，提升检索的“近因效应”（Recency bias）和处理速度。

## 6. 知识库重构与系统自愈 (Semantic Vault Maintenance) 优化点

> **核心痛点：当前的 `lint_vault` 技能是一个“语法检查器”，只能修复死链或属性缺失等硬伤；但随着时间推移，不断涌入的新概念会导致系统产生大量的“语义知识熵”（比如概念同义词碎片化、旧笔记内容变成陈旧记录）。**

*   **6.1 由“被动修复”升级为“后台主动巡查合并” (Semantic Deduplication)**
    *   **现状**：目前的 `wiki-lint` 技能依赖人类手动同意修复（如处理 orphans 孤儿笔记），且无法察觉字面不一样但意思一样的概念碎片（如 `LLM` 和 `Large Language Models`）。
    *   **优化建议**：建立夜间巡查的后台 Agent。利用词向量定时计算概念笔记相似度，遇到高重合项主动发起合并审查，同意后由系统全局替换所有的 markdown 引用链接。
*   **6.2 概念的自动提权与降维 (Ontology Promotion)**
    *   **现状**：概念层级固化。一个标签不管被引用了 1 次还是一年内被引用了 50 次，在文件系统和关联推荐时的权重是一样的。
    *   **优化建议**：引入触发器机制。当一个底层 Concept 被超过 N 篇重要文献密集引用，自动唤醒智能体将其提权为主拓扑节点 (Topic)，并自动为其撰写并维护一篇全局向的 Landscape Overview。
*   **6.3 告别信息化石：引诱式的“常青树”笔记刷新 (Evergreen Synthesis)**
    *   **现状**：当新论文进入系统，系统（在 `/compile` 阶段）只是机械地把新论文追加到已有 Concept/Topic 的“Representative Papers”列表中，或者直接全盘重写旧的 Overview，导致新旧知识缺乏有机融合，要么知识僵化，要么丢失历史脉络。
    *   **优化建议**：引入系统级的“知识动态保鲜（Time-sensitivity）”调度机制。具体应设计三类更新触发器：
        1. **体量阈值触发**：当某个 Topic 新关联了超过 N 篇文献（或体量增幅超 30%）时触发。
        2. **时间衰减触发**：距离上次梳理该 Overview 已达半年，且期间至少有 1-2 篇核心顶会文献入库时触发。
        3. **范式转移触发**：若新入库文献被大模型研判为“推翻或大幅扩展了”某 Topic 的历史共识，强制触发立即重写。
    *   **安全重写策略（Patching vs Overwrite）**：触发更新后，调度专职 Compiler Agent，传入 [旧版 Overview + 若干新论文摘要]。要求以“打补丁（Patching）”或独立开辟 `## 最新演进 (Recent Breakthroughs)` 章节的形式进行融合重写，而非暴力的全文替换，从而保留完整的技术演进时间线。

## 7. 跨文档宏观涌现机制 (Macro-Emergence) 优化点

> **核心挑战：多篇打碎后的信息拼装，极易因为失去原始语境而引发大模型的“缝合怪幻觉（Stitching Hallucination）”。在 Idea 生成和 Daily Digest 层，亟需从“静态模板罗列”走向“动态冲突博弈”。**

*   **7.1 Idea Generation：引入“边界条件约束校验”阻断缝合幻觉**
    *   **现状**：目前的 `idea-generator` 直接从知识图中取 Gap，让 LLM 发散 2-3 篇文献融合成新的研究思路（A+B）。但 LLM 在融合时会陷入“名词拼贴”，忽视不同学科/方法之间的底层数学假设或物理限制，产出缺乏可落地性的“水文大纲”。
    *   **优化建议（具体执行方案）**：在生成 Idea Card 时，强制在 Prompt 生成管道中加入一重**“反向论证 (Devil's Advocate)”**环节：
        1. **抽取假设 (Assumption Extraction)**：要求 LLM 首先输出 Method A 及其原发领域的基础物理/数学限制假设（如：方法 A 强依赖“全局连续可微”，而目标环境 B 是“离散文本空间”）。
        2. **暴露冲突 (Conflict Highlight)**：在卡片大纲中增加不可缩减的段落 `[Assumption Conflict]`，系统先“唱反调”指出强行结合的硬伤。
        3. **机理同构过滤 (Isomorphic Filtering)**：只有当 LLM 能够解释出“如何通过一个桥接层或变形”抹平这一根本冲突时，才允许将该创新评定为高 Priority，否则自动将其标记为“不可行的高危缝合怪”。

*   **7.2 Daily Digest：由“高级 RSS 罗列器”升级为“知识冲突雷达”**
    *   **现状**：`daily-digest` 使用传统的 Jinja 模板（统计候选数量、分段罗列大仓文献等）。这种基于配置文件的死板分类往往缺乏横向贯通的洞察，并未发挥系统的“涌现”能力。
    *   **优化建议（具体执行方案）**：打破纯信息流模板，由 LLM 提供**“动态聚类 (Trend Clustering)”**和**“旧知挑战预警”**：
        1. **抛弃刻板分类，生成“涌现趋势叙事”**：在生成最终 Markdown 前，注入一个轻量级 LLM Digest 预处理。不要枯燥地报送“CV 论文 3 篇，NLP 论文 2 篇”，而是提炼共性洞见——*“系统注意到，今日虽然有 5 篇跨领域的不同论文，但其中 3 篇在底层方法论上都在探索用『扩散模型解决时间序列对齐』问题，这可能是一个爆发中的交叉趋势。”*
        2. **新增“范式破坏 (Paradigm Shifts)”高优先级预警模块**：触发 `daily-digest` 时引入轻量级 RAG 对撞。如果当日一篇重磅论文的 Key Result 被研判为**颠覆了**本地 Vault 中某篇核心综述/笔记里的“陈旧常识”，Digest 应在顶部高亮生成防脱节警告：*“⚠ 认知挑战预警：【论文 A】最新的消融实验结果，反驳了您的旧笔记【Concept B】中关于‘提升层数必定获益’的观点，请优先阅读并考虑刷新您的本地知识树。”*

## 8. 系统底座与协议层架构 (MCP Server & Protocol Architecture) 优化点

> **核心矛盾：当前系统提供给 Agent 的 MCP (Model Context Protocol) 接口缺乏针对写操作的安全强沙盒，若直接开放通用文件写权限，极易导致 Agent 产生幻觉从而篡改底层系统配置或损坏库文件。**

*   **8.1 收缩并垂直化所有的“写库”接口 (Thickening the Sandbox)**
    *   **现状**：目前 `server/server.py` 虽然暴露了 `add_paper` 和 `query_vault` 等宏观控制 Tool，但针对核心业务节点（比如 Agent 想要重写学习到的 `settings.json` 偏好，或者把编译好的笔记写入本地 `.md` 文件）**缺失专用的写入 API**。为了让 Compiler 等系统运转，系统目前面临不得不向大模型开放底层文件通配写能力（如 `write_file`）的窘境。一旦开放，大模型即获得最高权限操作文件，随时可能因为输出截断或 JSON 格式错误，把用户的部分系统级配置（如 Zotero API Key）洗白。
    *   **优化建议（物理操作与意图解耦）**：全面掐断大模型通过基础层接触文件系统和手动组装 JSON 解析的可能。对于任何写操作，必须在 Python 的 MCP 侧暴露**极其细粒度的业务接口（Intent APIs）**：
        1. **动态偏好更新专用接口**：设计 `update_learned_preferences(accepted_keywords: list, rejected_keywords: list)` 等专用 Tool。由 Python 内核确保安全加载 `settings.json` 并仅原子化地将局部字段 append 进去，利用强 Schema 绝对隔离大模型对系统路径字典本身的不可控篡改。
        2. **Wiki 文章上链专用接口**：设计 `compile_paper_to_wiki(citekey: str, wiki_content: str, extracted_concepts: list)` Tool。由底层负责自动校验文件路径、防范目录遍历攻击（Path Traversal）、强约束并注入正确的 YAML Frontmatter、判断重名冲突后再安全写盘。

## 9. 智能体预设人格与认知引擎 (Agent Prompting Engine) 优化点

> **核心挑战：底层思维链路重度同质化。Agent 目前仅仅是依靠其出厂零样本指令去执行任务，极度缺乏“科研学者”专有推演逻辑的标准答案模板（Few-shot）。这直接导致由于系统对它要求宽泛，它的输出上限也就只停留在“敷衍的段落缝合”。**

*   **9.1 强制注入内嵌式“博士级反思链” (Internal Monologue / Chain-of-Thought)**
    *   **现状**：当下的 `searcher.md`、`reviewer.md`、`compiler.md` 往往是一层直接结构式的骨架动作说明，强行要求生成 “PhD-level understanding” 却不给出评估刻度标准。在这种没有任何推演过度空间的情况下，LLMs 往往会跳过批判性分析过程，直接提取原论文的 Abstract 或者 Conclusions 的原句子缝合交差。
    *   **优化建议（认知框架升级）**：在预设人设层，强行修改输出要求，注入类似于特定 XML Tags `<thought_process>` 包裹的强制化内部推演约束：
        *   **对于 Reviewer （内部槽点引擎）**：要求它在确定打分为 `INGEST / SKIP` 之前，必须先在 `<thought_process>` 中扮演该研究领域内毒舌且严苛的审稿人，列出 “该论文对痛点是否有强针对性改变 / 评估所用的 Baseline 是否具有误导性” 等犀利思考。通过内部推演拉高最终决策的严谨度。
        *   **对于 Compiler （概念对撞推演）**：要求在总结时，绝不能用口水话进行大段翻译。必须在内部思考要求它“尝试用图谱内已存在知识点的术语去重构 / 联系新看到的科研概念”（即强制唤起关联记忆法）。
*   **9.2 大幅填充“提纲挈领”级的真实 Golden Few-Shot Examples**
    *   **现状**：代码库现行所有的 Agent System Prompt 都是彻头彻尾的 Zero-shot（零演示范例）。它们根本不知道标准的“满分”表现长啥样（比如：什么是好的 Novelty 评价指标，高密度的 `[[backlinks]]` 结构在段落中该如何自然布局）。
    *   **优化建议**：务必在所有涉及高阶文字与概念连结产出的核心 Agent Prompt 末尾，人为编写并硬编码至少涵盖 2 个学科方向（如一份顶级计算机视觉提炼片段，一份顶级强化学习提炼片段）的**最佳实践范例 (Golden Examples)**。通过直观演示原论文是如何经过 `<thought_process>` 大浪淘沙后变成了凝练的 Next Step 指南，在极坐标上为大模型钉死可模仿的高强度基准线。

## 10. paper-discover: 仍停留在“单次直球检索”（缺少探索循环 Exploration Loop）
一个高级的 Discover Agent 应该是带有循环控制的。它发散出检索词后去抓取，拿到前 10 篇的 Abstract 后，系统应该自动阅读并进行自反馈评判（Self-Critique）：“这 10 篇怎么全都是医学应用的？我要自己修改搜索词加上 -medical 再搜索一次”。你需要给它赋予多轮自主尝试与容错评估的能力，而不仅仅是把词变复杂就抛给 API。

## 11. 并发编译 (wiki-compile / process-inbox) 的“聚合冲突”缺失
系统提到了通过多 Sub-agents 分发来加快处理多篇论文，并且在 6.1 中打算利用“晚间排雷”来解决知识重叠。
未解决的潜力：这属于“先污染，后治理”。在 Map-Reduce 的架构里，当 3 个 Subagent 各自提取了一篇同主题的论文后，它们在归笼汇聚回主线时（Reduce 阶段），必须立刻设置一道知识协商 (Knowledge Reconciliation) 的关卡，强制对比它们刚生成的几个新 Concepts 是否可以即时合并，防止短时间内知识库出现大量毛刺。

## 12.  paper-ingest 与 paper-add 的结构性冗余未被提及
Review 深度讨论了抓取和入库的细节，但没有审视目前存在大量高度相似技能导致的菜单臃肿。将它们在顶层抽象合并为一个动态判断上下文的分支技能 (如 Deep_Ingest_Protocol) 将极大降低大模型路由分配时出错的概率。