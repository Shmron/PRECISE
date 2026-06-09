#!/usr/bin/env python3
"""
Generate Population-Weighted Euclidean Distance (PWED) per admin unit.

  pw_hw(unit) = sum(cell_hw * cell_pop) / sum(cell_pop)
  pw_mr(unit) = sum(cell_mr * cell_pop) / sum(cell_pop)

Outputs (written to /var/www/precise/euclidean/data/pwdist/):
  adm1.geojson  — provinces / states
  adm2.geojson  — districts
  adm3.geojson  — sub-districts

Usage:
  python3 generate_pweuclidean.py                # process all countries
  python3 generate_pweuclidean.py ZWE KEN MOZ   # specific countries only
  python3 generate_pweuclidean.py --no-download  # skip downloads (use cached rasters)

Requirements: rasterio geopandas h3 tqdm requests numpy
"""

import os, sys, json, gzip, requests, warnings
import numpy as np
import geopandas as gpd
from shapely.geometry import Point
import h3
from tqdm import tqdm

warnings.filterwarnings('ignore')

# ── Paths ──────────────────────────────────────────────────────────────────────
EUCL_COUNTRIES_DIR = '/var/www/precise/euclidean/data/countries'
POP_DIR            = '/home/rutendo/PRECISE/roadnet/worldpop'
OUT_DIR            = '/var/www/precise/euclidean/data/pwdist'
ADM_DATA_DIR       = '/var/www/precise/roadnet/data'

for d in [POP_DIR, OUT_DIR]:
    os.makedirs(d, exist_ok=True)

# ── WorldPop download ──────────────────────────────────────────────────────────
WORLDPOP_URLS = [
    # Constrained estimate (preferred — uses building footprints)
    'https://data.worldpop.org/GIS/Population/Global_2000_2020_Constrained/2020/BSGM/{ISO}/{iso}_ppp_2020_constrained.tif',
    # Unconstrained fallback
    'https://data.worldpop.org/GIS/Population/Global_2000_2020/2020/{ISO}/{iso}_ppp_2020.tif',
]

def download_worldpop(iso3, skip_download=False):
    out_path = os.path.join(POP_DIR, f'{iso3}_pop_2020.tif')
    if os.path.exists(out_path):
        return out_path
    if skip_download:
        return None
    for url_tmpl in WORLDPOP_URLS:
        url = url_tmpl.format(ISO=iso3, iso=iso3.lower())
        try:
            print(f'  Downloading WorldPop for {iso3} from {url}')
            r = requests.get(url, stream=True, timeout=180)
            if r.status_code != 200:
                continue
            total = int(r.headers.get('content-length', 0))
            with open(out_path, 'wb') as f, tqdm(total=total, unit='B', unit_scale=True,
                                                   desc=f'  {iso3}', leave=False) as bar:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
                    bar.update(len(chunk))
            print(f'  Saved {out_path}')
            return out_path
        except Exception as e:
            print(f'  URL failed ({e}), trying next...')
    print(f'  WARNING: Could not download WorldPop for {iso3}')
    return None

# ── Load euclidean distance data ───────────────────────────────────────────────
def load_country_euclidean(iso3):
    path = os.path.join(EUCL_COUNTRIES_DIR, f'{iso3}.json.gz')
    if not os.path.exists(path):
        return {}
    with gzip.open(path) as f:
        return json.load(f)

def get_hw(v):
    """Extract highway distance (km) from a cell value object."""
    return float(v.get('hw', 0) or 0)

def get_mr(v):
    """Extract major road distance (km) from a cell value object."""
    return float(v.get('mr', 0) or 0)

# ── Raster → H3 cell population ───────────────────────────────────────────────
def raster_to_h3_pop(tif_path, res=7):
    """
    Aggregate WorldPop raster pixels to H3 cells at the given resolution.
    Each pixel's population is assigned to the H3 cell containing its centroid.
    Returns dict: {h3_cell_id: population_sum}
    """
    import rasterio
    cell_pop = {}
    with rasterio.open(tif_path) as src:
        data = src.read(1, masked=True)
        T = src.transform
        nodata = src.nodata

        # Find all pixels with valid positive population
        mask = (~data.mask) & (data.data > 0)
        if nodata is not None:
            mask &= (data.data != nodata)
        rows, cols = np.where(mask)
        if len(rows) == 0:
            return cell_pop

        # Pixel centroids
        lons = T.c + (cols + 0.5) * T.a
        lats = T.f + (rows + 0.5) * T.e
        pops = data.data[rows, cols].astype(float)

        print(f'    Assigning {len(rows):,} pixels to H3 res-{res} cells...')
        chunk = 200_000
        for start in tqdm(range(0, len(rows), chunk), desc='    pixels', leave=False):
            end = min(start + chunk, len(rows))
            for lat, lon, pop in zip(lats[start:end], lons[start:end], pops[start:end]):
                if np.isnan(pop) or pop <= 0:
                    continue
                try:
                    cell = h3.latlng_to_cell(float(lat), float(lon), res)
                    cell_pop[cell] = cell_pop.get(cell, 0.0) + float(pop)
                except Exception:
                    pass
    return cell_pop

# ── Spatial join: H3 cells → admin units ──────────────────────────────────────
def cells_to_geodataframe(eucl_data, cell_pop):
    """
    Build a GeoDataFrame of H3 cell centroids with hw, mr and population columns.
    Only includes cells that have population > 0 and at least one distance > 0.
    """
    rows = []
    for cell_id, v in eucl_data.items():
        hw  = get_hw(v)
        mr  = get_mr(v)
        pop = cell_pop.get(cell_id, 0.0)
        if pop <= 0:
            continue
        if hw <= 0 and mr <= 0:
            continue
        lat, lon = h3.cell_to_latlng(cell_id)
        rows.append({
            'cell_id':  cell_id,
            'hw':       hw,
            'mr':       mr,
            'pop':      pop,
            'geometry': Point(lon, lat),
        })
    if not rows:
        return gpd.GeoDataFrame(
            columns=['cell_id', 'hw', 'mr', 'pop', 'geometry'],
            crs='EPSG:4326'
        )
    return gpd.GeoDataFrame(rows, crs='EPSG:4326')

# ── Write outputs (called after each country so progress is never lost) ───────
def _write_outputs(adm_gdfs, adm_accum, adm_levels, out_dir):
    for key, _, _ in adm_levels:
        adm_gdf = adm_gdfs[key].copy()
        acc     = adm_accum[key]

        def lookup_hw(idx):
            entry = acc.get(idx)
            if not entry or entry['den'] <= 0:
                return None
            return round(entry['num_hw'] / entry['den'], 6)

        def lookup_mr(idx):
            entry = acc.get(idx)
            if not entry or entry['den'] <= 0:
                return None
            return round(entry['num_mr'] / entry['den'], 6)

        def lookup_pop(idx):
            entry = acc.get(idx)
            if not entry or entry['den'] <= 0:
                return 0.0
            return round(entry['den'])

        def lookup_cells(idx):
            entry = acc.get(idx)
            if not entry:
                return 0
            return entry['cells']

        adm_gdf['pw_hw']  = adm_gdf.index.map(lookup_hw)
        adm_gdf['pw_mr']  = adm_gdf.index.map(lookup_mr)
        adm_gdf['pop']    = adm_gdf.index.map(lookup_pop)
        adm_gdf['cells']  = adm_gdf.index.map(lookup_cells)

        # Only write features that have at least one valid metric and minimum 3 cells
        out_gdf = adm_gdf[
            (adm_gdf['pw_hw'].notna() | adm_gdf['pw_mr'].notna()) &
            (adm_gdf['cells'] >= 3)
        ].copy()
        out_gdf = out_gdf.drop(columns=['_name'], errors='ignore')

        out_path = os.path.join(out_dir, f'{key}.geojson')
        out_gdf.to_file(out_path, driver='GeoJSON')
        print(f'    {key}: {len(out_gdf)} features written to {out_path}')

# ── Main pipeline ──────────────────────────────────────────────────────────────
def main():
    skip_download = '--no-download' in sys.argv
    specific_isos = [a for a in sys.argv[1:] if not a.startswith('--')]

    # Which countries to process
    all_isos = sorted([
        f.split('.')[0]
        for f in os.listdir(EUCL_COUNTRIES_DIR)
        if f.endswith('.json.gz')
    ])
    isos = specific_isos if specific_isos else all_isos
    print(f'Processing {len(isos)} countries: {", ".join(isos)}')

    # Load admin boundaries (once — they cover all Africa)
    print('\nLoading admin boundary files...')
    adm_levels = [
        ('adm1', os.path.join(ADM_DATA_DIR, 'provinces.geojson'),     'name'),
        ('adm2', os.path.join(ADM_DATA_DIR, 'districts.geojson'),     'name'),
        ('adm3', os.path.join(ADM_DATA_DIR, 'sub_districts.geojson'), 'name'),
    ]
    adm_gdfs = {}
    for key, path, _ in adm_levels:
        gdf = gpd.read_file(path).to_crs('EPSG:4326')
        # Use name_en when available, fall back to name
        if 'name_en' in gdf.columns:
            gdf['_name'] = gdf['name_en'].where(gdf['name_en'].str.strip() != '', gdf['name'])
        else:
            gdf['_name'] = gdf['name']
        adm_gdfs[key] = gdf
        print(f'  {key}: {len(gdf)} features')

    # Accumulate results keyed by the feature's integer row index in adm_gdfs[key].
    # Using row index (not name) avoids false matches where two admin units in
    # different countries happen to share the same name (e.g. "Central Province").
    # Structure: {key: {row_idx: {'num_hw', 'num_mr', 'den', 'cells'}}}
    adm_accum = {key: {} for key in adm_gdfs}

    for iso in isos:
        print(f'\n── {iso} ─────────────────────────────────────────')

        # Load euclidean distance data
        eucl_data = load_country_euclidean(iso)
        if not eucl_data:
            print(f'  No euclidean data found, skipping')
            continue
        print(f'  {len(eucl_data):,} H3 cells')

        # Download / load WorldPop raster
        tif_path = download_worldpop(iso, skip_download=skip_download)
        if tif_path is None:
            print(f'  Skipping {iso} — no population raster')
            continue

        # Raster → H3 cell populations
        print(f'  Aggregating population raster...')
        try:
            cell_pop = raster_to_h3_pop(tif_path, res=7)
        except Exception as e:
            print(f'  ERROR reading raster for {iso}: {e}')
            print(f'  Deleting corrupt file and skipping — re-run to retry.')
            os.remove(tif_path)
            continue
        print(f'  {len(cell_pop):,} populated H3 cells')

        # Build cell GeoDataFrame
        cells_gdf = cells_to_geodataframe(eucl_data, cell_pop)
        print(f'  {len(cells_gdf):,} cells with pop>0 and distance data')
        if cells_gdf.empty:
            continue

        # Country bounding box to filter admin units quickly
        minx, miny, maxx, maxy = cells_gdf.total_bounds
        pad = 0.5
        bbox = (minx - pad, miny - pad, maxx + pad, maxy + pad)

        # For each admin level: spatial join, accumulate weighted sums
        for key, _, _ in adm_levels:
            adm_gdf = adm_gdfs[key]
            # Filter to admin units near this country
            adm_sub = adm_gdf.cx[bbox[0]:bbox[2], bbox[1]:bbox[3]].copy()
            if adm_sub.empty:
                continue

            joined = gpd.sjoin(cells_gdf, adm_sub[['geometry']],
                               how='inner', predicate='within')
            if joined.empty:
                continue

            # index_right is the row index of the matched feature in adm_gdfs[key]
            acc = adm_accum[key]
            for feat_idx, group in joined.groupby('index_right'):
                total_pop = float(group['pop'].sum())
                if total_pop <= 0:
                    continue
                weighted_hw = float((group['hw'] * group['pop']).sum())
                weighted_mr = float((group['mr'] * group['pop']).sum())
                if feat_idx not in acc:
                    acc[feat_idx] = {'num_hw': 0.0, 'num_mr': 0.0, 'den': 0.0, 'cells': 0}
                acc[feat_idx]['num_hw'] += weighted_hw
                acc[feat_idx]['num_mr'] += weighted_mr
                acc[feat_idx]['den']    += total_pop
                acc[feat_idx]['cells']  += len(group)

        del cell_pop, cells_gdf
        print(f'  Done {iso}. Writing interim results...')
        _write_outputs(adm_gdfs, adm_accum, adm_levels, OUT_DIR)

    print('\nFinal write...')
    _write_outputs(adm_gdfs, adm_accum, adm_levels, OUT_DIR)
    print('\nAll done. PWED files written to', OUT_DIR)

if __name__ == '__main__':
    main()
