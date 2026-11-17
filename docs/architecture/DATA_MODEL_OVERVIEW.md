# Memoir 数据模型总览

本总览索引三个领域的详细设计（由并行迭代分别维护）：

- [记忆与资源中心](DATA_MODEL_MEMORY.md) — Memory / MediaAsset / Recording / Transcript / 向量与实体
- [故事工作室](DATA_MODEL_STORY.md) — Story / StoryVersion / Interview / Prompt / AIJob
- [家庭与数字传承](DATA_MODEL_FAMILY_LEGACY.md) — Family / Book / Legacy / 权限与二维码

## 全局原则

1. **所有核心实体使用 UUID 字符串主键**；保留原 v0.1 的 UUID 与时间不变。
2. **每个领域表都有 `user_id`**，所有查询/修改/删除必须带用户过滤（服务端强制，不依赖前端）。
3. **软删除**：`deleted_at` 为空表示有效；回收站 → 恢复 → 彻底清除三段式。
4. **原始内容与 AI 衍生内容分离**：录音、逐字稿、AI 故事、人工修改版本分别存储，不互相覆盖。
5. **AI 可追溯**：`ai_generation_logs` 记录 provider/model/prompt_version/input_refs/output/status；不确定项标记 `needs_confirmation`。
6. **家庭资源双重归属**：`user_id`（创建者）+ `family_id`（家庭空间）；访问需同时满足用户归属与家庭角色。
7. **公开访问最小化**：二维码使用不可预测 token，可撤销，公开故事页仍校验可见范围与 token 状态。

## 用户空间隔离矩阵

| 资源 | 个人空间 | 家庭空间 | 公开 |
| --- | --- | --- | --- |
| Memory | `user_id == 当前用户` | `family_id` 命中且角色允许 | 需显式 visibility=public |
| MediaAsset | 同上 | 家庭共享媒体需 family_id | 仅签名 URL |
| Story | 同上 | 家庭可见需 visibility=family | 二维码 + token 校验 |
| Recording | 同上，原始录音协作者不可删 | 家庭讲述者上传 | 不直接公开 |
| Book | 同上 | 家庭书需 family_id | 导出文件仅本人下载 |

## 迁移

v0.1 SQLite 的 `users/entries/tags/media` 原表永不删除；新领域表通过 Alembic `0001_initial` 幂等创建；`scripts/migrate_legacy_data.py` 非破坏性复制，保留 UUID、时间戳、bcrypt 哈希与媒体相对路径。详见 `docs/audit/DATA_MODEL_AUDIT.md`。
