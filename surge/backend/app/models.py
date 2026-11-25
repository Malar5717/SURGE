from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Index,
    String,
    Text,
    false,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

CATEGORIES = ("pothole", "streetlight", "fallen_tree", "garbage", "waterlogging", "other")
EVENT_TYPES = ("reported", "note")
AUTH_EVENT_TYPES = ("signup", "login_ok", "login_fail", "logout")

_CATEGORY_IN = "category IN (" + ", ".join(repr(c) for c in CATEGORIES) + ")"
_TYPE_IN = "type IN (" + ", ".join(repr(t) for t in EVENT_TYPES) + ")"
_AUTH_EVENT_IN = "event IN (" + ", ".join(repr(e) for e in AUTH_EVENT_TYPES) + ")"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    handle: Mapped[str] = mapped_column(String(20), nullable=False)
    handle_lower: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_banned: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=false()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AuthSession(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class AuthEvent(Base):
    __tablename__ = "auth_events"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    handle_tried: Mapped[str | None] = mapped_column(String(20))
    event: Mapped[str] = mapped_column(String(16), nullable=False)
    ip: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(_AUTH_EVENT_IN, name="ck_auth_events_event"),
        Index("ix_auth_events_ip_event_created", "ip", "event", "created_at"),
        Index(
            "ix_auth_events_handle_event_created",
            "handle_tried",
            "event",
            "created_at",
        ),
    )


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    accuracy_m: Mapped[float | None] = mapped_column(Float)
    description: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    events: Mapped[list["Event"]] = relationship(
        back_populates="incident", order_by="Event.created_at", cascade="all, delete-orphan"
    )
    creator: Mapped[User | None] = relationship(lazy="joined")

    @property
    def created_by_handle(self) -> str | None:
        return self.creator.handle if self.creator else None

    __table_args__ = (
        CheckConstraint(_CATEGORY_IN, name="ck_incidents_category"),
        CheckConstraint("lat BETWEEN -90 AND 90", name="ck_incidents_lat"),
        CheckConstraint("lng BETWEEN -180 AND 180", name="ck_incidents_lng"),
        Index("ix_incidents_category_lat_lng", "category", "lat", "lng"),
    )


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    incident_id: Mapped[int] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    incident: Mapped[Incident] = relationship(back_populates="events")
    creator: Mapped[User | None] = relationship(lazy="joined")

    @property
    def created_by_handle(self) -> str | None:
        return self.creator.handle if self.creator else None

    __table_args__ = (CheckConstraint(_TYPE_IN, name="ck_events_type"),)


class IncidentLink(Base):
    __tablename__ = "incident_links"

    incident_a: Mapped[int] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), primary_key=True
    )
    incident_b: Mapped[int] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), primary_key=True
    )
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    creator: Mapped[User | None] = relationship(lazy="joined")

    @property
    def created_by_handle(self) -> str | None:
        return self.creator.handle if self.creator else None

    __table_args__ = (CheckConstraint("incident_a < incident_b", name="ck_links_order"),)
