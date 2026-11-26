from sqlalchemy import select

from app.categories import CATEGORIES, CATEGORY_BY_SLUG, GROUPS, radius_for
from app.models import Incident

OLD_RADII = {
    "pothole": 20,
    "streetlight": 20,
    "waterlogging": 100,
    "fallen_tree": 40,
    "garbage": 40,
    "other": 30,
}


def test_every_category_has_radius_group_and_label():
    for category in CATEGORIES:
        assert category.radius_m > 0
        assert category.group in GROUPS
        assert category.label.strip()
        assert category.slug == category.slug.lower()


def test_slugs_are_unique():
    slugs = [category.slug for category in CATEGORIES]
    assert len(slugs) == len(set(slugs))
    assert len(CATEGORY_BY_SLUG) == len(CATEGORIES)


def test_old_slugs_keep_their_radii():
    for slug, radius in OLD_RADII.items():
        assert radius_for(slug) == radius


def test_categories_endpoint_returns_every_category(client):
    body = client.get("/categories").json()
    assert len(body) == len(CATEGORIES)

    by_slug = {category["slug"]: category for category in body}
    for category in CATEGORIES:
        row = by_slug[category.slug]
        assert row["label"] == category.label
        assert row["group"] == category.group
        assert row["sensitive"] == category.sensitive
        assert row["postable"] == (not category.sensitive)
        assert row["radius_m"] == category.radius_m


def test_sensitive_categories_are_listed_but_not_postable(client):
    by_slug = {category["slug"]: category for category in client.get("/categories").json()}

    assert by_slug["gambling"]["sensitive"] is True
    assert by_slug["gambling"]["postable"] is False
    assert by_slug["pothole"]["sensitive"] is False
    assert by_slug["pothole"]["postable"] is True


def test_sensitive_slug_cannot_be_posted(auth_client, post_incident, session):
    response = post_incident(auth_client, category="gambling")
    assert response.status_code == 403
    assert session.scalars(select(Incident)).all() == []


def test_candidates_reject_unknown_slug(client):
    response = client.get(
        "/incidents/candidates",
        params={"category": "banana", "lat": 13.0, "lng": 80.0},
    )
    assert response.status_code == 422
