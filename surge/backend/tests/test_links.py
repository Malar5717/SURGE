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


def _create_at(client, lat, lng):
    return client.post(
        "/incidents", json={"category": "pothole", "lat": lat, "lng": lng}
    ).json()["id"]


def _linked_pair(client):
    a = _create_at(client, 13.0, 80.0)
    b = _create_at(client, 13.1, 80.1)
    client.post(f"/incidents/{a}/links", json={"other_id": b})
    return a, b


def test_links_without_params_returns_all(client):
    a, b = _linked_pair(client)

    body = client.get("/links").json()
    assert len(body) == 1
    link = body[0]
    assert (link["incident_a"], link["incident_b"]) == (min(a, b), max(a, b))


def test_links_box_with_both_ends_returns_link(client):
    _linked_pair(client)

    body = client.get(
        "/links",
        params={
            "min_lat": 12.9,
            "max_lat": 13.2,
            "min_lng": 79.9,
            "max_lng": 80.2,
        },
    ).json()
    assert len(body) == 1


def test_links_box_with_one_end_returns_link(client):
    a, _ = _linked_pair(client)

    body = client.get(
        "/links",
        params={
            "min_lat": 12.95,
            "max_lat": 13.05,
            "min_lng": 79.95,
            "max_lng": 80.05,
        },
    ).json()
    assert [link["incident_a"] for link in body] == [a]


def test_links_box_with_neither_end_returns_nothing(client):
    _linked_pair(client)

    body = client.get(
        "/links",
        params={
            "min_lat": 10.0,
            "max_lat": 10.5,
            "min_lng": 70.0,
            "max_lng": 70.5,
        },
    ).json()
    assert body == []


def test_links_include_both_ends_coordinates(client):
    a, b = _linked_pair(client)

    link = client.get("/links").json()[0]
    assert link["incident_a"] == a
    assert link["incident_b"] == b
    assert (link["a_lat"], link["a_lng"]) == (13.0, 80.0)
    assert (link["b_lat"], link["b_lng"]) == (13.1, 80.1)
