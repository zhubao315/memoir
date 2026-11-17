"""Media validation & signed URL tests (S-05, S-09)."""

from conftest import register_and_login


PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000a49444154789c6360000002000100ffff030000060005"
    "7c0f360000000049454e44ae426082"
)


def test_upload_validation_and_signed_url(client):
    _, h = register_and_login(client, "mediauser")

    bad = client.post("/api/v1/media/upload", headers=h, files={"file": ("evil.exe", b"MZ\x90", "application/octet-stream")})
    assert bad.status_code == 400

    ok = client.post("/api/v1/media/upload", headers=h, files={"file": ("photo.png", PNG, "image/png")})
    assert ok.status_code == 201, ok.text
    data = ok.json()
    assert data["media_type"] == "photo"
    assert "/api/v1/media/file?token=" in data["url"]

    served = client.get(data["url"])
    assert served.status_code == 200
    assert served.content == PNG

    # Signed URL expires; tampered token rejected.
    assert client.get(data["url"] + "tampered").status_code in (400, 404, 422)

    url_resp = client.get(f"/api/v1/media/{data['id']}/url", headers=h)
    assert url_resp.status_code == 200
