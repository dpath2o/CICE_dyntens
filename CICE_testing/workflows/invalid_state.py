"""B6.6 restart-entry tests of the live FSD adapter, serial and two-rank MPI.

Copies accepted B6.5-F feedback-off controls into fresh cases. Only copied input restarts are
perturbed. No model source changes, live timestep injection or mapped feedback.
"""
import argparse
import json
import re
import shutil
from pathlib import Path
import numpy as np
from netCDF4 import Dataset
from ..core.types import WorkflowSpec
from ..core.paths import model_repo, run_root
from ..core.reporting import EvidenceWorkflow, sha256, source_state
from .restart import require, entry, setting, set_entry, clock, expected_history, exact, ic_mapping
from .box import compare
from ..validation.candidates import check_dataset
from ..validation.spatial import field

MODES = ('valid', 'negative', 'nonfinite', 'bad_sum', 'zero_area', 'negligible_area')
LAYOUTS = ('s1', 'm2')
SOURCE = 'iced.2005-01-03-00000.nc'
IC = 'iceh_ic.2005-01-03-00000.nc'
ABORT = 'Invalid occupied FSD in dyntens candidate mapping; see status log'


def case_name(mode, layout):
    return 'dt_b66_' + mode + '_' + layout


def base_name(layout):
    return 'dt_b65f_large_off_' + layout


def restart_cell(restart, history):
    """Select an occupied ocean cell in global column 7, away from box edges.

    Column 7 lies in the other x block of the audited 6+6 split. No assumption
    about the MPI task assigned to that block is needed; actual task is logged.
    """
    with Dataset(history) as h, Dataset(restart) as r:
        mask = field(h, 'tmask')
        require(mask.shape == (12,12), 'requires audited 12x12 box history')
        a = r['aicen']
        require(a.dimensions == ('ncat','nj','ni'), 'unexpected aicen dimensions')
        shape = a.shape[1:]
        require(shape in ((12,12),(14,14)), 'unsupported restart halo extent')
        offset = 1 if shape == (14,14) else 0
        values = np.ma.asarray(a[:])
        for j in range(2,10):
            i = 6  # global column 7, one-based
            if np.ma.is_masked(mask[j,i]) or mask[j,i] != 1:
                continue
            areas = values[:,j+offset,i+offset]
            if np.ma.getmaskarray(areas).any() or not np.isfinite(areas).all():
                continue
            if areas.sum() > 1e-6:
                n = int(np.argmax(areas))
                return n, j+offset, i+offset, j+1, i+1
    raise ValueError('no occupied ocean category in global column 7')


def validate_source(restart, history):
    """Require a valid source throughout owned ocean before isolating a failure."""
    with Dataset(history) as h, Dataset(restart) as r:
        mask=field(h,'tmask')
        ocean=~np.ma.getmaskarray(mask) & (mask.data==1)
        a=r['aicen']
        require(a.dimensions==('ncat','nj','ni'),'unexpected source area dimensions')
        require(a.shape[1:] in ((12,12),(14,14)),'unexpected source halo extent')
        interior=(slice(1,-1),slice(1,-1)) if a.shape[1:]==(14,14) else (slice(None),slice(None))
        areas=np.ma.asarray(a[(slice(None),)+interior])
        require(not np.ma.getmaskarray(areas)[:,ocean].any(),'masked source area')
        data=areas.data
        require(np.isfinite(data[:,ocean]).all() and (data[:,ocean]>=0).all(),'invalid source area')
        total=data.sum(axis=0)
        require((total[ocean]<=1+1e-10).all(),'source total area exceeds one')
        occupied=(data>0) & (ocean & (total>1e-12))[None,:,:]
        total_f=np.zeros_like(data)
        for k in range(1,13):
            v=r[f'fsd{k:03d}']
            require(v.dimensions==a.dimensions and v.shape==a.shape,'source FSD dimensions differ')
            f=np.ma.asarray(v[(slice(None),)+interior])
            require(not np.ma.getmaskarray(f)[occupied].any(),'masked source occupied FSD')
            require(np.isfinite(f.data[occupied]).all() and (f.data[occupied]>=0).all() and
                    (f.data[occupied]<=1+1e-10).all(),'invalid source occupied FSD')
            total_f+=f.data
        require((np.abs(total_f[occupied]-1)<=1e-10).all(),'source occupied FSD not normalized')


def perturb_restart(path, history, mode):
    require(mode in MODES, 'unknown perturbation')
    n,j,i,gj,gi = restart_cell(path,history)
    before = sha256(path)
    with Dataset(path,'r+') as r:
        a = r['aicen']
        for k in range(1,13):
            require(r[f'fsd{k:03d}'].dimensions == a.dimensions, 'FSD dimensions differ')
        if mode == 'negative': r['fsd001'][n,j,i] = -0.1
        elif mode == 'nonfinite': r['fsd001'][n,j,i] = np.nan
        elif mode == 'bad_sum':
            for k in range(1,13): r[f'fsd{k:03d}'][n,j,i] = 0.
        elif mode in ('zero_area','negligible_area'):
            old = np.asarray(a[:,j,i],dtype=float)
            target = 0. if mode == 'zero_area' else 5e-13
            factor = target/old.sum()
            a[:,j,i] = old*factor
            # Retain thickness/snow depth while scaling category ice/snow volumes.
            for key in ('vicen','vsnon'):
                require(key in r.variables and r[key].dimensions == a.dimensions, 'missing compatible '+key)
                r[key][:,j,i] = r[key][:,j,i]*factor
            # Tiny positive ice may become active during the continuation.
            # Keep its valid normalized source tracers; zero bins would plant
            # an unrelated future occupied-FSD failure in a success test.
            if mode == 'zero_area':
                for k in range(1,13): r[f'fsd{k:03d}'][:,j,i] = 0.
    return {'mode':mode,'category':n+1,'global_j':gj,'global_i':gi,
            'restart_j':j+1,'restart_i':i+1,'before_sha256':before,'after_sha256':sha256(path),
            'fsd_policy':'preserve_source' if mode == 'negligible_area' else 'perturbed_or_zero_area'}


def check_abort(text):
    require('CICE COMPLETED SUCCESSFULLY' not in text, 'invalid case completed successfully')
    require(ABORT in text, 'expected collective mapping abort message absent')
    statuses = re.findall(r'dyntens invalid: rank, block, i, j, status=\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)', text)
    require(statuses and all(int(x[-1])==6 for x in statuses), 'missing/wrong occupied-FSD status 6')
    require(not re.search(r'walltime.*(exceed|limit)|TIME LIMIT|killed due to',text,re.I), 'timeout is not an accepted failure')
    return statuses


class InvalidStateWorkflow(EvidenceWorkflow):
    gate = 'B6.6-entry'
    pending = ('in-timestep injection', 'new-build B4 null and full B5 restart regression controls')

    def __init__(self,spec: WorkflowSpec, modes=MODES):
        self.spec = spec
        require(modes and len(set(modes)) == len(modes) and all(m in MODES for m in modes),
                'invalid/duplicate preparation modes')
        self.modes = tuple(modes)

    def prepare(self):
        repo,runs = self.spec.repo,self.spec.runs
        for layout in LAYOUTS:
            base = repo/base_name(layout)
            oldrun = runs/base.name
            require(Path(setting((base/'cice.settings').read_text(),'ICE_CASEDIR')) == base, 'use original B6.5 case')
            require(Path(setting((base/'cice.settings').read_text(),'ICE_RUNDIR')) == oldrun, 'base run path mismatch')
            require((oldrun/'cice').is_file(), 'accepted executable missing')
            clock(oldrun/'restart'/SOURCE,3,48)
            validate_source(oldrun/'restart'/SOURCE,oldrun/'history'/'iceh.2005-01-02.nc')
            template = (base/'ice_in').read_text()
            for key,want in [('use_dyntens','.false.'),('tr_fsd','.true.'),('nfsd','12'),('ndtd','1')]:
                require(entry(template,key).lower() == want, 'unexpected template '+key)
            for key,want in [('Ktens',.2),('dyntens_g_min',.2),('dyntens_diameter_threshold',300.),('dt',3600.)]:
                require(float(entry(template,key)) == want, 'unexpected template '+key)
            logs = list(oldrun.glob('cice.runlog.*'))
            require(any('CICE COMPLETED SUCCESSFULLY' in p.read_text(errors='replace') for p in logs), 'accepted control completion absent')
            for mode in self.modes:
                require(not (repo/case_name(mode,layout)).exists() and not (runs/case_name(mode,layout)).exists(), 'refusing existing case/run')
        # All destination checks above precede writes.
        for layout in LAYOUTS:
            base = repo/base_name(layout); oldrun = runs/base.name
            for mode in self.modes:
                case = repo/case_name(mode,layout); run = runs/case.name
                shutil.copytree(base,case,symlinks=True,ignore=shutil.ignore_patterns(
                    'b65-provenance','b65f-provenance','logs','history','restart','compile','input_restart',
                    '*-job-id.txt','*.gadi-pbs.*','*.log','*.o','*.mod'))
                for path in case.rglob('*'):
                    if path.is_file() and not path.is_symlink() and (path.suffix=='.csh' or path.name in ('cice.settings','cice.run','cice.submit','cice.build')):
                        text=path.read_text().replace(str(oldrun),str(run)).replace(str(base),str(case))
                        text=re.sub(r'(?m)^(\s*setenv\s+ICE_CASENAME\s+)\S+',lambda m:m[1]+case.name,text)
                        text=re.sub(r'(?m)^(#PBS\s+-N\s+)\S+',lambda m:m[1]+case.name,text)
                        path.write_text(text)
                text=(base/'ice_in').read_text()
                for key,value in [('npt','1'),('runtype',"'continue'"),('use_restart_time','.true.'),
                                  ('restart_fsd','.true.'),('use_dyntens_diagnostics','.true.'),('dyntens_box_fixture',"'none'")]:
                    text=set_entry(text,key,value)
                for key in ('f_dyntens_large_fraction','f_dyntens_g_candidate','f_ktens_eff_candidate','f_dyntens_mapping_status'):
                    text=set_entry(text,key,"'dh'")
                (case/'ice_in').write_text(text)
                (run/'input_restart').mkdir(parents=True)
                shutil.copy2(oldrun/'cice',run/'cice')
                target=run/'input_restart'/SOURCE
                shutil.copy2(oldrun/'restart'/SOURCE,target)
                record=perturb_restart(target,oldrun/'history'/'iceh.2005-01-02.nc',mode)
                require(record['before_sha256']==sha256(oldrun/'restart'/SOURCE), 'source restart copy mismatch')
                (run/'ice.restart_file').write_text(str(target)+'\n')
                provenance=case/'b66-provenance';provenance.mkdir()
                record.update(source_case=base.name, source_restart=str(oldrun/'restart'/SOURCE),
                              executable_sha256=sha256(run/'cice'), source=source_state(repo))
                (provenance/'input.json').write_text(json.dumps(record,indent=2)+'\n')
                for key in ('ice_in','cice.settings','cice.run','env.gadi1_intel','Macros.gadi1_intel'):
                    shutil.copy2(case/key,provenance/key)
                print('PREPARED',case.name,mode,'column',record['global_i'],'category',record['category'])
        print('No build required: reuse the accepted per-layout B6.5-F feedback-off executable. Inspect PBS/launcher before submission.')

    def analyse(self):
        repo,runs=self.spec.repo,self.spec.runs
        for layout in LAYOUTS:
            reference=runs/base_name(layout)
            for mode in MODES:
                name=case_name(mode,layout); run=runs/name
                record=json.loads((repo/name/'b66-provenance/input.json').read_text())
                require(sha256(run/'cice')==record['executable_sha256']==sha256(reference/'cice'),'executable changed')
                require(sha256(run/'input_restart'/SOURCE)==record['after_sha256'],'test input changed')
                logs=sorted(run.glob('cice.runlog.*'))
                require(len(logs)==1,'expected one model log per fresh case; inspect retries: '+name)
                text=logs[0].read_text(errors='replace')
                if mode in ('negative','nonfinite','bad_sum'):
                    ranks=check_abort(text)
                    require(len({x[0] for x in ranks})==1,'expected invalid input isolated to one task')
                    require(not list((run/'restart').glob('*.nc')),'invalid case advanced to output restart')
                    print('PASS expected restart-entry abort',name,'status=6; rank/block/local indices=',ranks)
                    continue
                require('CICE COMPLETED SUCCESSFULLY' in text,'completion absent '+name)
                want=expected_history(3,1,True)
                require({p.name for p in (run/'history').glob('*.nc')}==want,'history coverage '+name)
                with Dataset(run/'history'/IC) as ds:
                    check_dataset(ds,.2,.2,1e-10)
                    if mode != 'valid':
                        j,i=record['global_j']-1,record['global_i']-1
                        for suffix in ('','_h','_1'):
                            if 'dtens_status'+suffix not in ds.variables: continue
                            require(float(ds['dtens_status'+suffix][0,j,i])==1.,'expected inactive IC status '+name)
                            require(np.ma.is_masked(ds['dtens_flarge'+suffix][0,j,i]),'inactive IC fraction unmasked '+name)
                require({p.name for p in (run/'restart').glob('*.nc')}=={'iced.2005-01-04-00000.nc'},'restart coverage '+name)
                clock(run/'restart'/'iced.2005-01-04-00000.nc',4,72)
                for filename in sorted(want):
                    with Dataset(run/'history'/filename) as ds: check_dataset(ds,.2,.2,1e-10)
                if mode=='valid':
                    ic_mapping(run/'input_restart'/SOURCE,run/'history'/IC)
                    for filename in sorted(want-{IC}): compare(run/'history'/filename,reference/'history'/filename,candidates=False)
                    exact(run/'restart'/'iced.2005-01-04-00000.nc',reference/'restart'/'iced.2005-01-04-00000.nc')
                    print('PASS live diagnostic control continuity',name,'25 history pairs + one restart; IC independently reconstructed')
                else:
                    print('PASS inactive restart-entry IC and one-day completion',name,'not a physical-control equivalence test')
        print('PASS B6.6 restart-entry subset; full B6 acceptance still has pending gates:',', '.join(self.pending))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('prepare','analyse'))
    p.add_argument('--repo',type=Path)
    p.add_argument('--runs',type=Path,default=run_root())
    p.add_argument('--evidence',type=Path)
    p.add_argument('--modes',nargs='+',choices=MODES,help='prepare only selected fresh modes; analyse always checks all twelve cases')
    args=p.parse_args()
    if args.modes and args.action != 'prepare': p.error('--modes applies only to prepare')
    try:
        workflow=InvalidStateWorkflow(WorkflowSpec(args.repo or model_repo(),args.runs), args.modes or MODES)
        if args.evidence: workflow.run_with_evidence(args.action,args.evidence)
        else: getattr(workflow,args.action)()
    except (ValueError,OSError,KeyError) as exc: p.exit(1,'FAIL: '+str(exc)+'\n')

if __name__=='__main__': main()
