"""Feedback gate regressions: independent controls, physical response and isolation."""
from contextlib import redirect_stdout
import io
from pathlib import Path
import shutil
from CICE_testing.core.cases import case_path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from netCDF4 import Dataset
from CICE_testing.core.types import WorkflowSpec
from CICE_testing.workflows import feedback as w


class Feedback(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def history(self, path, fixture, mapped=True, response=True):
        g = float(w.G[fixture])
        with Dataset(path, 'w') as d:
            for k, n in [('time',1),('nj',2),('ni',2)]:
                d.createDimension(k,n)
            d.createVariable('tmask','f8',('nj','ni'))[:] = [[0.,1.],[1.,1.]]
            fields = {'dyntens_g':g, 'ktens_eff':.2*g, 'uvel':g if response else 1.}
            if mapped:
                fields.update(dtens_flarge=dict(small=0.,large=1.,mixed=.5)[fixture],
                              dtens_gcand=g, ktens_cand=.2*g, dtens_status=0.)
            for suffix in ('','_h'):
                for key, value in fields.items():
                    d.createVariable(key+suffix,'f8',('time','nj','ni'),fill_value=-999.)[:] = value

    def test_feedback_checks_reject_unapplied_mapping(self):
        path = self.root/'mixed.nc'
        self.history(path,'mixed')
        with Dataset(path) as d:
            w.check_mapped(d,'mixed')
        with Dataset(path,'a') as d:
            for suffix in ('','_h'):
                d['dyntens_g'+suffix][:] = 1.
                d['ktens_eff'+suffix][:] = .2
        with Dataset(path) as d:
            with self.assertRaisesRegex(ValueError,'applied'):
                w.check_mapped(d,'mixed')

    def test_exact_pair_excludes_only_candidate_fields(self):
        a,b = self.root/'map.nc',self.root/'ref.nc'
        self.history(a,'small')
        self.history(b,'small',mapped=False)
        w.compare(a,b,candidates=False)
        with Dataset(b,'a') as d:
            d['uvel'][0,0,1] += 1.e-12
        with self.assertRaisesRegex(ValueError,'exact values differ uvel'):
            w.compare(a,b,candidates=False)

    def test_response_requires_physics_not_coefficient_change(self):
        a,b = self.root/'small.nc',self.root/'large.nc'
        self.history(a,'small',response=False)
        self.history(b,'large',response=False)
        self.assertIsNone(w.physical_difference(a,b))
        with Dataset(a,'a') as d:
            d['uvel'][0,0,1] = .1
        self.assertEqual(w.physical_difference(a,b),'uvel')

    def test_prepare_and_distribute_isolate_accepted_matrix(self):
        repo,runs = self.root/'repo',self.root/'runs'
        repo.mkdir(); runs.mkdir()
        values = dict(use_dyntens='.false.', tr_fsd='.true.', nfsd='12', ndtd='1',
                      year_init='2005', day_init='1', ice_ic="'internal'", npt_unit="'d'",
                      diag_type="'stdout'", dt='3600', Ktens='.2', dyntens_g_min='.2',
                      dyntens_diameter_threshold='300', npt='5', runtype="'initial'",
                      use_restart_time='.false.',restart_fsd='.false.',use_dyntens_diagnostics='.false.')
        for k in ('f_dyntens_large_fraction','f_dyntens_g_candidate',
                  'f_ktens_eff_candidate','f_dyntens_mapping_status'):
            values[k]="'x'"
        original = '&domain_nml\n /\n&dynamics_nml\n'+''.join(' '+k+' = '+v+'\n' for k,v in values.items())+' /\n'
        for layout in w.LAYOUTS:
            case=repo/('dt_b65_ctl_'+layout);case.mkdir()
            (case/'ice_in').write_text(original)
            (case/'cice.settings').write_text('setenv ICE_CASEDIR '+str(case)+'\n')
            for filename in ('env.gadi1_intel','Macros.gadi1_intel'):
                (case/filename).write_text(layout)
            run=runs/case.name;run.mkdir()
            (run/'cice.runlog.1').write_text('CICE COMPLETED SUCCESSFULLY')
        def setup(command, **kwargs):
            case=repo/command[command.index('-c')+1];case.mkdir()
            (case/'ice_in').write_text('&domain_nml\n /\n')
            (case/'cice.settings').write_text('setenv ICE_RUNDIR '+str(runs/case.name)+'\n')
            (case/'cice.run').write_text('#PBS -l ncpus=999\n#PBS -l mem=1gb\n#PBS -l walltime=01:00:00\n')
        # Exercise the organised creation path using migrated control templates.
        (repo/'box01_tests').mkdir();(repo/'box01_tests/cases.json').write_text('{}')
        for layout in w.LAYOUTS:
            old=repo/('dt_b65_ctl_'+layout)
            new=repo/'box01_tests/B6.5'/old.name;new.parent.mkdir(parents=True,exist_ok=True)
            shutil.move(old,new)
            (new/'cice.settings').write_text('setenv ICE_CASEDIR '+str(new)+'\n')
        workflow=w.FeedbackWorkflow(WorkflowSpec(repo,runs))
        with patch.object(w.subprocess,'run',side_effect=setup), patch.object(w,'source_state',return_value={}), redirect_stdout(io.StringIO()):
            workflow.prepare()
        self.assertEqual(len(w.ROWS),21)
        for row in w.ROWS:
            text=(case_path(repo,w.name(row))/'ice_in').read_text()
            self.assertEqual(w.entry(text,'use_dyntens'),'.false.' if row[1]=='off' else '.true.')
            if row[1]=='map':
                self.assertEqual(w.entry(text,'dyntens_g_mode'),"'box_fsd'")
                self.assertEqual(w.entry(text,'dyntens_box_fixture'),"'"+row[0]+"'")
            elif row[1]=='ref':
                self.assertEqual(w.entry(text,'dyntens_g_mode'),"'box_constant'")
                self.assertEqual(w.entry(text,'dyntens_box_fixture'),"'none'")
            self.assertEqual(w.entry(text,'dyntens_g_const'),w.G[row[0]])
        for layout in w.LAYOUTS:
            run=runs/w.name(('large','ref',layout));run.mkdir()
            (run/'cice').write_bytes(layout.encode())
        with redirect_stdout(io.StringIO()):
            workflow.distribute()
        for row in w.ROWS:
            self.assertEqual((runs/w.name(row)/'cice').read_bytes(),row[2].encode())
        for layout in w.LAYOUTS:
            self.assertEqual((case_path(repo,'dt_b65_ctl_'+layout)/'ice_in').read_text(),original)
        with self.assertRaisesRegex(ValueError,'refusing existing'):
            workflow.prepare()

    def test_production_feedback_order_and_box_guards(self):
        repo=Path(__file__).resolve().parents[2]
        evp=(repo/'cicecore/cicedyn/dynamics/ice_dyn_evp.F90').read_text()
        init=(repo/'cicecore/cicedyn/general/ice_init.F90').read_text()
        driver=(repo/'cicecore/drivers/standalone/cice/CICE_InitMod.F90').read_text()
        branch=evp[evp.index("if (trim(dyntens_g_mode) == 'box_fsd' .or."):evp.index('dyntens_gT = dyntens_g_const')]
        self.assertIn('dyntens_gT(i,j,iblk) = dyntens_g_candidateT(i,j,iblk)',branch)
        self.assertIn('fillValue = c1',branch)
        self.assertIn('return',branch)
        self.assertIn("box_fsd requires small, large or mixed shadow fixture",init)
        self.assertIn('B6.5-F modes require 12x12 box',evp)
        pos=driver.index('call init_restart ')
        self.assertLess(driver.index('call update_dyntens_candidates()',pos),
                        driver.index('call update_dyntens_coefficients()',pos))


if __name__ == '__main__':
    unittest.main()
