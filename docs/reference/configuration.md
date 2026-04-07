# 配置参考

- 文档类型：参考文档
- 状态：当前
- 版本：v1 初代发布
- 更新日期：2026-04-07
- 适用对象：用户、集成方、维护者

## 配置来源

Paper Distill 主要从两处读取配置：

1. `settings.json`
2. 环境变量

当两者同时存在时，部分关键项会优先使用环境变量，例如：

- `VAULT_PATH`
- `ZOTERO_MODE`
- `ZOTERO_COLLECTION_NAME`

## 最重要的配置项

### `paper_distill.vault_path`

作用：

- 指定 Obsidian Vault 根目录

### `paper_distill.research_profile`

作用：

- 定义系统的研究偏好与推荐语境

常用字段：

- `direction`
- `whitelist_authors`
- `seed_papers`
- `learned_preferences`

### `paper_distill.capture`

作用：

- 控制 arXiv / PDF 清洗策略

关键字段：

- `appendix_policy`
- `min_body_chars`
- `preserve_math`
- `preserve_figures`
- `preserve_tables`
- `remove_refs`
- `remove_inline_citations`
- `remove_internal_links`
- `write_structured_sidecar`

### `paper_distill.zotero`

作用：

- 控制 Zotero handoff 模式

关键字段：

- `mode`
- `enabled`
- `collection_name`
- `local_export_dir`

## 最小示例

```json
{
  "paper_distill": {
    "vault_path": "/absolute/path/to/vault",
    "research_profile": {
      "direction": "Embodied AI with vision-language-action policies for robot manipulation",
      "whitelist_authors": [],
      "seed_papers": [],
      "learned_preferences": {
        "accepted_keywords": [],
        "rejected_keywords": [],
        "preferred_venues": [],
        "feedback_count": 0
      }
    }
  }
}
```

## 环境变量

- `VAULT_PATH`
- `OPENALEX_EMAIL`
- `S2_API_KEY`
- `ZOTERO_MODE`
- `ZOTERO_COLLECTION_NAME`
- `ZOTERO_LOCAL_EXPORT_DIR`
- `ZOTERO_LIBRARY_ID`
- `ZOTERO_API_KEY`

## Zotero 模式选择建议

- `local_first`：适合本地导入和保守集成
- `web_api`：适合直接写 Zotero 云端条目
- `disabled`：适合完全不接 Zotero

## 相关文档

- [vault-layout.md](vault-layout.md)
- [commands.md](commands.md)
- [../integration/installation.md](../integration/installation.md)
