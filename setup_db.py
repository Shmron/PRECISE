import duckdb
import glob
import os

BASE_DIR = '/home/rutendo/PRECISE'
DB_PATH  = os.path.join(BASE_DIR, 'precise.duckdb')

# Pick the most recently modified Daily_Big_Table parquet (or CSV as fallback)
candidates = sorted(
    glob.glob(os.path.join(BASE_DIR, 'Daily_Big_Table*.parquet')) +
    glob.glob(os.path.join(BASE_DIR, 'Daily_Big_Table*.csv')),
    key=os.path.getmtime,
    reverse=True,
)
if not candidates:
    raise FileNotFoundError("No Daily_Big_Table parquet/csv found in " + BASE_DIR)

SOURCE_PATH = candidates[0]
IS_PARQUET  = SOURCE_PATH.endswith('.parquet')
print(f"Source file: {os.path.basename(SOURCE_PATH)}")

print("Connecting to DuckDB...")
conn = duckdb.connect(DB_PATH)

print(f"Loading {'parquet' if IS_PARQUET else 'CSV'} into DuckDB (this may take a moment)...")
conn.execute("DROP TABLE IF EXISTS daily_data")

if IS_PARQUET:
    conn.execute(f"""
        CREATE TABLE daily_data AS
        SELECT
            * EXCLUDE (conception_date, edd, delivery_date),
            conception_date::DATE AS conception_date,
            edd::DATE             AS edd,
            delivery_date::DATE   AS delivery_date
        FROM read_parquet('{SOURCE_PATH}')
    """)
else:
    conn.execute(f"""
        CREATE TABLE daily_data AS
        SELECT
            * EXCLUDE (conception_date, edd, delivery_date),
            TRY_STRPTIME(conception_date, '%Y-%m-%d')::DATE AS conception_date,
            TRY_STRPTIME(edd,             '%d/%m/%Y')::DATE  AS edd,
            TRY_STRPTIME(delivery_date,   '%d/%m/%Y')::DATE  AS delivery_date
        FROM read_csv_auto('{SOURCE_PATH}', header=true, sample_size=-1, all_varchar=true)
    """)

row_count = conn.execute("SELECT COUNT(*) FROM daily_data").fetchone()[0]
print(f"Loaded {row_count:,} rows")

print("\nColumn types:")
for row in conn.execute("DESCRIBE daily_data").fetchall():
    print(f"  {row[0]}: {row[1]}")

print("\nCountry breakdown:")
for row in conn.execute("SELECT Country, COUNT(*) as days, COUNT(DISTINCT f2a_participant_id) as participants FROM daily_data GROUP BY Country ORDER BY Country").fetchall():
    print(f"  {row[0]}: {row[1]:,} days, {row[2]:,} participants")

conn.close()
print(f"\nDone! Database saved to {DB_PATH}")
