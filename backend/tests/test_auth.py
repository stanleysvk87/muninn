from app.auth import throttle
from app.auth.security import bootstrap_token


def test_bootstrap_requires_consent(client):
    client.cookies.clear()
    res = client.post(
        "/api/auth/bootstrap",
        json={
            "username": "no-consent-user",
            "password": "test-password-123",
            "setup_token": bootstrap_token(),
        },
    )
    assert res.status_code == 422


def test_bootstrap_rejects_missing_setup_token(client):
    """/api/auth/bootstrap is unauthenticated by necessity -- without the
    host-side token it was first-come-first-served for the whole archive."""
    throttle.clear_all()
    client.cookies.clear()
    res = client.post(
        "/api/auth/bootstrap",
        json={"username": "attacker", "password": "test-password-123", "consent": True},
    )
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "bootstrap_token_invalid"

    res = client.post(
        "/api/auth/bootstrap",
        json={
            "username": "attacker",
            "password": "test-password-123",
            "consent": True,
            "setup_token": "not-the-right-token",
        },
    )
    assert res.status_code == 403
    throttle.clear_all()


def test_login_throttles_repeated_failures(client, admin_session):
    """Unlimited login attempts were both a guessing oracle and a CPU
    amplifier (200k PBKDF2 rounds per attempt on an SBC)."""
    throttle.clear_all()
    client.cookies.clear()
    codes = []
    for _ in range(throttle.MAX_FAILURES + 1):
        res = client.post("/api/auth/login", json={"username": "admin", "password": "nope"})
        codes.append(res.status_code)

    assert codes[0] == 401
    assert codes[-1] == 429, "repeated failures must start being refused before the KDF runs"

    # A correct password is refused too while the lockout is active.
    res = client.post("/api/auth/login", json={"username": "admin", "password": "test-password-123"})
    assert res.status_code == 429

    throttle.clear_all()
    res = client.post("/api/auth/login", json={"username": "admin", "password": "test-password-123"})
    assert res.status_code == 200


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
