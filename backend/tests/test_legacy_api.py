"""Backward compatibility: all original v0.1 endpoints keep working."""

from conftest import register_and_login


def test_legacy_entries_tags_stats_and_media_endpoint(client):
    _, h = register_and_login(client, "legacyuser_v01")

    created = client.post(
        "/api/entries",
        headers=h,
        json={"title": "旧版记忆", "content": "内容", "entry_date": "2026-01-01", "tags": ["家人"]},
    )
    assert created.status_code == 200, created.text
    eid = created.json()["id"]

    assert client.get("/api/entries", headers=h).status_code == 200
    assert client.get(f"/api/entries/{eid}", headers=h).json()["title"] == "旧版记忆"

    upd = client.put(f"/api/entries/{eid}", headers=h, json={"title": "改过的记忆"})
    assert upd.json()["title"] == "改过的记忆"

    tag = client.post("/api/tags", headers=h, json={"name": "家人", "color": "#123456"})
    assert tag.status_code == 200
    assert client.get("/api/tags", headers=h).status_code == 200

    stats = client.get("/api/stats", headers=h)
    assert stats.json()["total_entries"] >= 1

    # Originally broken endpoint now exists and enforces ownership.
    missing = client.get("/api/media/does-not-exist/file", headers=h)
    assert missing.status_code == 404

    deleted = client.delete(f"/api/entries/{eid}", headers=h)
    assert deleted.status_code == 200
    assert client.get(f"/api/entries/{eid}", headers=h).status_code == 404
