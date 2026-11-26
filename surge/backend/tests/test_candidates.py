from datetime import datetime, timedelta, timezone

from app.categories import radius_for
from app.logic import haversine_m
from app.models import Event, Incident

METRES_PER_DEGREE = 111_194.9
POTHOLE_RADIUS = radius_for("pothole")


def _north(lat: float, metres: float) -> float:
    return lat + metres / METRES_PER_DEGREE


def _add_incident(session, category, lat, lng, days_ago=0):
    event = Event(
        type="reported",
        created_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
    )
    incident = Incident(category=category, lat=lat, lng=lng, events=[event])
    session.add(incident)
    session.commit()
    return incident


def _candidates(client, category, lat, lng, **extra):
    params = {"category": category, "lat": lat, "lng": lng, **extra}
    return client.get("/incidents/candidates", params=params)


def test_identical_points_are_zero():
    assert haversine_m(13.0, 80.0, 13.0, 80.0) == 0


def test_one_thousandth_degree_latitude_is_about_111m():
    assert abs(haversine_m(13.0, 80.0, 13.001, 80.0) - 111) < 2


def test_distance_is_symmetric():
    a = haversine_m(13.0, 80.0, 13.05, 80.07)
    b = haversine_m(13.05, 80.07, 13.0, 80.0)
    assert abs(a - b) < 1e-9


def test_same_category_within_radius_is_returned(client, session):
    incident = _add_incident(session, "pothole", 13.0, 80.0)

    body = _candidates(client, "pothole", 13.0, 80.0).json()
    assert [c["id"] for c in body] == [incident.id]
    assert body[0]["distance_m"] < 1


def test_different_category_is_not_returned(client, session):
    _add_incident(session, "garbage", 13.0, 80.0)
    assert _candidates(client, "pothole", 13.0, 80.0).json() == []


def test_beyond_radius_is_not_returned(client, session):
    _add_incident(session, "pothole", _north(13.0, POTHOLE_RADIUS * 3), 80.0)
    assert _candidates(client, "pothole", 13.0, 80.0).json() == []


def test_accuracy_widens_radius(client, session):
    incident = _add_incident(
        session, "pothole", _north(13.0, POTHOLE_RADIUS * 1.5), 80.0
    )

    assert _candidates(client, "pothole", 13.0, 80.0).json() == []
    body = _candidates(
        client, "pothole", 13.0, 80.0, accuracy_m=POTHOLE_RADIUS * 0.75
    ).json()
    assert [c["id"] for c in body] == [incident.id]


def test_accuracy_never_widens_beyond_twice_radius(client, session):
    _add_incident(session, "pothole", _north(13.0, POTHOLE_RADIUS * 2.5), 80.0)

    body = _candidates(client, "pothole", 13.0, 80.0, accuracy_m=10_000).json()
    assert body == []


def test_incident_with_old_latest_event_is_excluded(client, session):
    _add_incident(session, "pothole", 13.0, 80.0, days_ago=22)
    assert _candidates(client, "pothole", 13.0, 80.0).json() == []


def test_recent_note_keeps_old_incident(client, session):
    incident = _add_incident(session, "pothole", 13.0, 80.0, days_ago=30)
    session.add(
        Event(
            incident_id=incident.id,
            type="note",
            note="still there",
            created_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
    )
    session.commit()

    body = _candidates(client, "pothole", 13.0, 80.0).json()
    assert [c["id"] for c in body] == [incident.id]


def test_returns_at_most_three_nearest_first(client, session):
    offsets = [18, 5, 12, 9]
    created = {m: _add_incident(session, "pothole", _north(13.0, m), 80.0) for m in offsets}

    body = _candidates(client, "pothole", 13.0, 80.0).json()
    distances = [c["distance_m"] for c in body]

    assert len(body) == 3
    assert distances == sorted(distances)
    assert created[18].id not in [c["id"] for c in body]
