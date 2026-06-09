#!/usr/bin/env python3
"""
Filter per-country euclidean distance files to only include H3 cells that
have WorldPop population > 0, reducing cell counts and preventing browser crashes.

For each country:
  1. Read the WorldPop TIF from roadnet/worldpop/{ISO}_pop_2020.tif
  2. Build the set of H3 res-7 cells that contain at least one populated pixel
  3. Filter the euclidean JSON to only those cells
  4. Overwrite the .json.gz file in-place

Usage:
  python3 filter_euclidean_pop.py            # all countries
  python3 filter_euclidean_pop.py ZWE KEN    # specific countries

Requirements: rasterio h3 numpy tqdm
"""

import os, sys, gzip, json
import numpy as np

EUCL_DIR = '/var/www/precise/euclidean/data/countries'
POP_DIR  = '/home/rutendo/PRECISE/roadnet/worldpop'

def get_populated_cells(tif_path, res=7):
    """
    Return the set of H3 cells (at given resolution) that contain at least
    one pixel with population > 0 in the given WorldPop TIF.
    """
    import rasterio
    import h3

    populated = set()
    with rasterio.open(tif_path) as src:
        data = src.read(1, masked=True)
        T = src.transform
        nodata = src.nodata

        mask = (~data.mask) & (data.data > 0)
        if nodata is not None:
            mask &= (data.data != nodata)

        rows, cols = np.where(mask)
        if len(rows) == 0:
            return populated

        lons = T.c + (cols + 0.5) * T.a
        lats = T.f + (rows + 0.5) * T.e
        pops = data.data[rows, cols].astype(float)

        chunk = 200_000
        for start in range(0, len(rows), chunk):
            end = min(start + chunk, len(rows))
            for lat, lon, pop in zip(lats[start:end], lons[start:end], pops[start:end]):
                if np.isnan(pop) or pop <= 0:
                    continue
                try:
                    cell = h3.latlng_to_cell(float(lat), float(lon), res)
                    populated.add(cell)
                except Exception:
                    pass

    return populated


def process_country(iso):
    eucl_path = os.path.join(EUCL_DIR, f'{iso}.json.gz')
    tif_path  = os.path.join(POP_DIR,  f'{iso}_pop_2020.tif')

    if not os.path.exists(eucl_path):
        print(f'{iso}: no euclidean file, skipping')
        return

    if not os.path.exists(tif_path):
        print(f'{iso}: no WorldPop TIF, skipping')
        return

    # Load euclidean data
    with gzip.open(eucl_path) as f:
        data = json.load(f)
    before = len(data)

    # Build set of populated H3 cells from the raster
    try:
        populated = get_populated_cells(tif_path, res=7)
    except Exception as e:
        print(f'{iso}: ERROR reading TIF: {e}')
        return

    # Filter
    filtered = {cell: v for cell, v in data.items() if cell in populated}
    after = len(filtered)
    removed = before - after

    # Overwrite only if anything changed
    if removed == 0:
        print(f'{iso}: {before} cells → {after} cells (nothing removed)')
        return

    with gzip.open(eucl_path, 'wt', encoding='utf-8') as f:
        json.dump(filtered, f, separators=(',', ':'))

    print(f'{iso}: {before} cells → {after} cells (removed {removed})')


def main():
    specific_isos = [a for a in sys.argv[1:] if not a.startswith('--')]

    if specific_isos:
        isos = specific_isos
    else:
        isos = sorted([
            f.split('.')[0]
            for f in os.listdir(EUCL_DIR)
            if f.endswith('.json.gz')
        ])

    print(f'Processing {len(isos)} countr{"y" if len(isos)==1 else "ies"}')
    for iso in isos:
        process_country(iso)
    print('Done.')


if __name__ == '__main__':
    main()
