#!/usr/bin/env python3
"""
Africa Road Network Density — H3 Resolution 7
=============================================
Processes an OSM PBF file to compute road length density per H3 hexagon,
then spatially joins to Africa country boundaries for country attribution.

Usage:
    python generate_roadnet.py \
        /home/rutendo/pbf/africa-251110.osm.pbf \
        /home/rutendo/Harmonaize/core/HarmonAIze/harmonaize/geolocation/data_geocoding/Africa_Boundaries.geojson \
        /var/www/precise/roadnet/data

Output (in output_dir):
    roadnet_africa_r7.json.gz   — {h3_cell_id: {d, r, i, n, c}} per hex
                                   d = RND class-adjusted, r = RND raw,
                                   i = ISO, n = country name, c = class breakdown
    roadnet_stats.json          — summary statistics + per-country stats
    africa_bounds.geojson       — simplified country boundaries for the map

Requirements:
    pip install osmium h3
    (geopandas, shapely already installed)
"""

import sys
import os
import json
import gzip
import math
import time
import osmium
import h3
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
from collections import defaultdict

# ── Configuration ──────────────────────────────────────────────────────────────

RESOLUTION = 7          # H3 res 7 ≈ 5.16 km² per hex, ~27 km edge-to-edge
SAMPLE_STEP_KM = 0.4   # Sample every 400m along road segments (< hex edge length ~1.2 km)
BOUNDS_TOLERANCE = 0.05 # Degrees to simplify country boundaries (for web map)

# Road class weights — proxy for vehicular traffic volume / pollution exposure.
# Higher weight = more traffic contribution to RND.
# Footpaths, cycleways, steps etc. are excluded entirely.
HIGHWAY_WEIGHTS = {
    'motorway':       5.0,   # major controlled-access highway
    'trunk':          4.0,   # major arterial
    'primary':        3.0,   # primary route
    'secondary':      2.0,   # secondary route
    'tertiary':       1.5,   # tertiary road
    'unclassified':   1.0,   # minor road, some vehicular
    'residential':    0.8,   # residential street
    'living_street':  0.3,   # pedestrian priority, low vehicular
    'road':           1.0,   # unknown classification
    'track':          0.2,   # agricultural/forestry track — minimal vehicular
    'motorway_link':  4.5,
    'trunk_link':     3.5,
    'primary_link':   2.5,
    'secondary_link': 1.8,
    'tertiary_link':  1.2,
}

HIGHWAY_CLASSES = set(HIGHWAY_WEIGHTS.keys())

# Class groupings for per-hexagon breakdown in output
# (grouped to keep file size manageable)
CLASS_GROUPS = {
    'major':   {'motorway', 'trunk', 'motorway_link', 'trunk_link'},
    'primary': {'primary', 'secondary', 'primary_link', 'secondary_link'},
    'minor':   {'tertiary', 'unclassified', 'tertiary_link', 'road'},
    'local':   {'residential', 'living_street', 'track'},
}

# ── Geometry helpers ───────────────────────────────────────────────────────────

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def sample_segment(lat1, lon1, lat2, lon2, step_km=SAMPLE_STEP_KM):
    dist = haversine_km(lat1, lon1, lat2, lon2)
    if dist < 1e-6:
        return
    n = max(1, int(math.ceil(dist / step_km)))
    piece = dist / n
    for i in range(n):
        t = (i + 0.5) / n
        yield lat1 + t*(lat2-lat1), lon1 + t*(lon2-lon1), piece


# ── OSM handler ────────────────────────────────────────────────────────────────

def get_class_group(hw):
    for group, members in CLASS_GROUPS.items():
        if hw in members:
            return group
    return 'minor'


class RoadDensityHandler(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.hex_km = defaultdict(float)            # cell → class-adjusted km (for RND)
        self.hex_raw_km = defaultdict(float)        # cell → actual road km
        self.hex_class_km = defaultdict(           # cell → {group → actual km}
            lambda: defaultdict(float))
        self.n_ways = 0
        self.n_samples = 0
        self.t0 = time.time()

    def way(self, w):
        hw = w.tags.get('highway', '')
        if hw not in HIGHWAY_CLASSES:
            return
        nodes = list(w.nodes)
        if len(nodes) < 2:
            return
        try:
            coords = [(n.lat, n.lon) for n in nodes]
        except osmium.InvalidLocationError:
            return

        weight = HIGHWAY_WEIGHTS.get(hw, 1.0)
        group  = get_class_group(hw)

        self.n_ways += 1
        if self.n_ways % 200_000 == 0:
            elapsed = time.time() - self.t0
            print(f"  {self.n_ways:,} road ways | {len(self.hex_km):,} cells | "
                  f"{elapsed/60:.1f} min elapsed", flush=True)

        for i in range(len(coords) - 1):
            lat1, lon1 = coords[i]
            lat2, lon2 = coords[i+1]
            if abs(lat1) < 1e-6 and abs(lon1) < 1e-6:
                continue
            for lat, lon, seg_km in sample_segment(lat1, lon1, lat2, lon2):
                cell = h3.latlng_to_cell(lat, lon, RESOLUTION)
                self.hex_km[cell]          += seg_km * weight  # weighted km
                self.hex_raw_km[cell]      += seg_km           # actual km
                self.hex_class_km[cell][group] += seg_km       # class breakdown
                self.n_samples += 1


# ── Country spatial join ───────────────────────────────────────────────────────

def assign_countries(hex_km: dict, boundaries_path: str) -> dict:
    """
    Spatially join H3 cell centroids to Africa country boundaries.
    Returns {cell_id: {'iso': str, 'name': str}} for cells that fall in Africa.
    Cells outside any country polygon (ocean, islands) keep iso='ZZ'.
    """
    print("  Loading Africa boundaries...", flush=True)
    africa = gpd.read_file(boundaries_path)
    africa = africa[['ISO', 'NAME_0', 'geometry']].copy()
    africa = africa.to_crs('EPSG:4326')

    print(f"  Building centroids for {len(hex_km):,} H3 cells...", flush=True)
    cells = list(hex_km.keys())

    # h3.cell_to_latlng returns (lat, lon)
    centroids = []
    for cell in cells:
        lat, lon = h3.cell_to_latlng(cell)
        centroids.append(Point(lon, lat))   # shapely uses (x=lon, y=lat)

    cell_gdf = gpd.GeoDataFrame({'cell': cells}, geometry=centroids, crs='EPSG:4326')

    print("  Running spatial join (centroid → country)...", flush=True)
    joined = gpd.sjoin(cell_gdf, africa, how='left', predicate='within')

    result = {}
    for _, row in joined.iterrows():
        iso = row['ISO'] if pd.notna(row.get('ISO')) else 'ZZ'
        name = row['NAME_0'] if pd.notna(row.get('NAME_0')) else 'Unknown'
        result[row['cell']] = {'iso': iso, 'name': name}

    in_africa = sum(1 for v in result.values() if v['iso'] != 'ZZ')
    print(f"  Cells in Africa: {in_africa:,} | outside (ocean/edge): "
          f"{len(result)-in_africa:,}", flush=True)
    return result


def simplify_boundaries(boundaries_path: str, out_path: str):
    """Simplify boundaries for web map (reduces file size ~10×)."""
    print("  Simplifying country boundaries for web map...", flush=True)
    africa = gpd.read_file(boundaries_path)
    africa = africa[['ISO', 'NAME_0', 'REgion', 'geometry']].copy()
    africa['geometry'] = africa['geometry'].simplify(
        BOUNDS_TOLERANCE, preserve_topology=True
    )
    africa = africa.rename(columns={'NAME_0': 'name', 'REgion': 'region'})
    africa.to_file(out_path, driver='GeoJSON')
    size_kb = os.path.getsize(out_path) / 1024
    print(f"  Boundaries written: {out_path} ({size_kb:.0f} KB)", flush=True)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 4:
        print(__doc__)
        print("\nExample:")
        print("  python generate_roadnet.py \\")
        print("    /home/rutendo/pbf/africa-251110.osm.pbf \\")
        print("    /home/rutendo/Harmonaize/core/HarmonAIze/harmonaize/geolocation/data_geocoding/Africa_Boundaries.geojson \\")
        print("    /var/www/precise/roadnet/data")
        sys.exit(1)

    pbf_path      = sys.argv[1]
    bounds_path   = sys.argv[2]
    out_dir       = sys.argv[3]

    if not os.path.isfile(pbf_path):
        print(f"Error: PBF not found: {pbf_path}"); sys.exit(1)
    if not os.path.isfile(bounds_path):
        print(f"Error: Boundaries not found: {bounds_path}"); sys.exit(1)

    os.makedirs(out_dir, exist_ok=True)
    data_path   = os.path.join(out_dir, 'roadnet_africa_r7.json.gz')
    stats_path  = os.path.join(out_dir, 'roadnet_stats.json')
    bounds_out  = os.path.join(out_dir, 'africa_bounds.geojson')

    size_gb = os.path.getsize(pbf_path) / 1024**3
    print("=" * 60)
    print(f"Africa Road Network Density — H3 Resolution {RESOLUTION}")
    print("=" * 60)
    print(f"PBF:         {pbf_path}  ({size_gb:.1f} GB)")
    print(f"Boundaries:  {bounds_path}")
    print(f"Output:      {out_dir}")
    print(f"H3 res {RESOLUTION}: ~5.16 km²/hex, ~27 km edge-to-edge")
    print()

    # ── Step 1: Stream PBF ─────────────────────────────────────────────────────
    print("Step 1/4 — Streaming PBF, accumulating road lengths...")
    print("  (idx='flex_mem' keeps node locations in RAM — fastest on this server)")
    print()
    handler = RoadDensityHandler()
    handler.apply_file(pbf_path, locations=True, idx='flex_mem')

    elapsed = time.time() - handler.t0
    print(f"\n  Completed in {elapsed/60:.1f} min")
    print(f"  Road ways:  {handler.n_ways:,}")
    print(f"  Samples:    {handler.n_samples:,}")
    print(f"  H3 cells:   {len(handler.hex_km):,}")

    # ── Step 2: Compute densities ──────────────────────────────────────────────
    print("\nStep 2/4 — Computing RND (class-adjusted and raw) per cell...")
    hex_density = {}     # class-adjusted RND (km/km² accounting for road type)
    hex_raw_density = {} # raw RND (actual road km / km²)
    for cell, adj_km in handler.hex_km.items():
        area_km2 = h3.cell_area(cell, unit='km^2')
        hex_density[cell]     = round(adj_km / area_km2, 4)
        hex_raw_density[cell] = round(handler.hex_raw_km.get(cell, 0) / area_km2, 4)

    # ── Step 3: Country attribution ────────────────────────────────────────────
    print("\nStep 3/4 — Spatially attributing cells to countries...")
    country_map = assign_countries(handler.hex_km, bounds_path)

    # Build final data structure
    final = {}
    for cell, density in hex_density.items():
        info = country_map.get(cell, {})
        iso  = info.get('iso', 'ZZ')
        name = info.get('name', 'Unknown')

        # Class breakdown: actual km per group (rounded to 2dp)
        cg = handler.hex_class_km.get(cell, {})
        breakdown = {g: round(cg.get(g, 0), 2) for g in CLASS_GROUPS if cg.get(g, 0) > 0}

        final[cell] = {
            'r': hex_raw_density[cell],# RND = total road km / actual cell area (km²)
            'x': density,              # Traffic exposure index (class-adjusted, NOT RND)
            'i': iso,
            'n': name,
            'c': breakdown             # {major, primary, minor, local} km
        }

    # ── Step 4: Write output ───────────────────────────────────────────────────
    print("\nStep 4/4 — Writing output files...")

    # Compute stats
    africa_cells = {c: v for c, v in final.items() if v['i'] != 'ZZ'}
    densities_only = [v['r'] for v in africa_cells.values()]
    densities_only.sort()
    n = len(densities_only)

    # Per-country stats
    country_stats = defaultdict(lambda: {'cells': 0, 'total_km': 0.0,
                                          'name': '', 'mean_density': 0.0})
    for cell, v in final.items():
        iso = v['i']
        if iso == 'ZZ':
            continue
        km = handler.hex_km.get(cell, 0)
        country_stats[iso]['cells'] += 1
        country_stats[iso]['total_km'] += km
        country_stats[iso]['name'] = v['n']

    for iso, cs in country_stats.items():
        if cs['cells'] > 0:
            # Average density over the country's cells
            vals = [final[c]['r'] for c in africa_cells if final[c]['i'] == iso]
            cs['mean_density'] = round(sum(vals) / len(vals), 4) if vals else 0
            cs['total_km'] = round(cs['total_km'], 1)

    stats = {
        'n_cells_total': len(final),
        'n_cells_africa': n,
        'min_density': round(densities_only[0], 4) if n else 0,
        'max_density': round(densities_only[-1], 4) if n else 0,
        'mean_density': round(sum(densities_only) / n, 4) if n else 0,
        'p50': round(densities_only[n // 2], 4) if n else 0,
        'p75': round(densities_only[int(0.75 * n)], 4) if n else 0,
        'p90': round(densities_only[int(0.90 * n)], 4) if n else 0,
        'p95': round(densities_only[int(0.95 * n)], 4) if n else 0,
        'p99': round(densities_only[int(0.99 * n)], 4) if n else 0,
        'resolution': RESOLUTION,
        'highway_classes': sorted(HIGHWAY_CLASSES),
        'countries': {iso: {k: v for k, v in cs.items() if k != 'name'}
                      for iso, cs in country_stats.items()},
        'country_names': {iso: cs['name'] for iso, cs in country_stats.items()},
    }

    # Write gzipped data
    with gzip.open(data_path, 'wt', encoding='utf-8', compresslevel=6) as f:
        json.dump(final, f, separators=(',', ':'))
    size_mb = os.path.getsize(data_path) / 1024**2
    print(f"  {data_path}  ({size_mb:.1f} MB)")

    # Write stats
    with open(stats_path, 'w') as f:
        json.dump(stats, f, indent=2)
    print(f"  {stats_path}")

    # Write simplified boundaries
    simplify_boundaries(bounds_path, bounds_out)

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"  H3 cells (Africa):  {n:,}")
    print(f"  Mean density:       {stats['mean_density']} km/km²")
    print(f"  Median density:     {stats['p50']} km/km²")
    print(f"  95th percentile:    {stats['p95']} km/km²")
    print(f"  Max density:        {stats['max_density']} km/km²")
    print()
    print("Top 10 countries by mean road density:")
    top = sorted(country_stats.items(), key=lambda x: x[1]['mean_density'], reverse=True)[:10]
    for iso, cs in top:
        print(f"  {iso}  {cs['name']:<20} {cs['mean_density']:.4f} km/km²  "
              f"({cs['cells']:,} cells, {cs['total_km']:,.0f} km road)")
    print()
    print("Files ready. The web map will load them from:")
    print(f"  https://placealert.org/roadnet/")


if __name__ == '__main__':
    main()
