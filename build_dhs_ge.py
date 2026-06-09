#!/usr/bin/env python3
"""
Build DHS cluster coordinates database from GE shapefiles in DHS_downloads.zip.

Output: /home/rutendo/PRECISE/dhs_ge.duckdb  (table: clusters)

Key columns: country_code, survey_code, dhsclust, latnum, longnum,
             urban_rura, alt_dem, dhsregna, dhsregco
Join to other recodes on: survey_code + dhsclust = v001 (= hv001)
"""

import os
import re
import shutil
import tempfile
import traceback
import zipfile
from pathlib import Path

import duckdb
import geopandas as gpd
import pandas as pd

ZIP_PATH = "/home/rutendo/PRECISE/DHS_downloads.zip"
OUTPUT_DB = "/home/rutendo/PRECISE/dhs_ge.duckdb"
PARQUET_DIR = "/home/rutendo/PRECISE/dhs_ge_parquet"

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

# Shapefile component extensions needed
SHP_EXTS = {".shp", ".dbf", ".prj", ".shx"}


def get_ge_survey_groups(zip_path):
    """Group shapefile components by survey code."""
    groups = {}
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if "/GE/" not in name:
                continue
            p = Path(name)
            if p.suffix.lower() not in SHP_EXTS:
                continue
            stem = p.stem.upper()
            m = re.match(r"([A-Z]{2})GE([0-9][0-9A-Z])", stem)
            if not m:
                continue
            country = m.group(1)
            version = m.group(2)
            survey_code = f"{country}GE{version}"
            if survey_code not in groups:
                groups[survey_code] = {"country": country, "version": version, "files": []}
            groups[survey_code]["files"].append(name)
    return groups


def step1_extract_to_parquet(zip_path, groups, parquet_dir):
    os.makedirs(parquet_dir, exist_ok=True)

    with zipfile.ZipFile(zip_path) as zf:
        for i, (survey_code, info) in enumerate(sorted(groups.items())):
            country = info["country"]
            version = info["version"]
            phase = int(version[0]) if version[0].isdigit() else 0

            parquet_path = os.path.join(parquet_dir, f"{survey_code}.parquet")
            if os.path.exists(parquet_path):
                print(f"[{i+1}/{len(groups)}] {survey_code} — already done, skipping")
                continue

            print(f"[{i+1}/{len(groups)}] {survey_code}  ({COUNTRY_NAMES.get(country, country)})", flush=True)

            try:
                with tempfile.TemporaryDirectory() as tmpdir:
                    for zip_entry in info["files"]:
                        fname = Path(zip_entry).name
                        dest = os.path.join(tmpdir, fname)
                        with zf.open(zip_entry) as src, open(dest, "wb") as dst:
                            shutil.copyfileobj(src, dst)

                    shp_files = list(Path(tmpdir).glob("*.shp"))
                    if not shp_files:
                        print(f"  [SKIP] No .shp found")
                        continue

                    gdf = gpd.read_file(str(shp_files[0]))
                    gdf.columns = [c.lower() for c in gdf.columns]

                    # Drop geometry — we only want attribute table
                    df = pd.DataFrame(gdf.drop(columns="geometry", errors="ignore"))

                    df.insert(0, "country_code", country)
                    df.insert(1, "country_name", COUNTRY_NAMES.get(country, country))
                    df.insert(2, "survey_code", survey_code)
                    df.insert(3, "dhs_phase", phase)

                    df.to_parquet(parquet_path, index=False, engine="pyarrow")
                    print(f"  -> {len(df):,} clusters x {len(df.columns)} cols", flush=True)

            except Exception as e:
                print(f"  [ERROR] {survey_code}: {e}")
                traceback.print_exc()


def step2_to_duckdb(parquet_dir, output_db):
    parquet_files = sorted(Path(parquet_dir).glob("*.parquet"))
    print(f"\nMerging {len(parquet_files)} parquet files → {output_db} (table: clusters)", flush=True)

    if os.path.exists(output_db):
        os.remove(output_db)

    con = duckdb.connect(output_db)
    con.execute("SET memory_limit='20GB'")
    con.execute("SET threads=4")
    con.execute("SET preserve_insertion_order=false")

    glob_pattern = os.path.join(parquet_dir, "*.parquet")
    con.execute(f"""
        CREATE TABLE clusters AS
        SELECT * FROM read_parquet('{glob_pattern}', union_by_name=true)
    """)

    con.execute("CREATE INDEX idx_country  ON clusters(country_code)")
    con.execute("CREATE INDEX idx_survey   ON clusters(survey_code)")
    con.execute("CREATE INDEX idx_cluster  ON clusters(dhsclust)")

    totals = con.execute("""
        SELECT COUNT(*) AS total_clusters,
               COUNT(DISTINCT country_code) AS n_countries,
               COUNT(DISTINCT survey_code)  AS n_surveys
        FROM clusters
    """).fetchone()

    print(f"\n=== GE CLUSTERS DATABASE ===")
    print(f"Total clusters : {totals[0]:,}")
    print(f"Countries      : {totals[1]}")
    print(f"Surveys        : {totals[2]}")
    print(f"Database       : {output_db}")
    con.close()


def main():
    print("=== DHS Geographic Data (GE) Builder ===\n")
    groups = get_ge_survey_groups(ZIP_PATH)
    countries = len({v["country"] for v in groups.values()})
    print(f"Found {len(groups)} GE surveys across {countries} countries\n")

    print("Step 1: shapefiles → parquet\n")
    step1_extract_to_parquet(ZIP_PATH, groups, PARQUET_DIR)

    print("\nStep 2: parquet → DuckDB\n")
    step2_to_duckdb(PARQUET_DIR, OUTPUT_DB)


if __name__ == "__main__":
    main()
