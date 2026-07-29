"""Tests for static configuration and helpers."""
from src import config

TAIPEI_BBOX = {"lat": (24.9, 25.2), "lon": (121.3, 121.7)}


def test_district_profile_shape():
    assert len(config.DISTRICT_PROFILE) == 14
    required = {"city", "name_zh", "lat", "lon", "lat_sd", "lon_sd", "unit_price", "mrt_km"}
    for name, d in config.DISTRICT_PROFILE.items():
        assert required <= set(d), f"{name} missing keys"
        assert d["city"] in config.CITIES
        assert TAIPEI_BBOX["lat"][0] < d["lat"] < TAIPEI_BBOX["lat"][1]
        assert TAIPEI_BBOX["lon"][0] < d["lon"] < TAIPEI_BBOX["lon"][1]
        assert d["unit_price"] > 0


def test_room_types_valid():
    for name, r in config.ROOM_TYPES.items():
        lo, hi = r["size"]
        assert 0 < lo < hi
        assert r["weight"] > 0
        assert r["up_mult"] > 0


def test_price_band_boundaries():
    assert config.price_band(0) == "Budget"
    assert config.price_band(19999) == "Budget"
    assert config.price_band(20000) == "Standard"
    assert config.price_band(31999) == "Standard"
    assert config.price_band(32000) == "Premium"
    assert config.price_band(999999) == "Premium"


def test_band_color_is_hex():
    for name, _, _, color in config.PRICE_BANDS:
        assert color.startswith("#") and len(color) == 7
        assert config.band_color(name) == color


def test_districts_helper_matches_profile():
    assert set(config.districts()) == set(config.DISTRICT_PROFILE)
