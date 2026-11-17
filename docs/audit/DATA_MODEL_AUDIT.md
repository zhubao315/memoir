# Memoir 数据模型审计 (Phase 0)

审计日期：2026-11-17

## 1. 当前 schema（SQLite 实际读取）

```sql
users(id VARCHAR PK, username VARCHAR UQ, email VARCHAR UQ, hashed_password VARCHAR,
      created_at DATETIME, updated_at DATETIME)
entries(id VARCHAR PK, user_id VARCHAR FK, title VARCHAR NOT NULL, content TEXT,
        entry_date VARCHAR, entry_type VARCHAR, mood VARCHAR, location JSON, tags JSON,
        is_public BOOLEAN, created_at DATETIME, updated_at DATETIME)
tags(id VARCHAR PK, user_id VARCHAR FK, name VARCHAR, color VARCHAR, icon VARCHAR, created_at DATETIME)
media(id VARCHAR PK, entry_id VARCHAR FK, user_id VARCHAR FK, filename VARCHAR,
      file_type VARCHAR, file_path VARCHAR, file_size INTEGER, mime_type VARCHAR,
      caption TEXT, taken_at DATETIME, created_at DATETIME)
```

实际行数：`users=3 / entries=1 / tags=1 / media=0`。

## 2. 当前模型问题

| 问题 | 影响 |
| --- | --- |
| `entries.tags` 用 JSON 数组存标签名，无外键 | 标签重命名/删除需全表扫描改写；无法约束完整性（B2 bug 根源）。 |
| `entries.location` 无约束 JSON | 无法按地点查询/聚合。 |
| `media.file_path` 相对路径 + 硬编码根目录 | 迁移/换存储后端困难（S-03）。 |
| 无 `deleted_at` | 删除即物理删除，无回收站、不可恢复。 |
| 无 `updated_at`（media/tags 部分缺失） | 无法审计变更。 |
| 无版本概念 | AI 生成/人工修改会覆盖原始内容——任务书「坑 4」明确禁止。 |
| 无 Family / Story / Prompt / Recording / Transcript / Book / Legacy 等实体 | 无法支撑下一代产品（Remento 对标能力全部缺失）。 |
| `user_id` 虽为 UUID 字符串但无 FK 强制（SQLite 默认关闭） | 孤儿数据风险。 |
| 数据库文件被 git 跟踪 | 迁移事故高发点。 |

## 3. 目标领域模型（Phase 1+ 新增，不删旧表）

| 领域 | 新表 | 关键点 |
| --- | --- | --- |
| Identity | `sessions`, `refresh_tokens`, `token_denylist` | refresh 轮换、撤销、UUID sub |
| Family | `families`, `family_members`, `family_invitations` | 角色：owner/admin/storyteller/collaborator/viewer |
| Life | `life_stages`, `milestones`, `persons`, `person_relations` | 人物关系网络 |
| Memory | `memories`, `memory_tags`, `memory_locations`, `memory_relations` | 关联 legacy `entries` |
| Story | `stories`, `story_versions`, `story_chapters` | 原始/AI/人工版本分离 |
| Interview | `interviews`, `interview_messages`, `prompts`, `prompt_categories` | 多轮上下文 |
| Media | `recordings`, `transcripts`, `media_assets` | 原始录音永久保留 |
| AI | `ai_jobs`, `ai_providers`, `ai_generation_logs`, `prompt_templates` | 模型/prompt 版本可追溯 |
| Knowledge | `memory_entities`, `embeddings` | 图谱 + 向量检索（pgvector-ready） |
| Collaboration | `comments`, `reactions`, `votes`, `share_tokens` | 家庭协作 |
| Publishing | `books`, `book_chapters`, `book_qr_codes`, `book_export_jobs` | 二维码用不可预测 token |
| Legacy | `legacy_contacts`, `legacy_policies`, `legacy_events` | 显式授权 + 撤销 |
| Security | `audit_logs`, `data_export_jobs`, `deletion_requests` | 可审计、可导出 |

## 4. 三大设计原则（已落实到代码）

- **原则 A 原始不可覆盖**：录音 → `recordings`（原始文件）+ `transcripts`（逐字稿）独立；AI 故事写入 `story_versions`，`stories.current_version_id` 指向选定版本。原始内容无 update 接口。
- **原则 B 明确归属**：所有新表含 `user_id`（必填）+ 可选 `family_id`，查询强制过滤。
- **原则 C AI 可追溯**：`ai_generation_logs` 记录 model/provider/prompt_version/input_refs/output/created_at/status/error；事实保护：不确定信息标记 `needs_confirmation` 而非编造。

## 5. 迁移映射（legacy → 新模型，非破坏性复制）

- `users` → `users`（原表保留，不改动）+ 补充 `uuid`/`profile` 信息到新列
- `entries` → `memories`（`id` 保留原 UUID，`content` → `raw_content`，`tags`/`location` 原样迁移并建关系）
- `media` → `media_assets`（`file_path` 原样保留，由存储适配器解析）
- `tags` → `memory_tags`
- 迁移脚本：`scripts/migrate_legacy_data.py`，支持 `--dry-run`、`--verify`，前后行数比对，失败可回滚（删除本次新建的迁移数据，不动 legacy 表）。
