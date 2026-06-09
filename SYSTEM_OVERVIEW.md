# PALS Lab — Server & Data Infrastructure: Complete Overview

**Domain:** placealert.org  
**Server path:** `/home/rutendo/PRECISE/`  
**Last updated:** 2026-05-28

---

## Table of Contents

1. [Big Picture Architecture](#1-big-picture-architecture)
2. [The PRECISE Dataset](#2-the-precise-dataset)
3. [DHS Databases](#3-dhs-databases)
4. [Supporting Databases (SQLite)](#4-supporting-databases-sqlite)
5. [API Services & Ports](#5-api-services--ports)
6. [Web Tools — What Each Does](#6-web-tools--what-each-does)
7. [Nginx — How the Web Is Wired Together](#7-nginx--how-the-web-is-wired-together)
8. [Security Model](#8-security-model)
9. [Access Workflows: Step by Step](#9-access-workflows-step-by-step)
10. [Python Client Library (precise_db.py)](#10-python-client-library-precise_dbpy)
11. [Data Pipeline: How the Databases Get Built](#11-data-pipeline-how-the-databases-get-built)
12. [Email Notifications](#12-email-notifications)
13. [Geodata & Reference Datasets](#13-geodata--reference-datasets)
14. [File Map: Key Files and What They Do](#14-file-map-key-files-and-what-they-do)
15. [Privacy Protections](#15-privacy-protections)

---

## 1. Big Picture Architecture

```
Internet
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  NGINX  (placealert.org, pals.placealert.org)               │
│  Reverse proxy — all ports are private; nginx is the        │
│  only public entry point                                    │
└────────────┬───────────────────────────────────────────────┘
             │  routes by URL path
      ┌──────┼──────────────────────────────────────────┐
      │      │                                          │
      ▼      ▼                                          ▼
 Static   Flask / Python services               Streamlit apps
 HTML     (ports 5000, 35487, 35488,            (ports 8502, 8503)
 files    8086, 8087, 8110, 5001)
      │      │
      │      ▼
      │  ┌──────────────────────────────────────────────┐
      │  │  DuckDB files (chmod 600, rutendo only)      │
      │  │  precise.duckdb  — PRECISE Big Table         │
      │  │  dhs_*.duckdb    — 17 DHS recode databases   │
      │  └──────────────────────────────────────────────┘
      │
      ▼
  access_control.db  (SQLite)
  API keys, requests, catalogue tokens
```

**Key principle:** The DuckDB files on disk are `chmod 600` — only the `rutendo` system user can open them. There is no way for any tool, browser, or researcher to reach them except through the API service at port 5000, which enforces authentication and country-level access control before every query.

---

## 2. The PRECISE Dataset

### What it is

The **PRECISE Big Table** is the central research dataset for the project. It is a longitudinal daily-record dataset covering pregnant women enrolled across three countries:

| Country | Role in dataset |
|---|---|
| **Kenya** | ~47.8% of records |
| **Mozambique** | ~30.7% of records |
| **The Gambia** | ~19.1% of records (also written as "Gambia") |

- ~3.1 million rows (one row = one participant-day)
- 129 columns covering clinical, environmental, geospatial, and exposure variables
- Each participant identified by `f2a_participant_id`
- Date columns: `conception_date`, `edd` (estimated delivery date), `delivery_date`

### Where it lives

```
/home/rutendo/PRECISE/precise.duckdb          ← live database (1.9 GB)
/home/rutendo/PRECISE/precise.duckdb.bak      ← backup
```

Inside the database there is one table: **`daily_data`**.

### Where the source comes from

New data arrives as a parquet (or CSV) file named `Daily_Big_Table_*.parquet`. The most recently modified such file is always used. Running `setup_db.py` recreates the `daily_data` table from scratch:

```bash
python3 setup_db.py
```

That script picks the newest `Daily_Big_Table*.parquet` (falling back to CSV), drops and recreates `daily_data`, coercing the three date columns, then prints a country breakdown.

### How researchers access it

Researchers **never touch the DuckDB file directly**. They:
1. Request access at `placealert.org/duckrequest/request`
2. Receive an API key after admin approval
3. Use `PreciseDB(api_key="pals_...")` inside a PALSlab Hub notebook (see §10)

---

## 3. DHS Databases

The server holds a comprehensive DHS (Demographic and Health Surveys) multi-country database covering **35+ Sub-Saharan African countries**. These are built from `DHS_downloads.zip`.

### The 17 DuckDB files

| File | Recode | Description | Size |
|---|---|---|---|
| `dhs_births.duckdb` | BR | Birth Records (unified, 35 countries) | 3.0 GB |
| `dhs_br.duckdb` | BR | Birth Records (per-survey parquets) | 3.0 GB |
| `dhs_ir.duckdb` | IR | Individual / Women's Recode | 4.2 GB |
| `dhs_hr.duckdb` | HR | Household Recode | 5.0 GB |
| `dhs_pr.duckdb` | PR | Person / Household Member Recode | 2.3 GB |
| `dhs_kr.duckdb` | KR | Children's Recode (Kids) | 2.3 GB |
| `dhs_cr.duckdb` | CR | Couple's Recode | 1.1 GB |
| `dhs_mr.duckdb` | MR | Men's Recode | 581 MB |
| `dhs_br_geo.duckdb` | BR+GR | Birth Records merged with GPS cluster data | 511 MB |
| `dhs_gr.duckdb` | GR | Geographic / GPS Cluster Recode | 332 MB |
| `dhs_nr.duckdb` | NR | Nutrition Recode | 114 MB |
| `dhs_sr.duckdb` | SR | Service Availability Recode | 86 MB |
| `dhs_ar.duckdb` | AR | HIV Test Results Recode | 47 MB |
| `dhs_wi.duckdb` | WI | Women's Information | 16 MB |
| `dhs_hw.duckdb` | HW | Height/Weight Recode | 21 MB |
| `dhs_ge.duckdb` | GE | Geographic Encoded | 8.6 MB |
| `dhs_merged.duckdb` | — | Merged dataset | 12 KB |

**Total DHS storage:** ~25 GB

### Countries covered (35)

Angola, Benin, Burkina Faso, Burundi, Cameroon, Central African Republic, Chad, Comoros, Cote d'Ivoire, DR Congo, Eritrea / Ethiopia, Eswatini, Gabon, Gambia, Ghana, Guinea, Kenya, Lesotho, Liberia, Madagascar, Malawi, Mali, Mauritania, Mozambique, Namibia, Niger, Nigeria, Rwanda, Senegal, Sierra Leone, South Africa, Tanzania, Togo, Uganda, Zambia, Zimbabwe.

### DHS survey phases

The filename anatomy `ZWBR72DT.zip` decodes as:
- `ZW` — country code (Zimbabwe)
- `BR` — recode type (Birth Records)
- `72` — Phase 7, version 2
- `DT` — Stata format

Phases range from DHS-I (1986–1990) through DHS-IX (2023–present).

### How they are built

Each recode has its own build script:

| Script | Output |
|---|---|
| `build_dhs_br_database.py` | `dhs_births.duckdb` — all BR surveys unified |
| `build_dhs_br_geo.py` | `dhs_br_geo.duckdb` — BR merged with GPS |
| `build_dhs_ge.py` | `dhs_ge.duckdb` |
| `build_dhs_merged.py` | `dhs_merged.duckdb` |
| `build_dhs_recode.py` | All other `dhs_*.duckdb` files |

The general process:
1. Extract `.dta` (Stata) files from `DHS_downloads.zip`
2. Convert each survey to `.parquet` via `pyreadstat` → stored in `dhs_*_parquet/` directories
3. Use DuckDB `read_parquet(..., union_by_name=true)` to merge all surveys into one table
4. Create indexes and print a summary

The `dhs_*_parquet/` directories act as a cache — surveys already converted are skipped on re-runs.

**Codebook:** `DHS_Codebook.xlsx` and `generate_dhs_codebook.py` produce variable documentation. The reference file `README.txt` contains the full DHS filename anatomy and recode descriptions.

---

## 4. Supporting Databases (SQLite)

### access_control.db

```
/home/rutendo/PRECISE/access_control.db
```

This SQLite database is the **access control store** for the PRECISE data API. It has three tables:

#### `requests`

Stores every access request submitted through the web form.

| Column | Meaning |
|---|---|
| `id` | 16-char hex token (request ID) |
| `name` | Applicant full name |
| `email` | Applicant email |
| `institution` | Applicant institution |
| `hub_user` | Their PALSlab Hub username |
| `purpose` | Free-text research purpose |
| `countries_req` | JSON list of requested countries |
| `status` | `pending` / `approved` / `rejected` / `revoked` |
| `created_at` | ISO timestamp (UTC) |
| `reviewed_at` | ISO timestamp (UTC) |
| `notes` | Admin notes on decision |

#### `api_keys`

One row per issued key.

| Column | Meaning |
|---|---|
| `key` | `pals_` + 30-char URL-safe random token |
| `request_id` | FK → requests.id |
| `name` | Researcher name |
| `email` | Researcher email |
| `countries` | JSON list of **approved** countries (may be subset of what was requested) |
| `created_at` | ISO timestamp |
| `is_active` | 1 = active, 0 = revoked |
| `last_used` | ISO timestamp, updated on every query |

#### `catalogue_tokens`

Short-lived session tokens for the PRECISE Catalogue.

| Column | Meaning |
|---|---|
| `token` | `cat_` + 32-char URL-safe random |
| `expires_at` | ISO timestamp — tokens last **8 hours** |

Expired tokens are purged each time a new one is issued.

### jupyterhub.sqlite (managed by JupyterHub)

```
/var/lib/palslab-hub/jupyterhub.sqlite
```

This is the **JupyterHub user store**. PALSearth authentication reads the same database so researchers use one set of credentials for both. Fields used:

- `username` — login name
- `password` — bcrypt-hashed
- `is_authorized` — 0 = pending, 1 = approved
- `email` — for notifications

Passwords are hashed with `bcrypt` (cost factor default ~12). Plain passwords are never stored anywhere.

---

## 5. API Services & Ports

All ports are private (localhost or LAN only). Nginx is the only public entry point.

| Port | Script | What it does |
|---|---|---|
| **5000** | `api.py` | Main PRECISE data API — token-gated DuckDB queries, Arrow IPC transport |
| **35488** | `duckdb_request.py` | DuckDB access request form + admin approval dashboard |
| **35487** | (separate service) | Alternate DB request service (`/dbrequest/` path) |
| **8100** | JupyterHub | PALSlab research hub (pals.placealert.org) |
| **8110** | `catalogue_notify.py` | Catalogue access request email handler |
| **8502** | Streamlit | Dashboard |
| **8503** | `palsearth/app.py` | PALSearth geospatial extraction tool |
| **8087** | Pixel service | GIPEX / pixel tool |
| **8086** | SPECTRA (LAN) | APEX/SPECTRA GPS analytics (on 192.168.1.254) |
| **5001** | NeoHeat | Heat exposure catalogue service |

---

## 6. Web Tools — What Each Does

### Portal — placealert.org `/`

The public landing page. Static HTML (`index.html`, served from `/var/www/precise/`). No login required. Links out to all other tools.

### PRECISE Catalogue — `/catalogue/`

**What:** A rich, searchable catalogue of environmental and social determinants of maternal health across Kenya, Mozambique, and The Gambia. Includes an **AI research assistant called "Shmron"** that can query the participant dataset interactively.

**Access:** Requires an access code (not a username/password). The code is stored as the `CATALOGUE_ACCESS_CODE` environment variable on the server (default fallback is `PRECISE2024`). Codes are shared by the admin directly.

**How login works:**
1. Visitor enters the access code in the login gate
2. Frontend POSTs it to `/api/catalogue-login`
3. API verifies the code, issues a `cat_...` session token stored in `access_control.db`
4. Token is stored in `sessionStorage` in the browser
5. All subsequent API calls include it as `X-Session-Token` header
6. Tokens expire after **8 hours** — the user must re-enter the code

**AI assistant:** The Shmron assistant has full access to all three countries' data (not country-filtered like researcher keys). It queries `daily_data` through the same API, then Claude processes the results. Questions go through a rate limiter (20 requests / 60 seconds per IP).

**Request access:** Users who don't have the code click "Request Access" on the login screen, which sends their name/email/institution/reason to the admin via `catalogue_notify.py` on port 8110. The admin then shares the code out-of-band.

### HE2AT Centre Catalogue — `/heat-catalogue/`

Similar structure to the PRECISE Catalogue but themed for the HE2AT Centre's environmental exposure data. Separate access code. Static HTML with its own login gate.

### DuckDB Access Request — `/duckrequest/`

**What:** A self-service portal for researchers to request programmatic access to the PRECISE Big Table.

**Routes inside the service (duckdb_request.py, port 35488):**

| Route | Who uses it | What happens |
|---|---|---|
| `/duckrequest/request` | Researcher | Fills out form: name, email, institution, Hub username, countries wanted, research purpose |
| `/duckrequest/status/<id>` | Researcher | Check their request status (pending / approved / rejected) |
| `/duckrequest/admin/login` | Admin | Log in with admin credentials |
| `/duckrequest/admin` | Admin (logged in) | Dashboard: all requests table, approve/reject buttons |
| `/duckrequest/admin/approve` | Admin (POST) | Approve a request, select approved countries, generate key, send email |
| `/duckrequest/admin/reject` | Admin (POST) | Reject with optional notes, send email |

**Admin login:** Username `rutendo`, password from `/home/rutendo/PRECISE/.duck_admin_pass` (chmod 600). The session uses a randomly generated Flask secret key — admin sessions do not survive a service restart.

### PRECISE API — `/precise-api/`

The REST API that sits in front of `precise.duckdb`. Used by `precise_db.py` (the Python client) and the Catalogue AI. Not intended to be used directly by researchers.

Key endpoints:

| Endpoint | Method | Auth | What it returns |
|---|---|---|---|
| `/api/health` | GET | Key or token | Status, record count, participant count, authorised countries |
| `/api/schema` | GET | Key or token | All column names and types |
| `/api/query` | POST | Key or token | JSON result |
| `/api/query/arrow` | POST | Key or token | Arrow IPC binary stream (fast, for Python) |
| `/api/query/csv` | POST | Key or token | CSV stream (for R) |
| `/api/catalogue-login` | POST | Access code | Issues `cat_...` session token |
| `/api/chat` | POST | None (rate limited) | Portal chatbot response (Claude, informational only, no DB access) |

### PALSearth — `/palsearth/`

**What:** Point-and-extract environmental data tool. Upload a CSV of coordinates or a shapefile, select datasets (NDVI, temperature, rainfall, soil moisture, air quality, elevation), specify a date range, download results. Powered by Google Earth Engine via the service account key at `palsearth/palsearth-sa-key.json`.

**Auth:** Uses PALSlab Hub credentials (same `jupyterhub.sqlite` database). Bcrypt password verification. New accounts need admin approval before they can log in. Registration triggers an email to the admin.

**Pages:**
- `1_Extract.py` — the main extraction interface
- `2_My_Jobs.py` — view status of submitted extraction jobs
- `3_Help.py` — usage guide

Jobs are persisted in `palsearth/palsearth_jobs.db` (SQLite).

### PALS Lab Hub — pals.placealert.org

JupyterHub serving the research team. Python and R kernels available. Sign-up requires admin approval. The home folder has a shared `PALS/` directory accessible to the whole team. This is where researchers run notebooks using `precise_db.py` or direct DHS database queries.

### GIPEX / Pixel — `/pixel/` and `/gipex/`

Geospatial Indicators for Proxy Environmental eXposure. Extracts satellite-derived environmental exposure indicators across custom grid cells or study areas.

### SPECTRA / APEX — `/apex/`

Spatiotemporal Personal Exposure Characterisation & TRAjectory Analyzer. GPS trajectory analytics, wearable sensor integration, indoor/outdoor exposure classification. Runs on a separate machine at `192.168.1.254:8086` on the LAN.

### Africa Road Network Density Map — `/roadnet/`

Interactive hexagonal map of road network density across Africa, derived from OpenStreetMap data. Built by `generate_roadnet.py` and `split_roadnet.py`. Static HTML served from `roadnet_index.html`.

### HarmonAIze — `/harmonaize/`

Climate and Health Data Harmonisation toolkit.

### NeoHeat — `/neoheat/`

Heat exposure service (port 5001).

---

## 7. Nginx — How the Web Is Wired Together

The Nginx config is at `/home/rutendo/PRECISE/placealert-nginx.conf` (the live version is deployed to `/etc/nginx/sites-enabled/`).

```
placealert.org  (port 80/443)
├── /                       → /var/www/precise/index.html  (static)
├── /data/                  → /var/www/precise/data/       (static, no autoindex)
├── /catalogue/             → /var/www/precise/catalogue/  (static)
├── /heat-catalogue/        → /var/www/precise/heat-catalogue/ (static)
├── /catalogue-request/     → 127.0.0.1:8110              (catalogue_notify.py)
├── /duckrequest/           → 127.0.0.1:35488             (duckdb_request.py)
├── /precise-api/           → 127.0.0.1:5000              (api.py)
├── /dbrequest/             → 127.0.0.1:35487             (alt DB request)
├── /pixel/                 → 127.0.0.1:8087              (GIPEX/pixel)
├── /apex/                  → 192.168.1.254:8086          (SPECTRA, LAN)
├── /dashboard/             → 127.0.0.1:8502              (Streamlit dashboard)
├── /palsearth/             → 127.0.0.1:8503              (PALSearth Streamlit)
└── /neoheat/               → 127.0.0.1:5001              (NeoHeat)

pals.placealert.org  (port 80/443)
└── /                       → 127.0.0.1:8100              (JupyterHub)
```

**WebSocket support:** Services that need persistent connections (JupyterHub, Streamlit, pixel/GIPEX) have `Upgrade` / `Connection` headers forwarded and `proxy_read_timeout 86400` (24 hours).

**Real IP forwarding:** All proxied services receive `X-Real-IP` and `X-Forwarded-For` headers so they can log and rate-limit by the visitor's actual IP rather than `127.0.0.1`.

**HTTPS:** SSL/TLS is managed by Certbot (Let's Encrypt). The config file is initially HTTP-only; Certbot modifies it in-place to add `listen 443 ssl` blocks and certificate paths.

---

## 8. Security Model

### Layer 1: Network

All database services listen on `localhost` (127.0.0.1) only. There is no way to reach port 5000, 35488, etc., from the internet — Nginx is the sole public entry point. SPECTRA runs on a LAN-only address (192.168.1.254).

### Layer 2: Filesystem

`precise.duckdb` is `chmod 600` — only the `rutendo` system user can open it. No other OS user or process can read or write it directly.

### Layer 3: API authentication

Every endpoint in `api.py` that touches data calls `require_key()` before doing anything else. Two credential types are accepted:

**Researcher API keys** (`pals_...`):
- 30-character cryptographically random URL-safe token with `pals_` prefix
- Generated by `secrets.token_urlsafe(30)` — 180 bits of entropy
- Stored in `api_keys` table, checked on every request
- `last_used` timestamp updated on every successful call
- Can be individually revoked (`is_active = 0`) without affecting other keys

**Catalogue session tokens** (`cat_...`):
- 32-character cryptographically random URL-safe token with `cat_` prefix
- Issued after correct access code entry
- Stored in `catalogue_tokens` table with `expires_at` (8-hour TTL)
- Expired tokens purged on each new issuance

### Layer 4: Country-level data partitioning

Even with a valid key, a researcher cannot access data from countries they were not approved for. The `apply_country_filter()` function in `api.py` rewrites every query at the server before it reaches DuckDB:

```sql
-- Researcher approved for Kenya only
-- Their query: SELECT * FROM daily_data LIMIT 10
-- What actually runs:
SELECT * FROM (
    SELECT * FROM daily_data WHERE Country IN ('Kenya')
) AS daily_data
LIMIT 10
```

This rewrite happens for both `FROM daily_data` and `JOIN daily_data` patterns. A researcher cannot bypass it by any SQL trick because the country list comes from the database, not from the request.

Catalogue users get all three countries (they've accepted the access terms and the data is already de-identified / aggregate in the catalogue view).

### Layer 5: SQL injection prevention

`is_safe_query()` in `api.py` enforces read-only access:

- Query must start with: `SELECT`, `WITH`, `SHOW`, `DESCRIBE`, `DESC`, `PRAGMA`, or `EXPLAIN`
- Forbidden keywords checked with word-boundary regex: `DROP`, `DELETE`, `INSERT`, `UPDATE`, `CREATE`, `ALTER`, `TRUNCATE`
- Any violation returns a 400 error with a message — the query never reaches DuckDB

### Layer 6: Rate limiting

The portal chat endpoint uses an in-memory per-IP rate limiter: maximum **20 requests per 60-second window**. Requests beyond the limit receive a 429 response. This is separate from — and in addition to — any Nginx-level rate limiting.

### Layer 7: Admin access

Admin operations (approving/revoking access, viewing all requests) are protected by:
- Username `rutendo` + password from `.duck_admin_pass` (chmod 600, never in source code)
- Flask session cookie (ephemeral — invalidated on service restart)
- All admin routes check `session.get('admin')` before rendering

The admin password can be changed at any time by calling `access_db.set_admin_password(new_pass)` from a Python shell — this overwrites `.duck_admin_pass` with `chmod 600`.

### Layer 8: SMTP credentials

Email is sent via Gmail SMTP SSL (port 465). The app password is hardcoded in `duckdb_request.py` and `catalogue_notify.py`. This is a Gmail **app password** (not the main account password) — it can be revoked independently through Google account settings without affecting anything else.

---

## 9. Access Workflows: Step by Step

### Researcher wanting PRECISE data access

```
1. Researcher visits placealert.org/duckrequest/request
2. Fills form: name, email, institution, Hub username, countries, purpose
3. Form submits → duckdb_request.py saves to requests table in access_control.db
4. Admin emails sent to: rutendo.sibanda@ceshhar.org,
   nyonih@staff.msu.ac.zw, zororo.chinwadzimba@ceshhar.org
5. Admin logs in at /duckrequest/admin/login
6. Reviews request in dashboard, clicks Approve
7. Admin selects which countries to grant (can be subset of what was requested)
8. System:
   a. Generates pals_XXXX key (30-char random)
   b. Saves to api_keys table
   c. Updates request status to 'approved'
   d. Generates PDF instructions (Python + R code snippets)
   e. Emails researcher with key + PDF attachment
9. Researcher can check status at /duckrequest/status/<request_id>
10. Researcher uses key in Hub notebook via PreciseDB class
```

### Researcher wanting Catalogue access

```
1. Researcher visits placealert.org/catalogue/
2. Clicks "Request Access" tab on login screen
3. Fills: name, email, institution, reason
4. catalogue_notify.py sends email to admin
5. Admin reviews and replies directly with the access code
6. Researcher enters code → receives 8-hour session token
7. Token stored in browser sessionStorage (not localStorage — clears on tab close)
8. AI assistant and query builder available until token expires
```

### New researcher wanting Hub + PALSearth access

```
1. Researcher visits pals.placealert.org → clicks "Sign up"
2. Or visits placealert.org/palsearth/ and uses "Create account" tab
3. Fills username, email, password (bcrypt-hashed, stored in jupyterhub.sqlite)
4. Admin receives notification email
5. Admin approves at pals.placealert.org/hub/authorize
6. Researcher receives approval email
7. Can now log in to both JupyterHub and PALSearth with same credentials
```

### Revoking access

Admin can revoke from the admin dashboard. `revoke_access(req_id)` in `access_db.py`:
- Sets `is_active = 0` on all associated API keys
- Sets request `status = 'revoked'`
- Next query attempt returns HTTP 403

---

## 10. Python Client Library (precise_db.py)

The `PreciseDB` class in `precise_db.py` is the intended way for researchers to access data from a PALSlab Hub notebook.

### How it works

```python
import sys
sys.path.insert(0, '/home/rutendo/PRECISE')
from precise_db import PreciseDB

with PreciseDB(api_key="pals_your_key_here") as db:
    df = db.query("SELECT * FROM daily_data WHERE gestational_age > 37")
```

On construction, it calls `/api/health` to validate the key and retrieve the list of approved countries. If the key is invalid, it raises `PermissionError` with instructions on where to apply.

### Transport: Apache Arrow IPC

Queries use **Apache Arrow IPC binary format** rather than JSON. This matters for large results — a 100,000-row DataFrame transfers and deserialises far faster than JSON. The Arrow stream is decoded back to a pandas DataFrame in the client.

For R users, a CSV endpoint is available instead (JSON would hit R memory limits on large tables).

### Available methods

| Method | Returns | Notes |
|---|---|---|
| `db.query(sql)` | `pd.DataFrame` | SELECT queries only; Arrow transport |
| `db.query(sql, max_rows=N)` | `pd.DataFrame` | Hard cap on rows returned |
| `db.head(n=5)` | `pd.DataFrame` | First n rows of daily_data |
| `db.columns()` | `list[str]` | All column names |
| `db.shape()` | `(int, int)` | (n_rows, n_cols) for your approved countries |
| `db.dtypes()` | `pd.DataFrame` | Column names + DuckDB types |
| `db.summary()` | prints | Overview: user, countries, shape, columns |
| `db.info()` | prints | User and countries |
| `db.countries` | `list[str]` | Your approved countries |

### Country filtering is transparent

Researchers write plain SQL (`SELECT ... FROM daily_data`). The server automatically restricts results to their approved countries — they never need to add `WHERE Country = 'Kenya'` themselves, and they cannot remove the filter.

---

## 11. Data Pipeline: How the Databases Get Built

### PRECISE Big Table pipeline

```
New data delivery
       │
       ▼
Daily_Big_Table_UNS_YYYY_MM_DD.parquet   ← placed in /home/rutendo/PRECISE/
       │
       ▼
python3 setup_db.py
       │  1. Finds newest Daily_Big_Table*.parquet
       │  2. DROP TABLE IF EXISTS daily_data
       │  3. CREATE TABLE daily_data AS SELECT * FROM read_parquet(...)
       │     (coerces date columns)
       │  4. Prints row counts + country breakdown
       ▼
precise.duckdb   (live — api.py reads this)
```

### DHS pipeline (example: Birth Records)

```
DHS_downloads.zip
       │
       ▼
build_dhs_br_database.py
       │  For each BR survey file inside the zip:
       │  1. Extract .dta to /tmp/
       │  2. pyreadstat → DataFrame
       │  3. Add metadata columns: country_code, survey_code, dhs_phase
       │  4. Save as dhs_br_parquet/ZZBRVVDT.parquet
       │  (skips if parquet already exists)
       │
       │  After all parquets:
       │  5. DuckDB read_parquet('dhs_br_parquet/*.parquet', union_by_name=true)
       │  6. CREATE TABLE births AS SELECT ...
       │  7. CREATE INDEX, print summary
       ▼
dhs_births.duckdb   (table: births)
```

The parquet cache (`dhs_br_parquet/`, `dhs_ir_parquet/`, etc.) means incremental updates are fast — only new surveys get converted.

### Build logs

Every build script writes a `.log` file:
- `dhs_br_build.log`, `dhs_ir_build.log`, etc.
- `dhs_recovery.log` — recovery attempts
- `dhs_build_queue.log` — queue management

---

## 12. Email Notifications

All emails are sent via **Gmail SMTP SSL** (port 465), from `rutendosibanda18@gmail.com` using a Gmail app password.

| Trigger | Recipient(s) | Content |
|---|---|---|
| New DuckDB access request | All three admin emails | Name, email, institution, Hub username, countries, purpose, admin dashboard link |
| Request approved | Applicant | API key, Python snippet, R snippet, PDF instructions attached |
| Request rejected | Applicant | Rejection notice, optional reason |
| New PALSearth registration | Admin | Username, email, approval link |
| Catalogue access request | Admin only | Name, email, institution, reason (admin replies manually with code) |

**PDF instructions** (attached to approval emails): Generated with `fpdf2`. Contains the researcher's name, approved countries, API key, and ready-to-run Python and R code snippets.

**Admin emails list:**
- `rutendo.sibanda@ceshhar.org`
- `nyonih@staff.msu.ac.zw` (Bongani)
- `zororo.chinwadzimba@ceshhar.org` (Zororo)

---

## 13. Geodata & Reference Datasets

```
/home/rutendo/PRECISE/geodata/
├── admin_boundaries/    ← Country/district shapefiles
├── dhs/                 ← DHS GPS cluster point data
├── osm_poi/             ← OpenStreetMap points of interest
└── worldpop/            ← WorldPop population rasters

/home/rutendo/PRECISE/roadnet/
├── data/                ← Preprocessed road network tiles
├── generate_pwrnd.py    ← Population-weighted road network density generator
└── index.html           ← Interactive map app
```

The road network map uses OpenStreetMap data aggregated into H3 hexagonal cells. `generate_roadnet.py` and `split_roadnet.py` process the raw OSM data. The result is the interactive map at `/roadnet/`.

Flowchart PNGs in the root directory document the methodological pipelines for computing environmental exposure indicators:
- `Degree_Urbanization_Flowchart.png`
- `Euclidean_Distance_Highways_Flowchart.png`
- `Euclidean_Distance_Major_Roads_Flowchart.png`
- `Isolation_Flowchart.png`
- `Macronutrients_Elevation_Flowchart.png`
- `Relative_Humidity_Flowchart.png`
- `Static_RQI_Flowchart.png`
- `Temperature_Metrics_Flowchart.png`
- `Village_Accessibility_Flowchart.png`

---

## 14. File Map: Key Files and What They Do

```
/home/rutendo/PRECISE/
│
├── precise.duckdb          ← PRECISE Big Table (live, chmod 600)
├── access_control.db       ← SQLite: API keys, requests, catalogue tokens
│
├── api.py                  ← Main data API (Flask, port 5000)
├── access_db.py            ← Access control logic (key validation, request CRUD)
├── precise_db.py           ← Python client library for Hub notebooks
├── duckdb_request.py       ← Web UI for access requests + admin dashboard (port 35488)
├── catalogue_notify.py     ← Catalogue access request email handler (port 8110)
├── setup_db.py             ← Rebuild precise.duckdb from latest Big Table parquet
│
├── build_dhs_br_database.py ← Build dhs_births.duckdb (all BR surveys)
├── build_dhs_br_geo.py      ← Build dhs_br_geo.duckdb (BR + GPS merge)
├── build_dhs_ge.py          ← Build dhs_ge.duckdb
├── build_dhs_merged.py      ← Build dhs_merged.duckdb
├── build_dhs_recode.py      ← Build all other dhs_*.duckdb files
├── generate_dhs_codebook.py ← Generate DHS variable codebook
│
├── catalogue/index.html    ← PRECISE Catalogue frontend
├── heat-catalogue/index.html ← HE2AT Catalogue frontend
├── index.html              ← Portal landing page (also at /var/www/precise/)
├── roadnet_index.html      ← Road network density map
│
├── palsearth/              ← PALSearth Streamlit app
│   ├── app.py              ← Main entry point
│   ├── core/auth.py        ← Login/registration (reads jupyterhub.sqlite)
│   ├── pages/1_Extract.py  ← GEE extraction interface
│   ├── pages/2_My_Jobs.py  ← Job status viewer
│   ├── palsearth_jobs.db   ← SQLite: extraction job queue
│   └── palsearth-sa-key.json ← Google Earth Engine service account key
│
├── data/                   ← Parquet exports of Big Table subsets
│   ├── big_table_all_latest.parquet
│   ├── big_table_kenya_latest.parquet
│   ├── big_table_mozambique_latest.parquet
│   ├── big_table_gambia_latest.parquet
│   └── outcomes_latest.parquet
│
├── geodata/                ← Shapefiles, population rasters, DHS GPS
├── roadnet/                ← Road network tiles + generator scripts
│
├── dhs_births.duckdb       ← DHS Birth Records, 35 countries (3 GB)
├── dhs_ir.duckdb           ← DHS Individual/Women Records (4.2 GB)
├── dhs_hr.duckdb           ← DHS Household Records (5 GB)
│   [... and 14 other dhs_*.duckdb files]
│
├── dhs_br_parquet/         ← Per-survey parquet cache for BR
├── dhs_ir_parquet/         ← Per-survey parquet cache for IR
│   [... and other dhs_*_parquet/ directories]
│
├── placealert-nginx.conf   ← Nginx config (reference copy)
├── .duck_admin_pass        ← Admin password (chmod 600, never in git)
│
├── Daily_Big_Table*.parquet ← Source data files (newest auto-selected by setup_db.py)
└── DHS_downloads.zip       ← All DHS survey downloads (raw .dta files)
```

---

## 15. Privacy Protections

The PRECISE study involves real pregnant women. Multiple layers ensure participant privacy:

### No direct file access

Researchers never receive the DuckDB file or any raw export. All access is mediated through the API, which enforces their approved country scope on every query.

### Access is individually granted and logged

Every API key is tied to a named individual, their institution, and their stated research purpose. The `last_used` timestamp tracks activity. Keys can be revoked at any time.

### SQL is restricted to reads

Only `SELECT`, `WITH`, `SHOW`, `DESCRIBE`, and related read-only statements are permitted. Write operations are blocked at the application layer — even if someone had a valid key, they cannot modify, delete, or export the underlying file.

### Country-level segmentation

A researcher approved for Kenya cannot see Mozambique or Gambia data, even by accident. The server rewrites their queries before execution.

### Catalogue is access-code gated

The catalogue does not use username/password — the access code is a single shared secret that the admin distributes to vetted individuals. It is environment-variable based so it can be rotated without a code deployment.

### Passwords are bcrypt-hashed

JupyterHub/PALSearth user passwords are bcrypt-hashed with a random salt. The plain password is never stored or logged.

### Session tokens are short-lived

Catalogue session tokens expire after 8 hours. They live in `sessionStorage` (not `localStorage`), so they are cleared when the browser tab is closed.

### Admin credentials stored outside source control

`.duck_admin_pass` is `chmod 600` and should be in `.gitignore`. It is never committed to the repository.

### Rate limiting

The public portal chat is rate-limited per IP (20 requests / 60 seconds) to prevent abuse of the Claude API endpoint that has no authentication requirement.

---

*Documentation covers the system state as of 2026-05-28. For changes or questions, contact Rutendo Sibanda (rutendo.sibanda@ceshhar.org).*
