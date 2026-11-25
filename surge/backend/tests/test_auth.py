from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models import AuthSession, User


def _signup(client, handle="asha", password="password123"):
    return client.post(
        "/auth/signup", json={"handle": handle, "password": password}
    )


def test_signup_returns_handle_and_sets_http_only_cookie(client):
    response = _signup(client)
    assert response.status_code == 201
    assert response.json() == {"handle": "asha"}

    cookie = response.headers["set-cookie"].lower()
    assert "surge_session=" in cookie
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "path=/" in cookie


def test_duplicate_handle_in_different_case_gives_409(client):
    assert _signup(client, handle="Asha").status_code == 201
    assert _signup(client, handle="asha").status_code == 409


@pytest.mark.parametrize(
    "payload",
    [
        {"handle": "ab", "password": "password123"},
        {"handle": "bad handle", "password": "password123"},
        {"handle": "a" * 21, "password": "password123"},
        {"handle": "asha", "password": "short"},
    ],
)
def test_invalid_credentials_give_422(client, payload):
    assert client.post("/auth/signup", json=payload).status_code == 422


def test_login_works(client):
    _signup(client)
    client.post("/auth/logout")

    response = client.post(
        "/auth/login", json={"handle": "ASHA", "password": "password123"}
    )
    assert response.status_code == 200
    assert response.json() == {"handle": "asha"}


def test_wrong_password_and_unknown_handle_share_a_message(client):
    _signup(client)
    client.post("/auth/logout")

    wrong = client.post(
        "/auth/login", json={"handle": "asha", "password": "wrongpassword"}
    )
    unknown = client.post(
        "/auth/login", json={"handle": "nobody", "password": "password123"}
    )
    assert wrong.status_code == 401
    assert unknown.status_code == 401
    assert wrong.json()["detail"] == unknown.json()["detail"]


def test_me_works_with_cookie_and_gives_401_without(client):
    _signup(client)
    assert client.get("/auth/me").json() == {"handle": "asha"}

    client.cookies.clear()
    assert client.get("/auth/me").status_code == 401


def test_logout_ends_the_session(client):
    _signup(client)
    assert client.post("/auth/logout").status_code == 204
    assert client.get("/auth/me").status_code == 401


def test_expired_session_gives_401(client, session):
    _signup(client)

    record = session.scalar(select(AuthSession))
    record.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    session.commit()

    assert client.get("/auth/me").status_code == 401


def test_banned_user_gives_401(client, session):
    _signup(client)

    user = session.scalar(select(User))
    user.is_banned = True
    session.commit()

    assert client.get("/auth/me").status_code == 401
