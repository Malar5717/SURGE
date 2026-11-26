"""Single source of truth for incident categories."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Category:
    slug: str
    label: str
    group: str
    radius_m: float
    sensitive: bool = False


CATEGORIES = (
    # Tier A: postable now.
    Category("pothole", "Pothole", "roads", 20),
    Category("road_damage", "Road damage", "roads", 30),
    Category(
        "footpath_encroachment", "Footpath blocked or encroached", "roads", 30
    ),
    Category("bad_parking", "Illegal parking", "roads", 20),
    Category("abandoned_vehicle", "Abandoned vehicle", "roads", 20),
    Category("signal_signage", "Broken signal or signage", "roads", 20),
    Category("open_manhole_pit", "Open manhole or pit", "roads", 20),
    Category("waterlogging", "Waterlogging", "water", 100),
    Category("sewage_overflow", "Sewage overflow", "water", 40),
    Category("blocked_drain", "Blocked drain", "water", 30),
    Category("water_leak", "Water leak", "water", 30),
    Category("streetlight", "Streetlight not working", "power", 20),
    Category("electrical_hazard", "Fallen wire or electrical hazard", "power", 20),
    Category("garbage", "Garbage", "waste", 40),
    Category("illegal_dumping", "Illegal dumping", "waste", 40),
    Category("burning_waste", "Burning waste", "waste", 50),
    Category("fallen_tree", "Fallen tree", "waste", 40),
    Category("stray_animals", "Stray animals", "animals", 50),
    Category("dead_animal", "Dead animal", "animals", 20),
    Category("unsafe_construction", "Unsafe or illegal construction", "buildings", 30),
    Category("public_property_damage", "Damaged public property", "buildings", 30),
    Category("other", "Other", "other", 30),
    # Tier B: sensitive, not postable while SENSITIVE_ENABLED is false.
    Category(
        "drug_or_liquor_sale", "Drug or illicit liquor sale", "community_safety", 60, True
    ),
    Category("gambling", "Gambling", "community_safety", 60, True),
    Category(
        "harassment_hotspot",
        "Harassment hotspot or unsafe area",
        "community_safety",
        100,
        True,
    ),
)

CATEGORY_BY_SLUG = {category.slug: category for category in CATEGORIES}

GROUPS = (
    "roads",
    "water",
    "power",
    "waste",
    "animals",
    "buildings",
    "other",
    "community_safety",
)


def radius_for(slug: str) -> float:
    """Return the match radius in metres for a category slug."""
    return CATEGORY_BY_SLUG[slug].radius_m
