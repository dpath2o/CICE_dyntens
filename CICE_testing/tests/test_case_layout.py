"""Case move isolation, immutable provenance, aliases and path-hash integrity."""
from pathlib import Path
import hashlib
import json
import tempfile
import unittest
from unittest.mock import patch
from CICE_testing.core.cases import case_path, classification, verify_input_hash
from CICE_testing.workflows.case_layout import CaseLayoutWorkflow

class Layout(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.repo=self.root/'repo';self.repo.mkdir()
        self.runs=self.root/'runs';self.runs.mkdir()
        (self.repo/'box01_tests').mkdir();(self.repo/'box01_tests/cases.json').write_text('{}')

    def make_case(self,name):
        case=self.repo/name;case.mkdir();run=self.runs/name;run.mkdir()
        (run/'cice').write_bytes(b'accepted executable')
        (run/'cice.runlog.1').write_text('original result')
        (case/'cice.settings').write_text(f'setenv ICE_CASEDIR {case}\nsetenv ICE_RUNDIR {run}\nsetenv ICE_CASENAME {name}\nsetenv ICE_NTASKS 2\n')
        (case/'cice.run').write_text(f'#PBS -N {name}\ncd {case}\n')
        (case/'ice_in').write_text('Ktens = .2\nuse_dyntens = .false.\n')
        provenance=case/'b65f-provenance';provenance.mkdir()
        (provenance/'cice.settings').write_bytes((case/'cice.settings').read_bytes())
        (case/'active-link').symlink_to(case/'cice.settings')
        return case

    def test_move_retains_run_and_provenance_and_rejects_physics_change(self):
        case=self.make_case('dt_b65f_large_off_m2')
        old=(case/'cice.settings').read_bytes();digest=hashlib.sha256(old).hexdigest()
        (self.repo/'caselist.123').write_text(str(case)+'\n')
        backup=self.root/'backup';work=CaseLayoutWorkflow(self.repo,self.runs)
        plan=work.apply(backup)
        target=case_path(self.repo,case.name)
        self.assertEqual(target,self.repo/'box01_tests/B6.5-F'/case.name)
        self.assertFalse(case.exists());self.assertEqual((backup/case.name/'cice.settings').read_bytes(),old)
        self.assertEqual((target/'b65f-provenance/cice.settings').read_bytes(),old)
        self.assertEqual((self.runs/case.name/'cice').read_bytes(),b'accepted executable')
        self.assertEqual((target/'active-link').resolve(),target/'cice.settings')
        self.assertTrue(verify_input_hash(target,'cice.settings',digest))
        with (target/'cice.settings').open('a') as out:out.write('setenv ICE_NTASKS 999\n')
        self.assertFalse(verify_input_hash(target,'cice.settings',digest))
        registry=json.loads((self.repo/'box01_tests/_legacy_registry/case_creation_records.json').read_text())
        self.assertEqual(registry[0]['original_text'],str(case)+'\n')
        self.assertEqual(registry[0]['relocated_text'],str(target)+'\n')
        self.assertFalse(plan['runs_moved'])

    def test_b3_name_is_band_not_b67_stage(self):
        case=self.make_case('dt_b67_m2');CaseLayoutWorkflow(self.repo,self.runs).apply(self.root/'backup')
        target=case_path(self.repo,'dt_b67_m2')
        self.assertEqual(target.name,'dt_b3_band67_m2')
        text=(target/'cice.settings').read_text()
        self.assertIn('ICE_CASENAME dt_b3_band67_m2',text)
        self.assertIn(str(self.runs/'dt_b67_m2'),text)
        self.assertIn('dt_b3_band67_m2',(target/'cice.run').read_text())
        self.assertEqual(classification('dt_b6_s1')[1],'B3')

    def test_collision_preflight_writes_nothing(self):
        case=self.make_case('dt_b65_ctl_s1')
        target=self.repo/'box01_tests/B6.5'/case.name;target.mkdir(parents=True)
        work=CaseLayoutWorkflow(self.repo,self.runs)
        with self.assertRaisesRegex(ValueError,'destination'):work.apply(self.root/'backup')
        self.assertFalse((self.root/'backup').exists());self.assertTrue(case.exists())
        with self.assertRaisesRegex(ValueError,'ambiguous'):case_path(self.repo,case.name)

    def test_interrupted_move_keeps_backup_and_blocks_retry(self):
        case=self.make_case('dt_b66_valid_s1')
        work=CaseLayoutWorkflow(self.repo,self.runs)
        with patch('CICE_testing.workflows.case_layout.shutil.move',side_effect=OSError('simulated filesystem failure')):
            with self.assertRaisesRegex(OSError,'filesystem'):work.apply(self.root/'backup')
        self.assertTrue((self.root/'backup'/case.name/'ice_in').exists())
        self.assertTrue(case.exists())
        with self.assertRaisesRegex(ValueError,'incomplete migration'):work.plan()

    def test_nested_new_destinations_and_unknown_case(self):
        self.assertEqual(case_path(self.repo,'dt_b66_valid_s1'),self.repo/'box01_tests/B6.6/dt_b66_valid_s1')
        self.assertEqual(case_path(self.repo,'dyntens01'),self.repo/'global_tests/G0/dyntens01')
        with self.assertRaisesRegex(ValueError,'unclassified'):classification('dt_b68_s1')

if __name__=='__main__':unittest.main()
