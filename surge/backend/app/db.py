import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DATABASE_URL = os.environ["DATABASE_URL"]
TEST_DATABASE_URL = os.environ["TEST_DATABASE_URL"]
SENSITIVE_ENABLED = (
    os.environ.get("SENSITIVE_ENABLED", "false").strip().lower() == "true"
)
UPLOAD_DIR = Path(
    os.environ.get("UPLOAD_DIR", Path(__file__).resolve().parent.parent / "uploads")
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_session():
    """Yield a database session for one request."""
    with SessionLocal() as session:
        yield session
