#!/usr/bin/env python3
"""
Merge PRECISE visit-level outcomes into daily_data by nearest visit date.

Each exposure day is assigned the outcome values from whichever visit date
is closest (absolute distance). Uses pd.merge_asof direction='nearest' —
fully vectorised over 3.2M rows.
"""
import duckdb
import pandas as pd
import numpy as np

DB_PATH  = '/home/rutendo/PRECISE/precise.duckdb'
CSV_PATH = ('/home/rutendo/PRECISE/'
            'PRECISE_CoreVariables_data_2025_19_03_26'
            '(PRECISE_CoreVariables_data_2025).csv')

TIME_VARYING = [
    'bp_cat', 'average_dbp', 'average_sbp',
    'ht_overall', 'gh_overall', 'ch_overall', 'pe_overall',
    'gh_iso_overall', 'hdp_overall',
    'ht_flag', 'ch_flag', 'gh_flag',
]
STATIC_BIRTH = [
    'lowbirthweight', 'preterm', 'sga', 'svn',
    'Birthweight', 'bwt_kg', 'bwt_percentile', 'bwt_zscore',
    'delivery_mode', 'deliverylocation',
    'bornalive', 'livebirth', 'stillbirth', 'neonataldeath',
    'neonatal_nearmiss', 'nicu_admission', 'miscarriage',
    'apgarscore_1min', 'apgarscore_5min',
    'ga_PRECISE_days', 'GA_PRECISE', 'GA_PRECISE_code',
    'sex_of_baby', 'placenta_weight', 'placenta_weight_ratio',
    'maternal_death',
]
OUTCOME_COLS = TIME_VARYING + STATIC_BIRTH

# ── 1. Load and filter CSV ────────────────────────────────────────────────────
print("Loading core variables CSV (UNS cohort only)...")
cv = pd.read_csv(CSV_PATH, low_memory=False)
cv.columns = cv.columns.str.strip()
cv = cv[cv['cohort'] == 'UNS'].copy()
print(f"  {len(cv):,} rows, {cv['f2a_participant_id'].nunique():,} participants")

# ── 2. Parse dates; fill null visit_date from delivery_date ──────────────────
cv['visit_date']    = pd.to_datetime(cv['visit_date'],    dayfirst=True, errors='coerce', format='mixed').astype('datetime64[us]')
cv['delivery_date'] = pd.to_datetime(cv['delivery_date'], dayfirst=True, errors='coerce', format='mixed').astype('datetime64[us]')
cv.loc[cv['visit_date'].isna(), 'visit_date'] = cv.loc[cv['visit_date'].isna(), 'delivery_date']

# ── 3. Keep only needed columns, drop rows with no visit_date ────────────────
present = [c for c in OUTCOME_COLS if c in cv.columns]
missing_from_csv = set(OUTCOME_COLS) - set(present)
if missing_from_csv:
    print(f"  WARNING: columns not found in CSV (skipped): {missing_from_csv}")

keep = ['f2a_participant_id', 'visitevent', 'visit_date'] + present
visits = cv[keep].dropna(subset=['visit_date']).copy()
print(f"  {len(visits):,} visit rows with a valid visit_date")

# ── 4. Load exposure days from DuckDB ─────────────────────────────────────────
print("\nLoading exposure days from DuckDB...")
conn = duckdb.connect(DB_PATH)
exposures = conn.execute(
    "SELECT f2a_participant_id, exposure_day FROM daily_data"
).df()
exposures['exposure_day'] = pd.to_datetime(exposures['exposure_day']).astype('datetime64[us]')
exposures = exposures.dropna(subset=['exposure_day'])
print(f"  {len(exposures):,} exposure rows loaded")

# ── 5. Vectorised nearest-visit merge (per-participant merge_asof) ────────────
# merge_asof requires the `on` column to be globally monotone, which breaks when
# participants have overlapping date ranges. We group by participant and run a
# mini merge_asof on each — still vectorised within each group, no row loops.
print("\nRunning nearest-visit merge (grouped merge_asof)...")
visits_by_pid = {pid: grp.sort_values('visit_date').reset_index(drop=True)
                 for pid, grp in visits.groupby('f2a_participant_id')}

parts = []
for pid, exp_grp in exposures.groupby('f2a_participant_id'):
    exp_sorted = exp_grp.sort_values('exposure_day').reset_index(drop=True)
    vis_grp = visits_by_pid.get(pid)
    if vis_grp is None:
        parts.append(exp_sorted)   # no visits → outcome cols will be NaN
        continue
    # Drop f2a_participant_id from right to avoid column collision in merge output
    vis_right = vis_grp.drop(columns=['f2a_participant_id'])
    parts.append(pd.merge_asof(
        exp_sorted,
        vis_right,
        left_on='exposure_day',
        right_on='visit_date',
        direction='nearest',
    ))

merged = pd.concat(parts, ignore_index=True)
print(f"  Merged: {len(merged):,} rows")
print(f"  Visits assigned:\n{merged['visitevent'].value_counts().to_string()}")

# ── 6. Write outcome columns back into DuckDB ─────────────────────────────────
print("\nWriting outcome columns back to DuckDB...")

write_cols = ['visitevent'] + present  # include assigned visit name

# Drop existing outcome columns so we can recreate cleanly
existing_cols = {r[0] for r in conn.execute('DESCRIBE daily_data').fetchall()}
for col in write_cols:
    if col in existing_cols:
        conn.execute(f'ALTER TABLE daily_data DROP COLUMN "{col}"')

# Register merged as a DuckDB temp table (just the key + outcome cols)
write_df = merged[['f2a_participant_id', 'exposure_day'] + write_cols].copy()
conn.register('_outcomes_view', write_df)
conn.execute('CREATE TEMP TABLE _outcomes AS SELECT * FROM _outcomes_view')
conn.unregister('_outcomes_view')

# Add new columns — types inferred from the temp table
type_map = {r[0]: r[1] for r in conn.execute('DESCRIBE _outcomes').fetchall()}
for col in write_cols:
    dtype = type_map.get(col, 'VARCHAR')
    conn.execute(f'ALTER TABLE daily_data ADD COLUMN "{col}" {dtype}')

# Single UPDATE FROM — DuckDB executes this as a hash join over 3.2M rows
set_clause = ',\n    '.join([f'"{c}" = o."{c}"' for c in write_cols])
conn.execute(f"""
    UPDATE daily_data d
    SET {set_clause}
    FROM _outcomes o
    WHERE d.f2a_participant_id = o.f2a_participant_id
      AND d.exposure_day = o.exposure_day
""")
conn.execute('DROP TABLE _outcomes')
conn.close()

# ── 7. Summary ────────────────────────────────────────────────────────────────
print(f"\n{'─'*60}")
print(f"Total rows updated: {len(merged):,}")
print(f"\nFill rates per outcome column:")
for col in write_cols:
    n = merged[col].notna().sum()
    pct = 100 * n / len(merged)
    print(f"  {col:<30} {n:>10,}  ({pct:5.1f}%)")

print(f"\nSample (10 rows):")
sample_cols = ['f2a_participant_id', 'exposure_day', 'visitevent', 'bp_cat',
               'lowbirthweight', 'preterm']
print(merged[sample_cols].dropna(subset=['visitevent']).head(10).to_string(index=False))
print("\nDone.")
