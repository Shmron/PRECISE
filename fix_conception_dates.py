#!/usr/bin/env python3
"""
Two-step fix for the current precise.duckdb:

Step 1 — cast date columns from VARCHAR to DATE in-place
Step 2 — infer missing conception_date (edd - 280, then delivery_date - 280)

Run once. setup_db.py handles this automatically on future rebuilds.
"""
import duckdb

DB_PATH = '/home/rutendo/PRECISE/precise.duckdb'
conn = duckdb.connect(DB_PATH)

# ── Step 1: cast VARCHAR date columns to DATE ─────────────────────────────────
print("Casting date columns to DATE type...")
conn.execute("""
    ALTER TABLE daily_data
    ALTER COLUMN conception_date
    TYPE DATE USING TRY_STRPTIME(conception_date, '%Y-%m-%d')::DATE
""")
conn.execute("""
    ALTER TABLE daily_data
    ALTER COLUMN edd
    TYPE DATE USING TRY_STRPTIME(edd, '%d/%m/%Y')::DATE
""")
conn.execute("""
    ALTER TABLE daily_data
    ALTER COLUMN delivery_date
    TYPE DATE USING TRY_STRPTIME(delivery_date, '%d/%m/%Y')::DATE
""")
print("  Done — conception_date, edd, delivery_date are now DATE columns.")

# ── Step 2: infer missing conception_date ─────────────────────────────────────
before = conn.execute(
    "SELECT COUNT(*) FROM daily_data WHERE conception_date IS NULL"
).fetchone()[0]
print(f"\nMissing conception_date before: {before:,}")

conn.execute("""
    UPDATE daily_data
    SET conception_date = (edd - INTERVAL 280 DAYS)::DATE
    WHERE conception_date IS NULL AND edd IS NOT NULL
""")
mid = conn.execute(
    "SELECT COUNT(*) FROM daily_data WHERE conception_date IS NULL"
).fetchone()[0]
print(f"Recovered via edd - 280:           {before - mid:,}")

conn.execute("""
    UPDATE daily_data
    SET conception_date = (delivery_date - INTERVAL 280 DAYS)::DATE
    WHERE conception_date IS NULL AND delivery_date IS NOT NULL
""")
after = conn.execute(
    "SELECT COUNT(*) FROM daily_data WHERE conception_date IS NULL"
).fetchone()[0]
print(f"Recovered via delivery_date - 280: {mid - after:,}")
print(f"Still missing (no date at all):    {after:,}")

conn.close()
print("\nDone.")
