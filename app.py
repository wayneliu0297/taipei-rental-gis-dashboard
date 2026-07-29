"""
Taipei Rental GIS Dashboard
===========================

An interactive, Airbnb-style map of (synthetic) rental listings across Greater
Taipei (Taipei City + New Taipei City), built with Streamlit + Folium on a
SQLite backend.

Features
--------
* Folium map with Airbnb-style price-pill markers (clustered, clickable)
* Sidebar filters: city, district, monthly rent, room type, size, MRT distance
* Photo property cards linked to the map
* Click a card (or a marker) to "fly to" and highlight that listing
* Live KPI header that reacts to the filters
* 100 % generated fake data + royalty-free stock photos — no real listings

Run:  streamlit run app.py
"""

import streamlit as st
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium

from src import config, database, generate_data, media, mrt

# Build the SQLite database on first run (e.g. fresh clone / Streamlit Cloud,
# where there is no separate build step). No-op once the file exists.
if not config.DB_PATH.exists():
    generate_data.build_database()

# ---------------------------------------------------------------------------
# Version-compatibility helpers (target Streamlit 1.12 .. latest)
# ---------------------------------------------------------------------------
cache_data = getattr(st, "cache_data", st.cache)


def _rerun():
    if hasattr(st, "rerun"):
        st.rerun()
    elif hasattr(st, "experimental_rerun"):
        st.experimental_rerun()


st.set_page_config(page_title="Taipei Rental GIS Dashboard", page_icon="🏙️", layout="wide")

# ---------------------------------------------------------------------------
# Styling — minimal black & white, Airbnb-style cards
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    .block-container { padding-top: 1.1rem; padding-bottom: 1rem; max-width: 1500px; }
    header[data-testid="stHeader"] { background: transparent; }

    /* ---- top brand bar ---- */
    .topbar { display:flex; justify-content:space-between; align-items:center;
        padding:2px 2px 12px; border-bottom:1px solid #ECECEC; margin-bottom:14px; }
    .brand { font-size:1.35rem; font-weight:800; color:#111827; letter-spacing:-.01em; }
    .brand-mark { display:inline-block; background:#111827; color:#fff; border-radius:8px;
        padding:1px 8px; margin-right:8px; font-weight:900; }
    .brand-tag { color:#9CA3AF; font-weight:600; }
    .brand-right { font-size:.8rem; color:#6B7280; font-weight:600; text-align:right; }
    .brand-right b { color:#111827; }

    /* ---- KPI metrics ---- */
    div[data-testid="stMetricValue"] { font-size:1.25rem; font-weight:700; }
    div[data-testid="stMetricLabel"] { color:#6B7280; }

    /* ---- Airbnb-style property cards ---- */
    .property-card { border-radius:16px; background:#fff; border:1px solid #ECECEC;
        overflow:hidden; margin-bottom:6px;
        box-shadow:0 1px 2px rgba(0,0,0,.04), 0 8px 20px rgba(0,0,0,.05);
        transition:transform .12s ease, box-shadow .12s ease; }
    .property-card:hover { transform:translateY(-2px); box-shadow:0 10px 26px rgba(0,0,0,.10); }
    .property-card.selected { border:1.5px solid #111827; box-shadow:0 10px 26px rgba(0,0,0,.16); }
    .pc-photo { height:150px; background-size:cover; background-position:center;
        position:relative; background-color:#F3F4F6; }
    .pc-band { position:absolute; top:10px; left:10px; color:#fff; font-size:.66rem;
        font-weight:700; padding:3px 9px; border-radius:20px; letter-spacing:.02em;
        box-shadow:0 1px 3px rgba(0,0,0,.25); }
    .pc-heart { position:absolute; top:8px; right:10px; color:#fff; font-size:1.05rem;
        text-shadow:0 1px 3px rgba(0,0,0,.4); }
    .pc-body { padding:11px 14px 13px; }
    .pc-row1 { display:flex; justify-content:space-between; align-items:baseline; gap:8px; }
    .pc-title { font-weight:650; font-size:.94rem; color:#111827; }
    .pc-price { font-weight:800; font-size:1.02rem; color:#111827; white-space:nowrap; }
    .pc-sub { color:#9CA3AF; font-size:.72rem; margin-top:1px; }
    .pc-addr { color:#717171; font-size:.75rem; margin:6px 0 8px; }
    .badge { background:#F5F5F5; color:#374151; padding:2px 8px; border-radius:6px;
        font-size:.68rem; font-weight:500; margin-right:5px; border:1px solid #EDEDED;
        display:inline-block; margin-bottom:4px; }
    .dot { height:9px; width:9px; border-radius:50%; display:inline-block; margin-right:6px; }

    /* ---- filter chips -> black ---- */
    span[data-baseweb="tag"] { background-color:#111827 !important; }

    /* ---- buttons -> minimal ---- */
    .stButton button { border-radius:10px; border:1px solid #E5E7EB; color:#111827;
        font-weight:600; font-size:.82rem; background:#fff; }
    .stButton button:hover { border-color:#111827; color:#111827; background:#FAFAFA; }

    /* ---- keep the map pinned while only the listing column scrolls ---- */
    /* map column (the one holding the Folium iframe) */
    div[data-testid="column"]:has(iframe) {
        position: sticky; top: 0.5rem; align-self: flex-start; z-index: 5;
    }
    /* listing column = the column right after the map column */
    div[data-testid="column"]:has(iframe) + div[data-testid="column"] {
        max-height: 86vh; overflow-y: auto; padding-right: 8px;
    }
    div[data-testid="column"]:has(iframe) + div[data-testid="column"]::-webkit-scrollbar { width: 7px; }
    div[data-testid="column"]:has(iframe) + div[data-testid="column"]::-webkit-scrollbar-thumb {
        background: #D1D5DB; border-radius: 4px; }

    /* ---- centered listing modal (z above the sidebar @ 999991) ---- */
    .modal-backdrop { position:fixed; inset:0; background:rgba(17,24,39,.55);
        z-index:999992; }
    .listing-modal { position:fixed; top:50%; left:50%; transform:translate(-50%,-50%);
        width:min(560px,92vw); max-height:88vh; overflow:auto; background:#fff;
        border-radius:20px; box-shadow:0 24px 70px rgba(0,0,0,.42); z-index:999993; }
    .modal-photo { width:100%; height:230px; object-fit:cover; display:block;
        border-radius:20px 20px 0 0; }
    .modal-body { padding:15px 20px 20px; }
    .modal-head { display:flex; justify-content:space-between; align-items:flex-start; gap:10px; }
    .modal-title { font-weight:700; font-size:1.12rem; color:#111827; line-height:1.25; }
    .modal-zh { color:#9CA3AF; font-size:.74rem; font-weight:500; }
    .modal-addr { color:#6B7280; font-size:.8rem; margin-top:3px; }
    .modal-price { font-weight:800; font-size:1.2rem; color:#111827; white-space:nowrap; text-align:right; }
    .modal-permo { font-size:.64rem; color:#9CA3AF; font-weight:500; }
    .modal-stats { display:flex; gap:8px; margin:14px 0; }
    .modal-stats > div { flex:1; background:#F7F7F8; border-radius:12px; padding:8px 4px; text-align:center; }
    .modal-stats b { display:block; font-size:.92rem; color:#111827; }
    .modal-stats span { font-size:.64rem; color:#9CA3AF; }
    .modal-grid { display:grid; grid-template-columns:1fr 1fr; gap:9px 16px; font-size:.82rem; color:#374151; }
    .modal-grid > div span { display:block; color:#9CA3AF; font-size:.66rem;
        text-transform:uppercase; letter-spacing:.03em; }
    .modal-desc { margin-top:14px; font-size:.82rem; color:#4B5563; }
    .modal-contact { margin-top:8px; font-size:.72rem; color:#9CA3AF; }

    /* close button = the st.button rendered right after the hidden anchor
       (Streamlit 1.12 wraps each widget in .element-container, not a testid) */
    .element-container:has(#modal-close-anchor) { display:none; }
    .element-container:has(#modal-close-anchor) + .element-container {
        position:fixed; top:16px; right:22px; left:auto; width:44px; z-index:999994; }
    .element-container:has(#modal-close-anchor) + .element-container .stButton { width:44px; }
    .element-container:has(#modal-close-anchor) + .element-container .stButton button {
        border-radius:50%; width:44px; height:44px; font-size:1.15rem; font-weight:700;
        background:#fff; border:1px solid #E5E7EB; box-shadow:0 6px 18px rgba(0,0,0,.28); padding:0; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Inject the (once-embedded) photo background-image classes
st.markdown(media.photo_css(), unsafe_allow_html=True)

for _k, _v in {
    "selected_id": None,          # listing shown in the centered modal
    "last_click_xy": None,        # dedupe repeated last_object_clicked values
    "view": {"center": list(config.MAP_CENTER), "zoom": config.DEFAULT_ZOOM},
}.items():
    st.session_state.setdefault(_k, _v)


@cache_data
def _price_bounds():
    return database.price_bounds()


@cache_data
def _size_bounds():
    return database.size_bounds()


# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------
st.sidebar.markdown("## 🔎 Filters")

# --- City (checkboxes) ---
st.sidebar.markdown("**City**")
sel_cities = [c for c in config.CITIES
              if st.sidebar.checkbox(f"{c} ({config.CITY_ZH[c]})", value=True, key=f"city_{c}")]

# --- District (checkboxes, single column so the English + Chinese label fits) ---
st.sidebar.markdown("**District**")
sel_districts = []
for d in config.districts():
    if config.DISTRICT_PROFILE[d]["city"] not in sel_cities:
        continue
    label = f"{d} ({config.DISTRICT_PROFILE[d]['name_zh']})"
    if st.sidebar.checkbox(label, value=True, key=f"dist_{d}"):
        sel_districts.append(d)

pmin, pmax = _price_bounds()
price_range = st.sidebar.slider("Monthly rent (NT$)", min_value=pmin, max_value=pmax,
                                value=(pmin, pmax), step=500, format="%d")

st.sidebar.markdown("**Room type**")
sel_rooms = []
_rcols = st.sidebar.columns(3)
for _j, _r in enumerate(config.ROOM_TYPES.keys()):
    if _rcols[_j % 3].checkbox(_r, value=True, key=f"room_{_r}"):
        sel_rooms.append(_r)

smin, smax = _size_bounds()
size_range = st.sidebar.slider("Size (ping)", min_value=float(smin), max_value=float(smax),
                               value=(float(smin), float(smax)), step=1.0)

max_mrt = st.sidebar.slider("Max walk to MRT (min)", min_value=1, max_value=20, value=20)

st.sidebar.markdown("---")
_band_label = {"Budget": "under 20k", "Standard": "20–32k", "Premium": "32k+"}
legend_html = "**Price band (NT$/mo)**  \n".replace("$", "&#36;") + "  \n".join(
    f"<span class='dot' style='background:{color}'></span>{name} ({_band_label[name]})"
    for name, _, _, color in config.PRICE_BANDS
)
st.sidebar.caption(legend_html, unsafe_allow_html=True)

mrt_legend = "**MRT lines**  \n" + "  \n".join(
    f"<span class='dot' style='background:{color}'></span>{name}"
    for name, color in mrt.legend()
)
st.sidebar.caption(mrt_legend, unsafe_allow_html=True)

st.sidebar.caption("⚠️ All data is randomly generated for this demo. Photos are royalty-free "
                   "stock images — no real listings or company data. MRT geometry: open data.")

# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------
df = database.query_listings(
    cities=sel_cities or None, districts=sel_districts or None, price_range=price_range,
    room_types=sel_rooms or None, size_range=size_range,
    max_mrt_min=max_mrt if max_mrt < 20 else None,
)

if st.session_state.selected_id is not None and (
    df.empty or st.session_state.selected_id not in set(df["id"])):
    st.session_state.selected_id = None

selected = (database.get_listing(int(st.session_state.selected_id))
            if st.session_state.selected_id is not None else None)

# ---------------------------------------------------------------------------
# Brand header + KPI row
# ---------------------------------------------------------------------------
st.markdown(
    "<div class='topbar'>"
    "<div class='brand'><span class='brand-mark'>◗</span>Taipei Rental GIS "
    "<span class='brand-tag'>Dashboard</span></div>"
    "<div class='brand-right'>Greater Taipei · synthetic data<br>"
    "Data-Driven Portfolio · <b>Wayne Liu</b></div>"
    "</div>",
    unsafe_allow_html=True,
)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Listings shown", f"{len(df)}")
k2.metric("Median rent", f"NT$ {int(df['price'].median()):,}" if not df.empty else "—")
k3.metric("Avg. size", f"{df['size_ping'].mean():.1f} ping" if not df.empty else "—")
k4.metric("Avg. MRT walk", f"{df['mrt_min'].mean():.0f} min" if not df.empty else "—")
st.markdown("")

# ---------------------------------------------------------------------------
# Map markers — Airbnb-style price pills
# ---------------------------------------------------------------------------
def price_pin(price: int, band_color: str, is_sel: bool) -> folium.DivIcon:
    k = f"{price/1000:.0f}K"
    if is_sel:
        style = ("background:#111827;color:#fff;border-color:#111827;"
                 "transform:translate(-50%,-50%) scale(1.14);z-index:9999;")
        dot = "#fff"
    else:
        style = "background:#fff;color:#111827;border-color:#E5E7EB;transform:translate(-50%,-50%);"
        dot = band_color
    html = (f'<div style="position:absolute;{style}border:1px solid;border-radius:18px;'
            f'padding:2px 9px;font:700 11px/1.35 -apple-system,BlinkMacSystemFont,sans-serif;'
            f'box-shadow:0 1px 5px rgba(0,0,0,.30);white-space:nowrap;">'
            f'<span style="color:{dot}">●</span> {k}</div>')
    return folium.DivIcon(html=html, icon_size=(0, 0), icon_anchor=(0, 0))


def modal_card_html(s: dict) -> str:
    photo = media.photo_data_uri(media.photo_number(int(s["id"]), s["room_type"]))
    yn = lambda v: "Yes" if v else "No"
    return (
        '<div class="listing-modal">'
        f'<img class="modal-photo" src="{photo}">'
        '<div class="modal-body">'
        '<div class="modal-head"><div>'
        f'<div class="modal-title">{s["room_type"]} · {s["district"]} '
        f'<span class="modal-zh">{s["district_zh"]} · {s["city"]}</span></div>'
        f'<div class="modal-addr">📍 {s["address"]}</div></div>'
        f'<div class="modal-price">NT$ {s["price"]:,}<div class="modal-permo">per month</div></div>'
        '</div>'
        '<div class="modal-stats">'
        f'<div><b>{s["size_ping"]:g}</b><span>ping</span></div>'
        f'<div><b>{s["unit_price"]:,}</b><span>NT$/ping</span></div>'
        f'<div><b>{s["mrt_min"]} min</b><span>to MRT</span></div>'
        f'<div><b>{s["bedrooms"]}/{s["bathrooms"]}</b><span>bed/bath</span></div>'
        '</div>'
        '<div class="modal-grid">'
        f'<div><span>Building</span>{s["building_type"]}</div>'
        f'<div><span>Floor</span>{s["floor"]}/{s["total_floors"]}</div>'
        f'<div><span>Renovated</span>{s["renovation_age"]} yr ago</div>'
        f'<div><span>Elevator / Parking</span>{yn(s["has_elevator"])} / {yn(s["has_parking"])}</div>'
        f'<div><span>Pets</span>{"Allowed" if s["pet_allowed"] else "Not allowed"}</div>'
        f'<div><span>Rent subsidy</span>{"Eligible" if s["subsidy_eligible"] else "No"}</div>'
        '</div>'
        f'<div class="modal-desc">{s["description"]}</div>'
        f'<div class="modal-contact">Contact (fake): {s["landlord"]} · {s["phone"]} · '
        f'listed {s["posted_date"]}</div>'
        '</div></div>'
    )


col_map, col_list = st.columns([2.05, 1])

with col_map:
    view = st.session_state.view
    fmap = folium.Map(location=view["center"], zoom_start=view["zoom"],
                      tiles=config.MAP_TILES, control_scale=True)
    mrt.add_mrt_layer(fmap)     # Taipei MRT lines (under the listing markers)
    mrt.add_mrt_stations(fmap)  # station dots on top of the lines
    cluster = MarkerCluster(disableClusteringAtZoom=15).add_to(fmap)

    for _, row in df.iterrows():
        is_sel = st.session_state.selected_id == row["id"]
        bcolor = config.band_color(row["price_band"])
        folium.Marker(
            location=[row["lat"], row["lon"]],
            icon=price_pin(row["price"], bcolor, is_sel),
            tooltip=f"{row['room_type']} · NT$ {row['price']:,} · {row['district']}",
        ).add_to(cluster)

    map_state = st_folium(
        fmap, width=None, height=630, key="map",
        returned_objects=["bounds", "center", "zoom", "last_object_clicked"],
    )

# Keep the map where the user left it across reruns (so panning doesn't reset)
if map_state:
    c, z = map_state.get("center"), map_state.get("zoom")
    if c and z:
        st.session_state.view = {"center": [c["lat"], c["lng"]], "zoom": z}

# Click a marker -> open the modal (dedupe the persisted last_object_clicked)
lc = map_state.get("last_object_clicked") if map_state else None
if lc and not df.empty:
    xy = (round(lc["lat"], 6), round(lc["lng"], 6))
    if xy != st.session_state.last_click_xy:
        st.session_state.last_click_xy = xy
        df2 = df.copy()
        df2["_d"] = (df2["lat"] - lc["lat"]) ** 2 + (df2["lon"] - lc["lng"]) ** 2
        st.session_state.selected_id = int(df2.sort_values("_d").iloc[0]["id"])
        _rerun()

# Listings within the current map viewport (right-hand cards react to panning)
bounds = map_state.get("bounds") if map_state else None
in_view = df
if bounds and bounds.get("_southWest") and not df.empty:
    sw, ne = bounds["_southWest"], bounds["_northEast"]
    # ignore the degenerate bounds Leaflet reports before the map is sized
    if (ne["lat"] - sw["lat"]) > 0.002 and (ne["lng"] - sw["lng"]) > 0.002:
        in_view = df[(df["lat"] >= sw["lat"]) & (df["lat"] <= ne["lat"]) &
                     (df["lon"] >= sw["lng"]) & (df["lon"] <= ne["lng"])]

# ---------------------------------------------------------------------------
# Property cards
# ---------------------------------------------------------------------------
with col_list:
    st.markdown(f"#### {len(in_view)} stays in view")

    if df.empty:
        st.info("No listings match the current filters. Try widening them.")
    elif in_view.empty:
        st.info("No listings in the current map view — pan or zoom out.")
    else:
        ordered = in_view.sort_values("price")

        for _, row in ordered.head(24).iterrows():
            is_sel = row["id"] == st.session_state.selected_id
            bcolor = config.band_color(row["price_band"])
            pnum = media.photo_number(int(row["id"]), row["room_type"])
            badges = "".join(
                f"<span class='badge'>{b}</span>" for b in [
                    f"{row['size_ping']:g} ping", f"🚇 {row['mrt_min']} min",
                    f"Fl {row['floor']}/{row['total_floors']}",
                    "🛗 Elevator" if row["has_elevator"] else None,
                    "🐾 Pets" if row["pet_allowed"] else None,
                ] if b
            )
            st.markdown(
                f"""
                <div class="property-card {'selected' if is_sel else ''}">
                    <div class="pc-photo listing-photo-{pnum}">
                        <span class="pc-band" style="background:{bcolor}">{row['price_band']}</span>
                        <span class="pc-heart">♡</span>
                    </div>
                    <div class="pc-body">
                        <div class="pc-row1">
                            <span class="pc-title">{row['room_type']} · {row['district']}</span>
                            <span class="pc-price">NT$ {row['price']:,}</span>
                        </div>
                        <div class="pc-sub">{row['district_zh']} · {row['city']} · NT$ {row['price']//1000}k/mo</div>
                        <div class="pc-addr">📍 {row['address']}</div>
                        <div>{badges}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            label = "✓ Showing details" if is_sel else "View details  →"
            if st.button(label, key=f"btn_{row['id']}", disabled=bool(is_sel)):
                st.session_state.selected_id = int(row["id"])
                _rerun()

        if len(in_view) > 24:
            st.caption(f"Showing first 24 of {len(in_view)} in view — zoom in or filter to narrow.")

# ---------------------------------------------------------------------------
# Centered modal for the selected listing (marker click or card button)
# ---------------------------------------------------------------------------
if selected:
    # Hidden anchor -> CSS turns the *next* element (this button) into the
    # floating ✕ close button positioned over the modal.
    st.markdown('<div id="modal-close-anchor"></div>', unsafe_allow_html=True)
    if st.button("✕", key="modal_close", help="Close"):
        st.session_state.selected_id = None
        _rerun()
    st.markdown('<div class="modal-backdrop"></div>' + modal_card_html(selected),
                unsafe_allow_html=True)
