# 部署指南

## 本地开发（零外部依赖，Mock AI）

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
uvicorn main:app --reload --port 8000   # http://127.0.0.1:8000/docs

cd ../frontend
npm install && npm run dev              # http://127.0.0.1:5173（已代理 /api）
```

默认 `DATABASE_URL=sqlite:///./memoir.db`、本地文件存储、Mock AI/ASR。无需任何 Key。

## 数据迁移（从 v0.1 升级，必须先做）

```bash
# 1) 备份
cp backend/memoir.db backend/memoir.db.bak.$(date +%F)
cp -r backend/uploads backend/uploads.bak.$(date +%F) 2>/dev/null || true

# 2) Alembic 建表（不删旧表）
cd backend
DATABASE_URL=sqlite:///./memoir.db alembic upgrade head

# 3) 非破坏性导入旧数据（先 dry-run）
python3 ../scripts/migrate_legacy_data.py --legacy ./memoir.db --target sqlite:///./memoir.db --dry-run
python3 ../scripts/migrate_legacy_data.py --legacy ./memoir.db --target sqlite:///./memoir.db --verify

# 4) 校验行数、用户登录、记忆查询、媒体可访问后再切换流量
```

迁移失败时：恢复 `memoir.db.bak.*`，不要重跑覆盖脚本。详见 `docs/audit/DATA_MODEL_AUDIT.md`。

## 生产（Docker Compose）

```bash
cp .env.example .env
# 必须修改：SECRET_KEY（>=32 随机）、ENVIRONMENT=production、CORS_ORIGINS、
#           DATABASE_URL(PostgreSQL)、AI_*/ASR_*（真实 Key）、S3_*
docker compose up -d --build
# 迁移：
docker compose exec api alembic upgrade head
```

服务：api(8000) / worker / postgres(pgvector) / redis / minio / nginx(80)。
前端：`cd frontend && npm run build`，产物 `frontend/dist` 由 nginx 挂载。

生产切换要点：
- 必须用 PostgreSQL（修改 `DATABASE_URL`），并按 `DATA_MODEL_AUDIT.md` 做正式迁移与校验。
- HTTPS 终止在反向代理；`MediaRecorder` 需要安全上下文（HTTPS 或 localhost）。
- AI/ASR 未配置 Key 时保持 Mock，并在 UI 中明确标注；不得对外宣称已接通真实 AI。
- 备份：定期备份 PostgreSQL 与 MinIO，做恢复演练（待执行，见 PROGRESS.md）。

## 健康检查
`GET /health` → `{"status":"ok"}`。
