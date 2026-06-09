import streamlit as st
import sys
import os

sys.path.insert(0, '/home/rutendo/PRECISE/palsearth')

st.set_page_config(
    page_title="PALSearth",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)

from core.ui import inject_css, render_sidebar, render_chat_fab

inject_css()


# ── Auth guard / router ────────────────────────────────────────────────────────
def show_auth():
    # Hide sidebar on auth page
    st.markdown("<style>[data-testid='stSidebar']{display:none}</style>",
                unsafe_allow_html=True)

    col_l, col_c, col_r = st.columns([1, 1.6, 1])
    with col_c:
        st.markdown("""
        <div class="auth-wrap">
          <div class="auth-logo">
            <div class="logo-icon">🌍</div>
            <div class="logo-name">PALSearth</div>
            <div class="logo-sub">Geospatial Data Extraction · PALS Lab</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        tab_in, tab_reg = st.tabs(["  Sign in  ", "  Create account  "])

        with tab_in:
            st.markdown(" ")
            with st.form("login_form", clear_on_submit=False):
                username = st.text_input("Username", placeholder="your_username")
                password = st.text_input("Password", type="password",
                                         placeholder="••••••••")
                submitted = st.form_submit_button("Sign in", type="primary",
                                                  use_container_width=True)

            if submitted:
                if not username or not password:
                    st.error("Enter both username and password.")
                else:
                    from core.auth import login
                    ok, msg = login(username, password)
                    if ok:
                        st.session_state["username"] = username
                        st.rerun()
                    else:
                        st.error(msg)

            st.markdown("""
            <p style="text-align:center;font-size:.8rem;color:#80868b;margin-top:1.25rem;">
              Use the same credentials as PALS Hub (JupyterHub).
            </p>
            """, unsafe_allow_html=True)

        with tab_reg:
            st.markdown(" ")
            with st.form("reg_form", clear_on_submit=True):
                nu = st.text_input("Username", placeholder="choose_username",
                                   key="ru")
                ne = st.text_input("Email", placeholder="you@institution.ac.uk",
                                   key="re")
                np1 = st.text_input("Password", type="password",
                                    placeholder="min 8 characters", key="rp1")
                np2 = st.text_input("Confirm password", type="password",
                                    placeholder="repeat password", key="rp2")
                reg_go = st.form_submit_button("Create account", type="primary",
                                               use_container_width=True)

            if reg_go:
                if not all([nu, ne, np1, np2]):
                    st.error("All fields are required.")
                elif np1 != np2:
                    st.error("Passwords do not match.")
                elif len(np1) < 8:
                    st.error("Password must be at least 8 characters.")
                else:
                    from core.auth import register
                    ok, msg = register(nu, np1, ne)
                    if ok:
                        st.markdown("""
                        <div class="pe-success-block">
                          Account created — pending admin approval.
                          Once approved you can sign in above.
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.error(msg)

        st.markdown("""
        <p style="text-align:center;font-size:.78rem;color:#9aa0a6;margin-top:2rem;">
          © PALS Lab · PRECISE Project ·
          <a href="https://placealert.org" style="color:#0d5c2e;text-decoration:none;">
            placealert.org
          </a>
        </p>
        """, unsafe_allow_html=True)


def show_home():
    render_sidebar(active="home")
    username = st.session_state.get("username", "")

    st.markdown("""
    <div style="
      background: linear-gradient(135deg, #0a4520 0%, #0d5c2e 55%, #1a8a40 100%);
      border-radius: 16px;
      padding: 2.25rem 2.5rem;
      margin-bottom: 1.75rem;
      box-shadow: 0 4px 16px rgba(13,92,46,.25);
    ">
      <div style="display:flex;align-items:center;gap:1rem;margin-bottom:.5rem;">
        <span style="font-size:2.2rem;">🌍</span>
        <span style="font-size:1.85rem;font-weight:700;color:#fff;
                     font-family:'Google Sans',sans-serif;letter-spacing:-.01em;">
          PALSearth
        </span>
      </div>
      <p style="color:#a7dab8;margin:0;font-size:.96rem;max-width:580px;line-height:1.55;">
        Extract geospatial indicators from Google Earth Engine for your research
        locations — NDVI, rainfall, temperature, soil properties, elevation and more.
      </p>
    </div>
    """, unsafe_allow_html=True)

    # ── Feature cards (styled buttons — preserves session state) ──
    # Inject card-button styles scoped to this page only
    st.markdown("""
    <style>
    div[data-testid="stColumns"] [data-testid="stButton"] > button {
      background: #fff !important;
      border: 1px solid #e8eaed !important;
      border-radius: 16px !important;
      padding: 1.75rem 1.5rem !important;
      min-height: 185px !important;
      text-align: center !important;
      box-shadow: 0 1px 3px rgba(60,64,67,.07) !important;
      transition: transform .2s, box-shadow .2s, border-color .15s !important;
      width: 100% !important;
    }
    div[data-testid="stColumns"] [data-testid="stButton"] > button:hover {
      transform: translateY(-3px) !important;
      box-shadow: 0 6px 18px rgba(60,64,67,.14) !important;
      border-color: #0d5c2e !important;
      background: #fff !important;
    }
    div[data-testid="stColumns"] [data-testid="stButton"] > button p:nth-child(1) {
      font-size: 2.2rem !important;
      margin: 0 0 .75rem 0 !important;
      line-height: 1 !important;
    }
    div[data-testid="stColumns"] [data-testid="stButton"] > button p:nth-child(2) {
      font-size: 1rem !important;
      font-weight: 600 !important;
      color: #202124 !important;
      margin: 0 0 .35rem 0 !important;
    }
    div[data-testid="stColumns"] [data-testid="stButton"] > button p:nth-child(3) {
      font-size: .83rem !important;
      color: #5f6368 !important;
      font-weight: 400 !important;
      line-height: 1.5 !important;
      margin: 0 !important;
    }
    </style>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3, gap="medium")
    with c1:
        if st.button(
            "🗺️\n\nExtract Data\n\nUpload locations, pick datasets and submit a background extraction job.",
            key="nav_extract", use_container_width=True
        ):
            st.switch_page("pages/1_Extract.py")

    with c2:
        if st.button(
            "📋\n\nMy Jobs\n\nTrack extraction progress in real time and download results.",
            key="nav_jobs", use_container_width=True
        ):
            st.switch_page("pages/2_My_Jobs.py")

    with c3:
        if st.button(
            "💬\n\nShmron AI\n\nAsk about datasets, Earth Engine concepts and how to interpret results.",
            key="nav_help", use_container_width=True
        ):
            st.switch_page("pages/3_Help.py")

    st.markdown('<hr class="pe-hr">', unsafe_allow_html=True)

    # ── Supported datasets strip ──
    st.markdown("""
    <p style="font-size:.78rem;font-weight:600;color:#5f6368;
              text-transform:uppercase;letter-spacing:.07em;margin-bottom:.6rem;">
      Supported Datasets
    </p>
    """, unsafe_allow_html=True)

    datasets_meta = [
        ("🌿", "MODIS NDVI",             "Timeseries", "pe-chip-blue"),
        ("🌧️",  "CHIRPS Rainfall",        "Timeseries", "pe-chip-blue"),
        ("🌡️",  "ERA5 Temperature",       "Timeseries", "pe-chip-blue"),
        ("💧",  "MERRA-2 Wet Bulb",       "Timeseries", "pe-chip-blue"),
        ("🏭",  "CAMS Air Quality",       "Timeseries", "pe-chip-blue"),
        ("⛰️",  "MERIT Elevation",        "Static",     "pe-chip-purple"),
        ("🌱",  "iSDAsoil N/P/K/Ca",     "Static",     "pe-chip-purple"),
        ("🏙️",  "GHSL Urban Settlement",  "Static",     "pe-chip-purple"),
        ("💰",  "Wealth Index (Meta)",    "Static",     "pe-chip-purple"),
    ]
    chips_html = "".join(
        f'<span style="display:inline-flex;align-items:center;gap:.35rem;'
        f'background:#fff;border:1px solid #e8eaed;border-radius:100px;'
        f'padding:5px 12px;margin:.2rem;font-size:.82rem;">'
        f'{icon} {name} '
        f'<span class="pe-chip {chip_class}">{badge}</span></span>'
        for icon, name, badge, chip_class in datasets_meta
    )
    st.markdown(f'<div style="line-height:2.2;">{chips_html}</div>',
                unsafe_allow_html=True)

    render_chat_fab()


# ── Router ─────────────────────────────────────────────────────────────────────
if "username" not in st.session_state or not st.session_state["username"]:
    show_auth()
else:
    show_home()
