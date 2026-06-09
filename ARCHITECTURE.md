# PRECISE / placealert.org — Architecture Reference

> Generated from source: June 2026. Reflects the state of `/home/rutendo/PRECISE/`.

---

## 1. System Overview

The **PRECISE / PALs** platform is a multi-component research portal serving geospatial, climate, and maternal health data to researchers across Sub-Saharan Africa. It is operated by Place Alert Labs (PALs) at CESHHAR / HE²AT Centre.

| Domain | Purpose | Users |
|--------|---------|-------|
| `placealert.org` | Public organisation website | Anyone |
| `portal.placealert.org` | Research portal — landing page + all tools | Registered researchers |
| `pals.placealert.org` | PALSlab JupyterHub — collaborative notebooks | Approved research team |

**Top-level components:**

| Component | What it does |
|-----------|-------------|
| Public website | Static HTML/CSS/JS about, team, research, news pages |
| PRECISE Catalogue | AI research assistant over the PRECISE maternal health dataset (Kenya, Mozambique, Gambia) |
| HE²AT Catalogue | AI research assistant over HE²AT Centre climate/health data |
| PALSearth | Point-and-extract Google Earth Engine geospatial tool |
| Road Network Density Map | Interactive H3 hexagon map of road density across Africa |
| Road Proximity Map | Euclidean distance to highways/major roads across Africa |
| HarmonAIze | AI-assisted dataset harmonisation toolkit |
| GIPEX | Geospatial Indicators for Proxy Environmental Exposure |
| SPECTRA/APEX | GPS trajectory & personal sensor exposure analytics |
| Flask API (`api.py`) | Backend for all catalogue AI queries, auth, and data access |
| DuckDB Request service (`duckdb_request.py`) | Admin dashboard, API key management, legacy catalogue flows |
| Access Control DB (`access_db.py`) | SQLite-backed auth store for all portal users and API keys |
| Data pipelines | Scripts that build and update the DuckDB research databases |

---

## 2. Architecture Diagram

```
Internet
    │
    ▼
┌──────────────────────────────────────────────────────────────────┐
│  Nginx (Let's Encrypt TLS)                                       │
│                                                                  │
│  placealert.org ──────────────► /var/www/website  (static HTML) │
│                                                                  │
│  portal.placealert.org                                           │
│    /                ──────────► /var/www/precise  (static HTML) │
│    /catalogue/      ──────────► /var/www/precise/catalogue/     │
│    /heat-catalogue/ ──────────► /var/www/precise/heat-catalogue/│
│    /roadnet/        ──────────► /var/www/precise/roadnet/       │
│    /euclidean/      ──────────► /var/www/precise/euclidean/     │
│    /precise-api/    ──────────► :5000  Flask API (api.py)       │
│    /duckrequest/    ──────────► :35488 DuckDB Request Flask app  │
│    /dbrequest/      ──────────► :35487 (legacy dbrequest)       │
│    /catalogue-request/ ───────► :8110  (legacy catalogue req)   │
│    /palsearth/      ──────────► :8503  PALSearth (Streamlit)    │
│    /dashboard/      ──────────► :8502  Dashboard (Streamlit)    │
│    /harmonaize/     ──────────► :8082  HarmonAIze               │
│    /neoheat/        ──────────► :5001  NeoHeat                  │
│    /gipex/          ──────────► :8087  GIPEX (Streamlit)        │
│    /apex/           ──────────► :8086  SPECTRA/APEX             │
│                                                                  │
│  pals.placealert.org ─────────► :8100  JupyterHub               │
└──────────────────────────────────────────────────────────────────┘
         │                    │
         ▼                    ▼
   ┌───────────┐       ┌─────────────────────────────────────┐
   │ Flask API │       │ PALSearth Streamlit App              │
   │  :5000    │       │  app.py + pages/ + core/            │
   │           │       │  ─ auth → JupyterHub SQLite          │
   │ Databases:│       │  ─ extractor → Google Earth Engine   │
   │  precise  │       │  ─ worker → multiprocessing          │
   │  .duckdb  │       │  ─ jobs_db → palsearth_jobs.db       │
   │  sensor   │       │  ─ notifications → Gmail SMTP        │
   │  .duckdb  │       └─────────────────────────────────────┘
   │  access_  │
   │  control  │       ┌──────────────────────────────────────┐
   │  .db      │       │ DuckDB Request Admin App              │
   └───────────┘       │  duckdb_request.py  :35488            │
         │             │  ─ admin dashboard (approve users)    │
         ▼             │  ─ API key issuance                   │
   ┌─────────────┐     │  ─ legacy catalogue request flow      │
   │ Claude API  │     └──────────────────────────────────────┘
   │ (Anthropic) │
   │ Shmron AI   │     ┌──────────────────────────────────────┐
   │ Portal chat │     │ access_control.db (SQLite)            │
   └─────────────┘     │  requests, api_keys, catalogue_users  │
                       │  admins, tokens, shared_conversations  │
                       └──────────────────────────────────────┘
```

---

## 3. Component Reference

### 3.1 Public Website (`website/`)

**Purpose:** Static marketing/information site for the PRECISE Network and PALs Lab.

**Technology:** Plain HTML5, CSS, vanilla JavaScript. No build step.

**Key files:**
| File | Description |
|------|-------------|
| `website/index.html` | Homepage with hero, research areas, partners |
| `website/about.html` | About the PRECISE network |
| `website/team.html` | Team member profiles |
| `website/research.html` | Research summaries |
| `website/news.html` | News and updates |
| `website/publications.html` | Publication list |
| `website/assets/main.js` | Shared JS (navigation, animations) |
| `website/assets/style.css` | Global stylesheet |
| `deploy-website.sh` | rsync to `/var/www/website` |

**Interfaces:** Served as static files by nginx from `/var/www/website`. No backend.

---

### 3.2 PRECISE Catalogue (`catalogue/`)

**Purpose:** Browser-based AI research assistant over the PRECISE maternal health dataset. Users log in, then chat with Shmron (Claude Sonnet) which can query the live DuckDB database, run regressions, and render charts.

**Technology:** Single-page HTML app. Calls `portal.placealert.org/precise-api/api/*` endpoints.

**Key files:**
| File | Description |
|------|-------------|
| `catalogue/index.html` | Full SPA — login UI, chat interface, chart rendering (Chart.js), regression table display |

**Interfaces:**
- Auth: `POST /precise-api/api/catalogue-user-login` or `POST /precise-api/api/catalogue/signup`
- AI chat: `POST /precise-api/api/chat` (SSE stream, requires `X-Session-Token`)
- Data query: `POST /precise-api/api/query` (direct SQL, requires API key or session token)
- Password reset: `POST /precise-api/api/catalogue/forgot-password` + `reset-password`

---

### 3.3 HE²AT Catalogue (`/heat-catalogue/`)

**Purpose:** Same architecture as PRECISE Catalogue but covers HE²AT Centre climate/health data (9 countries, 74,000+ participants).

**Interfaces:** Same API endpoints with `catalogue='he2at'` parameter. Uses a separate `he2at_data.duckdb` database.

---

### 3.4 PALSearth (`palsearth/`)

**Purpose:** Authenticated point-and-extract tool. Researchers upload a CSV of locations (lat/lon) or a zipped shapefile, select datasets from Google Earth Engine (NDVI, temperature, rainfall, soil, air quality, elevation, etc.), and submit a background extraction job. Results are downloadable as CSV.

**Technology:** Streamlit multi-page app. Python 3.13. Runs as a systemd service on port 8503.

#### 3.4.1 Auth module (`core/auth.py`)

Authenticates against the JupyterHub SQLite database at `/var/lib/palslab-hub/jupyterhub.sqlite`. Passwords are hashed with bcrypt. `login()` checks the `users_info` table. `register()` inserts a new user as `is_authorized=0` (pending), notifies the admin by email, and also inserts into JupyterHub's `users` table so the account appears in the Hub admin.

#### 3.4.2 Datasets module (`core/datasets.py`)

Defines the catalogue of extractable GEE datasets: MODIS NDVI, CHIRPS rainfall, ERA5 temperature, MERRA-2 wet bulb, CAMS air quality, MERIT elevation, iSDAsoil nutrients, GHSL urban settlement, Meta Relative Wealth Index. Each dataset has a GEE collection ID, band names, and a temporal type (timeseries vs static).

#### 3.4.3 Extractor module (`core/extractor.py`)

Reads the uploaded file (CSV → lat/lon columns; zip → shapefile), authenticates with GEE via a service account key (`palsearth-sa-key.json`), and runs GEE extraction for each selected dataset over each point. Writes output to a CSV in `jobs/`. Called by the worker in a subprocess.

#### 3.4.4 Jobs DB (`core/jobs_db.py`)

SQLite database (`palsearth_jobs.db`) with a single `jobs` table. Tracks: `id` (UUID), `username`, `status` (pending/running/done/error), `progress` (0–100), `input_filename`, `output_filename`, `datasets`, `error_msg`, `created_at`, `updated_at`, `notified`, `downloaded`.

#### 3.4.5 Worker (`core/worker.py`)

Launched as a background `multiprocessing.Process` when a job is submitted. Calls `extractor.run_extraction()`, updates progress in the jobs DB, and on completion calls the notification module.

#### 3.4.6 Notifications (`core/notifications.py`)

Sends a Gmail email to the user when their extraction job completes. Uses SMTP SSL on port 465. **Note:** SMTP password is currently hardcoded (see security findings C-1).

#### 3.4.7 UI module (`core/ui.py`)

Injects shared CSS (dark green brand theme), renders the sidebar navigation, and renders the floating Shmron chat button (FAB).

**Key files:**
| File | Description |
|------|-------------|
| `app.py` | Entry point — auth router (show_auth / show_home) |
| `pages/1_Extract.py` | Upload file, select datasets, submit job |
| `pages/2_My_Jobs.py` | Poll job status, download results, delete files |
| `pages/3_Help.py` | Shmron AI assistant (GEE help, not DB access) |
| `run.sh` | Start command: `streamlit run app.py --server.port 8503 ...` |
| `palsearth.service` | systemd unit — runs as `rutendo`, sets env vars |
| `requirements.txt` | Python dependencies |
| `nginx_block.txt` | nginx proxy config snippet for reference |

**Port:** 8503 (WebSocket-upgraded, proxied by nginx at `/palsearth/`)

---

### 3.5 Flask API (`api.py`)

**Purpose:** Central backend for all data-access and auth operations. Serves the catalogues, portal chat, and direct research data API.

**Technology:** Flask + flask-cors. Port 5000. Proxied at `/precise-api/`.

**All API routes:**

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/health` | API key / session | Row count and participant count for authorised countries |
| GET | `/api/schema` | API key / session | Column list for `daily_data` |
| POST | `/api/query` | API key / session | Execute SQL SELECT, returns JSON |
| POST | `/api/query/arrow` | API key / session | Execute SQL, returns Apache Arrow IPC stream |
| POST | `/api/query/csv` | API key / session | Execute SQL, returns CSV download |
| POST | `/api/chat` | API key / session | Streaming SSE — Shmron AI with tool use (execute_query, render_chart, run_regression) |
| POST | `/api/he2at/query` | API key / session | Same as /api/query against HE²AT database |
| POST | `/api/he2at/chat` | API key / session | Shmron for HE²AT dataset |
| GET | `/api/validate-session` | Session token | Lightweight 200/401 session check |
| POST | `/api/catalogue-login` | Access code | Exchange access code for session token (legacy path) |
| POST | `/api/catalogue-user-login` | Email + password | Per-user login for PRECISE or HE²AT catalogue |
| POST | `/api/catalogue/signup` | Public | Self-signup — pending admin approval |
| POST | `/api/catalogue/forgot-password` | Public | Send password reset link |
| POST | `/api/catalogue/reset-password` | Reset token | Consume token and set new password |
| POST | `/api/portal/signup` | Public | Portal account signup |
| POST | `/api/portal/login` | Email + password | Portal login → session token |
| POST | `/api/portal/logout` | Session token | Invalidate session |
| GET | `/api/portal/validate-session` | Session token | Check portal session |
| POST | `/api/portal/forgot-password` | Public | Portal password reset |
| POST | `/api/portal/reset-password` | Reset token | Portal password change |
| POST | `/portal/chat` | Rate-limited, public | Portal landing page chatbot (informational only) |

**Key security controls:**
- `require_key()` — accepts `X-API-Key` header or `X-Session-Token` header
- `apply_country_filter()` — injects country-scoping subquery on every data query
- `_strip_id_cols()` — removes participant ID columns before sending data to LLM
- `is_safe_query()` — blocks non-SELECT SQL keywords
- `_open_conn()` — opens DuckDB with `read_only=True`

---

### 3.6 DuckDB Request Admin App (`duckdb_request.py`)

**Purpose:** Admin-facing Flask web app. Provides a dashboard for approving/rejecting API key requests, catalogue user signups, portal user signups, and token management. Also serves the legacy catalogue request and access-code flow.

**Technology:** Flask with Jinja2 HTML templates (inline). Port 35488. Proxied at `/duckrequest/`.

**Key routes:**
| Path | Description |
|------|-------------|
| `/duckrequest/request` | Public form to request a DuckDB API key |
| `/duckrequest/admin` | Admin login + tabbed dashboard |
| `/duckrequest/admin/approve/<id>` | Approve a DuckDB API key request |
| `/duckrequest/admin/catalogue-approve/<id>` | Approve a catalogue access request (legacy) |
| `/duckrequest/admin/portal-approve/<id>` | Approve a portal signup |
| `/duckrequest/admin/catalogue-user-approve/<id>` | Approve a self-signup catalogue user |
| `/duckrequest/admin/revoke/<key>` | Revoke an API key |
| `/duckrequest/status` | Public status page / instructions PDF |

---

### 3.7 Access Control DB (`access_db.py`)

**Purpose:** All user and auth state for the portal. SQLite at `/home/rutendo/PRECISE/access_control.db`.

**Technology:** Python stdlib `sqlite3`. Parameterised queries throughout.

**Schema:**

| Table | Purpose | Key columns |
|-------|---------|-------------|
| `requests` | DuckDB API key requests | id, name, email, institution, countries_req, status |
| `api_keys` | Issued DuckDB research API keys | key, request_id, name, email, countries, is_active |
| `catalogue_tokens` | Short-lived session tokens (8h TTL) | token, expires_at, user_id |
| `admins` | Admin dashboard users | username, password (plaintext — see C-3), must_change_pw |
| `admin_reset_tokens` | Admin password reset tokens | token, username, expires_at |
| `catalogue_requests` | Legacy catalogue access requests | id, catalogue, name, email, status |
| `catalogue_users` | Self-signup users for all catalogues + portal | id, catalogue, name, email, password (plaintext — see C-3), token_budget, tokens_used, status |
| `user_reset_tokens` | User password reset tokens (1h TTL) | token, user_id, expires_at |
| `shared_conversations` | Saved chat threads | share_id, catalogue, title, messages (JSON) |

---

### 3.8 Research Databases

| File | Type | Size | Contents |
|------|------|------|----------|
| `precise.duckdb` | DuckDB | ~3.1M rows | `daily_data` — one row per participant per exposure day, 129 columns across climate, air quality, maternal health, birth outcomes |
| `sensor.duckdb` | DuckDB | sensor_daily: 3,190 rows; sensor_raw: 3.7M rows | Personal wearable sensor data for 343 participants |
| `palsearth/palsearth_jobs.db` | SQLite | — | PALSearth extraction job queue |
| `access_control.db` | SQLite | — | All portal auth state (see §3.7) |
| `/var/lib/palslab-hub/jupyterhub.sqlite` | SQLite | — | JupyterHub user accounts — PALSearth auth reads from here |

**`daily_data` column categories:** identifiers & geography, dates (exposure_day, conception_date, delivery_date), air quality (CAMS2, MERRA2, fire smoke), temperature (ERA5, MERRA2, CAMS2), heat stress indices (UTCI, WBGT, humidex, Heat Index), weather (humidity, precipitation), environment (NDVI, elevation), access to care (walk/drive/public transport distances to facility, road distances), socioeconomic (RWI, VIIRS night lights, PPI), soil nutrients, demographics, maternal anthropometry & clinical, birth outcomes.

---

## 4. Data Flow: PALSearth Extraction Job

```
1. User visits portal.placealert.org/palsearth/
   └─ nginx proxies WebSocket to Streamlit :8503

2. app.py router checks st.session_state["username"]
   └─ if not set → show_auth() → login form
   └─ login() checks bcrypt hash in JupyterHub SQLite

3. User navigates to Extract page (pages/1_Extract.py)
   └─ auth guard checks session_state["username"]

4. User uploads CSV (lat/lon columns) or .zip (shapefile)
   └─ CSV: validated for required columns, previewed on map
   └─ ZIP: extracted to temp dir, shapefile read with geopandas,
           centroid computed per feature

5. User selects one or more datasets and a date range

6. User clicks "Submit extraction"
   └─ jobs_db.create_job() → UUID, status=pending, stored to palsearth_jobs.db
   └─ worker.start_worker(job_id) → multiprocessing.Process spawned

7. Worker process (core/worker.py)
   └─ authenticates with GEE via palsearth-sa-key.json
   └─ extractor.run_extraction() → for each point × dataset:
       └─ GEE image collection sampled at location + date range
       └─ results merged into a single DataFrame
   └─ output CSV written to jobs/<job_id>_output.csv
   └─ jobs_db.update_job(status='done', output_filename=...)
   └─ notifications.notify_user() → sends email via Gmail SMTP

8. User checks pages/2_My_Jobs.py
   └─ polls jobs_db.get_jobs(username) every few seconds
   └─ when status=done → "Download CSV" button
   └─ st.download_button streams jobs/<job_id>_output.csv
```

---

## 5. Data Flow: Catalogue Access

### Sign-up (new self-signup flow)
```
1. User visits /catalogue/ → SPA loads
2. Clicks "Request Access" → fills name, email, password, institution, reason
3. POST /precise-api/api/catalogue/signup
   └─ access_db.create_catalogue_signup_user() → status='pending'
   └─ admin notification email sent to ADMIN_EMAILS list
4. Admin logs into /duckrequest/admin, approves user
   └─ status → 'approved', approval email sent to user
```

### Login and AI query
```
1. User enters email + password in catalogue SPA
2. POST /precise-api/api/catalogue-user-login
   └─ checks status (pending/rejected/revoked → error)
   └─ access_db.authenticate_catalogue_user() → compares plaintext password (see C-3)
   └─ checks tokens_used < token_budget
   └─ access_db.issue_user_catalogue_token() → 32-byte token, 8h TTL in catalogue_tokens
3. SPA stores token in sessionStorage
4. User types query in chat box
5. POST /precise-api/api/chat with X-Session-Token header
   └─ require_key() validates token against catalogue_tokens
   └─ iteration 0: tool_choice='any' → Claude MUST call execute_query
   └─ execute_query → apply_country_filter() → DuckDB read-only query
   └─ _strip_id_cols() removes participant ID columns before returning to LLM
   └─ render_chart → streamed as SSE type='chart' with Chart.js spec
   └─ run_regression → statsmodels OLS/Logit, results streamed as type='stats_table'
   └─ Claude narrative text streamed as type='text'
6. token usage accumulated, stored to catalogue_users.tokens_used
```

### Open-access window (catalogue/index.html)
The catalogue SPA contains hardcoded JS timestamps defining a window (08:00–15:00 ZIM on 4 Jun 2026) during which a guest token is automatically issued. Outside this window, login is required.

---

## 6. Authentication & Authorization Model

Four separate auth systems exist, each with its own database and mechanism:

| System | Database | Mechanism | Session |
|--------|----------|-----------|---------|
| PALSearth / JupyterHub | `/var/lib/palslab-hub/jupyterhub.sqlite` | bcrypt password check | `st.session_state["username"]` (in-memory, no server-side expiry) |
| PRECISE / HE²AT Catalogue + Portal | `access_control.db` → `catalogue_users` | Plaintext password compare (see C-3) | 32-byte token, 8h TTL, stored in `catalogue_tokens` table |
| DuckDB Research API | `access_control.db` → `api_keys` | `secrets.token_urlsafe(32)` key, sent as `X-API-Key` header | Stateless (each request validates key) |
| Admin dashboard | `access_control.db` → `admins` | Plaintext password compare (see H-1) | Flask `session` with ephemeral `os.urandom(32)` secret key |

**Password reset:** All four catalogues (precise, he2at) and the portal support self-service password reset. A `secrets.token_urlsafe(32)` token is generated, stored in `user_reset_tokens` with a 1-hour TTL, and emailed as a `?reset_token=` URL. The token is consumed (deleted) on use.

**Admin approval required for:** PALSearth (JupyterHub admin approves), PRECISE catalogue self-signup, HE²AT catalogue self-signup, portal signup. DuckDB API key requests also require admin approval.

**Country-level scoping:** Each API key stores an approved `countries` list (JSON). Every query to `daily_data`, `sensor_daily`, and `sensor_raw` is wrapped with a country-restricting subquery before execution. Catalogue session tokens grant access to all three countries.

---

## 7. Geospatial Data Pipelines

Scripts are run manually (not scheduled) to build and update the research databases.

### 7.1 PRECISE Main Database

| Script | Input | Output | Purpose |
|--------|-------|--------|---------|
| `build_dhs_br_database.py` | DHS birth recode files (35 countries) | `dhs_births.duckdb` | Build 35-country DHS birth outcomes database |
| `build_dhs_br_geo.py` | DHS GPS cluster files | appends to dhs_births.duckdb | Add geolocation to DHS records |
| `build_dhs_ge.py` | DHS GE files | appends | Add geographic/environmental variables |
| `build_dhs_recode.py` | DHS recode files | appends | Apply country-specific recoding |
| `build_dhs_merged.py` | dhs_births.duckdb | merged outputs | Merge all DHS tables |
| `merge_outcomes.py` | PRECISE field data + satellite data | precise.duckdb / daily_data | Final merge of all exposure and outcome data |
| `fix_conception_dates.py` | precise.duckdb | precise.duckdb (in place) | Correct conception date calculation errors |
| `setup_db.py` | — | precise.duckdb schema | Create/migrate database schema |
| `setup_he2at_db.py` | — | he2at_data.duckdb schema | Create HE²AT database schema |

### 7.2 Geospatial Index Generation

| Script | Input | Output | Purpose |
|--------|-------|--------|---------|
| `generate_euclidean.py` | OSM road data, H3 cells | euclidean/data/ | Euclidean distance from each H3 cell to nearest highway and major road |
| `generate_pweuclidean.py` | euclidean/data/, WorldPop | euclidean/data/ | Population-weighted road proximity per admin unit |
| `filter_euclidean_pop.py` | euclidean/data/ | filtered outputs | Remove low-population cells |
| `generate_roadnet.py` | OSM road data, H3 cells | roadnet/data/ | Road network density (km/km²) per H3 cell |
| `generate_road_lines.py` | OSM | roadnet/data/ | Road line geometries for overlay rendering |
| `split_roadnet.py` | roadnet/data/ | per-country files | Split road network data by country for faster frontend loads |
| `roadnet/generate_pwrnd.py` | roadnet/data/, WorldPop | roadnet/data/ | Population-weighted road density per admin unit |

---

## 8. Infrastructure & Deployment

### Nginx Virtual Hosts

| Host | Config | Root/Upstream |
|------|--------|---------------|
| `placealert.org` | `/etc/nginx/sites-enabled/placealert` | `/var/www/website` |
| `portal.placealert.org` | same file | `/var/www/precise` + upstream proxies |
| `pals.placealert.org` | same file | `localhost:8100` (JupyterHub) |

### Port Map

| Port | Service | Managed by |
|------|---------|-----------|
| 5000 | Flask API (`api.py`) | Manual / systemd (not documented — run separately) |
| 8100 | JupyterHub | JupyterHub systemd service |
| 8082 | HarmonAIze | Separate service |
| 8086 | SPECTRA/APEX | Separate service |
| 8087 | GIPEX (Streamlit) | Separate service |
| 8110 | Legacy catalogue request Flask | Manual |
| 8502 | Dashboard (Streamlit) | Manual / systemd |
| 8503 | PALSearth (Streamlit) | `palsearth.service` |
| 35487 | Legacy dbrequest | Manual |
| 35488 | DuckDB Request admin app | Manual |

### PALSearth systemd Service

File: `palsearth/palsearth.service`

Runs as user `rutendo`. Sets environment variables including `ANTHROPIC_API_KEY` (currently hardcoded in the unit file — see security finding C-2) and `GEE_SA_KEY`. Starts `run.sh` which calls `streamlit run app.py --server.port 8503 --server.baseUrlPath /palsearth --server.enableXsrfProtection false`.

### Website Deployment

`deploy-website.sh` rsyncs `/home/rutendo/PRECISE/website/` to `/var/www/website/` and rsyncs the catalogue, roadnet, and euclidean frontend files to `/var/www/precise/`.

---

## 9. Environment Variables

### Required

| Variable | Used by | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | `api.py`, `palsearth.service` | Claude API key for Shmron and portal chat |
| `SMTP_APP_PASSWORD` | `api.py` | Gmail app password for sending email |
| `FLASK_SECRET_KEY` | `duckdb_request.py` (should be) | Flask session signing key — currently `os.urandom(32)` |
| `CATALOGUE_ACCESS_CODE` | `api.py`, `duckdb_request.py` | PRECISE catalogue legacy access code |
| `HE2AT_ACCESS_CODE` | `api.py`, `duckdb_request.py` | HE²AT catalogue legacy access code |
| `GEE_SA_KEY` | `palsearth.service` | Path to GEE service account JSON key |

### Hardcoded Credentials (security issues — see report)

| Variable | Location | Issue |
|----------|----------|-------|
| `SMTP_PASS = 'tulwiwtiswekzlhf'` | `palsearth/core/auth.py:9`, `core/notifications.py:5` | Gmail app password in source (C-1) |
| `ANTHROPIC_API_KEY=sk-ant-...` | `palsearth/palsearth.service:15` | Live API key in systemd unit file in repo (C-2) |
| `CATALOGUE_ACCESS_CODE = 'PRECISE2024'` | `api.py:46`, `duckdb_request.py:37` | Guessable fallback (M-8) |
| `HE2AT_ACCESS_CODE = 'HE2AT2022'` | `api.py:1494`, `duckdb_request.py:38` | Guessable fallback (M-8) |

---

## 10. Known Limitations / Tech Debt

### Security (fix urgently — see full security report)
1. **C-1** Gmail app-password hardcoded in `palsearth/core/auth.py` and `core/notifications.py`
2. **C-2** Anthropic API key hardcoded in `palsearth/palsearth.service`
3. **C-3** All catalogue, portal, and admin passwords stored in plaintext in SQLite
4. **C-4** Zip slip vulnerability in shapefile upload extraction (`pages/1_Extract.py:395`)

### Architecture
5. **No job queue manager:** PALSearth jobs use `multiprocessing.Process` directly. If the Streamlit process restarts, running jobs are silently killed with no recovery. A proper queue (Celery, RQ) would provide job persistence across restarts.
6. **Ephemeral Flask session key:** `duckdb_request.py` uses `os.urandom(32)` — admin sessions are lost on every restart.
7. **In-memory rate limiter:** The `/portal/chat` IP rate limiter lives in `api.py`'s process memory. A restart (or multiple workers) resets all counters. Redis would fix this.
8. **Duplicate notification service:** Both `palsearth/core/notifications.py` and `catalogue_notify.py` send email for different events. They share the same SMTP credentials and `From` address but are maintained separately.
9. **No auth on rate-limited portal chat tokens:** The public `/portal/chat` endpoint uses a rate limiter based on IP. IP spoofing via `X-Forwarded-For` manipulation is possible since the header is accepted unchecked.

### Operational
10. **`access_db.py` password for admins not hashed at creation:** `setup_db.py` may insert a default admin password from `.duck_admin_pass` without hashing.
11. **Service account key file in project tree:** `palsearth/palsearth-sa-key.json` is adjacent to source code. It should be in a separate, not-world-readable directory.
12. **No upload size limit:** PALSearth accepts uploads up to Streamlit's 200MB default. A large file can exhaust server memory during GEE extraction.
13. **Static catalogue access window:** The open-access window for the PRECISE demo is hardcoded as JS timestamps in `catalogue/index.html`. Changing the window requires a file edit and re-deployment.
14. **DuckDB `daily_data` has no LIMIT by default:** The `/api/query` endpoint has no server-side row cap — the user controls row counts entirely via SQL LIMIT. A missing LIMIT can return millions of rows.
15. **No monitoring or alerting:** There is no uptime monitoring, error alerting, or structured logging for any of the Flask services. Failures are silent until a user reports them.
