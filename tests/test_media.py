"""Tests for the photo helper module."""
from src import config, media


def test_photo_number_in_range_and_deterministic():
    for room in config.ROOM_TYPES:
        for lid in range(1, 50):
            n = media.photo_number(lid, room)
            assert 1 <= n <= 12
            assert media.photo_number(lid, room) == n  # deterministic


def test_available_photos_present():
    photos = media.available_photos()
    # Repo ships a set of interior photos; allow for local variation but expect some.
    assert len(photos) >= 1
    assert all(p.startswith("interior_") for p in photos)


def test_photo_data_uri_format():
    uri = media.photo_data_uri(1)
    assert uri.startswith("data:image/")


def test_photo_css_wraps_style():
    css = media.photo_css()
    assert css.startswith("<style>")
    assert ".listing-photo-" in css
