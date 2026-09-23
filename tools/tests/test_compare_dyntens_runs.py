"""Synthetic regressions for the numerical acceptance checker (no model run)."""
import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest

import numpy as np
from netCDF4 import Dataset

spec = importlib.util.spec_from_file_location('compare', Path(__file__).parents[1] / 'compare_dyntens_runs.py')
compare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compare)


class RunComparison(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.left = Path(self.tmp.name) / 'left'
        self.right = Path(self.tmp.name) / 'right'
        self.left.mkdir()
        (self.left / 'mpi_exit_status.txt').write_text('0\n')
        (self.left / 'cice').write_bytes(b'test executable')
        (self.left / 'input_restart').mkdir()
        (self.left / 'input_restart/iced.2000-09-01-00000.nc').write_bytes(b'identical input')
        for folder in ('history', 'restart'):
            (self.left / folder).mkdir()
            with Dataset(self.left / folder / 'state.nc', 'w') as ds:
                for name, size in [('ncat', 2), ('nj', 35), ('ni', 3)]:
                    ds.createDimension(name, size)
                ds.istep1 = 99456
                for name in ['aicen'] + [f'fsd{k:03d}' for k in range(1, 13)]:
                    var = ds.createVariable(name, 'f8', ('ncat', 'nj', 'ni'), fill_value=-999.)
                    var[:] = .2 if name == 'aicen' else 1 / 12
                ds['aicen'][:, 0, 0] = 0  # empty categories need not have unit FSD sums
                for k in range(1, 13):
                    ds[f'fsd{k:03d}'][:, 0, 0] = 0
        shutil.copytree(self.left, self.right)

    def mutate(self, name, value, both=False):
        for run in (self.left, self.right) if both else (self.right,):
            with Dataset(run / 'restart/state.nc', 'a') as ds:
                ds[name][1, 34, 2] = value  # exercise second row chunk

    def test_equal(self):
        compare.compare_runs(self.left, self.right, True)

    def test_changed_field(self):
        self.mutate('aicen', .3)
        with self.assertRaisesRegex(ValueError, 'numerical values differ'):
            compare.compare_runs(self.left, self.right)

    def test_changed_mask(self):
        self.mutate('aicen', -999.)
        with self.assertRaisesRegex(ValueError, 'masks differ'):
            compare.compare_runs(self.left, self.right)

    def test_equal_nonfinite_still_fails(self):
        self.mutate('fsd001', np.nan, both=True)
        with self.assertRaisesRegex(ValueError, 'nonfinite'):
            compare.compare_runs(self.left, self.right)

    def test_equal_bad_fsd_still_fails(self):
        self.mutate('fsd001', .5, both=True)
        with self.assertRaisesRegex(ValueError, 'FSD sum'):
            compare.compare_runs(self.left, self.right)

    def test_missing_output(self):
        (self.right / 'history/state.nc').unlink()
        with self.assertRaisesRegex(ValueError, 'output file sets'):
            compare.compare_runs(self.left, self.right)

    def test_date_counter(self):
        with Dataset(self.right / 'restart/state.nc', 'a') as ds:
            ds.istep1 = 99455
        with self.assertRaisesRegex(ValueError, 'istep1 differs'):
            compare.compare_runs(self.left, self.right)

    def test_executable(self):
        (self.right / 'cice').write_bytes(b'other build')
        with self.assertRaisesRegex(ValueError, 'Executable checksums'):
            compare.compare_runs(self.left, self.right, True)

    def test_input_restart(self):
        (self.right / 'input_restart/iced.2000-09-01-00000.nc').write_bytes(b'other input')
        with self.assertRaisesRegex(ValueError, 'Input restart checksums'):
            compare.compare_runs(self.left, self.right)


if __name__ == '__main__':
    unittest.main()
