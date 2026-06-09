import streamlit as st
import sys
import os
import json
import time

sys.path.insert(0, '/home/rutendo/PRECISE/palsearth')

st.set_page_config(page_title="My Jobs — PALSearth",
                   page_icon="📋", layout="wide")

from core.ui import inject_css, render_sidebar, render_chat_fab
inject_css()

# Auth guard
if "username" not in st.session_state or not st.session_state["username"]:
    st.switch_page("app.py")

render_sidebar(active="jobs")
username = st.session_state["username"]
JOBS_DIR = "/home/rutendo/PRECISE/palsearth/jobs"

from core.jobs_db import get_user_jobs, update_job

# ── Refresh state ──────────────────────────────────────────────────────────────
if "last_refresh" not in st.session_state:
    st.session_state["last_refresh"] = time.time()

jobs = get_user_jobs(username)
active_statuses = {"queued", "running"}
has_active = any(j["status"] in active_statuses for j in jobs)

# ── Page header ────────────────────────────────────────────────────────────────
hdr_col, btn_col = st.columns([5, 1])
with hdr_col:
    st.markdown("""
    <p class="pe-page-title">📋 My Jobs</p>
    <p class="pe-page-sub">Track extraction progress and download results.</p>
    """, unsafe_allow_html=True)
with btn_col:
    st.markdown(" ")
    if st.button("↻ Refresh", use_container_width=True):
        st.rerun()

# ── Stats strip ────────────────────────────────────────────────────────────────
if jobs:
    total    = len(jobs)
    complete = sum(1 for j in jobs if j["status"] == "complete")
    running  = sum(1 for j in jobs if j["status"] in active_statuses)
    failed   = sum(1 for j in jobs if j["status"] == "failed")

    st.markdown(f"""
    <div class="stats-row">
      <div class="stat-tile">
        <div class="st-val">{total}</div>
        <div class="st-label">Total jobs</div>
      </div>
      <div class="stat-tile">
        <div class="st-val" style="color:#137333;">{complete}</div>
        <div class="st-label">Complete</div>
      </div>
      <div class="stat-tile">
        <div class="st-val" style="color:#1a73e8;">{running}</div>
        <div class="st-label">Active</div>
      </div>
      <div class="stat-tile">
        <div class="st-val" style="color:#c5221f;">{failed}</div>
        <div class="st-label">Failed</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

# ── Job list ───────────────────────────────────────────────────────────────────
if not jobs:
    st.markdown("""
    <div class="pe-card" style="text-align:center;padding:3rem 2rem;">
      <div style="font-size:2.5rem;margin-bottom:.75rem;">📭</div>
      <div style="font-weight:600;font-size:1.05rem;margin-bottom:.35rem;">No jobs yet</div>
      <div style="color:#5f6368;font-size:.88rem;">
        Go to Extract Data to create your first extraction job.
      </div>
    </div>
    """, unsafe_allow_html=True)
    st.page_link("pages/1_Extract.py", label="Start extraction →", icon="🗺️")
else:
    for job in jobs:
        job_id   = job["id"]
        short_id = job_id[:8].upper()
        status   = job["status"]

        try:
            datasets_list = (
                json.loads(job.get("datasets", "[]"))
                if isinstance(job.get("datasets"), str)
                else job.get("datasets", [])
            )
        except Exception:
            datasets_list = []

        progress   = job.get("progress", 0) or 0
        created_at = (job.get("created_at", "") or "")[:16].replace("T", " ")
        updated_at = (job.get("updated_at", "") or "")[:16].replace("T", " ")
        start_d    = job.get("start_date") or "—"
        end_d      = job.get("end_date")   or "—"
        out_fmt    = job.get("output_format", "csv") or "csv"
        error_msg  = job.get("error_msg")

        # Status badge config
        status_cfg = {
            "queued":   ("pe-chip-gray",   "pe-dot-gray",  "Queued"),
            "running":  ("pe-chip-blue",   "pe-dot-blue",  "Running"),
            "complete": ("pe-chip-green",  "pe-dot-green", "Complete"),
            "failed":   ("pe-chip-red",    "pe-dot-red",   "Failed"),
        }
        chip_cls, dot_cls, label = status_cfg.get(
            status, ("pe-chip-gray", "pe-dot-gray", status.title())
        )

        ds_chips = "".join(
            f'<span class="pe-chip pe-chip-gray" style="margin:.15rem;">{d}</span>'
            for d in datasets_list
        )

        st.markdown(f"""
        <div class="pe-job-card">
          <div class="jc-row">
            <div>
              <span class="jc-id">Job {short_id}</span>
              &nbsp;
              <span class="pe-chip {chip_cls}">
                <span class="pe-dot {dot_cls}"></span>{label}
              </span>
            </div>
            <span class="jc-ts">{created_at}</span>
          </div>
          <div class="jc-chips">{ds_chips if ds_chips else '<span class="jc-ds">No datasets</span>'}</div>
          <div class="jc-meta">
            <span style="margin-right:.75rem;">📅 {start_d} → {end_d}</span>
            <span style="margin-right:.75rem;">📄 {out_fmt.upper()}</span>
            <span>🔄 {updated_at}</span>
          </div>
        </div>
        """, unsafe_allow_html=True)

        # Progress bar for active jobs
        if status in ("running", "queued"):
            prog_pct = int(progress)
            st.markdown(f"""
            <div class="pe-prog-track" style="margin-top:-.4rem;margin-bottom:.6rem;">
              <div class="pe-prog-bar {'anim' if status=='running' else ''}"
                   style="width:{prog_pct}%;"></div>
            </div>
            <div style="font-size:.77rem;color:#5f6368;margin-bottom:.75rem;">
              {prog_pct}% complete
            </div>
            """, unsafe_allow_html=True)

        # Error
        if status == "failed" and error_msg:
            st.error(f"Error: {error_msg}")

        # Download / delete
        if status == "complete":
            output_filename = job.get("output_filename")
            if output_filename:
                output_path = os.path.join(JOBS_DIR, output_filename)
                col_dl, col_del, col_sp = st.columns([2, 2, 5])
                with col_dl:
                    if os.path.exists(output_path):
                        try:
                            with open(output_path, "rb") as fh:
                                data = fh.read()
                            mime = (
                                "text/csv" if out_fmt == "csv"
                                else "application/octet-stream"
                            )
                            if st.download_button(
                                label=f"⬇ Download {out_fmt.upper()}",
                                data=data,
                                file_name=output_filename,
                                mime=mime,
                                key=f"dl_{job_id}",
                                type="primary",
                                use_container_width=True,
                            ):
                                update_job(job_id, downloaded=1)
                        except Exception as e:
                            st.error(f"Cannot read output file: {e}")
                    else:
                        st.warning("Output file not found on disk.")
                with col_del:
                    if st.button("🗑 Delete files",
                                 key=f"del_{job_id}",
                                 use_container_width=True):
                        for candidate in [
                            output_path,
                            os.path.join(JOBS_DIR,
                                         job.get("input_filename", "")),
                        ]:
                            try:
                                if candidate and os.path.exists(candidate):
                                    os.remove(candidate)
                            except Exception:
                                pass
                        update_job(job_id, status="complete",
                                   output_filename=None)
                        st.rerun()

        st.markdown('<div style="height:.25rem;"></div>', unsafe_allow_html=True)

# ── Auto-refresh ───────────────────────────────────────────────────────────────
if has_active:
    elapsed   = time.time() - st.session_state["last_refresh"]
    remaining = max(0, 10 - int(elapsed))

    st.markdown(f"""
    <div style="text-align:center;padding:.5rem;font-size:.78rem;color:#80868b;">
      <span class="pe-dot pe-dot-blue"
            style="display:inline-block;vertical-align:middle;margin-right:5px;">
      </span>
      Auto-refreshing in {remaining}s
    </div>
    """, unsafe_allow_html=True)

    if elapsed >= 10:
        st.session_state["last_refresh"] = time.time()
        st.rerun()
    else:
        time.sleep(1)
        st.rerun()

render_chat_fab()
