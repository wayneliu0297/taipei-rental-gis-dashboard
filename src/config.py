"""
Central configuration for the Taipei Rental GIS Dashboard.

The ``DISTRICT_PROFILE`` below holds *aggregate* statistics (district centroids,
median rent-per-ping, typical MRT distance) that were derived from a private
reference dataset and then used only to make the **synthetic** listings in this
demo look realistic. It contains no addresses, no individual records, and no
company-identifying information. Every listing served by the app is randomly
generated — see ``generate_data.py``.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "listings.db"

# Map default view (roughly the centroid of the districts below)
MAP_CENTER = (25.03, 121.53)
DEFAULT_ZOOM = 12
MAP_TILES = "CartoDB positron"

# ---------------------------------------------------------------------------
# District profile — Greater Taipei (Taipei City + New Taipei City)
#   lat / lon        : real geographic centroid of the district
#   lat_sd / lon_sd  : spread used to scatter synthetic listings
#   unit_price       : typical monthly rent per ping (NT$), drives pricing
#   mrt_km           : typical walking distance to the nearest MRT station
#   name_zh          : Chinese name (secondary label only)
# Aggregate figures only; see module docstring.
# ---------------------------------------------------------------------------
DISTRICT_PROFILE = {
    "Zhongshan":  {"city": "Taipei City",     "name_zh": "中山區", "lat": 25.05631, "lon": 121.53437, "lat_sd": 0.006,  "lon_sd": 0.0062, "unit_price": 1470, "mrt_km": 0.7},
    "Wenshan":    {"city": "Taipei City",     "name_zh": "文山區", "lat": 24.99362, "lon": 121.54416, "lat_sd": 0.0072, "lon_sd": 0.0083, "unit_price": 1131, "mrt_km": 0.45},
    "Zhonghe":    {"city": "New Taipei City", "name_zh": "中和區", "lat": 24.99575, "lon": 121.51125, "lat_sd": 0.007,  "lon_sd": 0.0086, "unit_price": 1064, "mrt_km": 0.5},
    "Sanchong":   {"city": "New Taipei City", "name_zh": "三重區", "lat": 25.06103, "lon": 121.48855, "lat_sd": 0.0125, "lon_sd": 0.0094, "unit_price": 1063, "mrt_km": 0.7},
    "Da'an":      {"city": "Taipei City",     "name_zh": "大安區", "lat": 25.02968, "lon": 121.54096, "lat_sd": 0.0074, "lon_sd": 0.0094, "unit_price": 1060, "mrt_km": 0.57},
    "Yonghe":     {"city": "New Taipei City", "name_zh": "永和區", "lat": 25.00803, "lon": 121.51959, "lat_sd": 0.006,  "lon_sd": 0.006,  "unit_price": 1045, "mrt_km": 1.0},
    "Nangang":    {"city": "Taipei City",     "name_zh": "南港區", "lat": 25.04921, "lon": 121.59503, "lat_sd": 0.0061, "lon_sd": 0.0135, "unit_price": 1015, "mrt_km": 0.55},
    "Datong":     {"city": "Taipei City",     "name_zh": "大同區", "lat": 25.05638, "lon": 121.513,   "lat_sd": 0.006,  "lon_sd": 0.006,  "unit_price": 997,  "mrt_km": 0.65},
    "Banqiao":    {"city": "New Taipei City", "name_zh": "板橋區", "lat": 25.02321, "lon": 121.47667, "lat_sd": 0.006,  "lon_sd": 0.006,  "unit_price": 960,  "mrt_km": 0.82},
    "Zhongzheng": {"city": "Taipei City",     "name_zh": "中正區", "lat": 25.02559, "lon": 121.51728, "lat_sd": 0.0061, "lon_sd": 0.0082, "unit_price": 868,  "mrt_km": 0.8},
    "Wanhua":     {"city": "Taipei City",     "name_zh": "萬華區", "lat": 25.031,   "lon": 121.49871, "lat_sd": 0.0091, "lon_sd": 0.006,  "unit_price": 770,  "mrt_km": 0.9},
    "Neihu":      {"city": "Taipei City",     "name_zh": "內湖區", "lat": 25.07762, "lon": 121.58806, "lat_sd": 0.0103, "lon_sd": 0.0229, "unit_price": 666,  "mrt_km": 0.35},
    "Xinyi":      {"city": "Taipei City",     "name_zh": "信義區", "lat": 25.03698, "lon": 121.57334, "lat_sd": 0.0126, "lon_sd": 0.0084, "unit_price": 662,  "mrt_km": 0.5},
    "Xindian":    {"city": "New Taipei City", "name_zh": "新店區", "lat": 24.97299, "lon": 121.53463, "lat_sd": 0.0135, "lon_sd": 0.0098, "unit_price": 610,  "mrt_km": 0.35},
}

CITIES = ["Taipei City", "New Taipei City"]
CITY_ZH = {"Taipei City": "台北市", "New Taipei City": "新北市"}

# ---------------------------------------------------------------------------
# Room types
#   size    : ping range
#   weight  : sampling weight (whole-unit rentals dominate the seed data)
#   up_mult : multiplier on the district rent-per-ping (small units cost more
#             per ping, large units slightly less)
# ---------------------------------------------------------------------------
ROOM_TYPES = {
    "Studio": {"size": (6, 12),  "weight": 10, "up_mult": 1.25, "beds": 0, "baths": 1},
    "1BR":    {"size": (10, 18), "weight": 18, "up_mult": 1.12, "beds": 1, "baths": 1},
    "2BR":    {"size": (16, 26), "weight": 30, "up_mult": 1.00, "beds": 2, "baths": 1},
    "3BR":    {"size": (24, 36), "weight": 28, "up_mult": 0.95, "beds": 3, "baths": 2},
    "4BR+":   {"size": (34, 48), "weight": 14, "up_mult": 0.90, "beds": 4, "baths": 2},
}

# Building type -> probability of having an elevator (seed: ~17% overall)
BUILDING_TYPES = {
    "Walk-up apartment": {"weight": 74, "elevator_p": 0.05},
    "Elevator building":  {"weight": 18, "elevator_p": 1.00},
    "Townhouse":          {"weight": 8,  "elevator_p": 0.10},
}

# ---------------------------------------------------------------------------
# Price bands — colour the map + power the legend (NT$/month)
# ---------------------------------------------------------------------------
PRICE_BANDS = [
    ("Budget",   0,      20000,      "#059669"),  # emerald   (< NT$20k)
    ("Standard", 20000,  32000,      "#2563EB"),  # blue      (NT$20k–32k)
    ("Premium",  32000,  10_000_000, "#7C3AED"),  # violet    (>= NT$32k)
]
SELECTED_COLOR = "#DC2626"  # red highlight for the selected listing

FEATURE_POOL = [
    "Newly renovated", "Bright & airy", "Quiet street", "Fully furnished",
    "Washer & dryer", "Fibre internet", "Rooftop access", "Balcony",
    "Convenience store nearby", "Near night market", "Managed building",
]

# Generic romanised street names (fake — not tied to any real address)
STREET_NAMES = [
    "Zhongxiao E. Rd", "Ren'ai Rd", "Xinyi Rd", "Heping E. Rd", "Nanjing E. Rd",
    "Minsheng E. Rd", "Dunhua N. Rd", "Fuxing S. Rd", "Keelung Rd", "Roosevelt Rd",
    "Bade Rd", "Songjiang Rd", "Wenhua Rd", "Zhongshan Rd", "Sanmin Rd",
    "Boai St", "Zhongzheng Rd", "Minquan Rd",
]

# Rough conversion used for the "X min walk to MRT" label
WALK_MIN_PER_KM = 13


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def districts():
    return list(DISTRICT_PROFILE.keys())


def price_band(price: int) -> str:
    for name, lo, hi, _ in PRICE_BANDS:
        if lo <= price < hi:
            return name
    return PRICE_BANDS[-1][0]


def band_color(band: str) -> str:
    for name, _, _, color in PRICE_BANDS:
        if name == band:
            return color
    return "#6B7280"
