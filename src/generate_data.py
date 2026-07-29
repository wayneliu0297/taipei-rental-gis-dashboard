"""
Generate synthetic Greater-Taipei rental listings and load them into SQLite.

Run:  python -m src.generate_data   (or  python src/generate_data.py)

Listings are fabricated with a fixed seed for reproducibility. Their *statistical
shape* (per-district rent-per-ping, sizes, MRT distances, amenity rates) is
calibrated to aggregate figures in ``config.DISTRICT_PROFILE`` so the demo looks
realistic — but no real address, price, contact, or record is reproduced.
"""

import random
import sqlite3
from datetime import date, timedelta

try:
    from src import config
except ImportError:  # pragma: no cover - direct execution fallback
    import config

SEED = 42
N_LISTINGS = 500

FIRST_NAMES = ["Chen", "Lin", "Huang", "Chang", "Lee", "Wang", "Wu", "Liu", "Tsai", "Yang", "Cheng", "Hsu"]


def _round_to(value: float, step: int = 500) -> int:
    return int(round(value / step) * step)


def _weighted_choice(rng, mapping, weight_key="weight"):
    keys = list(mapping.keys())
    weights = [mapping[k][weight_key] for k in keys]
    return rng.choices(keys, weights=weights, k=1)[0]


def _make_listing(idx: int, rng: random.Random) -> dict:
    district = rng.choice(config.districts())
    d = config.DISTRICT_PROFILE[district]

    room_type = rng.choices(
        list(config.ROOM_TYPES.keys()),
        weights=[config.ROOM_TYPES[r]["weight"] for r in config.ROOM_TYPES],
        k=1,
    )[0]
    r = config.ROOM_TYPES[room_type]

    size = round(rng.uniform(*r["size"]), 1)

    # Rent = district rent-per-ping * room multiplier * size * noise.
    # A modest floor keeps small-sample districts from producing implausibly
    # low rents while preserving the relative ordering from the seed data.
    base_unit = max(d["unit_price"], 820)
    unit_price = base_unit * r["up_mult"] * rng.uniform(0.92, 1.12)
    price = _round_to(unit_price * size)
    price = max(price, 9000)

    # Scatter around the district centroid
    lat = round(d["lat"] + rng.gauss(0, 1) * d["lat_sd"], 6)
    lon = round(d["lon"] + rng.gauss(0, 1) * d["lon_sd"], 6)

    building_type = _weighted_choice(rng, config.BUILDING_TYPES)
    has_elevator = rng.random() < config.BUILDING_TYPES[building_type]["elevator_p"]
    if building_type == "Townhouse":
        total_floors = rng.randint(3, 5)
    elif building_type == "Elevator building":
        total_floors = rng.randint(8, 22)
    else:  # walk-up
        total_floors = rng.randint(4, 6)
    floor = rng.randint(1, total_floors)

    # MRT distance around the district's typical value (km) -> walking minutes
    mrt_km = round(max(0.05, rng.gauss(d["mrt_km"], 0.28)), 2)
    mrt_min = max(1, round(mrt_km * config.WALK_MIN_PER_KM))

    renovation_age = min(int(abs(rng.gauss(0, 2.2))), 9)  # seed: mostly recently renovated

    street = rng.choice(config.STREET_NAMES)
    address = (
        f"No. {rng.randint(1, 180)}, Ln. {rng.randint(1, 300)}, {street}, "
        f"{district} Dist., {d['city']}"
    )

    features = rng.sample(config.FEATURE_POOL, k=rng.randint(2, 4))
    walk = f"{mrt_min} min walk to MRT"
    description = f"{room_type} · {size:g} ping in {district}. {walk}. " + ", ".join(features) + "."

    # Occupancy: ~80% of the managed units are currently rented.
    status = "Rented" if rng.random() < 0.80 else "Available"
    # Years left on the company's sub-lease contract with the property owner
    # (avg ~8, clamped to 5..12). Company-facing only.
    owner_contract_years_left = round(min(12.0, max(5.0, rng.gauss(8, 1.7))), 1)

    posted = date(2026, 7, 24) - timedelta(days=rng.randint(0, 75))

    return {
        "id": idx,
        "title": f"{room_type} in {district} · {size:g} ping",
        "city": d["city"],
        "district": district,
        "district_zh": d["name_zh"],
        "address": address,
        "lat": lat,
        "lon": lon,
        "price": price,
        "price_band": config.price_band(price),
        "unit_price": round(price / size),
        "room_type": room_type,
        "bedrooms": r["beds"],
        "bathrooms": r["baths"] + (1 if size > 32 and rng.random() < 0.5 else 0),
        "size_ping": size,
        "size_m2": round(size * 3.306, 1),
        "floor": floor,
        "total_floors": total_floors,
        "building_type": building_type,
        "renovation_age": renovation_age,
        "mrt_km": mrt_km,
        "mrt_min": mrt_min,
        "has_elevator": int(has_elevator),
        "has_parking": int(rng.random() < 0.3),
        "pet_allowed": int(rng.random() < 0.6),
        "subsidy_eligible": int(rng.random() < 0.8),
        "listing_type": "Whole unit" if room_type != "Studio" else "Studio suite",
        "status": status,
        "owner_contract_years_left": owner_contract_years_left,
        "features": "|".join(features),
        "landlord": f"Mr./Ms. {rng.choice(FIRST_NAMES)}",
        "phone": f"09{rng.randint(10, 89)}-{rng.randint(100, 999)}-{rng.randint(100, 999)}",
        "posted_date": posted.isoformat(),
        "description": description,
    }


SCHEMA = """
CREATE TABLE listings (
    id              INTEGER PRIMARY KEY,
    title           TEXT NOT NULL,
    city            TEXT NOT NULL,
    district        TEXT NOT NULL,
    district_zh     TEXT,
    address         TEXT,
    lat             REAL NOT NULL,
    lon             REAL NOT NULL,
    price           INTEGER NOT NULL,
    price_band      TEXT NOT NULL,
    unit_price      INTEGER,
    room_type       TEXT NOT NULL,
    bedrooms        INTEGER,
    bathrooms       INTEGER,
    size_ping       REAL NOT NULL,
    size_m2         REAL,
    floor           INTEGER,
    total_floors    INTEGER,
    building_type   TEXT,
    renovation_age  INTEGER,
    mrt_km          REAL,
    mrt_min         INTEGER,
    has_elevator    INTEGER,
    has_parking     INTEGER,
    pet_allowed     INTEGER,
    subsidy_eligible INTEGER,
    listing_type    TEXT,
    status          TEXT,
    owner_contract_years_left REAL,
    features        TEXT,
    landlord        TEXT,
    phone           TEXT,
    posted_date     TEXT,
    description     TEXT
);
"""


def generate(n: int = N_LISTINGS, seed: int = SEED) -> list:
    rng = random.Random(seed)
    return [_make_listing(i + 1, rng) for i in range(n)]


def build_database(n: int = N_LISTINGS, seed: int = SEED, db_path=None) -> int:
    db_path = db_path or config.DB_PATH
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    listings = generate(n, seed)

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("DROP TABLE IF EXISTS listings")
        cur.executescript(SCHEMA)
        cur.execute("CREATE INDEX idx_district ON listings(district)")
        cur.execute("CREATE INDEX idx_price ON listings(price)")
        cur.execute("CREATE INDEX idx_room ON listings(room_type)")

        columns = list(listings[0].keys())
        placeholders = ", ".join("?" for _ in columns)
        cur.executemany(
            f"INSERT INTO listings ({', '.join(columns)}) VALUES ({placeholders})",
            [tuple(row[c] for c in columns) for row in listings],
        )
        conn.commit()
    finally:
        conn.close()
    return len(listings)


if __name__ == "__main__":
    count = build_database()
    print(f"✓ Generated {count} synthetic listings -> {config.DB_PATH}")
