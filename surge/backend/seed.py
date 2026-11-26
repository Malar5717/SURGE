"""Reset the main database and load sample incidents around Chennai."""

import shutil
from datetime import datetime, timedelta, timezone
from io import BytesIO

from PIL import Image, ImageDraw

from app.db import Base, SessionLocal, UPLOAD_DIR, engine
from app.models import Event, Incident, IncidentLink, User
from app.photos import process_photo
from app.security import hash_password

DEMO_USERS = ("asha", "ravi", "meena")
DEMO_PASSWORD = "surge-demo-password"

AREAS = {
    "Anna Nagar": (13.0850, 80.2101),
    "T. Nagar": (13.0418, 80.2341),
    "Adyar": (13.0067, 80.2570),
    "Mylapore": (13.0339, 80.2699),
    "Velachery": (12.9791, 80.2210),
    "Tambaram": (12.9249, 80.1000),
    "Porur": (13.0358, 80.1560),
    "Kodambakkam": (13.0500, 80.2200),
    "Egmore": (13.0790, 80.2600),
    "Besant Nagar": (13.0000, 80.2700),
}

# (area, category, description)
SEED = [
    ("Anna Nagar", "pothole", "Deep pothole near the bus stop"),
    ("Anna Nagar", "pothole", "Second pothole on the same stretch"),
    ("Anna Nagar", "road_damage", "Sunken road holding rainwater"),
    ("Anna Nagar", "garbage", "Overflowing bin outside the market"),
    ("Anna Nagar", "waterlogging", "Water knee-deep after last night's rain"),
    ("T. Nagar", "pothole", "Pothole at the junction"),
    ("T. Nagar", "fallen_tree", "Branch blocking the footpath"),
    ("T. Nagar", "illegal_dumping", "Waste dumped on the pavement"),
    ("T. Nagar", "streetlight", "Streetlight out for three nights"),
    ("Adyar", "fallen_tree", "Tree leaning over the road"),
    ("Adyar", "road_damage", "Broken road near the school"),
    ("Adyar", "waterlogging", "Drain overflow by the park"),
    ("Adyar", "illegal_dumping", "Rubbish piled beside the canal"),
    ("Mylapore", "streetlight", "Dark stretch near the temple"),
    ("Mylapore", "pothole", "Pothole on the narrow lane"),
    ("Mylapore", "garbage", "Bin not cleared for two days"),
    ("Velachery", "waterlogging", "Underpass floods every evening"),
    ("Velachery", "pothole", "Pothole opposite the mall"),
    ("Velachery", "illegal_dumping", "Construction debris on the road"),
    ("Tambaram", "pothole", "Pothole by the railway station"),
    ("Tambaram", "fallen_tree", "Fallen branch after the storm"),
    ("Porur", "streetlight", "Two lights off on the main road"),
    ("Porur", "illegal_dumping", "Waste near the bus depot"),
    ("Kodambakkam", "pothole", "Pothole outside the cinema"),
    ("Kodambakkam", "waterlogging", "Stagnant water for days"),
    ("Egmore", "garbage", "Litter around the station entrance"),
    ("Egmore", "public_property_damage", "Broken footpath slab"),
    ("Besant Nagar", "fallen_tree", "Tree down on the beach road"),
    ("Besant Nagar", "pothole", "Pothole near the beach car park"),
    ("Besant Nagar", "waterlogging", "Water pooling at the corner"),
]

# (index in SEED, note)
NOTES = [
    (0, "Two-wheeler damaged here yesterday"),
    (1, "Still not fixed after a week"),
    (7, "Picked up this morning, thanks"),
    (14, "Water collects here after every rain"),
    (26, "Dangerous for evening walkers"),
]

# Incidents linked into one group each.
CLUSTERS = [
    [0, 1, 2],
    [10, 11, 12],
    [16, 17],
]


def _placeholder(index: int) -> bytes:
    """Build a visibly different placeholder JPEG for one seeded incident."""
    width, height = 640, 480
    image = Image.new(
        "RGB",
        (width, height),
        (
            (index * 53) % 180 + 40,
            (index * 97) % 180 + 40,
            (index * 31) % 180 + 40,
        ),
    )
    draw = ImageDraw.Draw(image)
    for x in range(0, width, 60):
        draw.line((x, 0, width - x, height), fill=(20, 20, 20), width=9)
    left = (index * 37) % (width - 120)
    top = (index * 53) % (height - 90)
    draw.rectangle((left, top, left + 120, top + 90), fill=(250, 250, 250))
    buffer = BytesIO()
    image.save(buffer, "JPEG", quality=85)
    return buffer.getvalue()


def main():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    shutil.rmtree(UPLOAD_DIR, ignore_errors=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    with SessionLocal() as session:
        users = []
        for handle in DEMO_USERS:
            user = User(
                handle=handle,
                handle_lower=handle,
                password_hash=hash_password(DEMO_PASSWORD),
            )
            session.add(user)
            users.append(user)
        session.flush()

        incidents = []
        now = datetime.now(timezone.utc)
        for i, (area, category, description) in enumerate(SEED):
            base_lat, base_lng = AREAS[area]
            lat = base_lat + ((i % 5) - 2) * 0.00005
            lng = base_lng + ((i % 7) - 3) * 0.00005
            creator = users[i % len(users)]
            photo = process_photo(_placeholder(i), UPLOAD_DIR)
            created = now - timedelta(days=(i % 10) + 1, hours=(i * 7) % 24)
            incident = Incident(
                category=category,
                lat=lat,
                lng=lng,
                description=description,
                created_by=creator.id,
                created_at=created,
            )
            incident.events.append(
                Event(
                    type="reported",
                    created_by=creator.id,
                    photo_file=photo.photo_file,
                    thumb_file=photo.thumb_file,
                    phash=photo.phash,
                    captured_at=created,
                    created_at=created,
                )
            )
            session.add(incident)
            incidents.append(incident)
        session.flush()

        for index, note in NOTES:
            session.add(
                Event(
                    incident_id=incidents[index].id,
                    type="note",
                    note=note,
                    created_by=users[(index + 1) % len(users)].id,
                    created_at=incidents[index].created_at + timedelta(hours=2),
                )
            )

        links = 0
        for group in CLUSTERS:
            for left, right in zip(group, group[1:]):
                a, b = sorted((incidents[left].id, incidents[right].id))
                session.add(
                    IncidentLink(
                        incident_a=a,
                        incident_b=b,
                        created_by=users[left % len(users)].id,
                    )
                )
                links += 1

        session.commit()

    print(
        f"Seeded {len(incidents)} incidents, {len(NOTES)} notes and {links} links."
    )
    print(
        "Demo logins: "
        + ", ".join(DEMO_USERS)
        + f" (password: {DEMO_PASSWORD})"
    )


if __name__ == "__main__":
    main()
