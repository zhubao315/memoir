"""跨用户越权 / 逻辑隔离回归测试（家庭空间 + 回忆录 + 数字传承）。

所有用例都从「另一个登录用户」的视角发起请求，验证服务端资源级鉴权：
前端隐藏按钮不算鉴权；越权必须返回 403/404。
"""

from conftest import register_and_login

from app.db.session import SessionLocal
from app.models.story import Story, StoryVersion


def _user_id(data):
    return data["user"]["id"]


def _make_story(db, user_id, visibility, title="秘密故事"):
    story = Story(user_id=user_id, title=title, visibility=visibility, status="published")
    db.add(story)
    db.flush()
    version = StoryVersion(
        story_id=story.id,
        version_no=1,
        content="这是仅本人可见的正文内容",
        is_ai=False,
    )
    db.add(version)
    db.flush()
    story.current_version_id = version.id
    db.commit()
    return story.id


# ---------------------------------------------------------------------------
# 家庭空间
# ---------------------------------------------------------------------------


def test_family_cross_user_and_member_removal(client):
    da, ha = register_and_login(client, "iso_owner")
    db_user, hb = register_and_login(client, "iso_outsider")

    fid = client.post("/api/v1/family", headers=ha, json={"name": "王家"}).json()["id"]

    # 非成员：不能查看家庭、成员列表、邀请，也不能改角色。
    assert client.get(f"/api/v1/family/{fid}", headers=hb).status_code == 403
    assert client.get(f"/api/v1/family/{fid}/members", headers=hb).status_code == 403
    assert client.post(f"/api/v1/family/{fid}/invite", headers=hb, json={"email": "x@y.com"}).status_code == 403

    # 邀请并接受后成为 viewer。
    inv = client.post(
        f"/api/v1/family/{fid}/invite",
        headers=ha,
        json={"email": "b@example.com", "role": "viewer"},
    ).json()
    assert client.post(f"/api/v1/family/invite/{inv['token']}/accept", headers=hb).status_code == 200
    members = client.get(f"/api/v1/family/{fid}/members", headers=ha).json()
    assert client.get(f"/api/v1/family/{fid}", headers=hb).status_code == 200

    # viewer 不能邀请、改角色或移除成员。
    viewer = next(m for m in members if m["user_id"] == _user_id(db_user))
    assert client.post(f"/api/v1/family/{fid}/invite", headers=hb, json={"email": "z@y.com"}).status_code == 403
    assert client.put(
        f"/api/v1/family/{fid}/members/{viewer['id']}", headers=hb, json={"role": "admin"}
    ).status_code == 403
    assert client.delete(f"/api/v1/family/{fid}/members/{viewer['id']}", headers=hb).status_code == 403

    # owner 移除后，该用户立即失去访问权。
    assert client.delete(f"/api/v1/family/{fid}/members/{viewer['id']}", headers=ha).status_code == 200
    assert client.get(f"/api/v1/family/{fid}", headers=hb).status_code == 403


def test_family_invitation_revoke_and_multi_family(client):
    da, ha = register_and_login(client, "iso_inv_owner")
    db_data, hb = register_and_login(client, "iso_invitee")

    fam_a = client.post("/api/v1/family", headers=ha, json={"name": "A 家"}).json()["id"]
    fam_b = client.post("/api/v1/family", headers=ha, json={"name": "B 家"}).json()["id"]

    # B 家的邀请：只能由 B 家的 owner 列出；A 家的 owner 看到空列表。
    inv = client.post(
        f"/api/v1/family/{fam_b}/invite",
        headers=ha,
        json={"email": "inv@example.com", "role": "viewer"},
    ).json()
    assert any(x["id"] == inv["id"] for x in client.get(f"/api/v1/family/{fam_b}/invitations", headers=ha).json())
    assert all(x["id"] != inv["id"] for x in client.get(f"/api/v1/family/{fam_a}/invitations", headers=ha).json())

    # token 属于 B 家，接受后只加入 B 家，不能访问 A 家。
    assert client.post(f"/api/v1/family/invite/{inv['token']}/accept", headers=hb).status_code == 200
    assert client.get(f"/api/v1/family/{fam_b}", headers=hb).status_code == 200
    assert client.get(f"/api/v1/family/{fam_a}", headers=hb).status_code == 403

    # 撤销邀请后 token 不可再被第三方使用。
    inv2 = client.post(
        f"/api/v1/family/{fam_a}/invite",
        headers=ha,
        json={"email": "rev@example.com", "role": "viewer"},
    ).json()
    dc, hc = register_and_login(client, "iso_revoked")
    assert client.post(f"/api/v1/family/{fam_a}/invitations/{inv2['id']}/revoke", headers=ha).status_code == 200
    assert client.post(f"/api/v1/family/invite/{inv2['token']}/accept", headers=hc).status_code == 400


# ---------------------------------------------------------------------------
# 回忆录（Book）
# ---------------------------------------------------------------------------


def test_book_cross_user_cannot_modify_or_export(client):
    _, ha = register_and_login(client, "iso_book_owner")
    _, hb = register_and_login(client, "iso_book_thief")

    bid = client.post("/api/v1/book", headers=ha, json={"title": "我的回忆录"}).json()["id"]
    ch = client.post(
        f"/api/v1/book/{bid}/chapters",
        headers=ha,
        json={"title": "第一章", "order_index": 0},
    ).json()

    # 他人：不能读详情、改章节、删章节、导出、列二维码、建二维码、撤销二维码。
    assert client.get(f"/api/v1/book/{bid}", headers=hb).status_code == 404
    assert client.put(
        f"/api/v1/book/chapters/{ch['id']}", headers=hb, json={"order_index": 99}
    ).status_code == 404
    assert client.delete(f"/api/v1/book/chapters/{ch['id']}", headers=hb).status_code == 404
    assert client.get(f"/api/v1/book/{bid}/export?format=markdown", headers=hb).status_code == 404
    assert client.get(f"/api/v1/book/{bid}/qr", headers=hb).status_code == 404
    assert client.post(f"/api/v1/book/{bid}/qr", headers=hb).status_code == 404

    qr = client.post(f"/api/v1/book/{bid}/qr", headers=ha).json()
    assert client.post(f"/api/v1/book/qr/{qr['id']}/revoke", headers=hb).status_code == 404

    # 合法所有者仍可操作（向后兼容）。
    assert client.put(
        f"/api/v1/book/chapters/{ch['id']}", headers=ha, json={"order_index": 5}
    ).status_code == 200
    assert client.get(f"/api/v1/book/{bid}/qr", headers=ha).json()[0]["id"] == qr["id"]


def test_book_chapter_partial_update_preserves_fields(client):
    _, ha = register_and_login(client, "iso_book_order")
    bid = client.post("/api/v1/book", headers=ha, json={"title": "排序测试"}).json()["id"]
    ch = client.post(
        f"/api/v1/book/{bid}/chapters",
        headers=ha,
        json={"title": "原始标题", "content": "原始正文", "order_index": 0},
    ).json()

    # 上移/下移只传 order_index，不应清空 title/content。
    r = client.put(
        f"/api/v1/book/chapters/{ch['id']}", headers=ha, json={"order_index": 2}
    )
    assert r.status_code == 200
    assert r.json()["order_index"] == 2
    assert r.json()["title"] == "原始标题"
    assert r.json()["content"] == "原始正文"


# ---------------------------------------------------------------------------
# 公开二维码故事页
# ---------------------------------------------------------------------------


def test_public_qr_visibility_and_revocation(client):
    da, ha = register_and_login(client, "iso_story_owner")
    _, hb = register_and_login(client, "iso_qr_viewer")
    uid = _user_id(da)

    db = SessionLocal()
    try:
        private_id = _make_story(db, uid, "private", "私人故事")
        public_id = _make_story(db, uid, "public", "公开故事")
        family_id = _make_story(db, uid, "family", "家庭故事")
    finally:
        db.close()

    bid = client.post("/api/v1/book", headers=ha, json={"title": "二维码书"}).json()["id"]

    # 私有故事不能生成公开二维码。
    assert client.post(f"/api/v1/book/{bid}/qr?story_id={private_id}", headers=ha).status_code == 400

    # 公开故事：token 可匿名访问，不暴露任何存储路径字段。
    pub_qr = client.post(f"/api/v1/book/{bid}/qr?story_id={public_id}", headers=ha).json()
    resp = client.get(f"/api/v1/book/public/story/{pub_qr['token']}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "公开故事"
    assert "storage" not in resp.json() and "file_path" not in resp.json()

    # 撤销后立即失效。
    assert client.post(f"/api/v1/book/qr/{pub_qr['id']}/revoke", headers=ha).status_code == 200
    assert client.get(f"/api/v1/book/public/story/{pub_qr['token']}").status_code == 404

    # 家庭可见故事：匿名访问被拒绝，作者本人可访问。
    fam_qr = client.post(f"/api/v1/book/{bid}/qr?story_id={family_id}", headers=ha).json()
    assert client.get(f"/api/v1/book/public/story/{fam_qr['token']}").status_code == 403
    assert client.get(f"/api/v1/book/public/story/{fam_qr['token']}", headers=ha).status_code == 200

    # 私有故事即使伪造 token 也不能匿名访问：构造一个指向 private 的二维码记录后访问。
    db = SessionLocal()
    try:
        from app.models.publishing import BookQRCode

        rogue = BookQRCode(book_id=bid, story_id=private_id, token="rogue-token-for-test", status="active")
        db.add(rogue)
        db.commit()
    finally:
        db.close()
    assert client.get("/api/v1/book/public/story/rogue-token-for-test").status_code == 403


# ---------------------------------------------------------------------------
# 数字传承
# ---------------------------------------------------------------------------


def test_digital_legacy_cross_user_isolation(client):
    da, ha = register_and_login(client, "iso_legacy_owner")
    _, hb = register_and_login(client, "iso_legacy_thief")

    c = client.post(
        "/api/v1/legacy/contacts", headers=ha, json={"name": "女儿", "email": "d@example.com"}
    ).json()
    p = client.post(
        "/api/v1/legacy/policies",
        headers=ha,
        json={"contact_id": c["id"], "trigger": "manual", "share_scope": ["story:abc"]},
    ).json()

    # 他人：不能列出/修改/删除联系人，不能操作策略或查看事件。
    assert all(x["id"] != c["id"] for x in client.get("/api/v1/legacy/contacts", headers=hb).json())
    assert client.put(f"/api/v1/legacy/contacts/{c['id']}", headers=hb, json={"name": "篡改"}).status_code == 404
    assert client.delete(f"/api/v1/legacy/contacts/{c['id']}", headers=hb).status_code == 404
    assert all(x["id"] != p["id"] for x in client.get("/api/v1/legacy/policies", headers=hb).json())
    assert client.post(f"/api/v1/legacy/policies/{p['id']}/grant", headers=hb).status_code == 404
    assert client.post(f"/api/v1/legacy/policies/{p['id']}/revoke", headers=hb).status_code == 404
    assert client.get(f"/api/v1/legacy/policies/{p['id']}/events", headers=hb).status_code == 404
    assert client.post(f"/api/v1/legacy/policies/{p['id']}/trigger-review", headers=hb).status_code == 404

    # 他人不能用别人的 contact_id 创建策略。
    assert client.post(
        "/api/v1/legacy/policies", headers=hb, json={"contact_id": c["id"], "trigger": "manual"}
    ).status_code == 404


def test_digital_legacy_explicit_consent_and_scope(client):
    _, h = register_and_login(client, "iso_legacy_flow")
    c = client.post("/api/v1/legacy/contacts", headers=h, json={"name": "儿子"}).json()

    # share_scope 拒绝通配符。
    bad = client.post(
        "/api/v1/legacy/policies",
        headers=h,
        json={"contact_id": c["id"], "share_scope": ["all"]},
    )
    assert bad.status_code == 422

    p = client.post(
        "/api/v1/legacy/policies",
        headers=h,
        json={"contact_id": c["id"], "trigger": "manual", "share_scope": ["story:s1", "memory:m1"]},
    ).json()
    assert p["granted"] is False and p["status"] == "draft"

    # 未授权不能触发交付；授权后可触发人工审核；撤销后再次被拒。
    assert client.post(f"/api/v1/legacy/policies/{p['id']}/trigger-review", headers=h).status_code == 400
    assert client.post(f"/api/v1/legacy/policies/{p['id']}/grant", headers=h).status_code == 200
    assert client.post(f"/api/v1/legacy/policies/{p['id']}/trigger-review", headers=h).status_code == 200
    events = client.get(f"/api/v1/legacy/policies/{p['id']}/events", headers=h).json()
    assert {e["event_type"] for e in events} >= {"created", "granted", "triggered"}
    assert client.post(f"/api/v1/legacy/policies/{p['id']}/revoke", headers=h).status_code == 200
    assert client.post(f"/api/v1/legacy/policies/{p['id']}/trigger-review", headers=h).status_code == 400

    # 已撤销策略不能重新授权。
    assert client.post(f"/api/v1/legacy/policies/{p['id']}/grant", headers=h).status_code == 400
