# Memoir 安全审计报告 (Phase 0)

审计日期：2026-11-17 · 依据：源码逐行审计（未连接生产环境）

## 漏洞清单

| ID | 级别 | 问题 | 位置 | 修复方案（Phase 1 状态） |
| --- | --- | --- | --- | --- |
| S-01 | P0 | JWT Secret 硬编码默认值 `memoir-secret-key-change-in-production` | main.py:24 | ✅ 迁移到 `SECRET_KEY` 环境变量，启动时强度校验（长度≥32 且非默认值），生产环境缺失即拒绝启动。 |
| S-02 | P0 | CORS `allow_origins=["*"]` + `allow_credentials=True`，允许任意站点携带凭证跨域 | main.py:250-256 | ✅ 改为 `CORS_ORIGINS` 白名单，默认本机；生产必须显式配置。 |
| S-03 | P0 | 上传目录硬编码 `/fs/memoir/uploads`，不可移植、部署迁移困难 | main.py:39 | ✅ 抽象 `StorageBackend`（`LOCAL` / `S3`），由 `STORAGE_*` 环境变量配置。 |
| S-04 | P0 | 无数据库迁移机制，`create_all` 无法安全演进结构 | main.py:105 | ✅ 引入 Alembic；legacy 数据非破坏性导入。 |
| S-05 | P0 | 媒体访问无授权：缺少 `/api/media/{id}/file` 端点，前端 404；且任何媒体下载都无归属校验 | 前端:1211/1366 | ✅ 新增带所有权校验的媒体文件端点，签名 URL 带过期时间（`MEDIA_URL_TTL`）。 |
| S-06 | P1 | JWT `sub` 使用 `username`（可用户自定义、可改），不是稳定 UUID | main.py:236,287 | ✅ `sub` 改为用户 UUID；兼容旧 token 的 username 回退（过渡期）。 |
| S-07 | P1 | 无 Refresh Token、无 Token 撤销/失效机制（7 天长期凭证无法吊销） | main.py:26,285 | ✅ 增加 refresh token + 轮换 + 撤销名单（服务端 denylist），`/api/v1/auth/logout` 撤销。 |
| S-08 | P1 | 无登录频率限制、无注册防滥用 | main.py:259-294 | ✅ 内存限流中间件（按 IP+用户名），可接入 Redis。 |
| S-09 | P1 | 文件上传无 MIME/文件头/大小/扩展名校验，可上传任意文件 | main.py:403-450 | ✅ 白名单 + 文件头魔数校验 + 大小上限 + 随机文件名 + 路径穿越防护。 |
| S-10 | P1 | 无 CSRF 防护、XSS 依赖前端 `escapeHtml`（CDN 无 CSP） | 全局 | ⚠️ 采用 Bearer Token（非 Cookie），天然规避 CSRF；前端保留转义；CSP/安全头在 Nginx 模板补充。 |
| S-11 | P1 | 无审计日志 | 全局 | ✅ 关键操作（登录/删除/分享/权限变更）写入 `audit_logs`。 |
| S-12 | P1 | 无资源级授权（IDOR 风险）：列表查询虽有 `user_id` 过滤，但新模块必须强制 | 全局 | ✅ 所有 v1 查询强制归属过滤 + 依赖注入 `current_user`。 |
| S-13 | P2 | SQLite 单库并发受限、无备份恢复演练 | 部署 | ⚠️ 支持 `DATABASE_URL` 切换 PostgreSQL；备份脚本 + 恢复演练文档。 |
| S-14 | P2 | AI 数据隐私：无 AI 处理授权与撤回、无最小必要数据策略 | 未实现 | ✅ AI Provider 层强制最小数据字段 + `ai_processing_consent` 用户开关；未配置 key 时使用 Mock，不外发数据。 |

## 数字遗产特别说明

任务书明确要求：不得因账户长期未登录就自动交付全部记忆。新 `legacy_policies` 模型要求：
- 显式授权（`granted` 标志 + 授权时间）
- 生效条件（手动触发或延迟天数）
- 身份核验字段（联系方式校验）
- 可撤销
- 争议状态机
- 仅分享明确指定的故事/记忆，而非整个账户

## 结论

Phase 1 修复全部 P0 与大部分 P1。P2 中 PostgreSQL 生产切换、备份恢复演练、CSP 属于基础设施，需在生产部署阶段结合真实环境完成，当前提供配置与脚本，不伪造「已接通」。
