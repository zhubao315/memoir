# Memoir Next — 真实进度记录

更新日期：2026-11-17

> 原则：只记录真实完成的内容。「⚠️ 基础」表示提供了可用接口/配置/脚本，但完整生效依赖生产资源（PostgreSQL、对象存储、真实 AI Key、域名 HTTPS、备份存储），未伪造已接通。

## Phase 0 — 审计与工程准备 ✅ 完成

- 逐文件读取全部源码（后端 563 行、前端 1517 行、全部部署脚本、nginx、真实 SQLite 数据）。
- 只读查询真实数据库：users=3 / entries=1 / tags=1 / media=0，确认文件被 git 跟踪。
- 发现并定位关键 bug：前端调用 `GET /api/media/{id}/file` 但后端无此端点（媒体查看实际不可用）。
- 交付文档：`docs/audit/PROJECT_AUDIT.md`、`SECURITY_AUDIT.md`、`DATA_MODEL_AUDIT.md`、`TECH_DEBT.md`、`docs/architecture/CURRENT_ARCHITECTURE.md`、`TARGET_ARCHITECTURE.md`。

## Phase 1 — 基础架构升级 ✅ 完成

- 后端模块化为 `backend/app/`（core / db / models / schemas / services / storage / ai / tasks / api/v1）。
- 配置全部环境化（`core/config.py` + `.env.example`），启动时校验生产密钥强度；CORS 白名单。
- **保留 legacy API**：`backend/app/api/v1/legacy.py` 完整复刻 v0.1 全部端点与响应结构，`backend/main.py` 保留 `uvicorn main:app` 入口。
- 安全：JWT sub 改为用户 UUID（兼容旧 username token）、refresh token 轮换 + 撤销名单、登录限流、文件魔数校验 + 大小限制 + 随机文件名 + 路径穿越防护、审计日志。
- 存储抽象：`StorageBackend` + `LocalStorage`（HMAC 签名 URL）+ `S3Storage`（boto3 可选）。修复硬编码 `/fs/memoir/uploads`。
- **修复媒体 bug**：新增带所有权校验的 `GET /api/media/{id}/file` 与 v1 签名 URL 端点。
- Alembic 迁移：`0001_initial` 幂等创建表，不删除旧表。
- 非破坏性数据迁移：`scripts/migrate_legacy_data.py`（`--dry-run` / `--verify`，保留 UUID、时间、bcrypt 哈希、媒体相对路径）。
- Docker Compose（api + worker + postgres(pgvector) + redis + minio + nginx）、Dockerfile、nginx 安全头模板。
- 依赖清单 `backend/requirements.txt`。

## Phase 2/3 — Memory Vault + Story Studio 核心闭环 ✅ 完成（本迭代核心）

- Memory Vault：创建/列表/查询/软删除、异步实体抽取与 embedding 任务。
- 200 条中文问题库（20 分类，`app/ai/prompts/questions.py`），随应用启动幂等 seed。
- AI 人生访谈：多轮上下文 + 动态追问 + 事实抽取 + 暂停/继续/结束。
- 录音：MediaRecorder 前端 + `POST /v1/story/recordings` + 异步转录任务 + 逐字稿人工修正（原始录音无覆盖接口）。
- AI 故事生成：7 种叙事模式；原始/A I/人工版本分离（`story_versions`）；事实保护（日期不一致标记待确认）；每次生成写 `ai_generation_logs`（模型/Prompt 版本/输入引用）。
- AI Provider Adapter：OpenAI-compatible / Anthropic-compatible / Local / **Mock**（无 Key 时不联网、明确标注为离线 Mock，不伪造真实服务）。
- ASR Adapter：OpenAI-compatible whisper / Mock。
- RAG 私人记忆问答：用户隔离的检索 + 来源引用 + 无证据时明确回答“没有找到”。

## Phase 4–7 — 基础模块 ⚠️ 基础（可运行，非完整产品化）

- Family Circle：家庭空间、邀请 token、成员角色（owner/admin/storyteller/collaborator/viewer）、资源级权限校验（已测试 403 拒绝）。
- Legacy Book：书籍/章节 CRUD、PDF（reportlab，中文字体）/Markdown/JSON 导出、稳定不可预测二维码 token + 撤销 + 公开故事页权限校验。
- Digital Legacy：联系人、显式授权策略、撤销、人工审核触发（**不自动交付数据**）。
- Life Graph：实体抽取 + 关系表 + 人生阶段/里程碑模型；RAG 检索接口。
- 前端：React + TS + Vite SPA，7 个一级栏目、新设计 Token、响应式、老年简洁模式、真实 API 交互，已通过 `npm run build`。

## 测试（真实执行）

- `cd backend && pytest tests -q` → **11 passed**。
- 覆盖：认证/刷新/撤销、legacy API 兼容、媒体校验与签名 URL、200 问题库、访谈动态追问、故事多版本与恢复、RAG、家庭权限拒绝、PDF/二维码、数字遗产显式授权。
- Alembic + 数据迁移在真实 db 副本上验证：`users=3 / entries=1` 保留，1 条 entry 映射为 memory，原始数据无丢失。
- 端到端 HTTP 验证：注册 → 登录 → 创建记忆 → 生成故事 → 统计 → 200 问题库，全部 200。
- 前端 `npm run build` 成功（44 modules，gzip 63 KB JS）。

## 未完成 / 风险（诚实记录）

1. **真实 AI/ASR 未接通**：默认 Mock。需项目所有者提供 API Key 与兼容端点；已提供 Adapter 与配置，不伪造。
2. **PostgreSQL / S3 / Redis 生产部署**：`docker-compose.yml` 已提供，但未在真实生产环境验证；SQLite 到 PG 的正式数据迁移需 DBA 执行（当前默认仍是 SQLite）。
3. **EPUB / 打印级 PDF / 实体书模板**：未实现；已实现 PDF/Markdown/JSON。
4. **备份恢复演练**：脚本与文档待生产环境执行；未实际演练。
5. **旧前端 index.html**：新 SPA 在 `frontend/`，旧 `frontend/index.html` 保留作回退，生产需切换 Nginx 根目录到 `frontend/dist`。
6. **OTP/身份核验、争议处理流程**：数字遗产仅实现状态机与人工审核入口，完整流程需产品与法务定义。
7. **OpenTelemetry 链路追踪**：当前为结构化日志。

## 下阶段路线

1. 接入真实 AI/ASR Provider 并补齐事实保真度评测集（任务书要求：HTTP 200 不等于 AI 正确）。
2. 生产 PostgreSQL + pgvector + MinIO 落地与迁移演练。
3. EPUB 与打印级排版、二维码音频播放页完善。
4. 家庭协作通知、评论/投票 UI、图谱可视化。
5. 完整 E2E（Playwright）、备份恢复演练、正式发布。
