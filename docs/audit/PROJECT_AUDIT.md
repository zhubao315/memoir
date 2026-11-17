# Memoir 项目审计报告 (Phase 0)

- 审计日期：2026-11-17
- 审计范围：`https://github.com/zhubao315/memoir` 仓库全量源码、配置、部署脚本、SQLite 实际数据
- 审计方式：逐文件读取源码 + 只读查询 SQLite 数据库。**未连接生产服务器**（无授权），因此不对生产环境状态做断言。
- 审计人：升级工程 Agent

---

## 1. 当前实际架构

| 层 | 现状 |
| --- | --- |
| 前端 | 单个 `frontend/index.html`（1517 行）：内联 CSS + 内联 JS，原生 DOM 操作，`fetch` 调用 API。无构建、无组件化、无路由、无测试。 |
| 后端 | 单个 `backend/main.py`（563 行）：FastAPI + Pydantic v1 风格 + SQLAlchemy，所有模型/路由/业务逻辑混在一起。 |
| 数据库 | SQLite 文件 `backend/memoir.db`（44 KB，且被 git 跟踪）。4 张表：`users`、`entries`、`tags`、`media`。 |
| 媒体存储 | 硬编码 `/fs/memoir/uploads`，无抽象、无授权访问、无签名 URL。 |
| 部署 | `deploy.sh` + `start.sh` + `nginx.conf`，硬编码 IP `192.168.1.22` 与路径 `/fs/memoir`、`/data/venv`。无 Docker。 |
| 测试 | `test.sh`：依赖运行中服务的 curl 冒烟脚本，不是自动化测试，无断言框架、无 CI。 |

实际数据（只读查询）：`users=3`、`entries=1`、`tags=1`、`media=0`。用户均为测试数据（`admin`、`test123`、`testuser_1769672094`）。**这些数据必须在升级中完整保留。**

## 2. 已实现功能（必须保留）

- 用户注册 `/api/auth/register`、登录 `/api/auth/login`、当前用户 `/api/auth/me`（JWT）
- 记忆 CRUD：`GET/POST /api/entries`、`GET/PUT/DELETE /api/entries/{id}`
- 媒体上传 `POST /api/entries/{id}/media`、列表 `GET /api/entries/{id}/media`、删除 `DELETE /api/media/{id}`
- 标签 `GET/POST /api/tags`、`DELETE /api/tags/{id}`
- 统计 `GET /api/stats`
- 时间线、心情、类型、位置、标签筛选（前端）
- 根路由 `/` 健康检查

## 3. 未实现 / 缺失功能

- **AI 全部能力**：无问题库、无访谈、无转录、无故事生成、无 RAG、无实体/关系抽取。README 里仍是「未来计划」。
- 家庭空间、角色权限、协作。
- 回忆录出版、二维码、PDF/EPUB 导出。
- 数字遗产与传承策略。
- 搜索（全文/语义）、人物关系图谱。
- 刷新 Token、Token 撤销、登录限流、CSRF、审计日志。
- 数据导出/删除请求、备份与恢复演练。
- 真正的自动化测试与 CI。

## 4. 关键 bug（非功能缺失，是现有功能坏掉）

| # | 问题 | 证据 |
| --- | --- | --- |
| B1 | **媒体查看端点不存在**：前端 `viewMedia()` / 详情页调用 `GET /api/media/{id}/file`，后端没有该路由，返回 404。图片/录音/视频实际无法查看播放。 | 前端第 1211、1366 行；后端路由清单无此端点 |
| B2 | `GET /api/entries` 的 `tag` 过滤用 `Entry.tags.contains(tag)`（SQLite JSON 字符串模糊匹配），结果不可靠。 | main.py:318 |
| B3 | `get_current_user` 的 `db` 参数类型标注为 `SessionLocal`（工厂）而非 `Session`，类型错误。 | main.py:228 |
| B4 | 删除记忆时物理文件删除路径 `UPLOAD_DIR / media.file_path`，但上传时 `file_path` 是相对路径，拼接正确但无任何访问授权。 | main.py:392 |
| B5 | 前端 `API_BASE` 硬编码为 `http://192.168.1.22:8000`，换环境即失效；且 HTTP 明文传输 JWT 与隐私记忆。 | index.html:890 |

## 5. 安全漏洞（详见 SECURITY_AUDIT.md）

- P0：JWT Secret 硬编码（`memoir-secret-key-change-in-production`）
- P0：CORS `allow_origins=["*"]` + `allow_credentials=True`（非法组合且危险）
- P0：上传目录硬编码 `/fs/memoir/uploads`
- P0：无数据库迁移机制（靠 `create_all`，结构变更会丢数据）
- P0：媒体访问无授权校验（IDOR 风险，且端点缺失）
- P1：JWT `sub=username` 而非稳定 UUID；无刷新/撤销
- P1：无登录限流、无注册防滥用、无审计日志
- P1：无文件类型/文件头/MIME 校验、无大小限制（后端层面）

## 6. 数据迁移风险

1. `backend/memoir.db` 被 git 跟踪——任何「重新初始化」都会覆盖历史数据。
2. `entries.tags` / `location` 是无约束 JSON，承载了核心关系，迁移需保留原值。
3. `media.file_path` 为相对路径，依赖硬编码上传根目录；迁移媒体文件时要保持相对结构。
4. 现有 `password` 为 bcrypt 哈希，必须原样保留，不能重置。
5. 必须保留原始 UUID 与 `created_at`/`updated_at`。

**迁移策略（已采用）**：不删旧表、不覆盖原库；新建 Alembic 迁移只「新增表 + 新增列」，并编写非破坏性导入脚本把 legacy `users/entries/tags/media` 复制到新领域模型。迁移前后做行数校验，失败可回滚。

## 7. 重构建议

1. 模块化单体：`backend/app/` 按 core/db/models/schemas/repositories/services/api/ai/storage/tasks 分层。
2. 配置全部环境化（pydantic-settings），启动时校验密钥强度。
3. 先保留 legacy API 原样可用，新能力走 `/api/v1/*`；旧路由做兼容转发。
4. 媒体访问统一走「存储适配器 + 有权限校验的签名 URL」。
5. AI 独立成 Provider Adapter 层，业务代码不直接依赖任何 SDK。
6. 原始数据（录音/逐字稿）与 AI 衍生内容分表存储、多版本可追溯。

## 8. 实施顺序（P0 → P1 → P2）

- **P0（Phase 1）**：配置环境化、JWT/CORS/上传目录修复、刷新+撤销 Token、存储适配器、Alembic + 数据保护迁移、修复媒体端点、Docker Compose、测试骨架。
- **P1（核心闭环）**：Story Studio（问题库 / 访谈 / 录音 / 转录 / 故事生成与版本）、Memory Vault 增强。
- **P1（基础模块）**：Family / Book / Legacy 的数据模型与基础 API。
- **P2**：RAG/图谱/前端精修/备份恢复/正式发布。

详细任务清单见 `TECH_DEBT.md`；进度见 `docs/PROGRESS.md`。
