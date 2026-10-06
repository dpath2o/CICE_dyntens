"""B6.5-F box shadow-mapping feedback versus independent prescribed controls."""
import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path
from ..core.types import WorkflowSpec
from ..core.paths import model_repo, run_root
from ..core.cases import case_path, diagnostic_cases, verify_input_hash
from ..core.reporting import EvidenceWorkflow, source_state
from .restart import require, entry, set_entry, setting, sha, clock, expected_history, exact
from .box import LAYOUTS, compare

# Independently prescribed decimal literals, including binary64 mixture rounding.
G = {'small': '0.2', 'large': '1.0', 'mixed': '0.6000000000000001'}
ROWS = [(fixture, kind, layout) for layout in LAYOUTS for fixture in G
        for kind in ('map', 'ref')] + [('large', 'off', layout) for layout in LAYOUTS]


def name(row):
    return 'dt_b65f_'+'_'.join(row)


def put(text, key, value):
    if re.search(r'(?mi)^\s*'+re.escape(key)+r'\s*=', text):
        return set_entry(text, key, value)
    text, count = re.subn(r'(?mi)^(\s*&dynamics_nml\s*)$',
                         lambda m: m[1]+'\n    '+key+' = '+value, text)
    require(count == 1, 'missing dynamics_nml')
    return text


def check_applied(ds, g, tol=1e-10):
    import numpy as np
    from ..validation.candidates import ocean_cells, close
    for base, expected in [('dyntens_g', g), ('ktens_eff', .2*g)]:
        names = [n for n in ds.variables if re.fullmatch(base+r'(?:_\w+)?', n)]
        require(names, 'missing applied field '+base)
        for key in names:
            field = np.ma.asarray(ds[key][:])
            ocean = ocean_cells(ds, ds[key])
            require(not np.any(ocean & np.ma.getmaskarray(field)), 'masked applied '+key)
            close(field.data[ocean], expected, tol, 'wrong applied '+key)


def check_mapped(ds, fixture):
    import numpy as np
    from ..validation.candidates import check_dataset, BASES, ocean_cells, close
    g = float(G[fixture])
    check_dataset(ds, .2, .2, 1e-10, applied_g=g)
    expected = [dict(small=0., large=1., mixed=.5)[fixture], g, .2*g, 0.]
    for base, value in zip(BASES, expected):
        for key in ds.variables:
            if re.fullmatch(base+r'(?:_\w+)?', key):
                field = np.ma.asarray(ds[key][:])
                ocean = ocean_cells(ds, ds[key])
                require(not np.any(ocean & np.ma.getmaskarray(field)), 'masked fixture '+key)
                close(field.data[ocean], value, 1e-10, 'wrong fixture '+key)


def physical_difference(left, right):
    """Require a response in velocity/ice state, not only in coefficient output."""
    import numpy as np
    from netCDF4 import Dataset
    from ..validation.candidates import ocean_cells
    with Dataset(left) as a, Dataset(right) as b:
        keys = [n for n in a.variables if re.fullmatch(r'(?:uvel|vvel|aice|hi)(?:_\w+)?', n)]
        require(keys, 'no response fields in '+str(left))
        for key in keys:
            require(key in b.variables, 'response inventory differs')
            x, y = np.ma.asarray(a[key][:]), np.ma.asarray(b[key][:])
            ocean = ocean_cells(a, a[key])
            require(x.shape == y.shape, 'response dimensions differ')
            valid = ocean & ~np.ma.getmaskarray(x) & ~np.ma.getmaskarray(y)
            require(np.isfinite(x.data[valid]).all() and np.isfinite(y.data[valid]).all(),
                    'nonfinite response '+key)
            if np.any(x.data[valid] != y.data[valid]):
                return key
    return None


class FeedbackWorkflow(EvidenceWorkflow):
    gate = 'B6.5F'
    pending = ('B6.6 live invalid-state tests', 'live-FSD mapped adapter/global validation')

    def __init__(self, spec):
        self.spec = spec

    def prepare(self):
        repo, runs = self.spec.repo.resolve(), self.spec.runs.resolve()
        templates = {}
        for layout in LAYOUTS:
            base = case_path(repo,'dt_b65_ctl_'+layout)
            text = (base/'ice_in').read_text()
            require(Path(setting((base/'cice.settings').read_text(), 'ICE_CASEDIR')) == base,
                    'use original accepted B6.5 controls')
            for key, value in [('use_dyntens', '.false.'), ('tr_fsd', '.true.'), ('nfsd', '12'),
                               ('ndtd', '1'), ('year_init', '2005'), ('day_init', '1'),
                               ('ice_ic', "'internal'"), ('npt_unit', "'d'"), ('diag_type', "'stdout'")]:
                require(entry(text, key).lower() == value, 'unexpected template '+key)
            for key, value in [('dt', 3600.), ('Ktens', .2), ('dyntens_g_min', .2),
                               ('dyntens_diameter_threshold', 300.)]:
                require(float(entry(text, key)) == value, 'unexpected template '+key)
            require(any('CICE COMPLETED SUCCESSFULLY' in p.read_text(errors='replace')
                        for p in (runs/base.name).glob('cice.runlog.*')), 'unfinished source control '+base.name)
            for filename in ('env.gadi1_intel', 'Macros.gadi1_intel'):
                require((base/filename).is_file(), 'missing build environment '+filename)
            templates[layout] = (base, text)
        for row in ROWS:
            require(not (case_path(repo,name(row))).exists() and not (runs/name(row)).exists(),
                    'refusing existing case/run '+name(row))
        domain = re.compile(r'(?ms)^\s*&domain_nml\b.*?^\s*/\s*$')
        state = source_state(repo)
        for row in ROWS:
            fixture, kind, layout = row
            case = case_path(repo,name(row))
            base, text = templates[layout]
            case.parent.mkdir(parents=True,exist_ok=True)
            subprocess.run(['./cice.setup', '-c', str(case), '-m', 'gadi1', '-e', 'intel',
                            '-g', 'gbox12', '-p', LAYOUTS[layout],
                            '-s', 'boxforcee,boxclosed,buildclean'], cwd=repo, check=True)
            settings = (case/'cice.settings').read_text()
            require(Path(setting(settings, 'ICE_RUNDIR')) == runs/case.name, 'unexpected run directory')
            generated = (case/'ice_in').read_text()
            groups = domain.findall(generated)
            require(len(groups) == 1 and len(domain.findall(text)) == 1, 'unexpected domain_nml')
            text = domain.sub(lambda m: groups[0], text)
            for key, value in [('npt', '5'), ('runtype', "'initial'"), ('use_restart_time', '.false.'),
                               ('restart_fsd', '.false.'), ('use_dyntens', '.false.' if kind=='off' else '.true.'),
                               ('use_dyntens_diagnostics', '.true.' if kind=='map' else '.false.'),
                               ('dyntens_g_mode', "'box_fsd'" if kind=='map' else
                                ("'box_constant'" if kind=='ref' else "'constant'")),
                               ('dyntens_g_const', G[fixture]),
                               ('dyntens_box_fixture', "'"+fixture+"'" if kind=='map' else "'none'")]:
                text = put(text, key, value)
            for key in ('f_dyntens_large_fraction', 'f_dyntens_g_candidate',
                        'f_ktens_eff_candidate', 'f_dyntens_mapping_status'):
                text = set_entry(text, key, "'dh'" if kind=='map' else "'x'")
            (case/'ice_in').write_text(text)
            for filename in ('env.gadi1_intel', 'Macros.gadi1_intel'):
                shutil.copy2(base/filename, case/filename)
            launcher = (case/'cice.run').read_text()
            for resource, value in [('ncpus', '2' if layout=='m2' else '1'),
                                    ('mem', '9gb'), ('walltime', '00:30:00')]:
                launcher, count = re.subn(r'(?m)^(#PBS\s+-l\s+'+resource+r'=)\S+',
                                         lambda m: m[1]+value, launcher)
                require(count == 1, 'inspect PBS '+resource)
            (case/'cice.run').write_text(launcher)
            evidence = case/'b65f-provenance'
            evidence.mkdir()
            for filename in ('ice_in', 'cice.settings', 'cice.run', 'env.gadi1_intel', 'Macros.gadi1_intel'):
                shutil.copy2(case/filename, evidence/filename)
            manifest = {'source': state, 'template': str(base), 'fixture': fixture, 'kind': kind,
                        'layout': layout, 'prescribed_g_literal': G[fixture],
                        'inputs': {f: sha(case/f) for f in ('ice_in','cice.settings','cice.run',
                                                          'env.gadi1_intel','Macros.gadi1_intel')}}
            (evidence/'input.json').write_text(json.dumps(manifest, indent=2)+'\n')
            print('PREPARED', case.name)

    def distribute(self):
        repo, runs = self.spec.repo.resolve(), self.spec.runs.resolve()
        for layout in LAYOUTS:
            require((runs/name(('large','ref',layout))/'cice').is_file(), 'build missing '+layout)
        for row in ROWS:
            run = runs/name(row)
            source = runs/name(('large','ref',row[2]))/'cice'
            require(not list((run/'history').glob('*.nc')), 'existing output '+str(run))
            run.mkdir(parents=True, exist_ok=True)
            if run/'cice' != source:
                require(not (run/'cice').exists(), 'executable already distributed '+str(run))
                shutil.copy2(source, run/'cice')
            (case_path(repo,name(row))/'b65f-provenance'/'executable.sha256').write_text(sha(run/'cice')+'\n')
            print('EXECUTABLE', name(row), sha(run/'cice'))

    def analyse(self):
        from netCDF4 import Dataset
        from ..validation.candidates import is_candidate
        repo, runs = self.spec.repo.resolve(), self.spec.runs.resolve()
        histories = expected_history(1, 5, True)
        restarts = {'iced.2005-01-%02d-00000.nc'%day for day in range(2,7)}
        for row in ROWS:
            fixture, kind, layout = row
            run = runs/name(row)
            evidence = case_path(repo,name(row))/'b65f-provenance'
            manifest = json.loads((evidence/'input.json').read_text())
            for filename, digest in manifest['inputs'].items():
                require(verify_input_hash(case_path(repo,name(row)),filename,digest), 'input changed '+name(row)+'/'+filename)
            digest = sha(run/'cice')
            require(digest == (evidence/'executable.sha256').read_text().strip(), 'executable provenance mismatch')
            require(digest == sha(runs/name(('large','ref',layout))/'cice'), 'layout executable mismatch')
            logs = list(run.glob('cice.runlog.*'))
            require(len(logs) == 1 and 'CICE COMPLETED SUCCESSFULLY' in logs[0].read_text(errors='replace'),
                    'expected one successful fresh log '+name(row))
            require({p.name for p in (run/'history').glob('*.nc')} == histories, 'history coverage '+name(row))
            require({p.name for p in (run/'restart').glob('*.nc')} == restarts, 'restart coverage '+name(row))
            for filename in sorted(histories):
                with Dataset(run/'history'/filename) as ds:
                    try:
                        if kind=='map':
                            check_mapped(ds, fixture)
                        else:
                            require(not any(is_candidate(k) for k in ds.variables), 'unexpected control candidate')
                            check_applied(ds, float(G[fixture]))
                    except ValueError as exc:
                        raise ValueError(str(run/'history'/filename)+': '+str(exc)) from exc
            for filename in sorted(restarts):
                day = int(filename.split('-')[2])
                clock(run/'restart'/filename, day, (day-1)*24)
            print('PASS fields/coverage', name(row), '126 histories, five restarts')
        for layout in LAYOUTS:
            for fixture in G:
                mapped, reference = [runs/name((fixture, kind, layout)) for kind in ('map','ref')]
                for filename in sorted(histories):
                    compare(mapped/'history'/filename, reference/'history'/filename, candidates=False)
                for filename in sorted(restarts):
                    exact(mapped/'restart'/filename, reference/'restart'/filename)
                print('PASS exact mapped/prescribed', fixture, layout)
            unity, off = [runs/name(('large', kind, layout)) for kind in ('ref','off')]
            for filename in sorted(histories):
                compare(unity/'history'/filename, off/'history'/filename, candidates=False)
            for filename in sorted(restarts):
                exact(unity/'restart'/filename, off/'restart'/filename)
            print('PASS unity/off', layout)
            small, large = [runs/name((fixture, 'ref', layout)) for fixture in ('small','large')]
            response = next(((f, key) for f in sorted(histories) if not f.startswith('iceh_ic.')
                             if (key := physical_difference(small/'history'/f, large/'history'/f))), None)
            require(response, 'no physical response to g=0.2 versus g=1: '+layout)
            print('PASS physical response', layout, response)
        for layout in ('s2','m2'):
            for fixture, kind, _ in [r for r in ROWS if r[2]=='s1']:
                run, ref = [runs/name((fixture, kind, k)) for k in (layout,'s1')]
                for filename in sorted(histories):
                    compare(run/'history'/filename, ref/'history'/filename, layout=True)
                for filename in sorted(restarts):
                    exact(run/'restart'/filename, ref/'restart'/filename)
                print('PASS exact decomposition', run.name, '(only history blkmask values excluded)')
        print('PASS B6.5F controlled shadow-feedback equivalence; not live/global FSD validation')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['prepare','distribute','analyse'])
    p.add_argument('--repo', type=Path)
    p.add_argument('--runs', type=Path, default=run_root())
    p.add_argument('--evidence', type=Path)
    args = p.parse_args()
    workflow = FeedbackWorkflow(WorkflowSpec(args.repo or model_repo(), args.runs))
    try:
        if args.evidence:
            workflow.run_with_evidence(args.action, args.evidence)
        else:
            getattr(workflow, args.action)()
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as exc:
        p.exit(1, 'FAIL: '+str(exc)+'\n')


if __name__ == '__main__':
    main()
