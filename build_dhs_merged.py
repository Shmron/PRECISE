#!/usr/bin/env python3
"""
Merge DHS recode databases into one unified DHS database.

Run AFTER all individual recode databases are built:
    python3 build_dhs_recode.py BR
    python3 build_dhs_recode.py IR
    python3 build_dhs_recode.py HR
    python3 build_dhs_recode.py KR
    python3 build_dhs_recode.py MR

Then run this script:
    python3 build_dhs_merged.py

Join keys (DHS standard):
    BR ↔ IR  :  survey_code + caseid          (same woman/mother)
    BR ↔ KR  :  survey_code + caseid + bidx   (same child under 5)
    BR ↔ HR  :  survey_code + v001 + v002     (same household)

Output: dhs_merged.duckdb
  Table: dhs_merged  — birth-level rows with mother, household, and child columns merged in
"""

import os
import duckdb
import pandas as pd

BASE_DIR = "/home/rutendo/PRECISE"

RECODES = {
    "BR": ("births",             os.path.join(BASE_DIR, "dhs_br.duckdb")),
    "IR": ("women",              os.path.join(BASE_DIR, "dhs_ir.duckdb")),
    "HR": ("households",         os.path.join(BASE_DIR, "dhs_hr.duckdb")),
    "KR": ("children",           os.path.join(BASE_DIR, "dhs_kr.duckdb")),
    # WI excluded: wealth quintile/score already in HR (hv270/hv271); whhid key not directly joinable to BR
    "AR": ("hiv_results",        os.path.join(BASE_DIR, "dhs_ar.duckdb")),
    "GR": ("antenatal_postnatal",os.path.join(BASE_DIR, "dhs_gr.duckdb")),
    "NR": ("pregnancies",        os.path.join(BASE_DIR, "dhs_nr.duckdb")),
    "GE": ("clusters",           os.path.join(BASE_DIR, "dhs_ge.duckdb")),
}

OUTPUT_DB = os.path.join(BASE_DIR, "dhs_merged.duckdb")


def prefix_columns(con, db_path, table, prefix, skip_cols):
    """Return SQL SELECT list that prefixes all columns except skip_cols."""
    cols = con.execute(
        f"SELECT column_name FROM information_schema.columns "
        f"WHERE table_name='{table}' ORDER BY ordinal_position",
        connection=None
    )
    # Use ATTACH approach instead
    return None  # handled inline below


def get_columns(con, qualified_table):
    return [r[0] for r in con.execute(f"DESCRIBE {qualified_table}").fetchall()]


def build_prefixed_select(cols, prefix, skip):
    parts = []
    for c in cols:
        if c in skip:
            continue
        parts.append(f'    t."{c}" AS "{prefix}_{c}"')
    return ",\n".join(parts)


def main():
    available = {k: v for k, v in RECODES.items() if os.path.exists(v[1])}
    missing = [k for k in RECODES if k not in available]

    if "BR" not in available:
        print("ERROR: dhs_br.duckdb not found. Run build_dhs_recode.py BR first.")
        return

    if missing:
        print(f"Note: {missing} databases not found — will skip those joins")

    print(f"Available: {list(available.keys())}")
    print(f"Output: {OUTPUT_DB}\n")

    if os.path.exists(OUTPUT_DB):
        os.remove(OUTPUT_DB)

    import os as _os
    _os.makedirs('/home/rutendo/PRECISE/duckdb_tmp', exist_ok=True)

    con = duckdb.connect(OUTPUT_DB)
    con.execute("SET temp_directory='/home/rutendo/PRECISE/duckdb_tmp'")
    con.execute("SET memory_limit='100GB'")
    con.execute("SET threads=4")
    con.execute("SET preserve_insertion_order=false")

    # Attach source databases read-only
    for recode, (table, db_path) in available.items():
        alias = recode.lower()
        con.execute(f"ATTACH '{db_path}' AS {alias} (READ_ONLY)")
        print(f"Attached: {alias} ({table})")

    # Get column lists
    br_cols = get_columns(con, "br.births")

    # Shared metadata cols (already in BR, skip from other recodes to avoid duplication)
    meta_skip = {"country_code", "country_name", "survey_code", "dhs_phase", "source_file"}

    print("\nBuilding merged table...", flush=True)

    # Start with BR as base, LEFT JOIN IR, HR, KR
    join_clauses = []
    # Use explicit column list for BR base (br.births.* is invalid with ATTACH syntax)
    br_select = ",\n".join(f'    b."{c}"' for c in br_cols)
    select_parts = [br_select]

    if "IR" in available:
        ir_cols = get_columns(con, "ir.women")
        ir_skip = meta_skip | {"caseid", "bidx", "v001", "v002", "v003"}
        br_col_set = set(br_cols)
        ir_add = [c for c in ir_cols if c not in ir_skip and c not in br_col_set]
        if ir_add:
            ir_select = ",\n".join(f'    ir_t."{c}" AS "ir_{c}"' for c in ir_add[:500])
            select_parts.append(ir_select)
        join_clauses.append("""
    LEFT JOIN ir.women AS ir_t
           ON b.survey_code = ir_t.survey_code
          AND b.caseid      = ir_t.caseid""")

    if "HR" in available:
        hr_cols = get_columns(con, "hr.households")
        hr_skip = meta_skip | {"hhid", "v001", "v002", "hv001", "hv002"}
        br_col_set = set(br_cols)
        hr_add = [c for c in hr_cols if c not in hr_skip and c not in br_col_set]
        if hr_add:
            hr_select = ",\n".join(f'    hr_t."{c}" AS "hr_{c}"' for c in hr_add[:300])
            select_parts.append(hr_select)
        join_clauses.append("""
    LEFT JOIN hr.households AS hr_t
           ON b.survey_code = hr_t.survey_code
          AND b.v001        = hr_t.hv001
          AND b.v002        = hr_t.hv002""")

    if "KR" in available:
        kr_cols = get_columns(con, "kr.children")
        kr_skip = meta_skip | {"caseid", "bidx", "v001", "v002", "v003"}
        br_col_set = set(br_cols)
        kr_add = [c for c in kr_cols if c not in kr_skip and c not in br_col_set]
        if kr_add:
            kr_select = ",\n".join(f'    kr_t."{c}" AS "kr_{c}"' for c in kr_add[:300])
            select_parts.append(kr_select)
        join_clauses.append("""
    LEFT JOIN kr.children AS kr_t
           ON b.survey_code = kr_t.survey_code
          AND b.caseid      = kr_t.caseid
          AND b.bidx        = kr_t.bidx""")

    # Wealth index — joins on household (v001+v002)
    if "WI" in available:
        wi_cols = get_columns(con, "wi.wealth")
        wi_skip = meta_skip | {"hhid", "whhid", "v001", "v002", "hv001", "hv002"}
        br_col_set = set(br_cols)
        wi_add = [c for c in wi_cols if c not in wi_skip and c not in br_col_set]
        if wi_add:
            wi_select = ",\n".join(f'    wi_t."{c}" AS "wi_{c}"' for c in wi_add[:100])
            select_parts.append(wi_select)
        join_clauses.append("""
    LEFT JOIN wi.wealth AS wi_t
           ON b.survey_code = wi_t.survey_code
          AND b.v001        = wi_t.v001
          AND b.v002        = wi_t.v002""")

    # HIV test results — joins on caseid (same woman)
    if "AR" in available:
        ar_cols = get_columns(con, "ar.hiv_results")
        ar_skip = meta_skip | {"hivclust", "hivnumb", "hivline"}
        br_col_set = set(br_cols)
        ar_add = [c for c in ar_cols if c not in ar_skip and c not in br_col_set]
        if ar_add:
            ar_select = ",\n".join(f'    ar_t."{c}" AS "ar_{c}"' for c in ar_add[:100])
            select_parts.append(ar_select)
        join_clauses.append("""
    LEFT JOIN ar.hiv_results AS ar_t
           ON b.survey_code = ar_t.survey_code
          AND b.v001        = ar_t.hivclust
          AND b.v002        = ar_t.hivnumb
          AND b.v003        = ar_t.hivline""")

    # Pregnancy/postnatal care — joins on caseid
    if "GR" in available:
        gr_cols = get_columns(con, "gr.antenatal_postnatal")
        gr_skip = meta_skip | {"caseid", "pidx", "v001", "v002", "v003"}
        br_col_set = set(br_cols)
        gr_add = [c for c in gr_cols if c not in gr_skip and c not in br_col_set]
        if gr_add:
            gr_select = ",\n".join(f'    gr_t."{c}" AS "gr_{c}"' for c in gr_add[:200])
            select_parts.append(gr_select)
        join_clauses.append("""
    LEFT JOIN gr.antenatal_postnatal AS gr_t
           ON b.survey_code = gr_t.survey_code
          AND b.caseid      = gr_t.caseid
          AND b.bidx        = gr_t.pidx""")

    # Pregnancies recode (NR) — joins on caseid + pregnancy index
    if "NR" in available:
        nr_cols = get_columns(con, "nr.pregnancies")
        nr_skip = meta_skip | {"caseid", "pidx", "v001", "v002", "v003"}
        br_col_set = set(br_cols)
        nr_add = [c for c in nr_cols if c not in nr_skip and c not in br_col_set]
        if nr_add:
            nr_select = ",\n".join(f'    nr_t."{c}" AS "nr_{c}"' for c in nr_add[:200])
            select_parts.append(nr_select)
        join_clauses.append("""
    LEFT JOIN nr.pregnancies AS nr_t
           ON b.survey_code = nr_t.survey_code
          AND b.caseid      = nr_t.caseid
          AND b.bidx        = nr_t.pidx""")

    # Cluster coordinates (GE) — joins on cluster number (v001 = dhsclust)
    if "GE" in available:
        ge_cols = get_columns(con, "ge.clusters")
        ge_skip = meta_skip | {"dhsclust"}
        ge_add = [c for c in ge_cols if c not in ge_skip]
        if ge_add:
            ge_select = ",\n".join(f'    ge_t."{c}" AS "ge_{c}"' for c in ge_add)
            select_parts.append(ge_select)
        join_clauses.append("""
    LEFT JOIN ge.clusters AS ge_t
           ON b.survey_code = ge_t.survey_code
          AND b.v001        = ge_t.dhsclust""")

    sql = f"""
CREATE TABLE dhs_merged AS
SELECT
{chr(10).join(',' + p if i > 0 else p for i, p in enumerate(select_parts))}
FROM br.births AS b
{''.join(join_clauses)}
"""

    print("Running join (this may take several minutes)...", flush=True)
    con.execute(sql)

    # Indexes
    print("Creating indexes...", flush=True)
    con.execute("CREATE INDEX idx_country ON dhs_merged(country_code)")
    con.execute("CREATE INDEX idx_survey  ON dhs_merged(survey_code)")
    con.execute("CREATE INDEX idx_phase   ON dhs_merged(dhs_phase)")

    # Summary
    totals = con.execute("""
        SELECT COUNT(*) AS rows,
               COUNT(DISTINCT country_code) AS countries,
               COUNT(DISTINCT survey_code) AS surveys
        FROM dhs_merged
    """).fetchone()

    col_count = len(get_columns(con, "dhs_merged"))

    print("\n=== MERGED DATABASE ===")
    print(f"Total rows   : {totals[0]:,}")
    print(f"Countries    : {totals[1]}")
    print(f"Surveys      : {totals[2]}")
    print(f"Columns      : {col_count}")
    print(f"Database     : {OUTPUT_DB}")
    con.close()


if __name__ == "__main__":
    main()
