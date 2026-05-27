from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import duckdb
import re
import io
import os
import json
import sys
sys.path.insert(0, '/home/rutendo/PRECISE')
import access_db
import pyarrow.ipc as _ipc

app = Flask(__name__)
CORS(app)

DB_PATH = '/home/rutendo/PRECISE/precise.duckdb'


# ── Security helpers ──────────────────────────────────────────────────────────

def get_api_key():
    """Extract API key from X-API-Key header or ?api_key= query param."""
    return (request.headers.get('X-API-Key') or
            request.args.get('api_key') or
            (request.get_json(silent=True) or {}).get('api_key'))


def require_key():
    """Returns (key_info dict, None) or (None, error response)."""
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

        def _coerce(v):
            if hasattr(v, '__float__') and not isinstance(v, (int, str, bool, type(None))):
                return float(v)
            return v

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
1. You MUST call execute_query for every question about data, exposures, counts, distributions, trends, or statistics. Never describe what you will do — just call the tool and present the results. Do not generate preamble text before calling the tool.
2. NUMBERS MUST ADD UP: When reporting totals alongside country breakdowns, always use a single query with GROUP BY Country so all rows come from the same result set. Never compute a total in one query and country breakdown in another — they will diverge due to participants with NULL Country values. If you must use separate queries, always reconcile: total = Kenya + Mozambique + Gambia + (any NULL/unassigned). Flag discrepancies explicitly.
3. Always include WHERE Country IS NOT NULL if you want only the three named countries, and make clear when you are excluding unassigned participants.

Settlement breakdown (GHSL_class): Kenya 66% Urban/8% Rural/26% Peri-Urban | Mozambique 72%/21%/7% | Gambia 40%/60%/0.2%

Social survey data (NOT in daily_data — cite directly if asked):
- Financial autonomy: Kenya 68.8% | Mozambique 50.6% | Gambia 72.9%
- Community help: Kenya 75.0% | Mozambique 51.3% | Gambia 49.6%
- Partner availability: Kenya 80.3% | Mozambique 63.1% | Gambia 66.3%

=== DATABASE SCHEMA (table: daily_data, 3,129,121 rows — one row per participant per exposure day) ===

**Identifiers & Geography:**
- f2a_participant_id (VARCHAR): unique participant ID
- Country (VARCHAR): 'Kenya', 'Mozambique', 'Gambia'
- Village (VARCHAR), Village code (BIGINT), Longitude/Latitude (DOUBLE)
- health_facility (VARCHAR), GHSL_class (VARCHAR): 'Urban', 'Rural', 'Peri-Urban'
- climate_zone (VARCHAR), IPCC_zone (VARCHAR)

**Dates:**
- exposure_day (DATE): the daily record date
- conception_date (VARCHAR), delivery_date (DATE)

**Air Quality:**
- CAMS2_pm2p5_ugm3 (DOUBLE): PM2.5 μg/m³
- Fire_Smoke_PM25, Non_Fire_Smoke_PM25 (DOUBLE)
- CAMS2_aod550, CAMS2_bcaod550, CAMS2_duaod550 (DOUBLE): AOD
- CAMS2_tcno2_umolm2, CAMS2_gtco3_DU, CAMS2_tcco_gm2, CAMS2_tcso2_DU (DOUBLE)

**Temperature:**
- ERA5_T2M_Mean, ERA5_T2M_Max (DOUBLE)
- ERA5_T2M_Min, ERA5_T2M_Diurnal (VARCHAR — use TRY_CAST AS DOUBLE)
- ERA5_LST_village (VARCHAR — use TRY_CAST AS DOUBLE)
- ERA5_T2M_deviation (DOUBLE)
- ERA5_T2M_extreme_hot_day, ERA5_T2M_heatwave_day (BOOLEAN)

**Heat Stress:**
- MERRA2_T2MWET_mean, MERRA2_T2MWET_max (DOUBLE): wet bulb temp

**Weather:**
- Relative_Humidity (DOUBLE), Precipitation (DOUBLE)

**Environment:**
- NDVI_village (VARCHAR — use TRY_CAST AS DOUBLE)
- meanDEM (VARCHAR — use TRY_CAST AS DOUBLE): elevation

**Access to Care (all VARCHAR — use TRY_CAST AS DOUBLE):**
- PW_WalkDist_Fac, PW_WalkTime_Fac, PW_DriveDist_Fac, PW_DriveTime_Fac
- PW_PubTrans_Dist_Fac, PW_PubTrans_Time_Fac
- PW_EuclMajorRd, PW_EuclHwy, PW_RoadDens, RQI
- PW_WalkIso_MajorRd, PW_WalkIso_Hwy, PW_DriveIso_MajorRd, PW_DriveIso_Hwy

**Socioeconomic:**
- RWI (DOUBLE): Relative Wealth Index
- VIIRS (DOUBLE): night lights
- PPI_score, extreme_poverty_line, poverty_line (DOUBLE)

**Soil (all VARCHAR — use TRY_CAST AS DOUBLE):**
- N_mean, P_mean, K_mean, Ca_mean

**Demographics:**
- age_enrolment (DOUBLE), Ethnicity, religion, marital_status (VARCHAR)
- highest_school_level, occupation (VARCHAR)

=== QUERY GUIDELINES ===
Always use aggregations — never return more than 50 raw rows.

**RESPONSE STYLE:**
- Always use the execute_query tool for any data question — you have the full dataset
- Present results clearly with counts, percentages, and averages
- Compare across countries (Kenya, Mozambique, Gambia) when relevant
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
    }
]


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
                tool_choice = {'type': 'any'} if i == 0 else {'type': 'auto'}
                status = 'Thinking…' if i == 0 else 'Querying data…'
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

                # Execute each SQL tool call against DuckDB
                tool_results = []
                conn = duckdb.connect(DB_PATH, read_only=True)
                try:
                    for block in tool_blocks:
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
                                result = {
                                    'columns':   cols,
                                    'rows':      [[_coerce(v) for v in r] for r in rows],
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
