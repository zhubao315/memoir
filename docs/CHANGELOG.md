# Changelog

## 1.0.0 — 2026-11-17 — "Memoir Next" 系统性升级

### 新增
- 六大产品中心骨架：Life Studio / Memory Vault / Story Studio / Family Circle / Legacy Book / Digital Legacy。
- 200 条中文人生问题库（20 分类），启动幂等 seed。
- AI 访谈（动态追问）、7 模式故事生成、多版本与恢复、事实保护与生成日志。
- AI Provider Adapter（OpenAI-compatible / Anthropic-compatible / Local / Mock）与 ASR Adapter。
- RAG 私人记忆问答（用户隔离 + 引用来源）。
- 家庭空间、角色权限、邀请 token。
- 回忆录书籍/章节、PDF/Markdown/JSON 导出、二维码与撤销。
- 数字遗产显式授权策略与人工审核流程。
- React + TypeScript + Vite SPA，新设计系统、响应式、老年简洁模式。
- Alembic 迁移 + 非破坏性 legacy 数据迁移脚本。
- Docker Compose 部署栈、`.env.example`、API 文档。
- pytest 测试集（11 项）。

### 变更（向后兼容）
- 后端从单文件 `main.py` 模块化到 `backend/app/`，但 `uvicorn main:app` 与全部旧 REST API 路径保持不变。
- JWT `sub` 由 username 改为 UUID（兼容旧 token）；新增 refresh token 与撤销。
- CORS 由 `*` 改为白名单；上传路径改为可配置存储适配器。

### 修复
- 媒体查看端点 `GET /api/media/{id}/file` 原本缺失（前端 404），现已实现并带所有权校验。
- 媒体上传新增类型/文件头/大小校验，杜绝任意文件上传。

### 数据
- 不删除、不覆盖原 SQLite 与任何旧表；新增领域表通过 Alembic 创建；legacy 数据通过脚本非破坏性复制。
