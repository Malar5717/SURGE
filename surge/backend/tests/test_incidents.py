import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import Event, Incident


def test_invalid_event_type_is_rejected(session):
    incident = Incident(category="pothole", lat=13.0, lng=80.0)
    session.add(incident)
    session.flush()

    session.add(Event(incident_id=incident.id, type="closed"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_create_incident_creates_one_reported_event(auth_client, post_incident, session):
    response = post_incident(auth_client)
    assert response.status_code == 201
    body = response.json()
    assert body["category"] == "pothole"
    assert [e["type"] for e in body["events"]] == ["reported"]

    events = session.scalars(
        select(Event).where(Event.incident_id == body["id"])
    ).all()
    assert [e.type for e in events] == ["reported"]


def test_note_is_appended_oldest_first(auth_client, post_incident):
    incident = post_incident(auth_client, category="garbage").json()

    note = auth_client.post(
        f"/incidents/{incident['id']}/events",
        json={"type": "note", "note": "still here"},
    )
    assert note.status_code == 201

    detail = auth_client.get(f"/incidents/{incident['id']}").json()
    assert [e["type"] for e in detail["events"]] == ["reported", "note"]
    assert detail["events"][1]["note"] == "still here"


def test_reported_event_cannot_be_added(auth_client, post_incident):
    incident = post_incident(auth_client).json()

    response = auth_client.post(
        f"/incidents/{incident['id']}/events",
        json={"type": "reported", "note": "x"},
    )
    assert response.status_code == 422


def test_invalid_category_gives_422(auth_client, post_incident, session):
    response = post_incident(auth_client, category="banana")
    assert response.status_code == 422
    assert session.scalars(select(Incident)).all() == []


@pytest.mark.parametrize("lat,lng", [(91, 80), (-91, 80), (13, 181), (13, -181)])
def test_out_of_range_coordinates_give_422(auth_client, post_incident, lat, lng):
    response = post_incident(auth_client, lat=lat, lng=lng)
    assert response.status_code == 422


def test_missing_incident_gives_404(auth_client):
    assert auth_client.get("/incidents/999999").status_code == 404
    assert (
        auth_client.post(
            "/incidents/999999/events", json={"type": "note", "note": "x"}
        ).status_code
        == 404
    )


def test_bounding_box_filter(auth_client, post_incident):
    near = post_incident(auth_client, lat=13.0, lng=80.0).json()
    post_incident(auth_client, category="garbage", lat=13.25, lng=80.30)

    response = auth_client.get(
        "/incidents",
        params={
            "min_lat": 12.95,
            "max_lat": 13.05,
            "min_lng": 79.95,
            "max_lng": 80.05,
        },
    )
    assert response.status_code == 200
    assert [i["id"] for i in response.json()] == [near["id"]]
