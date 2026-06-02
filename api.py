from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import duckdb
import re
import io
import os
import json
import sys
import time
from collections import defaultdict
sys.path.insert(0, '/home/rutendo/PRECISE')
import access_db
import pyarrow.ipc as _ipc

app = Flask(__name__)
CORS(app)

DB_PATH        = '/home/rutendo/PRECISE/precise.duckdb'
SENSOR_DB_PATH = '/home/rutendo/PRECISE/sensor.duckdb'

CATALOGUE_ACCESS_CODE = os.environ.get('CATALOGUE_ACCESS_CODE', 'PRECISE2024')

# ── IP rate limiter for the public portal chat ────────────────────────────────
_ip_hits: dict = defaultdict(list)
_RATE_WINDOW = 60    # seconds
_RATE_LIMIT  = 20    # requests per window

def _allow_ip(ip: str) -> bool:
    now  = time.time()
    hits = [t for t in _ip_hits[ip] if now - t < _RATE_WINDOW]
    if len(hits) >= _RATE_LIMIT:
        _ip_hits[ip] = hits
        return False
    hits.append(now)
    _ip_hits[ip] = hits
    return True

# ── Portal chat system prompt (informational only, no DB access) ──────────────
_PORTAL_SYSTEM = """You are the Place Alert Labs (PALs) portal assistant at placealert.org. Be concise and helpful. Use markdown for links and lists.

ABOUT PALs: Place Alert Labs is an initiative advancing geographically precise public health through climate, environmental, and geospatial intelligence. Funded by NIH, Google, Grand Challenges Canada, and UKRI. Team: Dr Prestige Tatenda Makanga, Liberty Makacha, Terrence Mushore, Reason Mlambo, Cherlynn Dumbura, Bongani Nyoni, Anotida Chapunza, Tendai Shangwe, Zororo Chinwadzimba, Rutendo Sibanda.

PORTAL (placealert.org) — open landing page with links to all tools. No login required to view.

PALS LAB HUB (pals.placealert.org):
- JupyterHub for the research team. Python & R kernels available.
- Sign up at pals.placealert.org — click "Sign up". Provide a username, password, and email address.
- After signing up, an admin must approve your account. You will receive an approval email once done.
- Forgot password: click "Forgot your password?" on the login page — a reset link will be emailed to you.
- Once logged in, your home folder has a PALS/ directory shared with the team.

DATABASE ACCESS — DuckDB (placealert.org/duckrequest/request):
- Request direct access to the PRECISE Big Table (~3.1M rows, 129 columns) via DuckDB.
- Fill in the request form; tokens are reviewed and issued by the admin.
- Once approved, use the provided Python or R snippet inside any PALSlab Hub notebook.

PRECISE CATALOGUE (placealert.org/catalogue/):
- Catalogue of Environmental & Social Determinants of Maternal Health across Kenya, Mozambique, The Gambia.
- Requires an access code — use the "Request Access" tab on the login screen to ask for one.
- Contains an AI research assistant ("Shmron") for querying the PRECISE participant dataset.

PALSEARTH (placealert.org/palsearth/):
- Point-and-extract environmental data for any location and time window.
- Upload a CSV or shapefile, select datasets (NDVI, temperature, rainfall, soil, air quality, elevation), download results.
- Powered by Google Earth Engine.

GIPEX (placealert.org/gipex/):
- Geospatial Indicators for Proxy Environmental eXposure.
- Extracts satellite-derived environmental exposure indicators across custom grid cells or study areas.

SPECTRA (placealert.org/apex/):
- Spatiotemporal Personal Exposure Characterization & TRAjectory Analyzer.
- GPS trajectory analytics, wearable sensor integration, indoor/outdoor exposure classification.

AFRICA ROAD NETWORK DENSITY MAP (placealert.org/roadnet/):
- Interactive hexagonal map of road network density across Africa derived from OpenStreetMap.

HARMONAIZE (placealert.org/harmonaize/):
- Climate & Health Data Harmonisation toolkit.

For technical issues or account problems, contact the PALs admin."""


# ── Security helpers ──────────────────────────────────────────────────────────

def get_api_key():
    """Extract API key from X-API-Key header or ?api_key= query param."""
    return (request.headers.get('X-API-Key') or
            request.args.get('api_key') or
            (request.get_json(silent=True) or {}).get('api_key'))


def require_key():
    """Returns (key_info dict, None) or (None, error response).
    Accepts either a researcher DB API key (X-API-Key) or a catalogue
    session token (X-Session-Token) issued by /api/catalogue-login.
    """
    token = request.headers.get('X-Session-Token', '')
    if token and access_db.validate_catalogue_token(token):
        return {'countries': ['Kenya', 'Mozambique', 'Gambia'], 'name': 'catalogue'}, None

    key = get_api_key()
    if not key:
        return None, (jsonify({'error': 'API key required. Include X-API-Key header.'}), 401)
    info = access_db.validate_key(key)
    if not info:
        return None, (jsonify({'error': 'Invalid or revoked API key.'}), 403)
    return info, None


@app.route('/api/catalogue-user-login', methods=['POST'])
def catalogue_user_login():
    """Per-user login for both catalogues — email + password → session token."""
    data      = request.json or {}
    catalogue = data.get('catalogue', 'precise')
    email     = data.get('email', '').strip()
    password  = data.get('password', '')

    if not email or not password:
        return jsonify({'ok': False, 'error': 'Email and password required'}), 400

    user = access_db.authenticate_catalogue_user(catalogue, email, password)
    if not user:
        return jsonify({'ok': False, 'error': 'Invalid email or password'}), 401
    if not user['is_active']:
        return jsonify({'ok': False, 'error': 'Your access has been revoked. Contact the administrator.'}), 403
    if user['tokens_used'] >= user['token_budget']:
        return jsonify({'ok': False, 'error': 'Your token budget is exhausted. Contact the administrator.'}), 403

    token = access_db.issue_user_catalogue_token(user['id'])
    return jsonify({
        'ok':           True,
        'token':        token,
        'name':         user['name'],
        'tokens_used':  user['tokens_used'],
        'token_budget': user['token_budget'],
    })


def is_safe_query(sql):
    """Allow SELECT / WITH / SHOW / DESCRIBE / PRAGMA statements."""
    stripped = sql.strip().upper()
    read_only_starts = ('SELECT', 'WITH', 'SHOW', 'DESCRIBE', 'DESC', 'PRAGMA', 'EXPLAIN')
    if not any(stripped.startswith(s) for s in read_only_starts):
        return False, "Only read-only queries are allowed (SELECT, SHOW, DESCRIBE)."
    forbidden = ['DROP', 'DELETE', 'INSERT', 'UPDATE', 'CREATE', 'ALTER', 'TRUNCATE']
    for word in forbidden:
        if re.search(r'\b' + word + r'\b', stripped):
            return False, f"Query contains forbidden keyword: {word}"
    return True, None


def _coerce(v):
    """Coerce DuckDB return values to JSON-serialisable Python scalars."""
    import datetime as _dt
    if isinstance(v, (_dt.date, _dt.datetime)):
        return v.isoformat()
    if hasattr(v, '__float__') and not isinstance(v, (int, str, bool, type(None))):
        return float(v)
    return v


# ── PII stripping — never let individual participant/patient IDs reach the LLM ─

_PRECISE_ID_COLS = frozenset({'f2a_participant_id', 'f2a_precise_id', 'pid'})
_HE2AT_ID_COLS   = frozenset({'Patient_Identifier'})


def _strip_id_cols(result, id_cols):
    """Remove participant/patient identifier columns from execute_query results
    before they are sent back to the LLM, preventing verbatim ID disclosure."""
    if 'columns' not in result or 'rows' not in result:
        return result
    keep = [c for c in result['columns'] if c not in id_cols]
    if len(keep) == len(result['columns']):
        return result
    return {
        'columns':   keep,
        'rows':      [{k: v for k, v in r.items() if k not in id_cols}
                      for r in result['rows']],
        'row_count': result.get('row_count', len(result['rows'])),
    }


def apply_country_filter(sql, countries):
    """
    Wrap every reference to daily_data, sensor_daily, and sensor_raw so queries
    are restricted to the caller's approved countries.  Works for both FROM and JOIN.
    sensor_daily/sensor_raw are also rewritten to use the sensor. catalog prefix.
    """
    if not countries:
        return "SELECT * FROM daily_data WHERE 1=0"

    c_list = ', '.join(f"'{c}'" for c in countries)

    # daily_data — Country column (capital C)
    subq_daily = (f"(SELECT * FROM daily_data "
                  f"WHERE Country IN ({c_list})) AS daily_data")
    filtered = re.sub(r'\bFROM\s+daily_data\b', f'FROM {subq_daily}', sql, flags=re.IGNORECASE)
    filtered = re.sub(r'\bJOIN\s+daily_data\b',  f'JOIN {subq_daily}', filtered, flags=re.IGNORECASE)

    # sensor_daily — country column (lowercase c), qualify with sensor. catalog
    subq_sensor_daily = (f"(SELECT * FROM sensor.sensor_daily "
                         f"WHERE country IN ({c_list})) AS sensor_daily")
    filtered = re.sub(r'\bFROM\s+sensor_daily\b', f'FROM {subq_sensor_daily}', filtered, flags=re.IGNORECASE)
    filtered = re.sub(r'\bJOIN\s+sensor_daily\b',  f'JOIN {subq_sensor_daily}', filtered, flags=re.IGNORECASE)

    # sensor_raw — country column (lowercase c), qualify with sensor. catalog
    subq_sensor_raw = (f"(SELECT * FROM sensor.sensor_raw "
                       f"WHERE country IN ({c_list})) AS sensor_raw")
    filtered = re.sub(r'\bFROM\s+sensor_raw\b', f'FROM {subq_sensor_raw}', filtered, flags=re.IGNORECASE)
    filtered = re.sub(r'\bJOIN\s+sensor_raw\b',  f'JOIN {subq_sensor_raw}', filtered, flags=re.IGNORECASE)

    return filtered


def _open_conn():
    """Open precise.duckdb read-only and attach sensor.duckdb."""
    conn = duckdb.connect(DB_PATH, read_only=True)
    conn.execute(f"ATTACH '{SENSOR_DB_PATH}' AS sensor (READ_ONLY)")
    return conn


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.route('/api/health')
def health():
    key_info, err = require_key()
    if err:
        return err

    countries = key_info['countries']
    conn = _open_conn()
    try:
        c_list = ', '.join(f"'{c}'" for c in countries)
        count = conn.execute(
            f"SELECT COUNT(*) FROM daily_data WHERE Country IN ({c_list})"
        ).fetchone()[0]
        participants = conn.execute(
            f"SELECT COUNT(DISTINCT f2a_participant_id) FROM daily_data "
            f"WHERE Country IN ({c_list})"
        ).fetchone()[0]
        return jsonify({
            'status': 'ok',
            'authorised_countries': countries,
            'total_records': count,
            'participants': participants,
            'user': key_info['name'],
        })
    finally:
        conn.close()


@app.route('/api/schema')
def schema():
    key_info, err = require_key()
    if err:
        return err

    conn = _open_conn()
    try:
        columns = conn.execute("DESCRIBE daily_data").fetchall()
        return jsonify({
            'columns': [{'name': r[0], 'type': r[1]} for r in columns],
            'authorised_countries': key_info['countries'],
        })
    finally:
        conn.close()


@app.route('/api/query', methods=['POST'])
def query():
    key_info, err = require_key()
    if err:
        return err

    data = request.json or {}
    sql  = data.get('sql', '').strip()

    if not sql:
        return jsonify({'error': 'No SQL provided'}), 400

    safe, reason = is_safe_query(sql)
    if not safe:
        return jsonify({'error': reason}), 400

    # No hard row cap — user controls this via LIMIT in their SQL.
    # Default fetch is all rows; pass max_rows to cap if needed.
    max_rows = data.get('max_rows')

    # Inject country filter — user only sees their approved countries
    filtered_sql = apply_country_filter(sql, key_info['countries'])

    conn = _open_conn()
    try:
        cur = conn.execute(filtered_sql)
        # Preserve original column order from the table definition
        columns = [d[0] for d in cur.description]

        raw = cur.fetchmany(int(max_rows)) if max_rows else cur.fetchall()

        # Return rows as ordered lists (not dicts) so column order is
        # always guaranteed when the caller does pd.DataFrame(rows, columns=columns)
        rows = [[_coerce(v) for v in row] for row in raw]

        return jsonify({
            'columns':             columns,
            'rows':                rows,
            'row_count':           len(rows),
            'truncated':           bool(max_rows and len(rows) == int(max_rows)),
            'authorised_countries': key_info['countries'],
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    finally:
        conn.close()


@app.route('/api/query/arrow', methods=['POST'])
def query_arrow():
    """
    Same as /api/query but returns Apache Arrow IPC stream (binary).
    ~10-50x faster than JSON for large result sets — no serialisation overhead.
    Use PreciseDB.query() which calls this automatically.
    """
    key_info, err = require_key()
    if err:
        return err

    data = request.json or {}
    sql  = data.get('sql', '').strip()

    if not sql:
        return jsonify({'error': 'No SQL provided'}), 400

    safe, reason = is_safe_query(sql)
    if not safe:
        return jsonify({'error': reason}), 400

    # Optional row limit — inject as a subquery wrapper if requested
    max_rows = data.get('max_rows')
    if max_rows:
        sql = f"SELECT * FROM ({sql}) __q LIMIT {int(max_rows)}"

    filtered_sql = apply_country_filter(sql, key_info['countries'])

    conn = _open_conn()
    try:
        result      = conn.execute(filtered_sql)
        arrow_table = result.fetch_arrow_table()

        sink   = io.BytesIO()
        writer = _ipc.new_stream(sink, arrow_table.schema)
        writer.write_table(arrow_table)
        writer.close()

        return Response(
            sink.getvalue(),
            mimetype='application/vnd.apache.arrow.stream',
            headers={
                'X-Row-Count':            str(arrow_table.num_rows),
                'X-Authorised-Countries': ','.join(key_info['countries']),
            }
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    finally:
        conn.close()


@app.route('/api/query/csv', methods=['POST'])
def query_csv():
    """
    Same as /api/query but returns CSV text.
    Designed for R users: read.csv(text = content(resp, as = "text"))
    No special packages required beyond httr.
    """
    key_info, err = require_key()
    if err:
        return err

    data = request.json or {}
    sql  = data.get('sql', '').strip()

    if not sql:
        return jsonify({'error': 'No SQL provided'}), 400

    safe, reason = is_safe_query(sql)
    if not safe:
        return jsonify({'error': reason}), 400

    max_rows = data.get('max_rows')
    if max_rows:
        sql = f"SELECT * FROM ({sql}) __q LIMIT {int(max_rows)}"

    filtered_sql = apply_country_filter(sql, key_info['countries'])

    conn = _open_conn()
    try:
        cur     = conn.execute(filtered_sql)
        columns = [d[0] for d in cur.description]
        rows    = cur.fetchall()

        buf = io.StringIO()
        import csv as _csv
        writer = _csv.writer(buf)
        writer.writerow(columns)
        writer.writerows(rows)

        return Response(
            buf.getvalue(),
            mimetype='text/csv',
            headers={
                'X-Row-Count':            str(len(rows)),
                'X-Authorised-Countries': ','.join(key_info['countries']),
                'Content-Disposition':    'attachment; filename="precise_data.csv"',
            }
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    finally:
        conn.close()


_CHAT_SYSTEM_PROMPT = """You are Shmron, an expert research assistant for the PRECISE Network study on Environmental & Social Determinants of Maternal Health. 6,960 pregnant women across 525 communities: Kenya (n=3,535, 370 communities), Mozambique (n=2,097, 74 communities), The Gambia (n=1,328, 81 communities).

**CRITICAL RULES:**
1. You MUST call execute_query for every question about data, exposures, counts, distributions, trends, or statistics. Never describe what you will do — just call the tool and present the results.
2. NUMBERS MUST ADD UP: Use GROUP BY Country in a single query when comparing countries. Never run separate queries for total vs breakdown — they diverge due to NULL Country rows. If you must use separate queries, reconcile totals explicitly.
3. Always include WHERE Country IS NOT NULL if you want only the three named countries.
4. **PRIVACY — NEVER quote raw participant identifier hashes.** Do not include f2a_participant_id, f2a_precise_id, or pid hash strings in your response text. You SHOULD report participant-level statistics: counts, distributions, min/max values, percentiles, percentages. When a query finds the most-exposed participant, describe their village, country, and exposure level — omit the ID hash. Example: "The highest-exposed participant was in Nanoro, Burkina Faso with a mean UTCI of 33.4°C."

Settlement breakdown (GHSL_class): Kenya 66% Urban/8% Rural/26% Peri_Urban | Mozambique 72%/21%/7% | Gambia 40%/60%/0.2%

=== DATABASE SCHEMA (table: daily_data, 3,129,121 rows — one row per participant per exposure day) ===

ALL numeric columns below are DOUBLE unless stated otherwise. Do NOT use TRY_CAST on DOUBLE columns.

**Identifiers & Geography:**
- f2a_participant_id, f2a_precise_id, participant_status (VARCHAR)
- Country (VARCHAR): 'Kenya', 'Mozambique', 'Gambia'
- Village (VARCHAR), Village code (DOUBLE), Longitude, Latitude (DOUBLE)
- health_facility (VARCHAR), GHSL_class (VARCHAR): 'Urban', 'Rural', 'Peri_Urban' (underscore, not hyphen), 'No_Data'
- IPCC_zone, climate_zone, season_wb (VARCHAR)

**Dates:**
- exposure_day (TIMESTAMP_NS): cast with exposure_day::DATE for date comparisons
- conception_date (DATE), delivery_date (DATE), edd (DATE)

**Air Quality (all DOUBLE):**
- CAMS2_pm2p5_ugm3: PM2.5 μg/m³
- Fire_Smoke_PM25, Non_Fire_Smoke_PM25
- CAMS2_aod550: total aerosol optical depth
- CAMS2_bcaod550: black carbon AOD
- CAMS2_duaod550: CAMS dust AOD
- duaod550, duaod550_village, duaod550_facility: alternative dust AOD source
- CAMS2_tcno2_umolm2, CAMS2_gtco3_DU, CAMS2_tcco_gm2, CAMS2_tcso2_DU

**Dust (MERRA2 — all DOUBLE):**
- MERRA2_dust_AOD550: dust aerosol optical depth at 550nm
- MERRA2_dust_pm25_ugm3: dust-attributed PM2.5
- MERRA2_dust_column_kgm2: vertically integrated dust column

**Temperature (all DOUBLE):**
- ERA5_T2M_Mean, ERA5_T2M_Mean_village, ERA5_T2M_Mean_facility
- ERA5_T2M_Max, ERA5_T2M_Max_village, ERA5_T2M_Max_facility
- ERA5_T2M_Min, ERA5_T2M_Min_village, ERA5_T2M_Min_facility
- ERA5_T2M_Diurnal: diurnal temperature range
- ERA5_T2M_deviation, ERA5_T2M_threshold
- ERA5_LST_mean, ERA5_LST_mean_village, ERA5_LST_mean_facility: land surface temp
- ERA5_T2M_extreme_hot_day, ERA5_T2M_heatwave_day (VARCHAR: 'Yes'/'No' — use = 'Yes' or = 'No', NOT boolean TRUE/FALSE)
- MERRA2_T2M_mean, MERRA2_T2M_max: air temperature
- CAMS2_t2m_C, CAMS2_d2m_C: CAMS 2m temperature & dew point

**Heat Stress Indices (all DOUBLE):**
- UTCI_min, UTCI_mean, UTCI_max: Universal Thermal Climate Index (°C)
  UTCI stress categories: <0°C cold, 9-26°C no stress, 26-32°C moderate, 32-38°C strong, 38-46°C very strong, >46°C extreme
- WBGT_mean: Wet Bulb Globe Temperature
- WBGTsimple_mean: simplified WBGT
- WBT_mean: wet bulb temperature
- humidex_mean: humidex comfort index
- HI_mean: Heat Index
- tasapp_mean: apparent temperature
- tasdp_mean: dew point temperature
- Wind_Chill_mean, MRT_mean: mean radiant temp, NET_mean, ws_mean

**Weather (DOUBLE):**
- Relative_Humidity, Precipitation
- Precip_village, Precip_facility

**Environment (all DOUBLE):**
- NDVI, NDVI_village, NDVI_facility: vegetation index
- meanDEM: elevation (m)

**Access to Care (all DOUBLE):**
- PW_WalkDist_Fac, PW_WalkTime_Fac: walk distance (m) and time (min) to facility
- PW_DriveDist_Fac, PW_DriveTime_Fac: drive distance and time
- PW_PubTrans_Dist_Fac, PW_PubTrans_Time_Fac: public transport
- PW_EuclMajorRd, PW_EuclHwy: Euclidean distance to roads
- PW_RoadDens, RQI: road density and quality index
- PW_WalkIso_MajorRd, PW_WalkIso_Hwy, PW_DriveIso_MajorRd, PW_DriveIso_Hwy

**Socioeconomic (all DOUBLE):**
- RWI: Relative Wealth Index
- VIIRS: night-time light intensity
- PPI_score, extreme_poverty_line, poverty_line

**Soil Nutrients (all DOUBLE):**
- N_mean, P_mean, K_mean, Ca_mean

**Demographics:**
- age_enrolment (DOUBLE), Ethnicity, religion, marital_status, highest_school_level, occupation (VARCHAR)
- dietary_diversity (DOUBLE), minimum_dietary_diversity (VARCHAR)

**Maternal Anthropometry & Clinical (DOUBLE unless stated):**
- maternal_height, maternal_weight, maternal_bmi, average_muac
- maternal_bmi_categorised, average_muac_categorised (VARCHAR)
- average_dbp, average_sbp: blood pressure
- gh_overall, ch_overall, pe_overall, ht_overall, hdp_overall, gh_iso_overall (VARCHAR 'Yes'/'No'): hypertensive disorders
- ht_flag, ch_flag, gh_flag (VARCHAR 'Yes'/'No'): hypertension flags
- bp_cat (VARCHAR): 'Normal BP', 'Elevated BP', 'Stage 1 Hypertension', 'Stage 2 Hypertension'
- hiv_status, pre_gest_diab, previous_csection, previous_stillbirth, tobacco_use (VARCHAR 'Yes'/'No')
- maternal_death (VARCHAR 'Yes'/'No')
- deliverylocation (VARCHAR): 'District hospital', 'PHC', 'Regional hospital', 'Home', 'Private hospital/clinic'
- delivery_mode (VARCHAR): 'Unassisted vaginal without episiotomy', 'Unassisted vaginal with episiotomy', 'Caesarean section', 'Operative vaginal', 'Vaginal breech'
- cooking (VARCHAR): 'Biomass', 'Coal', 'Gas', 'Kerosene', 'Electric'
- heating (VARCHAR): 'Not needed', 'Electric', 'Coal', 'Biomass', 'Battery'
- lighting (VARCHAR): 'Electric', 'Battery', 'Kerosene', 'Biomass', 'Generator'
- sanitation_jmp (VARCHAR): 'At least basic', 'Limited', 'Unimproved', 'Open defecation'
- water_jmp (VARCHAR): 'At least basic', 'Limited', 'Unimproved', 'Surface water'
- hygiene_jmp (VARCHAR): 'At least limited', 'No facility'
- parity, age_edd (DOUBLE)
- nicu_admission (VARCHAR): 'Yes', 'No', "Don't know"

**Birth Outcomes:**
- Birthweight (DOUBLE): grams
- bwt_kg, bwt_percentile, bwt_zscore (DOUBLE)
- GA_PRECISE, GA_clinical (DOUBLE): gestational age in weeks
- preterm, lowbirthweight, svn, neonataldeath, stillbirth, livebirth, bornalive (VARCHAR: 'Yes'/'No')
- sga (VARCHAR): full descriptive strings — 'Appropriate for Gestational Age (10th to 90th centile)', 'Small for Gestational Age (3rd - <10th centile)', 'Severely Small for Gestational Age (<3rd centile)', 'Large for Gestational Age (>90th centile)', 'Large for Gestational Age (>97th centile)'. For binary SGA use: CASE WHEN sga LIKE 'Small%' OR sga LIKE 'Severe%' THEN 1 ELSE 0 END
- sex_of_baby (VARCHAR): 'Male', 'Female', 'Indeterminate'
- ageatdeath (BOOLEAN: TRUE/FALSE — one of the few actual booleans; use = TRUE or = FALSE)
- placenta_weight, placenta_weight_ratio (DOUBLE)

=== PERSONAL SENSOR DATABASE (343 participants, 3 countries) ===

A subset of 343 PRECISE participants wore personal air quality and environmental sensors during a monitoring window (typically 5–7 days). Unlike the satellite/reanalysis data in daily_data, these are ground-level PERSONAL measurements — what the participant themselves breathed and experienced.

**Table: sensor_daily** — 3,190 rows — ONE ROW PER PARTICIPANT PER DAY
- pid (VARCHAR): participant ID — joins to f2a_participant_id in daily_data
- country (VARCHAR): 'Kenya', 'Mozambique', 'Gambia'
- exposure_date (DATE): the calendar day
- season (VARCHAR): 'Dry' or 'Wet'
- pm25_mean, pm25_max, pm25_min, pm25_sd (DOUBLE): personal PM2.5 μg/m³ — daily aggregate
- no2_mean, no2_max, no2_min, no2_sd (DOUBLE): personal NO2 ppb — daily aggregate
- temp_mean, temp_max, temp_min, temp_sd (DOUBLE): personal temperature °C — daily aggregate
- rh_mean, rh_max, rh_min, rh_sd (DOUBLE): personal relative humidity % — daily aggregate
- lat, lon (DOUBLE): mean GPS position for the day
- n_readings (BIGINT): number of minute-level readings that day (use to assess data quality)
- monitoring_start, monitoring_end (DATE): the participant's full sensor deployment window

**Table: sensor_raw** — 3,723,990 rows — ONE ROW PER MINUTE (use sparingly — always add LIMIT)
- pid, country (VARCHAR), datetime (TIMESTAMP)
- pm25, no2, temp, rh, lat, lon (DOUBLE): raw minute-level measurements
- season, pid_season (VARCHAR)
- startdate, enddate (TIMESTAMP): monitoring window

**WHEN TO USE EACH TABLE:**
| Question | Table |
|---|---|
| Cohort characteristics, outcomes (birthweight, preterm, SGA), demographics | daily_data |
| Area-level climate exposure (ERA5, CAMS2, MERRA2), satellite data | daily_data |
| Participants WITHOUT personal sensor data (n=6,960 total) | daily_data |
| Personal sensor PM2.5, NO2, temperature, humidity | sensor_daily |
| Intra-day patterns, diurnal variation, time of peak exposure | sensor_raw |
| Comparing satellite vs personal exposure (exposure misclassification) | JOIN both |

**IMPORTANT — TEMPORAL MISMATCH:**
The sensor monitoring window (2022–2023) was conducted AFTER most participants' pregnancy period. Do NOT join on date. Instead, join at the participant level — aggregate each participant's pregnancy-period satellite exposure from daily_data and their sensor-period personal exposure from sensor_daily separately, then compare.

**CROSS-DATABASE JOIN — satellite (pregnancy period) vs personal sensor (monitoring window):**
```sql
-- Country-level summary: average satellite PM2.5 during pregnancy vs average personal PM2.5 during sensor window
WITH sat AS (
    SELECT f2a_participant_id, Country,
           AVG(CAMS2_pm2p5_ugm3) AS satellite_pm25_pregnancy
    FROM daily_data
    WHERE Country IS NOT NULL AND CAMS2_pm2p5_ugm3 IS NOT NULL
    GROUP BY f2a_participant_id, Country
),
sens AS (
    SELECT pid, country,
           AVG(pm25_mean) AS personal_pm25_sensor,
           COUNT(*)       AS sensor_days
    FROM sensor_daily
    GROUP BY pid, country
),
joined AS (
    SELECT sat.Country,
           sat.satellite_pm25_pregnancy,
           sens.personal_pm25_sensor,
           sens.personal_pm25_sensor - sat.satellite_pm25_pregnancy AS exposure_difference
    FROM sat
    JOIN sens ON sat.f2a_participant_id = sens.pid
)
SELECT Country,
       ROUND(AVG(satellite_pm25_pregnancy),2) AS mean_satellite_pm25,
       ROUND(AVG(personal_pm25_sensor),2)     AS mean_personal_pm25,
       ROUND(AVG(exposure_difference),2)      AS mean_difference,
       COUNT(*)                               AS n_participants
FROM joined
GROUP BY Country
ORDER BY Country
```
Join key: sensor_daily.pid = daily_data.f2a_participant_id (participant level only — do NOT join on date)

NOTE: Only 343 participants have sensor data (Kenya=105, Mozambique=78, Gambia=160). Counts from sensor_daily/sensor_raw will be much smaller than daily_data. Always note this when reporting sensor-based results.

=== QUERY GUIDELINES ===
Always use aggregations — never return more than 50 raw rows.

**CHARTING RULES — MANDATORY:**
Always call render_chart IN THE SAME RESPONSE as execute_query (both tools in one turn). You decide the chart type — even when the user does not ask for one, pick the most appropriate type for the data returned.

CRITICAL — chart data must come from the query you just ran, not a separate unrelated query. If the analysis filtered to Country='Gambia' AND PM2.5>500, the chart/map must show those exact records — never silently run a broader query to get "nicer" chart data and then present it alongside text about a different subset.

**AUTO-SELECT the right chart type:**
| Situation | Chart type |
|---|---|
| "compare X across countries/settlements", means/counts grouped by category | bar |
| "how does X vary", "distribution of", "spread", "outliers", "percentiles" | box |
| "breakdown", "proportion", "share", "what percentage" | pie or doughnut |
| "trend over time", "monthly", "seasonal", "how has X changed" | line |
| "relationship between X and Y", "does X correlate with Y" | scatter |
| "correlation matrix", "correlations between multiple variables" | heatmap |
| After run_regression with multiple predictors | forest |
| "map", "where are participants", "geographic", "spatial distribution", "show on a map" | map |
| Single scalar result (one number) | no chart needed |

**How to query and build each type:**
- **bar**: GROUP BY category → AVG/COUNT → labels=categories, datasets=[{label, data}]
- **line**: DATE_TRUNC('month', exposure_day::DATE) as month GROUP BY month ORDER BY month → labels=months
- **pie/doughnut**: COUNT GROUP BY → compute % → labels=groups, datasets=[{label, data:[...]}]
- **box** (always use PERCENTILE_CONT — never pass raw rows):
  ```sql
  SELECT Country,
    PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY col) as p5,
    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY col) as q1,
    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY col) as median,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY col) as q3,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY col) as p95,
    AVG(col) as mean
  FROM daily_data WHERE Country IS NOT NULL AND col IS NOT NULL GROUP BY Country
  ```
  → box_data: [{name, lowerfence:p5, q1, median, q3, upperfence:p95, mean}]
  One render_chart call per variable. For multiple variables call render_chart once each.
- **heatmap**: SELECT CORR(a,b), CORR(a,c)… FROM daily_data → build symmetric z_values matrix
  → x_labels=y_labels=[var names], z_values=[[1,r_ab,…],[r_ab,1,…],…]
- **scatter**: SELECT col_a, col_b FROM daily_data ORDER BY RANDOM() LIMIT 500
  → scatter_data: [{name, x:[...], y:[...]}] — one series per group if comparing countries
- **map** (geographic scatter — always aggregate to village level for clean maps):
  ```sql
  SELECT Village,
      AVG(Latitude)              AS lat,       -- Latitude → lat (ALWAYS, never swap)
      AVG(Longitude)             AS lon,       -- Longitude → lon (ALWAYS, never swap)
      MAX(Country)               AS country,
      AVG(CAMS2_pm2p5_ugm3)      AS value,
      COUNT(DISTINCT f2a_participant_id) AS n_participants
  FROM daily_data
  WHERE Latitude IS NOT NULL AND Longitude IS NOT NULL AND Country IS NOT NULL
  GROUP BY Village
  ```
  → map_data: [{lat, lon, label: Village + " (" + country + ")", value, size: n_participants}]
  → color_label: "Mean PM2.5 (μg/m³)"
  For binary outcomes (e.g. preterm rate): AVG(CASE WHEN preterm='Yes' THEN 1.0 ELSE 0.0 END)*100 AS value → color_label: "Preterm Rate (%)"
  Participant-level maps: GROUP BY f2a_participant_id — LIMIT 3000.

  CONSISTENCY RULE — the map query MUST filter to the same subset as the analysis:
  If the text analysis filtered to Country='Gambia' AND PM2.5 > 500, the map SQL must include those exact same WHERE conditions. Never render a generic all-villages map when the analysis is about a specific filtered subset — the dots on the map must represent the same records the text is describing.

  COORDINATE VALIDATION — check your map_data before rendering:
  - Gambia:     lat 12–14°N  (positive),  lon -17 to -13°W (negative)
  - Kenya:      lat -5 to 5°N (near zero), lon  34–42°E    (positive ~39)
  - Mozambique: lat -27 to -10°S (negative), lon 32–41°E  (positive ~35)
  If any point falls outside these ranges you have swapped Latitude/Longitude — fix the SQL aliases before calling render_chart.

- **forest** (always call after run_regression — use the coefficients it returned):
  → forest_data: [{variable, coef, ci_lower, ci_upper, p_value, stars}] — exclude Intercept row
  → scale: 'OR' for Logit models (exponentiates to odds ratios, null line at 1), 'coef' for OLS
  → x_label: e.g. "Coefficient (grams)" for OLS, "Odds Ratio" for Logit

NEVER echo chart_type, labels, datasets, box_data, or any raw numbers/JSON in your text. Write only natural language findings.

=== REGRESSION & STATISTICAL INFERENCE ===

**Phase 1 — Simple regression via DuckDB (for single-predictor questions, no extra tool):**
When asked for slope, trend, or R² between two continuous variables, use REGR_* inside execute_query:
```sql
SELECT Country,
    REGR_SLOPE(Birthweight, CAMS2_pm2p5_ugm3)     AS slope,
    REGR_INTERCEPT(Birthweight, CAMS2_pm2p5_ugm3) AS intercept,
    REGR_R2(Birthweight, CAMS2_pm2p5_ugm3)        AS r_squared,
    COUNT(*)                                        AS n
FROM daily_data
WHERE CAMS2_pm2p5_ugm3 IS NOT NULL AND Birthweight IS NOT NULL AND Country IS NOT NULL
GROUP BY Country
```
Interpret: "Each 1 μg/m³ increase in PM2.5 is associated with a [slope]g change in birthweight (R²=[r_squared], n=[n])."

**Phase 2 — Multivariate regression via run_regression tool:**
Use when: user wants to control for confounders, multiple predictors in one model, binary outcomes (LBW/preterm), user asks for p-values or statistical significance.

model_type:
- OLS → continuous outcomes (Birthweight, GA_PRECISE, bwt_zscore, maternal_bmi, UTCI_mean)
- Logit → binary 0/1 outcomes — convert VARCHAR in SQL first

formula syntax (R-style):
- 'Birthweight ~ CAMS2_pm2p5_ugm3 + RWI'  — OLS, two predictors
- 'Birthweight ~ CAMS2_pm2p5_ugm3 + RWI + C(Country)'  — C() wraps categorical fixed effects
- 'lowbirthweight ~ CAMS2_pm2p5_ugm3 + RWI + C(Country)'  — Logit
- 'Birthweight ~ CAMS2_pm2p5_ugm3 * RWI'  — interaction term

SQL rules for run_regression — ALWAYS aggregate to EXACTLY one row per participant:

**EXPOSURE WINDOW — this is the most important rule:**
The dataset deliberately includes daily rows from preconception through ~1 month post-delivery. Each window is epidemiologically distinct and must be selected correctly using CASE WHEN inside AVG() — NEVER average across all rows indiscriminately.

Named exposure windows and their SQL filters:

  Preconception — 3 months before conception (default when user says "preconception"):
    exposure_day::DATE >= (conception_date - INTERVAL '90 days')
    AND exposure_day::DATE < conception_date
  Preconception — 6 months (use if user specifies):
    exposure_day::DATE >= (conception_date - INTERVAL '180 days')
    AND exposure_day::DATE < conception_date
  Whole gestation (default for most birth outcome analyses):
    exposure_day::DATE >= conception_date AND exposure_day::DATE <= delivery_date
  T1 — organogenesis, weeks 1–12:
    DATEDIFF('day', conception_date, exposure_day::DATE) BETWEEN 0 AND 83
  T2 — fetal growth, weeks 13–26:
    DATEDIFF('day', conception_date, exposure_day::DATE) BETWEEN 84 AND 181
  T3 — lung maturation/preterm risk, weeks 27–birth:
    DATEDIFF('day', conception_date, exposure_day::DATE) >= 182
  Post-delivery — 1 month after birth (neonatal outcomes):
    exposure_day::DATE > delivery_date
    AND exposure_day::DATE <= (delivery_date + INTERVAL '30 days')

When user does NOT specify a window, default to whole gestation for birth outcome regressions.
When user says "preconception", use the 3-month window unless they specify otherwise.
When reporting results, ALWAYS state which exposure window was used: "using mean exposure over the 3-month preconception period" or "gestational mean" etc.

GROUP BY f2a_participant_id only — do NOT include Country, GHSL_class, or other categorical columns in GROUP BY (they are constant per participant; include them in SELECT as MAX(Country) etc.)

Binary VARCHAR outcomes (lowbirthweight, preterm, stillbirth, neonataldeath, livebirth) MUST be converted with CASE WHEN col='Yes' THEN 1 ELSE 0 END.

LIMIT 10000 always.

**Canonical example — gestational + preconception PM2.5, comparing both windows:**
```sql
SELECT f2a_participant_id,
    MAX(Country)    AS Country,
    MAX(GHSL_class) AS GHSL_class,
    -- preconception mean (3 months before conception)
    AVG(CASE WHEN exposure_day::DATE >= (conception_date - INTERVAL '90 days')
              AND exposure_day::DATE <  conception_date
             THEN CAMS2_pm2p5_ugm3 END)                          AS PM25_preconception,
    -- whole-gestation mean
    AVG(CASE WHEN exposure_day::DATE >= conception_date
              AND exposure_day::DATE <= delivery_date
             THEN CAMS2_pm2p5_ugm3 END)                          AS PM25_gestational,
    AVG(CASE WHEN exposure_day::DATE >= conception_date
              AND exposure_day::DATE <= delivery_date
             THEN RWI END)                                         AS RWI,
    MAX(Birthweight)                                               AS Birthweight,
    MAX(CASE WHEN lowbirthweight='Yes' THEN 1 ELSE 0 END)         AS lowbirthweight,
    MAX(CASE WHEN preterm='Yes' THEN 1 ELSE 0 END)                AS preterm
FROM daily_data
WHERE Country IS NOT NULL
  AND conception_date IS NOT NULL
  AND delivery_date IS NOT NULL
  AND Birthweight IS NOT NULL
GROUP BY f2a_participant_id
LIMIT 10000
```

CRITICAL — the N should be the number of DISTINCT participants with complete data (≤ 6,960). If N > 6,960 the GROUP BY is wrong — fix it before proceeding.

When reporting results, always state clearly: "exposure averaged over the gestational period" (or "T1/T2/T3" if trimester-specific).

After run_regression returns results, ALWAYS call render_chart with chart_type='forest' using the coefficients from the result (exclude the Intercept row). Use scale='OR' for Logit models. Then write a clinical interpretation: for each significant predictor (p<0.05), state the coefficient and what it means for maternal health. Mention N and R²/pseudo-R².

**REGRESSION INTERPRETATION RULES:**
- When interpreting a regression table, every coefficient, OR, SE, CI, and p-value you quote in text MUST come directly from the run_regression result returned to you in this conversation. Never invent, round differently, or recompute them from memory.
- The reference category in a categorical variable (e.g. Gambia in C(Country)) is captured by the Intercept — it does NOT appear as a named row. If the user asks about the reference group's absolute rate, run a separate execute_query COUNT to get it from the data.
- When converting a logit coefficient to an Odds Ratio, compute exp(coef) exactly — e.g. coef=0.1050 → OR=exp(0.1050)=1.111, NOT 0.756. Never cite an OR that contradicts the coefficient in the table.
- If asked a follow-up about regression results, re-read the regression output from earlier in the conversation rather than guessing.

**RESPONSE STYLE:**
- Always query the live database — never guess or cite from memory
- Present results with counts, percentages, and averages
- Compare across countries when relevant
- Highlight notable findings"""

_CHAT_TOOLS = [
    {
        "name": "execute_query",
        "description": "Run a SQL SELECT query against the PRECISE database. Three tables are available: (1) 'daily_data' — 3,129,121 rows, one per participant per exposure day, satellite/modelled exposures + outcomes; (2) 'sensor_daily' — 3,190 rows, personal sensor data aggregated to daily means/max/min/SD per participant; (3) 'sensor_raw' — 3,723,990 minute-level sensor readings (use sparingly with LIMIT). See the system prompt for which table to use. You can call this tool multiple times and can JOIN across tables.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "A DuckDB-compatible SELECT query. Table names: 'daily_data', 'sensor_daily', 'sensor_raw'. ALL numeric columns in daily_data are already DOUBLE — do NOT use TRY_CAST on any of them. ERA5_T2M_extreme_hot_day and ERA5_T2M_heatwave_day are VARCHAR 'Yes'/'No' columns — use = 'Yes' not = TRUE. ageatdeath is a real BOOLEAN — use = TRUE or = FALSE. sga is VARCHAR with full descriptive strings (not Yes/No) — use LIKE 'Small%' for SGA cases."
                }
            },
            "required": ["sql"]
        }
    },
    {
        "name": "render_chart",
        "description": "Render an interactive chart inline in the conversation. Call in the SAME response as execute_query. Supports bar, line, pie, doughnut, scatter, box plot, and heatmap/correlation matrix.",
        "input_schema": {
            "type": "object",
            "properties": {
                "chart_type": {
                    "type": "string",
                    "enum": ["bar", "line", "pie", "doughnut", "scatter", "box", "heatmap", "forest", "map"],
                    "description": "bar/line/pie/doughnut → use labels+datasets. box → use box_data (needs PERCENTILE_CONT query). heatmap → use x_labels+y_labels+z_values. scatter → use scatter_data. forest → use forest_data (coefficients + CIs from regression). map → use map_data (lat/lon points from village or participant aggregation)."
                },
                "title": {"type": "string", "description": "Chart title"},
                "labels": {
                    "type": "array", "items": {"type": "string"},
                    "description": "Category labels for bar/line/pie/doughnut"
                },
                "datasets": {
                    "type": "array",
                    "description": "Data series for bar/line/pie/doughnut — one per group/variable",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string"},
                            "data":  {"type": "array", "items": {"type": "number"}}
                        },
                        "required": ["label", "data"]
                    }
                },
                "box_data": {
                    "type": "array",
                    "description": "Pre-computed box plot stats per group. Use PERCENTILE_CONT(0.05/0.25/0.50/0.75/0.95) in SQL.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name":       {"type": "string"},
                            "lowerfence": {"type": "number", "description": "p5"},
                            "q1":         {"type": "number", "description": "p25"},
                            "median":     {"type": "number", "description": "p50"},
                            "q3":         {"type": "number", "description": "p75"},
                            "upperfence": {"type": "number", "description": "p95"},
                            "mean":       {"type": "number"}
                        },
                        "required": ["name", "q1", "median", "q3"]
                    }
                },
                "x_labels": {"type": "array", "items": {"type": "string"},
                             "description": "Column variable names for heatmap"},
                "y_labels": {"type": "array", "items": {"type": "string"},
                             "description": "Row variable names for heatmap"},
                "z_values": {
                    "type": "array",
                    "items": {"type": "array", "items": {"type": "number"}},
                    "description": "2D array [rows][cols] of values in [-1,1] for correlation heatmaps"
                },
                "scatter_data": {
                    "type": "array",
                    "description": "Data series for scatter — query LIMIT 500 for a representative sample",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "x":    {"type": "array", "items": {"type": "number"}},
                            "y":    {"type": "array", "items": {"type": "number"}}
                        },
                        "required": ["name", "x", "y"]
                    }
                },
                "forest_data": {
                    "type": "array",
                    "description": "Predictor rows for a forest plot. Use after run_regression — pull values from the coefficients it returns. Exclude Intercept. For Logit models set scale='OR' to exponentiate.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "variable": {"type": "string"},
                            "coef":     {"type": "number", "description": "Point estimate (coefficient or log-OR)"},
                            "ci_lower": {"type": "number", "description": "Lower 95% CI"},
                            "ci_upper": {"type": "number", "description": "Upper 95% CI"},
                            "p_value":  {"type": "number"},
                            "stars":    {"type": "string", "description": "Significance stars from regression: ***, **, *, or empty"}
                        },
                        "required": ["variable", "coef", "ci_lower", "ci_upper"]
                    }
                },
                "scale": {
                    "type": "string",
                    "enum": ["coef", "OR"],
                    "description": "coef (default) — plot raw coefficients with null line at 0. OR — exponentiate to odds ratios, null line at 1. Use OR for Logit models."
                },
                "map_data": {
                    "type": "array",
                    "description": "Points for a geographic scatter map. Aggregate to village level (GROUP BY Village) for cleaner maps — 525 villages is ideal. Each point has a lat/lon, a numeric value for colour, and a label for hover.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "lat":   {"type": "number", "description": "Latitude"},
                            "lon":   {"type": "number", "description": "Longitude"},
                            "label": {"type": "string",  "description": "Hover label — village name, country, or participant ID"},
                            "value": {"type": "number",  "description": "Numeric value for colour scale — e.g. mean PM2.5, preterm rate"},
                            "size":  {"type": "number",  "description": "Optional marker size hint — e.g. n_participants"},
                            "group": {"type": "string",  "description": "Optional category for colour — e.g. Country"}
                        },
                        "required": ["lat", "lon", "label"]
                    }
                },
                "color_label": {"type": "string", "description": "Label for the colour scale on a map — e.g. 'Mean PM2.5 (μg/m³)'"},
                "y_label": {"type": "string", "description": "Y-axis label"},
                "x_label": {"type": "string", "description": "X-axis label"}
            },
            "required": ["chart_type", "title"]
        }
    },
    {
        "name": "run_regression",
        "description": "Run OLS or Logistic regression with statsmodels. Use when user wants to control for confounders, get p-values/confidence intervals, or model binary outcomes (LBW, preterm). The backend runs the model and streams a publication-quality coefficient table to the user. Do NOT use for simple single-predictor questions — use execute_query with REGR_SLOPE/REGR_R2 instead.",
        "input_schema": {
            "type": "object",
            "properties": {
                "model_type": {
                    "type": "string",
                    "enum": ["OLS", "Logit"],
                    "description": "OLS for continuous outcomes (Birthweight, GA_PRECISE, bwt_zscore). Logit for binary 0/1 outcomes (lowbirthweight, preterm, stillbirth — must be CASE WHEN col='Yes' THEN 1 ELSE 0 END in SQL)."
                },
                "formula": {
                    "type": "string",
                    "description": "R-style formula. E.g. 'Birthweight ~ CAMS2_pm2p5_ugm3 + RWI + C(Country)' or 'lowbirthweight ~ CAMS2_pm2p5_ugm3 + RWI'. Use C(var) for categorical predictors."
                },
                "sql_query": {
                    "type": "string",
                    "description": "DuckDB SELECT that returns ONE ROW PER PARTICIPANT (GROUP BY f2a_participant_id, Country). Include all formula variables. Binary VARCHAR outcomes must be converted to 0/1 with CASE WHEN. Use LIMIT 10000."
                },
                "title": {
                    "type": "string",
                    "description": "Descriptive title for the coefficient table, e.g. 'Effect of PM2.5 on Birthweight controlling for Wealth Index'"
                }
            },
            "required": ["model_type", "formula", "sql_query", "title"]
        }
    }
]


@app.route('/api/catalogue-login', methods=['POST'])
def catalogue_login():
    """Exchange the catalogue access code for a short-lived session token."""
    code = (request.json or {}).get('code', '').strip()
    if code != CATALOGUE_ACCESS_CODE:
        return jsonify({'ok': False, 'error': 'Invalid access code'}), 403
    return jsonify({'ok': True, 'token': access_db.issue_catalogue_token()})


@app.route('/portal/chat', methods=['POST'])
def portal_chat():
    """Public, rate-limited informational chat for the main portal widget."""
    ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
    if not _allow_ip(ip):
        return jsonify({'error': 'Too many requests — please wait a moment.'}), 429

    messages = (request.json or {}).get('messages', [])
    if not messages or messages[-1].get('role') != 'user':
        return jsonify({'error': 'messages must end with a user turn'}), 400

    def generate():
        try:
            import anthropic as _anthropic
            client = _anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY', ''))
            response = client.messages.create(
                model='claude-haiku-4-5-20251001',
                max_tokens=512,
                system=_PORTAL_SYSTEM,
                messages=messages[-10:],
            )
            text = response.content[0].text if response.content else 'Sorry, I had trouble answering that.'
            yield f"data: {json.dumps({'type': 'text', 'text': text})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'text': str(e)})}\n\n"

    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@app.route('/api/chat', methods=['POST'])
def chat():
    key_info, err = require_key()
    if err:
        return err

    data     = request.json or {}
    messages = data.get('messages', [])

    if not messages or messages[-1].get('role') != 'user':
        return jsonify({'error': 'messages must end with a user turn'}), 400

    countries = key_info['countries']
    sess_token = request.headers.get('X-Session-Token', '')

    def generate():
        try:
            import anthropic as _anthropic
            client = _anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY', ''))

            # Resolve the catalogue user for this session (may be None for API-key callers)
            cat_user    = access_db.get_catalogue_user_from_token(sess_token) if sess_token else None
            tokens_this_req = 0

            history = list(messages)
            max_iterations = 8

            for i in range(max_iterations):
                # Enforce token budget before each LLM call
                if cat_user and (cat_user['tokens_used'] + tokens_this_req) >= cat_user['token_budget']:
                    yield f"data: {json.dumps({'type': 'error', 'text': 'Your token budget is exhausted. Please contact the administrator.'})}\n\n"
                    break

                # Force tool use only on iteration 0 so Claude must call
                # execute_query + render_chart together in one turn.
                # From iteration 1 onwards Claude can write narrative freely.
                tool_choice = {'type': 'any'} if i == 0 else {'type': 'auto'}
                status = 'Thinking…' if i == 0 else 'Analysing…'
                yield f"data: {json.dumps({'type': 'status', 'text': status})}\n\n"

                response = client.messages.create(
                    model='claude-sonnet-4-20250514',
                    max_tokens=4096,
                    system=_CHAT_SYSTEM_PROMPT,
                    messages=history,
                    tools=_CHAT_TOOLS,
                    tool_choice=tool_choice,
                )

                # Accumulate token usage
                if hasattr(response, 'usage'):
                    tokens_this_req += (response.usage.input_tokens +
                                        response.usage.output_tokens)

                tool_blocks = [b for b in response.content if b.type == 'tool_use']
                text_blocks = [b for b in response.content if b.type == 'text']
                final_text  = text_blocks[0].text if text_blocks else ''

                # Append assistant turn to in-flight history
                assistant_content = []
                for b in response.content:
                    if b.type == 'text':
                        assistant_content.append({'type': 'text', 'text': b.text})
                    elif b.type == 'tool_use':
                        assistant_content.append({
                            'type': 'tool_use', 'id': b.id,
                            'name': b.name, 'input': b.input,
                        })
                history.append({'role': 'assistant', 'content': assistant_content})

                if not tool_blocks:
                    yield f"data: {json.dumps({'type': 'text', 'text': final_text})}\n\n"
                    break

                # Execute tool calls — render_chart streams to browser, execute_query hits DuckDB
                tool_results = []
                conn = _open_conn()
                try:
                    for block in tool_blocks:
                        if block.name == 'render_chart':
                            yield f"data: {json.dumps({'type': 'chart', 'spec': block.input})}\n\n"
                            result = {'rendered': True}
                        elif block.name == 'run_regression':
                            reg_sql    = block.input.get('sql_query', '')
                            formula    = block.input.get('formula', '')
                            model_type = block.input.get('model_type', 'OLS')
                            reg_title  = block.input.get('title', 'Regression Analysis')
                            safe, reason = is_safe_query(reg_sql)
                            if not safe:
                                result = {'error': reason}
                            else:
                                try:
                                    import pandas as _pd
                                    import statsmodels.formula.api as _smf
                                    filtered_reg = apply_country_filter(reg_sql, countries)
                                    yield f"data: {json.dumps({'type': 'status', 'text': 'Running regression model…'})}\n\n"
                                    df = conn.execute(filtered_reg).df()
                                    # Deduplicate on participant ID if present —
                                    # guards against GROUP BY mistakes that produce
                                    # multiple rows per person.
                                    id_col = next((c for c in df.columns
                                                   if 'participant_id' in c.lower()), None)
                                    if id_col and df[id_col].duplicated().any():
                                        df = df.drop_duplicates(subset=[id_col])
                                    df = df.dropna()
                                    if len(df) < 10:
                                        result = {'error': f'Too few complete observations ({len(df)}) for regression. Check the SQL query.'}
                                    else:
                                        if model_type == 'Logit':
                                            fit = _smf.logit(formula, data=df).fit(disp=False)
                                            r2_key, r2_val = 'pseudo_r_squared', float(fit.prsquared)
                                        else:
                                            fit = _smf.ols(formula, data=df).fit()
                                            r2_key, r2_val = 'r_squared', float(fit.rsquared)
                                        ci = fit.conf_int()
                                        coefficients = []
                                        for var in fit.params.index:
                                            p = float(fit.pvalues[var])
                                            stars = '***' if p < 0.001 else '**' if p < 0.01 else '*' if p < 0.05 else ''
                                            coefficients.append({
                                                'variable': str(var),
                                                'coef':     round(float(fit.params[var]), 4),
                                                'se':       round(float(fit.bse[var]), 4),
                                                'p_value':  round(p, 4),
                                                'ci_lower': round(float(ci.loc[var, 0]), 4),
                                                'ci_upper': round(float(ci.loc[var, 1]), 4),
                                                'stars':    stars,
                                            })
                                        stats_table = {
                                            'title':        reg_title,
                                            'model_type':   model_type,
                                            'formula':      formula,
                                            'n_obs':        int(fit.nobs),
                                            r2_key:         round(r2_val, 4),
                                            'aic':          round(float(fit.aic), 1),
                                            'coefficients': coefficients,
                                        }
                                        yield f"data: {json.dumps({'type': 'stats_table', 'result': stats_table})}\n\n"
                                        # Return condensed summary to Claude for narrative
                                        result = {
                                            'n_obs': stats_table['n_obs'],
                                            r2_key:  stats_table[r2_key],
                                            'aic':   stats_table['aic'],
                                            'coefficients': [
                                                {k: v for k, v in c.items() if k != 'se'}
                                                for c in coefficients
                                            ],
                                        }
                                except Exception as e:
                                    result = {'error': f'Regression failed: {str(e)}'}

                        else:  # execute_query
                            sql = block.input.get('sql', '')
                            safe, reason = is_safe_query(sql)
                            if not safe:
                                result = {'error': reason}
                            else:
                                filtered = apply_country_filter(sql, countries)
                                try:
                                    cur  = conn.execute(filtered)
                                    cols = [d[0] for d in cur.description]
                                    rows = cur.fetchmany(50)
                                    # Return rows as dicts so Claude reads
                                    # {"Country":"Gambia","median":44.5} directly
                                    # instead of parsing column-index arrays —
                                    # prevents country↔value mix-ups in box_data.
                                    result = _strip_id_cols({
                                        'columns':   cols,
                                        'rows':      [
                                            {cols[j]: _coerce(v) for j, v in enumerate(r)}
                                            for r in rows
                                        ],
                                        'row_count': len(rows),
                                    }, _PRECISE_ID_COLS)
                                except Exception as e:
                                    result = {'error': str(e)}
                        tool_results.append({
                            'type':        'tool_result',
                            'tool_use_id': block.id,
                            'content':     json.dumps(result),
                        })
                finally:
                    conn.close()

                history.append({'role': 'user', 'content': tool_results})

            # Persist token usage for catalogue users
            if cat_user and tokens_this_req > 0:
                access_db.add_tokens_used(cat_user['id'], tokens_this_req)

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'text': str(e)})}\n\n"

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control':      'no-cache',
            'X-Accel-Buffering':  'no',   # prevents nginx from buffering the stream
        },
    )


# ══════════════════════════════════════════════════════════════════════════════
# HE2AT CENTRE — CATALOGUE AI
# ══════════════════════════════════════════════════════════════════════════════

HE2AT_DB_PATH    = '/home/rutendo/PRECISE/he2at.duckdb'
HE2AT_ACCESS_CODE = os.environ.get('HE2AT_ACCESS_CODE', 'HE2AT2022')

_HE2AT_SYSTEM = """You are an expert research assistant for the HE²AT Centre (Heat and Health African Transdisciplinary Center). You help researchers explore environmental exposure data linked to pregnancy cohorts across Sub-Saharan Africa.

**STUDY OVERVIEW:**
74,483 pregnant women across 9 countries and 295 study locations, 21 study cohorts, 2003–2024.
Country breakdown: Kenya 25,139 | Malawi 14,037 | Zambia 12,024 | South Africa 11,534 | The Gambia 2,987 | Ethiopia 2,547 | Burkina Faso 2,362 | Ghana 1,997 | Tanzania 1,856

**CRITICAL RULES:**
1. ALWAYS call execute_query for any question about counts, distributions, trends, or statistics. Never guess numbers.
2. ALWAYS call render_chart in the SAME response as execute_query. Choose the best chart type automatically.
3. CHART DATA MUST MATCH TEXT: the chart must show exactly the same filtered subset as your narrative.
4. Use aggregations — never return more than 50 raw rows. The AI receives only up to 50 result rows.
5. If N patients > 74,483 your query is wrong — GROUP BY Patient_Identifier to deduplicate.
6. **PRIVACY — NEVER quote raw patient identifier hashes.** Do not include Patient_Identifier hash strings in your response text. You SHOULD report patient-level statistics: counts, distributions, min/max values, percentiles, percentages. When a query finds the most-exposed patient, describe their Study, Location, Country, and exposure level — omit the ID hash. Example: "The highest-exposed patient was in the MUL140 study, Nanoro, Burkina Faso with a mean UTCI of 33.4°C."

**DATABASES — three tables, one view:**

### PRIMARY TABLE: patient_exposures  (74,483 rows — ONE ROW PER PATIENT)
Use this for almost everything: comparisons across countries/studies, distributions, correlations.

**Identifiers:**
- Patient_Identifier (VARCHAR), Country (VARCHAR), Study (VARCHAR), Location (VARCHAR)
- Latitude (DOUBLE), Longitude (DOUBLE)

**Urbanisation & Climate Zone:**
- urbanization (DOUBLE: 10=Very Low Density Rural, 11=Low Density Rural, 12=Rural Cluster, 13=Suburban/Peri-urban, 21=Semi-dense Urban, 22=Dense Urban Cluster, 23=Urban Centre)
- urbanization_class (VARCHAR): 'Very Low Density Rural', 'Low Density Rural', 'Rural Cluster', 'Suburban / Peri-urban', 'Semi-dense Urban Cluster', 'Dense Urban Cluster', 'Urban Centre'
- ipcc_climate_zone_code (DOUBLE), ipcc_climate_zone_name (VARCHAR): 'Cold', 'Polar', 'Temperate', 'Tropical'

**Geography & Soil:**
- elevation (DOUBLE): metres above sea level
- soil_nitrogen (DOUBLE), soil_phosphorus (DOUBLE), soil_organic_carbon (DOUBLE): kg/ha or g/kg

**Socioeconomic:**
- rwi (DOUBLE): Relative Wealth Index (range −0.85 to 1.92; higher = wealthier)

**Temperature (all DOUBLE — patient gestational mean):**
- tas_mean: 2m air temperature mean (°C)
- tas_min: 2m air temperature minimum (°C)
- tas_max: 2m air temperature maximum (°C)

**Heat Stress Indices (all DOUBLE):**
- WBGT_mean: Wet Bulb Globe Temperature (°C) — occupational heat stress threshold: 28°C
- humidex_mean: Humidex (°C equivalent)
- Wind_Chill_mean, HI_mean: Heat Index (°C), tasapp_mean: apparent temperature (°C)
- tasdp_mean: dew point temperature (°C)
- WBGTsimple_mean: simplified WBGT (°C), WBT_mean: wet bulb temperature (°C)
- NET_mean: Net Effective Temperature (°C)
- ws_mean: wind speed (m/s)
- UTCI_min, UTCI_mean, UTCI_max: Universal Thermal Climate Index (°C)
  UTCI stress: <0 cold stress | 9–26 no stress | 26–32 moderate heat | 32–38 strong | 38–46 very strong | >46 extreme
- MRT_min, MRT_mean, MRT_max: Mean Radiant Temperature (°C)

**Air Quality (all DOUBLE):**
- pm2p5_mean: PM2.5 μg/m³ (WHO guideline: 5 μg/m³ annual; >35 unhealthy)
- no2as_mean: NO₂ (μg/m³)
- aod550_mean: aerosol optical depth at 550nm
- od550bc_mean: black carbon AOD

**Dust (all DOUBLE):**
- duaod550_nc_mean: dust AOD 550nm
- duexttau_ee_mean: dust extinction optical depth (MERRA-2)
- dusmass25_ee_mean: dust PM2.5 mass concentration (μg/m³)
- ducmass_ee_mean: total dust column mass (kg/m²)

**Climate & Environment (all DOUBLE):**
- RH_mean: relative humidity (%)
- ndvi: NDVI vegetation index (−1 to 1; >0.3 = moderate vegetation)
- precipitation: mm/day

### SECONDARY TABLE: climate_data  (305,808 rows — ONE ROW PER LOCATION PER DAY)
Use for temporal trends (monthly/seasonal), geographic patterns across locations.
Same climate columns as patient_exposures plus: Exposure_Date (DATE).
Join to exposure_days on (Study, Location, Exposure_Date) if you need patient context.
Key columns: Country, Study, Location, Latitude, Longitude, Exposure_Date, [all climate columns]

### SECONDARY TABLE: exposure_days  (23M rows — ONE ROW PER PATIENT PER DAY)
Use only with aggressive GROUP BY. Contains: Patient_Identifier, Country, Study, Location,
Latitude, Longitude, Birth_Date (DATE), GA_Days (DOUBLE: gestational age in days),
Exposure_Date (DATE), Window_Type ('full' or 'dob_only').
Window_Type='full' means full gestational period; 'dob_only' means date of birth only.

### VIEW: exposure_climate  (joins exposure_days + climate_data)
Full patient-day dataset with all climate variables. Use with heavy aggregation only.
Always add WHERE Window_Type='full' for gestational analyses.

=== QUERY STRATEGY ===

| Question type | Table to use |
|---|---|
| Mean exposure by country/study/urbanisation | patient_exposures |
| Distribution, box plots, correlations | patient_exposures |
| Regression (exposure → health) | patient_exposures (GROUP BY Patient_Identifier already done) |
| Monthly/seasonal trends | climate_data (GROUP BY month/season) |
| Geographic map of exposures | patient_exposures (Latitude, Longitude per patient) |
| Patient count by country | patient_exposures |
| Gestational day trajectory | exposure_climate WHERE Window_Type='full' |

=== CHARTING RULES (MANDATORY) ===
Always call render_chart IN THE SAME RESPONSE as execute_query. Pick the best type automatically:

| Situation | Chart type |
|---|---|
| Compare means across countries/studies/urban classes | bar |
| Distribution, spread, outliers | box |
| Proportion, breakdown by category | pie or doughnut |
| Trend over time (monthly, seasonal) | line |
| Relationship between two continuous variables | scatter |
| Correlation matrix | heatmap |
| Regression coefficients with CIs | forest |
| Geographic pattern, "where", "map", spatial | map |

**box** — use PERCENTILE_CONT:
```sql
SELECT Country,
  PERCENTILE_CONT(0.05) WITHIN GROUP (ORDER BY col) as p5,
  PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY col) as q1,
  PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY col) as median,
  PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY col) as q3,
  PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY col) as p95,
  AVG(col) as mean
FROM patient_exposures WHERE Country IS NOT NULL AND col IS NOT NULL GROUP BY Country
```
→ box_data: [{name, lowerfence:p5, q1, median, q3, upperfence:p95, mean}]

**map** — aggregate to location level:
```sql
SELECT Location, AVG(Latitude) AS lat, AVG(Longitude) AS lon,
       MAX(Country) AS country, AVG(pm2p5_mean) AS value,
       COUNT(DISTINCT Patient_Identifier) AS n_patients
FROM patient_exposures
WHERE Latitude IS NOT NULL AND Longitude IS NOT NULL
GROUP BY Location
```
→ map_data: [{lat, lon, label, value, size: n_patients}]

COORDINATE VALIDATION (check before rendering):
- Burkina Faso: lat 10–16°N, lon −6 to 2°E
- Ethiopia:     lat 4–15°N, lon 33–48°E
- Ghana:        lat 5–11°N, lon −4 to 1°E
- Kenya:        lat −5 to 5°N, lon 34–42°E
- Malawi:       lat −17 to −9°S, lon 32–36°E
- South Africa: lat −35 to −22°S, lon 16–33°E
- Tanzania:     lat −12 to −1°S, lon 29–41°E
- The Gambia:   lat 13–14°N, lon −17 to −13°W
- Zambia:       lat −18 to −8°S, lon 22–34°E

NEVER echo raw chart JSON, labels, or datasets in your text. Write only natural language findings.

=== REGRESSION ===
**Simple (single predictor):** use REGR_SLOPE / REGR_R2 inside execute_query on patient_exposures.
**Multivariate:** use run_regression tool. patient_exposures already has one row per patient — no GROUP BY needed.
- OLS for continuous (WBGT_mean, pm2p5_mean, UTCI_mean, tas_mean)
- Logit for binary outcomes (must be CASE WHEN ... THEN 1 ELSE 0 END)
- Always state which exposure variable and what the coefficient means clinically.

**RESPONSE STYLE:**
- Always query the live database — never guess or cite numbers from memory.
- Compare across countries when relevant.
- Always state N (number of patients) in any result.
- Highlight the most notable finding first."""


@app.route('/api/he2at-login', methods=['POST'])
def he2at_login():
    """Exchange the HE2AT catalogue access code for a short-lived session token."""
    code = (request.json or {}).get('code', '').strip()
    if code != HE2AT_ACCESS_CODE:
        return jsonify({'ok': False, 'error': 'Invalid access code'}), 403
    return jsonify({'ok': True, 'token': access_db.issue_catalogue_token()})


@app.route('/api/he2at/chat', methods=['POST'])
def he2at_chat():
    """HE2AT Centre AI research assistant — token-gated, streams SSE."""
    token = request.headers.get('X-Session-Token', '')
    if not token or not access_db.validate_catalogue_token(token):
        return jsonify({'error': 'Valid session token required. Please log in.'}), 401

    data     = request.json or {}
    messages = data.get('messages', [])
    if not messages or messages[-1].get('role') != 'user':
        return jsonify({'error': 'messages must end with a user turn'}), 400

    def generate():
        try:
            import anthropic as _anthropic
            client      = _anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY', ''))
            cat_user    = access_db.get_catalogue_user_from_token(token)
            tokens_this_req = 0
            history     = list(messages)
            max_iterations = 8

            for i in range(max_iterations):
                # Enforce token budget
                if cat_user and (cat_user['tokens_used'] + tokens_this_req) >= cat_user['token_budget']:
                    yield f"data: {json.dumps({'type': 'error', 'text': 'Your token budget is exhausted. Please contact the administrator.'})}\n\n"
                    break

                tool_choice = {'type': 'any'} if i == 0 else {'type': 'auto'}
                yield f"data: {json.dumps({'type': 'status', 'text': 'Thinking…' if i == 0 else 'Analysing…'})}\n\n"

                response = client.messages.create(
                    model='claude-sonnet-4-20250514',
                    max_tokens=4096,
                    system=_HE2AT_SYSTEM,
                    messages=history,
                    tools=_CHAT_TOOLS,
                    tool_choice=tool_choice,
                )

                if hasattr(response, 'usage'):
                    tokens_this_req += (response.usage.input_tokens +
                                        response.usage.output_tokens)

                tool_blocks = [b for b in response.content if b.type == 'tool_use']
                text_blocks = [b for b in response.content if b.type == 'text']

                assistant_content = []
                for b in response.content:
                    if b.type == 'text':
                        assistant_content.append({'type': 'text', 'text': b.text})
                    elif b.type == 'tool_use':
                        assistant_content.append({
                            'type': 'tool_use', 'id': b.id,
                            'name': b.name, 'input': b.input,
                        })
                history.append({'role': 'assistant', 'content': assistant_content})

                if not tool_blocks:
                    yield f"data: {json.dumps({'type': 'text', 'text': text_blocks[0].text if text_blocks else ''})}\n\n"
                    break

                tool_results = []
                conn = duckdb.connect(HE2AT_DB_PATH, read_only=True)
                try:
                    for block in tool_blocks:
                        if block.name == 'render_chart':
                            yield f"data: {json.dumps({'type': 'chart', 'spec': block.input})}\n\n"
                            result = {'rendered': True}

                        elif block.name == 'run_regression':
                            reg_sql    = block.input.get('sql_query', '')
                            formula    = block.input.get('formula', '')
                            model_type = block.input.get('model_type', 'OLS')
                            reg_title  = block.input.get('title', 'Regression')
                            safe, reason = is_safe_query(reg_sql)
                            if not safe:
                                result = {'error': reason}
                            else:
                                try:
                                    import pandas as _pd
                                    import statsmodels.formula.api as _smf
                                    yield f"data: {json.dumps({'type': 'status', 'text': 'Running regression…'})}\n\n"
                                    df = conn.execute(reg_sql).df()
                                    id_col = next((c for c in df.columns if 'patient' in c.lower()), None)
                                    if id_col and df[id_col].duplicated().any():
                                        df = df.drop_duplicates(subset=[id_col])
                                    df = df.dropna()
                                    if len(df) < 10:
                                        result = {'error': f'Too few observations ({len(df)}) for regression.'}
                                    else:
                                        if model_type == 'Logit':
                                            fit = _smf.logit(formula, data=df).fit(disp=False)
                                            r2_key, r2_val = 'pseudo_r_squared', float(fit.prsquared)
                                        else:
                                            fit = _smf.ols(formula, data=df).fit()
                                            r2_key, r2_val = 'r_squared', float(fit.rsquared)
                                        ci = fit.conf_int()
                                        coefficients = []
                                        for var in fit.params.index:
                                            p = float(fit.pvalues[var])
                                            stars = '***' if p < 0.001 else '**' if p < 0.01 else '*' if p < 0.05 else ''
                                            coefficients.append({
                                                'variable': str(var),
                                                'coef':     round(float(fit.params[var]), 4),
                                                'se':       round(float(fit.bse[var]), 4),
                                                'p_value':  round(p, 4),
                                                'ci_lower': round(float(ci.loc[var, 0]), 4),
                                                'ci_upper': round(float(ci.loc[var, 1]), 4),
                                                'stars':    stars,
                                            })
                                        stats_table = {
                                            'title': reg_title, 'model_type': model_type,
                                            'formula': formula, 'n_obs': int(fit.nobs),
                                            r2_key: round(r2_val, 4),
                                            'aic': round(float(fit.aic), 1),
                                            'coefficients': coefficients,
                                        }
                                        yield f"data: {json.dumps({'type': 'stats_table', 'result': stats_table})}\n\n"
                                        result = {
                                            'n_obs': stats_table['n_obs'], r2_key: stats_table[r2_key],
                                            'aic': stats_table['aic'],
                                            'coefficients': [{k: v for k, v in c.items() if k != 'se'} for c in coefficients],
                                        }
                                except Exception as e:
                                    result = {'error': f'Regression failed: {e}'}

                        else:  # execute_query
                            sql = block.input.get('sql', '')
                            safe, reason = is_safe_query(sql)
                            if not safe:
                                result = {'error': reason}
                            else:
                                try:
                                    cur  = conn.execute(sql)
                                    cols = [d[0] for d in cur.description]
                                    rows = cur.fetchmany(50)
                                    result = _strip_id_cols({
                                        'columns':   cols,
                                        'rows':      [{cols[j]: _coerce(v) for j, v in enumerate(r)} for r in rows],
                                        'row_count': len(rows),
                                    }, _HE2AT_ID_COLS)
                                except Exception as e:
                                    result = {'error': str(e)}

                        tool_results.append({
                            'type': 'tool_result', 'tool_use_id': block.id,
                            'content': json.dumps(result),
                        })
                finally:
                    conn.close()

                history.append({'role': 'user', 'content': tool_results})

            if cat_user and tokens_this_req > 0:
                access_db.add_tokens_used(cat_user['id'], tokens_this_req)

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'text': str(e)})}\n\n"

    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


# ══════════════════════════════════════════════════════════════════════════════
# SHARED CONVERSATION LINKS
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/api/share', methods=['POST'])
def create_share():
    """Store a conversation for public read-only sharing. Requires catalogue session token."""
    token = request.headers.get('X-Session-Token', '')
    if not token or not access_db.validate_catalogue_token(token):
        return jsonify({'error': 'Authentication required'}), 401

    data      = request.json or {}
    catalogue = data.get('catalogue', '')
    messages  = data.get('messages', [])
    title     = data.get('title', '')

    if not messages:
        return jsonify({'error': 'No messages to share'}), 400

    share_id = access_db.create_shared_conversation(catalogue, title, messages)
    return jsonify({'ok': True, 'share_id': share_id})


@app.route('/api/share/<share_id>', methods=['GET'])
def get_share(share_id):
    """Retrieve a shared conversation — public, no auth required."""
    conv = access_db.get_shared_conversation(share_id)
    if not conv:
        return jsonify({'error': 'Share not found'}), 404
    return jsonify(conv)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
