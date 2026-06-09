import os
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

JOBS_DIR = '/home/rutendo/PRECISE/palsearth/jobs'

PERCENTILE_MAP = {'p50': 50, 'p75': 75, 'p95': 95, 'p99': 99}


def _detect_lat_lon(df):
    lat_candidates = ['latitude', 'lat', 'LAT', 'Latitude', 'LATITUDE', 'y', 'Y']
    lon_candidates = ['longitude', 'lon', 'LON', 'Longitude', 'LONGITUDE', 'x', 'X', 'lng', 'LNG']
    lat_col = next((c for c in lat_candidates if c in df.columns), None)
    lon_col = next((c for c in lon_candidates if c in df.columns), None)
    return lat_col, lon_col


def _build_reducer(stats):
    import ee
    reducer = None
    for stat in stats:
        if stat == 'mean':
            r = ee.Reducer.mean()
        elif stat == 'min':
            r = ee.Reducer.min()
        elif stat == 'max':
            r = ee.Reducer.max()
        elif stat in PERCENTILE_MAP:
            r = ee.Reducer.percentile([PERCENTILE_MAP[stat]], outputNames=[stat])
        else:
            continue
        reducer = r if reducer is None else reducer.combine(r, sharedInputs=True)
    return reducer


def _extract_points(ee_obj, locs_df, reducer, scale):
    """Extract values for points. locs_df must have _lat, _lon, _loc_idx columns."""
    import ee
    features = [
        ee.Feature(ee.Geometry.Point([float(r['_lon']), float(r['_lat'])]), {'_idx': int(r['_loc_idx'])})
        for _, r in locs_df.iterrows()
    ]
    result = ee.FeatureCollection(features).map(
        lambda f: f.set(ee_obj.reduceRegion(reducer=reducer, geometry=f.geometry(), scale=scale, bestEffort=True))
    )
    info = result.getInfo()
    out = {}
    for feat in info.get('features', []):
        props = feat.get('properties', {})
        idx = props.pop('_idx', None)
        if idx is not None:
            out[idx] = props
    return out


def _extract_polygons(ee_obj, gdf_batch, reducer, scale):
    """Extract values for polygons."""
    import ee
    features = [
        ee.Feature(ee.Geometry(row.geometry.__geo_interface__), {'_idx': int(i)})
        for i, row in gdf_batch.iterrows()
    ]
    result = ee.FeatureCollection(features).map(
        lambda f: f.set(ee_obj.reduceRegion(reducer=reducer, geometry=f.geometry(), scale=scale, bestEffort=True))
    )
    info = result.getInfo()
    out = {}
    for feat in info.get('features', []):
        props = feat.get('properties', {})
        idx = props.pop('_idx', None)
        if idx is not None:
            out[idx] = props
    return out


def _effective_bands(ds_info):
    """Return the effective (possibly renamed) band list for a dataset."""
    return ds_info.get('band_rename', ds_info['band'])


def _col_names(ds_info, ds_stats):
    """Return list of output column names for a dataset."""
    band = _effective_bands(ds_info)
    out_col = ds_info['output_col']
    cols = []
    if isinstance(band, list):
        for b in band:
            for st in ds_stats:
                cols.append(f"{b}_{st}")
    else:
        for st in ds_stats:
            cols.append(f"{out_col}_{st}" if len(ds_stats) > 1 else out_col)
    return cols


def _parse_vals(props, ds_info, ds_stats):
    """Parse EE result properties into a dict of {col_name: value}.

    EE reduceRegion key format:
      - Single reducer:   {band: value}          e.g. {'dem': 42.5}
      - Combined reducer: {band_stat: value}      e.g. {'dem_mean': 42.5, 'dem_min': 40.0}
      - Percentile:       {band_pNN: value}       e.g. {'dem_p50': 41.0}
    """
    band = _effective_bands(ds_info)
    out_col = ds_info['output_col']
    multi = len(ds_stats) > 1
    result = {}
    if isinstance(band, list):
        for b in band:
            for st in ds_stats:
                ee_key = f"{b}_{st}" if multi else b
                result[f"{b}_{st}"] = props.get(ee_key) if props else None
    else:
        for st in ds_stats:
            col = f"{out_col}_{st}" if multi else out_col
            ee_key = f"{band}_{st}" if multi else band
            result[col] = props.get(ee_key) if props else None
    return result


def run_extraction(job, update_progress_fn=None):
    import ee
    import geopandas as gpd

    job_id = job['id']
    datasets_list = json.loads(job['datasets']) if isinstance(job['datasets'], str) else job['datasets']
    stats_requested = json.loads(job['stats_requested']) if isinstance(job['stats_requested'], str) else job['stats_requested']
    input_filename = job['input_filename']
    output_format = job.get('output_format', 'csv')
    start_date = job.get('start_date')
    end_date = job.get('end_date')

    output_ext = 'csv' if output_format == 'csv' else 'parquet'
    output_path = os.path.join(JOBS_DIR, f'{job_id}_output.{output_ext}')
    checkpoint_path = os.path.join(JOBS_DIR, f'{job_id}_checkpoint.parquet')

    # Init EE via service account
    SA_KEY = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'palsearth-sa-key.json')
    try:
        creds = ee.ServiceAccountCredentials('palsearth@ee-rutendosibanda18.iam.gserviceaccount.com', SA_KEY)
        ee.Initialize(credentials=creds, project='ee-rutendosibanda18')
    except Exception as e:
        raise RuntimeError(f"Earth Engine initialisation failed: {e}")

    if update_progress_fn:
        update_progress_fn(2, status='running')

    # Load input — auto-detect geometry type
    is_shapefile = input_filename.endswith('.shp')
    if is_shapefile:
        gdf = gpd.read_file(input_filename)
        geom_type = gdf.geometry.geom_type.iloc[0]
        is_points = geom_type in ('Point', 'MultiPoint')
        attr_cols = [c for c in gdf.columns if c != 'geometry']
        locs = gdf[attr_cols].copy()
        locs['_loc_idx'] = range(len(locs))
        if is_points:
            locs['_lon'] = gdf.geometry.x
            locs['_lat'] = gdf.geometry.y
        else:
            locs['_geometry'] = gdf.geometry
    else:
        df = pd.read_csv(input_filename)
        lat_col, lon_col = _detect_lat_lon(df)
        if not lat_col or not lon_col:
            raise ValueError("Could not detect latitude/longitude columns.")
        is_points = True
        attr_cols = [c for c in df.columns]
        locs = df.copy()
        locs['_loc_idx'] = range(len(locs))
        locs['_lon'] = df[lon_col]
        locs['_lat'] = df[lat_col]

    n_locs = len(locs)

    from core.datasets import DATASETS
    requested_ds = {name: DATASETS[name] for name in datasets_list if name in DATASETS}
    timeseries_ds = {n: d for n, d in requested_ds.items() if d['type'] == 'timeseries'}
    static_ds = {n: d for n, d in requested_ds.items() if d['type'] in ('static', 'static_fc', 'static_mode')}

    BATCH = 50
    total_steps = max(1, len(timeseries_ds) * (
        len(pd.date_range(start_date, end_date)) if start_date and end_date else 1
    ) + len(static_ds))
    step = 0

    # ── Build base wide dataframe ──────────────────────────────────────────
    # If timeseries: cross-join locations × dates
    if timeseries_ds and start_date and end_date:
        date_range = pd.date_range(start=start_date, end=end_date, freq='D')
        dates_df = pd.DataFrame({'date': [d.strftime('%Y-%m-%d') for d in date_range]})
        locs_base = locs[[c for c in locs.columns if not c.startswith('_geometry')]].copy()
        locs_base['_xkey'] = 1
        dates_df['_xkey'] = 1
        wide = locs_base.merge(dates_df, on='_xkey').drop(columns='_xkey')
    else:
        wide = locs[[c for c in locs.columns if not c.startswith('_geometry')]].copy()
        date_range = []

    # ── Timeseries extraction ──────────────────────────────────────────────
    for ds_name, ds_info in timeseries_ds.items():
        coll_id = ds_info['collection']
        band = ds_info['band']
        scale = ds_info['scale']
        ds_stats = [s for s in stats_requested if s in (ds_info.get('stats', []) + list(PERCENTILE_MAP.keys()) + ['mean', 'min', 'max'])] or ['mean']
        reducer = _build_reducer(ds_stats)
        col_names = _col_names(ds_info, ds_stats)

        # Pre-fill columns with NaN
        for col in col_names:
            wide[col] = np.nan

        for date in date_range:
            date_str = date.strftime('%Y-%m-%d')
            next_str = (date + timedelta(days=1)).strftime('%Y-%m-%d')

            try:
                bands = band if isinstance(band, list) else [band]
                ee_img = ee.ImageCollection(coll_id).filterDate(date_str, next_str).select(bands).mean()
                if 'band_rename' in ds_info:
                    ee_img = ee_img.rename(ds_info['band_rename'])

                # Check if image has bands (handles empty collections)
                n_bands = ee_img.bandNames().size().getInfo()
                if n_bands == 0:
                    step += 1
                    if update_progress_fn:
                        update_progress_fn(min(95, int((step / total_steps) * 90) + 2))
                    continue

                date_mask = wide['date'] == date_str

                for batch_start in range(0, n_locs, BATCH):
                    batch_locs = locs.iloc[batch_start:batch_start + BATCH]
                    try:
                        if is_points:
                            vals = _extract_points(ee_img, batch_locs, reducer, scale)
                        else:
                            batch_gdf = gdf.iloc[batch_start:batch_start + BATCH]
                            vals = _extract_polygons(ee_img, batch_gdf, reducer, scale)

                        for loc_idx, props in vals.items():
                            parsed = _parse_vals(props, ds_info, ds_stats)
                            loc_mask = locs['_loc_idx'] == loc_idx
                            if not loc_mask.any():
                                continue
                            row_mask = date_mask & (wide['_loc_idx'] == loc_idx)
                            for col, val in parsed.items():
                                wide.loc[row_mask, col] = val
                    except Exception as e:
                        print(f"[extractor] Batch error {ds_name} {date_str}: {e}")

            except Exception as e:
                print(f"[extractor] Day error {ds_name} {date_str}: {e}")

            step += 1
            if update_progress_fn:
                update_progress_fn(min(95, int((step / total_steps) * 90) + 2))

            # Checkpoint
            if step % 10 == 0:
                try:
                    wide.to_parquet(checkpoint_path, index=False)
                except Exception:
                    pass

    # ── Static extraction ──────────────────────────────────────────────────
    for ds_name, ds_info in static_ds.items():
        coll_id = ds_info['collection']
        band = ds_info['band']
        scale = ds_info['scale']

        # static_mode always uses mode reducer regardless of user stat selection
        if ds_info['type'] == 'static_mode':
            ds_stats = ['mode']
            reducer = ee.Reducer.mode()
        else:
            ds_stats = [s for s in stats_requested if s in (ds_info.get('stats', []) + list(PERCENTILE_MAP.keys()) + ['mean', 'min', 'max'])] or ['mean']
            reducer = _build_reducer(ds_stats)

        col_names = _col_names(ds_info, ds_stats)

        for col in col_names:
            wide[col] = np.nan

        try:
            if ds_info['type'] == 'static_fc':
                ee_img = ee.ImageCollection(coll_id).mosaic().select(band)
            else:
                ee_img = ee.Image(coll_id).select(band)

            for batch_start in range(0, n_locs, BATCH):
                batch_locs = locs.iloc[batch_start:batch_start + BATCH]
                try:
                    if is_points:
                        vals = _extract_points(ee_img, batch_locs, reducer, scale)
                    else:
                        batch_gdf = gdf.iloc[batch_start:batch_start + BATCH]
                        vals = _extract_polygons(ee_img, batch_gdf, reducer, scale)

                    for loc_idx, props in vals.items():
                        parsed = _parse_vals(props, ds_info, ds_stats)
                        loc_mask = wide['_loc_idx'] == loc_idx
                        for col, val in parsed.items():
                            wide.loc[loc_mask, col] = val
                except Exception as e:
                    print(f"[extractor] Static batch error {ds_name}: {e}")

        except Exception as e:
            print(f"[extractor] Static error {ds_name}: {e}")

        step += 1
        if update_progress_fn:
            update_progress_fn(min(97, int((step / total_steps) * 90) + 2))

    # ── Post-processing: apply classification labels ───────────────────────
    for ds_name, ds_info in static_ds.items():
        clf = ds_info.get('classify')
        if not clf:
            continue
        src = clf['source_col']
        out = clf['output_col']
        if src not in wide.columns:
            continue
        def _apply_clf(val, ranges=clf['ranges'], default=clf.get('default')):
            if pd.isna(val):
                return None
            code = int(val)
            for lo, hi, label in ranges:
                if lo <= code <= hi:
                    return label
            return default
        wide[out] = wide[src].apply(_apply_clf)

    # ── Clean up internal columns and save ────────────────────────────────
    drop_cols = [c for c in wide.columns if c.startswith('_')]
    wide = wide.drop(columns=drop_cols, errors='ignore')

    # Put date first if present
    if 'date' in wide.columns:
        cols = ['date'] + [c for c in wide.columns if c != 'date']
        wide = wide[cols]

    if wide.empty:
        raise ValueError("No data was extracted.")

    if output_format == 'parquet':
        wide.to_parquet(output_path, index=False)
    else:
        wide.to_csv(output_path, index=False)

    if os.path.exists(checkpoint_path):
        try:
            os.remove(checkpoint_path)
        except Exception:
            pass

    if update_progress_fn:
        update_progress_fn(100, status='complete')

    return output_path
