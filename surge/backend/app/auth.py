import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .db import get_session
from .models import AuthEvent, AuthSession, User
from .security import hash_password, hash_token, new_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE_NAME = "surge_session"
SESSION_DAYS = 30

SIGNUP_LIMIT = 5
SIGNUP_WINDOW = timedelta(hours=1)
LOGIN_HANDLE_LIMIT = 5
LOGIN_IP_LIMIT = 20
LOGIN_WINDOW = timedelta(minutes=15)

_LOGIN_ERROR = "wrong handle or password"
_DUMMY_HASH = hash_password("dummy-password-for-timing")


class Credentials(BaseModel):
    handle: str = Field(min_length=3, max_length=20, pattern=r"^[A-Za-z0-9_]+$")
    password: str = Field(min_length=8, max_length=128)


def _cookie_secure() -> bool:
    return os.environ.get("COOKIE_SECURE", "false").strip().lower() == "true"


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _count_events(
    session: Session,
    event: str,
    since: datetime,
    *,
    ip: str | None = None,
    handle: str | None = None,
) -> int:
    """Count an event type in the window, optionally by IP or handle."""
    stmt = (
        select(func.count())
        .select_from(AuthEvent)
        .where(AuthEvent.event == event, AuthEvent.created_at >= since)
    )
    if ip is not None:
        stmt = stmt.where(AuthEvent.ip == ip)
    if handle is not None:
        stmt = stmt.where(AuthEvent.handle_tried == handle)
    return session.scalar(stmt)


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=SESSION_DAYS * 24 * 60 * 60,
        httponly=True,
        samesite="lax",
        path="/",
        secure=_cookie_secure(),
    )


def _create_session(session: Session, user: User) -> str:
    """Create a session row and return the raw token."""
    token = new_token()
    session.add(
        AuthSession(
            user_id=user.id,
            token_hash=hash_token(token),
            expires_at=datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS),
        )
    )
    session.commit()
    return token


def current_user(
    request: Request, session: Session = Depends(get_session)
) -> User:
    """Return the logged-in user or raise 401."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="not logged in")

    record = session.scalar(
        select(AuthSession).where(AuthSession.token_hash == hash_token(token))
    )
    if record is None or record.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="not logged in")

    user = session.get(User, record.user_id)
    if user is None or user.is_banned:
        raise HTTPException(status_code=401, detail="not logged in")
    return user


@router.post("/signup", status_code=201)
def signup(
    payload: Credentials,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
):
    """Create a user and log them in."""
    ip = _client_ip(request)
    since = datetime.now(timezone.utc) - SIGNUP_WINDOW
    if _count_events(session, "signup", since, ip=ip) >= SIGNUP_LIMIT:
        raise HTTPException(status_code=429, detail="too many signups")

    handle_lower = payload.handle.lower()
    if session.scalar(select(User.id).where(User.handle_lower == handle_lower)):
        raise HTTPException(status_code=409, detail="handle already taken")

    user = User(
        handle=payload.handle,
        handle_lower=handle_lower,
        password_hash=hash_password(payload.password),
    )
    session.add(user)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="handle already taken")

    session.add(
        AuthEvent(
            event="signup", ip=ip, handle_tried=handle_lower, user_id=user.id
        )
    )
    token = _create_session(session, user)
    _set_session_cookie(response, token)
    return {"handle": user.handle}


@router.post("/login")
def login(
    payload: Credentials,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
):
    """Log in with a handle and password."""
    ip = _client_ip(request)
    handle_lower = payload.handle.lower()
    since = datetime.now(timezone.utc) - LOGIN_WINDOW

    too_many = _count_events(
        session, "login_fail", since, handle=handle_lower
    ) >= LOGIN_HANDLE_LIMIT or _count_events(
        session, "login_fail", since, ip=ip
    ) >= LOGIN_IP_LIMIT
    if too_many:
        raise HTTPException(status_code=429, detail="too many login attempts")

    user = session.scalar(select(User).where(User.handle_lower == handle_lower))
    password_hash = user.password_hash if user else _DUMMY_HASH

    if (
        not verify_password(password_hash, payload.password)
        or user is None
        or user.is_banned
    ):
        session.add(
            AuthEvent(
                event="login_fail",
                ip=ip,
                handle_tried=handle_lower,
                user_id=user.id if user else None,
            )
        )
        session.commit()
        raise HTTPException(status_code=401, detail=_LOGIN_ERROR)

    session.add(
        AuthEvent(event="login_ok", ip=ip, handle_tried=handle_lower, user_id=user.id)
    )
    token = _create_session(session, user)
    _set_session_cookie(response, token)
    return {"handle": user.handle}


@router.post("/logout", status_code=204)
def logout(
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
):
    """Delete the current session and clear the cookie."""
    ip = _client_ip(request)
    token = request.cookies.get(COOKIE_NAME)
    if token:
        record = session.scalar(
            select(AuthSession).where(AuthSession.token_hash == hash_token(token))
        )
        if record is not None:
            session.add(AuthEvent(event="logout", ip=ip, user_id=record.user_id))
            session.delete(record)
            session.commit()
    response.delete_cookie(COOKIE_NAME, path="/")


@router.get("/me")
def me(user: User = Depends(current_user)):
    """Return the current user's handle."""
    return {"handle": user.handle}
