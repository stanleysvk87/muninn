def test_bootstrap_requires_consent(client):
    client.cookies.clear()
    res = client.post(
        "/api/auth/bootstrap",
        json={"username": "no-consent-user", "password": "test-password-123"},
    )
    assert res.status_code == 422


def test_me_requires_authentication(client):
    client.cookies.clear()
    res = client.get("/api/auth/me")
    assert res.status_code == 401


def test_bootstrap_then_me(client, admin_session):
    res = client.get("/api/auth/me")
    assert res.status_code == 200
    assert res.json()["username"] == "admin"


def test_login_rejects_wrong_password(client, admin_session):
    client.cookies.clear()
    res = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert res.status_code == 401


def test_logout_clears_session(client, admin_session, csrf_headers):
    res = client.post("/api/auth/logout", headers=csrf_headers)
    assert res.status_code == 200
    res = client.get("/api/auth/me")
    assert res.status_code == 401
