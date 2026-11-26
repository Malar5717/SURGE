import os
import random
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import text

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Tests always use the separate test database.
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]

from app import models  # noqa: E402,F401  (registers tables)
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def schema():
    """Create the tables in the test database, then drop them."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def clean_tables():
    """Empty the tables before each test."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE auth_events, sessions, events, incident_links, "
                "incidents, users RESTART IDENTITY CASCADE"
            )
        )
    yield


@pytest.fixture(autouse=True)
def uploads(tmp_path, monkeypatch):
    """Point photo storage at a fresh folder for each test."""
    folder = tmp_path / "uploads"
    monkeypatch.setattr("app.main.UPLOAD_DIR", folder)
    yield folder


@pytest.fixture
def client():
    """A test client that runs the app lifespan."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_client(client):
    """A client already logged in as the default test user."""
    response = client.post(
        "/auth/signup", json={"handle": "tester", "password": "password123"}
    )
    assert response.status_code == 201
    return client


@pytest.fixture
def make_jpeg():
    """Build a JPEG whose low-frequency pattern is random per seed."""

    def build(seed=0, size=(3200, 2000), exif=None):
        rng = random.Random(seed)
        cells = bytes(rng.randrange(256) for _ in range(9 * 8))
        small = Image.frombytes("L", (9, 8), cells)
        image = small.resize(size, Image.NEAREST).convert("RGB")
        buffer = BytesIO()
        options = {"exif": exif} if exif is not None else {}
        image.save(buffer, "JPEG", **options)
        return buffer.getvalue()

    return build


@pytest.fixture
def post_incident(make_jpeg):
    """POST a multipart incident with a fresh, distinct photo unless one is given."""
    counter = [0]

    def post(
        client,
        *,
        category="pothole",
        lat=13.0,
        lng=80.0,
        accuracy_m=10.0,
        description=None,
        captured_at=None,
        link_to=None,
        photo=None,
        filename="photo.jpg",
    ):
        data = {
            "category": category,
            "lat": str(lat),
            "lng": str(lng),
            "accuracy_m": str(accuracy_m),
            "captured_at": (
                captured_at
                if captured_at is not None
                else datetime.now(timezone.utc).isoformat()
            ),
        }
        if description is not None:
            data["description"] = description
        if link_to:
            data["link_to"] = [str(target) for target in link_to]

        if photo is None:
            photo = make_jpeg(seed=counter[0])
            counter[0] += 1
        files = {"photo": (filename, photo, "image/jpeg")}
        return client.post("/incidents", data=data, files=files)

    return post


@pytest.fixture
def session():
    """A session that is rolled back after the test."""
    with SessionLocal() as db:
        yield db
        db.rollback()
