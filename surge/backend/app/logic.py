import math
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Event, Incident, IncidentLink

# Match radius per category in metres (starting guesses).
RADIUS_M = {
    "pothole": 20.0,
    "streetlight": 20.0,
    "fallen_tree": 40.0,
    "garbage": 40.0,
    "waterlogging": 100.0,
    "other": 30.0,
}

RECENT_DAYS = 21
MAX_CANDIDATES = 3

EARTH_RADIUS_M = 6_371_000.0
_METRES_PER_DEGREE = 111_000.0  # slightly generous, only used for the prefilter


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two points in metres."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = phi2 - phi1
    dlambda = math.radians(lng2 - lng1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def match_radius_m(category: str, accuracy_m: float | None) -> float:
    """Category radius plus accuracy, capped at twice the radius."""
    radius = RADIUS_M[category]
    if accuracy_m is None:
        return radius
    return min(radius + accuracy_m, 2 * radius)


def _bounding_box(lat: float, lng: float, radius_m: float):
    lat_delta = radius_m / _METRES_PER_DEGREE
    cos_lat = max(math.cos(math.radians(lat)), 1e-6)
    lng_delta = radius_m / (_METRES_PER_DEGREE * cos_lat)
    return lat - lat_delta, lat + lat_delta, lng - lng_delta, lng + lng_delta


def find_candidates(
    session: Session,
    category: str,
    lat: float,
    lng: float,
    accuracy_m: float | None = None,
) -> list[tuple[float, Incident]]:
    """Return up to three nearby same-category incidents, nearest first."""
    radius = match_radius_m(category, accuracy_m)
    min_lat, max_lat, min_lng, max_lng = _bounding_box(lat, lng, radius)
    cutoff = datetime.now(timezone.utc) - timedelta(days=RECENT_DAYS)

    stmt = select(Incident).where(
        Incident.category == category,
        Incident.lat >= min_lat,
        Incident.lat <= max_lat,
        Incident.lng >= min_lng,
        Incident.lng <= max_lng,
        Incident.events.any(Event.created_at >= cutoff),
    )

    found = []
    for incident in session.scalars(stmt):
        distance = haversine_m(lat, lng, incident.lat, incident.lng)
        if distance <= radius:
            found.append((distance, incident))

    found.sort(key=lambda pair: pair[0])
    return found[:MAX_CANDIDATES]


def linked_ids(session: Session, incident_id: int) -> list[int]:
    """Return the ids directly linked to an incident, sorted."""
    rows = session.execute(
        select(IncidentLink.incident_a, IncidentLink.incident_b).where(
            (IncidentLink.incident_a == incident_id)
            | (IncidentLink.incident_b == incident_id)
        )
    )
    return sorted(b if a == incident_id else a for a, b in rows)


def group_of(session: Session, incident_id: int) -> set[int]:
    """Return every incident id reachable from this one through links."""
    seen = {incident_id}
    queue = [incident_id]
    while queue:
        node = queue.pop()
        for a, b in session.execute(
            select(IncidentLink.incident_a, IncidentLink.incident_b).where(
                (IncidentLink.incident_a == node) | (IncidentLink.incident_b == node)
            )
        ):
            for neighbour in (a, b):
                if neighbour not in seen:
                    seen.add(neighbour)
                    queue.append(neighbour)
    return seen

