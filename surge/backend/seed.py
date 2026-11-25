"""Reset the main database and load sample incidents around Chennai."""

from sqlalchemy import text

from app.db import Base, SessionLocal, engine
from app.models import Event, Incident, IncidentLink

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
    ("Anna Nagar", "pothole", "Pothole filled with rainwater"),
    ("Anna Nagar", "garbage", "Overflowing bin outside the market"),
    ("Anna Nagar", "waterlogging", "Water knee-deep after last night's rain"),
    ("T. Nagar", "pothole", "Pothole at the junction"),
    ("T. Nagar", "fallen_tree", "Branch blocking the footpath"),
    ("T. Nagar", "garbage", "Waste dumped on the pavement"),
    ("T. Nagar", "streetlight", "Streetlight out for three nights"),
    ("Adyar", "fallen_tree", "Tree leaning over the road"),
    ("Adyar", "pothole", "Broken road near the school"),
    ("Adyar", "waterlogging", "Drain overflow by the park"),
    ("Adyar", "garbage", "Rubbish piled beside the canal"),
    ("Mylapore", "streetlight", "Dark stretch near the temple"),
    ("Mylapore", "pothole", "Pothole on the narrow lane"),
    ("Mylapore", "garbage", "Bin not cleared for two days"),
    ("Velachery", "waterlogging", "Underpass floods every evening"),
    ("Velachery", "pothole", "Pothole opposite the mall"),
    ("Velachery", "garbage", "Construction debris on the road"),
    ("Tambaram", "pothole", "Pothole by the railway station"),
    ("Tambaram", "fallen_tree", "Fallen branch after the storm"),
    ("Porur", "streetlight", "Two lights off on the main road"),
    ("Porur", "garbage", "Waste near the bus depot"),
    ("Kodambakkam", "pothole", "Pothole outside the cinema"),
    ("Kodambakkam", "waterlogging", "Stagnant water for days"),
    ("Egmore", "garbage", "Litter around the station entrance"),
    ("Egmore", "other", "Broken footpath slab"),
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


def main():
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as session:
        session.execute(
            text(
                "TRUNCATE events, incident_links, incidents RESTART IDENTITY CASCADE"
            )
        )

        incidents = []
        for i, (area, category, description) in enumerate(SEED):
            base_lat, base_lng = AREAS[area]
            lat = base_lat + ((i % 5) - 2) * 0.00005
            lng = base_lng + ((i % 7) - 3) * 0.00005
            incident = Incident(
                category=category, lat=lat, lng=lng, description=description
            )
            incident.events.append(Event(type="reported"))
            session.add(incident)
            incidents.append(incident)
        session.flush()

        for index, note in NOTES:
            session.add(
                Event(incident_id=incidents[index].id, type="note", note=note)
            )

        links = 0
        for group in CLUSTERS:
            for left, right in zip(group, group[1:]):
                a, b = sorted((incidents[left].id, incidents[right].id))
                session.add(IncidentLink(incident_a=a, incident_b=b))
                links += 1

        session.commit()

    print(
        f"Seeded {len(incidents)} incidents, {len(NOTES)} notes and {links} links."
    )


if __name__ == "__main__":
    main()
