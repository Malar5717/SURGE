import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import Incident, IncidentLink


def _two_incidents(session):
    a = Incident(category="pothole", lat=13.0, lng=80.0)
    b = Incident(category="pothole", lat=13.0001, lng=80.0)
    session.add_all([a, b])
    session.flush()
    return a, b


def _create(client, lat=13.0):
    return client.post(
        "/incidents", json={"category": "pothole", "lat": lat, "lng": 80.0}
    ).json()["id"]


def _links(session):
    return session.scalars(select(IncidentLink)).all()


def test_link_to_itself_is_rejected(session):
    a, _ = _two_incidents(session)
    session.add(IncidentLink(incident_a=a.id, incident_b=a.id))
    with pytest.raises(IntegrityError):
        session.flush()


def test_link_must_be_sorted(session):
    a, b = _two_incidents(session)
    session.add(IncidentLink(incident_a=b.id, incident_b=a.id))
    with pytest.raises(IntegrityError):
        session.flush()


def test_duplicate_link_is_rejected(session):
    a, b = _two_incidents(session)
    session.add(IncidentLink(incident_a=a.id, incident_b=b.id))
    session.flush()

    session.add(IncidentLink(incident_a=a.id, incident_b=b.id))
    with pytest.raises(IntegrityError):
        session.flush()


def test_linking_works_from_either_direction_and_stores_one_row(client, session):
    a = _create(client)
    b = _create(client)

    response = client.post(f"/incidents/{b}/links", json={"other_id": a})
    assert response.status_code == 201
    body = response.json()
    assert (body["incident_a"], body["incident_b"]) == (min(a, b), max(a, b))

    duplicate = client.post(f"/incidents/{a}/links", json={"other_id": b})
    assert duplicate.status_code == 409
    assert len(_links(session)) == 1


def test_linking_to_itself_gives_422(client):
    a = _create(client)
    response = client.post(f"/incidents/{a}/links", json={"other_id": a})
    assert response.status_code == 422


def test_duplicate_link_gives_409(client):
    a = _create(client)
    b = _create(client)

    assert client.post(f"/incidents/{a}/links", json={"other_id": b}).status_code == 201
    assert client.post(f"/incidents/{a}/links", json={"other_id": b}).status_code == 409


def test_unknown_incident_gives_404(client):
    a = _create(client)
    assert (
        client.post("/incidents/999999/links", json={"other_id": a}).status_code == 404
    )
    assert (
        client.post(f"/incidents/{a}/links", json={"other_id": 999999}).status_code
        == 404
    )


def test_group_size_through_a_chain(client):
    a = _create(client)
    b = _create(client)
    c = _create(client)
    client.post(f"/incidents/{a}/links", json={"other_id": b})
    client.post(f"/incidents/{b}/links", json={"other_id": c})

    assert client.get(f"/incidents/{a}").json()["linked_incident_ids"] == [b]
    for incident_id in (a, b, c):
        assert client.get(f"/incidents/{incident_id}").json()["group_size"] == 3


def test_deleting_a_link_shrinks_the_group(client):
    a = _create(client)
    b = _create(client)
    c = _create(client)
    client.post(f"/incidents/{a}/links", json={"other_id": b})
    client.post(f"/incidents/{b}/links", json={"other_id": c})

    response = client.delete(f"/incidents/{c}/links/{b}")
    assert response.status_code == 204
    assert client.get(f"/incidents/{a}").json()["group_size"] == 2
    assert client.get(f"/incidents/{c}").json()["group_size"] == 1


def test_deleting_a_missing_link_gives_404(client):
    a = _create(client)
    b = _create(client)
    assert client.delete(f"/incidents/{a}/links/{b}").status_code == 404
