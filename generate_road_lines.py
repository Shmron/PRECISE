#!/usr/bin/env python3
"""
Generate simplified road line GeoJSON files from the Africa OSM PBF.

Outputs (in output_dir/roads/):
  highways.json.gz     — motorway + trunk lines, Africa-wide (simplified)
  major_roads.json.gz  — primary + secondary lines, Africa-wide (simplified)

The simplification tolerance (degrees) reduces file size while keeping
the road network visually correct at country/continent zoom levels.

Usage:
    python generate_road_lines.py \\
        /home/rutendo/pbf/africa-latest.osm.pbf \\
        /var/www/precise/euclidean/data
"""

import sys, os, json, gzip, math, time
import osmium
from shapely.geometry import LineString, mapping
from shapely.ops import transform
import pyproj

PBF_PATH = '/home/rutendo/pbf/africa-latest.osm.pbf'
OUT_DIR  = '/var/www/precise/euclidean/data'

HIGHWAY_TYPES = {'motorway', 'trunk', 'motorway_link', 'trunk_link'}
MAJOR_TYPES   = HIGHWAY_TYPES | {'primary', 'secondary', 'primary_link', 'secondary_link'}

# Simplification tolerance in degrees (~1km at equator)
HW_TOLERANCE = 0.005   # ~500m — highways: keep good detail
MR_TOLERANCE = 0.01    # ~1km  — major roads: more aggressive


class RoadLineHandler(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.hw_lines = []
        self.mr_lines = []
        self.n_ways   = 0
        self.t0       = time.time()

    def way(self, w):
        hw = w.tags.get('highway', '')
        if hw not in MAJOR_TYPES:
            return
        nodes = list(w.nodes)
        if len(nodes) < 2:
            return
        try:
            coords = [(n.lon, n.lat) for n in nodes]
        except osmium.InvalidLocationError:
            return
        if any(abs(lon) < 1e-6 and abs(lat) < 1e-6 for lon, lat in coords):
            return

        self.n_ways += 1
        if self.n_ways % 200_000 == 0:
            e = time.time() - self.t0
            print(f"  {self.n_ways:,} ways  hw={len(self.hw_lines):,}  mr={len(self.mr_lines):,}  {e/60:.1f}m", flush=True)

        is_hw = hw in HIGHWAY_TYPES
        if is_hw:
            self.hw_lines.append(coords)
        # ALL major road types go into mr_lines (highways + primary/secondary)
        # because highways are a subset of major roads
        self.mr_lines.append(coords)


def simplify_lines(lines, tolerance):
    features = []
    for coords in lines:
        try:
            ls = LineString(coords)
            ls_s = ls.simplify(tolerance, preserve_topology=False)
            if ls_s.is_empty or len(ls_s.coords) < 2:
                continue
            features.append({
                'type': 'Feature',
                'properties': {},
                'geometry': mapping(ls_s),
            })
        except Exception:
            continue
    return {'type': 'FeatureCollection', 'features': features}


def write_gz(path, gj):
    with gzip.open(path, 'wt', encoding='utf-8', compresslevel=6) as f:
        json.dump(gj, f, separators=(',', ':'))
    size_mb = os.path.getsize(path) / 1024**2
    print(f"  {path}  ({size_mb:.1f} MB, {len(gj['features']):,} features)")


def main():
    pbf_path = sys.argv[1] if len(sys.argv) > 1 else PBF_PATH
    out_dir  = sys.argv[2] if len(sys.argv) > 2 else OUT_DIR
    roads_dir = os.path.join(out_dir, 'roads')
    os.makedirs(roads_dir, exist_ok=True)

    if not os.path.isfile(pbf_path):
        print(f"Error: PBF not found: {pbf_path}"); sys.exit(1)

    print("=" * 60)
    print("Africa Road Line Extractor")
    print("=" * 60)
    print(f"PBF:    {pbf_path}  ({os.path.getsize(pbf_path)/1024**3:.1f} GB)")
    print(f"Output: {roads_dir}")
    print()

    print("Step 1/3 — Streaming PBF...")
    handler = RoadLineHandler()
    handler.apply_file(pbf_path, locations=True, idx='flex_mem')
    elapsed = time.time() - handler.t0
    print(f"\n  Done in {elapsed/60:.1f} min")
    print(f"  Highway ways:    {len(handler.hw_lines):,}")
    print(f"  Major road ways: {len(handler.mr_lines):,}")

    print("\nStep 2/3 — Simplifying highway lines...")
    hw_gj = simplify_lines(handler.hw_lines, HW_TOLERANCE)
    handler.hw_lines = None
    print(f"  {len(hw_gj['features']):,} highway features")

    print("\nStep 3/3 — Simplifying major road lines and writing output...")
    mr_gj = simplify_lines(handler.mr_lines, MR_TOLERANCE)
    handler.mr_lines = None
    print(f"  {len(mr_gj['features']):,} major road features")

    write_gz(os.path.join(roads_dir, 'highways.json.gz'), hw_gj)
    write_gz(os.path.join(roads_dir, 'major_roads.json.gz'), mr_gj)

    print("\nDone. Road line files written to:", roads_dir)


if __name__ == '__main__':
    main()
