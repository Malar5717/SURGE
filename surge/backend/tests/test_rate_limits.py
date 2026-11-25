from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models import AuthEvent


def _signup(client, handle, password="password123"):
    return client.post(
        "/auth/signup", json={"handle": handle, "password": password}
    )


def test_sixth_signup_per_ip_gives_429(client):
    for i in range(5):
        assert _signup(client, f"user{i}").status_code == 201
    assert _signup(client, "user5").status_code == 429


def test_sixth_failed_login_for_handle_gives_429(client):
    assert _signup(client, "asha").status_code == 201
    client.post("/auth/logout")

    for _ in range(5):
        response = client.post(
            "/auth/login", json={"handle": "asha", "password": "wrongpassword"}
        )
        assert response.status_code == 401

    response = client.post(
        "/auth/login", json={"handle": "ASHA", "password": "password123"}
    )
    assert response.status_code == 429


def test_twenty_first_failed_login_per_ip_gives_429(client):
    for i in range(20):
        response = client.post(
            "/auth/login", json={"handle": f"ghost{i}", "password": "wrongpassword"}
        )
        assert response.status_code == 401

    response = client.post(
        "/auth/login", json={"handle": "ghost20", "password": "wrongpassword"}
    )
    assert response.status_code == 429


def test_old_signups_do_not_count(client, session):
    old = datetime.now(timezone.utc) - timedelta(hours=2)
    for i in range(5):
        session.add(
            AuthEvent(
                event="signup",
                ip="testclient",
                handle_tried=f"old{i}",
                created_at=old,
            )
        )
    session.commit()

    assert _signup(client, "fresh1").status_code == 201


def test_old_failed_logins_do_not_count(client, session):
    old = datetime.now(timezone.utc) - timedelta(minutes=16)
    for _ in range(5):
        session.add(
            AuthEvent(
                event="login_fail",
                ip="testclient",
                handle_tried="asha",
                created_at=old,
            )
        )
    session.commit()

    assert _signup(client, "asha").status_code == 201
    client.post("/auth/logout")

    response = client.post(
        "/auth/login", json={"handle": "asha", "password": "password123"}
    )
    assert response.status_code == 200


def test_each_action_writes_the_right_event(client, session):
    assert _signup(client, "asha").status_code == 201
    assert (
        client.post(
            "/auth/login", json={"handle": "asha", "password": "wrongpassword"}
        ).status_code
        == 401
    )
    assert client.post("/auth/logout").status_code == 204
    assert (
        client.post(
            "/auth/login", json={"handle": "asha", "password": "password123"}
        ).status_code
        == 200
    )

    events = session.scalars(select(AuthEvent).order_by(AuthEvent.id)).all()
    assert [event.event for event in events] == [
        "signup",
        "login_fail",
        "logout",
        "login_ok",
    ]


def test_events_never_contain_password_or_token(client, session):
    password = "password123"
    _signup(client, "asha", password)
    token = client.cookies.get("surge_session")

    events = session.scalars(select(AuthEvent)).all()
    dumped = " ".join(
        f"{event.event} {event.handle_tried} {event.ip} {event.user_id}"
        for event in events
    )
    assert password not in dumped
    assert token not in dumped
