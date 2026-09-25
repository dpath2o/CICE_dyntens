#!/usr/bin/env python3
"""Check prescribed box coefficients/loading and optionally another decomposition.
Requires numpy and netCDF4. Does not certify yielding or restart reproducibility.
"""
import argparse
from pathlib import Path
import numpy as np
from netCDF4 import Dataset


def field(ds, name):
    if name not in ds.variables:
        raise ValueError(f'missing field {name}')
    x = np.ma.asarray(ds[name][:])
    if x.ndim == 3 and x.shape[0] == 1:
        x = x[0]
    if x.ndim != 2:
        raise ValueError(f'{name}: expected one 2D record, got {x.shape}')
    return x


def check_file(path, args):
    with Dataset(path) as ds:
        mask = field(ds, 'tmask')
        ocean = ~np.ma.getmaskarray(mask) & np.isfinite(mask.data) & (mask.data > 0.5)
        if not ocean.any():
            raise ValueError('no active ocean cells')
        g = field(ds, 'dyntens_g')
        k = field(ds, 'ktens_eff')
        ig = np.broadcast_to(np.arange(1, mask.shape[1]+1), mask.shape)
        expected = np.full(mask.shape, args.background)
        if args.mode == 'box_band':
            expected[(ig >= args.ilo) & (ig <= args.ihi)] = args.band
        for name, x, want in [('dyntens_g', g, expected), ('ktens_eff', k, args.ktens*expected)]:
            if np.any(np.ma.getmaskarray(x)[ocean]):
                raise ValueError(f'{name}: masked ocean values')
            if not np.allclose(x.data[ocean], want[ocean], atol=1e-12, rtol=0):
                raise ValueError(f'{name}: incorrect spatial coefficient; max error '
                                 f'{np.max(np.abs(x.data[ocean]-want[ocean]))}')
        for name, v in ds.variables.items():
            x = np.ma.asarray(v[:])
            if np.issubdtype(x.dtype, np.number) and not np.isfinite(x.compressed()).all():
                raise ValueError(f'{name}: nonfinite unmasked values')
        if args.tensile:
            if mask.shape[1] % 2:
                raise ValueError('tensile box must have even width')
            want = np.where(ig <= mask.shape[1]//2, -5., 5.)
            for name, target in [('uatm', want), ('vatm', np.zeros(mask.shape))]:
                x = field(ds, name)
                if np.any(np.ma.getmaskarray(x)[ocean]) or not np.allclose(x.data[ocean], target[ocean], atol=1e-12, rtol=0):
                    raise ValueError(f'{name}: incorrect prescribed wind')
        if 'divu' in ds.variables:
            d = field(ds, 'divu')
            centre = ocean & (ig >= mask.shape[1]//2) & (ig <= mask.shape[1]//2+1)
            vals = d[centre].compressed()
            print(f'  central divu [{ds["divu"].units}]: min={vals.min():.8g}, max={vals.max():.8g}')


def compare_runs(run, reference, atol=0., rtol=0.):
    count = 0
    for folder in ['history', 'restart']:
        files = sorted((run/folder).glob('*.nc'))
        refs = sorted((reference/folder).glob('*.nc'))
        if not files or [p.name for p in files] != [p.name for p in refs]:
            raise ValueError(f'{folder}: missing or different file inventories')
        for p, q in zip(files, refs):
            with Dataset(p) as a, Dataset(q) as b:
                if set(a.variables) != set(b.variables):
                    raise ValueError(f'{p.name}: variable inventories differ')
                if {k: len(v) for k,v in a.dimensions.items()} != {k: len(v) for k,v in b.dimensions.items()}:
                    raise ValueError(f'{p.name}: dimensions differ')
                for name in a.variables:
                    if a[name].dimensions != b[name].dimensions:
                        raise ValueError(f'{p.name}:{name}: dimension order differs')
                    x, y = np.ma.asarray(a[name][:]), np.ma.asarray(b[name][:])
                    if not np.array_equal(np.ma.getmaskarray(x), np.ma.getmaskarray(y)):
                        raise ValueError(f'{p.name}:{name}: masks differ')
                    x, y = x.compressed(), y.compressed()
                    if np.issubdtype(x.dtype, np.number):
                        ok = np.isfinite(x).all() and np.isfinite(y).all() and np.allclose(x,y,atol=atol,rtol=rtol)
                    else:
                        ok = np.array_equal(x,y)
                    if not ok:
                        raise ValueError(f'{p.name}:{name}: values differ')
            count += 1
    print(f'PASS reference comparison: {count} file pairs; atol={atol}, rtol={rtol}')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('run', type=Path)
    p.add_argument('--mode', choices=['constant','box_band'], required=True)
    p.add_argument('--ktens', type=float, required=True)
    p.add_argument('--background', type=float, default=1.)
    p.add_argument('--band', type=float, default=.5)
    p.add_argument('--ilo', type=int, default=6)
    p.add_argument('--ihi', type=int, default=7)
    p.add_argument('--tensile', action='store_true')
    p.add_argument('--reference-run', type=Path)
    p.add_argument('--atol', type=float, default=0.)
    p.add_argument('--rtol', type=float, default=0.)
    args = p.parse_args()
    try:
        files = sorted((args.run/'history').glob('*.nc'))
        if not files:
            raise ValueError('no history NetCDF files')
        for path in files:
            print(path.name)
            check_file(path, args)
        print(f'PASS prescribed fields/finite history: {len(files)} files')
        if args.reference_run:
            compare_runs(args.run, args.reference_run, args.atol, args.rtol)
    except (ValueError, OSError, KeyError) as e:
        p.exit(1, f'FAIL: {e}\n')


if __name__ == '__main__':
    main()
