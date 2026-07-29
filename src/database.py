"""
Thin data-access layer over the SQLite listings database.

Queries are parameterised (no string interpolation of user input) and results
are returned as pandas DataFrames for easy consumption by the Streamlit UI.
"""

import sqlite3
import pandas as pd

try:
    from src import config
except ImportError:  # pragma: no cover - direct execution fallback
    import config


def _connect(db_path=None) -> sqlite3.Connection:
    db_path = db_path or config.DB_PATH
    if not db_path.exists():
        raise FileNotFoundError(
            f"Database not found at {db_path}. Run `python -m src.generate_data` first."
        )
    return sqlite3.connect(db_path)


def price_bounds(db_path=None) -> tuple:
    with _connect(db_path) as conn:
        lo, hi = conn.execute("SELECT MIN(price), MAX(price) FROM listings").fetchone()
    return int(lo), int(hi)


def size_bounds(db_path=None) -> tuple:
    with _connect(db_path) as conn:
        lo, hi = conn.execute("SELECT MIN(size_ping), MAX(size_ping) FROM listings").fetchone()
    return float(lo), float(hi)


def query_listings(
    cities=None,
    districts=None,
    price_range=None,
    room_types=None,
    size_range=None,
    max_mrt_min=None,
    statuses=None,
    db_path=None,
) -> pd.DataFrame:
    """Return listings matching the given filters, ordered by price ascending.

    All filters are optional; None / empty means "no constraint".
    """
    clauses, params = [], []

    if cities:
        clauses.append(f"city IN ({','.join('?' for _ in cities)})")
        params.extend(cities)
    if districts:
        clauses.append(f"district IN ({','.join('?' for _ in districts)})")
        params.extend(districts)
    if price_range:
        clauses.append("price BETWEEN ? AND ?")
        params.extend([price_range[0], price_range[1]])
    if room_types:
        clauses.append(f"room_type IN ({','.join('?' for _ in room_types)})")
        params.extend(room_types)
    if size_range:
        clauses.append("size_ping BETWEEN ? AND ?")
        params.extend([size_range[0], size_range[1]])
    if max_mrt_min is not None:
        clauses.append("mrt_min <= ?")
        params.append(max_mrt_min)
    if statuses:
        clauses.append(f"status IN ({','.join('?' for _ in statuses)})")
        params.extend(statuses)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"SELECT * FROM listings {where} ORDER BY price ASC"

    with _connect(db_path) as conn:
        return pd.read_sql_query(sql, conn, params=params)


def get_listing(listing_id: int, db_path=None) -> dict:
    with _connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM listings WHERE id = ?", (listing_id,)).fetchone()
    return dict(row) if row else None
