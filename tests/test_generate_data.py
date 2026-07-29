"""Tests for the synthetic data generator."""
from src import config, generate_data

TAIPEI_BBOX = {"lat": (24.85, 25.25), "lon": (121.25, 121.75)}


def test_generate_count_and_ids():
    rows = generate_data.generate(50)
    assert len(rows) == 50
    assert [r["id"] for r in rows] == list(range(1, 51))


def test_generate_is_deterministic():
    a = generate_data.generate(30, seed=42)
    b = generate_data.generate(30, seed=42)
    assert a == b
    c = generate_data.generate(30, seed=7)
    assert a != c  # different seed -> different data


def test_row_invariants():
    for r in generate_data.generate(120):
        assert r["price"] >= 9000
        assert r["size_ping"] > 0
        assert r["room_type"] in config.ROOM_TYPES
        assert r["city"] in config.CITIES
        assert r["district"] in config.DISTRICT_PROFILE
        assert TAIPEI_BBOX["lat"][0] < r["lat"] < TAIPEI_BBOX["lat"][1]
        assert TAIPEI_BBOX["lon"][0] < r["lon"] < TAIPEI_BBOX["lon"][1]
        assert r["mrt_min"] >= 1
        assert r["has_elevator"] in (0, 1)
        assert r["pet_allowed"] in (0, 1)


def test_price_band_matches_price():
    for r in generate_data.generate(120):
        assert r["price_band"] == config.price_band(r["price"])


def test_no_real_address_leakage():
    # Synthetic addresses must not contain the private district-in-Chinese +
    # real street markers from the reference data (sanity guard).
    for r in generate_data.generate(60):
        assert "號" not in r["address"]  # real seed used Chinese house numbers
        assert r["phone"].startswith("09")


def test_new_fields_present_and_valid():
    for r in generate_data.generate(200):
        assert r["status"] in ("Available", "Rented")
        assert 5.0 <= r["owner_contract_years_left"] <= 12.0
        assert r["features"] and "|" in r["features"] or r["features"]


def test_occupancy_rate_about_80pct():
    rows = generate_data.generate(1000)
    rented = sum(r["status"] == "Rented" for r in rows)
    assert 0.74 < rented / len(rows) < 0.86  # ~80% occupancy


def test_build_database(tmp_path):
    db = tmp_path / "t.db"
    n = generate_data.build_database(n=40, db_path=db)
    assert n == 40
    assert db.exists()
