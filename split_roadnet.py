#!/usr/bin/env python3
"""
Split the Africa-wide roadnet JSON into per-country files + a coarse overview.

Usage:
    python split_roadnet.py /var/www/precise/roadnet/data

Reads:  roadnet_africa_r7.json.gz
Writes: countries/{ISO}.json.gz   — per-country hex data (res 7)
        overview_r4.json.gz        — Africa overview at H3 res 4 (~17k cells)
        overview_r4_stats.json     — min/max/p95 for overview color scale
"""
import sys, os, json, gzip
from collections import defaultdict

try:
    import h3
except ImportError:
    print("h3 not found — run: /opt/anaconda3/bin/pip install h3")
    sys.exit(1)

OVERVIEW_RES = 4   # ~1,770 km² per cell, Africa ≈ 17k cells

def main():
    data_dir = sys.argv[1] if len(sys.argv) > 1 else '/var/www/precise/roadnet/data'
    src      = os.path.join(data_dir, 'roadnet_africa_r7.json.gz')
    cdir     = os.path.join(data_dir, 'countries')
    os.makedirs(cdir, exist_ok=True)

    print(f"Reading {src} ...", flush=True)
    with gzip.open(src, 'rt') as f:
        data = json.load(f)
    print(f"  {len(data):,} total cells", flush=True)

    # ── Split by country ────────────────────────────────────────────────────────
    by_country = defaultdict(dict)
    for cell, v in data.items():
        iso = v.get('i', 'ZZ')
        if iso == 'ZZ':
            continue
        by_country[iso][cell] = v

    print(f"Splitting into {len(by_country)} country files ...", flush=True)
    for iso, cells in by_country.items():
        out = os.path.join(cdir, f'{iso}.json.gz')
        with gzip.open(out, 'wt', compresslevel=6) as f:
            json.dump(cells, f, separators=(',', ':'))

    sizes = {iso: os.path.getsize(os.path.join(cdir, f'{iso}.json.gz')) / 1024
             for iso in by_country}
    total_kb = sum(sizes.values())
    print(f"  Written {len(by_country)} files, total {total_kb/1024:.1f} MB", flush=True)
    top5 = sorted(sizes.items(), key=lambda x: -x[1])[:5]
    for iso, kb in top5:
        print(f"  {iso}: {kb:.0f} KB ({len(by_country[iso]):,} cells)")

    # ── Build overview at res 4 ────────────────────────────────────────────────
    print(f"\nBuilding overview at H3 res {OVERVIEW_RES} ...", flush=True)
    parent_km   = defaultdict(float)   # parent cell → sum of child densities
    parent_n    = defaultdict(int)
    parent_iso  = {}                   # parent cell → dominant ISO

    for cell, v in data.items():
        iso = v.get('i', 'ZZ')
        if iso == 'ZZ':
            continue
        # Get res field — new format uses 'r', legacy uses 'd'
        rnd = v.get('r') if v.get('r') is not None else v.get('d', 0)
        parent = h3.cell_to_parent(cell, OVERVIEW_RES)
        parent_km[parent]  += rnd
        parent_n[parent]   += 1
        parent_iso[parent]  = iso   # last one wins — good enough for overview

    overview = {}
    for parent, total in parent_km.items():
        n   = parent_n[parent]
        avg = round(total / n, 4)
        overview[parent] = {'r': avg, 'i': parent_iso[parent], 'n': n}

    out = os.path.join(data_dir, 'overview_r4.json.gz')
    with gzip.open(out, 'wt', compresslevel=6) as f:
        json.dump(overview, f, separators=(',', ':'))
    size_kb = os.path.getsize(out) / 1024
    print(f"  {len(overview):,} overview cells → {out} ({size_kb:.0f} KB)", flush=True)

    # Stats for overview color scale
    vals = sorted(v['r'] for v in overview.values())
    n    = len(vals)
    stats = {
        'n_cells': n,
        'min':  round(vals[0], 4),
        'max':  round(vals[-1], 4),
        'mean': round(sum(vals)/n, 4),
        'p50':  round(vals[n//2], 4),
        'p90':  round(vals[int(0.9*n)], 4),
        'p95':  round(vals[int(0.95*n)], 4),
        'resolution': OVERVIEW_RES,
    }
    with open(os.path.join(data_dir, 'overview_r4_stats.json'), 'w') as f:
        json.dump(stats, f, indent=2)
    print(f"  Overview stats: mean={stats['mean']}, p95={stats['p95']}, max={stats['max']}")
    print("\nDone.")

if __name__ == '__main__':
    main()
