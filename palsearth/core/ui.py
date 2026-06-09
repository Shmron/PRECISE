"""
PALSearth – Shared UI / Design System
Inject once per page via inject_css() + render_sidebar() + render_chat_fab().
"""
import os
import streamlit as st

# ── Google Fonts & icon import ─────────────────────────────────────────────────
_FONT_IMPORT = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Google+Sans:wght@400;500;600;700&family=Roboto:wght@300;400;500&display=swap" rel="stylesheet">
"""

# ── Full design-system CSS ─────────────────────────────────────────────────────
GLOBAL_CSS = _FONT_IMPORT + """
<style>

/* Load Material Symbols so sidebar icons render as glyphs, not raw text */
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=swap');

/* ══ Base & reset ═══════════════════════════════════════════════════════════ */
*, *::before, *::after { box-sizing: border-box; }

html, body, [class*="css"], [class*="st-"] {
  font-family: 'Google Sans', 'Roboto', -apple-system, BlinkMacSystemFont,
               'Segoe UI', sans-serif !important;
  color: #202124;
}

.stApp { background: #f0f2f0 !important; }
.main .block-container {
  max-width: 1100px;
  padding: 1.75rem 2rem 6rem 2rem;
}
#MainMenu, footer { visibility: hidden; }
header[data-testid="stHeader"] {
  background: transparent !important;
  box-shadow: none !important;
}

/* ── Sidebar expand/collapse icon — force Material Symbols font;
      if it still can't load, make the raw text invisible so it
      doesn't bleed over the page content ─────────────────────── */
[data-testid="collapsedControl"] button span,
[data-testid="collapsedControl"] span {
  font-family: 'Material Symbols Rounded', sans-serif !important;
  font-optical-sizing: auto;
  font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24;
  overflow: hidden !important;
  max-width: 2rem !important;
  white-space: nowrap !important;
}

/* ── Hide Streamlit auto-generated sidebar nav (we use our own) ─── */
[data-testid="stSidebarNav"],
[data-testid="stSidebarNavItems"],
[data-testid="stSidebarNavSeparator"],
[data-testid="stSidebarNavLink"],
section[data-testid="stSidebar"] nav { display: none !important; }

/* ══ Sidebar ════════════════════════════════════════════════════════════════ */
[data-testid="stSidebar"] {
  background: #ffffff !important;
  border-right: 1px solid #e8eaed !important;
}
[data-testid="stSidebarContent"] { padding: 1rem 1rem 1rem 1rem !important; }

/* ══ Typography ════════════════════════════════════════════════════════════ */
h1, h2, h3, h4 {
  font-family: 'Google Sans', sans-serif !important;
  font-weight: 600 !important;
  color: #202124 !important;
}
p, li, td, th { line-height: 1.6; }

/* ══ Cards ══════════════════════════════════════════════════════════════════ */
.pe-card {
  background: #ffffff;
  border-radius: 12px;
  border: 1px solid #e8eaed;
  padding: 1.5rem 1.75rem;
  box-shadow: 0 1px 2px rgba(60,64,67,.08), 0 1px 3px rgba(60,64,67,.04);
  margin-bottom: 1rem;
  transition: box-shadow .18s;
}
.pe-card:hover {
  box-shadow: 0 2px 6px rgba(60,64,67,.12), 0 2px 4px rgba(60,64,67,.06);
}

/* ══ Page header ════════════════════════════════════════════════════════════ */
.pe-page-title {
  font-size: 1.65rem !important;
  font-weight: 700 !important;
  color: #202124 !important;
  margin: 0 0 .2rem 0 !important;
  letter-spacing: -.01em;
}
.pe-page-sub {
  font-size: .92rem;
  color: #5f6368;
  margin: 0 0 1.5rem 0;
}

/* ══ Step / Section header ══════════════════════════════════════════════════ */
.pe-step-header,
.pe-section-header {
  display: flex;
  align-items: center;
  gap: .75rem;
  padding: .8rem 1.1rem;
  background: #ffffff;
  border: 1px solid #e8eaed;
  border-radius: 10px;
  margin-bottom: 1.1rem;
  font-weight: 600;
  font-size: .97rem;
  color: #202124;
  box-shadow: 0 1px 2px rgba(60,64,67,.06);
}
.pe-step-num {
  display: inline-flex; align-items: center; justify-content: center;
  width: 26px; height: 26px;
  background: #0d5c2e;
  color: #fff;
  border-radius: 50%;
  font-size: .8rem;
  font-weight: 700;
  flex-shrink: 0;
}
.pe-step-done .pe-step-num { background: #137333; }
.pe-step-done { border-color: #ceead6; background: #f6fef7; }

/* ══ Chips / Badges ═════════════════════════════════════════════════════════ */
.pe-chip {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 10px;
  border-radius: 100px;
  font-size: .74rem;
  font-weight: 500;
  letter-spacing: .01em;
}
.pe-chip-green  { background: #e6f4ea; color: #137333; }
.pe-chip-blue   { background: #e8f0fe; color: #1a73e8; }
.pe-chip-purple { background: #f3e8fd; color: #7b1fa2; }
.pe-chip-orange { background: #fef7e0; color: #b05e00; }
.pe-chip-red    { background: #fce8e6; color: #c5221f; }
.pe-chip-gray   { background: #f1f3f4; color: #5f6368; }

/* Status dot animation */
.pe-dot {
  display: inline-block;
  width: 8px; height: 8px;
  border-radius: 50%;
  margin-right: 5px;
  vertical-align: middle;
  flex-shrink: 0;
}
.pe-dot-green  { background: #137333; }
.pe-dot-blue   { background: #1a73e8; animation: blink .9s ease-in-out infinite; }
.pe-dot-red    { background: #c5221f; }
.pe-dot-gray   { background: #9aa0a6; }

@keyframes blink {
  0%, 100% { opacity: 1; transform: scale(1); }
  50%       { opacity: .45; transform: scale(1.25); }
}

/* ══ Progress bar ════════════════════════════════════════════════════════════ */
.pe-prog-track {
  width: 100%; height: 4px;
  background: #e8eaed;
  border-radius: 2px;
  overflow: hidden;
  margin: .5rem 0;
}
.pe-prog-bar {
  height: 100%;
  background: linear-gradient(90deg, #0d5c2e, #34a853);
  border-radius: 2px;
  transition: width .4s ease;
}
.pe-prog-bar.anim {
  background-size: 200% 100%;
  animation: shimmer 1.6s linear infinite;
  background-image: linear-gradient(90deg, #0d5c2e 0%, #34a853 50%, #0d5c2e 100%);
}
@keyframes shimmer {
  from { background-position: 200% 0; }
  to   { background-position: -200% 0; }
}

/* ══ Dataset cards ═══════════════════════════════════════════════════════════ */
.pe-ds-card {
  background: #fff;
  border: 1.5px solid #e8eaed;
  border-radius: 10px;
  padding: .875rem 1.1rem;
  margin-bottom: .5rem;
  transition: border-color .14s, box-shadow .14s;
  cursor: default;
}
.pe-ds-card:hover {
  border-color: #0d5c2e;
  box-shadow: 0 0 0 3px rgba(13,92,46,.08);
}
.pe-ds-card .ds-name { font-weight: 600; font-size: .93rem; color: #202124; }
.pe-ds-card .ds-desc { font-size: .81rem; color: #5f6368; margin-top: 2px; }
.pe-ds-card .ds-meta { font-size: .77rem; color: #80868b; margin-top: 5px; }

/* ══ Job cards ═══════════════════════════════════════════════════════════════ */
.pe-job-card {
  background: #fff;
  border: 1px solid #e8eaed;
  border-radius: 12px;
  padding: 1.15rem 1.4rem;
  margin-bottom: .85rem;
  box-shadow: 0 1px 3px rgba(60,64,67,.07);
  transition: box-shadow .18s;
}
.pe-job-card:hover { box-shadow: 0 3px 10px rgba(60,64,67,.12); }
.jc-row  { display: flex; align-items: center; justify-content: space-between; }
.jc-id   { font-weight: 700; font-size: .95rem; color: #202124; font-family: 'Google Sans', sans-serif; }
.jc-ts   { font-size: .78rem; color: #9aa0a6; }
.jc-ds   { font-size: .82rem; color: #5f6368; margin-top: .3rem; }
.jc-meta { font-size: .79rem; color: #80868b; margin-top: .25rem; }
.jc-chips { display: flex; flex-wrap: wrap; gap: .3rem; margin-top: .45rem; }

/* ══ Summary box ══════════════════════════════════════════════════════════════ */
.pe-summary {
  background: #f6fef7;
  border: 1.5px solid #a8d5b5;
  border-radius: 12px;
  padding: 1.25rem 1.5rem;
  margin: 1rem 0;
}
.pe-summary .sr { margin-bottom: .3rem; font-size: .88rem; }
.pe-summary .sl { font-weight: 600; color: #0d5c2e; margin-right: .4rem; }

/* ══ Home cards ══════════════════════════════════════════════════════════════ */
.home-feat-card {
  background: #fff;
  border: 1px solid #e8eaed;
  border-radius: 16px;
  padding: 1.75rem 1.5rem;
  text-align: center;
  height: 100%;
  box-shadow: 0 1px 3px rgba(60,64,67,.07);
  transition: transform .2s, box-shadow .2s;
}
.home-feat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 18px rgba(60,64,67,.13);
}
.hc-icon {
  width: 60px; height: 60px;
  border-radius: 18px;
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 1.75rem;
  margin-bottom: 1rem;
}
.hc-title { font-size: 1.05rem; font-weight: 600; color: #202124; margin-bottom: .35rem; }
.hc-desc  { font-size: .84rem; color: #5f6368; line-height: 1.55; }

/* ══ Stats bar ═══════════════════════════════════════════════════════════════ */
.stats-row {
  display: flex; gap: .75rem;
  flex-wrap: wrap;
  margin-bottom: 1.5rem;
}
.stat-tile {
  flex: 1; min-width: 120px;
  background: #fff;
  border: 1px solid #e8eaed;
  border-radius: 10px;
  padding: .875rem 1rem;
  text-align: center;
}
.st-val   { font-size: 1.65rem; font-weight: 700; color: #0d5c2e; }
.st-label { font-size: .76rem; color: #5f6368; margin-top: 2px; }

/* ══ Auth ════════════════════════════════════════════════════════════════════ */
.auth-wrap {
  max-width: 460px; margin: 0 auto; padding: 2.5rem 0;
}
.auth-logo {
  display: flex; flex-direction: column; align-items: center;
  margin-bottom: 2rem;
}
.auth-logo .logo-icon {
  width: 68px; height: 68px;
  background: linear-gradient(135deg, #0d5c2e 0%, #34a853 100%);
  border-radius: 20px;
  display: flex; align-items: center; justify-content: center;
  font-size: 2.1rem;
  box-shadow: 0 6px 20px rgba(13,92,46,.28);
  margin-bottom: .85rem;
}
.auth-logo .logo-name { font-size: 1.75rem; font-weight: 700; color: #202124; }
.auth-logo .logo-sub  { font-size: .88rem; color: #5f6368; margin-top: .15rem; }

/* ══ Divider ══════════════════════════════════════════════════════════════════ */
.pe-hr { border: none; border-top: 1px solid #e8eaed; margin: 1.5rem 0; }

/* ══ Sidebar logo ════════════════════════════════════════════════════════════ */
.sb-logo {
  display: flex; align-items: center; gap: .65rem;
  padding: .25rem 0 1rem 0;
  border-bottom: 1px solid #e8eaed;
  margin-bottom: .85rem;
}
.sb-logo .sl-icon {
  width: 38px; height: 38px;
  background: linear-gradient(135deg, #0d5c2e, #34a853);
  border-radius: 11px;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.25rem;
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(13,92,46,.25);
}
.sb-logo .sl-text { font-size: 1.05rem; font-weight: 700; color: #202124; }
.sb-logo .sl-sub  { font-size: .7rem; color: #5f6368; line-height: 1.2; }

.sb-user {
  display: flex; align-items: center; gap: .5rem;
  padding: .45rem .75rem;
  background: #f0faf3;
  border: 1px solid #b7dfbf;
  border-radius: 100px;
  margin-bottom: .85rem;
  font-size: .84rem; color: #137333; font-weight: 500;
}
.sb-user .avatar {
  width: 26px; height: 26px;
  background: #0d5c2e;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  color: #fff; font-size: .75rem; font-weight: 700;
}
.sb-divider { border: none; border-top: 1px solid #e8eaed; margin: .5rem 0 .75rem; }

/* ══ Inputs / Buttons ════════════════════════════════════════════════════════ */
[data-testid="stTextInput"] input {
  border-radius: 8px !important;
  border-color: #dadce0 !important;
  font-size: .9rem !important;
  transition: border-color .14s, box-shadow .14s !important;
}
[data-testid="stTextInput"] input:focus {
  border-color: #0d5c2e !important;
  box-shadow: 0 0 0 3px rgba(13,92,46,.14) !important;
}

button[kind="primary"],
.stButton > button[kind="primary"] {
  background: #0d5c2e !important;
  border-color: #0d5c2e !important;
  color: #fff !important;
  border-radius: 8px !important;
  font-weight: 500 !important;
  letter-spacing: .01em !important;
  transition: background .15s, box-shadow .15s !important;
}
button[kind="primary"]:hover,
.stButton > button[kind="primary"]:hover {
  background: #09471f !important;
  border-color: #09471f !important;
  box-shadow: 0 2px 8px rgba(13,92,46,.3) !important;
}

/* ══ Tabs ════════════════════════════════════════════════════════════════════ */
[data-baseweb="tab-list"] { gap: 4px !important; }
[data-baseweb="tab"] {
  border-radius: 8px 8px 0 0 !important;
  font-weight: 500 !important;
  font-size: .88rem !important;
}
[data-baseweb="tab"][aria-selected="true"] { color: #0d5c2e !important; }
[data-baseweb="tab-highlight"] { background: #0d5c2e !important; }

/* ══ Floating AI Chat FAB ════════════════════════════════════════════════════ */
.shmron-fab-wrap {
  position: fixed;
  bottom: 26px; right: 26px;
  z-index: 99999;
  display: flex; flex-direction: column; align-items: flex-end; gap: 7px;
}
.shmron-fab {
  width: 56px; height: 56px;
  border-radius: 50%;
  background: linear-gradient(135deg, #0d5c2e 0%, #2ea84b 100%);
  box-shadow: 0 4px 16px rgba(13,92,46,.45), 0 2px 5px rgba(0,0,0,.18);
  display: flex; align-items: center; justify-content: center;
  cursor: pointer;
  text-decoration: none;
  font-size: 1.45rem;
  border: 2.5px solid rgba(255,255,255,.25);
  color: #fff;
  transition: transform .2s cubic-bezier(.34,1.56,.64,1),
              box-shadow .2s;
  animation: fab-pop .4s cubic-bezier(.34,1.56,.64,1) forwards;
}
.shmron-fab:hover {
  transform: scale(1.1);
  box-shadow: 0 7px 24px rgba(13,92,46,.55), 0 3px 8px rgba(0,0,0,.22);
}
.shmron-fab:active { transform: scale(.96); }
.shmron-fab-tip {
  background: #202124;
  color: #fff;
  padding: 5px 12px;
  border-radius: 8px;
  font-size: .76rem;
  font-family: 'Google Sans', sans-serif;
  white-space: nowrap;
  opacity: 0;
  transform: translateY(4px) scale(.95);
  transition: opacity .16s, transform .16s;
  pointer-events: none;
  box-shadow: 0 2px 8px rgba(0,0,0,.2);
}
.shmron-fab-wrap:hover .shmron-fab-tip {
  opacity: 1; transform: translateY(0) scale(1);
}
@keyframes fab-pop {
  0%   { transform: scale(0) rotate(-15deg); opacity: 0; }
  100% { transform: scale(1) rotate(0deg);  opacity: 1; }
}

/* ══ Help / Docs ══════════════════════════════════════════════════════════════ */
.docs-card {
  background: #fff;
  border: 1px solid #e8eaed;
  border-radius: 12px;
  padding: 1.1rem 1.4rem;
  margin-bottom: .6rem;
  box-shadow: 0 1px 2px rgba(60,64,67,.06);
}
.docs-ds-row {
  display: flex; align-items: flex-start; gap: 1rem;
  padding: .85rem 0;
  border-bottom: 1px solid #f0f2f0;
}
.docs-ds-row:last-child { border-bottom: none; }
.docs-ds-icon {
  width: 36px; height: 36px; flex-shrink: 0;
  border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.2rem;
}
.docs-ds-name  { font-weight: 600; font-size: .9rem; color: #202124; }
.docs-ds-desc  { font-size: .8rem; color: #5f6368; margin-top: 2px; }
.docs-ds-meta  { font-size: .75rem; color: #80868b; margin-top: 4px; font-family: monospace; }

/* ══ File uploader — hide the weird keyboard/arrow SVG icon ═════════════════ */
[data-testid="stFileUploaderDropzoneInstructions"] svg,
[data-testid="stFileUploaderDropzoneInstructions"] > div > span:first-child > svg {
  display: none !important;
}
[data-testid="stFileUploaderDropzone"] {
  border-radius: 10px !important;
  border: 1.5px dashed #c5cad0 !important;
  background: #fafbfc !important;
  transition: border-color .15s, background .15s !important;
}
[data-testid="stFileUploaderDropzone"]:hover {
  border-color: #0d5c2e !important;
  background: #f6fef7 !important;
}
[data-testid="stFileUploaderDropzoneInstructions"] {
  gap: .25rem !important;
}

/* ══ Alerts / info blocks ════════════════════════════════════════════════════ */
.pe-info-block {
  background: #e8f0fe;
  border-left: 4px solid #1a73e8;
  border-radius: 0 8px 8px 0;
  padding: .75rem 1rem;
  font-size: .86rem;
  color: #1a1a2e;
  margin-bottom: 1rem;
}
.pe-success-block {
  background: #e6f4ea;
  border-left: 4px solid #34a853;
  border-radius: 0 8px 8px 0;
  padding: .75rem 1rem;
  font-size: .86rem;
  color: #0d4a1e;
  margin-bottom: 1rem;
}

</style>
"""


def inject_css():
    """Call once at the top of each page."""
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


def render_sidebar(active: str = ""):
    """Consistent sidebar: logo + user chip + nav + signout."""
    username = st.session_state.get("username", "")
    with st.sidebar:
        initial = username[0].upper() if username else "?"
        st.markdown(f"""
        <div class="sb-logo">
          <div class="sl-icon">🌍</div>
          <div>
            <div class="sl-text">PALSearth</div>
            <div class="sl-sub">Geospatial Platform</div>
          </div>
        </div>
        <div class="sb-user">
          <div class="avatar">{initial}</div>
          <span>{username}</span>
        </div>
        """, unsafe_allow_html=True)

        st.page_link("app.py",              label="Home",          icon="🏠")
        st.page_link("pages/1_Extract.py",  label="Extract Data",  icon="🗺️")
        st.page_link("pages/2_My_Jobs.py",  label="My Jobs",       icon="📋")
        st.page_link("pages/3_Help.py",     label="Help & Shmron AI", icon="💬")

        st.markdown('<hr class="sb-divider">', unsafe_allow_html=True)
        if st.button("Sign out", use_container_width=True, key="sb_signout"):
            st.session_state["username"] = ""
            st.switch_page("app.py")


def render_chat_fab():
    """
    Inject a fixed-position floating button that takes users to the AI chat.
    Uses pure HTML/CSS — no Streamlit interaction needed.
    """
    st.markdown("""
    <div class="shmron-fab-wrap">
      <div class="shmron-fab-tip">Ask Shmron AI</div>
      <a href="Help" class="shmron-fab" title="Shmron AI">💬</a>
    </div>
    """, unsafe_allow_html=True)
