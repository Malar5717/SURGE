from sqlalchemy import select

from app.models import Event, Incident, IncidentLink, User


def _login(client, handle, password="password123"):
    response = client.post(
        "/auth/login", json={"handle": handle, "password": password}
    )
    assert response.status_code == 200


def _signup(client, handle, password="password123"):
    response = client.post(
        "/auth/signup", json={"handle": handle, "password": password}
    )
    assert response.status_code == 201


def _new_incident(client):
    return client.post(
        "/incidents", json={"category": "pothole", "lat": 13.0, "lng": 80.0}
    )


def test_each_write_endpoint_needs_a_login(client):
    payload = {"category": "pothole", "lat": 13.0, "lng": 80.0}
    assert client.post("/incidents", json=payload).status_code == 401
    assert (
        client.post(
            "/incidents/1/events", json={"type": "note", "note": "x"}
        ).status_code
        == 401
    )
    assert client.post("/incidents/1/links", json={"other_id": 2}).status_code == 401
    assert client.delete("/incidents/1/links/2").status_code == 401


def test_reads_still_work_logged_out(auth_client):
    incident = _new_incident(auth_client).json()
    auth_client.cookies.clear()

    assert auth_client.get("/incidents").status_code == 200
    assert auth_client.get(f"/incidents/{incident['id']}").status_code == 200
    assert auth_client.get("/links").status_code == 200
    assert (
        auth_client.get(
            "/incidents/candidates",
            params={"category": "pothole", "lat": 13.0, "lng": 80.0},
        ).status_code
        == 200
    )


def test_created_rows_carry_the_logged_in_user(auth_client, session):
    user = session.scalar(select(User).where(User.handle_lower == "tester"))
    incident = _new_incident(auth_client).json()
    other = _new_incident(auth_client).json()

    note = auth_client.post(
        f"/incidents/{incident['id']}/events",
        json={"type": "note", "note": "still here"},
    ).json()
    link = auth_client.post(
        f"/incidents/{incident['id']}/links", json={"other_id": other["id"]}
    ).json()

    stored_incident = session.get(Incident, incident["id"])
    assert stored_incident.created_by == user.id

    stored_reported = session.scalar(
        select(Event).where(
            Event.incident_id == incident["id"], Event.type == "reported"
        )
    )
    assert stored_reported.created_by == user.id

    stored_note = session.get(Event, note["id"])
    assert stored_note.created_by == user.id

    stored_link = session.get(
        IncidentLink, (link["incident_a"], link["incident_b"])
    )
    assert stored_link.created_by == user.id


def test_responses_show_the_handle_and_never_the_user_id(auth_client):
    incident = _new_incident(auth_client).json()
    assert incident["created_by_handle"] == "tester"
    assert "created_by" not in incident
    assert all("created_by" not in event for event in incident["events"])

    note = auth_client.post(
        f"/incidents/{incident['id']}/events",
        json={"type": "note", "note": "hello"},
    ).json()
    assert note["created_by_handle"] == "tester"
    assert "created_by" not in note

    other = auth_client.post(
        "/incidents", json={"category": "garbage", "lat": 13.0, "lng": 80.0}
    ).json()
    link = auth_client.post(
        f"/incidents/{incident['id']}/links", json={"other_id": other["id"]}
    ).json()
    assert link["created_by_handle"] == "tester"
    assert "created_by" not in link

    detail = auth_client.get(f"/incidents/{incident['id']}").json()
    assert detail["created_by_handle"] == "tester"
    assert "created_by" not in detail


def test_only_the_link_creator_can_delete_it(client):
    _signup(client, "asha")
    incident = _new_incident(client).json()
    other = _new_incident(client).json()
    link = client.post(
        f"/incidents/{incident['id']}/links", json={"other_id": other['id']}
    ).json()

    client.post("/auth/logout")
    _signup(client, "ravi")

    assert (
        client.delete(
            f"/incidents/{incident['id']}/links/{other['id']}"
        ).status_code
        == 403
    )

    client.post("/auth/logout")
    _login(client, "asha")
    assert (
        client.delete(
            f"/incidents/{incident['id']}/links/{other['id']}"
        ).status_code
        == 204
    )
    assert client.get("/links").json() == []
    assert link["incident_a"] != link["incident_b"]
