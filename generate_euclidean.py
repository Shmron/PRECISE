#!/usr/bin/env python3
"""
Africa Euclidean Distance to Highways and Major Roads — H3 Resolution 7
=======================================================================
For each H3 res-7 cell in Africa, computes straight-line distance (km) to the
nearest highway and to the nearest major road.

  Highways:    motorway, trunk  (+ _link variants)
  Major roads: highways + primary, secondary  (+ _link variants)

  Note: every highway IS a major road, so dist_major <= dist_highway always.

Usage:
    python generate_euclidean.py \\
        /home/rutendo/africa-latest.osm.pbf \\
        /home/rutendo/Harmonaize/core/HarmonAIze/harmonaize/geolocation/data_geocoding/Africa_Boundaries.geojson \\
        /var/www/precise/euclidean/data

Output (in out_dir/):
    countries/{ISO}.json.gz   — per-country res-7 data: {cell: {hw, mr, i, n}}
    overview_r4.json.gz       — continent overview at H3 res 4 (median of children)
    overview_r4_stats.json    — color-scale calibration for the viewer
    euclidean_stats.json      — Africa-wide + per-country stats

Requirements:
    pip install osmium h3 scipy numpy geopandas
"""

import sys
import os
import json
import gzip
import math
import time
import osmium
import h3
import numpy as np
import geopandas as gpd
from scipy.spatial import cKDTree
from collections import defaultdict

RESOLUTION   = 7
OVERVIEW_RES = 4
STEP_KM      = 0.5    # sample road geometry every 500 m
R_EARTH      = 6371.0

# Highways: controlled-access motorways and trunk arterials
HIGHWAY_TYPES = {'motorway', 'trunk', 'motorway_link', 'trunk_link'}

# Major roads: highways + primary and secondary roads
MAJOR_TYPES = HIGHWAY_TYPES | {'primary', 'secondary', 'primary_link', 'secondary_link'}


# ── Geometry helpers ──────────────────────────────────────────────────────────

def haversine_km(lat1, lon1, lat2, lon2):
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return R_EARTH * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def sample_segment(lat1, lon1, lat2, lon2):
    d = haversine_km(lat1, lon1, lat2, lon2)
    if d < 1e-6:
        return
    n = max(1, int(math.ceil(d / STEP_KM)))
    for i in range(n):
        t = (i + 0.5) / n
        yield lat1 + t*(lat2-lat1), lon1 + t*(lon2-lon1)


def to_xyz(lats, lons):
    """Convert lat/lon arrays (degrees) to unit-sphere 3D Cartesian."""
    phi = np.radians(np.asarray(lats, dtype=np.float64))
    lam = np.radians(np.asarray(lons, dtype=np.float64))
    return np.stack([
        np.cos(phi) * np.cos(lam),
        np.cos(phi) * np.sin(lam),
        np.sin(phi),
    ], axis=1)


def chord_to_km(d):
    """Chord distance on unit sphere → great-circle km."""
    return R_EARTH * 2 * np.arcsin(np.clip(d / 2, 0, 1))


# ── OSM handler ───────────────────────────────────────────────────────────────

class PointCollector(osmium.SimpleHandler):
    """Stream OSM ways; accumulate sampled lat/lon for highway and major road classes."""

    def __init__(self):
        super().__init__()
        self.hw_lats, self.hw_lons = [], []
        self.mr_lats, self.mr_lons = [], []
        self.n_ways = 0
        self.t0 = time.time()

    def way(self, w):
        hw = w.tags.get('highway', '')
        if hw not in MAJOR_TYPES:
            return
        nodes = list(w.nodes)
        if len(nodes) < 2:
            return
        try:
            coords = [(n.lat, n.lon) for n in nodes]
        except osmium.InvalidLocationError:
            return

        is_hw = hw in HIGHWAY_TYPES
        self.n_ways += 1
        if self.n_ways % 100_000 == 0:
            e = time.time() - self.t0
            print(f"  {self.n_ways:,} ways  hw={len(self.hw_lats):,}  mr={len(self.mr_lats):,}  {e/60:.1f} min", flush=True)

        for i in range(len(coords) - 1):
            lat1, lon1 = coords[i]
            lat2, lon2 = coords[i+1]
            if abs(lat1) < 1e-6 and abs(lon1) < 1e-6:
                continue
            for lat, lon in sample_segment(lat1, lon1, lat2, lon2):
                self.mr_lats.append(lat)
                self.mr_lons.append(lon)
                if is_hw:
                    self.hw_lats.append(lat)
                    self.hw_lons.append(lon)


# ── Main ──────────────────────────────────────────────────────────────────────

def pct(arr, p):
    """p-th percentile of a sorted list."""
    n = len(arr)
    return round(arr[min(n - 1, int(p / 100 * n))], 2)


def main():
    if len(sys.argv) < 4:
        print(__doc__); sys.exit(1)

    pbf_path    = sys.argv[1]
    bounds_path = sys.argv[2]
    out_dir     = sys.argv[3]

    for p in [pbf_path, bounds_path]:
        if not os.path.isfile(p):
            print(f"Error: not found: {p}"); sys.exit(1)

    cdir = os.path.join(out_dir, 'countries')
    os.makedirs(cdir, exist_ok=True)

    print("=" * 60)
    print("Africa Euclidean Distance — H3 Resolution 7")
    print("=" * 60)
    print(f"PBF:     {pbf_path}  ({os.path.getsize(pbf_path)/1024**3:.1f} GB)")
    print(f"Bounds:  {bounds_path}")
    print(f"Output:  {out_dir}")
    print()

    # ── Step 1: Stream PBF ────────────────────────────────────────────────────
    print("Step 1/4 — Streaming PBF, collecting road sample points...")
    print("  (Highways: motorway/trunk  |  Major roads: + primary/secondary)")
    collector = PointCollector()
    collector.apply_file(pbf_path, locations=True, idx='flex_mem')
    elapsed = time.time() - collector.t0
    print(f"\n  Done in {elapsed/60:.1f} min")
    print(f"  Highway pts:    {len(collector.hw_lats):,}")
    print(f"  Major road pts: {len(collector.mr_lats):,}")

    # ── Step 2: Build KD-trees ────────────────────────────────────────────────
    print("\nStep 2/4 — Building 3D unit-sphere KD-trees...")
    t2 = time.time()
    hw_tree = cKDTree(to_xyz(collector.hw_lats, collector.hw_lons))
    mr_tree = cKDTree(to_xyz(collector.mr_lats, collector.mr_lons))
    collector.hw_lats = collector.hw_lons = collector.mr_lats = collector.mr_lons = None
    print(f"  hw_tree: {hw_tree.n:,} pts  |  mr_tree: {mr_tree.n:,} pts  ({time.time()-t2:.0f}s)")

    # ── Step 3: Per-country polyfill + distance query ─────────────────────────
    print("\nStep 3/4 — Computing per-country distances (polyfill → query)...")
    africa = gpd.read_file(bounds_path)[['ISO', 'NAME_0', 'geometry']].to_crs('EPSG:4326')

    country_stats  = {}
    overview_rows  = []    # (cell, hw_km, mr_km, iso, name)
    all_hw_vals    = []    # for Africa-wide stats
    all_mr_vals    = []

    for _, row in africa.iterrows():
        iso  = str(row['ISO'])    if row['ISO']    else 'ZZ'
        name = str(row['NAME_0']) if row['NAME_0'] else 'Unknown'
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue

        t_c = time.time()
        try:
            cells = list(h3.geo_to_cells(geom.__geo_interface__, RESOLUTION))
        except Exception as e:
            print(f"  Warning: {iso} polyfill failed — {e}", flush=True)
            continue

        if not cells:
            continue

        lats = np.array([h3.cell_to_latlng(c)[0] for c in cells])
        lons = np.array([h3.cell_to_latlng(c)[1] for c in cells])
        xyz  = to_xyz(lats, lons)
        hw_km = chord_to_km(hw_tree.query(xyz, workers=-1)[0])
        mr_km = chord_to_km(mr_tree.query(xyz, workers=-1)[0])

        # Write per-country file
        country_data = {}
        for i, cell in enumerate(cells):
            country_data[cell] = {
                'hw': round(float(hw_km[i]), 2),
                'mr': round(float(mr_km[i]), 2),
                'i':  iso,
                'n':  name,
            }
        with gzip.open(os.path.join(cdir, f'{iso}.json.gz'), 'wt', compresslevel=6) as f:
            json.dump(country_data, f, separators=(',', ':'))

        # Country stats
        hw_s = sorted(float(x) for x in hw_km)
        mr_s = sorted(float(x) for x in mr_km)
        n    = len(hw_s)
        country_stats[iso] = {
            'name':   name,
            'cells':  n,
            'hw_med': pct(hw_s, 50), 'hw_p75': pct(hw_s, 75), 'hw_p95': pct(hw_s, 95),
            'mr_med': pct(mr_s, 50), 'mr_p75': pct(mr_s, 75), 'mr_p95': pct(mr_s, 95),
        }

        for i, cell in enumerate(cells):
            hw_v = float(hw_km[i])
            mr_v = float(mr_km[i])
            overview_rows.append((cell, hw_v, mr_v, iso, name))
            all_hw_vals.append(hw_v)
            all_mr_vals.append(mr_v)

        elapsed_c = time.time() - t_c
        print(f"  {iso:<4} {name:<22} {n:>7,} cells  "
              f"hw_med={country_stats[iso]['hw_med']:>7.1f} km  "
              f"mr_med={country_stats[iso]['mr_med']:>7.1f} km  ({elapsed_c:.0f}s)", flush=True)

    # ── Step 4: Overview (res 4) ──────────────────────────────────────────────
    print("\nStep 4/4 — Building res-4 overview and writing stats...")

    parent_hw   = defaultdict(list)
    parent_mr   = defaultdict(list)
    parent_meta = {}
    for cell, hw, mr, iso, name in overview_rows:
        p = h3.cell_to_parent(cell, OVERVIEW_RES)
        parent_hw[p].append(hw)
        parent_mr[p].append(mr)
        parent_meta[p] = (iso, name)

    overview = {}
    for parent in parent_hw:
        hw_vals = sorted(parent_hw[parent])
        mr_vals = sorted(parent_mr[parent])
        n = len(hw_vals)
        iso, name = parent_meta[parent]
        overview[parent] = {
            'hw': round(hw_vals[n // 2], 2),
            'mr': round(mr_vals[n // 2], 2),
            'i':  iso,
            'n':  name,
        }

    with gzip.open(os.path.join(out_dir, 'overview_r4.json.gz'), 'wt', compresslevel=6) as f:
        json.dump(overview, f, separators=(',', ':'))
    sz = os.path.getsize(os.path.join(out_dir, 'overview_r4.json.gz')) / 1024
    print(f"  Overview: {len(overview):,} cells ({sz:.0f} KB)")

    hw_ov = sorted(v['hw'] for v in overview.values())
    mr_ov = sorted(v['mr'] for v in overview.values())
    n_ov  = len(hw_ov)
    q = lambda arr, p: round(arr[int(p / 100 * n_ov)], 2)
    ov_stats = {
        'n_cells': n_ov,
        'highway': {
            'min': hw_ov[0], 'max': hw_ov[-1], 'mean': round(sum(hw_ov) / n_ov, 2),
            'p50': q(hw_ov, 50), 'p75': q(hw_ov, 75), 'p90': q(hw_ov, 90), 'p95': q(hw_ov, 95),
        },
        'major': {
            'min': mr_ov[0], 'max': mr_ov[-1], 'mean': round(sum(mr_ov) / n_ov, 2),
            'p50': q(mr_ov, 50), 'p75': q(mr_ov, 75), 'p90': q(mr_ov, 90), 'p95': q(mr_ov, 95),
        },
    }
    with open(os.path.join(out_dir, 'overview_r4_stats.json'), 'w') as f:
        json.dump(ov_stats, f, indent=2)

    # Africa-wide stats from all cells
    hw_a = sorted(all_hw_vals)
    mr_a = sorted(all_mr_vals)
    n_a  = len(hw_a)
    qa = lambda arr, p: round(arr[int(p / 100 * n_a)], 2)
    full_stats = {
        'n_countries': len(country_stats),
        'resolution': RESOLUTION,
        'highway_types': sorted(HIGHWAY_TYPES),
        'major_road_types': sorted(MAJOR_TYPES),
        'africa': {
            'cells': n_a,
            'highway': {
                'mean': round(sum(hw_a) / n_a, 2),
                'p50': qa(hw_a, 50), 'p75': qa(hw_a, 75), 'p90': qa(hw_a, 90), 'p95': qa(hw_a, 95),
            },
            'major': {
                'mean': round(sum(mr_a) / n_a, 2),
                'p50': qa(mr_a, 50), 'p75': qa(mr_a, 75), 'p90': qa(mr_a, 90), 'p95': qa(mr_a, 95),
            },
        },
        'countries': country_stats,
        'country_names': {iso: cs['name'] for iso, cs in country_stats.items()},
    }
    with open(os.path.join(out_dir, 'euclidean_stats.json'), 'w') as f:
        json.dump(full_stats, f, indent=2)
    print(f"  {len(country_stats)} countries, {n_a:,} total cells")

    print(f"\n{'='*60}")
    print("Summary")
    print(f"{'='*60}")
    print(f"  Total cells:              {n_a:,}")
    print(f"  Africa median → highway:  {full_stats['africa']['highway']['p50']} km")
    print(f"  Africa median → major:    {full_stats['africa']['major']['p50']} km")
    print(f"  Africa 95th  → highway:   {full_stats['africa']['highway']['p95']} km")
    print(f"  Africa 95th  → major:     {full_stats['africa']['major']['p95']} km")
    print()
    print("Top 5 most isolated (highest median distance to highway):")
    top5 = sorted(country_stats.items(), key=lambda x: x[1]['hw_med'], reverse=True)[:5]
    for iso, cs in top5:
        print(f"  {iso:<4} {cs['name']:<22}  hw_med={cs['hw_med']:>7.1f} km  mr_med={cs['mr_med']:>7.1f} km")
    print()
    print(f"Output: {out_dir}")
    print("Deploy: copy euclidean_index.html → /var/www/precise/euclidean/index.html")


if __name__ == '__main__':
    main()
