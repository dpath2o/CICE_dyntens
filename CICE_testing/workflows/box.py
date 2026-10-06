#!/usr/bin/env python3
"""B6.5 diagnostic shadow-fixture matrix, decomposition and split restart.

prepare creates fresh cases; stage stages the two-day spatial restart;
analyse checks analytical candidates, exact neutrality and equivalence.
Model building/submission remains explicit in Bash. No mapped feedback here.
"""
import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path
from ..core.types import WorkflowSpec
from ..core.reporting import EvidenceWorkflow
from ..core.paths import model_repo, run_root
from .restart import require, entry, set_entry, setting, sha, clock, expected_history, exact

LAYOUTS = {'s1': '1x1x12x12x1', 's2': '1x1x6x12x2', 'm2': '2x1x6x12x1'}
ROWS = [('ctl', 'none', 's1', 5), ('small', 'small', 's1', 5),
        ('large', 'large', 's1', 5), ('mix', 'mixed', 's1', 5),
        ('uneq', 'unequal', 's1', 5), ('dil', 'dilute', 's1', 5),
        ('zero', 'inactive', 's1', 5), ('sp', 'spatial', 's1', 5),
        ('ctl', 'none', 's2', 5), ('sp', 'spatial', 's2', 5),
        ('ctl', 'none', 'm2', 5), ('sp', 'spatial', 'm2', 5),
        ('sp_a', 'spatial', 'm2', 2), ('sp_b', 'spatial', 'm2', 3)]


def name(row):
    return 'dt_b65_' + row[0] + '_' + row[2]








def check_fixture(ds, mode):
    import numpy as np
    from ..validation.candidates import check_dataset, BASES
    check_dataset(ds, .2, .2, 1e-10)
    grid = np.ma.asarray(ds['tmask'][:])
    ocean = (~np.ma.getmaskarray(grid)) & (grid.data == 1)
    expected = {'small': 0., 'large': 1., 'mixed': .5, 'unequal': 2./3., 'dilute': 2./3., 'inactive': 0.}
    fraction = np.full(grid.shape, expected.get(mode, 1.))
    if mode=='spatial':
        require(grid.shape == (12, 12), 'spatial fixture requires 12x12 history')
        fraction[:, 5] = 0.
    g = .2+.8*fraction if mode!='inactive' else np.ones(grid.shape)
    targets = [fraction, g, .2*g, np.full(grid.shape, 1. if mode=='inactive' else 0.)]
    for base, target in zip(BASES, targets):
        for key in [n for n in ds.variables if re.fullmatch(base+r'(?:_\w+)?', n)]:
            x = np.ma.asarray(ds[key][:])
            region = np.broadcast_to(ocean, x.shape)
            if base=='dtens_flarge' and mode=='inactive':
                require(np.all(np.ma.getmaskarray(x)[region]), 'inactive fixture fraction unmasked')
            else:
                want = np.broadcast_to(target, x.shape)
                require(not np.any(np.ma.getmaskarray(x)[region]) and
                        np.all(np.abs(x.data[region]-want[region])<=1e-10), 'wrong analytical fixture '+key)


def compare(left, right, candidates=True, layout=False):
    import numpy as np
    from netCDF4 import Dataset
    from ..validation.candidates import is_candidate
    with Dataset(left) as a, Dataset(right) as b:
        names = [{n for n in d.variables if candidates or not is_candidate(n)} for d in (a,b)]
        require(names[0]==names[1], left.name+': inventories differ')
        require({n:len(d) for n,d in a.dimensions.items()} == {n:len(d) for n,d in b.dimensions.items()},
                left.name+': dimensions differ')
        for key in names[0]:
            x, y = a[key], b[key]
            require(x.dimensions==y.dimensions, left.name+': dimension order '+key)
            for attr in ['units','calendar','bounds','time_rep']:
                require(getattr(x,attr,None)==getattr(y,attr,None), left.name+': metadata '+key)
            xx, yy = np.ma.asarray(x[:]), np.ma.asarray(y[:])
            require(np.array_equal(np.ma.getmaskarray(xx),np.ma.getmaskarray(yy)), left.name+': masks '+key)
            xx, yy = xx.compressed(), yy.compressed()
            if np.issubdtype(xx.dtype,np.number):
                require(np.isfinite(xx).all() and np.isfinite(yy).all(), left.name+': nonfinite '+key)
            if not (layout and key=='blkmask'):
                require(np.array_equal(xx,yy), left.name+': exact values differ '+key)




class BoxWorkflow(EvidenceWorkflow):
    """Configured box workflow; building and job submission remain explicit."""

    gate = 'B6.5'
    pending = ('B6.5-F mapped-feedback equivalence', 'B6.6 live invalid-state tests')

    def __init__(self, spec: WorkflowSpec):
        self.spec = spec

    def prepare(self):
        spec = self.spec
        repo, runs = spec.repo.resolve(), spec.runs.resolve()
        base = spec.base_case
        if base is None:
            matches = [p.parent for p in repo.glob('dt_b63*/ice_in')
                       if re.search(r'(?mi)^\s*use_dyntens_diagnostics\s*=\s*\.true\.', p.read_text())]
            require(len(matches) == 1, 'specify --base-case; diagnostic cases=' + str(matches))
            base = matches[0]
        base = base.resolve()
        template = (base / 'ice_in').read_text()
        require(Path(setting((base/'cice.settings').read_text(), 'ICE_CASEDIR')) == base,
                '--base-case must be the original case directory, not the run directory')
        for key, want in [('use_dyntens', '.false.'), ('use_dyntens_diagnostics', '.true.'),
                          ('tr_fsd', '.true.'), ('nfsd', '12'), ('ndtd', '1'),
                          ('npt_unit', "'d'"), ('year_init', '2005'), ('day_init', '1'),
                          ('ice_ic', "'internal'"), ('diag_type', "'stdout'")]:
            require(entry(template, key).lower() == want, 'unexpected template ' + key)
        for key, want in [('dt', 3600.), ('Ktens', .2), ('dyntens_g_min', .2),
                          ('dyntens_diameter_threshold', 300.)]:
            require(float(entry(template, key)) == want, 'unexpected template ' + key)
        for row in ROWS:
            require(not (repo/name(row)).exists() and not (runs/name(row)).exists(),
                    'refusing existing case/run: ' + name(row))
        domain = re.compile(r'(?ms)^\s*&domain_nml\b.*?^\s*/\s*$')
        require(len(domain.findall(template)) == 1, 'expected exactly one template domain_nml')
        for row in ROWS:
            casename = name(row)
            subprocess.run(['./cice.setup', '-c', casename, '-m', 'gadi1', '-e', 'intel',
                            '-g', 'gbox12', '-p', LAYOUTS[row[2]], '-s', 'boxforcee,boxclosed,buildclean'],
                           cwd=repo, check=True)
            case = repo/casename
            settings = (case/'cice.settings').read_text()
            require(Path(setting(settings, 'ICE_RUNDIR')) == runs/casename, 'unexpected generated run directory')
            generated = (case/'ice_in').read_text()
            groups = domain.findall(generated)
            require(len(groups) == 1, 'expected exactly one generated domain_nml')
            result = domain.sub(lambda m: groups[0], template)
            for key, value in [('npt', str(row[3])), ('runtype', "'continue'" if row[0]=='sp_b' else "'initial'"),
                               ('use_restart_time', '.true.' if row[0]=='sp_b' else '.false.'),
                               ('restart_fsd', '.true.' if row[0]=='sp_b' else '.false.'),
                               ('use_dyntens_diagnostics', '.false.' if row[0]=='ctl' else '.true.')]:
                result = set_entry(result, key, value)
            if re.search(r'(?mi)^\s*dyntens_box_fixture\s*=', result):
                result = set_entry(result, 'dyntens_box_fixture', "'"+row[1]+"'")
            else:
                result, count = re.subn(r'(?mi)^(\s*&dynamics_nml\s*)$',
                                       lambda m: m[1]+"\n    dyntens_box_fixture = '"+row[1]+"'", result)
                require(count == 1, 'missing dynamics_nml')
            if row[0]=='ctl':
                for key in ['f_dyntens_large_fraction', 'f_dyntens_g_candidate',
                            'f_ktens_eff_candidate', 'f_dyntens_mapping_status']:
                    result = set_entry(result, key, "'x'")
            (case/'ice_in.setup-original').write_text(generated)
            (case/'ice_in').write_text(result)
            for filename in ['env.gadi1_intel', 'Macros.gadi1_intel']:
                shutil.copy2(base/filename, case/filename)
            # Retain generator's launcher; alter resources only to the accepted small-box values.
            text = (case/'cice.run').read_text()
            for resource, value in [('ncpus', '2' if row[2]=='m2' else '1'),
                                    ('mem', '9gb'), ('walltime', '00:30:00')]:
                text, count = re.subn(r'(?m)^(#PBS\s+-l\s+'+resource+r'=)\S+',
                                     lambda m: m[1]+value, text)
                require(count == 1, 'inspect generated PBS resource '+resource)
            (case/'cice.run').write_text(text)
            provenance = case/'b65-provenance'
            provenance.mkdir()
            for filename in ['ice_in', 'cice.settings', 'cice.run', 'env.gadi1_intel', 'Macros.gadi1_intel']:
                shutil.copy2(case/filename, provenance/filename)
            for filename, command in [('HEAD.txt', ['git','rev-parse','HEAD']),
                                      ('local.diff', ['git','diff'])]:
                (provenance/filename).write_text(subprocess.check_output(command, cwd=repo, universal_newlines=True))
            print('PREPARED', casename, row[1], row[2], row[3], 'days')


    def distribute(self):
        spec = self.spec
        repo, runs = spec.repo.resolve(), spec.runs.resolve()
        for row in ROWS:
            source = runs/('dt_b65_ctl_'+row[2])/'cice'
            require(source.is_file(), 'build missing: '+str(source))
        for row in ROWS:
            source = runs/('dt_b65_ctl_'+row[2])/'cice'
            run = runs/name(row)
            require(not list((run/'history').glob('*.nc')), 'already has history: '+str(run))
            run.mkdir(parents=True, exist_ok=True)
            if source != run/'cice':
                require(not (run/'cice').exists(), 'executable already distributed: '+str(run))
                shutil.copy2(source, run/'cice')
            (repo/name(row)/'b65-provenance'/'executable.sha256').write_text(sha(run/'cice')+'\n')
            print('EXECUTABLE', name(row), sha(run/'cice'))


    def stage(self):
        spec = self.spec
        repo, runs = spec.repo.resolve(), spec.runs.resolve()
        source = runs/'dt_b65_sp_a_m2'/'restart'/'iced.2005-01-03-00000.nc'
        clock(source, 3, 48)
        run = runs/'dt_b65_sp_b_m2'
        require(not list((run/'history').glob('*.nc')), 'continuation already has output')
        targetdir = run/'input_restart'
        require(not targetdir.exists(), 'restart already staged')
        targetdir.mkdir()
        target = targetdir/source.name
        shutil.copy2(source, target)
        require(sha(source) == sha(target), 'restart copy differs')
        (run/'ice.restart_file').write_text(str(target)+'\n')
        (repo/'dt_b65_sp_b_m2'/'b65-provenance'/'input-restart.sha256').write_text(sha(target)+'\n')
        print('PASS staged spatial restart', target)


    def analyse(self):
        spec = self.spec
        repo, runs = spec.repo.resolve(), spec.runs.resolve()
        from netCDF4 import Dataset
        for row in ROWS:
            run = runs/name(row)
            reference = runs/('dt_b65_ctl_'+row[2])
            require(sha(run/'cice')==sha(reference/'cice'), 'layout executable mismatch '+name(row))
            first = 3 if row[0]=='sp_b' else 1
            names = expected_history(first,row[3],True)
            require({p.name for p in (run/'history').glob('*.nc')}==names, 'history coverage '+name(row))
            for filename in sorted(names):
                if row[0]!='ctl':
                    with Dataset(run/'history'/filename) as d:
                        check_fixture(d,row[1])
                    # Continuation IC precedes forcing and has no same-phase control snapshot.
                    if not (row[0]=='sp_b' and filename.startswith('iceh_ic.')):
                        compare(run/'history'/filename, reference/'history'/filename, candidates=False)
            restarts = {'iced.2005-01-%02d-00000.nc'%day for day in range(first+1,first+row[3]+1)}
            require({p.name for p in (run/'restart').glob('*.nc')}==restarts, 'restart coverage '+name(row))
            for filename in sorted(restarts):
                day = int(filename.split('-')[2])
                clock(run/'restart'/filename,day,(day-1)*24)
                if row[0]!='ctl':
                    exact(run/'restart'/filename,reference/'restart'/filename)
            print('PASS analytical/neutrality',name(row),len(names),'history files')
        for layout in ['s2','m2']:
            for tag in ['ctl','sp']:
                run = runs/('dt_b65_'+tag+'_'+layout)
                reference = runs/('dt_b65_'+tag+'_s1')
                for path in sorted((run/'history').glob('*.nc')):
                    compare(path,reference/'history'/path.name,layout=True)
                for path in sorted((run/'restart').glob('*.nc')):
                    exact(path,reference/'restart'/path.name)
                print('PASS exact decomposition',run.name,'vs',reference.name,'(history blkmask ownership values excluded)')
        cont = runs/'dt_b65_sp_m2'
        source = runs/'dt_b65_sp_a_m2'/'restart'/'iced.2005-01-03-00000.nc'
        staged = runs/'dt_b65_sp_b_m2'/'input_restart'/source.name
        require(sha(source)==sha(staged),'staged spatial input changed')
        for tag, first, days, ic in [('sp_a',1,2,True),('sp_b',3,3,False)]:
            run = runs/('dt_b65_'+tag+'_m2')
            names = expected_history(first,days,ic)
            for filename in sorted(names):
                compare(run/'history'/filename,cont/'history'/filename)
            for path in sorted((run/'restart').glob('*.nc')):
                exact(path,cont/'restart'/path.name)
            print('PASS exact spatial continuation',run.name,len(names),'history pairs')
        print('PASS B6.5 diagnostic shadow-fixture matrix: analytical, neutrality, decomposition, spatial continuation')
        print('B6.5-F mapped-feedback equivalence and B6.6 live invalid-state tests remain pending.')


def prepare(args):
    """Compatibility adapter; prefer BoxWorkflow."""
    return BoxWorkflow(WorkflowSpec(args.repo, args.runs, getattr(args, "base_case", None))).prepare()

def distribute(args):
    """Compatibility adapter; prefer BoxWorkflow."""
    return BoxWorkflow(WorkflowSpec(args.repo, args.runs, getattr(args, "base_case", None))).distribute()

def stage(args):
    """Compatibility adapter; prefer BoxWorkflow."""
    return BoxWorkflow(WorkflowSpec(args.repo, args.runs, getattr(args, "base_case", None))).stage()

def analyse(args):
    """Compatibility adapter; prefer BoxWorkflow."""
    return BoxWorkflow(WorkflowSpec(args.repo, args.runs, getattr(args, "base_case", None))).analyse()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['prepare','distribute','stage','analyse'])
    p.add_argument('--repo',type=Path,default=None)
    p.add_argument('--runs',type=Path,default=run_root())
    p.add_argument('--base-case',type=Path)
    p.add_argument('--evidence', type=Path, help='write analyse transcript and validation JSON')
    args=p.parse_args()
    args.repo = args.repo or model_repo()
    try:
        workflow = BoxWorkflow(WorkflowSpec(args.repo, args.runs, args.base_case))
        if args.evidence:
            workflow.run_with_evidence(args.action, args.evidence)
        else:
            getattr(workflow, args.action)()
    except (ValueError,OSError,KeyError,subprocess.CalledProcessError) as e:
        p.exit(1,'FAIL: '+str(e)+'\n')


if __name__=='__main__':
    main()
