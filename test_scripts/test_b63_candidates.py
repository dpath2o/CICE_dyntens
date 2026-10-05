#!/usr/bin/env python3
# dpath2o: dyntens
# Synthetic history fixtures exercise the checker, not CICE integration.
import unittest
import uuid
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
        values={'dyntens_large_fraction':[.5,0,0],
                'dyntens_g_candidate':[.6,1,0],
                'ktens_eff_candidate':[.12,.2,0],
                'dyntens_mapping_status':[0,1,0],
                'dyntens_g':[1,1,0],'ktens_eff':[.2,.2,0]}
        for suffix in suffixes:
            for name,data in values.items():
                var=ds.createVariable(name+suffix,'f8',('time','nj','ni'),fill_value=1.e30)
                mask=[False,name=='dyntens_large_fraction',True]
                var[:]=np.ma.array(data,mask=mask).reshape(1,1,3)
        return ds

    def test_valid_and_inactive(self):
        check_dataset(self.fixture(),.2,.2,1.e-10)

    def test_duplicate_ic_streams(self):
        check_dataset(self.fixture(('', '_1')),.2,.2,1.e-10)

    def test_bad_mapping(self):
        ds=self.fixture();ds['dyntens_g_candidate'][0,0,0]=.7
        with self.assertRaises(ValueError): check_dataset(ds,.2,.2,1.e-10)

    def test_masked_applied_coefficient(self):
        ds=self.fixture();ds['dyntens_g'][:]=np.ma.masked_all((1,1,3))
        with self.assertRaises(ValueError): check_dataset(ds,.2,.2,1.e-10)

    def test_feedback_rejected(self):
        ds=self.fixture();ds['dyntens_g'][0,0,0]=.5
        with self.assertRaises(ValueError): check_dataset(ds,.2,.2,1.e-10)

    def test_unmasked_inactive_fraction(self):
        ds=self.fixture();ds['dyntens_large_fraction'][0,0,1]=0
        with self.assertRaises(ValueError): check_dataset(ds,.2,.2,1.e-10)

    def test_mixed_interval(self):
        ds=self.fixture();ds['dyntens_mapping_status'][0,0,1]=.5
        ds['dyntens_g_candidate'][0,0,1]=.8;ds['ktens_eff_candidate'][0,0,1]=.16
        check_dataset(ds,.2,.2,1.e-10)

    def test_nonfinite(self):
        ds=self.fixture();ds['dyntens_g_candidate'][0,0,0]=np.nan
        with self.assertRaises(ValueError): check_dataset(ds,.2,.2,1.e-10)

    def test_missing_field(self):
        ds=self.fixture();ds.renameVariable('dyntens_g_candidate','missing')
        with self.assertRaises(ValueError): check_dataset(ds,.2,.2,1.e-10)

    def test_control_identity_and_difference(self):
        a,b=self.fixture(),self.fixture()
        compare_history(a,b)
        b['ktens_eff'][0,0,0]=.1
        with self.assertRaises(ValueError): compare_history(a,b)


if __name__=='__main__':
    unittest.main()
# dpath2o: dyntens
