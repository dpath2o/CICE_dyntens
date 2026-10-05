#!/usr/bin/env python3
# dpath2o: dyntens
# Synthetic history fixtures exercise the checker, not CICE integration.
import unittest
import uuid
import re
from pathlib import Path
import numpy as np
from netCDF4 import Dataset
from check_b63_candidates import check_dataset, compare_history


class CandidateHistory(unittest.TestCase):
    def fixture(self, suffixes=('',)):
        ds=Dataset('fixture-'+uuid.uuid4().hex,mode='w',diskless=True,persist=False)
        self.addCleanup(ds.close)
        ds.createDimension('time',1)
        ds.createDimension('nj',1)
        ds.createDimension('ni',3)
        grid=ds.createVariable('tmask','f8',('nj','ni'),fill_value=1.e30)
        grid[:]=[[1,1,0]]
        values={'dtens_flarge':[.5,0,0],
                'dtens_gcand':[.6,1,0],
                'ktens_cand':[.12,.2,0],
                'dtens_status':[0,1,0],
                'dyntens_g':[1,1,0],'ktens_eff':[.2,.2,0]}
        for suffix in suffixes:
            for name,data in values.items():
                var=ds.createVariable(name+suffix,'f8',('time','nj','ni'),fill_value=1.e30)
                mask=[False,name=='dtens_flarge',True]
                var[:]=np.ma.array(data,mask=mask).reshape(1,1,3)
        return ds

    def test_fortran_stream_names_fit_and_remain_unique(self):
        root = Path(__file__).resolve().parents[1]
        source = (root/'cicecore/cicedyn/analysis/ice_history.F90').read_text()
        shared = (root/'cicecore/cicedyn/analysis/ice_history_shared.F90').read_text()
        width = int(re.search(r'character\s*\(len=(\d+)\)\s*::\s*vname', shared, re.I).group(1))
        names = []
        for index in ('dyntens_large_fraction', 'dyntens_g_candidate',
                      'ktens_eff_candidate', 'dyntens_mapping_status'):
            name = re.search(r'define_hist_field\(n_' + index + r',"([^"]+)"', source).group(1)
            for suffix in ('', '_h', '_1'):
                candidate = name + suffix
                self.assertLessEqual(len(candidate), width)
                names.append(candidate[:width])
        self.assertEqual(len(names), len(set(names)))
        with Dataset('stream-names-'+uuid.uuid4().hex, mode='w', diskless=True, persist=False) as ds:
            for name in names:
                ds.createVariable(name, 'f8')

    def test_hourly_suffixes(self):
        check_dataset(self.fixture(('', '_h')),.2,.2,1.e-10)

    def test_ic_hourly_unmasked_land_zeros(self):
        ds=self.fixture(('', '_h'))
        for name in ds.variables:
            if name.endswith('_h'):
                ds[name][0,0,2]=0.
        check_dataset(ds,.2,.2,1.e-10)

    def test_hourly_ocean_zero_still_fails(self):
        ds=self.fixture(('', '_h'))
        ds['dtens_gcand_h'][0,0,0]=0.
        with self.assertRaises(ValueError): check_dataset(ds,.2,.2,1.e-10)

    def test_missing_ocean_candidate_fails(self):
        ds=self.fixture()
        ds['dtens_gcand'][0,0,0]=np.ma.masked
        with self.assertRaises(ValueError): check_dataset(ds,.2,.2,1.e-10)

    def test_missing_tmask_fails(self):
        ds=self.fixture();ds.renameVariable('tmask','missing_mask')
        with self.assertRaises(ValueError): check_dataset(ds,.2,.2,1.e-10)

    def test_nonbinary_tmask_fails(self):
        ds=self.fixture();ds['tmask'][0,0]=.5
        with self.assertRaises(ValueError): check_dataset(ds,.2,.2,1.e-10)

    def test_masked_land_tmask(self):
        ds=self.fixture();ds['tmask'][0,2]=np.ma.masked
        check_dataset(ds,.2,.2,1.e-10)

    def test_control_land_difference_still_fails(self):
        a,b=self.fixture(),self.fixture()
        a['dyntens_g'][0,0,2]=0.
        b['dyntens_g'][0,0,2]=.1
        with self.assertRaises(ValueError): compare_history(a,b)

    def test_valid_and_inactive(self):
        check_dataset(self.fixture(),.2,.2,1.e-10)

    def test_duplicate_ic_streams(self):
        check_dataset(self.fixture(('', '_1')),.2,.2,1.e-10)

    def test_bad_mapping(self):
        ds=self.fixture();ds['dtens_gcand'][0,0,0]=.7
        with self.assertRaises(ValueError): check_dataset(ds,.2,.2,1.e-10)

    def test_masked_applied_coefficient(self):
        ds=self.fixture();ds['dyntens_g'][:]=np.ma.masked_all((1,1,3))
        with self.assertRaises(ValueError): check_dataset(ds,.2,.2,1.e-10)

    def test_feedback_rejected(self):
        ds=self.fixture();ds['dyntens_g'][0,0,0]=.5
        with self.assertRaises(ValueError): check_dataset(ds,.2,.2,1.e-10)

    def test_unmasked_inactive_fraction(self):
        ds=self.fixture();ds['dtens_flarge'][0,0,1]=0
        with self.assertRaises(ValueError): check_dataset(ds,.2,.2,1.e-10)

    def test_mixed_interval(self):
        ds=self.fixture();ds['dtens_status'][0,0,1]=.5
        ds['dtens_gcand'][0,0,1]=.8;ds['ktens_cand'][0,0,1]=.16
        check_dataset(ds,.2,.2,1.e-10)

    def test_nonfinite(self):
        ds=self.fixture();ds['dtens_gcand'][0,0,0]=np.nan
        with self.assertRaises(ValueError): check_dataset(ds,.2,.2,1.e-10)

    def test_missing_field(self):
        ds=self.fixture();ds.renameVariable('dtens_gcand','missing')
        with self.assertRaises(ValueError): check_dataset(ds,.2,.2,1.e-10)

    def test_control_identity_and_difference(self):
        a,b=self.fixture(),self.fixture()
        compare_history(a,b)
        b['ktens_eff'][0,0,0]=.1
        with self.assertRaises(ValueError): compare_history(a,b)


if __name__=='__main__':
    unittest.main()
# dpath2o: dyntens
