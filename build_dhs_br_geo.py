#!/usr/bin/env python3
"""
Build dhs_br_geo.duckdb — births enriched with:
  - GPS cluster coordinates (GE)
  - Per-birth care outcomes from IR (birth weight, delivery, ANC, C-section)
  - Pregnancy complications from GR (hemorrhage, eclampsia, hypertension, etc.)
  - Mother-level reproductive health flags from IR (stillbirth history, fistula)
  - Pregnancy outcomes from NR (outcome type, gestational age)

Output: /home/rutendo/PRECISE/dhs_br_geo.duckdb  (table: br_geo)

Join keys:
  BR ↔ GE  : survey_code (mapped) + v001 = dhsclust
  BR ↔ IR  : survey_code (mapped) + caseid           (mother-level)
  BR ↔ GR  : survey_code (mapped) + caseid + bidx = pidx
  BR ↔ NR  : survey_code (mapped) + caseid + bidx = pidxb

IR birth variables are indexed by birth order (_1 = most recent birth,
matching BR bidx). Only births 1-6 carry indexed IR data; older births
(bidx > 6) get NULL for those columns.
"""

import duckdb
import os
import pandas as pd

BR_DB  = "/home/rutendo/PRECISE/dhs_births.duckdb"
GE_DB  = "/home/rutendo/PRECISE/dhs_ge.duckdb"
IR_DB  = "/home/rutendo/PRECISE/dhs_ir.duckdb"
GR_DB  = "/home/rutendo/PRECISE/dhs_gr.duckdb"
NR_DB  = "/home/rutendo/PRECISE/dhs_nr.duckdb"
OUT_DB = "/home/rutendo/PRECISE/dhs_br_geo.duckdb"

MAX_IR_IDX = 6


def map_survey_codes(br_db, target_db, target_table, target_recode):
    """Map each BR survey code to the best matching survey in target_db."""
    br = duckdb.connect(br_db, read_only=True)
    tgt = duckdb.connect(target_db, read_only=True)

    br_surveys = [r[0] for r in br.execute(
        "SELECT DISTINCT survey_code FROM births ORDER BY 1").fetchall()]
    tgt_surveys = set(r[0] for r in tgt.execute(
        f"SELECT DISTINCT survey_code FROM {target_table}").fetchall())

    mapping = {}
    for s in br_surveys:
        country, version = s[:2], s[4:]
        phase = version[0]

        exact = country + target_recode + version
        if exact in tgt_surveys:
            mapping[s] = exact
            continue

        candidates = sorted(
            [g for g in tgt_surveys if g[:2] == country and g[4] == phase],
            reverse=True
        )
        if candidates:
            mapping[s] = candidates[0]

    br.close(); tgt.close()
    return mapping


def bidx_case(alias, var, max_idx=MAX_IR_IDX):
    """Generate: CASE b.bidx WHEN 1 THEN alias.var_1 ... END AS var"""
    whens = " ".join(f"WHEN {i} THEN {alias}.{var}_{i}" for i in range(1, max_idx + 1))
    return f"CASE b.bidx {whens} END AS {var}"


def main():
    print("Building dhs_br_geo.duckdb ...\n")

    ge_map = map_survey_codes(BR_DB, GE_DB, "clusters", "GE")
    print(f"GE: {len(ge_map)} surveys mapped")

    ir_available = os.path.exists(IR_DB)
    gr_available = os.path.exists(GR_DB)
    nr_available = os.path.exists(NR_DB)

    ir_map = map_survey_codes(BR_DB, IR_DB, "women",              "IR") if ir_available else {}
    gr_map = map_survey_codes(BR_DB, GR_DB, "antenatal_postnatal","GR") if gr_available else {}
    nr_map = map_survey_codes(BR_DB, NR_DB, "pregnancies",        "NR") if nr_available else {}

    print(f"IR: {len(ir_map)} surveys  GR: {len(gr_map)} surveys  NR: {len(nr_map)} surveys")

    if os.path.exists(OUT_DB):
        os.remove(OUT_DB)

    con = duckdb.connect(OUT_DB)
    con.execute("SET memory_limit='60GB'")
    con.execute("SET threads=4")
    con.execute("SET preserve_insertion_order=false")
    os.makedirs("/home/rutendo/PRECISE/duckdb_tmp", exist_ok=True)
    con.execute("SET temp_directory='/home/rutendo/PRECISE/duckdb_tmp'")

    con.execute(f"ATTACH '{BR_DB}' AS br (READ_ONLY)")
    con.execute(f"ATTACH '{GE_DB}' AS ge (READ_ONLY)")
    if ir_available: con.execute(f"ATTACH '{IR_DB}' AS ir (READ_ONLY)")
    if gr_available: con.execute(f"ATTACH '{GR_DB}' AS gr (READ_ONLY)")
    if nr_available: con.execute(f"ATTACH '{NR_DB}' AS nr (READ_ONLY)")

    # Load survey mappings
    def load_map(m, name):
        df = pd.DataFrame(list(m.items()), columns=["br_survey", "tgt_survey"])
        con.execute(f"CREATE TEMP TABLE {name} AS SELECT * FROM df")

    load_map(ge_map, "ge_map")
    if ir_available and ir_map: load_map(ir_map, "ir_map")
    if gr_available and gr_map: load_map(gr_map, "gr_map")
    if nr_available and nr_map: load_map(nr_map, "nr_map")

    # ── IR: birth-indexed variables (CASE bidx WHEN 1..6) ──────────────────
    ir_select = ""
    if ir_available and ir_map:
        ir_indexed = [
            "m18",   # birth weight card source (1=card, 2=maternal recall)
            "m19",   # birth weight in grams (>=9990 = missing/DK)
            "m19a",  # birth weight in kg (alternate surveys)
            "m45",   # perceived birth size (1=very large..5=very small)
            "m15",   # place of delivery (coded: 11=home, 21=gov hospital, etc.)
            "m17",   # C-section (0=no, 1=yes)
            "m17a",  # C-section scar seen
            "m14",   # months pregnant at 1st ANC visit (0=not 1st trim, 98=DK)
            "m13",   # ANC provider type (0=none, 1=doctor, 2=nurse/midwife, etc.)
            "m3a",   # doctor present at delivery (0/1)
            "m3b",   # nurse/midwife present at delivery (0/1)
            "m4",    # postnatal check for mother (0=no, 1=yes)
        ]
        ir_select = ",\n            " + ",\n            ".join(
            bidx_case("ir_t", v) for v in ir_indexed
        )

    # ── IR: mother-level (not birth-indexed) ───────────────────────────────
    ir_mother_select = ""
    if ir_available and ir_map:
        ir_mother_select = """,
            ir_t.v228  AS ir_had_terminated_pregnancy,
            ir_t.v234  AS ir_obstetric_fistula,
            ir_t.v248  AS ir_bp_taken_anc"""

    # ── GR: pregnancy complication flags ──────────────────────────────────
    gr_select = ""
    gr_join_clause = ""
    if gr_available and gr_map:
        gr_join_clause = """
        LEFT JOIN gr_map AS grm ON b.survey_code = grm.br_survey
        LEFT JOIN gr.antenatal_postnatal AS gr_t
               ON grm.tgt_survey = gr_t.survey_code
              AND b.caseid       = gr_t.caseid
              AND b.bidx         = gr_t.pidx"""
        gr_select = """,
            gr_t.m77   AS comp_any,
            gr_t.m78a  AS comp_hemorrhage,
            gr_t.m78b  AS comp_eclampsia_convulsions,
            gr_t.m78c  AS comp_prolonged_labor,
            gr_t.m78d  AS comp_fever,
            gr_t.m78e  AS comp_fistula_symptoms,
            gr_t.m78f  AS comp_prom,
            gr_t.m78g  AS comp_malaria,
            gr_t.m78h  AS comp_anemia,
            gr_t.m78j  AS comp_hypertension,
            gr_t.m78m  AS comp_other_a,
            gr_t.m78n  AS comp_other_b,
            gr_t.m78o  AS comp_other_c,
            gr_t.m55   AS comp_postpartum,
            gr_t.m60   AS comp_blood_transfusion,
            gr_t.m66   AS comp_pph,
            gr_t.m80   AS postnatal_care_timing,
            gr_t.m82   AS fistula_reported"""

    # ── NR: pregnancy outcome record ───────────────────────────────────────
    nr_select = ""
    nr_join_clause = ""
    if nr_available and nr_map:
        nr_join_clause = """
        LEFT JOIN nr_map AS nrm ON b.survey_code = nrm.br_survey
        LEFT JOIN nr.pregnancies AS nr_t
               ON nrm.tgt_survey = nr_t.survey_code
              AND b.caseid       = nr_t.caseid
              AND b.bidx         = nr_t.pidxb"""
        nr_select = """,
            nr_t.p0   AS nr_outcome_code,
            nr_t.p5   AS nr_child_alive_at_survey,
            nr_t.p8   AS nr_birth_size,
            nr_t.p9   AS nr_gestational_age,
            nr_t.p10  AS nr_place_of_delivery,
            nr_t.p11  AS nr_anc_visits,
            nr_t.p12  AS nr_anc_months_pregnant,
            nr_t.p30  AS nr_anc_provider,
            nr_t.p31  AS nr_complications,
            nr_t.p32  AS nr_delivery_assistance"""

    ir_join_clause = ""
    if ir_available and ir_map:
        ir_join_clause = """
        LEFT JOIN ir_map AS irm ON b.survey_code = irm.br_survey
        LEFT JOIN ir.women AS ir_t
               ON irm.tgt_survey = ir_t.survey_code
              AND b.caseid       = ir_t.caseid"""

    sql = f"""
        CREATE TABLE br_geo AS
        SELECT
            b.country_code,
            b.country_name,
            b.survey_code,
            b.dhs_phase,

            b.caseid,
            b.v001,
            b.v002,
            b.v003,
            b.bidx,

            b.b3,    -- date of birth (CMC)
            b.b4,    -- birth order
            b.b0,    -- twin indicator (0=singleton)
            b.b5,    -- child alive at survey (1=yes, 0=no)
            b.b7,    -- age at death in months
            b.b8,    -- current age in years (if alive)
            b.b11,   -- preceding birth interval (months)
            b.b12,   -- succeeding birth interval (months)
            b.b20,   -- months of gestation (phase 7+; 9=DK)

            b.v005,  -- sample weight (divide by 1e6 for probability)
            b.v006,  -- month of interview
            b.v007,  -- year of interview
            b.v008,  -- date of interview (CMC)
            b.v021,  -- primary sampling unit
            b.v023,  -- stratification variable
            b.v025,  -- urban/rural

            g.latnum,
            g.longnum,
            g.urban_rura,
            g.alt_dem,
            g.dhsregna,
            g.dhsregco,
            g.dhscc,
            g.dhsyear{ir_select}{ir_mother_select}{gr_select}{nr_select}

        FROM br.births AS b
        LEFT JOIN ge_map AS gm ON b.survey_code = gm.br_survey
        LEFT JOIN ge.clusters AS g
               ON gm.tgt_survey = g.survey_code
              AND b.v001        = g.dhsclust{ir_join_clause}{gr_join_clause}{nr_join_clause}
    """

    print("Running join...", flush=True)
    con.execute(sql)

    print("Creating indexes...", flush=True)
    con.execute("CREATE INDEX idx_country ON br_geo(country_code)")
    con.execute("CREATE INDEX idx_survey  ON br_geo(survey_code)")
    con.execute("CREATE INDEX idx_caseid  ON br_geo(caseid)")
    con.execute("CREATE INDEX idx_cluster ON br_geo(v001)")

    cols = [r[0] for r in con.execute("DESCRIBE br_geo").fetchall()]
    totals = con.execute("""
        SELECT
            COUNT(*)                                                               AS n,
            COUNT(DISTINCT country_code)                                           AS countries,
            COUNT(DISTINCT survey_code)                                            AS surveys,
            SUM(CASE WHEN latnum IS NOT NULL AND latnum != 0 THEN 1 ELSE 0 END)   AS with_gps,
            SUM(CASE WHEN m19 IS NOT NULL AND m19 < 9990 THEN 1 ELSE 0 END)       AS with_weight,
            SUM(CASE WHEN m17 = 1 THEN 1 ELSE 0 END)                              AS csections,
            SUM(CASE WHEN comp_any = 1 THEN 1 ELSE 0 END)                         AS with_complication,
            SUM(CASE WHEN comp_eclampsia_convulsions = 1 THEN 1 ELSE 0 END)       AS eclampsia,
            SUM(CASE WHEN comp_hemorrhage = 1 THEN 1 ELSE 0 END)                  AS hemorrhage,
            SUM(CASE WHEN comp_hypertension = 1 THEN 1 ELSE 0 END)                AS hypertension
        FROM br_geo
    """).fetchone()

    print("\n=== BR_GEO DATABASE ===")
    print(f"Total births             : {totals[0]:,}")
    print(f"Countries                : {totals[1]}")
    print(f"Surveys                  : {totals[2]}")
    print(f"Columns                  : {len(cols)}")
    print(f"With GPS coordinates     : {totals[3]:,}  ({100*totals[3]/totals[0]:.1f}%)")
    print(f"With birth weight (m19)  : {totals[4]:,}  ({100*(totals[4] or 0)/totals[0]:.1f}%)")
    print(f"C-section births         : {totals[5]:,}  ({100*(totals[5] or 0)/totals[0]:.1f}%)")
    print(f"With any complication    : {totals[6]:,}  ({100*(totals[6] or 0)/totals[0]:.1f}%)")
    print(f"  Eclampsia/convulsions  : {totals[7]:,}")
    print(f"  Hemorrhage             : {totals[8]:,}")
    print(f"  Hypertension           : {totals[9]:,}")
    print(f"Database                 : {OUT_DB}")
    con.close()


if __name__ == "__main__":
    main()
