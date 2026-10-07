"""Small-memory regional tables for the final G0 daily mean; no plotting imports."""
import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np
from netCDF4 import Dataset, num2date

from ..core.reporting import sha256


def read2d(ds, name, start, stop):
    var = ds[name]
    if var.dimensions[-2:] != ('nj', 'ni'):
        raise ValueError(f'{name}: expected nj,ni dimensions')
    if var.ndim == 2:
        value = var[start:stop, :]
    elif var.ndim == 3 and var.dimensions[0] == 'time' and var.shape[0] == 1:
        value = var[0, start:stop, :]
    else:
        raise ValueError(f'{name}: expected one daily record')
    return np.ma.asarray(value, dtype=float)


def factor(units, kind):
    units = units.lower().strip().replace(' ', '')
    allowed = {'area': {'m2': 1., 'm^2': 1., 'm**2': 1., 'km2': 1e6, 'km^2': 1e6,
                        'cm2': 1e-4, 'cm^2': 1e-4},
               'latitude': {'degrees_north': 1., 'degrees_n': 1., 'degree_north': 1.,
                            'degrees': 1., 'degree': 1., 'rad': 180/math.pi, 'radians': 180/math.pi},
               'fraction': {'1': 1., 'dimensionless': 1., '%': .01, 'percent': .01},
               'length': {'m': 1., 'cm': .01}}
    if units not in allowed[kind]:
        raise ValueError(f'unrecognised {kind} units: {units!r}')
    return allowed[kind][units]


def time_description(ds):
    t = ds['time']
    if t.size != 1:
        raise ValueError('expected one daily mean')
    calendar = getattr(t, 'calendar', 'standard')
    result = dict(units=t.units, calendar=calendar, value=float(t[0]),
                  date=str(num2date(t[0], t.units, calendar)))
    bounds = getattr(t, 'bounds', '')
    if bounds:
        values = np.asarray(ds[bounds][:]).reshape(-1)
        if len(values) != 2:
            raise ValueError('expected daily time bounds')
        result['bounds'] = values.tolist()
        result['interval'] = [str(num2date(v, t.units, calendar)) for v in values]
    return result


class Moments:
    def __init__(self):
        self.w = self.wx = self.wx2 = 0.
        self.minimum, self.maximum = math.inf, -math.inf
        self.count = 0

    def add(self, x, w):
        if not len(x):
            return
        self.w += float(w.sum())
        self.wx += float(np.sum(w*x))
        self.wx2 += float(np.sum(w*x*x))
        self.minimum = min(self.minimum, float(x.min()))
        self.maximum = max(self.maximum, float(x.max()))
        self.count += len(x)

    def values(self):
        if not self.w:
            return dict(minimum=None, mean=None, maximum=None, std=None)
        mean = self.wx/self.w
        return dict(minimum=self.minimum, mean=mean, maximum=self.maximum,
                    std=math.sqrt(max(0., self.wx2/self.w-mean*mean)))


class GlobalComparisonSummary:
    """Aggregate T-cell data in latitude bands, reading at most rows x ni cells."""
    def __init__(self, off, unity, output, latitude_cutoff=0., ice_threshold=.15, rows=32):
        self.files = [Path(off), Path(unity)]
        self.output = Path(output)
        self.cutoff, self.threshold, self.rows = latitude_cutoff, ice_threshold, rows
        if not 0 <= latitude_cutoff < 90 or not 0 < ice_threshold <= 1 or rows < 1:
            raise ValueError('invalid latitude cutoff, ice threshold or chunk size')

    def run(self):
        aggregates = {r: [dict(area=0., extent=0., volume=0.) for _ in self.files]
                      for r in ('Circum-Arctic (NH)', 'Circum-Antarctic (SH)')}
        stats, differences, coverage = {}, {}, {}
        with Dataset(self.files[0]) as a, Dataset(self.files[1]) as b:
            times = [time_description(ds) for ds in (a, b)]
            if times[0] != times[1]:
                raise ValueError('daily times/bounds differ')
            shape = a['aice'].shape[-2:]
            if shape != b['aice'].shape[-2:]:
                raise ValueError('daily grids differ')
            for name in ('tarea', 'TLAT'):
                if getattr(a[name], 'units', '') != getattr(b[name], 'units', ''):
                    raise ValueError('grid units differ: '+name)
            fields = []
            skipped = []
            for name in ('strength', 'divu', 'shear', 'sig1', 'sig2', 'hs', 'Tsfc'):
                if (name in a.variables) != (name in b.variables):
                    raise ValueError('variable inventories differ: '+name)
                if name not in a.variables:
                    skipped.append(name+': not written')
                    continue
                coords = getattr(a[name], 'coordinates', '')
                if coords and 'TLAT' not in coords.split():
                    skipped.append(name+': not a T-cell field; no velocity-grid interpolation')
                    continue
                if getattr(a[name], 'units', '') != getattr(b[name], 'units', ''):
                    raise ValueError('units differ: '+name)
                fields.append(name)
            for ds in (a, b):
                for name, kind in [('tarea', 'area'), ('TLAT', 'latitude'), ('aice', 'fraction'), ('hi', 'length')]:
                    factor(ds[name].units, kind)
            for region in aggregates:
                for name in fields:
                    stats[region, name] = [Moments(), Moments()]
                    differences[region, name] = dict(max_abs=0., unequal_cells=0, masks_equal=True)
                    coverage[region, name] = [0., 0.]
            for start in range(0, shape[0], self.rows):
                stop = min(start+self.rows, shape[0])
                grids = [[read2d(ds, n, start, stop) for n in ('tmask', 'TLAT', 'tarea')] for ds in (a, b)]
                for x, y in zip(*grids):
                    if not np.ma.allequal(x, y) or not np.array_equal(np.ma.getmaskarray(x), np.ma.getmaskarray(y)):
                        raise ValueError('grid masks/coordinates/areas differ')
                mask, lat, area = grids[0]
                known = ~np.ma.getmaskarray(mask)
                if np.any(known & (~np.isfinite(mask.data) | (mask.data < 0) | (mask.data > 1))):
                    raise ValueError('invalid ocean mask')
                ocean = ~np.ma.getmaskarray(mask) & (mask.data > .5)
                for grid in (lat, area):
                    if np.any(ocean & (np.ma.getmaskarray(grid) | ~np.isfinite(grid.data))):
                        raise ValueError('invalid ocean grid data')
                lat = lat.data*factor(a['TLAT'].units, 'latitude')
                area = area.data*factor(a['tarea'].units, 'area')
                if np.any(ocean & (area <= 0)):
                    raise ValueError('nonpositive ocean area')
                core = []
                for ds in (a, b):
                    conc = read2d(ds, 'aice', start, stop)*factor(ds['aice'].units, 'fraction')
                    hi = read2d(ds, 'hi', start, stop)*factor(ds['hi'].units, 'length')
                    for value in (conc, hi):
                        if np.any(ocean & (np.ma.getmaskarray(value) | ~np.isfinite(value.data))):
                            raise ValueError('missing/nonfinite ocean ice area or volume')
                    if np.any(ocean & ((conc.data < 0) | (conc.data > 1) | (hi.data < 0))):
                        raise ValueError('ice area/volume outside physical bounds')
                    core.append((conc.data, hi.data))
                for region, selected in [('Circum-Arctic (NH)', lat > self.cutoff),
                                         ('Circum-Antarctic (SH)', lat < -self.cutoff)]:
                    wet = ocean & selected
                    for i, (conc, hi) in enumerate(core):
                        totals = aggregates[region][i]
                        totals['area'] += float(np.sum(area[wet]*conc[wet]))
                        totals['extent'] += float(np.sum(area[wet & (conc >= self.threshold)]))
                        totals['volume'] += float(np.sum(area[wet]*hi[wet]))
                for name in fields:
                    pair = [read2d(ds, name, start, stop) for ds in (a, b)]
                    for region, selected in [('Circum-Arctic (NH)', lat > self.cutoff),
                                             ('Circum-Antarctic (SH)', lat < -self.cutoff)]:
                        eligible = [ocean & selected & (conc >= self.threshold) for conc, _ in core]
                        masks = [np.ma.getmaskarray(v) for v in pair]
                        valid = []
                        for i, value in enumerate(pair):
                            if np.any(eligible[i] & ~masks[i] & ~np.isfinite(value.data)):
                                raise ValueError('nonfinite ice-covered '+name)
                            good = eligible[i] & ~masks[i]
                            valid.append(good)
                            w = area*core[i][0]
                            coverage[region, name][i] += float(np.sum(w[eligible[i]]))
                            stats[region, name][i].add(value.data[good], w[good])
                        d = differences[region, name]
                        selected = eligible[0] | eligible[1]
                        d['masks_equal'] &= bool(np.array_equal(masks[0][selected], masks[1][selected]))
                        common = valid[0] & valid[1]
                        if common.any():
                            delta = np.abs(pair[1].data[common]-pair[0].data[common])
                            d['max_abs'] = max(d['max_abs'], float(delta.max()))
                            d['unequal_cells'] += int(np.count_nonzero(delta))
            units = {n: a[n].units for n in fields}
        totals_rows, field_rows = [], []
        for region, pair in aggregates.items():
            for metric, unit, scale in [('area', 'km2', 1e-6), ('extent', 'km2', 1e-6), ('volume', 'km3', 1e-9), ('mean_ice_thickness', 'm', 1.)]:
                values = [(v['volume']/v['area'] if v['area'] else None) if metric == 'mean_ice_thickness' else v[metric]*scale for v in pair]
                totals_rows.append(dict(region=region, metric=metric, units=unit, off=values[0], unity=values[1],
                                        unity_minus_off=None if None in values else values[1]-values[0]))
            for name in fields:
                for stat in ('minimum', 'mean', 'maximum', 'std'):
                    values = [s.values()[stat] for s in stats[region, name]]
                    field_rows.append(dict(region=region, variable=name, statistic=stat, units=units[name],
                                           off=values[0], unity=values[1], unity_minus_off=None if None in values else values[1]-values[0],
                                           max_abs_cell_difference=differences[region, name]['max_abs'],
                                           unequal_cells=differences[region, name]['unequal_cells'], masks_equal=differences[region, name]['masks_equal'],
                                           off_valid_ice_area_fraction=stats[region, name][0].w/coverage[region, name][0] if coverage[region, name][0] else None,
                                           unity_valid_ice_area_fraction=stats[region, name][1].w/coverage[region, name][1] if coverage[region, name][1] else None))
        self.output.mkdir(parents=True, exist_ok=True)
        for filename, rows in [('g0-regional-totals.csv', totals_rows), ('g0-regional-fields.csv', field_rows)]:
            with (self.output/filename).open('w', newline='') as out:
                if rows:
                    writer = csv.DictWriter(out, fieldnames=list(rows[0]))
                    writer.writeheader()
                    writer.writerows(rows)
            print('WROTE', self.output/filename)
        metadata = dict(time=times[0], latitude_cutoff=self.cutoff, extent_threshold=self.threshold,
                        inputs=[dict(path=str(p.resolve()), size=p.stat().st_size, sha256=sha256(p)) for p in self.files],
                        skipped_fields=skipped, rows_per_chunk=self.rows,
                        interpretation='Final daily mean, not instantaneous final state. Regional tables supplement full G0 exact comparison.',
                        formulas=dict(area='sum(tarea*aice)', extent='sum(tarea where aice>=threshold)', volume='sum(tarea*hi)',
                                      mean_ice_thickness='total volume / total ice area', fields='ice-area-weighted moments where aice>=threshold; extrema over valid selected cells'))
        (self.output/'g0-regional-summary.json').write_text(json.dumps(metadata, indent=2, allow_nan=False)+'\n')
        return totals_rows, field_rows


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--off', type=Path, required=True)
    p.add_argument('--unity', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--latitude-cutoff', type=float, default=0.)
    p.add_argument('--ice-threshold', type=float, default=.15)
    p.add_argument('--rows', type=int, default=32)
    a = p.parse_args()
    GlobalComparisonSummary(a.off, a.unity, a.output, a.latitude_cutoff, a.ice_threshold, a.rows).run()


if __name__ == '__main__':
    main()
