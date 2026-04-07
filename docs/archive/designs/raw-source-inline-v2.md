# Raw Source Inline V2 设计与落地记录

- 文档类型：归档设计
- 状态：已实施
- 版本：v2
- 初始设计日期：2026-04-07
- 实施完成日期：2026-04-07
- 适用对象：维护者、追溯者

## 背景

`raw/source/*.md` 早期采用“正文 + 文末 snapshot”结构：

- `Appendix Snapshot`
- `Figure Snapshot`
- `Table Snapshot`
- `Equation Snapshot`

这种格式实现简单，但会把正文论证链与图表公式拆开，削弱 agent 的局部语义连续性，也让 display math 和表格的阅读体验变差。

## 设计目标

- 保留 frontmatter 与 `.assets.json` 结构化契约
- 将 figure / table / equation 尽量贴回正文附近
- 用稳定 display math block 呈现公式
- 保持 `raw/notes`、`compile`、`query` 基本兼容
- 只影响新生成的 `raw/source`，不迁移历史数据

## 最终落地结果

本次实现采用了 Hybrid Inline Source V2，行为如下：

- `raw/source` 改为按 DOM 顺序输出正文，并在原位置附近插入：
  - `**Figure N**` + caption + 可选 image URL
  - `**Table N**` + caption + Markdown table
  - `**Equation EN**` + display math
- 文末不再输出 `Figure/Table/Equation Snapshot`
- `Appendix Snapshot` 继续保留，用于 summary-only appendix capture
- 新增 `Captured Assets Index`，汇总 figure / table / equation 数量，并指向对应 `.assets.json`
- `.assets.json` 继续作为结构化证据主契约，保留 `sections`、`appendix_snapshot`、`figures`、`tables`、`equations`、`quality` 和 capture provenance

## 实现范围

本轮实际改动覆盖：

- `server/arxiv_capture.py`
  - 重写 `clean_ar5iv_html(...)` 的 markdown 组装逻辑
  - 改为单次 DOM 顺序内联渲染
  - 停止单独输出 `figcaption` 文本块
  - DNL evidence 标签改为使用真实 `Equation E1` / `Table 1` / appendix heading
- `server/arxiv_markdown.py`
  - 新增共享 math normalization
  - 统一 annotation / alttext / aria-label 的提取优先级
  - 将 block math 和 equation table 都规范化为 display math
- `server/vault_ops.py` 与 `server/server.py`
  - 在写盘阶段补入 `Captured Assets Index` 的 `Structured data: ...assets.json` 路径
- 文档与技能
  - 同步更新 `vault-layout`、知识模型、工作流、ingestion protocol、wiki-compile 说明

## 兼容性结论

- 新生成的 `raw/source` 使用 inline evidence v2
- 历史 `raw/source` 仍可保留旧 snapshot 形式
- 下游流程继续依赖 `.assets.json` 和 `CleanedArxivDocument` 的结构字段，而不是依赖旧 snapshot 文本

## 验证结果

实现完成后，运行了全量测试：

```bash
/Users/huang/Desktop/paper-distill-v2/.venv/bin/python -m unittest discover -s tests -v
```

结果：`128 tests`，`0 failures`。

## 备注

本文件保留这次设计与落地的关键决策。当前用户文档已直接反映最终行为，因此不再保留单独的 `docs/designs/` 当前设计目录版本。
