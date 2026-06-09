"""
Build he2at.duckdb from the three HE2AT parquet files.

Tables:
  patient_exposures  — one row per patient (74K rows, 45 cols)
  exposure_days      — one row per patient-day (23M rows, 10 cols)
  climate_data       — one row per location-day (305K rows, 45 cols)

View:
  exposure_climate   — exposure_days JOIN climate_data (for temporal patient-level queries)
"""
import duckdb, os

BASE_DIR   = '/home/rutendo/PRECISE'
DB_PATH    = os.path.join(BASE_DIR, 'he2at.duckdb')
P_PATIENT  = os.path.join(BASE_DIR, 'per_patient_env_exposures (1).parquet')
P_DAYS     = os.path.join(BASE_DIR, 'patient_exposure_days (2).parquet')
P_CLIMATE  = os.path.join(BASE_DIR, 'climate_unified.parquet')

conn = duckdb.connect(DB_PATH)

for obj in ('exposure_climate', 'patient_exposures', 'exposure_days', 'climate_data'):
    conn.execute(f"DROP VIEW  IF EXISTS {obj}")
    conn.execute(f"DROP TABLE IF EXISTS {obj}")

print("Loading patient_exposures …")
conn.execute(f"CREATE TABLE patient_exposures AS SELECT * FROM read_parquet('{P_PATIENT}')")
n = conn.execute("SELECT COUNT(*) FROM patient_exposures").fetchone()[0]
print(f"  {n:,} rows")

print("Loading exposure_days …")
conn.execute(f"""
    CREATE TABLE exposure_days AS
    SELECT Study, Patient_Identifier, Country, Location,
           Latitude, Longitude,
           Birth_Date::DATE    AS Birth_Date,
           GA_Days,
           Exposure_Date::DATE AS Exposure_Date,
           Window_Type
    FROM read_parquet('{P_DAYS}')
""")
n = conn.execute("SELECT COUNT(*) FROM exposure_days").fetchone()[0]
print(f"  {n:,} rows")

print("Loading climate_data …")
conn.execute(f"""
    CREATE TABLE climate_data AS
    SELECT Country, Study, Location, Latitude, Longitude,
           Exposure_Date::DATE AS Exposure_Date,
           elevation, soil_nitrogen, soil_phosphorus, soil_organic_carbon,
           ipcc_climate_zone_code, ipcc_climate_zone_name,
           rwi, urbanization, urbanization_class,
           tas_mean, tas_min, tas_max,
           pm2p5_mean, no2as_mean, aod550_mean, od550bc_mean,
           WBGT_mean, humidex_mean, Wind_Chill_mean, HI_mean,
           tasapp_mean, tasdp_mean, WBGTsimple_mean, WBT_mean,
           NET_mean, ws_mean,
           UTCI_min, UTCI_mean, UTCI_max,
           MRT_min, MRT_mean, MRT_max,
           duaod550_nc_mean, RH_mean, ndvi, precipitation,
           duexttau_ee_mean, dusmass25_ee_mean, ducmass_ee_mean
    FROM read_parquet('{P_CLIMATE}')
""")
n = conn.execute("SELECT COUNT(*) FROM climate_data").fetchone()[0]
print(f"  {n:,} rows")

print("Creating exposure_climate view …")
conn.execute("""
    CREATE VIEW exposure_climate AS
    SELECT ed.Patient_Identifier, ed.Country, ed.Study, ed.Location,
           ed.Latitude, ed.Longitude,
           ed.Birth_Date, ed.GA_Days, ed.Exposure_Date, ed.Window_Type,
           cd.elevation, cd.soil_nitrogen, cd.soil_phosphorus, cd.soil_organic_carbon,
           cd.ipcc_climate_zone_code, cd.ipcc_climate_zone_name,
           cd.rwi, cd.urbanization, cd.urbanization_class,
           cd.tas_mean, cd.tas_min, cd.tas_max,
           cd.pm2p5_mean, cd.no2as_mean, cd.aod550_mean, cd.od550bc_mean,
           cd.WBGT_mean, cd.humidex_mean, cd.Wind_Chill_mean, cd.HI_mean,
           cd.tasapp_mean, cd.tasdp_mean, cd.WBGTsimple_mean, cd.WBT_mean,
           cd.NET_mean, cd.ws_mean,
           cd.UTCI_min, cd.UTCI_mean, cd.UTCI_max,
           cd.MRT_min, cd.MRT_mean, cd.MRT_max,
           cd.duaod550_nc_mean, cd.RH_mean, cd.ndvi, cd.precipitation,
           cd.duexttau_ee_mean, cd.dusmass25_ee_mean, cd.ducmass_ee_mean
    FROM exposure_days ed
    JOIN climate_data cd
      ON ed.Study = cd.Study
     AND ed.Location = cd.Location
     AND ed.Exposure_Date = cd.Exposure_Date
""")

print("Creating indexes …")
conn.execute("CREATE INDEX idx_pe_country  ON patient_exposures(Country)")
conn.execute("CREATE INDEX idx_pe_study    ON patient_exposures(Study)")
conn.execute("CREATE INDEX idx_cd_loc_date ON climate_data(Location, Exposure_Date)")
conn.execute("CREATE INDEX idx_ed_patient  ON exposure_days(Patient_Identifier)")
conn.execute("CREATE INDEX idx_ed_loc_date ON exposure_days(Location, Exposure_Date)")

print("\nCountry breakdown (patient_exposures):")
for row in conn.execute("""
    SELECT Country,
           COUNT(DISTINCT Patient_Identifier) AS n_patients,
           COUNT(DISTINCT Study)              AS n_studies,
           COUNT(DISTINCT Location)           AS n_locations
    FROM patient_exposures
    GROUP BY Country ORDER BY n_patients DESC
""").fetchall():
    print(f"  {row[0]:<20} {row[1]:>6,} patients  {row[2]:>2} studies  {row[3]:>3} locations")

conn.close()
print(f"\nDone → {DB_PATH}")
