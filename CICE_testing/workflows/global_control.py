"""G0: fresh two-day global off/unity controls on one executable."""
import argparse
import importlib.util
import json
import re
import shutil
from pathlib import Path

from ..core.types import WorkflowSpec
from ..core.reporting import EvidenceWorkflow, sha256, source_state
from .restart import entry, set_entry, setting, require
from .feedback import put

NAMES = ('dt_g0_off', 'dt_g0_unity')
INPUT = 'iced.2000-09-01-00000.nc'


def nonempty_path(value):
    if not value.strip():
        raise argparse.ArgumentTypeError('path is empty; set --runs explicitly in this shell')
    return Path(value)


def check_completion(run, namelist):
    """Read CICE's configured diagnostic destination, retaining retry checks."""
    logs = list(run.glob('cice.runlog.*'))
    require(len(logs) == 1, 'expected one launch log; inspect missing logs or retries: '+str(run))
    kind = entry(namelist, 'diag_type').strip("'\"").lower()
    if kind == 'file':
        target = (run/entry(namelist, 'diag_file').strip("'\"")).resolve()
        require(target.is_relative_to(run.resolve()), 'diagnostic file must remain inside run directory')
        require(target.is_file(), 'missing configured diagnostic file: '+str(target))
    elif kind == 'stdout':
        target = logs[0]
    else:
        raise ValueError('unsupported diagnostic destination '+kind)
    require('CICE COMPLETED SUCCESSFULLY' in target.read_text(errors='replace'),
            'model completion missing: '+str(target))
    print('PASS model completion', target)


def configure(text, enabled):
    """Change run controls only; retain the inherited physical configuration."""
    for key, value in dict(npt='2', npt_unit="'d'", runtype="'initial'",
                           ice_ic="'./input_restart/"+INPUT+"'",
                           use_restart_time='.true.').items():
        text = set_entry(text, key, value)
    for key, value in dict(use_dyntens='.true.' if enabled else '.false.',
                           dyntens_g_const='1.0', dyntens_g_mode="'constant'",
                           use_dyntens_diagnostics='.false.').items():
        text = put(text, key, value)
    return text


def launch(case, header, machcomp, tasks):
    return '\n'.join(['#!/bin/csh -f', *header,
        'source /etc/profile.d/modules.csh', f'cd {case}',
        'source ./cice.settings || exit 2',
        f'source ./env.{machcomp} || exit 2',
        'cd ${ICE_RUNDIR}',
        'cp -p ${ICE_CASEDIR}/ice_in ./ice_in',
        'cp -p ${ICE_CASEDIR}/cice.settings ./cice.settings',
        'setenv OMP_NUM_THREADS ${ICE_NTHRDS}',
        'setenv OMP_SCHEDULE "${ICE_OMPSCHED}"',
        'set stamp = `date +%y%m%d-%H%M%S`',
        'set log = "cice.runlog.${stamp}"',
        f'mpirun -np {tasks} ./cice >&! $log',
        'set result = $status',
        'echo $result >! mpi_exit_status.txt',
        'cp -p $log ${ICE_LOGDIR}/',
        'exit $result', ''])


class GlobalControlWorkflow(EvidenceWorkflow):
    gate = 'G0-short'
    pending = ('comparison with pre-development executable, if available',
               'G1 evolving-FSD policy and diagnostic-only verification',
               'G2 supported global feedback and scientific evaluation')

    def __init__(self, spec):
        self.spec = spec

    def run_with_evidence(self, action, output):
        try:
            return super().run_with_evidence(action, output)
        finally:
            path = Path(output).expanduser().resolve()/'g0-short-validation.json'
            if path.exists():
                record = json.loads(path.read_text())
                record['scope'] = 'two-day off/unity identity; not full G0 scientific acceptance'
                record['executables'] = {str(self.spec.runs/name/'cice'): sha256(self.spec.runs/name/'cice')
                                         for name in NAMES if (self.spec.runs/name/'cice').is_file()}
                path.write_text(json.dumps(record, indent=2)+'\n')

    def prepare(self, restart):
        from netCDF4 import Dataset
        repo, runs = self.spec.repo, self.spec.runs
        template = self.spec.base_case or repo/'global_tests/G0/dyntens01'
        restart = Path(restart).expanduser().resolve()
        require(restart.is_file(), 'input restart not found: '+str(restart))
        require(restart.name == INPUT, 'this first G0 test requires '+INPUT)
        text = (template/'ice_in').read_text()
        settings = (template/'cice.settings').read_text()
        require((int(entry(text, 'nx_global')), int(entry(text, 'ny_global'))) == (1440, 1080),
                'expected the inherited 1440x1080 global grid')
        require(entry(text, 'atm_data_type').strip("'") == 'ERA5', 'expected ERA5')
        require(entry(text, 'ocn_data_type').strip("'") == 'AFIM', 'expected inherited AFIM ocean reader')
        require(entry(text, 'tr_fsd').lower() == '.true.', 'inherited FSD must remain enabled')
        require(float(entry(text, 'dt')) == 1800., 'this first test expects a 30-minute timestep')
        require([int(entry(text, k)) for k in ('year_init', 'month_init', 'day_init', 'sec_init')] == [2000, 9, 1, 0], 'unexpected initial date')
        require(entry(text, 'histfreq').replace(' ', '').startswith("'d','x'"), 'expected daily-only history')
        require(entry(text, 'dumpfreq').replace(' ', '').startswith("'d','x'"), 'expected daily-only restart')
        require(entry(text, 'write_ic').lower() == '.true.', 'initial history required')
        require(not re.search(r"(?im)^\s*thermo_type\s*=\s*'none'", text), 'box thermodynamics setting')
        for key in ('grid_file', 'kmt_file', 'atm_data_dir', 'ocn_data_dir'):
            path = Path(entry(text, key).strip("'\""))
            require(path.exists(), 'missing inherited input '+key+': '+str(path))
        with Dataset(restart) as ds:
            require('aicen' in ds.variables, 'restart has no category area')
            require(ds['aicen'].shape[-2:] in ((1080, 1440), (1082, 1442)), 'restart is not global')
            clock = [int(ds.getncattr(next(k for k in keys if k in ds.ncattrs())))
                     for keys in [('myear', 'nyr'), ('mmonth', 'month'), ('mday',), ('msec', 'sec')]]
            require(clock == [2000, 9, 1, 0], 'wrong input restart clock: '+str(clock))
            first_step = int(ds.getncattr('istep1'))
        tasks = int(setting(settings, 'ICE_NTASKS'))
        require(tasks > 1, 'global MPI case requires more than one task')
        machcomp = setting(settings, 'ICE_MACHCOMP')
        required = ['cice.build', 'Makefile', 'makdep.c', 'Macros.'+machcomp, 'env.'+machcomp]
        require(all((template/f).is_file() for f in required), 'incomplete build template')
        for name in NAMES:
            require(not (repo/'global_tests/G0'/name).exists() and not (runs/name).exists(),
                    'refusing existing case/run '+name)
        require(all(not re.search(r'[\s\x27\x22`$]', str(p)) for p in (repo, runs)), 'unsupported shell path')
        header = [l for l in (template/'cice.run').read_text().splitlines() if l.startswith('#PBS')]
        storage = sorted({x for l in header if 'storage=' in l for x in l.split('storage=', 1)[1].split('+')})
        header = [l for l in header if 'storage=' not in l and not l.startswith('#PBS -N')]
        if storage:
            header.append('#PBS -l storage='+'+'.join(storage))
        require(any(re.fullmatch(r'#PBS -l ncpus='+str(tasks), l) for l in header), 'PBS/task mismatch')
        source = sha256(restart)
        for name, enabled in zip(NAMES, (False, True)):
            case, run = repo/'global_tests/G0'/name, runs/name
            case.mkdir(parents=True)
            for folder in ('input_restart', 'history', 'restart'):
                (run/folder).mkdir(parents=True)
            (case/'logs').mkdir()
            for file in required:
                shutil.copy2(template/file, case/file)
            changes = dict(ICE_CASENAME=name, ICE_SANDBOX=str(repo),
                           ICE_SCRIPTS=str(repo/'configuration/scripts'), ICE_CASEDIR=str(case),
                           ICE_RUNDIR=str(run), ICE_GRID='global_1440x1080', ICE_CLEANBUILD='true')
            patched = settings
            for key, value in changes.items():
                patched, count = re.subn(r'(?m)^\s*setenv\s+'+key+r'\s+[^\n]*',
                                         lambda m: 'setenv '+key+' '+value, patched)
                require(count == 1, 'missing/duplicate setting '+key)
            (case/'cice.settings').write_text(patched)
            (case/'ice_in').write_text(configure(text, enabled))
            (case/'cice.run').write_text(launch(case, ['#PBS -N '+name, *header], machcomp, tasks))
            (case/'cice.run').chmod(0o755)
            shutil.copy2(restart, run/'input_restart'/INPUT)
            record = dict(template=str(template), source_restart=str(restart),
                          input_sha256=source, ice_in_sha256=sha256(case/'ice_in'),
                          settings_sha256=sha256(case/'cice.settings'),
                          launcher_sha256=sha256(case/'cice.run'), source=source_state(repo),
                          first_step=first_step,
                          wave_spec_type=entry(text, 'wave_spec_type'), tasks=tasks)
            (case/'g0-input.json').write_text(json.dumps(record, indent=2)+'\n')
            print('PREPARED', name, 'tasks='+str(tasks), 'wave_spec_type='+record['wave_spec_type'])
        print('Build off once; copy that executable to unity before submission.')

    def analyse(self):
        from netCDF4 import Dataset
        # Reuse the exact chunked NetCDF comparator, without its G1 FSD-sum gate.
        spec = importlib.util.spec_from_file_location('g0_exact', self.spec.repo/'tools/compare_dyntens_runs.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        records = []
        for name in NAMES:
            case, run = self.spec.repo/'global_tests/G0'/name, self.spec.runs/name
            record = json.loads((case/'g0-input.json').read_text())
            for file, key in [('ice_in', 'ice_in_sha256'), ('cice.settings', 'settings_sha256'), ('cice.run', 'launcher_sha256')]:
                require(sha256(case/file) == record[key], 'prepared configuration changed: '+name+'/'+file)
            require(sha256(run/'ice_in') == record['ice_in_sha256'], 'run namelist differs '+name)
            require(sha256(run/'input_restart'/INPUT) == record['input_sha256'], 'input changed '+name)
            require((run/'mpi_exit_status.txt').read_text().strip() == '0', 'MPI failed '+name)
            check_completion(run, (run/'ice_in').read_text())
            want_h = {'iceh_ic.2000-09-01-00000.nc', 'iceh.2000-09-01.nc', 'iceh.2000-09-02.nc'}
            want_r = {'iced.2000-09-02-00000.nc', 'iced.2000-09-03-00000.nc'}
            require({p.name for p in (run/'history').glob('*.nc')} == want_h, 'history coverage '+name)
            require({p.name for p in (run/'restart').glob('*.nc')} == want_r, 'restart coverage '+name)
            for day in (2, 3):
                with Dataset(run/'restart'/f'iced.2000-09-{day:02d}-00000.nc') as ds:
                    values = [int(ds.getncattr(k)) for k in ('myear', 'mmonth', 'mday', 'msec', 'istep1')]
                    require(values == [2000, 9, day, 0, record['first_step']+48*(day-1)], 'incorrect restart clock '+name)
            for file in (run/'history').glob('*.nc'):
                with Dataset(file) as ds:
                    require(len(ds.dimensions['nj']) == 1080 and len(ds.dimensions['ni']) == 1440, 'output is not global '+name)
                    require(all(k in ds.variables for k in ('aice', 'hi', 'hs', 'Tsfc', 'uvel', 'vvel')), 'missing physical history fields '+name)
            records.append(record)
        require(records[0]['input_sha256'] == records[1]['input_sha256'], 'different starting restarts')
        left, right = [self.spec.runs/n for n in NAMES]
        require(sha256(left/'cice') == sha256(right/'cice'), 'different executables')
        print('EXECUTABLE', sha256(left/'cice'))
        for folder in ('history', 'restart'):
            for file in sorted((left/folder).glob('*.nc')):
                module.compare_nc(file, right/folder/file.name)
                print('PASS exact', folder, file.name)
        print('PASS G0-short: off/unity output equality on the two-day inherited global configuration.')
        print('FSD sum policy, inherited-build comparison and wider global physics assessment are not certified here.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['prepare', 'analyse'])
    p.add_argument('--repo', type=Path, required=True)
    p.add_argument('--runs', type=nonempty_path, required=True)
    p.add_argument('--template', type=Path)
    p.add_argument('--restart', type=Path)
    p.add_argument('--evidence', type=Path)
    a = p.parse_args()
    workflow = GlobalControlWorkflow(WorkflowSpec(a.repo, a.runs, a.template))
    try:
        if a.action == 'prepare':
            require(a.restart is not None, '--restart required for prepare')
            workflow.prepare(a.restart)
        elif a.evidence:
            workflow.run_with_evidence('analyse', a.evidence)
        else:
            workflow.analyse()
    except (ValueError, OSError, KeyError, StopIteration) as exc:
        p.exit(1, 'FAIL: '+str(exc)+'\n')
