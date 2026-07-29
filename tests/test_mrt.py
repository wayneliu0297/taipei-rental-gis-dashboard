"""Tests for the Taipei MRT overlay data."""
from src import mrt

TAIPEI_BBOX = {"lat": (24.85, 25.30), "lon": (121.25, 121.80)}
EXPECTED_LINES = {"Tamsui–Xinyi", "Songshan–Xindian", "Zhonghe–Xinlu", "Bannan", "Wenhu"}


def test_segments_present():
    segs = mrt.mrt_segments()
    assert len(segs) >= 10
    for s in segs:
        assert {"zh", "line", "color", "paths"} <= set(s)
        assert s["color"].startswith("#")
        assert s["paths"] and all(len(p) >= 2 for p in s["paths"])


def test_all_official_lines_covered():
    lines = {s["line"] for s in mrt.mrt_segments()}
    assert EXPECTED_LINES <= lines


def test_coords_within_taipei_and_latlon_order():
    for s in mrt.mrt_segments():
        for path in s["paths"]:
            for lat, lon in path:
                assert TAIPEI_BBOX["lat"][0] < lat < TAIPEI_BBOX["lat"][1]
                assert TAIPEI_BBOX["lon"][0] < lon < TAIPEI_BBOX["lon"][1]


def test_legend_unique_ordered():
    leg = mrt.legend()
    names = [n for n, _ in leg]
    assert len(names) == len(set(names))  # unique
    assert EXPECTED_LINES <= set(names)
