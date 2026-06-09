import streamlit as st
import sys
import os
import json
import shutil
import tempfile
import zipfile
import pandas as pd

sys.path.insert(0, '/home/rutendo/PRECISE/palsearth')

st.set_page_config(page_title="Extract — PALSearth",
                   page_icon="🗺️", layout="wide")

from core.ui import inject_css, render_sidebar, render_chat_fab
inject_css()

# Auth guard
if "username" not in st.session_state or not st.session_state["username"]:
    st.switch_page("app.py")

render_sidebar(active="extract")
username = st.session_state["username"]
JOBS_DIR = "/home/rutendo/PRECISE/palsearth/jobs"
os.makedirs(JOBS_DIR, exist_ok=True)

from core.datasets import DATASETS

ALL_STATS = ["mean", "min", "max", "p50", "p75", "p95", "p99"]
ee_project = "ee-rutendosibanda18"

# ── Dataset category config ─────────────────────────────────────────────────
CATEGORIES = [
    ("🌿", "Vegetation",    "#e6f4ea", "#137333"),
    ("🌧️",  "Climate",       "#e8f0fe", "#1a73e8"),
    ("🏭",  "Air Quality",   "#fce8e6", "#c5221f"),
    ("⛰️",  "Terrain",       "#f3e8fd", "#7b1fa2"),
    ("🌱",  "Soil",          "#fef7e0", "#b05e00"),
    ("🏙️",  "Urban",         "#e8f0fe", "#1a73e8"),
    ("💰",  "Socioeconomic", "#f0faf3", "#137333"),
]

def detect_lat_lon(df):
    lat_c = ["latitude", "lat", "LAT", "Latitude", "LATITUDE", "y", "Y"]
    lon_c = ["longitude", "lon", "LON", "Longitude", "LONGITUDE",
             "x", "X", "lng", "LNG"]
    lat = next((c for c in lat_c if c in df.columns), None)
    lon = next((c for c in lon_c if c in df.columns), None)
    return lat, lon

# ── State ───────────────────────────────────────────────────────────────────
if "uploaded_ok" not in st.session_state:
    st.session_state["uploaded_ok"] = False
if "geometry_type" not in st.session_state:
    st.session_state["geometry_type"] = None

# ── Page header ─────────────────────────────────────────────────────────────
st.markdown("""
<div style="margin-bottom:1.5rem;">
  <p class="pe-page-title">🗺️ Extract Geospatial Data</p>
  <p class="pe-page-sub">Upload locations · choose datasets · submit a background job · download results.</p>
</div>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# SECTION 1 — UPLOAD
# ════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="pe-section-header">
  <span class="pe-step-num">1</span>
  Upload your locations
</div>
""", unsafe_allow_html=True)

uploaded_file = st.file_uploader(
    "CSV (lat/lon columns) or a zipped shapefile",
    type=["csv", "zip"],
    help="CSV: must have latitude & longitude columns.  "
         "Shapefile: zip the .shp, .dbf, .shx (+ .prj) together.",
    label_visibility="collapsed",
)

input_df_preview = None
geometry_type = None

if uploaded_file is not None:
    fname = uploaded_file.name
    if fname.endswith(".csv"):
        try:
            input_df_preview = pd.read_csv(uploaded_file)
            uploaded_file.seek(0)
            lat_col, lon_col = detect_lat_lon(input_df_preview)
            geometry_type = "points"
            c1, c2 = st.columns([2, 1])
            with c1:
                coord_txt = (
                    f" · Coords: <b>{lat_col}</b> / <b>{lon_col}</b>"
                    if lat_col and lon_col else ""
                )
                st.markdown(f"""
                <div class="pe-success-block">
                  <strong>CSV loaded</strong> — {len(input_df_preview):,} rows,
                  {len(input_df_preview.columns)} columns{coord_txt}
                </div>
                """, unsafe_allow_html=True)
            if not lat_col or not lon_col:
                st.warning("Could not auto-detect lat/lon. Rename columns to "
                           "`latitude`/`longitude`, `lat`/`lon`, or `y`/`x`.")
            with st.expander("Preview first 5 rows"):
                st.dataframe(input_df_preview.head(5), use_container_width=True)
        except Exception as e:
            st.error(f"Could not read CSV: {e}")

    elif fname.endswith(".zip"):
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                zip_path = os.path.join(tmpdir, fname)
                with open(zip_path, "wb") as f:
                    f.write(uploaded_file.read())
                uploaded_file.seek(0)
                with zipfile.ZipFile(zip_path, "r") as z:
                    z.extractall(tmpdir)
                from glob import glob
                shp_files = glob(os.path.join(tmpdir, "**", "*.shp"), recursive=True)
                if not shp_files:
                    st.error("No .shp file found inside the zip.")
                else:
                    import geopandas as gpd
                    gdf = gpd.read_file(shp_files[0])
                    geom_type = gdf.geometry.geom_type.iloc[0]
                    geometry_type = (
                        "points" if geom_type in ("Point", "MultiPoint")
                        else "polygons"
                    )
                    st.markdown(f"""
                    <div class="pe-success-block">
                      <strong>Shapefile loaded</strong> — {len(gdf):,} {geometry_type}
                      · CRS: {gdf.crs}
                    </div>
                    """, unsafe_allow_html=True)
                    with st.expander("Preview attributes (first 5 rows)"):
                        st.dataframe(
                            gdf.drop(columns="geometry", errors="ignore").head(5),
                            use_container_width=True,
                        )
                    input_df_preview = gdf.drop(columns="geometry", errors="ignore").head(5)
        except Exception as e:
            st.error(f"Could not read shapefile: {e}")

st.markdown('<hr class="pe-hr">', unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# SECTION 2 — DATASET BROWSER  +  PARAMETERS (side by side)
# ════════════════════════════════════════════════════════════════════════════
col_ds, col_cfg = st.columns([3, 2], gap="large")

# ── Left: Dataset browser ──────────────────────────────────────────────────
with col_ds:
    st.markdown("""
    <div class="pe-section-header">
      <span class="pe-step-num">2</span>
      Choose datasets
    </div>
    """, unsafe_allow_html=True)

    selected_datasets = []

    for icon, cat_name, bg, accent in CATEGORIES:
        ds_in_cat = [
            name for name, info in DATASETS.items()
            if info.get("category") == cat_name
        ]
        if not ds_in_cat:
            continue

        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:.5rem;
                    margin:.9rem 0 .35rem 0;">
          <span style="width:26px;height:26px;border-radius:8px;
                       background:{bg};display:inline-flex;
                       align-items:center;justify-content:center;
                       font-size:.95rem;">{icon}</span>
          <span style="font-weight:600;font-size:.88rem;
                       color:#202124;letter-spacing:.01em;">
            {cat_name}
          </span>
        </div>
        """, unsafe_allow_html=True)

        for ds_name in ds_in_cat:
            info = DATASETS[ds_name]
            is_ts = info["type"] == "timeseries"
            badge_cls = "pe-chip-blue" if is_ts else "pe-chip-purple"
            badge_txt = "Timeseries" if is_ts else "Static"

            checked = st.checkbox(
                ds_name,
                key=f"ds__{ds_name}",
                help=f"{info['description']}  |  Scale: {info['scale']} m  |  Collection: {info['collection']}",
            )
            if checked:
                selected_datasets.append(ds_name)
                # Show an inline info row under the checked dataset
                st.markdown(f"""
                <div style="margin:-.25rem 0 .4rem 1.75rem;display:flex;
                            align-items:center;gap:.4rem;flex-wrap:wrap;">
                  <span class="pe-chip {badge_cls}">{badge_txt}</span>
                  <span style="font-size:.75rem;color:#80868b;">
                    {info['description']}
                  </span>
                </div>
                """, unsafe_allow_html=True)

    if not selected_datasets:
        st.markdown("""
        <div style="margin-top:.5rem;padding:.75rem 1rem;background:#f8f9fa;
                    border-radius:8px;font-size:.83rem;color:#9aa0a6;
                    border:1px dashed #dadce0;">
          Tick one or more datasets above to include them in the extraction.
        </div>
        """, unsafe_allow_html=True)

# ── Right: Parameters ──────────────────────────────────────────────────────
with col_cfg:
    st.markdown("""
    <div class="pe-section-header">
      <span class="pe-step-num">3</span>
      Parameters
    </div>
    """, unsafe_allow_html=True)

    has_ts = any(
        DATASETS[d]["type"] == "timeseries"
        for d in selected_datasets
    ) if selected_datasets else False

    start_date = end_date = None

    if has_ts:
        st.markdown("**Date range** *(timeseries datasets)*")
        import datetime
        default_end   = datetime.date.today()
        default_start = default_end - datetime.timedelta(days=30)
        c_s, c_e = st.columns(2)
        with c_s:
            start_str = st.text_input("Start", value=str(default_start),
                                      placeholder="YYYY-MM-DD",
                                      key="start_date")
        with c_e:
            end_str = st.text_input("End", value=str(default_end),
                                    placeholder="YYYY-MM-DD",
                                    key="end_date")
        try:
            start_date = datetime.date.fromisoformat(start_str)
            end_date   = datetime.date.fromisoformat(end_str)
            if start_date > end_date:
                st.error("Start must be before end date.")
                start_date = end_date = None
            else:
                n_days = (end_date - start_date).days + 1
                st.markdown(f"""
                <div class="pe-info-block" style="margin-top:.3rem;">
                  {n_days:,} day{'s' if n_days != 1 else ''} selected
                </div>
                """, unsafe_allow_html=True)
        except ValueError:
            st.error("Use YYYY-MM-DD format.")
            start_date = end_date = None
        st.markdown(" ")
    else:
        import datetime  # still needed below

    st.markdown("**Statistics**")
    selected_stats = st.multiselect(
        "Statistics",
        options=ALL_STATS,
        default=["mean"],
        help="Applied to each extracted band. Timeseries-only stats (p50–p99) are ignored for static datasets.",
        label_visibility="collapsed",
    )

    st.markdown(" ")
    st.markdown("**Output format**")
    output_format = st.radio(
        "Format", ["csv", "parquet"], index=0, horizontal=True,
        help="CSV: universal. Parquet: faster for large datasets.",
        label_visibility="collapsed",
    )

    # Quick summary chip strip
    if selected_datasets:
        st.markdown(" ")
        has_static  = any(DATASETS[d]["type"] != "timeseries" for d in selected_datasets)
        has_dynamic = has_ts
        type_chips = ""
        if has_dynamic:
            type_chips += '<span class="pe-chip pe-chip-blue">Timeseries</span> '
        if has_static:
            type_chips += '<span class="pe-chip pe-chip-purple">Static</span> '
        ds_count = len(selected_datasets)
        st.markdown(f"""
        <div style="padding:.65rem .9rem;background:#f6fef7;
                    border:1px solid #b7dfbf;border-radius:8px;
                    font-size:.82rem;">
          <strong style="color:#0d5c2e;">{ds_count} dataset{'s' if ds_count!=1 else ''}</strong>
          selected &nbsp; {type_chips}
        </div>
        """, unsafe_allow_html=True)

st.markdown('<hr class="pe-hr">', unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# SECTION 4 — REVIEW & SUBMIT
# ════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="pe-section-header">
  <span class="pe-step-num">4</span>
  Review &amp; submit
</div>
""", unsafe_allow_html=True)

can_submit = True
issues = []

if uploaded_file is None:
    can_submit = False
    issues.append("No file uploaded.")
if not selected_datasets:
    can_submit = False
    issues.append("No datasets selected.")
if has_ts and (not start_date or not end_date):
    can_submit = False
    issues.append("Date range required for timeseries datasets.")
if not selected_stats:
    can_submit = False
    issues.append("Select at least one statistic.")

if can_submit and uploaded_file is not None and geometry_type:
    date_row = ""
    if has_ts and start_date and end_date:
        n = (end_date - start_date).days + 1
        date_row = (
            f'<div class="sr"><span class="sl">Date range</span>'
            f'{start_date} → {end_date} ({n:,} days)</div>'
        )
    datasets_chips = "".join(
        f'<span class="pe-chip pe-chip-{"blue" if DATASETS[d]["type"]=="timeseries" else "purple"}">{d}</span> '
        for d in selected_datasets
    )
    stats_chips = "".join(
        f'<span class="pe-chip pe-chip-gray">{s}</span> '
        for s in selected_stats
    )
    st.markdown(f"""
    <div class="pe-summary">
      <div class="sr">
        <span class="sl">File</span>
        {uploaded_file.name}
        <span class="pe-chip pe-chip-gray" style="margin-left:6px;">{geometry_type}</span>
      </div>
      <div class="sr"><span class="sl">Datasets</span>{datasets_chips}</div>
      <div class="sr"><span class="sl">Stats</span>{stats_chips}</div>
      <div class="sr">
        <span class="sl">Format</span>
        <span class="pe-chip pe-chip-green">{output_format.upper()}</span>
      </div>
      {date_row}
    </div>
    """, unsafe_allow_html=True)

for issue in issues:
    st.warning(issue)

submit_btn = st.button(
    "Submit extraction job",
    type="primary",
    disabled=not can_submit,
)

if submit_btn and can_submit and uploaded_file is not None:
    from core.jobs_db import create_job
    from core.worker import run_job_in_background
    import uuid

    job_tmp = str(uuid.uuid4())
    ext = ".csv" if uploaded_file.name.endswith(".csv") else ".zip"
    saved = os.path.join(JOBS_DIR, f"{job_tmp}_input{ext}")
    uploaded_file.seek(0)
    with open(saved, "wb") as f:
        f.write(uploaded_file.read())

    if ext == ".zip":
        exdir = os.path.join(JOBS_DIR, f"{job_tmp}_shp")
        os.makedirs(exdir, exist_ok=True)
        with zipfile.ZipFile(saved, "r") as z:
            for member in z.namelist():
                dest = os.path.realpath(os.path.join(exdir, member))
                if not dest.startswith(os.path.realpath(exdir) + os.sep):
                    raise ValueError(f"Rejected unsafe zip entry: {member}")
            z.extractall(exdir)
        from glob import glob
        shps = glob(os.path.join(exdir, "**", "*.shp"), recursive=True)
        if shps:
            saved = shps[0]

    job_id = create_job(
        username=username,
        datasets=selected_datasets,
        start_date=str(start_date) if start_date else None,
        end_date=str(end_date) if end_date else None,
        geometry_type=geometry_type,
        input_filename=saved,
        ee_project=ee_project,
        stats_requested=selected_stats,
        output_format=output_format,
    )
    run_job_in_background(job_id)

    st.success(f"Job submitted — ID: **{job_id[:8]}…**")
    st.markdown("""
    <div class="pe-info-block">
      Extraction is running in the background.
      Go to <strong>My Jobs</strong> to track progress and download results.
    </div>
    """, unsafe_allow_html=True)
    st.page_link("pages/2_My_Jobs.py", label="Track in My Jobs →", icon="📋")

render_chat_fab()
