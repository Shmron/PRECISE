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

DB_PATH = '/home/rutendo/PRECISE/precise.duckdb'

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
    if hasattr(v, '__float__') and not isinstance(v, (int, str, bool, type(None))):
        return float(v)
    return v


def apply_country_filter(sql, countries):
    """
    Wrap every reference to daily_data so queries are restricted to
    the caller's approved countries.  Works for both FROM and JOIN.

    e.g. countries = ['Kenya', 'Gambia']
    'SELECT * FROM daily_data LIMIT 10'
    → 'SELECT * FROM (SELECT * FROM daily_data
                      WHERE Country IN ('Kenya','Gambia')) AS daily_data LIMIT 10'
    """
    if not countries:
        # No countries approved — return unsatisfiable query
        return "SELECT * FROM daily_data WHERE 1=0"

    c_list  = ', '.join(f"'{c}'" for c in countries)
    subq    = (f"(SELECT * FROM daily_data "
               f"WHERE Country IN ({c_list})) AS daily_data")

    # Replace  FROM daily_data  and  JOIN daily_data
    filtered = re.sub(r'\bFROM\s+daily_data\b',  f'FROM {subq}',  sql, flags=re.IGNORECASE)
    filtered = re.sub(r'\bJOIN\s+daily_data\b',   f'JOIN {subq}',  filtered, flags=re.IGNORECASE)
    return filtered


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.route('/api/health')
def health():
    key_info, err = require_key()
    if err:
        return err

    countries = key_info['countries']
    conn = duckdb.connect(DB_PATH, read_only=True)
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

    conn = duckdb.connect(DB_PATH, read_only=True)
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

    conn = duckdb.connect(DB_PATH, read_only=True)
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

    conn = duckdb.connect(DB_PATH, read_only=True)
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

    conn = duckdb.connect(DB_PATH, read_only=True)
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

Settlement breakdown (GHSL_class): Kenya 66% Urban/8% Rural/26% Peri-Urban | Mozambique 72%/21%/7% | Gambia 40%/60%/0.2%

=== DATABASE SCHEMA (table: daily_data, 3,129,121 rows — one row per participant per exposure day) ===

ALL numeric columns below are DOUBLE unless stated otherwise. Do NOT use TRY_CAST on DOUBLE columns.

**Identifiers & Geography:**
- f2a_participant_id, f2a_precise_id, participant_status (VARCHAR)
- Country (VARCHAR): 'Kenya', 'Mozambique', 'Gambia'
- Village (VARCHAR), Village code (DOUBLE), Longitude, Latitude (DOUBLE)
- health_facility (VARCHAR), GHSL_class (VARCHAR): 'Urban', 'Rural', 'Peri-Urban'
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
- ERA5_T2M_extreme_hot_day, ERA5_T2M_heatwave_day (VARCHAR: 'TRUE'/'FALSE' — use = 'TRUE' not = TRUE)
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
- gh_overall, ch_overall, pe_overall, ht_overall, hdp_overall, bp_cat (VARCHAR): hypertensive disorders
- hiv_status, deliverylocation, delivery_mode, cooking, heating, lighting (VARCHAR)
- sanitation_jmp, water_jmp, hygiene_jmp, tobacco_use (VARCHAR)
- parity, age_edd (DOUBLE)

**Birth Outcomes:**
- Birthweight (DOUBLE): grams
- bwt_kg, bwt_percentile, bwt_zscore (DOUBLE)
- GA_PRECISE, GA_clinical (DOUBLE): gestational age in weeks
- preterm, sga, lowbirthweight, svn, neonataldeath, stillbirth, livebirth (VARCHAR: 'Yes'/'No' or '1'/'0')
- sex_of_baby (VARCHAR), placenta_weight, placenta_weight_ratio (DOUBLE)

=== QUERY GUIDELINES ===
Always use aggregations — never return more than 50 raw rows.

**CHARTING RULES — MANDATORY:**
Always call render_chart IN THE SAME RESPONSE as execute_query (both tools in one turn). You decide the chart type — even when the user does not ask for one, pick the most appropriate type for the data returned:

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
        "description": "Run a SQL SELECT query against the PRECISE daily data table (daily_data). This table has 3,129,121 rows — one row per participant per exposure day. Use aggregations (COUNT, AVG, SUM, GROUP BY) to answer questions. Always write efficient queries. The table name is 'daily_data'. You can call this tool multiple times to answer different parts of a question.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "A DuckDB-compatible SELECT query against 'daily_data'. Use TRY_CAST(col AS DOUBLE) for VARCHAR columns that contain numbers (ERA5_T2M_Min, ERA5_T2M_Diurnal, ERA5_LST_village, RQI, meanDEM, N_mean, P_mean, K_mean, Ca_mean, PW_RoadDens, PW_EuclMajorRd, PW_EuclHwy, PW_WalkIso_MajorRd, PW_WalkIso_Hwy, PW_DriveIso_MajorRd, PW_DriveIso_Hwy, PW_WalkDist_Fac, PW_DriveDist_Fac, PW_PubTrans_Dist_Fac, PW_WalkTime_Fac, PW_DriveTime_Fac, PW_PubTrans_Time_Fac, NDVI_village). ERA5_T2M_extreme_hot_day and ERA5_T2M_heatwave_day are BOOLEAN columns."
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
                    "enum": ["bar", "line", "pie", "doughnut", "scatter", "box", "heatmap", "forest"],
                    "description": "bar/line/pie/doughnut → use labels+datasets. box → use box_data (needs PERCENTILE_CONT query). heatmap → use x_labels+y_labels+z_values. scatter → use scatter_data. forest → use forest_data (coefficients + CIs from regression)."
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

    def generate():
        try:
            import anthropic as _anthropic
            client = _anthropic.Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY', ''))

            history = list(messages)
            max_iterations = 8

            for i in range(max_iterations):
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
                conn = duckdb.connect(DB_PATH, read_only=True)
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
                                    result = {
                                        'columns':   cols,
                                        'rows':      [
                                            {cols[j]: _coerce(v) for j, v in enumerate(r)}
                                            for r in rows
                                        ],
                                        'row_count': len(rows),
                                    }
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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
