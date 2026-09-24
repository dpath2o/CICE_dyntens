#!/usr/bin/env python3
"""Read-only CICE restart FSD diagnosis using tmask/TLAT/tarea from matching history."""
import argparse
from pathlib import Path
import numpy as np
from netCDF4 import Dataset

THRESHOLDS = (1e-8, 1e-6, 1e-4, 1e-3, 1e-2)

CLASSES = ('normalised', 'zero', 'other_sum', 'invalid_bins')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def field2d(ds, name):
    v = ds[name]
    require(v.dimensions == ('nj', 'ni'), f'{name}: expected (nj,ni), got {v.dimensions}')
    return np.ma.asarray(v[:], dtype=float).filled(np.nan)


def mask_summary(ds):
    """Describe decoded values and metadata without guessing mask semantics."""
    v = ds['tmask']
    a = np.ma.asarray(v[:])
    vals = a.compressed()
    finite = vals[np.isfinite(vals)]
    unique, counts = np.unique(finite, return_counts=True)
    order = np.argsort(-counts)[:12]
    lines = [f'tmask dtype={v.dtype}; dimensions={v.dimensions}; shape={v.shape}',
             'attributes=' + repr({n: v.getncattr(n) for n in v.ncattrs()}),
             f'masked={np.count_nonzero(np.ma.getmaskarray(a))}; '
             f'unmasked_nonfinite={np.count_nonzero(~np.isfinite(vals))}; '
             f'distinct_finite={len(unique)}',
             'Most frequent decoded values (value: count): ' +
             ', '.join(f'{unique[i]!r}: {counts[i]}' for i in order)]
    unexpected = (unique != 0) & (unique != 1)
    lines.append('Nonbinary decoded values (first 12, value: count): ' +
                 ', '.join(f'{x!r}: {n}' for x, n in zip(unique[unexpected][:12], counts[unexpected][:12])))
    if finite.size:
        lines.append(f'Decoded finite range: {finite.min()!r} to {finite.max()!r}')
    return '\n'.join(lines)


def read_grid(path):
    with Dataset(path) as ds:
        mask, lat, area = (field2d(ds, n) for n in ('tmask', 'TLAT', 'tarea'))
        require(mask.shape == lat.shape == area.shape, 'Grid shapes differ')
        require(np.all(np.isnan(mask) | (np.isfinite(mask) & (mask >= 0) & (mask <= 1))),
                'tmask contains values outside [0,1]. No cells have been reclassified.\n' + mask_summary(ds))
        # History tmask stores hm; ice_grid constructs the logical mask as hm > p5.
        # Preserve missing values as unknown, rather than interpreting them as land.
        mask = np.where(np.isnan(mask), np.nan, (mask > 0.5).astype(float))
        units = str(getattr(ds['TLAT'], 'units', '')).lower().strip()
        if units in ('radian', 'radians', 'rad'):
            lat = np.rad2deg(lat)
        else:
            require(units in ('degrees_north', 'degree_north', 'degrees', 'degree', 'degrees north'),
                    f'Unrecognised TLAT units: {units!r}')
        units = str(getattr(ds['tarea'], 'units', '')).lower().replace(' ', '')
        factors = {'m2': 1e-6, 'm^2': 1e-6, 'm**2': 1e-6,
                   'cm2': 1e-10, 'cm^2': 1e-10, 'cm**2': 1e-10,
                   'km2': 1., 'km^2': 1., 'km**2': 1.}
        require(units in factors, f'Unrecognised tarea units: {units!r}')
        area *= factors[units]
        ocean = mask == 1
        require(np.any(ocean), 'No ocean cells in tmask')
        require(np.all(np.isfinite(lat[ocean]) & (np.abs(lat[ocean]) <= 90)), 'Invalid ocean latitude')
        require(np.all(np.isfinite(area[ocean]) & (area[ocean] > 0)), 'Invalid ocean area')
    return mask, lat, area


def read_longitude(path, mask):
    with Dataset(path) as ds:
        lon = field2d(ds, 'TLON')
        units = str(getattr(ds['TLON'], 'units', '')).lower().strip()
        if units in ('radian', 'radians', 'rad'):
            lon = np.rad2deg(lon)
        else:
            require(units in ('degrees_east', 'degree_east', 'degrees', 'degree', 'degrees east'),
                    f'Unrecognised TLON units: {units!r}')
        require(lon.shape == mask.shape, 'Longitude/grid dimensions differ')
        require(np.all(np.isfinite(lon[mask == 1])), 'Missing ocean longitude')
    return (lon + 180) % 360 - 180


def diagnose(path, grid, occupied_min=1e-12, sum_tol=1e-10, bin_tol=1e-12, detail=None, lon=None):
    mask, lat, area = grid
    regions = {'global': mask == 1, 'SH': (mask == 1) & (lat < 0),
               'NH': (mask == 1) & (lat >= 0)}
    stats = {r: {c: dict(count=0, area=0., max_a=0., min_sum=np.inf,
                         max_sum=-np.inf, substantial=0) for c in CLASSES} for r in regions}
    affected_cells = dict.fromkeys(regions, 0)
    excluded = {'inactive_T': 0, 'unknown_mask': 0}
    samples = {c: [] for c in CLASSES if c != 'normalised'}
    if detail is not None:
        require(lon is not None and lon.shape == mask.shape, 'Detailed report requires matching longitude')
        detail.update({r: dict(thresholds={t: dict(count=0, cells=0, area=0., deficit=0., surplus=0.)
                                          for t in THRESHOLDS}, worst=[]) for r in regions})
    with Dataset(path) as ds:
        a_var = ds['aicen']
        require(a_var.dimensions == ('ncat', 'nj', 'ni'), 'Unexpected aicen dimensions')
        require(a_var.shape[1:] == mask.shape, 'Restart/history grid dimensions differ')
        bins = [ds[f'fsd{k:03d}'] for k in range(1, 13)]
        for v in bins:
            require(v.dimensions == a_var.dimensions and v.shape == a_var.shape,
                    f'{v.name}: dimensions differ from aicen')
        for start in range(0, mask.shape[0], 32):
            sl = slice(start, start + 32)
            a = np.ma.asarray(a_var[:, sl, :], dtype=float).filled(np.nan)
            wet = (mask[sl] == 1)[None, :, :]
            require(not np.any(wet & (~np.isfinite(a) | (a < -bin_tol) | (a > 1 + bin_tol))),
                    f'{path}: invalid ocean aicen near row {start}')
            occupied = np.isfinite(a) & (a > occupied_min)
            excluded['inactive_T'] += int(np.count_nonzero(occupied & (mask[sl] == 0)[None]))
            excluded['unknown_mask'] += int(np.count_nonzero(occupied & ~np.isfinite(mask[sl])[None]))
            total = np.zeros_like(a)
            invalid = np.zeros(a.shape, dtype=bool)
            zero = np.ones(a.shape, dtype=bool)
            for v in bins:
                f = np.ma.asarray(v[:, sl, :], dtype=float).filled(np.nan)
                invalid |= ~np.isfinite(f) | (f < -bin_tol) | (f > 1 + bin_tol)
                zero &= np.abs(f) <= bin_tol
                total += f
            normal = ~invalid & (np.abs(total - 1) <= sum_tol)
            labels = {'normalised': normal, 'zero': ~invalid & zero,
                      'other_sum': ~invalid & ~zero & ~normal, 'invalid_bins': invalid}
            for region, domain in regions.items():
                active = occupied & domain[sl][None]
                affected_cells[region] += int(np.count_nonzero(np.any(active & ~normal, axis=0)))
                weights = a * np.where(domain[sl], area[sl], 0)[None]
                if detail is not None:
                    valid = active & ~invalid
                    error = np.abs(total - 1)
                    for threshold, record in detail[region]['thresholds'].items():
                        selected = valid & (error > threshold)
                        record['count'] += int(np.count_nonzero(selected))
                        record['cells'] += int(np.count_nonzero(np.any(selected, axis=0)))
                        record['area'] += float(weights[selected].sum())
                        record['deficit'] += float(weights[selected & (total < 1)].sum())
                        record['surplus'] += float(weights[selected & (total > 1)].sum())
                    # Retain ten worst category entries per region across all chunks.
                    candidates = np.flatnonzero(valid & (error > sum_tol))
                    if candidates.size:
                        scores = error.ravel()[candidates]
                        order = np.argsort(-scores, kind='stable')[:10]
                        for flat in candidates[order]:
                            n, j, i = np.unravel_index(flat, a.shape)
                            detail[region]['worst'].append(dict(
                                ncat=int(n+1), j=int(start+j+1), i=int(i+1),
                                lat=float(lat[start+j,i]), lon=float(lon[start+j,i]),
                                aicen=float(a[n,j,i]), ice_km2=float(weights[n,j,i]),
                                fsd_sum=float(total[n,j,i]), signed_error=float(total[n,j,i]-1),
                                abs_error=float(error[n,j,i])))
                        detail[region]['worst'].sort(key=lambda x: (-x['abs_error'], x['ncat'], x['j'], x['i']))
                        del detail[region]['worst'][10:]
                for label, selected in labels.items():
                    selected = selected & active
                    s = stats[region][label]
                    s['count'] += int(np.count_nonzero(selected))
                    s['area'] += float(np.sum(weights[selected]))
                    s['substantial'] += int(np.count_nonzero(selected & (a > 1e-6)))
                    if selected.any():
                        s['max_a'] = max(s['max_a'], float(a[selected].max()))
                        vals = total[selected & np.isfinite(total)]
                        if vals.size:
                            s['min_sum'] = min(s['min_sum'], float(vals.min()))
                            s['max_sum'] = max(s['max_sum'], float(vals.max()))
                    if region == 'global' and label in samples:
                        for n, j, i in np.argwhere(selected)[:max(0, 3-len(samples[label]))]:
                            samples[label].append(dict(ncat=int(n+1), j=int(start+j+1), i=int(i+1),
                                lat=float(lat[start+j, i]), aicen=float(a[n,j,i]), fsd_sum=float(total[n,j,i])))
    return stats, affected_cells, excluded, samples


def report(path, result, detail=None):
    stats, cells, excluded, samples = result
    print(f'\nFILE {path}', flush=True)
    print(f'Excluded occupied category entries: {excluded}')
    print('region class          categories   ice_km2       %ice    max_aicen  sum_min   sum_max   count_a>1e-6')
    for region, classes in stats.items():
        denominator = sum(s['area'] for s in classes.values())
        for label, s in classes.items():
            pct = 100*s['area']/denominator if denominator else 0.
            lo = s['min_sum'] if np.isfinite(s['min_sum']) else float('nan')
            hi = s['max_sum'] if np.isfinite(s['max_sum']) else float('nan')
            print(f'{region:6} {label:14} {s["count"]:10d} {s["area"]:12.5g} {pct:8.4f} '
                  f'{s["max_a"]:10.5g} {lo:9.4g} {hi:9.4g} {s["substantial"]:12d}')
        print(f'  {region}: affected ocean grid cells={cells[region]}; total ice area={denominator:.8g} km2')
    for label, entries in samples.items():
        for entry in entries:
            print(f'  SAMPLE {label} (1-based indices): {entry}')


    if detail is not None:
        print('\nCUMULATIVE ERROR THRESHOLDS: abs(sum(fsd)-1) > threshold; valid bins only')
        print('region threshold categories cells ice_km2 %all_ice deficit_ice_km2 surplus_ice_km2')
        for region, records in detail.items():
            denominator = sum(v['area'] for v in stats[region].values())
            for threshold, v in records['thresholds'].items():
                pct = 100*v['area']/denominator if denominator else 0.
                print(f"{region:6} {threshold:.0e} {v['count']:10d} {v['cells']:8d} "
                      f"{v['area']:.9g} {pct:.9g} {v['deficit']:.9g} {v['surplus']:.9g}")
        print('\nWORST TEN PER HEMISPHERE: valid-bin occupied categories; longitude -180..180; indices 1-based')
        for region in ('SH', 'NH'):
            for v in detail[region]['worst']:
                print(f"WORST {region} cat={v['ncat']} j={v['j']} i={v['i']} "
                      f"lat={v['lat']:.6f} lon={v['lon']:.6f} aicen={v['aicen']:.12g} "
                      f"ice_km2={v['ice_km2']:.9g} sum={v['fsd_sum']:.15g} "
                      f"signed_error={v['signed_error']:+.9e}")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--grid-history', type=Path, required=True, help='same-run history containing tmask, TLAT, tarea')
    p.add_argument('--inspect-grid', action='store_true', help='print mask values/metadata only; no restart files needed')
    p.add_argument('restarts', type=Path, nargs='*')
    args = p.parse_args()
    try:
        if args.inspect_grid:
            with Dataset(args.grid_history) as ds:
                print(mask_summary(ds))
            return
        if not args.restarts:
            p.error('provide at least one restart, or use --inspect-grid')
        grid = read_grid(args.grid_history)
        print(f'Grid: {args.grid_history}\nOccupancy: aicen>1e-12; sum tolerance=1e-10; bin tolerance=1e-12')
        print('Mask rule: finite hm > 0.5 is active ocean; hm <= 0.5 is inactive; fill remains unknown.')
        print('Ice area = sum(aicen*tarea) over occupied ocean categories; NH includes the equator.')
        lon = read_longitude(args.grid_history, grid[0])
        for path in args.restarts:
            detail = {}
            result = diagnose(path, grid, detail=detail, lon=lon)
            report(path, result, detail)
    except (ValueError, OSError, KeyError) as exc:
        p.exit(1, f'ERROR: {exc}\n')


if __name__ == '__main__':
    main()
