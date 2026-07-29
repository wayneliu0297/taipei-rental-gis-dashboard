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
    </style>
    """,
    unsafe_allow_html=True,
)

# Inject the (once-embedded) photo background-image classes
st.markdown(media.photo_css(), unsafe_allow_html=True)

if "selected_id" not in st.session_state:
    st.session_state.selected_id = None


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
sel_cities = st.sidebar.multiselect("City", options=config.CITIES, default=config.CITIES)

district_opts = [d for d in config.districts()
                 if not sel_cities or config.DISTRICT_PROFILE[d]["city"] in sel_cities]
sel_districts = st.sidebar.multiselect(
    "District", options=district_opts, default=district_opts,
    format_func=lambda d: f"{d} ({config.DISTRICT_PROFILE[d]['name_zh']})",
)

pmin, pmax = _price_bounds()
price_range = st.sidebar.slider("Monthly rent (NT$)", min_value=pmin, max_value=pmax,
                                value=(pmin, pmax), step=500, format="%d")

sel_rooms = st.sidebar.multiselect("Room type", options=list(config.ROOM_TYPES.keys()),
                                   default=list(config.ROOM_TYPES.keys()))

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


col_map, col_list = st.columns([2.05, 1])

with col_map:
    if selected:
        center, zoom = [selected["lat"], selected["lon"]], 16
    else:
        center, zoom = list(config.MAP_CENTER), config.DEFAULT_ZOOM

    fmap = folium.Map(location=center, zoom_start=zoom, tiles=config.MAP_TILES,
                      control_scale=True)
    mrt.add_mrt_layer(fmap)  # Taipei MRT network (under the listing markers)
    cluster = MarkerCluster(disableClusteringAtZoom=15).add_to(fmap)

    for _, row in df.iterrows():
        is_sel = selected is not None and row["id"] == selected["id"]
        bcolor = config.band_color(row["price_band"])
        popup_html = (
            f"<div style='font-family:sans-serif;font-size:12px;min-width:180px'>"
            f"<b>{row['room_type']} · {row['district']}</b><br>"
            f"<span style='color:#666'>{row['address']}</span><br>"
            f"<b style='font-size:14px'>NT$ {row['price']:,}</b> / mo · "
            f"{row['size_ping']:g} ping<br>"
            f"🚇 {row['mrt_min']} min to MRT · Floor {row['floor']}/{row['total_floors']}</div>"
        )
        folium.Marker(
            location=[row["lat"], row["lon"]],
            icon=price_pin(row["price"], bcolor, is_sel),
            popup=folium.Popup(popup_html, max_width=250),
            tooltip=f"{row['room_type']} · NT$ {row['price']:,}",
        ).add_to(cluster)

    map_state = st_folium(fmap, width=None, height=630, key="map")

    clicked = map_state.get("last_object_clicked") if map_state else None
    if clicked and not df.empty:
        clat, clon = clicked["lat"], clicked["lng"]
        df2 = df.copy()
        df2["_d"] = (df2["lat"] - clat) ** 2 + (df2["lon"] - clon) ** 2
        nearest = int(df2.sort_values("_d").iloc[0]["id"])
        if nearest != st.session_state.selected_id:
            st.session_state.selected_id = nearest
            _rerun()

# ---------------------------------------------------------------------------
# Property cards
# ---------------------------------------------------------------------------
with col_list:
    st.markdown(f"#### {len(df)} stays")
    if selected and st.button("↩︎ Reset selection"):
        st.session_state.selected_id = None
        _rerun()

    if df.empty:
        st.info("No listings match the current filters. Try widening them.")
    else:
        ordered = df.copy()
        ordered["_sel"] = (ordered["id"] == st.session_state.selected_id).astype(int)
        ordered = ordered.sort_values(["_sel", "price"], ascending=[False, True])

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
            label = "✓ Selected — see details below" if is_sel else "View on map  →"
            if st.button(label, key=f"btn_{row['id']}", disabled=bool(is_sel)):
                st.session_state.selected_id = int(row["id"])
                _rerun()

        if len(df) > 24:
            st.caption(f"Showing first 24 of {len(df)} listings — narrow the filters to see more.")

# ---------------------------------------------------------------------------
# Detail panel (hero photo + full info)
# ---------------------------------------------------------------------------
if selected:
    st.markdown("---")
    st.subheader(f"🏠 {selected['title']}")

    # KPI row (top-level columns)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Monthly rent", f"NT$ {selected['price']:,}")
    m2.metric("Size", f"{selected['size_ping']:g} ping")
    m3.metric("Rent / ping", f"NT$ {selected['unit_price']:,}")
    m4.metric("MRT walk", f"{selected['mrt_min']} min")

    # Hero photo + details (top-level columns; no nesting inside)
    pnum = media.photo_number(int(selected["id"]), selected["room_type"])
    img_col, txt_col = st.columns([1, 1.6])
    with img_col:
        st.markdown(
            f"<img src='{media.photo_data_uri(pnum)}' "
            f"style='width:100%;height:210px;object-fit:cover;border-radius:16px'>",
            unsafe_allow_html=True,
        )
    with txt_col:
        st.markdown(
            f"**District:** {selected['district']} ({selected['district_zh']}), {selected['city']}  \n"
            f"**Address:** {selected['address']}  \n"
            f"**Layout:** {selected['room_type']} · {selected['bedrooms']} bed / {selected['bathrooms']} bath  \n"
            f"**Building:** {selected['building_type']} · Floor {selected['floor']}/{selected['total_floors']}  \n"
            f"**Renovated:** {selected['renovation_age']} yr ago · "
            f"**Elevator:** {'Yes' if selected['has_elevator'] else 'No'} · "
            f"**Parking:** {'Yes' if selected['has_parking'] else 'No'}  \n"
            f"**Pets:** {'Allowed' if selected['pet_allowed'] else 'Not allowed'} · "
            f"**Rent-subsidy eligible:** {'Yes' if selected['subsidy_eligible'] else 'No'}"
        )
    st.caption(selected["description"])
    st.caption(f"Contact (fake): {selected['landlord']} · {selected['phone']} · listed {selected['posted_date']}")
