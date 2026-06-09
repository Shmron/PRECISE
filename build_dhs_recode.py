#!/usr/bin/env python3
"""
Build a DHS single-recode database from DHS_downloads.zip.

Usage:
    python3 build_dhs_recode.py BR      # Birth Records
    python3 build_dhs_recode.py IR      # Individual (Women) Recode
    python3 build_dhs_recode.py HR      # Household Recode
    python3 build_dhs_recode.py KR      # Children Recode
    python3 build_dhs_recode.py MR      # Men Recode
    python3 build_dhs_recode.py PR      # Person Recode

Output files:
    dhs_{recode_lower}.duckdb   (table name = recode code, e.g. "births", "women", "households")
    dhs_{recode_lower}_parquet/ (intermediate parquet files, safe to delete after)
"""

import os
import re
import shutil
import sys
import traceback
import zipfile
from pathlib import Path

import duckdb
import pyreadstat
import pandas as pd

ZIP_PATH = "/home/rutendo/PRECISE/DHS_downloads.zip"
BASE_DIR = "/home/rutendo/PRECISE"

RECODE_TABLES = {
    # Core household survey recodes
    "BR": "births",
    "IR": "women",
    "HR": "households",
    "KR": "children",
    "MR": "men",
    "PR": "persons",
    "CR": "couples",
    # Outcomes / biomarkers
    "AR": "hiv_results",
    "BQ": "biomarkers",
    "GR": "antenatal_postnatal",
    "HW": "anthropometry",
    "NR": "pregnancies",
    "SR": "siblings",
    "WI": "wealth",
    # Mortality / community
    "CT": "community",
    "VA": "verbal_autopsy",
    # Raw files (pre-recode, lower priority)
    "HH": "household_raw",
    "IQ": "women_raw",
    "MS": "men_raw",
    # SPA — Service Provision Assessment (facility-level, separate analysis)
    "AI": "spa_accidents",
    "AN": "spa_antenatal",
    "AT": "spa_art",
    "CL": "spa_clients",
    "CN": "spa_consultations",
    "CO": "spa_country_specific",
    "CS": "spa_country_specific2",
    "FC": "spa_facility",
    "FP": "spa_family_planning",
    "HT": "spa_health_info",
    "IN": "spa_inpatient",
    "IP": "spa_inpatient_outpatient",
    "LB": "spa_labor_delivery",
    "LD": "spa_labor_delivery2",
    "ML": "spa_malaria",
    "OD": "spa_other",
    "OI": "spa_outpatient_inpatient",
    "OP": "spa_outpatient",
    "PH": "spa_pharmacy",
    "PM": "spa_pmtct",
    "PV": "spa_providers",
    "SC": "spa_sick_child",
    "SI": "spa_safe_injection",
    "SL": "spa_staff",
    "SQ": "spa_service_provision",
    "TB": "spa_tb",
}

COUNTRY_NAMES = {
    "AO": "Angola", "BF": "Burkina Faso", "BJ": "Benin", "BU": "Burundi",
    "CD": "DR Congo", "CF": "Central African Republic", "CI": "Cote d'Ivoire",
    "CM": "Cameroon", "ET": "Ethiopia", "GA": "Gabon", "GH": "Ghana",
    "GM": "Gambia", "GN": "Guinea", "KE": "Kenya", "KM": "Comoros",
    "LB": "Liberia", "LS": "Lesotho", "MD": "Madagascar", "ML": "Mali",
    "MR": "Mauritania", "MW": "Malawi", "MZ": "Mozambique", "NG": "Nigeria",
    "NI": "Niger", "NM": "Namibia", "RW": "Rwanda", "SL": "Sierra Leone",
    "SN": "Senegal", "SZ": "Eswatini", "TD": "Chad", "TG": "Togo",
    "TZ": "Tanzania", "UG": "Uganda", "ZA": "South Africa",
    "ZM": "Zambia", "ZW": "Zimbabwe",
}


def parse_survey(filename, recode):
    name = Path(filename).stem.upper()
    m = re.match(rf"([A-Z]{{2}}){recode}([0-9][0-9A-Z])", name)
    if not m:
        return None, None, None
    country = m.group(1)
    version = m.group(2)
    phase = int(version[0]) if version[0].isdigit() else 0
    return country, f"{country}{recode}{version}", phase


def get_recode_files(zip_path, recode):
    files = []
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if f"/{recode}/" in name and name.upper().endswith(".DTA"):
                files.append(name)
    return sorted(files)


def step1_to_parquet(zip_path, recode_files, parquet_dir, recode):
    os.makedirs(parquet_dir, exist_ok=True)
    tmp_dta = "/tmp/dhs_recode_tmp.dta"

    with zipfile.ZipFile(zip_path) as zf:
        for i, zip_entry in enumerate(recode_files):
            filename = Path(zip_entry).name
            country, survey_code, phase = parse_survey(filename, recode)
            if not country:
                print(f"  [SKIP] {filename}")
                continue

            parquet_path = os.path.join(parquet_dir, f"{survey_code}.parquet")
            if os.path.exists(parquet_path):
                print(f"[{i+1}/{len(recode_files)}] {survey_code} — already done, skipping")
                continue

            print(f"[{i+1}/{len(recode_files)}] {survey_code}  ({COUNTRY_NAMES.get(country, country)})", flush=True)

            try:
                with zf.open(zip_entry) as src, open(tmp_dta, "wb") as dst:
                    shutil.copyfileobj(src, dst)

                df, _ = pyreadstat.read_dta(tmp_dta, apply_value_formats=False)
                df.columns = [c.lower() for c in df.columns]

                df.insert(0, "country_code", country)
                df.insert(1, "country_name", COUNTRY_NAMES.get(country, country))
                df.insert(2, "survey_code", survey_code)
                df.insert(3, "dhs_phase", phase)
                df.insert(4, "source_file", filename)

                df.to_parquet(parquet_path, index=False, engine="pyarrow")
                print(f"  -> {len(df):,} rows x {len(df.columns)} cols", flush=True)

            except Exception as e:
                print(f"  [ERROR] {filename}: {e}")
                traceback.print_exc()
            finally:
                if os.path.exists(tmp_dta):
                    os.remove(tmp_dta)


def step2_to_duckdb(parquet_dir, output_db, table_name):
    parquet_files = sorted(Path(parquet_dir).glob("*.parquet"))
    print(f"\nMerging {len(parquet_files)} parquet files → {output_db} (table: {table_name})", flush=True)

    if os.path.exists(output_db):
        os.remove(output_db)

    con = duckdb.connect(output_db)
    con.execute("SET memory_limit='150GB'")
    con.execute("SET threads=8")
    con.execute("SET preserve_insertion_order=false")

    # Create empty table with the full union schema (schema scan only — low memory)
    glob_pattern = os.path.join(parquet_dir, "*.parquet")
    con.execute(f"""
        CREATE TABLE {table_name} AS
        SELECT * FROM read_parquet('{glob_pattern}', union_by_name=true)
        LIMIT 0
    """)

    # Insert one parquet at a time to avoid loading all files into memory at once
    for i, pf in enumerate(parquet_files):
        print(f"  inserting [{i+1}/{len(parquet_files)}] {pf.name}", flush=True)
        con.execute(f"""
            INSERT INTO {table_name} BY NAME
            SELECT * FROM read_parquet('{str(pf)}')
        """)

    print("Creating indexes...", flush=True)
    con.execute(f"CREATE INDEX idx_country ON {table_name}(country_code)")
    con.execute(f"CREATE INDEX idx_survey  ON {table_name}(survey_code)")
    con.execute(f"CREATE INDEX idx_phase   ON {table_name}(dhs_phase)")

    print(f"\n=== {table_name.upper()} DATABASE SUMMARY ===")
    summary = con.execute(f"""
        SELECT country_code, country_name, survey_code, dhs_phase,
               COUNT(*) AS n_rows
        FROM {table_name}
        GROUP BY ALL
        ORDER BY country_code, dhs_phase
    """).fetchdf()
    pd.set_option("display.max_rows", 300)
    print(summary.to_string(index=False))

    totals = con.execute(f"""
        SELECT COUNT(*) AS total,
               COUNT(DISTINCT country_code) AS n_countries,
               COUNT(DISTINCT survey_code)  AS n_surveys
        FROM {table_name}
    """).fetchone()

    col_count = con.execute(
        f"SELECT COUNT(*) FROM information_schema.columns WHERE table_name='{table_name}'"
    ).fetchone()[0]

    print(f"\nTotal rows   : {totals[0]:,}")
    print(f"Countries    : {totals[1]}")
    print(f"Surveys      : {totals[2]}")
    print(f"Columns      : {col_count}")
    print(f"Database     : {output_db}")
    con.close()


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 build_dhs_recode.py <RECODE>")
        print("       e.g.  BR  IR  HR  KR  MR  PR")
        sys.exit(1)

    recode = sys.argv[1].upper()
    table_name = RECODE_TABLES.get(recode, recode.lower() + "_recode")
    parquet_dir = os.path.join(BASE_DIR, f"dhs_{recode.lower()}_parquet")
    output_db = os.path.join(BASE_DIR, f"dhs_{recode.lower()}.duckdb")

    recode_files = get_recode_files(ZIP_PATH, recode)
    countries = len({Path(f).name[:2] for f in recode_files})
    print(f"Recode: {recode}  ({table_name})")
    print(f"Found {len(recode_files)} surveys across {countries} countries\n")
    print(f"Step 1: .dta → parquet  ({parquet_dir})\n")
    step1_to_parquet(ZIP_PATH, recode_files, parquet_dir, recode)

    print(f"\nStep 2: parquet → DuckDB\n")
    step2_to_duckdb(parquet_dir, output_db, table_name)


if __name__ == "__main__":
    main()
