# Memoir

**Your Life. Your Stories. Your Legacy.**

AI 原生个人记忆、人生故事、家庭记忆与数字传承平台。从一个人的记忆开始，构建一个家庭的数字记忆资产。

> 本次迭代：从 v0.1 MVP 系统性升级为产品级模块化架构（v1.0.0）。
> 详细进度见 [`docs/PROGRESS.md`](docs/PROGRESS.md)，真实完成情况与未完成项均记录于此。

---

## 六大产品中心

| 中心 | 说明 |
| --- | --- |
| **Life Studio** 人生工作台 | 登录后的默认首页：记忆/故事/媒体统计、每日记忆问题、最近记录、里程碑 |
| **Memory Vault** 个人记忆库 | 多模态记忆、时间线、实体与人物关联、语义检索；原始数据不可被 AI 覆盖 |
| **Story Studio** AI 故事工作室 | 200 条中文问题库、AI 动态访谈、语音录制与转录、7 种叙事模式、多版本与事实保护 |
| **Family Circle** 家庭记忆空间 | 家庭空间、邀请、角色权限（owner/admin/storyteller/collaborator/viewer）、协作 |
| **Legacy Book** 回忆录出版 | 书籍/章节、PDF/Markdown/JSON 导出、可撤销的故事二维码 |
| **Digital Legacy** 数字传承 | 传承联系人、显式授权策略、可撤销、人工审核；绝不自动交付数据 |

## 核心设计原则

1. **原始不可覆盖**：录音、逐字稿、AI 故事、人工修改分开保存，原始录音无覆盖接口。
2. **明确归属**：所有数据有 `user_id`，可选 `family_id`，服务端强制过滤（防 IDOR）。
3. **AI 可追溯**：每次生成记录模型、Prompt 版本、输入引用与时间；不确定信息标记「待确认」，不编造。
4. **向后兼容**：保留 v0.1 全部 REST API 与原数据库；新能力在 `/api/v1/*`。
5. **诚实集成**：无 API Key 时使用明确标注的离线 Mock，不伪造真实 AI 服务已接通。

## 技术栈

- 前端：React + TypeScript + Vite（新设计系统、响应式、老年简洁模式）
- 后端：FastAPI + Pydantic v2 + SQLAlchemy 2.x（模块化单体 + 独立 Worker）
- 数据：SQLite（开发）/ PostgreSQL + pgvector（生产），Alembic 迁移
- 存储：Local（HMAC 签名 URL）/ S3 兼容（MinIO）
- AI：Provider Adapter（OpenAI-compatible / Anthropic-compatible / Local / Mock）+ ASR Adapter
- 部署：Docker Compose + Nginx

## 快速开始

```bash
# 后端（默认 SQLite + 本地存储 + Mock AI，零外部依赖）
cd backend && pip install -r requirements.txt && uvicorn main:app --reload

# 前端
cd frontend && npm install && npm run dev
```

完整部署、迁移、API、使用文档见 [`docs/`](docs/)：

- [部署指南](docs/DEPLOYMENT.md)
- [API 文档](docs/API.md)
- [用户手册](docs/USER_MANUAL.md)
- [审计报告](docs/audit/PROJECT_AUDIT.md) · [安全审计](docs/audit/SECURITY_AUDIT.md) · [数据模型审计](docs/audit/DATA_MODEL_AUDIT.md)
- [目标架构](docs/architecture/TARGET_ARCHITECTURE.md) · [决策记录](docs/DECISIONS.md) · [变更记录](docs/CHANGELOG.md)

## 测试

```bash
cd backend && pytest tests -q     # 11 passed
cd frontend && npm run build      # 构建通过
```

## 版本

v1.0.0 · 2026-11-17
