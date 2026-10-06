"""Portability, configuration and evidence regression tests."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from CICE_testing import CandidateSpec, SpatialSpec, WorkflowSpec, TestingPaths as Paths
from CICE_testing.core.paths import model_repo
from CICE_testing.core.reporting import EvidenceWorkflow
from CICE_testing.workflows.box import BoxWorkflow, ROWS
from CICE_testing.workflows.restart import RestartWorkflow
from CICE_testing.workflows.fortran_mapping import MappingFixtures, fixtures
from importlib.resources import files


class PackageTests(unittest.TestCase):
    def test_explicit_checkout_and_run_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec = WorkflowSpec(Path(tmp)/'model',Path(tmp)/'runs')
            self.assertEqual(BoxWorkflow(spec).spec.repo,Path(tmp)/'model')
            self.assertEqual(RestartWorkflow(spec).spec.runs,Path(tmp)/'runs')
            with patch.dict('os.environ', {'CICE_MODEL_REPO': str(spec.repo)}):
                self.assertEqual(model_repo(),spec.repo)
            paths=Paths(Path(tmp)/'reports','global')
            self.assertEqual(paths.figures,Path(tmp)/'reports/global/figures')

    def test_specs_reject_invalid_parameters(self):
        for kw in ({'atol':-1},{'ktens':float('nan')},{'gmin':1.1}):
            with self.assertRaises(ValueError): CandidateSpec(**kw)
        with self.assertRaises(ValueError): SpatialSpec('box_band',.2,ilo=7,ihi=6)
        with self.assertRaises(ValueError): SpatialSpec('constant',float('inf'))

    def test_compiler_driver_is_package_resource(self):
        self.assertIn('program',files('CICE_testing.resources').joinpath('b6_mapping_driver.F90').read_text().lower())
        self.assertEqual(len(fixtures()),67)
        self.assertEqual(len(ROWS),14)

    def test_failed_gate_writes_fail_and_preserves_exception(self):
        class Fake(EvidenceWorkflow):
            gate='B6.5'
            pending=('B6.6',)
            def analyse(self):
                print('checking real inputs')
                raise ValueError('missing hourly file')
        with tempfile.TemporaryDirectory() as tmp:
            workflow=Fake();workflow.spec=WorkflowSpec(tmp,Path(tmp)/'runs')
            with self.assertRaisesRegex(ValueError,'missing hourly'):
                workflow.run_with_evidence('analyse',Path(tmp)/'evidence')
            report=json.loads((Path(tmp)/'evidence/b65-validation.json').read_text())
            self.assertEqual(report['status'],'FAIL')
            self.assertEqual(report['pending'],['B6.6'])
            self.assertIn('checking real inputs',Path(report['transcript']).read_text())
            with self.assertRaises(ValueError): workflow.run_with_evidence('prepare',tmp)

    def test_pass_applies_only_to_current_gate(self):
        class Fake(EvidenceWorkflow):
            gate='B6.4'; pending=('B6.5-F','B6.6')
            def analyse(self): print('test transcript');return 17
        with tempfile.TemporaryDirectory() as tmp:
            workflow=Fake();workflow.spec=WorkflowSpec(tmp,Path(tmp)/'runs')
            self.assertEqual(workflow.run_with_evidence('analyse',tmp),17)
            report=json.loads((Path(tmp)/'b64-validation.json').read_text())
            self.assertEqual(report['status'],'PASS')
            self.assertEqual(report['pending'],['B6.5-F','B6.6'])

if __name__=='__main__': unittest.main()
