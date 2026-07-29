"""Tests for the SQLite data-access layer (built against a temp DB)."""
import pytest

from src import database, generate_data


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    path = tmp_path_factory.mktemp("data") / "listings.db"
    generate_data.build_database(n=200, seed=42, db_path=path)
    return path


def test_query_all(db):
    df = database.query_listings(db_path=db)
    assert len(df) == 200
    # ordered by price ascending
    assert list(df["price"]) == sorted(df["price"])


def test_filter_by_city(db):
    df = database.query_listings(cities=["Taipei City"], db_path=db)
    assert (df["city"] == "Taipei City").all()
    assert len(df) > 0


def test_filter_by_district(db):
    df = database.query_listings(districts=["Da'an", "Xinyi"], db_path=db)
    assert set(df["district"]) <= {"Da'an", "Xinyi"}


def test_filter_by_price_range(db):
    df = database.query_listings(price_range=(15000, 25000), db_path=db)
    assert df["price"].between(15000, 25000).all()


def test_filter_by_room_type(db):
    df = database.query_listings(room_types=["Studio"], db_path=db)
    assert (df["room_type"] == "Studio").all()


def test_filter_by_size(db):
    df = database.query_listings(size_range=(20.0, 30.0), db_path=db)
    assert df["size_ping"].between(20.0, 30.0).all()


def test_filter_by_mrt(db):
    df = database.query_listings(max_mrt_min=5, db_path=db)
    assert (df["mrt_min"] <= 5).all()


def test_filter_by_status(db):
    df = database.query_listings(statuses=["Available"], db_path=db)
    assert (df["status"] == "Available").all()
    assert len(df) > 0


def test_combined_filters(db):
    df = database.query_listings(
        cities=["Taipei City"], room_types=["2BR", "3BR"],
        price_range=(10000, 40000), db_path=db,
    )
    if len(df):
        assert (df["city"] == "Taipei City").all()
        assert set(df["room_type"]) <= {"2BR", "3BR"}
        assert df["price"].between(10000, 40000).all()


def test_bounds(db):
    lo, hi = database.price_bounds(db_path=db)
    assert lo < hi
    slo, shi = database.size_bounds(db_path=db)
    assert slo < shi


def test_get_listing(db):
    df = database.query_listings(db_path=db)
    first_id = int(df.iloc[0]["id"])
    row = database.get_listing(first_id, db_path=db)
    assert row["id"] == first_id
    assert database.get_listing(999999, db_path=db) is None
