# 当前架构（升级前，Phase 0 快照）

> 目标架构见 `docs/architecture/TARGET_ARCHITECTURE.md`。

```
              Browser (http://192.168.1.22/memoir/)
              frontend/index.html  (inline CSS/JS, 原生 DOM)
                          │  fetch (Bearer JWT over HTTP 明文)
                          ▼
              Nginx  (80, server_name 192.168.1.22)
                ├─ /memoir/   → /fs/memoir/frontend/ (静态)
                ├─ /api/      → 127.0.0.1:8000
                └─ /docs      → 127.0.0.1:8000
                          │
                          ▼
              Uvicorn  → backend/main.py (单体, 563 行)
                          │
              ┌───────────┼────────────┐
              ▼           ▼            ▼
        SQLAlchemy   python-jose    /fs/memoir/uploads
        (SQLite)     (JWT, HS256)   (本地文件, 无鉴权)
        memoir.db    sub=username
```

## 特征

- **单体**：所有模型、schema、路由、认证、文件处理在一个 `main.py`（563 行）。
- **无分层**：没有 core / services / repositories / ai / storage 边界。
- **无异步任务**：所有操作同步；媒体上传是逐文件 `await file.read()` 全量进内存。
- **无 AI**：无任何模型调用、转录、故事生成。
- **无测试框架**：`test.sh` 是 curl 冒烟脚本，依赖已运行服务。
- **硬编码**：密钥、IP、路径、上传目录、API_BASE 全部写死。
- **数据**：SQLite 单文件被 git 跟踪；4 张表；3 用户 / 1 记忆 / 1 标签 / 0 媒体。

## 关键断点

前端调用 `GET /api/media/{id}/file` 查看图片/录音/视频，但后端无此端点 → **媒体查看功能实际不可用**。这是升级必须修复的第一个真实 bug。

## 升级原则（来自任务书）

1. 保留全部现有业务能力与 legacy REST API（向后兼容）。
2. 渐进式重构，不推倒重写；分阶段独立提交。
3. 原始数据不可被 AI 覆盖；所有记忆有明确归属；AI 结果可追溯。
4. 不伪造第三方服务已接通；缺 Key 时用 Provider Adapter + Mock + 配置说明。
