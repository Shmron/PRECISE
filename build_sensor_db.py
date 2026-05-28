#!/usr/bin/env python3
"""
Build sensor.duckdb from personal sensor CSVs (Kenya, Mozambique, Gambia).

Tables created:
  sensor_raw   — minute-level readings (all rows from the 3 CSVs)
  sensor_daily — daily aggregates per participant (mean, max, min, SD, count)
"""
import duckdb
import os
import time

DB_PATH = '/home/rutendo/PRECISE/sensor.duckdb'
CSV_PATHS = {
    'Kenya':      '/home/rutendo/Kenya/Kenya.csv',
    'Mozambique': '/home/rutendo/Mozambique/Mozambique.csv',
    'Gambia':     '/home/rutendo/Gambia/Gambia.csv',
}

if os.path.exists(DB_PATH):
    os.remove(DB_PATH)
    print(f'Removed existing {DB_PATH}')

con = duckdb.connect(DB_PATH)

# ── sensor_raw ─────────────────────────────────────────────────────────────────
print('Building sensor_raw ...')
t0 = time.time()

con.execute("""
CREATE TABLE sensor_raw (
    pid          VARCHAR,
    country      VARCHAR,
    datetime     TIMESTAMP,
    pm25         DOUBLE,
    no2          DOUBLE,
    temp         DOUBLE,
    rh           DOUBLE,
    lat          DOUBLE,
    lon          DOUBLE,
    season       VARCHAR,
    pid_season   VARCHAR,
    startdate    TIMESTAMP,
    enddate      TIMESTAMP
)
""")

for country, path in CSV_PATHS.items():
    print(f'  Loading {country} ({path}) ...')
    con.execute(f"""
    INSERT INTO sensor_raw
    SELECT
        "PID"        AS pid,
        "country"    AS country,
        TRY_CAST("date"      AS TIMESTAMP) AS datetime,
        TRY_CAST("pm25"      AS DOUBLE)    AS pm25,
        TRY_CAST("no2"       AS DOUBLE)    AS no2,
        TRY_CAST("temp"      AS DOUBLE)    AS temp,
        TRY_CAST("rh"        AS DOUBLE)    AS rh,
        TRY_CAST("lat"       AS DOUBLE)    AS lat,
        TRY_CAST("lon"       AS DOUBLE)    AS lon,
        "season"     AS season,
        "PID_season" AS pid_season,
        TRY_CAST("startdate" AS TIMESTAMP) AS startdate,
        TRY_CAST("enddate"   AS TIMESTAMP) AS enddate
    FROM read_csv_auto('{path}', ignore_errors=true)
    """)
    n = con.execute("SELECT COUNT(*) FROM sensor_raw").fetchone()[0]
    print(f'    sensor_raw now has {n:,} rows')

raw_count = con.execute("SELECT COUNT(*) FROM sensor_raw").fetchone()[0]
print(f'sensor_raw complete: {raw_count:,} rows  ({time.time()-t0:.1f}s)\n')

# ── sensor_daily ───────────────────────────────────────────────────────────────
print('Building sensor_daily ...')
t1 = time.time()

con.execute("""
CREATE TABLE sensor_daily AS
SELECT
    pid,
    country,
    datetime::DATE                  AS exposure_date,
    season,

    -- PM2.5
    AVG(pm25)                       AS pm25_mean,
    MAX(pm25)                       AS pm25_max,
    MIN(pm25)                       AS pm25_min,
    STDDEV(pm25)                    AS pm25_sd,

    -- NO2
    AVG(no2)                        AS no2_mean,
    MAX(no2)                        AS no2_max,
    MIN(no2)                        AS no2_min,
    STDDEV(no2)                     AS no2_sd,

    -- Temperature
    AVG(temp)                       AS temp_mean,
    MAX(temp)                       AS temp_max,
    MIN(temp)                       AS temp_min,
    STDDEV(temp)                    AS temp_sd,

    -- Relative Humidity
    AVG(rh)                         AS rh_mean,
    MAX(rh)                         AS rh_max,
    MIN(rh)                         AS rh_min,
    STDDEV(rh)                      AS rh_sd,

    -- Location (median lat/lon for the day)
    AVG(lat)                        AS lat,
    AVG(lon)                        AS lon,

    -- Reading count (data quality indicator)
    COUNT(*)                        AS n_readings,

    -- Monitoring window
    MIN(startdate)::DATE            AS monitoring_start,
    MAX(enddate)::DATE              AS monitoring_end

FROM sensor_raw
WHERE pm25 IS NOT NULL
  AND datetime IS NOT NULL
GROUP BY pid, country, datetime::DATE, season
ORDER BY pid, exposure_date
""")

daily_count = con.execute("SELECT COUNT(*) FROM sensor_daily").fetchone()[0]
print(f'sensor_daily complete: {daily_count:,} rows  ({time.time()-t1:.1f}s)\n')

# ── Indexes ────────────────────────────────────────────────────────────────────
print('Creating indexes ...')
con.execute("CREATE INDEX idx_raw_pid_dt    ON sensor_raw(pid, datetime)")
con.execute("CREATE INDEX idx_raw_country   ON sensor_raw(country)")
con.execute("CREATE INDEX idx_daily_pid_dt  ON sensor_daily(pid, exposure_date)")
con.execute("CREATE INDEX idx_daily_country ON sensor_daily(country)")
print('Indexes done.\n')

# ── Summary ────────────────────────────────────────────────────────────────────
print('=== Summary ===')
print(con.execute("SELECT country, COUNT(*) AS raw_rows FROM sensor_raw GROUP BY country ORDER BY country").fetchdf().to_string(index=False))
print()
print(con.execute("SELECT country, COUNT(*) AS daily_rows, COUNT(DISTINCT pid) AS participants FROM sensor_daily GROUP BY country ORDER BY country").fetchdf().to_string(index=False))
print()
print('sensor_daily sample:')
print(con.execute("SELECT * FROM sensor_daily LIMIT 3").fetchdf().to_string())

con.close()
print(f'\nDone. Database saved to {DB_PATH}')
print(f'File size: {os.path.getsize(DB_PATH)/1e6:.1f} MB')
