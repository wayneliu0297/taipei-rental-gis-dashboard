"""
Photo helpers for the property cards, map popups, and detail panel.

Interior photos live in ``assets/photos`` and are embedded as base64 data URIs
so they render everywhere — inside Streamlit markdown *and* inside the Folium
map iframe — with no external requests (works fully offline).

Photos are royalty-free interior shots (Unsplash license — free to use, no
attribution required). They are illustrative stock images, not pictures of any
real listing.
"""

import base64
from functools import lru_cache

try:
    from src import config
except ImportError:  # pragma: no cover
    import config

PHOTO_DIR = config.PROJECT_ROOT / "assets" / "photos"

# Loosely group photos so smaller units get bedroom/studio shots and larger
# units get living-room / lounge shots (purely cosmetic).
_BEDROOM_LIKE = [6, 7, 8, 10, 11]                 # cozy / bedroom / studio
_LIVING_LIKE = [1, 2, 3, 4, 5, 9, 12]             # living / dining / lounge
_ROOM_BUCKET = {
    "Studio": _BEDROOM_LIKE,
    "1BR": _BEDROOM_LIKE,
    "2BR": _LIVING_LIKE,
    "3BR": _LIVING_LIKE,
    "4BR+": _LIVING_LIKE,
}


def photo_number(listing_id: int, room_type: str = "2BR") -> int:
    """Deterministically pick a photo (1..12) for a listing."""
    bucket = _ROOM_BUCKET.get(room_type, _LIVING_LIKE)
    return bucket[listing_id % len(bucket)]


@lru_cache(maxsize=32)
def photo_data_uri(n: int) -> str:
    """Return a base64 data URI for photo number ``n`` (cached)."""
    path = PHOTO_DIR / f"interior_{n:02d}.jpg"
    if not path.exists():
        # 1x1 transparent gif fallback
        return "data:image/gif;base64,R0lGODlhAQABAAAAACwAAAAAAQABAAA="
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/jpeg;base64,{data}"


@lru_cache(maxsize=1)
def available_photos() -> tuple:
    if not PHOTO_DIR.exists():
        return tuple()
    return tuple(sorted(p.stem for p in PHOTO_DIR.glob("interior_*.jpg")))


def photo_css() -> str:
    """A <style> block mapping ``.listing-photo-N`` to each embedded photo.

    Injected once into the Streamlit page so cards can reference photos by class
    without repeating the (large) base64 payload per card.
    """
    rules = []
    for stem in available_photos():
        n = int(stem.split("_")[1])
        rules.append(
            f".listing-photo-{n}{{background-image:url('{photo_data_uri(n)}');}}"
        )
    return "<style>\n" + "\n".join(rules) + "\n</style>"
