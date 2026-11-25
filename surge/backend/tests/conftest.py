import os
from pathlib import Path

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
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
def session():
    """A session that is rolled back after the test."""
    with SessionLocal() as db:
        yield db
        db.rollback()
