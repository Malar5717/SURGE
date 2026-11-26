from datetime import datetime, timedelta, timezone

from PIL import Image

from app.models import Event


def _now_minus(minutes):
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()


def _now_plus(minutes):
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


def _files(uploads):
    return sorted(path.name for path in uploads.glob("*"))


def test_valid_post_creates_incident_event_and_files(
    auth_client, post_incident, session, uploads
):
    response = post_incident(auth_client, description="  deep pothole  ")
    assert response.status_code == 201

    body = response.json()
    assert body["description"] == "deep pothole"
    assert body["photo_url"].startswith("/photos/")
    assert body["thumb_url"].endswith("_t.jpg")
    assert [event["type"] for event in body["events"]] == ["reported"]

    event = body["events"][0]
    assert event["photo_url"] == body["photo_url"]
    assert event["thumb_url"] == body["thumb_url"]

    stored = session.get(Event, event["id"])
    assert stored.photo_file and stored.thumb_file
    assert len(stored.phash) == 16
    assert stored.captured_at is not None

    assert len(_files(uploads)) == 2
    assert (uploads / stored.photo_file).exists()
    assert (uploads / stored.thumb_file).exists()

    with Image.open(uploads / stored.photo_file) as image:
        assert dict(image.getexif()) == {}


def test_eleventh_post_in_an_hour_gives_429(
    auth_client, post_incident
):
    for _ in range(10):
        assert post_incident(auth_client).status_code == 201

    assert post_incident(auth_client).status_code == 429


def test_post_outside_service_area_gives_422(auth_client, post_incident):
    assert post_incident(auth_client, lat=12.0, lng=80.0).status_code == 422
    assert post_incident(auth_client, lat=13.0, lng=79.0).status_code == 422


def test_accuracy_worse_than_100m_gives_422(auth_client, post_incident):
    assert post_incident(auth_client, accuracy_m=101).status_code == 422
    assert post_incident(auth_client, accuracy_m=100).status_code == 201


def test_stale_or_future_capture_time_gives_422(auth_client, post_incident):
    assert (
        post_incident(auth_client, captured_at=_now_minus(20)).status_code == 422
    )
    assert post_incident(auth_client, captured_at=_now_plus(5)).status_code == 422
    assert post_incident(auth_client, captured_at=_now_minus(5)).status_code == 201


def test_description_longer_than_280_gives_422(auth_client, post_incident):
    assert post_incident(auth_client, description="x" * 281).status_code == 422
    assert post_incident(auth_client, description="x" * 280).status_code == 201


def test_oversized_file_gives_413(auth_client, post_incident):
    oversized = b"x" * (5 * 1024 * 1024 + 1)
    assert post_incident(auth_client, photo=oversized).status_code == 413


def test_non_image_gives_422(auth_client, post_incident):
    assert post_incident(auth_client, photo=b"not an image").status_code == 422


def test_same_photo_twice_gives_409_with_existing_id(
    auth_client, post_incident, uploads, make_jpeg
):
    photo = make_jpeg(seed=99, size=(900, 700))
    first = post_incident(auth_client, photo=photo)
    assert first.status_code == 201

    second = post_incident(auth_client, photo=photo)
    assert second.status_code == 409
    assert second.json()["detail"]["existing_incident_id"] == first.json()["id"]

    assert len(_files(uploads)) == 2


def test_link_to_a_valid_candidate_creates_the_link(
    auth_client, post_incident, session
):
    first = post_incident(auth_client, lat=13.0, lng=80.0).json()

    response = post_incident(auth_client, lat=13.0, lng=80.0, link_to=[first["id"]])
    assert response.status_code == 201
    assert response.json()["linked_incident_ids"] == [first["id"]]

    links = auth_client.get("/links").json()
    assert len(links) == 1
    assert {links[0]["incident_a"], links[0]["incident_b"]} == {
        first["id"],
        response.json()["id"],
    }


def test_link_to_far_or_other_category_gives_422(
    auth_client, post_incident, uploads
):
    far = post_incident(auth_client, lat=13.1, lng=80.1).json()["id"]
    other = post_incident(auth_client, category="garbage").json()["id"]

    before = len(_files(uploads))
    assert post_incident(auth_client, link_to=[far]).status_code == 422
    assert post_incident(auth_client, link_to=[other]).status_code == 422
    assert len(_files(uploads)) == before


def test_max_three_links(auth_client, post_incident, session):
    candidates = [
        post_incident(auth_client, lat=13.0, lng=80.0).json()["id"]
        for _ in range(4)
    ]
    response = post_incident(auth_client, link_to=candidates[:3])
    assert response.status_code == 201
    assert len(response.json()["linked_incident_ids"]) == 3
    assert post_incident(auth_client, link_to=candidates[:4]).status_code == 422
