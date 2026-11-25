from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, or_, select, text, true
from sqlalchemy.orm import Session, aliased

from . import models  # noqa: F401  (registers tables on Base.metadata)
from .auth import current_user, router as auth_router
from .db import Base, engine, get_session
from .models import CATEGORIES, Event, Incident, IncidentLink, User
from .logic import find_candidates, group_of, linked_ids

Category = Literal[*CATEGORIES]


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="SURGE API", version="0.1.0", lifespan=lifespan)
app.include_router(auth_router)


class IncidentCreate(BaseModel):
    category: Category
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    accuracy_m: float | None = None
    description: str | None = None


class IncidentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category: str
    lat: float
    lng: float
    accuracy_m: float | None
    description: str | None
    created_by_handle: str | None
    created_at: datetime


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    incident_id: int
    type: str
    note: str | None
    created_by_handle: str | None
    created_at: datetime


class IncidentDetail(IncidentOut):
    events: list[EventOut]
    linked_incident_ids: list[int]
    group_size: int


class CandidateOut(IncidentOut):
    distance_m: float


class LinkCreate(BaseModel):
    other_id: int


class LinkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    incident_a: int
    incident_b: int
    created_by_handle: str | None
    created_at: datetime


class LinkCoordsOut(BaseModel):
    incident_a: int
    incident_b: int
    a_lat: float
    a_lng: float
    b_lat: float
    b_lng: float


class EventCreate(BaseModel):
    type: Literal["note"]
    note: str


def _events_for(session: Session, incident_id: int) -> list[Event]:
    """Return an incident's events oldest first."""
    return list(
        session.scalars(
            select(Event)
            .where(Event.incident_id == incident_id)
            .order_by(Event.created_at, Event.id)
        )
    )


def _detail(session: Session, incident: Incident) -> IncidentDetail:
    return IncidentDetail(
        **IncidentOut.model_validate(incident).model_dump(),
        events=[EventOut.model_validate(e) for e in _events_for(session, incident.id)],
        linked_incident_ids=linked_ids(session, incident.id),
        group_size=len(group_of(session, incident.id)),
    )


def _get_incident(session: Session, incident_id: int) -> Incident:
    incident = session.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")
    return incident


@app.get("/health")
def health(session: Session = Depends(get_session)):
    """Return ok after a successful database round trip."""
    session.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}


@app.post("/incidents", response_model=IncidentDetail, status_code=201)
def create_incident(
    payload: IncidentCreate,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    """Store a new incident and its first reported event."""
    incident = Incident(**payload.model_dump(), created_by=user.id)
    incident.events.append(Event(type="reported", created_by=user.id))
    session.add(incident)
    session.commit()
    session.refresh(incident)
    return _detail(session, incident)


@app.get("/incidents", response_model=list[IncidentOut])
def list_incidents(
    session: Session = Depends(get_session),
    min_lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    max_lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    min_lng: Annotated[float | None, Query(ge=-180, le=180)] = None,
    max_lng: Annotated[float | None, Query(ge=-180, le=180)] = None,
):
    """List incidents, optionally limited to a lat/lng bounding box."""
    stmt = select(Incident)
    if min_lat is not None:
        stmt = stmt.where(Incident.lat >= min_lat)
    if max_lat is not None:
        stmt = stmt.where(Incident.lat <= max_lat)
    if min_lng is not None:
        stmt = stmt.where(Incident.lng >= min_lng)
    if max_lng is not None:
        stmt = stmt.where(Incident.lng <= max_lng)
    return list(session.scalars(stmt.order_by(Incident.id)))


@app.get("/incidents/candidates", response_model=list[CandidateOut])
def incident_candidates(
    category: Category,
    lat: Annotated[float, Query(ge=-90, le=90)],
    lng: Annotated[float, Query(ge=-180, le=180)],
    accuracy_m: float | None = None,
    session: Session = Depends(get_session),
):
    """Return up to three nearby incidents of the same category, nearest first."""
    return [
        CandidateOut(
            **IncidentOut.model_validate(incident).model_dump(),
            distance_m=round(distance, 1),
        )
        for distance, incident in find_candidates(
            session, category, lat, lng, accuracy_m
        )
    ]


@app.get("/incidents/{incident_id}", response_model=IncidentDetail)
def get_incident(incident_id: int, session: Session = Depends(get_session)):
    """Return one incident with its events, oldest first."""
    return _detail(session, _get_incident(session, incident_id))


@app.post(
    "/incidents/{incident_id}/events",
    response_model=EventOut,
    status_code=201,
)
def add_event(
    incident_id: int,
    payload: EventCreate,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    """Append a note event to an incident."""
    incident = _get_incident(session, incident_id)
    event = Event(
        incident_id=incident.id,
        type=payload.type,
        note=payload.note,
        created_by=user.id,
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


@app.post("/incidents/{incident_id}/links", response_model=LinkOut, status_code=201)
def create_link(
    incident_id: int,
    payload: LinkCreate,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    """Link this incident to another one."""
    incident = _get_incident(session, incident_id)
    if payload.other_id == incident_id:
        raise HTTPException(status_code=422, detail="an incident cannot link to itself")
    other = _get_incident(session, payload.other_id)

    a, b = sorted((incident.id, other.id))
    if session.get(IncidentLink, (a, b)) is not None:
        raise HTTPException(status_code=409, detail="link already exists")

    link = IncidentLink(incident_a=a, incident_b=b, created_by=user.id)
    session.add(link)
    session.commit()
    session.refresh(link)
    return link


@app.delete("/incidents/{incident_id}/links/{other_id}", status_code=204)
def delete_link(
    incident_id: int,
    other_id: int,
    user: User = Depends(current_user),
    session: Session = Depends(get_session),
):
    """Remove a link the current user created."""
    a, b = sorted((incident_id, other_id))
    link = session.get(IncidentLink, (a, b))
    if link is None:
        raise HTTPException(status_code=404, detail="link not found")
    if link.created_by != user.id:
        raise HTTPException(status_code=403, detail="only the creator can delete this link")
    session.delete(link)
    session.commit()


@app.get("/links", response_model=list[LinkCoordsOut])
def list_links(
    session: Session = Depends(get_session),
    min_lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    max_lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    min_lng: Annotated[float | None, Query(ge=-180, le=180)] = None,
    max_lng: Annotated[float | None, Query(ge=-180, le=180)] = None,
):
    """List links, keeping any with at least one end inside the box."""
    a = aliased(Incident)
    b = aliased(Incident)
    stmt = (
        select(
            IncidentLink.incident_a,
            IncidentLink.incident_b,
            a.lat,
            a.lng,
            b.lat,
            b.lng,
        )
        .join(a, a.id == IncidentLink.incident_a)
        .join(b, b.id == IncidentLink.incident_b)
        .order_by(IncidentLink.incident_a, IncidentLink.incident_b)
    )

    def inside(side):
        conditions = []
        if min_lat is not None:
            conditions.append(side.lat >= min_lat)
        if max_lat is not None:
            conditions.append(side.lat <= max_lat)
        if min_lng is not None:
            conditions.append(side.lng >= min_lng)
        if max_lng is not None:
            conditions.append(side.lng <= max_lng)
        return and_(*conditions) if conditions else true()

    if any(v is not None for v in (min_lat, max_lat, min_lng, max_lng)):
        stmt = stmt.where(or_(inside(a), inside(b)))

    return [
        LinkCoordsOut(
            incident_a=link_a,
            incident_b=link_b,
            a_lat=alat,
            a_lng=alng,
            b_lat=blat,
            b_lng=blng,
        )
        for link_a, link_b, alat, alng, blat, blng in session.execute(stmt)
    ]
