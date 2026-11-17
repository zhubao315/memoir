"""记忆与资源中心的多用户逻辑隔离测试（IDOR / 401 / 403 / 404）。

覆盖：
- 未认证访问一律 401；
- 记忆与媒体的读取/修改/删除/回收站操作必须带 user_id 过滤，跨用户返回 404；
- 上传时 memory_id 必须属于当前用户，否则 404；
- 移动媒体到他人记忆必须 404；
- 家庭空间越权写入返回 403；
- 合法归属的操作保持可用（防止过度收紧导致功能回归）。
"""

import pytest  # noqa: F401

from conftest import register_and_login

# 有效的 1x1 PNG，满足扩展名白名单 + magic bytes 校验。
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000a49444154789c6360000002000100ffff030000060005"
    "7c0f360000000049454e44ae426082"
)


@pytest.fixture(autouse=True)
def _clear_rate_limit():
    """清空内存限流桶，避免其它测试模块的注册次数影响本模块。"""
    from app.core.ratelimit import _hits

    _hits.clear()


@pytest.fixture(scope="module")
def users(client):
    da, ha = register_and_login(client, "mem_iso_alice")
    db_user, hb = register_and_login(client, "mem_iso_bob")
    return {"a": (da, ha), "b": (db_user, hb)}


def _memory(client, headers, title="测试记忆"):
    r = client.post("/api/v1/memories", headers=headers, json={"title": title, "raw_content": "原始内容"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _asset(client, headers, memory_id=None, name="pic.png"):
    data = {"memory_id": memory_id} if memory_id else None
    r = client.post(
        "/api/v1/media/upload",
        headers=headers,
        files={"file": (name, PNG, "image/png")},
        data=data,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ---------------------------------------------------------------- 认证
def test_unauthenticated_requests_are_401(client):
    assert client.get("/api/v1/memories").status_code == 401
    assert client.get("/api/v1/media").status_code == 401
    assert client.post("/api/v1/memories", json={"title": "x"}).status_code == 401
    assert client.get("/api/v1/memories/some-id/media").status_code == 401
    assert client.get("/api/v1/media/some-id/url").status_code == 401


# ---------------------------------------------------------------- 记忆
def test_cross_user_memory_read_and_media_list_are_404(client, users):
    ha = users["a"][1]
    hb = users["b"][1]
    mid = _memory(client, ha, "A 的私密记忆")

    assert client.get(f"/api/v1/memories/{mid}", headers=hb).status_code == 404
    # 列出附件前会先校验记忆归属，跨用户同样 404（而不是空列表）。
    assert client.get(f"/api/v1/memories/{mid}/media", headers=hb).status_code == 404
    # 本人可访问。
    assert client.get(f"/api/v1/memories/{mid}", headers=ha).status_code == 200


def test_cross_user_memory_update_is_404_and_does_not_mutate(client, users):
    ha = users["a"][1]
    hb = users["b"][1]
    mid = _memory(client, ha, "不可被改标题")

    r = client.put(f"/api/v1/memories/{mid}", headers=hb, json={"title": "被篡改"})
    assert r.status_code == 404
    assert client.get(f"/api/v1/memories/{mid}", headers=ha).json()["title"] == "不可被改标题"


def test_cross_user_memory_trash_operations_are_404(client, users):
    ha = users["a"][1]
    hb = users["b"][1]
    mid = _memory(client, ha, "A 的回收站记忆")

    assert client.delete(f"/api/v1/memories/{mid}", headers=hb).status_code == 404
    # 先由本人软删除，再验证跨用户不能恢复 / 彻底删除。
    assert client.delete(f"/api/v1/memories/{mid}", headers=ha).status_code == 200
    assert client.post(f"/api/v1/memories/{mid}/restore", headers=hb).status_code == 404
    assert client.delete(f"/api/v1/memories/{mid}/purge", headers=hb).status_code == 404
    # B 的回收站列表不含 A 的记忆。
    trashed = client.get("/api/v1/memories?show_trash=true", headers=hb).json()
    assert all(m["id"] != mid for m in trashed)


# ---------------------------------------------------------------- 媒体
def test_cross_user_media_read_url_update_delete_are_404(client, users):
    ha = users["a"][1]
    hb = users["b"][1]
    mid = _memory(client, ha, "带媒体的记忆")
    aid = _asset(client, ha, memory_id=mid)

    assert client.get(f"/api/v1/media/{aid}", headers=hb).status_code == 404
    assert client.get(f"/api/v1/media/{aid}/url", headers=hb).status_code == 404
    assert client.put(f"/api/v1/media/{aid}", headers=hb, json={"caption": " stolen"}).status_code == 404
    assert client.delete(f"/api/v1/media/{aid}", headers=hb).status_code == 404

    # 本人的签名 URL 与详情可用。
    assert client.get(f"/api/v1/media/{aid}/url", headers=ha).status_code == 200
    own = client.get(f"/api/v1/media/{aid}", headers=ha).json()
    assert own["id"] == aid


def test_upload_to_other_users_memory_is_404(client, users):
    ha = users["a"][1]
    hb = users["b"][1]
    mid = _memory(client, ha, "A 独占")

    r = client.post(
        "/api/v1/media/upload",
        headers=hb,
        files={"file": ("stolen.png", PNG, "image/png")},
        data={"memory_id": mid},
    )
    assert r.status_code == 404

    # A 没有媒体的记忆列表仍为空（B 没有成功写入）。
    assert client.get(f"/api/v1/memories/{mid}/media", headers=ha).json() == []


def test_move_media_to_other_users_memory_is_404(client, users):
    ha = users["a"][1]
    hb = users["b"][1]
    own = _memory(client, ha, "A 的源记忆")
    other = _memory(client, hb, "B 的目标记忆")
    aid = _asset(client, ha, memory_id=own)

    r = client.put(f"/api/v1/media/{aid}", headers=ha, json={"memory_id": other})
    assert r.status_code == 404

    # 资产仍属于原记忆。
    listed = client.get(f"/api/v1/memories/{own}/media", headers=ha).json()
    assert [x["id"] for x in listed] == [aid]


def test_caption_update_and_own_memory_move_work(client, users):
    ha = users["a"][1]
    src = _memory(client, ha, "源")
    dst = _memory(client, ha, "目标")
    aid = _asset(client, ha, memory_id=src)

    r = client.put(f"/api/v1/media/{aid}", headers=ha, json={"caption": "海边留影", "memory_id": dst})
    assert r.status_code == 200, r.text
    assert r.json()["caption"] == "海边留影"
    assert r.json()["memory_id"] == dst
    assert client.get(f"/api/v1/memories/{src}/media", headers=ha).json() == []
    assert [x["id"] for x in client.get(f"/api/v1/memories/{dst}/media", headers=ha).json()] == [aid]


# ---------------------------------------------------------------- 家庭越权
def test_family_id_requires_membership(client, users):
    ha = users["a"][1]
    hb = users["b"][1]
    created = client.post("/api/v1/family", headers=ha, json={"name": "A 的家庭"})
    assert created.status_code == 201, created.text
    family_id = created.json()["id"]

    # B 不是该家庭成员，不能把记忆/媒体写入 A 的家庭。
    r1 = client.post("/api/v1/memories", headers=hb, json={"title": "越权", "family_id": family_id})
    assert r1.status_code == 403
    r2 = client.post(
        "/api/v1/media/upload",
        headers=hb,
        files={"file": ("x.png", PNG, "image/png")},
        data={"family_id": family_id},
    )
    assert r2.status_code == 403

    # A 本人可以写入。
    r3 = client.post("/api/v1/memories", headers=ha, json={"title": "正常", "family_id": family_id})
    assert r3.status_code == 201
