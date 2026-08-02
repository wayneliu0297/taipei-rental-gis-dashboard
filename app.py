"""
Taipei Rental GIS Dashboard
===========================

An interactive, Airbnb-style map of (synthetic) rental listings across Greater
Taipei (Taipei City + New Taipei City), built with Streamlit + Folium on a
SQLite backend.

Architecture note
-----------------
Map interactions are deliberately decoupled from Streamlit's rerun loop:

* ``st_folium`` watches only ``all_drawings`` (which never changes here), so
  panning / zooming NEVER triggers a Python rerun — the map is pure Leaflet
  and stays butter-smooth.
* A tiny ``components.html`` injector receives the filtered listings as JSON
  and renders the "stays in view" cards **client-side** on every ``moveend`` /
  ``zoomend``, opens the listing modal (from cards or map pins), and persists
  the view in ``sessionStorage`` so sidebar-filter reruns restore it.
* Only sidebar filter changes rerun Python (they re-query SQLite and rebuild
  the marker set — the one case where a rerun is actually needed).

Run:  streamlit run app.py
"""

import json

import streamlit as st
import streamlit.components.v1 as components
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium

from src import config, database, generate_data, media, mrt

# Build the SQLite database on first run (e.g. fresh clone / Streamlit Cloud,
# where there is no separate build step). No-op once the file exists.
if not config.DB_PATH.exists():
    generate_data.build_database()

cache_data = getattr(st, "cache_data", st.cache)  # Streamlit 1.12 .. latest

st.set_page_config(page_title="Taipei Rental GIS Dashboard", page_icon="🗺️", layout="wide")

CARD_CAP = 24  # cards rendered in the right-hand column at any one time

# ---------------------------------------------------------------------------
# Design system — ink navy + Inter, Airbnb-style surfaces
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&family=Noto+Sans+TC:wght@400;500;700&display=swap');

    :root {
        --accent: #FB6E3B;        /* lively coral-orange — selected pills, logo, sliders */
        --accent-deep: #E85A28;
        --accent-soft: #FFF1EA;
        --brand: #111111;        /* black — primary UI (selected pills, accents) */
        --brand-2: #333333;       /* softer black */
        --brand-deep: #000000;    /* hover / pressed */
        --brand-tint: #F2F3F5;    /* neutral chip wash */
        --ink: #111827;           /* primary text */
        --muted: #6B7280;         /* secondary text */
        --faint: #9CA3AF;         /* tertiary text */
        --line: #E7E8EB;          /* hairlines */
        --surface: #F4F5F7;       /* tiles / chips / unselected pills */
        --gold: #F4C430;          /* "極新裝潢 / newly renovated" badge */
        --gold-bg: #FEF7E0;
        --avail: #F59E0B;         /* Available (待租中) — amber (= config.STATUS_COLOR) */
        --rented: #059669;        /* Rented (已出租) — green  (= config.STATUS_COLOR) */
    }

    html, body, [class*="css"] {
        font-family: 'Inter', 'Noto Sans TC', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    .stApp { background: #FFFFFF; }
    .block-container { padding: 1.1rem 1.7rem 1rem; max-width: 1560px; }
    header[data-testid="stHeader"] { background: transparent; }

    /* ---- top brand bar ---- */
    .topbar { display:flex; justify-content:space-between; align-items:center;
        padding:2px 2px 13px; border-bottom:1px solid var(--line); margin-bottom:14px; }
    .brand { display:flex; align-items:center; gap:11px; }
    .brand-name { font-size:1.3rem; font-weight:800; color:var(--ink); letter-spacing:-.02em; }
    .brand-name .thin { color:var(--faint); font-weight:600; }
    .brand-sub { font-size:.68rem; color:var(--muted); font-weight:700; letter-spacing:.11em;
        text-transform:uppercase; margin-top:2px; }
    .brand-right { font-size:.78rem; color:var(--muted); font-weight:600; text-align:right; line-height:1.5; }
    .brand-right b { color:var(--ink); }
    .demo-pill { display:inline-block; background:var(--accent); color:#fff;
        font-size:.62rem; font-weight:700; letter-spacing:.05em; text-transform:uppercase;
        padding:2px 9px; border-radius:20px; margin-bottom:3px; }

    /* ---- KPI tiles ---- */
    div[data-testid="metric-container"], div[data-testid="stMetric"] {
        background:#fff; border:1px solid var(--line); border-radius:15px;
        padding:11px 16px 13px; box-shadow:0 1px 2px rgba(15,23,42,.04); }
    div[data-testid="stMetricValue"] { font-size:1.24rem; font-weight:800; color:var(--ink); }
    div[data-testid="stMetricLabel"] { color:var(--muted); }
    /* split "Listings" KPI: Available (amber) / Rented (green) */
    .kpi-split { background:#fff; border:1px solid var(--line); border-radius:15px;
        padding:11px 16px 13px; box-shadow:0 1px 2px rgba(15,23,42,.04); }
    .kpi-split .ks-label { color:var(--muted); font-size:.8rem; font-weight:500;
        line-height:1.6; margin-bottom:1px; }
    .kpi-split .ks-val { font-weight:800; font-size:1.24rem; letter-spacing:-.01em;
        display:flex; align-items:baseline; gap:7px; }
    .kpi-split .ks-a { color:var(--avail); }
    .kpi-split .ks-r { color:var(--rented); }
    .kpi-split .ks-slash { color:#CBD5E1; font-weight:600; }
    .kpi-split .ks-dot { font-size:.7em; margin-right:2px; }

    /* ---- listing cards (client-generated) — clean text-forward style ---- */
    .property-card { border-radius:16px; background:#fff; border:1px solid var(--line);
        overflow:hidden; margin-bottom:12px; cursor:pointer;
        box-shadow:0 1px 2px rgba(17,17,17,.04), 0 10px 24px rgba(17,17,17,.06);
        transition:transform .12s ease, box-shadow .12s ease; }
    .property-card:hover { transform:translateY(-2px); box-shadow:0 14px 30px rgba(17,17,17,.14); }
    .pc-photo { height:132px; background-size:cover; background-position:center;
        position:relative; background-color:#F1F5F9; }
    .pc-status { position:absolute; top:10px; left:10px; color:#fff; font-size:.64rem;
        font-weight:700; padding:3px 9px; border-radius:20px; box-shadow:0 1px 3px rgba(0,0,0,.25); }
    .pc-heart { position:absolute; top:8px; right:11px; color:#fff; font-size:1.1rem;
        text-shadow:0 1px 3px rgba(0,0,0,.4); transition:transform .12s ease; }
    .property-card:hover .pc-heart { color:var(--accent); transform:scale(1.15); }
    .pc-body { padding:12px 14px 13px; }
    .pc-top { display:flex; justify-content:space-between; align-items:center; gap:8px; }
    .pc-top-l { display:flex; align-items:center; gap:6px; flex-wrap:wrap; }
    .pc-tag { background:var(--accent); color:#fff; font-size:.66rem; font-weight:700;
        padding:2px 9px; border-radius:8px; letter-spacing:.02em; }
    .pc-badge { background:var(--gold-bg); color:#9A7B12; font-size:.62rem; font-weight:700;
        padding:2px 8px; border-radius:8px; border:1px solid #F3E2A8; white-space:nowrap; }
    .pc-price { font-weight:800; font-size:1.12rem; color:var(--ink); white-space:nowrap; letter-spacing:-.01em; }
    .pc-room { font-weight:800; font-size:1.02rem; color:var(--ink); margin:8px 0 2px; }
    .pc-room-sub { font-weight:500; font-size:.8rem; color:var(--muted); }
    .pc-addr { color:var(--muted); font-size:.74rem; margin:3px 0 10px; line-height:1.4; }
    .pc-stats { display:flex; gap:8px; margin-bottom:10px; }
    .pc-stats > div { flex:1; background:var(--surface); border:1px solid var(--line);
        border-radius:8px; padding:7px 10px; }
    .pc-stats span { display:block; font-size:.6rem; color:var(--faint); font-weight:600;
        text-transform:uppercase; letter-spacing:.04em; }
    .pc-stats b { font-size:.86rem; color:var(--ink); }
    .pc-tags { display:flex; flex-wrap:wrap; gap:5px; }
    .pc-hash { background:var(--surface); color:#374151; font-size:.66rem; font-weight:500;
        padding:2px 8px; border-radius:8px; border:1px solid var(--line); }
    .dot { height:9px; width:9px; border-radius:50%; display:inline-block; margin-right:6px; }

    /* ---- right column: header + client-rendered card list ---- */
    .stays-head { font-size:1.12rem; font-weight:800; color:#0F172A; margin:0 0 2px; }
    .stays-sub { font-size:.7rem; color:#94A3B8; margin-bottom:10px; }
    #cards-note { font-size:.72rem; color:#94A3B8; margin:2px 0 10px; }
    .cards-empty { background:#F8FAFC; border:1px solid #EEF2F7; border-radius:12px;
        padding:16px; font-size:.84rem; color:#475569; }

    /* ---- keep the map pinned (sticky) while the listings column scrolls ---- */
    div[data-testid="column"]:has(iframe) {
        position: sticky !important; top: 1rem;
        align-self: flex-start; height: fit-content; z-index: 5; }
    div[data-testid="column"]:has(iframe) + div[data-testid="column"] {
        max-height: 88vh; overflow-y: auto; padding-right: 8px; }
    div[data-testid="column"]:has(iframe) + div[data-testid="column"]::-webkit-scrollbar { width: 7px; }
    div[data-testid="column"]:has(iframe) + div[data-testid="column"]::-webkit-scrollbar-thumb {
        background: #D8DEE6; border-radius: 4px; }

    /* ---- centered listing modal (z above the sidebar @ 999991) ----
       Fade with opacity/pointer-events, NOT display:none. A hard display
       toggle removes a full-screen fixed layer in one frame, which forces the
       browser to recomposite the canvas-heavy Leaflet map underneath — that
       one-frame repaint was the "map flicker" seen on close. Fading keeps the
       map layer untouched, so close is smooth. */
    .modal-backdrop { position:fixed; inset:0; background:rgba(15,23,42,.46);
        z-index:999992; opacity:0; pointer-events:none; will-change:opacity;
        transition:opacity .17s ease; }
    .modal-backdrop.lm-open { opacity:1; pointer-events:auto; }
    .listing-modal { position:fixed; top:50%; left:50%;
        transform:translate(-50%,-50%) scale(.985);
        width:min(560px,92vw); max-height:88vh; overflow:auto; background:#fff;
        border-radius:20px; box-shadow:0 24px 70px rgba(15,23,42,.34); z-index:999993;
        opacity:0; pointer-events:none;
        transition:opacity .17s ease, transform .17s cubic-bezier(.2,.7,.3,1); }
    .listing-modal.lm-open { opacity:1; pointer-events:auto;
        transform:translate(-50%,-50%) scale(1); }
    /* keep the map iframe on its own layer — an overlay fade then never
       re-rasterises the Leaflet canvas (belt-and-braces against flicker) */
    div[data-testid="column"]:has(iframe) iframe { transform: translateZ(0); }
    .modal-close-x { position:absolute; top:12px; right:14px; width:34px; height:34px;
        border-radius:50%; background:rgba(255,255,255,.94); color:#0F172A; cursor:pointer;
        display:flex; align-items:center; justify-content:center; font-weight:700;
        font-size:.95rem; box-shadow:0 2px 10px rgba(0,0,0,.3); z-index:2; }
    .modal-photo { height:230px; background-size:cover; background-position:center;
        background-color:#EEF1F5; border-radius:20px 20px 0 0; position:relative; }
    .modal-status { position:absolute; top:12px; left:14px; color:#fff; font-size:.68rem;
        font-weight:700; padding:3px 11px; border-radius:20px; box-shadow:0 1px 4px rgba(0,0,0,.3); }
    .modal-body { padding:15px 20px 20px; }
    .modal-head { display:flex; justify-content:space-between; align-items:flex-start; gap:10px; }
    .modal-title { font-weight:800; font-size:1.1rem; color:#0F172A; line-height:1.25; }
    .modal-zh { color:#94A3B8; font-size:.74rem; font-weight:500; }
    .modal-addr { color:#64748B; font-size:.8rem; margin-top:3px; }
    .modal-price { font-weight:800; font-size:1.2rem; color:#0F172A; white-space:nowrap; text-align:right; }
    .modal-permo { font-size:.64rem; color:#94A3B8; font-weight:500; }
    .modal-stats { display:flex; gap:8px; margin:14px 0; }
    .modal-stats > div { flex:1; background:#F6F7F9; border-radius:12px; padding:8px 4px; text-align:center; }
    .modal-stats b { display:block; font-size:.92rem; color:#0F172A; }
    .modal-stats span { font-size:.64rem; color:#94A3B8; }
    .modal-grid { display:grid; grid-template-columns:1fr 1fr; gap:9px 16px; font-size:.82rem; color:#334155; }
    .modal-grid > div span { display:block; color:#94A3B8; font-size:.66rem;
        text-transform:uppercase; letter-spacing:.03em; }
    .modal-desc { margin-top:14px; font-size:.82rem; color:#475569; line-height:1.55; }
    .modal-contact { margin-top:8px; font-size:.72rem; color:#94A3B8; }

    /* ---- sidebar: clean design system, everything at a glance ---- */
    section[data-testid="stSidebar"] { min-width:330px; border-right:1px solid var(--line); }
    /* Streamlit hard-codes ~96px top padding on the wrapper ABOVE .block-container
       — that was the big blank at the top of the left column. Pull it up. */
    section[data-testid="stSidebar"] div:has(> .block-container) { padding-top:1.15rem !important; }
    section[data-testid="stSidebar"] .block-container { padding:.35rem 1.05rem 1.2rem; }
    section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap:.34rem; }
    .sb-title { font-size:1.06rem; font-weight:800; color:var(--ink); letter-spacing:-.01em;
        display:flex; align-items:center; gap:8px; }
    .sb-title::before { content:""; width:9px; height:9px; border-radius:3px;
        background:var(--accent); }
    .sb-h { font-size:.92rem; font-weight:800; letter-spacing:.02em; text-transform:uppercase;
        color:var(--ink); margin:.95rem 0 .45rem; line-height:1.3; }
    .sb-h.sb-h-sp { margin-bottom:1rem; }     /* extra gap after Status/City/District/Room */
    .sb-h.sb-h-tight { margin-bottom:.1rem; } /* tighter gap after View mode */
    section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] { gap:.5rem; margin-top:.05rem; }
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] .stMarkdown p { font-size:11px; }
    /* Streamlit renders each checkbox/radio label's TEXT in a nested markdown
       <div> that keeps its own 16px and ignores the label's font-size — so it
       must be targeted directly (this is the element the user actually sees). */
    section[data-testid="stSidebar"] .stCheckbox label div,
    section[data-testid="stSidebar"] .stCheckbox label p,
    section[data-testid="stSidebar"] .stRadio label div,
    section[data-testid="stSidebar"] .stRadio label p {
        font-size:11px !important; line-height:1.15 !important; min-height:0 !important; }
    section[data-testid="stSidebar"] label { white-space:nowrap; }
    /* ---- checkboxes rendered as compact pill toggles (indigo when selected) ---- */
    section[data-testid="stSidebar"] .stCheckbox > label {
        display:flex; align-items:center; justify-content:center; gap:3px;
        background:var(--surface); border:1px solid var(--line); border-radius:6px;
        padding:2px 6px; line-height:1.15; cursor:pointer;
        transition:background .12s ease, border-color .12s ease; }
    section[data-testid="stSidebar"] .stCheckbox > label:hover { border-color:#FBC0A0; }
    section[data-testid="stSidebar"] .stCheckbox > label > span:first-child { display:none !important; }
    section[data-testid="stSidebar"] .stCheckbox:has(input:checked) > label {
        background:var(--accent); border-color:var(--accent); }
    section[data-testid="stSidebar"] .stCheckbox:has(input:checked) > label div,
    section[data-testid="stSidebar"] .stCheckbox:has(input:checked) > label p { color:#fff !important; }
    section[data-testid="stSidebar"] .stCheckbox { margin-bottom:.16rem; }
    /* ---- Tenant / Company radio → matching segmented pills ---- */
    section[data-testid="stSidebar"] div[role="radiogroup"] { flex-direction:row; gap:.5rem; }
    section[data-testid="stSidebar"] div[role="radiogroup"] > label {
        flex:1; display:flex; align-items:center; justify-content:center;
        background:var(--surface); border:1px solid var(--line); border-radius:8px;
        padding:4px 10px; margin:0; cursor:pointer;
        transition:background .12s ease, border-color .12s ease; }
    section[data-testid="stSidebar"] div[role="radiogroup"] > label:hover { border-color:#FBC0A0; }
    section[data-testid="stSidebar"] div[role="radiogroup"] > label > div:first-child { display:none !important; }
    section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {
        background:var(--accent); border-color:var(--accent); }
    section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) div,
    section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) p { color:#fff !important; }
    section[data-testid="stSidebar"] .stSlider { padding-bottom:.12rem; }
    /* SYSTEM ONLINE status footer */
    .sys-status { display:flex; align-items:center; gap:7px; font-size:.66rem; font-weight:700;
        letter-spacing:.06em; text-transform:uppercase; color:var(--muted); margin-top:1.1rem; }
    .sys-status .sys-dot { width:8px; height:8px; border-radius:50%; background:var(--rented);
        box-shadow:0 0 0 3px rgba(5,150,105,.18); }
    section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p { font-size:.7rem; }
    section[data-testid="stSidebar"] .streamlit-expanderHeader { font-size:.75rem; }

    /* the invisible JS-injector component takes no space */
    iframe[title="st.iframe"] { display:block; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Inject the (once-embedded) photo background-image classes
st.markdown(media.photo_css(), unsafe_allow_html=True)


@cache_data
def _price_bounds():
    return database.price_bounds()


@cache_data
def _size_bounds():
    return database.size_bounds()


# ---------------------------------------------------------------------------
# Sidebar — every control visible at a glance
# ---------------------------------------------------------------------------
sb = st.sidebar
sb.markdown("<div class='sb-title'>Filters 篩選</div>", unsafe_allow_html=True)

sb.markdown("<div class='sb-h sb-h-tight'>View mode 檢視模式</div>", unsafe_allow_html=True)
view_mode = sb.radio(" ", ["Tenant", "Company"], key="view_mode",
                     format_func=lambda x: {"Tenant": "Tenant 租客", "Company": "Company 公司"}[x])

sb.markdown("<div class='sb-h sb-h-sp'>Status 狀態</div>", unsafe_allow_html=True)
_stc = sb.columns(2)
sel_statuses = []
if _stc[0].checkbox("🟡 Available 待租", value=True, key="st_avail"):
    sel_statuses.append("Available")
if _stc[1].checkbox("🟢 Rented 已租", value=True, key="st_rented"):
    sel_statuses.append("Rented")

sb.markdown("<div class='sb-h sb-h-sp'>City 城市</div>", unsafe_allow_html=True)
_cityl = {"Taipei City": "Taipei 台北", "New Taipei City": "New Taipei 新北"}
_cc = sb.columns(2)
sel_cities = [c for i, c in enumerate(config.CITIES)
              if _cc[i % 2].checkbox(_cityl[c], value=True, key=f"city_{c}")]

sb.markdown("<div class='sb-h sb-h-sp'>District 行政區</div>", unsafe_allow_html=True)
sel_districts = []
_dc = sb.columns(2)
_di = 0
for d in config.districts():
    if config.DISTRICT_PROFILE[d]["city"] not in sel_cities:
        continue
    _zh = config.DISTRICT_PROFILE[d]["name_zh"].replace("區", "")
    if _dc[_di % 2].checkbox(f"{d} {_zh}", value=True, key=f"dist_{d}"):
        sel_districts.append(d)
    _di += 1

sb.markdown("<div class='sb-h'>Monthly rent 月租 (NT&#36;)</div>", unsafe_allow_html=True)
pmin, pmax = _price_bounds()
price_range = sb.slider(" ", min_value=pmin, max_value=pmax, value=(pmin, pmax),
                        step=500, format="%d", key="f_price")

sb.markdown("<div class='sb-h sb-h-sp'>Room type 房型</div>", unsafe_allow_html=True)
sel_rooms = []
_roomzh = {"Studio": "套房", "1BR": "一房", "2BR": "二房", "3BR": "三房", "4BR+": "四房"}
_rc = sb.columns(3)
for _j, _r in enumerate(config.ROOM_TYPES.keys()):
    if _rc[_j % 3].checkbox(f"{_r} {_roomzh.get(_r, '')}", value=True, key=f"room_{_r}"):
        sel_rooms.append(_r)

sb.markdown("<div class='sb-h'>Size 坪數 (ping)</div>", unsafe_allow_html=True)
smin, smax = _size_bounds()
size_range = sb.slider("  ", min_value=float(smin), max_value=float(smax),
                       value=(float(smin), float(smax)), step=1.0, key="f_size")

sb.markdown("<div class='sb-h'>Max MRT walk 捷運步行 (min)</div>", unsafe_allow_html=True)
max_mrt = sb.slider("   ", min_value=1, max_value=20, value=20, key="f_mrt")

with sb.expander("MRT line colours · data notes"):
    st.caption(
        "  \n".join(f"<span class='dot' style='background:{color}'></span>{name}"
                    for name, color in mrt.legend()),
        unsafe_allow_html=True)
    st.caption("⚠️ All data is randomly generated for this demo. Photos are royalty-free "
               "stock images — no real listings or company data. MRT geometry: open data.")

# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------
df = database.query_listings(
    cities=sel_cities or None, districts=sel_districts or None, price_range=price_range,
    room_types=sel_rooms or None, size_range=size_range,
    max_mrt_min=max_mrt if max_mrt < 20 else None,
    statuses=sel_statuses or None,
)

sb.markdown(
    f"<div class='sys-status'><span class='sys-dot'></span>System online 系統上線 · {len(df)} listings 物件</div>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Brand header + KPI tiles
# ---------------------------------------------------------------------------
LOGO_SVG = (
    '<svg width="38" height="38" viewBox="0 0 38 38" xmlns="http://www.w3.org/2000/svg">'
    '<rect width="38" height="38" rx="11" fill="#FB6E3B"/>'
    # folded map (unmistakably a map, not a house)
    '<path d="M7 13.2 15 10.4 23 13.2 31 10.4 31 24.8 23 27.6 15 24.8 7 27.6Z" fill="#fff"/>'
    # fold creases
    '<path d="M15 10.4V24.8M23 13.2V27.6" stroke="#FB6E3B" stroke-width="1.1" stroke-linecap="round" opacity=".35"/>'
    # location pin dropped on the map
    '<path d="M19 13.5c-1.93 0-3.5 1.53-3.5 3.4 0 2.55 3.5 5.7 3.5 5.7s3.5-3.15 3.5-5.7c0-1.87-1.57-3.4-3.5-3.4z" fill="#FB6E3B"/>'
    '<circle cx="19" cy="16.9" r="1.2" fill="#fff"/>'
    '</svg>'
)

st.markdown(
    "<div class='topbar'>"
    f"<div class='brand'>{LOGO_SVG}<div>"
    "<div class='brand-name'>Taipei Rental GIS <span class='thin'>Dashboard</span></div>"
    "<div class='brand-sub'>Greater Taipei · interactive rental map</div>"
    "</div></div>"
    "<div class='brand-right'><span class='demo-pill'>Synthetic demo</span><br>"
    "Data-Driven Portfolio · <b>Wayne Liu</b></div>"
    "</div>",
    unsafe_allow_html=True,
)

n_avail = int((df["status"] == "Available").sum()) if not df.empty else 0
n_rented = int((df["status"] == "Rented").sum()) if not df.empty else 0

k1, k2, k3, k4 = st.columns(4)
k1.markdown(
    "<div class='kpi-split'>"
    "<div class='ks-label'>Listings 物件 · Available / Rented</div>"
    "<div class='ks-val'>"
    f"<span class='ks-a'><span class='ks-dot'>●</span>{n_avail}</span>"
    "<span class='ks-slash'>/</span>"
    f"<span class='ks-r'><span class='ks-dot'>●</span>{n_rented}</span>"
    "</div></div>",
    unsafe_allow_html=True,
)
k2.metric("Median rent 中位租金", f"NT$ {int(df['price'].median()):,}" if not df.empty else "—")
k3.metric("Avg. size 平均坪數", f"{df['size_ping'].mean():.1f} ping" if not df.empty else "—")
k4.metric("Avg. MRT walk 平均步行", f"{df['mrt_min'].mean():.0f} min" if not df.empty else "—")
st.markdown("")

# ---------------------------------------------------------------------------
# Map — pure Leaflet; interactions never rerun Python
# ---------------------------------------------------------------------------
# Colourful, Google-Roadmap-like base (CartoDB Voyager)
VOYAGER_TILES = "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
VOYAGER_ATTR = ('&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> '
                '&copy; <a href="https://carto.com/attributions">CARTO</a>')


def house_pin(status_color: str, lid: int) -> folium.DivIcon:
    """Black rounded-square marker with a white house glyph and a small
    Available/Rented status dot — the interaction/feature is unchanged."""
    html = (
        f'<div onclick="event.stopPropagation();parent.__showLM({lid})" '
        f'style="position:absolute;cursor:pointer;transform:translate(-50%,-50%);'
        f'filter:drop-shadow(0 2px 3px rgba(0,0,0,.4));">'
        f'<svg width="30" height="30" viewBox="0 0 30 30" xmlns="http://www.w3.org/2000/svg">'
        f'<rect x="1.5" y="1.5" width="27" height="27" rx="8.5" fill="#141414"/>'
        f'<path d="M15 8 L22 13.6 V22 H16.7 V16.9 H13.3 V22 H8 V13.6 Z" fill="#fff"/>'
        f'<circle cx="24" cy="6" r="3.9" fill="{status_color}" stroke="#fff" stroke-width="1.5"/>'
        f'</svg></div>')
    return folium.DivIcon(html=html, icon_size=(0, 0), icon_anchor=(0, 0))


col_map, col_list = st.columns([2.05, 1])

with col_map:
    fmap = folium.Map(location=list(config.MAP_CENTER), zoom_start=config.DEFAULT_ZOOM,
                      tiles=VOYAGER_TILES, attr=VOYAGER_ATTR,
                      control_scale=True, prefer_canvas=True)
    mrt.add_mrt_layer(fmap)     # Taipei MRT lines (under the listing markers)
    mrt.add_mrt_stations(fmap)  # station dots on top of the lines
    cluster = MarkerCluster(disableClusteringAtZoom=15).add_to(fmap)
    for r in df.itertuples():
        folium.Marker(
            location=[r.lat, r.lon],
            icon=house_pin(config.status_color(r.status), int(r.id)),
            tooltip=f"{r.room_type} · NT$ {r.price:,} · {r.district} · {r.status}",
        ).add_to(cluster)
    # Watch only `all_drawings` (always null here): the component's value never
    # changes, so pan/zoom NEVER rerun Python. Cards react client-side instead.
    st_folium(fmap, width=None, height=630, key="map", returned_objects=["all_drawings"])

with col_list:
    st.markdown(
        "<div class='stays-head'><span id='stays-count'>Loading…</span></div>"
        "<div class='stays-sub'>Updates live as you move the map · click a card for details<br>移動地圖即時更新，點擊卡片查看細節</div>"
        "<div id='cards-list'></div><div id='cards-note'></div>",
        unsafe_allow_html=True,
    )
    if df.empty:
        st.info("No listings match the current filters. Try widening them.")

# ---------------------------------------------------------------------------
# Modal shell + client-side injector (cards, modal, view persistence)
# ---------------------------------------------------------------------------
st.markdown('<div class="modal-backdrop" id="lm-backdrop"></div>'
            '<div class="listing-modal" id="lm-shell"></div>', unsafe_allow_html=True)

payload = {}
for r in df.itertuples():
    payload[int(r.id)] = {
        "lat": float(r.lat), "lon": float(r.lon), "price": int(r.price),
        "rt": r.room_type, "d": r.district, "dz": r.district_zh, "city": r.city,
        "addr": r.address, "ping": float(r.size_ping), "up": int(r.unit_price),
        "mrt": int(r.mrt_min), "bed": int(r.bedrooms), "bath": int(r.bathrooms),
        "bt": r.building_type, "fl": int(r.floor), "tfl": int(r.total_floors),
        "ren": int(r.renovation_age), "elev": int(r.has_elevator),
        "park": int(r.has_parking), "pet": int(r.pet_allowed), "sub": int(r.subsidy_eligible),
        "st": r.status, "oc": float(r.owner_contract_years_left),
        "ft": [f for f in str(r.features).split("|") if f],
        "ll": r.landlord, "ph": r.phone, "pd": r.posted_date, "band": r.price_band,
        "pn": media.photo_number(int(r.id), r.room_type),
    }

st.session_state["_nonce"] = st.session_state.get("_nonce", 0) + 1

INJECTOR_JS = r"""
/* gis-injector nonce __NONCE__ */
(function () {
  var doc = window.parent.document;
  var LISTINGS = __LISTINGS__;
  var MODE = "__MODE__";
  var CAP = __CAP__;
  var SCOLOR = __SCOLOR__;
  var SZH = __SZH__;
  var BAND = __BAND__;

  function money(n) { return Number(n).toLocaleString('en-US'); }

  function cardHTML(id) {
    var s = LISTINGS[id];
    // hashtag chips synthesised from the listing's own fields
    var tags = ['#' + s.mrt + 'min to MRT'];
    if (s.sub) tags.push('#Rent subsidy 可租補');
    s.ft.slice(0, 2).forEach(function (f) { tags.push('#' + f); });
    var badge = (s.ren <= 1) ? '<span class="pc-badge">✨ Newly renovated</span>' : '';
    return '<div class="property-card" data-lid="' + id + '">'
      + '<div class="pc-photo listing-photo-' + s.pn + '">'
      + '<span class="pc-status" style="background:' + SCOLOR[s.st] + '">' + s.st + ' ' + SZH[s.st] + '</span>'
      + '<span class="pc-heart">♡</span></div>'
      + '<div class="pc-body">'
      + '<div class="pc-top"><div class="pc-top-l">'
      + '<span class="pc-tag">' + s.d + ' ' + s.dz.replace('區', '') + '</span>' + badge + '</div>'
      + '<span class="pc-price">NT$ ' + money(s.price) + '</span></div>'
      + '<div class="pc-room">' + s.rt
      + '<span class="pc-room-sub"> · ' + (s.bed > 0 ? s.bed + ' bed / ' : '') + s.bath + ' bath</span></div>'
      + '<div class="pc-addr">📍 ' + s.addr + '</div>'
      + '<div class="pc-stats">'
      + '<div><span>Size 空間</span><b>' + s.ping + ' ping 坪</b></div>'
      + '<div><span>Walk 步行</span><b>' + s.mrt + ' min</b></div></div>'
      + '<div class="pc-tags">' + tags.map(function (t) { return '<span class="pc-hash">' + t + '</span>'; }).join('') + '</div>'
      + '</div></div>';
  }

  function modalHTML(id) {
    var s = LISTINGS[id];
    var yn = function (v) { return v ? 'Yes' : 'No'; };
    var desc = s.rt + ' · ' + s.ping + ' ping in ' + s.d
      + '. <b>' + s.mrt + ' min walk to MRT</b>. '
      + s.ft.map(function (f) { return '<b>' + f + '</b>'; }).join(', ') + '.';
    var company = (MODE === 'Company')
      ? '<div><span>Owner contract left</span>' + s.oc + ' yr</div>' : '';
    return '<span class="modal-close-x">✕</span>'
      + '<div class="modal-photo listing-photo-' + s.pn + '">'
      + '<span class="modal-status" style="background:' + SCOLOR[s.st] + '">'
      + s.st + ' · ' + SZH[s.st] + '</span></div>'
      + '<div class="modal-body">'
      + '<div class="modal-head"><div>'
      + '<div class="modal-title">' + s.rt + ' · ' + s.d
      + ' <span class="modal-zh">' + s.dz + ' · ' + s.city + '</span></div>'
      + '<div class="modal-addr">📍 ' + s.addr + '</div></div>'
      + '<div class="modal-price">NT$ ' + money(s.price)
      + '<div class="modal-permo">per month</div></div></div>'
      + '<div class="modal-stats">'
      + '<div><b>' + s.ping + '</b><span>ping</span></div>'
      + '<div><b>' + money(s.up) + '</b><span>NT$/ping</span></div>'
      + '<div><b>' + s.mrt + ' min</b><span>to MRT</span></div>'
      + '<div><b>' + s.bed + '/' + s.bath + '</b><span>bed/bath</span></div></div>'
      + '<div class="modal-grid">'
      + '<div><span>Building</span>' + s.bt + '</div>'
      + '<div><span>Floor</span>' + s.fl + '/' + s.tfl + '</div>'
      + '<div><span>Renovated</span>' + s.ren + ' yr ago</div>'
      + '<div><span>Elevator / Parking</span>' + yn(s.elev) + ' / ' + yn(s.park) + '</div>'
      + '<div><span>Pets</span>' + (s.pet ? 'Allowed' : 'Not allowed') + '</div>'
      + '<div><span>Rent subsidy</span>' + (s.sub ? 'Eligible' : 'No') + '</div>'
      + company + '</div>'
      + '<div class="modal-desc">' + desc + '</div>'
      + '<div class="modal-contact">Contact (fake): ' + s.ll + ' · ' + s.ph
      + ' · listed ' + s.pd + '</div></div>';
  }

  window.parent.__showLM = function (id) {
    var shell = doc.getElementById('lm-shell');
    var bd = doc.getElementById('lm-backdrop');
    if (!shell || !LISTINGS[id]) return;
    shell.innerHTML = modalHTML(id);
    shell.scrollTop = 0;
    shell.classList.add('lm-open');
    if (bd) bd.classList.add('lm-open');
  };
  window.parent.__hideLM = function () {
    var shell = doc.getElementById('lm-shell');
    var bd = doc.getElementById('lm-backdrop');
    if (shell) shell.classList.remove('lm-open');
    if (bd) bd.classList.remove('lm-open');
  };

  var bd = doc.getElementById('lm-backdrop');
  if (bd) bd.onclick = window.parent.__hideLM;
  var shell = doc.getElementById('lm-shell');
  if (shell) shell.onclick = function (e) {
    if (e.target.classList.contains('modal-close-x')) window.parent.__hideLM();
  };
  doc.onkeydown = function (e) { if (e.key === 'Escape') window.parent.__hideLM(); };

  var list = doc.getElementById('cards-list');
  if (list) list.onclick = function (e) {
    var c = e.target.closest('.property-card');
    if (c) window.parent.__showLM(c.getAttribute('data-lid'));
  };

  function findMap() {
    var res = null;
    doc.querySelectorAll('iframe').forEach(function (f) {
      // only consider iframes that are attached AND visible (a stale, replaced
      // component iframe must never win over the on-screen map)
      if (!f.isConnected || f.offsetParent === null) return;
      try {
        var w = f.contentWindow;
        var k = Object.keys(w).find(function (x) { return x.indexOf('map_') === 0; });
        if (k) res = w[k];
      } catch (err) {}
    });
    return res;
  }

  function renderCards(map) {
    var listEl = doc.getElementById('cards-list');
    var countEl = doc.getElementById('stays-count');
    var noteEl = doc.getElementById('cards-note');
    if (!listEl || !map) return;
    var b = map.getBounds();
    var ids = Object.keys(LISTINGS).filter(function (id) {
      var s = LISTINGS[id];
      return b.contains([s.lat, s.lon]);
    });
    ids.sort(function (a, c) { return LISTINGS[a].price - LISTINGS[c].price; });
    if (countEl) countEl.textContent = ids.length + ' stays in view';
    if (!ids.length) {
      listEl.innerHTML = '<div class="cards-empty">No listings in the current map view — pan or zoom out.</div>';
      if (noteEl) noteEl.textContent = '';
      return;
    }
    listEl.innerHTML = ids.slice(0, CAP).map(cardHTML).join('');
    if (noteEl) noteEl.textContent = ids.length > CAP
      ? 'Showing the ' + CAP + ' cheapest of ' + ids.length + ' in view — zoom in to narrow.'
      : '';
  }

  function boot(tries) {
    var map = findMap();
    if (!map) { if (tries > 0) setTimeout(function () { boot(tries - 1); }, 300); return; }
    map.whenReady(function () {
      try {
        var saved = sessionStorage.getItem('gisView');
        if (saved) {
          var v = JSON.parse(saved);
          map.setView(v.c, v.z, { animate: false });
        }
      } catch (err) {}
      // detach the PREVIOUS injector's handler first (it closes over stale
      // data), then attach this run's
      if (map.__gisHandler) map.off('moveend zoomend', map.__gisHandler);
      map.__gisHandler = function () {
        try {
          sessionStorage.setItem('gisView', JSON.stringify(
            { c: [map.getCenter().lat, map.getCenter().lng], z: map.getZoom() }));
        } catch (err) {}
        renderCards(map);
      };
      map.on('moveend zoomend', map.__gisHandler);
      renderCards(map);
      setTimeout(function () { renderCards(map); }, 800);
    });
  }
  boot(40);
})();
"""

_js = (INJECTOR_JS
       .replace("__NONCE__", str(st.session_state["_nonce"]))
       .replace("__LISTINGS__", json.dumps(payload, ensure_ascii=False))
       .replace("__MODE__", view_mode)
       .replace("__CAP__", str(CARD_CAP))
       .replace("__SCOLOR__", json.dumps(config.STATUS_COLOR))
       .replace("__SZH__", json.dumps(config.STATUS_ZH, ensure_ascii=False))
       .replace("__BAND__", json.dumps({n: c for n, _, _, c in config.PRICE_BANDS})))

components.html("<script>" + _js + "</script>", height=0)
