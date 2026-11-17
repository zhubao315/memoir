# 目标架构（Phase 1+）

采用**模块化单体 + 独立后台 Worker**（不引入微服务/K8s/复杂事件总线）。

```
 Browser / PWA / 公开故事页(二维码)
   React + TS + Vite · 响应式 · 老年简洁模式
              │  HTTPS / Bearer JWT (access+refresh)
              ▼
 FastAPI API (backend/app/api/v1)
   认证 · 权限 · 限流 · API Versioning
              │
   ┌──────────┼───────────┬────────────┬───────────┐
   ▼          ▼           ▼            ▼           ▼
Identity   Memory      Story        Family      Publishing
Auth       Vault       Studio       Circle      Legacy Book
              │           │            │           │
              └───────────┼────────────┘           │
                          ▼                        ▼
              AI Engine (app/ai)            Legacy / Export
   Provider Adapters (OpenAI-compatible / Anthropic / Local / Mock)
   Interview · Speech · StoryWriter · MemoryGraph · Retrieval(RAG)
                          │
              ┌───────────┼──────────────┐
              ▼           ▼              ▼
      PostgreSQL     Object Storage    Redis
      + pgvector     (Local / S3)      (队列/缓存)
      (DATABASE_URL) (Storage Adapter)  (可选)
              ▲
              │ 后台任务
   Worker: ASR · AI Story · OCR · Embedding · Book Render · Notify
   (AIJob: pending/processing/completed/failed/cancelled, 幂等, 可重试)
```

## 代码结构

```
backend/app/
  core/        config(.env) · security(JWT/refresh/撤销) · deps · errors · ratelimit · audit
  db/          base · session · init
  models/      identity · family · memory · story · interview · media · ai · knowledge
               · collaboration · publishing · legacy · security · legacy_tables(兼容)
  schemas/     对应 Pydantic v2 模型
  repositories/ 数据访问封装
  services/    业务编排（auth/memory/story/media/family/book/legacy）
  storage/     base(接口) · local · s3
  ai/          providers(openai_compatible/anthropic_compatible/mock) · factory
               transcription · interview · story_writer · extraction · retrieval
               prompts/ (版本化 prompt 模板)
  tasks/       runner(内存/ARQ-ready) · jobs
  api/v1/      router + 各资源路由
```

## 数据归属与隔离

- 所有领域表含 `user_id`，可选 `family_id`；依赖注入强制过滤，杜绝 IDOR。
- 家庭资源级权限：角色 + 资源校验，不靠前端隐藏按钮。
- 媒体访问：存储适配器生成**短期签名 URL**，普通协作者不能删除原始录音。

## AI 事实保护

AI 仅改善表达，不补充未讲述的日期/人物/地点/事件/对话。不确定项标记 `needs_confirmation`。每次生成写 `ai_generation_logs`（model/provider/prompt_version/input_refs/output/status），支持重新生成、版本对比、恢复。原始录音/逐字稿独立且无覆盖接口。

## 部署

`docker-compose.yml`：api + worker + postgres(pgvector) + redis + minio + nginx。开发默认 SQLite + 本地存储 + Mock AI，零外部依赖即可运行与测试；生产通过 `.env` 切换。
