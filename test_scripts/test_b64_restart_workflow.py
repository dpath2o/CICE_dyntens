#!/usr/bin/env python3
"""Synthetic regression tests for restart coverage, phase alignment and failures."""
import contextlib
import io
from pathlib import Path
import tempfile
import shutil
from types import SimpleNamespace
import unittest
import numpy as np
from netCDF4 import Dataset
import b64_restart_workflow as w


class RestartWorkflow(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.args = SimpleNamespace(repo=Path(__file__).resolve().parents[1], runs=self.root)
        for case, first, days in zip(w.CASES, [1, 1, 3], [5, 2, 3]):
            run = self.root / case
            (run / 'history').mkdir(parents=True)
            (run / 'restart').mkdir()
            (run / 'cice').write_bytes(b'same executable')
            for name in w.expected_history(first, days, True):
                self.history(run / 'history' / name)
            for day in range(first+1, first+days+1):
                self.restart(run / 'restart' / ('iced.2005-01-%02d-00000.nc' % day), day)
        staged = self.root / w.CASES[2] / 'input_restart'
        staged.mkdir()
        source = self.root / w.CASES[1] / 'restart' / ('iced.' + w.SPLIT + '.nc')
        (staged / source.name).write_bytes(source.read_bytes())
        # The old pre-EVP candidate differs from the restored end-step mapping.
        for case in w.CASES[:2]:
            self.set_fraction(self.root / case / 'history' / ('iceh_inst.' + w.SPLIT + '.nc'), .5)

    def tearDown(self):
        self.temp.cleanup()

    def history(self, path):
        with Dataset(path, 'w') as d:
            for name, size in [('time', 1), ('nj', 2), ('ni', 2)]:
                d.createDimension(name, size)
            d.createVariable('tmask', 'f8', ('nj', 'ni'))[:] = [[1, 1], [0, 0]]
            for name, data in [('dtens_flarge', [[.25, -999.], [0., 0.]]),
                               ('dtens_gcand', [[.4, 1.], [0., 0.]]),
                               ('ktens_cand', [[.08, .2], [0., 0.]]),
                               ('dtens_status', [[0., 1.], [0., 0.]]),
                               ('dyntens_g', [[1., 1.], [0., 0.]]),
                               ('ktens_eff', [[.2, .2], [0., 0.]]),
                               ('uvel', [[2., 3.], [0., 0.]])]:
                v = d.createVariable(name, 'f8', ('time', 'nj', 'ni'), fill_value=-999.)
                v[:] = np.asarray(data)[None, :, :]
            for base in ['dtens_flarge', 'dtens_gcand', 'ktens_cand', 'dtens_status']:
                if path.name.startswith('iceh_ic'):
                    v = d.createVariable(base+'_h', 'f8', ('time', 'nj', 'ni'), fill_value=-999.)
                    v[:] = d[base][:]

    def restart(self, path, day):
        with Dataset(path, 'w') as d:
            for name, size in [('ncat', 2), ('nj', 2), ('ni', 2)]:
                d.createDimension(name, size)
            for name, value in [('myear', 2005), ('mmonth', 1), ('mday', day),
                                ('msec', 0), ('istep1', (day-1)*24)]:
                d.setncattr(name, value)
            a = d.createVariable('aicen', 'f8', ('ncat', 'nj', 'ni'))
            a[:] = 0.
            a[:, 0, 0] = [.3, .6]
            for k in range(1, 13):
                v = d.createVariable('fsd%03d' % k, 'f8', a.dimensions)
                v[:] = 0.
                v[:, 0, 0] = .75 if k == 6 else .25 if k == 7 else 0.

    def set_fraction(self, path, value):
        with Dataset(path, 'a') as d:
            d['dtens_flarge'][0, 0, 0] = value
            d['dtens_gcand'][0, 0, 0] = .2+.8*value
            d['ktens_cand'][0, 0, 0] = .2*(.2+.8*value)

    def analyse(self):
        with contextlib.redirect_stdout(io.StringIO()):
            w.analyse(self.args)

    def test_complete_split_and_distinct_restart_ic_phase(self):
        self.analyse()

    def test_missing_hour_rejected(self):
        path = self.root / w.CASES[2] / 'history' / 'iceh_inst.2005-01-03-03600.nc'
        path.unlink()
        with self.assertRaisesRegex(ValueError, 'history inventory differs'):
            self.analyse()

    def test_physical_difference_rejected(self):
        path = self.root / w.CASES[2] / 'history' / 'iceh_inst.2005-01-03-03600.nc'
        with Dataset(path, 'a') as d:
            d['uvel'][0, 0, 0] += 1.
        with self.assertRaisesRegex(ValueError, 'uvel: decoded values differ'):
            self.analyse()

    def test_candidate_difference_rejected(self):
        path = self.root / w.CASES[2] / 'history' / 'iceh_inst.2005-01-03-03600.nc'
        self.set_fraction(path, .5)
        with self.assertRaisesRegex(ValueError, 'decoded values differ'):
            self.analyse()

    def test_restart_ic_wrong_mapping_rejected(self):
        path = self.root / w.CASES[2] / 'history' / ('iceh_ic.' + w.SPLIT + '.nc')
        self.set_fraction(path, .5)
        with self.assertRaisesRegex(ValueError, 'restart IC mapping differs'):
            self.analyse()

    def test_restart_clock_rejected(self):
        path = self.root / w.CASES[2] / 'restart' / ('iced.' + w.FINAL + '.nc')
        with Dataset(path, 'a') as d:
            d.setncattr('istep1', 48)
        with self.assertRaisesRegex(ValueError, 'wrong restart clock'):
            self.analyse()

    def test_input_restart_change_rejected(self):
        path = self.root / w.CASES[2] / 'input_restart' / ('iced.' + w.SPLIT + '.nc')
        with Dataset(path, 'a') as d:
            d['fsd007'][0, 0, 0] = .5
        with self.assertRaisesRegex(ValueError, 'staged input changed'):
            self.analyse()

    def test_stage_copies_exact_restart_and_refuses_repeat(self):
        run = self.root / w.CASES[2]
        shutil.rmtree(run / 'history')
        shutil.rmtree(run / 'input_restart')
        repo = self.root / 'repo'
        (repo / w.CASES[2] / 'b64-provenance').mkdir(parents=True)
        args = SimpleNamespace(repo=repo, runs=self.root)
        with contextlib.redirect_stdout(io.StringIO()):
            w.stage(args)
        staged = run / 'input_restart' / ('iced.' + w.SPLIT + '.nc')
        self.assertEqual((run / 'ice.restart_file').read_text().strip(), str(staged))
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError, 'already staged'):
                w.stage(args)


if __name__ == '__main__':
    unittest.main()
