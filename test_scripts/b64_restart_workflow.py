#!/usr/bin/env python3
"""Prepare and check the B6.4 diagnostic-only 5-day / 2+3-day restart test.

Reuse the accepted B6.3 executable and layout. No build or job submission here.
Requires numpy/netCDF4 for stage/analyse; prepare uses the standard library.
"""
import argparse
import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

CASES = ('dt_b64_cont', 'dt_b64_seg1', 'dt_b64_seg2')
SPLIT = '2005-01-03-00000'
FINAL = '2005-01-06-00000'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def setting(text, key):
    m = re.search(r'(?m)^\s*setenv\s+' + re.escape(key) + r'\s+(\S+)', text)
    require(m is not None, 'missing setting ' + key)
    return m[1].strip('\"\'')


def entry(text, key):
    m = re.search(r'(?mi)^\s*' + re.escape(key) + r'\s*=\s*([^!\n]+)', text)
    require(m is not None, 'missing namelist entry ' + key)
    return m[1].strip().rstrip(',').strip()


def set_entry(text, key, value):
    pattern = r'(?mi)^(\s*' + re.escape(key) + r'\s*=)[^\n]*$'
    text, count = re.subn(pattern, lambda m: m[1] + ' ' + value, text)
    require(count == 1, 'expected exactly one namelist entry ' + key)
    return text


def prepare(args):
    repo = args.repo.resolve()
    base = args.base_case.resolve()
    require(base.is_dir(), 'accepted B6.3 case missing: ' + str(base))
    settings = (base / 'cice.settings').read_text()
    oldcase = Path(setting(settings, 'ICE_CASEDIR'))
    oldrun = Path(setting(settings, 'ICE_RUNDIR'))
    require('$' not in str(oldrun), 'ICE_RUNDIR must be an explicit path')
    source_exe = oldrun / 'cice'
    require(source_exe.is_file(), 'accepted executable missing: ' + str(source_exe))
    namelist = (base / 'ice_in').read_text()
    expected = {'use_dyntens': '.false.', 'use_dyntens_diagnostics': '.true.',
                'tr_fsd': '.true.', 'restart_fsd': '.false.', 'nfsd': '12',
                'ice_ic': "'internal'", 'runtype': "'initial'", 'npt_unit': "'d'",
                'npt': '5', 'ndtd': '1', 'year_init': '2005', 'day_init': '1',
                'atm_data_type': "'box_tensile'", 'restart_file': "'iced'",
                'pointer_file': "'./ice.restart_file'", 'diag_type': "'stdout'"}
    for key, value in expected.items():
        require(entry(namelist, key).lower() == value.lower(), 'unexpected accepted ' + key)
    for key, value in [('dt', 3600.), ('Ktens', .2), ('dyntens_g_min', .2),
                       ('dyntens_diameter_threshold', 300.)]:
        require(float(entry(namelist, key)) == value, 'unexpected accepted ' + key)
    for key, value in [('history_dir', './history/'), ('restart_dir', './restart/'),
                       ('incond_dir', './history/')]:
        require(entry(namelist, key).strip("'\"") == value, 'unexpected output path ' + key)
    require(entry(namelist, 'histfreq').replace(' ', '').replace('"', "'") == "'d','h','x','x','x'",
            'requires accepted daily/hourly streams')
    require(entry(namelist, 'histfreq_n').replace(' ', '') == '1,1,1,1,1', 'requires daily/hourly frequency 1')
    require(entry(namelist, 'hist_avg').replace(' ', '').lower() == '.true.,.false.,.true.,.true.,.true.',
            'requires daily means and instantaneous hourly output')
    require(entry(namelist, 'incond_file').strip("'\"") == 'iceh_ic', 'requires iceh_ic prefix')
    require(entry(namelist, 'history_file').strip("'\"") == 'iceh', 'requires iceh history prefix')
    for key in ['f_dyntens_g', 'f_ktens_eff', 'f_dyntens_large_fraction',
                'f_dyntens_g_candidate', 'f_ktens_eff_candidate', 'f_dyntens_mapping_status']:
        require(entry(namelist, key).strip("'\"") == 'dh', 'requires dh output for ' + key)
    require(list((oldrun / 'history').glob('iceh*.nc')), 'accepted history missing')
    cases = [repo / name for name in CASES]
    runs = [args.runs.resolve() / name for name in CASES]
    for path in cases + runs:
        require(not path.exists(), 'refusing existing path: ' + str(path))
    require(oldcase == base, 'base case differs from ICE_CASEDIR; use the original accepted case')
    for case, run, days in zip(cases, runs, [5, 2, 3]):
        shutil.copytree(base, case, symlinks=True,
                        ignore=shutil.ignore_patterns('logs', 'history', 'restart', 'compile',
                                                     'input_restart', 'cice.runlog.*', '*.o', '*.mod'))
        # Retarget generated case scripts; retain machine environment and macros.
        for path in case.rglob('*'):
            if path.is_file() and not path.is_symlink() and (path.suffix == '.csh' or
                    path.name in ['cice.settings', 'cice.run', 'cice.submit', 'cice.build']):
                text = path.read_text()
                text = text.replace(str(oldrun), str(run)).replace(str(oldcase), str(case))
                text = re.sub(r'(?m)^(\s*setenv\s+ICE_CASENAME\s+)\S+',
                              lambda m: m[1] + case.name, text)
                text = re.sub(r'(?m)^(#PBS\s+-N\s+)\S+', lambda m: m[1] + case.name, text)
                path.write_text(text)
        text = set_entry(namelist, 'npt', str(days))
        text = set_entry(text, 'use_restart_time', '.true.' if days == 3 else '.false.')
        text = set_entry(text, 'runtype', "'continue'" if days == 3 else "'initial'")
        text = set_entry(text, 'restart_fsd', '.true.' if days == 3 else '.false.')
        (case / 'ice_in.b63-template').write_text(namelist)
        (case / 'ice_in').write_text(text)
        run.mkdir(parents=True)
        shutil.copy2(source_exe, run / 'cice')
        require(sha(source_exe) == sha(run / 'cice'), 'executable copy differs')
        provenance = case / 'b64-provenance'
        provenance.mkdir()
        (provenance / 'executable.sha256').write_text(sha(source_exe) + '\n')
        (provenance / 'accepted-case.txt').write_text(str(base) + '\n' + str(oldrun) + '\n')
        for key, command in [('HEAD.txt', ['git', 'rev-parse', 'HEAD']),
                             ('local.diff', ['git', 'diff']),
                             ('status.txt', ['git', 'status', '--short'])]:
            result = subprocess.run(command, cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, check=True)
            (provenance / key).write_text(result.stdout)
        for filename in ['ice_in', 'cice.settings', 'cice.run', 'env.gadi1_intel', 'Macros.gadi1_intel']:
            source = case / filename
            if source.is_file():
                shutil.copy2(source, provenance / filename)
        print('PREPARED', case, 'run=', run, 'days=', days)
    print('Same accepted executable:', sha(source_exe))
    print('No build needed. Inspect PBS headers/launchers before submitting.')


def clock(path, date, step):
    from netCDF4 import Dataset
    with Dataset(path) as ds:
        values = []
        for alternatives in [('myear', 'nyr'), ('mmonth', 'month'), ('mday',),
                             ('msec', 'sec'), ('istep1',)]:
            name = next((n for n in alternatives if n in ds.ncattrs()), None)
            require(name is not None, 'missing restart clock ' + str(alternatives))
            values.append(int(ds.getncattr(name)))
        require(values == [2005, 1, date, 0, step], 'wrong restart clock: ' + str(values))
        require(all('fsd%03d' % k in ds.variables for k in range(1, 13)), 'missing raw FSD restart bins')
    print('PASS restart clock/FSD inventory', path.name, values)


def stage(args):
    runs = args.runs.resolve()
    source = runs / CASES[1] / 'restart' / ('iced.' + SPLIT + '.nc')
    clock(source, 3, 48)
    run = runs / CASES[2]
    require(not list((run / 'history').glob('*.nc')), 'segment 2 already has history')
    targetdir = run / 'input_restart'
    require(not targetdir.exists(), 'restart already staged; inspect before repeating')
    targetdir.mkdir()
    target = targetdir / source.name
    shutil.copy2(source, target)
    require(sha(source) == sha(target), 'staged restart checksum differs')
    (run / 'ice.restart_file').write_text(str(target) + '\n')
    (args.repo.resolve() / CASES[2] / 'b64-provenance' / 'input-restart.sha256').write_text(sha(target) + '\n')
    print('PASS staged byte-identical restart', target)
    print('Pointer:', run / 'ice.restart_file')


def exact(left, right):
    import numpy as np
    from netCDF4 import Dataset
    with Dataset(left) as a, Dataset(right) as b:
        require(set(a.variables) == set(b.variables), left.name + ': variable inventory differs')
        require({n: len(d) for n, d in a.dimensions.items()} ==
                {n: len(d) for n, d in b.dimensions.items()}, left.name + ': dimensions differ')
        for name in a.variables:
            x, y = a[name], b[name]
            require(x.dimensions == y.dimensions, left.name + ':' + name + ': dimension order differs')
            for attr in ['units', 'calendar', 'bounds', 'time_rep']:
                require(getattr(x, attr, None) == getattr(y, attr, None), left.name + ':' + name + ':' + attr)
            xv, yv = np.ma.asarray(x[:]), np.ma.asarray(y[:])
            require(np.array_equal(np.ma.getmaskarray(xv), np.ma.getmaskarray(yv)),
                    left.name + ':' + name + ': masks differ')
            xv, yv = xv.compressed(), yv.compressed()
            if np.issubdtype(xv.dtype, np.number):
                require(np.isfinite(xv).all() and np.isfinite(yv).all(), left.name + ':' + name + ': nonfinite')
            require(np.array_equal(xv, yv), left.name + ':' + name + ': decoded values differ')


def expected_history(first, days, ic):
    import datetime as dt
    start = dt.datetime(2005, 1, first)
    names = {'iceh.' + (start + dt.timedelta(days=k)).strftime('%Y-%m-%d') + '.nc'
             for k in range(days)}
    for hour in range(1, days * 24 + 1):
        now = start + dt.timedelta(hours=hour)
        names.add('iceh_inst.' + now.strftime('%Y-%m-%d-') + '%05d' % (now.hour * 3600) + '.nc')
    if ic:
        names.add('iceh_ic.' + start.strftime('%Y-%m-%d-00000') + '.nc')
    return names


def ic_mapping(restart, ic):
    """Independent area-weighted mapping of raw 12-bin restart fractions."""
    import numpy as np
    from netCDF4 import Dataset
    with Dataset(restart) as r, Dataset(ic) as h:
        grid = np.ma.asarray(h['tmask'][:])
        ocean = (~np.ma.getmaskarray(grid)) & (grid.data == 1)
        area_var = r['aicen']
        # Restart convention: category, y, x; reject other layouts explicitly.
        require(area_var.dimensions == ('ncat', 'nj', 'ni'),
                'unexpected restart aicen dimensions: ' + str(area_var.dimensions))
        shape = area_var.shape[-2:]
        if shape == grid.shape:
            interior = (slice(None), slice(None))
        elif shape == tuple(n + 2 for n in grid.shape):
            # restart_ext writes nx/ny_global+2*nghost. The audited build
            # uses nghost=1 and gather_global_ext offsets global i/j by one.
            interior = (slice(1, -1), slice(1, -1))
            print('INFO restart_ext: use owned global interior from', shape,
                  'for history grid', grid.shape, '(one halo cell per edge)')
        else:
            raise ValueError('unsupported restart/history grid shapes: aicen='
                             + str(area_var.shape) + ', tmask=' + str(grid.shape))
        selection = (slice(None),) + interior
        areas = np.ma.asarray(area_var[selection])
        fsd = []
        for k in range(1, 13):
            v = r['fsd%03d' % k]
            require(v.dimensions == area_var.dimensions, 'restart FSD/area dimensions differ')
            fsd.append(np.ma.asarray(v[selection]))
        a = np.asarray(areas)
        f = np.asarray(np.ma.stack(fsd))
        require(not np.any(np.ma.getmaskarray(areas)[:, ocean]), 'masked restart ocean areas')
        require(np.isfinite(a[:, ocean]).all() and (a[:, ocean] >= 0).all(), 'invalid restart area')
        total = np.sum(a, axis=0)
        require((total[ocean] <= 1 + 1e-10).all(), 'restart concentration exceeds one')
        active = ocean & (total > 1e-12)
        occupied = (a > 0) & active[None, :, :]
        masks = np.ma.getmaskarray(np.ma.stack(fsd))
        require(not np.any(masks[:, occupied]), 'masked occupied raw FSD')
        require(np.isfinite(f[:, occupied]).all() and (f[:, occupied] >= 0).all(), 'invalid occupied raw FSD')
        require((np.abs(np.sum(f, axis=0)[occupied] - 1) <= 1e-10).all(), 'raw FSD sum differs from one')
        # Audited 12-bin radius centres: diameter >300 selects bins 7..12.
        large = np.sum(np.where(occupied[None, :, :, :], f[6:], 0.), axis=0)
        fraction = np.zeros(grid.shape)
        fraction[active] = np.sum(a * large, axis=0)[active] / total[active]
        require(((fraction[active] >= -1e-10) & (fraction[active] <= 1+1e-10)).all(), 'invalid large fraction')
        fraction = np.clip(fraction, 0., 1.)
        g = np.ones(grid.shape)
        g[active] = .2 + .8 * fraction[active]
        expected = {'dtens_gcand': g, 'ktens_cand': .2*g,
                    'dtens_status': (~active).astype(float), 'dtens_flarge': fraction}
        for base, target in expected.items():
            names = [n for n in h.variables if re.fullmatch(base + r'(?:_\w+)?', n)]
            require(names, 'missing restart IC family ' + base)
            for name in names:
                value = np.ma.asarray(h[name][:])
                require(value.shape == (1,) + grid.shape, 'unexpected IC dimensions ' + name)
                value = value[0]
                check = active if base == 'dtens_flarge' else ocean
                require(not np.any(np.ma.getmaskarray(value)[check]), 'masked IC ocean field ' + name)
                require(np.isfinite(value.data[check]).all() and
                        (np.abs(value.data[check]-target[check]) <= 1e-10).all(), 'restart IC mapping differs ' + name)
                if base == 'dtens_flarge':
                    require(np.all(np.ma.getmaskarray(value)[ocean & ~active]), 'inactive IC fraction unmasked')
    print('PASS restart IC candidate independently reconstructed from raw FSD (atol=1e-10)')


def analyse(args):
    repo, runs = args.repo.resolve(), args.runs.resolve()
    sys.path.insert(0, str(repo / 'test_scripts'))
    from check_b63_candidates import check_dataset
    from netCDF4 import Dataset
    runpaths = [runs / n for n in CASES]
    hashes = [sha(p / 'cice') for p in runpaths]
    require(len(set(hashes)) == 1, 'executables differ')
    print('PASS executable equality', hashes[0])
    for run, first, days in zip(runpaths, [1, 1, 3], [5, 2, 3]):
        want = expected_history(first, days, True)
        have = {p.name for p in (run / 'history').glob('*.nc')}
        require(have == want, str(run) + ': history inventory differs; missing=' +
                str(sorted(want-have)) + ' extra=' + str(sorted(have-want)))
        for name in sorted(want):
            with Dataset(run / 'history' / name) as ds:
                check_dataset(ds, .2, .2, 1e-10)
        print('PASS candidate/applied history', run.name, len(want), 'files')
        restart_names = {'iced.2005-01-%02d-00000.nc' % d for d in range(first+1, first+days+1)}
        require({p.name for p in (run / 'restart').glob('*.nc')} == restart_names,
                str(run) + ': restart inventory differs')
        for day in range(first+1, first+days+1):
            clock(run / 'restart' / ('iced.2005-01-%02d-00000.nc' % day), day, (day-1)*24)
    cont, seg1, seg2 = runpaths
    source = seg1 / 'restart' / ('iced.' + SPLIT + '.nc')
    staged = seg2 / 'input_restart' / source.name
    require(sha(source) == sha(staged), 'staged input changed')
    ic_mapping(staged, seg2 / 'history' / ('iceh_ic.' + SPLIT + '.nc'))
    for seg, first, days, include_ic in [(seg1, 1, 2, True), (seg2, 3, 3, False)]:
        names = expected_history(first, days, include_ic)
        for name in sorted(names):
            exact(seg / 'history' / name, cont / 'history' / name)
        restarts = sorted((seg / 'restart').glob('*.nc'))
        for path in restarts:
            exact(path, cont / 'restart' / path.name)
        print('PASS exact comparison', seg.name, len(names), 'histories +', len(restarts), 'restarts')
    print('PASS B6.4 diagnostic-only continuation: 126 history pairs and 5 restart pairs; atol=rtol=0')
    print('Restart IC checked independently; mapped-feedback/halo validation remains pending.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['prepare', 'stage', 'analyse'])
    p.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--runs', type=Path, default=Path('/g/data/gv90/da1339/cice-dirs/runs'))
    p.add_argument('--base-case', type=Path, help='accepted B6.3 diagnostic case; auto-detect if unique')
    args = p.parse_args()
    try:
        if args.action == 'prepare' and args.base_case is None:
            matches = []
            for path in args.repo.resolve().glob('dt_b63*/ice_in'):
                if re.search(r'(?mi)^\s*use_dyntens_diagnostics\s*=\s*\.true\.', path.read_text()):
                    matches.append(path.parent)
            require(len(matches) == 1, 'specify --base-case: found diagnostic cases ' + str(matches))
            args.base_case = matches[0]
        {'prepare': prepare, 'stage': stage, 'analyse': analyse}[args.action](args)
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as e:
        p.exit(1, 'FAIL: ' + str(e) + '\n')


if __name__ == '__main__':
    main()
