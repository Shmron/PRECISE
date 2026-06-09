import streamlit as st
import sys
import os

sys.path.insert(0, '/home/rutendo/PRECISE/palsearth')

st.set_page_config(page_title="Help & Shmron AI — PALSearth",
                   page_icon="💬", layout="wide")

from core.ui import inject_css, render_sidebar, render_chat_fab
inject_css()

# Auth guard
if "username" not in st.session_state or not st.session_state["username"]:
    st.switch_page("app.py")

render_sidebar(active="help")

from core.datasets import DATASETS

# ── Page header ────────────────────────────────────────────────────────────────
st.markdown("""
<p class="pe-page-title">💬 Help &amp; Shmron AI</p>
<p class="pe-page-sub">Ask questions, explore datasets, and get answers powered by Claude.</p>
""", unsafe_allow_html=True)

tab_ai, tab_ref = st.tabs(["  Shmron AI  ", "  Dataset Reference  "])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — SHMRON AI CHAT
# ══════════════════════════════════════════════════════════════════════════════
with tab_ai:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    anthropic_ok = False
    try:
        import anthropic
        anthropic_ok = True
    except ImportError:
        pass

    if not anthropic_ok:
        st.error("`anthropic` package not installed. Run `pip install anthropic`.")
    elif not api_key:
        st.error("No `ANTHROPIC_API_KEY` found. Contact the admin.")
    else:
        SYSTEM_PROMPT = (
            "You are Shmron AI, the intelligent assistant for PALSearth — a "
            "geospatial data extraction platform built for researchers at PALS Lab "
            "(Place Alert & Landscape Systems), part of the PRECISE project.\n\n"
            "You help users with:\n"
            "- Using PALSearth (uploading files, selecting datasets, understanding outputs)\n"
            "- Geospatial datasets available in PALSearth:\n"
            "  * MODIS NDVI (500m daily timeseries)\n"
            "  * CHIRPS precipitation (5km daily, ~2-month lag)\n"
            "  * ERA5-Land temperature (11km hourly->daily)\n"
            "  * MERRA-2 wet bulb temperature (T2M and T2MWET bands)\n"
            "  * CAMS NRT air quality — PM2.5, NO2, O3, CO, SO2, Black Carbon, AOD (~44km daily)\n"
            "  * MERIT DEM elevation (90m static)\n"
            "  * iSDAsoil nitrogen, phosphorus, potassium, calcium (250m/30m, Africa only)\n"
            "  * GHSL Urban Settlement Model 2025 (1km static, mode of smod_code: 22-30=Urban, 14-21=Peri-urban, 11-13=Rural)\n"
            "  * Facebook/Meta Relative Wealth Index (1km static)\n"
            "- Google Earth Engine concepts and best practices\n"
            "- Interpreting wide-format extraction outputs (date + location attributes "
            "+ one column per extracted variable)\n"
            "- Troubleshooting empty values, date ranges, coordinate issues\n"
            "- CAMS air quality units: PM2.5 in kg/m³, NO2/O3/CO/SO2 in kg/m², "
            "Black Carbon and AOD are dimensionless optical depth.\n\n"
            "Be concise, practical, and friendly. Use plain language. "
            "When users ask about CHIRPS data gaps, remind them of the ~2-month lag. "
            "When users ask about GHSL, explain the smod_code classification scheme."
        )

        if "chat_history" not in st.session_state:
            st.session_state["chat_history"] = []

        # ── Welcome / empty state ──────────────────────────────────────────────
        if not st.session_state["chat_history"]:
            st.markdown("""
            <div style="
              background:#fff;
              border:1px solid #e8eaed;
              border-radius:16px;
              padding:2.5rem 2rem;
              text-align:center;
              max-width:560px;
              margin:1.5rem auto;
              box-shadow:0 1px 3px rgba(60,64,67,.07);
            ">
              <div style="font-size:3rem;margin-bottom:.75rem;">🌍</div>
              <div style="font-size:1.15rem;font-weight:700;color:#202124;
                          margin-bottom:.4rem;">
                Hi, I'm Shmron AI
              </div>
              <div style="font-size:.88rem;color:#5f6368;line-height:1.6;
                          margin-bottom:1.5rem;">
                Ask me anything about PALSearth, your datasets,<br>
                extraction outputs, or Earth Engine.
              </div>
              <div style="display:flex;flex-wrap:wrap;gap:.5rem;
                          justify-content:center;">
                <div style="background:#f0faf3;border:1px solid #b7dfbf;
                            border-radius:100px;padding:5px 14px;
                            font-size:.81rem;color:#137333;cursor:default;">
                  What is NDVI?
                </div>
                <div style="background:#f0faf3;border:1px solid #b7dfbf;
                            border-radius:100px;padding:5px 14px;
                            font-size:.81rem;color:#137333;cursor:default;">
                  Why are my CHIRPS values empty?
                </div>
                <div style="background:#f0faf3;border:1px solid #b7dfbf;
                            border-radius:100px;padding:5px 14px;
                            font-size:.81rem;color:#137333;cursor:default;">
                  How do I format my CSV?
                </div>
                <div style="background:#f0faf3;border:1px solid #b7dfbf;
                            border-radius:100px;padding:5px 14px;
                            font-size:.81rem;color:#137333;cursor:default;">
                  What units is ERA5 temperature in?
                </div>
              </div>
            </div>
            """, unsafe_allow_html=True)

        # ── Chat history ───────────────────────────────────────────────────────
        for msg in st.session_state["chat_history"]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        # ── Input ──────────────────────────────────────────────────────────────
        user_input = st.chat_input("Ask Shmron AI anything about PALSearth…")

        if user_input:
            st.session_state["chat_history"].append(
                {"role": "user", "content": user_input}
            )
            with st.chat_message("user"):
                st.markdown(user_input)

            with st.chat_message("assistant"):
                with st.spinner(""):
                    try:
                        client = anthropic.Anthropic(api_key=api_key)
                        response = client.messages.create(
                            model="claude-sonnet-4-6",
                            max_tokens=1024,
                            system=SYSTEM_PROMPT,
                            messages=st.session_state["chat_history"],
                        )
                        reply = response.content[0].text
                        st.markdown(reply)
                        st.session_state["chat_history"].append(
                            {"role": "assistant", "content": reply}
                        )
                    except Exception as e:
                        err = f"Shmron AI error: {e}"
                        st.error(err)
                        st.session_state["chat_history"].append(
                            {"role": "assistant", "content": err}
                        )

        # ── Clear button ───────────────────────────────────────────────────────
        if st.session_state.get("chat_history"):
            st.markdown(" ")
            if st.button("Clear conversation", key="clear_chat"):
                st.session_state["chat_history"] = []
                st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — DATASET REFERENCE
# ══════════════════════════════════════════════════════════════════════════════
with tab_ref:
    st.markdown("""
    <p class="pe-page-sub" style="margin-bottom:1.25rem;">
      All datasets available in PALSearth, extracted via Google Earth Engine
      using the PALSearth service account — no EE credentials required from users.
    </p>
    """, unsafe_allow_html=True)

    # ── Quick usage guide ──────────────────────────────────────────────────────
    st.markdown("""
    <div class="pe-card" style="margin-bottom:1.25rem;">
      <div style="font-weight:600;font-size:.97rem;margin-bottom:.85rem;color:#202124;">
        ⚡ How to use PALSearth
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:.75rem;">
        <div style="background:#f8f9fa;border-radius:10px;padding:.875rem 1rem;">
          <div style="font-weight:600;font-size:.85rem;color:#0d5c2e;margin-bottom:.3rem;">
            1 · Upload locations
          </div>
          <div style="font-size:.81rem;color:#5f6368;line-height:1.5;">
            CSV with <code>latitude</code> / <code>longitude</code> columns,
            or a zipped shapefile (.shp + .dbf + .shx).
          </div>
        </div>
        <div style="background:#f8f9fa;border-radius:10px;padding:.875rem 1rem;">
          <div style="font-weight:600;font-size:.85rem;color:#0d5c2e;margin-bottom:.3rem;">
            2 · Pick datasets &amp; stats
          </div>
          <div style="font-size:.81rem;color:#5f6368;line-height:1.5;">
            Select one or more datasets. Timeseries datasets need a date range.
            Choose mean, min, max, or percentiles.
          </div>
        </div>
        <div style="background:#f8f9fa;border-radius:10px;padding:.875rem 1rem;">
          <div style="font-weight:600;font-size:.85rem;color:#0d5c2e;margin-bottom:.3rem;">
            3 · Submit &amp; wait
          </div>
          <div style="font-size:.81rem;color:#5f6368;line-height:1.5;">
            Jobs run in the background. Visit <strong>My Jobs</strong> to track
            progress — the page auto-refreshes every 10 seconds.
          </div>
        </div>
        <div style="background:#f8f9fa;border-radius:10px;padding:.875rem 1rem;">
          <div style="font-weight:600;font-size:.85rem;color:#0d5c2e;margin-bottom:.3rem;">
            4 · Download results
          </div>
          <div style="font-size:.81rem;color:#5f6368;line-height:1.5;">
            Output is wide-format: <code>date</code> + your location attributes +
            one column per extracted variable. Available as CSV or Parquet.
          </div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Dataset table ──────────────────────────────────────────────────────────
    st.markdown("""
    <div style="font-weight:600;font-size:.97rem;margin-bottom:.85rem;color:#202124;">
      📦 Available datasets
    </div>
    """, unsafe_allow_html=True)

    DS_ICONS = {
        "NDVI (MODIS)":                      ("🌿", "#e6f4ea"),
        "Precipitation - CHIRPS":            ("🌧️",  "#e8f0fe"),
        "Temperature - ERA5-Land":           ("🌡️",  "#fef7e0"),
        "Temperature + Wet Bulb - MERRA-2":  ("💧",  "#e8f0fe"),
        "Air Quality - CAMS NRT":            ("🏭",  "#fce8e6"),
        "Elevation - MERIT DEM":             ("⛰️",  "#f3e8fd"),
        "Soil Nitrogen (iSDAsoil)":          ("🌱",  "#e6f4ea"),
        "Soil Phosphorus (iSDAsoil)":        ("🌱",  "#e6f4ea"),
        "Soil Potassium (iSDAsoil)":         ("🌱",  "#e6f4ea"),
        "Soil Calcium (iSDAsoil)":           ("🌱",  "#e6f4ea"),
        "Urban Settlement - GHSL":           ("🏙️",  "#e8f0fe"),
        "Relative Wealth Index (Facebook)":  ("💰",  "#fef7e0"),
    }

    rows_html = ""
    for name, info in DATASETS.items():
        is_ts       = info["type"] == "timeseries"
        badge_cls   = "pe-chip-blue" if is_ts else "pe-chip-purple"
        badge_label = "Timeseries" if is_ts else "Static"
        icon, bg    = DS_ICONS.get(name, ("📊", "#f1f3f4"))
        band_disp   = (
            ", ".join(info["band"]) if isinstance(info["band"], list)
            else info["band"]
        )
        rows_html += f"""
        <div class="docs-ds-row">
          <div class="docs-ds-icon" style="background:{bg};">{icon}</div>
          <div style="flex:1;min-width:0;">
            <div style="display:flex;align-items:center;gap:.5rem;flex-wrap:wrap;">
              <span class="docs-ds-name">{name}</span>
              <span class="pe-chip {badge_cls}">{badge_label}</span>
            </div>
            <div class="docs-ds-desc">{info['description']}</div>
            <div class="docs-ds-meta">
              collection: {info['collection']} &nbsp;·&nbsp;
              band: {band_disp} &nbsp;·&nbsp;
              scale: {info['scale']} m
            </div>
          </div>
        </div>
        """

    st.markdown(f"""
    <div class="docs-card">{rows_html}</div>
    """, unsafe_allow_html=True)

    # ── Notes ──────────────────────────────────────────────────────────────────
    st.markdown("""
    <div class="pe-info-block" style="margin-top:1rem;">
      <strong>Notes:</strong>
      CHIRPS has a ~2-month data lag — recent dates will return empty values.
      iSDAsoil datasets cover Africa only.
      All extractions use the PALSearth service account; no personal Earth Engine
      credentials are needed.
    </div>
    """, unsafe_allow_html=True)

render_chat_fab()
