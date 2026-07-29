"""
Taipei MRT network overlay for the Folium map.

Line geometry comes from the open-source ``leoluyi/taipei_mrt`` dataset
(public MRT route data), pre-processed into ``assets/taipei_mrt.json`` as
lat/lon paths tagged with each line's official Taipei Metro colour.
"""

import json
from functools import lru_cache

try:
    from src import config
except ImportError:  # pragma: no cover
    import config

MRT_PATH = config.PROJECT_ROOT / "assets" / "taipei_mrt.json"
STATIONS_PATH = config.PROJECT_ROOT / "assets" / "taipei_mrt_stations.json"


@lru_cache(maxsize=1)
def mrt_segments() -> list:
    if not MRT_PATH.exists():
        return []
    return json.loads(MRT_PATH.read_text(encoding="utf-8")).get("lines", [])


@lru_cache(maxsize=1)
def mrt_stations() -> list:
    if not STATIONS_PATH.exists():
        return []
    return json.loads(STATIONS_PATH.read_text(encoding="utf-8")).get("stations", [])


def legend() -> list:
    """Ordered list of (line_name, color) for the sidebar legend."""
    seen = {}
    for seg in mrt_segments():
        seen.setdefault(seg["line"], seg["color"])
    return list(seen.items())


def _thin(path, step=2):
    """Keep every ``step``-th point (plus the last) to cut the payload size."""
    if len(path) <= 3:
        return path
    kept = path[::step]
    if kept[-1] != path[-1]:
        kept.append(path[-1])
    return kept


def add_mrt_layer(fmap, weight: float = 3.0, opacity: float = 0.75):
    """Draw the MRT lines onto a Folium map (below the listing markers).

    Lines are point-thinned so the (re)drawn payload stays small — the full
    geometry is ~8k points, which made every Streamlit rerun sluggish.
    """
    import folium

    for seg in mrt_segments():
        for path in seg["paths"]:
            if len(path) < 2:
                continue
            folium.PolyLine(_thin(path), color=seg["color"], weight=weight,
                            opacity=opacity, tooltip=f"{seg['line']} Line").add_to(fmap)
    return fmap


def add_mrt_stations(fmap, radius: float = 3):
    """Draw MRT stations as small white dots with a dark ring (metro-map style)."""
    import folium

    for st in mrt_stations():
        folium.CircleMarker(
            location=[st["lat"], st["lon"]],
            radius=radius,
            color="#374151", weight=1.4,
            fill=True, fill_color="#ffffff", fill_opacity=1.0,
            tooltip=st["name"],
        ).add_to(fmap)
    return fmap
