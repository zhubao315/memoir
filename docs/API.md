# API 文档

交互式 Swagger：`http://<host>/docs`。基础地址：本机 `/api`（legacy）+ `/api/v1`（新 API）。所有受保护端点使用 `Authorization: Bearer <access_token>`。

## 认证
| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/auth/register` | 注册 `{username,email,password}` |
| POST | `/api/auth/login` | 登录，返回 access_token + refresh_token + user（兼容旧响应） |
| GET | `/api/auth/me` | 当前用户 |
| POST | `/api/v1/auth/refresh` | refresh token 轮换 |
| POST | `/api/v1/auth/logout` | 撤销当前 access token 与全部 refresh token |

## Legacy（v0.1 兼容，全部保留）
`GET/POST /api/entries` · `GET/PUT/DELETE /api/entries/{id}` · `POST/GET /api/entries/{id}/media` · `DELETE /api/media/{id}` · `GET /api/media/{id}/file`（新增修复）· `GET/POST /api/tags` · `DELETE /api/tags/{id}` · `GET /api/stats`

## Memory Vault
`GET/POST /api/v1/memories` · `GET/PUT/DELETE /api/v1/memories/{id}`（DELETE 为软删除）

## Story Studio
- `GET /api/v1/story/prompts?category=&favorite=&limit=` · `GET /api/v1/story/prompts/categories` · `POST /api/v1/story/prompts/{id}/favorite`
- `POST/GET /api/v1/story/interviews` · `GET /api/v1/story/interviews/{id}` · `GET /api/v1/story/interviews/{id}/messages` · `POST /api/v1/story/interviews/{id}/answer` · `POST /api/v1/story/interviews/{id}/pause`
- `POST /api/v1/story/recordings` · `GET /api/v1/story/recordings/{id}` · `PUT /api/v1/story/transcripts/{id}`
- `POST /api/v1/story/stories/generate` `{mode,source_memory_id?,source_recording_id?,source_interview_id?}`
- `GET /api/v1/story/stories` · `GET /api/v1/story/stories/{id}` · `GET /api/v1/story/stories/{id}/versions` · `POST /api/v1/story/stories/{id}/versions` · `POST /api/v1/story/stories/{id}/versions/{version_id}/restore`

模式：`transcript | clean | first_person | third_person | literary | concise | documentary`

## Media
`POST /api/v1/media/upload` · `GET /api/v1/media/{id}` · `GET /api/v1/media/{id}/url` · `GET /api/v1/media/file?token=`（签名） · `DELETE /api/v1/media/{id}`

## Family
`POST/GET /api/v1/family` · `GET /api/v1/family/{id}` · `POST /api/v1/family/{id}/invite` · `POST /api/v1/family/invite/{token}/accept` · `GET /api/v1/family/{id}/members` · `PUT/DELETE /api/v1/family/{id}/members/{member_id}`

## Book
`POST/GET /api/v1/book` · `GET /api/v1/book/{id}` · `POST /api/v1/book/{id}/chapters` · `PUT/DELETE /api/v1/book/chapters/{id}` · `GET|POST /api/v1/book/{id}/export?format=pdf|markdown|json` · `POST /api/v1/book/{id}/qr` · `POST /api/v1/book/qr/{id}/revoke` · `GET /api/v1/book/public/story/{token}`

## Legacy / AI / Dashboard
`POST/GET /api/v1/legacy/contacts` · `POST/GET /api/v1/legacy/policies` · `POST /api/v1/legacy/policies/{id}/grant|revoke|trigger-review`
`POST /api/v1/ai/ask` `{question,family_id?,top_k?}` · `GET /api/v1/ai/jobs/{id}` · `POST /api/v1/ai/jobs/{id}/cancel`
`GET /api/v1/dashboard/summary` · `GET /api/v1/dashboard/export`

## 错误码
`400` 参数/业务校验 · `401` 凭证无效或已撤销 · `403` 权限不足 · `404` 资源不存在 · `413` 文件过大 · `429` 请求过于频繁 · `422` 参数校验失败。
