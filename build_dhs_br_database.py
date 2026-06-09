#!/usr/bin/env python3
"""
Build a unified DHS Birth Records (BR) database from DHS_downloads.zip.

Strategy:
  1. Extract each BR .dta file from the zip
  2. Read with pyreadstat, add metadata columns, save as .parquet
  3. Use DuckDB read_parquet(union_by_name=true) to merge all into one table
  4. Create indexes and print a summary

Output: /home/rutendo/PRECISE/dhs_births.duckdb  (table: births)
"""

import os
import re
import shutil
import traceback
import zipfile
from pathlib import Path

import duckdb
import pyreadstat
import pandas as pd

ZIP_PATH = "/home/rutendo/PRECISE/DHS_downloads.zip"
OUTPUT_DB = "/home/rutendo/PRECISE/dhs_births.duckdb"
PARQUET_DIR = "/home/rutendo/PRECISE/dhs_br_parquet"

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


def parse_survey_code(filename):
    name = Path(filename).stem.upper()
    m = re.match(r"([A-Z]{2})BR([0-9][0-9A-Z])", name)
    if not m:
        return None, None, None
    country = m.group(1)
    version = m.group(2)
    phase = int(version[0]) if version[0].isdigit() else 0
    return country, f"{country}BR{version}", phase


def get_br_files(zip_path):
    files = []
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if "/BR/" in name and name.upper().endswith(".DTA"):
                files.append(name)
    return sorted(files)


def step1_extract_to_parquet(zip_path, br_files, parquet_dir):
    os.makedirs(parquet_dir, exist_ok=True)
    tmp_dta = "/tmp/dhs_br_tmp.dta"

    with zipfile.ZipFile(zip_path) as zf:
        for i, zip_entry in enumerate(br_files):
            filename = Path(zip_entry).name
            country, survey_code, phase = parse_survey_code(filename)
            if not country:
                print(f"  [SKIP] Cannot parse name: {filename}")
                continue

            parquet_path = os.path.join(parquet_dir, f"{survey_code}.parquet")
            if os.path.exists(parquet_path):
                print(f"[{i+1}/{len(br_files)}] {survey_code} — already exists, skipping")
                continue

            label = f"[{i+1}/{len(br_files)}] {survey_code}  ({COUNTRY_NAMES.get(country, country)})"
            print(label, flush=True)

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
                print(f"  -> {len(df):,} rows x {len(df.columns)} cols saved", flush=True)

            except Exception as e:
                print(f"  [ERROR] {filename}: {e}")
                traceback.print_exc()
            finally:
                if os.path.exists(tmp_dta):
                    os.remove(tmp_dta)


def step2_build_duckdb(parquet_dir, output_db):
    parquet_files = sorted(Path(parquet_dir).glob("*.parquet"))
    print(f"\nMerging {len(parquet_files)} parquet files into DuckDB...", flush=True)

    if os.path.exists(output_db):
        os.remove(output_db)

    con = duckdb.connect(output_db)
    con.execute("SET memory_limit='80GB'")
    con.execute("SET threads=4")
    con.execute("SET preserve_insertion_order=false")

    # One-shot merge using union_by_name — fills missing columns with NULL
    glob_pattern = os.path.join(parquet_dir, "*.parquet")
    con.execute(f"""
        CREATE TABLE births AS
        SELECT * FROM read_parquet('{glob_pattern}', union_by_name=true)
    """)

    print("Creating indexes...", flush=True)
    con.execute("CREATE INDEX idx_country  ON births(country_code)")
    con.execute("CREATE INDEX idx_survey   ON births(survey_code)")
    con.execute("CREATE INDEX idx_phase    ON births(dhs_phase)")

    # Summary
    print("\n=== DATABASE SUMMARY ===")
    summary = con.execute("""
        SELECT country_code, country_name, survey_code, dhs_phase,
               COUNT(*) AS n_births
        FROM births
        GROUP BY ALL
        ORDER BY country_code, dhs_phase
    """).fetchdf()
    pd.set_option("display.max_rows", 200)
    print(summary.to_string(index=False))

    totals = con.execute("""
        SELECT COUNT(*)                   AS total_births,
               COUNT(DISTINCT country_code) AS n_countries,
               COUNT(DISTINCT survey_code)  AS n_surveys
        FROM births
    """).fetchone()

    col_count = con.execute(
        "SELECT COUNT(*) FROM information_schema.columns WHERE table_name='births'"
    ).fetchone()[0]

    print(f"\nTotal births : {totals[0]:,}")
    print(f"Countries    : {totals[1]}")
    print(f"Surveys      : {totals[2]}")
    print(f"Columns      : {col_count}")
    print(f"\nDatabase     : {output_db}")
    con.close()


def main():
    br_files = get_br_files(ZIP_PATH)
    countries = len({Path(f).name[:2] for f in br_files})
    print(f"Found {len(br_files)} BR surveys across {countries} countries")
    print(f"Step 1: Convert .dta → .parquet ({PARQUET_DIR})\n")
    step1_extract_to_parquet(ZIP_PATH, br_files, PARQUET_DIR)

    print("\nStep 2: Merge parquet → DuckDB\n")
    step2_build_duckdb(PARQUET_DIR, OUTPUT_DB)


if __name__ == "__main__":
    main()
