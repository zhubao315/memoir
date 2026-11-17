"""Family permissions, book export & QR, digital legacy consent."""

from conftest import register_and_login


def test_family_roles_and_permissions(client):
    _, ha = register_and_login(client, "owner1")
    _, hb = register_and_login(client, "member1")

    fam = client.post("/api/v1/family", headers=ha, json={"name": "王家"})
    assert fam.status_code == 201
    fid = fam.json()["id"]

    # Outsider cannot view the family.
    assert client.get(f"/api/v1/family/{fid}", headers=hb).status_code == 403

    inv = client.post(f"/api/v1/family/{fid}/invite", headers=ha, json={"email": "m@example.com", "role": "viewer"})
    assert inv.status_code == 201
    token = inv.json()["token"]

    assert client.post(f"/api/v1/family/invite/{token}/accept", headers=hb).status_code == 200
    assert client.get(f"/api/v1/family/{fid}", headers=hb).status_code == 200

    # Viewer cannot invite others (resource-level authorization).
    assert client.post(f"/api/v1/family/{fid}/invite", headers=hb, json={"email": "x@y.com"}).status_code == 403


def test_book_export_and_qr(client):
    _, h = register_and_login(client, "bookuser")
    book = client.post("/api/v1/book", headers=h, json={"title": "我的一生", "author": "我"})
    assert book.status_code == 201
    bid = book.json()["id"]
    ch = client.post(f"/api/v1/book/{bid}/chapters", headers=h, json={"title": "第一章", "content": "童年"})
    assert ch.status_code == 201

    md = client.get(f"/api/v1/book/{bid}/export?format=markdown", headers=h)
    assert md.status_code == 200 and "我的一生" in md.text

    pdf = client.get(f"/api/v1/book/{bid}/export?format=pdf", headers=h)
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"

    qr = client.post(f"/api/v1/book/{bid}/qr", headers=h)
    assert qr.status_code == 201
    qr_id, token = qr.json()["id"], qr.json()["token"]

    # Stable public token works; revocation invalidates it.
    assert client.get(f"/api/v1/book/public/story/{token}").status_code == 404  # no story linked
    assert client.post(f"/api/v1/book/qr/{qr_id}/revoke", headers=h).status_code == 200
    assert client.get(f"/api/v1/book/public/story/{token}").status_code == 404


def test_digital_legacy_explicit_consent(client):
    _, h = register_and_login(client, "legacyuser")
    c = client.post("/api/v1/legacy/contacts", headers=h, json={"name": "女儿", "email": "d@example.com"})
    assert c.status_code == 201
    p = client.post("/api/v1/legacy/policies", headers=h, json={"contact_id": c.json()["id"], "trigger": "manual"})
    assert p.status_code == 201
    pid = p.json()["id"]

    # Trigger before grant is refused.
    assert client.post(f"/api/v1/legacy/policies/{pid}/trigger-review", headers=h).status_code == 400
    assert client.post(f"/api/v1/legacy/policies/{pid}/grant", headers=h).status_code == 200
    review = client.post(f"/api/v1/legacy/policies/{pid}/trigger-review", headers=h)
    assert review.status_code == 200 and "人工审核" in review.json()["message"]
    assert client.post(f"/api/v1/legacy/policies/{pid}/revoke", headers=h).status_code == 200
