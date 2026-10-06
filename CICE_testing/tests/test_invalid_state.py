"""Synthetic tests of restart-copy mutations and expected-abort evidence."""
from pathlib import Path
import shutil
import tempfile
import unittest
import numpy as np
from netCDF4 import Dataset
from CICE_testing.workflows.invalid_state import perturb_restart, validate_source, check_abort, ABORT, InvalidStateWorkflow, MODES, case_name, base_name
from CICE_testing import WorkflowSpec
from contextlib import redirect_stdout
import io
import json

class RestartEntry(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.history=self.root/'history.nc';self.source=self.root/'source.nc'
        with Dataset(self.history,'w') as d:
            d.createDimension('nj',12);d.createDimension('ni',12)
            d.createVariable('tmask','f8',('nj','ni'))[:]=1.
        with Dataset(self.source,'w') as d:
            for key,size in [('ncat',2),('nj',14),('ni',14)]:d.createDimension(key,size)
            for key in ('aicen','vicen','vsnon'):d.createVariable(key,'f8',('ncat','nj','ni'))[:]=.3
            for k in range(1,13):d.createVariable(f'fsd{k:03d}','f8',('ncat','nj','ni'))[:]=1. if k==1 else 0.

    def test_valid_source_and_isolated_invalid_mutations(self):
        validate_source(self.source,self.history)
        for mode in ('negative','nonfinite','bad_sum'):
            target=self.root/(mode+'.nc');shutil.copy2(self.source,target)
            record=perturb_restart(target,self.history,mode)
            self.assertEqual(record['global_i'],7)
            self.assertEqual(record['restart_i'],8)
            with self.assertRaises(ValueError):validate_source(target,self.history)
        validate_source(self.source,self.history)

    def test_inactive_area_and_volume_scaling(self):
        for mode,total in [('zero_area',0.),('negligible_area',5e-13)]:
            target=self.root/(mode+'.nc');shutil.copy2(self.source,target)
            record=perturb_restart(target,self.history,mode)
            j,i=record['restart_j']-1,record['restart_i']-1
            with Dataset(target) as d:
                self.assertAlmostEqual(float(d['aicen'][:,j,i].sum()),total,delta=1e-25)
                np.testing.assert_allclose(d['vicen'][:,j,i],d['aicen'][:,j,i],rtol=0,atol=0)
            validate_source(target,self.history)

    def test_prepare_preserves_sources_layouts_and_refuses_repeat(self):
        repo=self.root/'model';runs=self.root/'runs';repo.mkdir();runs.mkdir()
        template="""use_dyntens = .false.
tr_fsd = .true.
nfsd = 12
ndtd = 1
Ktens = .2
dyntens_g_min = .2
dyntens_diameter_threshold = 300.
dt = 3600.
npt = 5
runtype = 'initial'
use_restart_time = .false.
restart_fsd = .false.
use_dyntens_diagnostics = .false.
dyntens_box_fixture = 'none'
f_dyntens_large_fraction = 'x'
f_dyntens_g_candidate = 'x'
f_ktens_eff_candidate = 'x'
f_dyntens_mapping_status = 'x'
"""
        source_bytes=self.source.read_bytes()
        for layout in ('s1','m2'):
            case=repo/base_name(layout);run=runs/case.name;case.mkdir()
            (run/'restart').mkdir(parents=True);(run/'history').mkdir()
            (case/'ice_in').write_text(template)
            (case/'cice.settings').write_text(f'setenv ICE_CASEDIR {case}\nsetenv ICE_RUNDIR {run}\nsetenv ICE_CASENAME {case.name}\n')
            (case/'cice.run').write_text(f'#PBS -N {case.name}\ncd {run}\n')
            for key in ('env.gadi1_intel','Macros.gadi1_intel'):(case/key).write_text('test environment')
            (case/'b65f-provenance').mkdir()
            (case/'b65f-provenance/input.json').write_text('{}')
            (case/'180000.gadi-pbs.OU').write_text('old scheduler output')
            (case/'b65f-job-id.txt').write_text('old job id')
            (run/'cice').write_text('layout '+layout)
            (run/'cice.runlog.test').write_text('CICE COMPLETED SUCCESSFULLY')
            shutil.copy2(self.history,run/'history/iceh.2005-01-02.nc')
            target=run/'restart/iced.2005-01-03-00000.nc';shutil.copy2(self.source,target)
            with Dataset(target,'a') as d:
                for key,value in dict(myear=2005,mmonth=1,mday=3,msec=0,istep1=48).items():d.setncattr(key,value)
        workflow=InvalidStateWorkflow(WorkflowSpec(repo,runs))
        with redirect_stdout(io.StringIO()):workflow.prepare()
        for layout in ('s1','m2'):
            for mode in MODES:
                name=case_name(mode,layout)
                self.assertEqual((runs/name/'cice').read_text(),'layout '+layout)
                text=(repo/name/'cice.settings').read_text()
                self.assertIn(str(runs/name),text)
                self.assertNotIn('dt_b65f_large_off',text)
                self.assertFalse((repo/name/'b65f-provenance').exists())
                self.assertFalse((repo/name/'180000.gadi-pbs.OU').exists())
                self.assertFalse((repo/name/'b65f-job-id.txt').exists())
                record=json.loads((repo/name/'b66-provenance/input.json').read_text())
                self.assertEqual(record['global_i'],7)
                self.assertEqual(record['mode'],mode)
                self.assertEqual(record['source_case'],base_name(layout))
        self.assertEqual(self.source.read_bytes(),source_bytes)
        with self.assertRaisesRegex(ValueError,'existing'):workflow.prepare()

    def test_abort_requires_specific_status_and_no_success(self):
        text='dyntens invalid: rank, block, i, j, status= 1 2 3 4 6\n'+ABORT
        self.assertEqual(check_abort(text)[0][0],'1')
        for bad in ('generic abort',text.replace('4 6','4 5'),text+'\nCICE COMPLETED SUCCESSFULLY',text+'\nwalltime limit exceeded'):
            with self.assertRaises(ValueError):check_abort(bad)

if __name__=='__main__':unittest.main()
