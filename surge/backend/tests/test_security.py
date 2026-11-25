import pytest
from sqlalchemy.exc import IntegrityError

from app.models import User
from app.security import hash_password, hash_token, new_token, verify_password


def test_hashed_password_verifies():
    hashed = hash_password("correct horse battery")
    assert verify_password(hashed, "correct horse battery")


def test_wrong_password_fails():
    hashed = hash_password("correct horse battery")
    assert verify_password(hashed, "wrong password") is False


def test_same_password_hashes_differently():
    assert hash_password("same-password") != hash_password("same-password")


def test_handle_lower_is_unique_ignoring_case(session):
    session.add(
        User(
            handle="Asha",
            handle_lower="asha",
            password_hash=hash_password("password123"),
        )
    )
    session.flush()

    session.add(
        User(
            handle="asha",
            handle_lower="asha",
            password_hash=hash_password("password123"),
        )
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_token_hash_is_deterministic_and_differs_from_token():
    token = new_token()
    digest = hash_token(token)

    assert digest != token
    assert digest == hash_token(token)
    assert len(digest) == 64
