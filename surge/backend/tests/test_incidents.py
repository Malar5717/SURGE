import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import Event, Incident


def test_invalid_category_is_rejected(session):
    session.add(Incident(category="banana", lat=13.0, lng=80.0))
    with pytest.raises(IntegrityError):
        session.flush()


def test_invalid_event_type_is_rejected(session):
    incident = Incident(category="pothole", lat=13.0, lng=80.0)
    session.add(incident)
    session.flush()

    session.add(Event(incident_id=incident.id, type="closed"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_create_incident_creates_one_reported_event(client, session):
    response = client.post(
        "/incidents", json={"category": "pothole", "lat": 13.0, "lng": 80.0}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["category"] == "pothole"
    assert [e["type"] for e in body["events"]] == ["reported"]

    events = session.scalars(
        select(Event).where(Event.incident_id == body["id"])
    ).all()
    assert [e.type for e in events] == ["reported"]


def test_note_is_appended_oldest_first(client):
    incident = client.post(
        "/incidents", json={"category": "garbage", "lat": 13.0, "lng": 80.0}
    ).json()

    note = client.post(
        f"/incidents/{incident['id']}/events",
        json={"type": "note", "note": "still here"},
    )
    assert note.status_code == 201

    detail = client.get(f"/incidents/{incident['id']}").json()
    assert [e["type"] for e in detail["events"]] == ["reported", "note"]
    assert detail["events"][1]["note"] == "still here"


def test_reported_event_cannot_be_added(client):
    incident = client.post(
        "/incidents", json={"category": "pothole", "lat": 13.0, "lng": 80.0}
    ).json()

    response = client.post(
        f"/incidents/{incident['id']}/events",
        json={"type": "reported", "note": "x"},
    )
    assert response.status_code == 422


def test_invalid_category_gives_422(client):
    response = client.post(
        "/incidents", json={"category": "banana", "lat": 13.0, "lng": 80.0}
    )
    assert response.status_code == 422


@pytest.mark.parametrize("lat,lng", [(91, 80), (-91, 80), (13, 181), (13, -181)])
def test_out_of_range_coordinates_give_422(client, lat, lng):
    response = client.post(
        "/incidents", json={"category": "pothole", "lat": lat, "lng": lng}
    )
    assert response.status_code == 422


def test_missing_incident_gives_404(client):
    assert client.get("/incidents/999999").status_code == 404
    assert (
        client.post(
            "/incidents/999999/events", json={"type": "note", "note": "x"}
        ).status_code
        == 404
    )


def test_bounding_box_filter(client):
    near = client.post(
        "/incidents", json={"category": "pothole", "lat": 13.0, "lng": 80.0}
    ).json()
    client.post("/incidents", json={"category": "garbage", "lat": 14.0, "lng": 81.0})

    response = client.get(
        "/incidents",
        params={
            "min_lat": 12.5,
            "max_lat": 13.5,
            "min_lng": 79.5,
            "max_lng": 80.5,
        },
    )
    assert response.status_code == 200
    assert [i["id"] for i in response.json()] == [near["id"]]
