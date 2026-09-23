#!/usr/bin/env python3
"""Exact numerical comparison of CICE baseline directories; requires numpy/netCDF4.

Checks all history/restart variables in bounded row chunks, matching masks,
finite unmasked values, restart dates/counters and occupied-category FSD sums.
Does not establish split-run restart reproducibility or scientific validity.
"""
import argparse
import hashlib
from pathlib import Path

import numpy as np
from netCDF4 import Dataset


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.digest()


def chunks(shape):
    """Slice the penultimate (normally latitude) axis to bound memory."""
    if len(shape) < 2:
        yield (...,)
        return
    for start in range(0, shape[-2], 32):
        yield (slice(None),) * (len(shape) - 2) + (slice(start, start + 32), slice(None))


def finite(data, label):
    values = np.ma.asarray(data).compressed()
    if np.issubdtype(values.dtype, np.number):
        require(np.isfinite(values).all(), f'{label}: nonfinite unmasked values')


def compare_nc(left, right):
    with Dataset(left) as a, Dataset(right) as b:
        require({k: len(v) for k, v in a.dimensions.items()} ==
                {k: len(v) for k, v in b.dimensions.items()}, f'{left.name}: dimensions differ')
        require(a.variables.keys() == b.variables.keys(), f'{left.name}: variable sets differ')
        for attr in ('myear', 'nyr', 'mmonth', 'month', 'mday', 'msec', 'sec', 'istep1'):
            require((attr in a.ncattrs()) == (attr in b.ncattrs()), f'{left.name}: {attr} missing')
            if attr in a.ncattrs():
                require(np.array_equal(a.getncattr(attr), b.getncattr(attr)),
                        f'{left.name}: {attr} differs')
        for name, va in a.variables.items():
            vb = b[name]
            label = f'{left.name}:{name}'
            require(va.dimensions == vb.dimensions and va.dtype == vb.dtype,
                    f'{label}: dimensions/type differ')
            for attr in ('units', 'calendar', '_FillValue', 'missing_value', 'scale_factor', 'add_offset'):
                require((attr in va.ncattrs()) == (attr in vb.ncattrs()), f'{label}: {attr} missing')
                if attr in va.ncattrs():
                    x, y = va.getncattr(attr), vb.getncattr(attr)
                    require(np.array_equal(x, y), f'{label}: {attr} differs')
            for key in chunks(va.shape):
                x, y = np.ma.asarray(va[key]), np.ma.asarray(vb[key])
                finite(x, label + ' left')
                finite(y, label + ' right')
                require(np.array_equal(np.ma.getmaskarray(x), np.ma.getmaskarray(y)),
                        f'{label}: masks differ at {key}')
                require(np.array_equal(x.compressed(), y.compressed()),
                        f'{label}: numerical values differ at {key}')


def check_fsd(path):
    with Dataset(path) as ds:
        require('aicen' in ds.variables, f'{path}: missing aicen')
        names = [f'fsd{k:03d}' for k in range(1, 13)]
        require(all(n in ds.variables for n in names), f'{path}: missing FSD bins')
        area = ds['aicen']
        require(area.dimensions == ('ncat', 'nj', 'ni'), f'{path}: unexpected aicen dimensions')
        for n in names:
            require(ds[n].dimensions == area.dimensions, f'{path}:{n}: unexpected dimensions')
        for key in chunks(area.shape):
            a = np.ma.asarray(area[key])
            occupied = (~np.ma.getmaskarray(a)) & (a.filled(0) > 1e-12)
            total = np.zeros(a.shape)
            for n in names:
                f = np.ma.asarray(ds[n][key])
                require(not np.any(np.ma.getmaskarray(f) & occupied), f'{path}:{n}: masked occupied bin')
                vals = f.filled(np.nan)[occupied]
                require(np.isfinite(vals).all(), f'{path}:{n}: nonfinite occupied bin')
                require(np.all((vals >= -1e-12) & (vals <= 1 + 1e-12)), f'{path}:{n}: outside [0,1]')
                total[occupied] += vals
            require(np.all(np.abs(total[occupied] - 1) <= 1e-10),
                    f'{path}: occupied-category FSD sum differs from 1 at {key}')


def compare_runs(left, right, same_executable=False):
    for run in (left, right):
        require((run / 'mpi_exit_status.txt').read_text().strip() == '0', f'{run}: MPI did not succeed')
    restart = Path('input_restart/iced.2000-09-01-00000.nc')
    require(digest(left / restart) == digest(right / restart), 'Input restart checksums differ')
    if same_executable:
        require(digest(left / 'cice') == digest(right / 'cice'), 'Executable checksums differ')
    for folder in ('history', 'restart'):
        files = sorted(p.name for p in (left / folder).glob('*.nc'))
        require(files and files == sorted(p.name for p in (right / folder).glob('*.nc')),
                f'{folder}: missing or different output file sets')
        for name in files:
            compare_nc(left / folder / name, right / folder / name)
            if folder == 'restart':
                for run in (left, right):
                    check_fsd(run / folder / name)
            print(f'PASS {folder}/{name}', flush=True)
    print('PASS: exact numerical equality, matching masks, finite unmasked fields and restart FSD checks')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('left', type=Path)
    parser.add_argument('right', type=Path)
    parser.add_argument('--same-executable', action='store_true', help='require identical executable SHA256 (off/on pair)')
    args = parser.parse_args()
    try:
        compare_runs(args.left, args.right, args.same_executable)
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(1, f'FAIL: {exc}\n')


if __name__ == '__main__':
    main()
