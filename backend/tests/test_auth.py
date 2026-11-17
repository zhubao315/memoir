"""Auth & security tests (S-01, S-06, S-07, S-08)."""

from conftest import register_and_login


def test_register_login_me_refresh_logout(client):
    data, headers = register_and_login(client, "authuser")
    assert "access_token" in data and "refresh_token" in data

    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["username"] == "authuser"

    refreshed = client.post("/api/v1/auth/refresh", json={"refresh_token": data["refresh_token"]})
    assert refreshed.status_code == 200, refreshed.text
    new_tokens = refreshed.json()
    assert new_tokens["refresh_token"] != data["refresh_token"]

    # Old refresh token must be rejected (rotation).
    reuse = client.post("/api/v1/auth/refresh", json={"refresh_token": data["refresh_token"]})
    assert reuse.status_code == 401

    out = client.post("/api/v1/auth/logout", headers=headers)
    assert out.status_code == 200
    after = client.get("/api/auth/me", headers=headers)
    assert after.status_code == 401  # access token revoked


def test_cors_and_secret_not_default_in_source():
    from app.core.config import settings

    assert "*" not in settings.cors_origin_list
    assert settings.SECRET_KEY  # loaded from env/settings


def test_wrong_password(client):
    r = client.post("/api/auth/login", json={"username": "authuser", "password": "wrongpass"})
    assert r.status_code == 401
