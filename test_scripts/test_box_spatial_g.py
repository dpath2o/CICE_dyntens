"""Small fixtures check that the diagnostic gate detects errors, not just success."""
import tempfile
import shutil
import unittest
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from netCDF4 import Dataset
from check_box_spatial_g import check_file, compare_runs

class SpatialGate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/'box.nc'
        self.args = SimpleNamespace(mode='box_band',background=1.,band=.5,ilo=6,ihi=7,ktens=.2,tensile=True)
        with Dataset(self.path,'w') as d:
            d.createDimension('nj',12); d.createDimension('ni',12)
            mask=np.zeros((12,12));mask[2:10,2:10]=1
            g=np.ones((12,12));g[:,5:7]=.5
            wind=np.ones((12,12))*5;wind[:,:6]=-5
            for n,x in [('tmask',mask),('dyntens_g',g),('ktens_eff',g*.2),('uatm',wind),('vatm',mask*0)]:
                d.createVariable(n,'f8',('nj','ni'))[:]=x
    def test_correct(self):
        check_file(self.path,self.args)
    def test_displaced_band_rejected(self):
        with Dataset(self.path,'a') as d:
            d['dyntens_g'][4,5]=1
        with self.assertRaises(ValueError):check_file(self.path,self.args)
    def test_wrong_effective_factor_rejected(self):
        with Dataset(self.path,'a') as d:d['ktens_eff'][4,5]=.2
        with self.assertRaises(ValueError):check_file(self.path,self.args)
    def test_inward_wind_rejected(self):
        with Dataset(self.path,'a') as d:d['uatm'][:]=-d['uatm'][:]
        with self.assertRaises(ValueError):check_file(self.path,self.args)
    def make_pair(self):
        runs=[Path(self.tmp.name)/'run',Path(self.tmp.name)/'reference']
        for r in runs:
            for folder in ['history','restart']:
                (r/folder).mkdir(parents=True)
                shutil.copyfile(self.path,r/folder/'box.nc')
        return runs
    def test_reference_equal(self):
        compare_runs(*self.make_pair())
    def test_restart_difference_rejected(self):
        a,b=self.make_pair()
        with Dataset(b/'restart'/'box.nc','a') as d:d['ktens_eff'][4,5]=.2
        with self.assertRaises(ValueError):compare_runs(a,b)
    def test_missing_restart_rejected(self):
        a,b=self.make_pair()
        (b/'restart'/'box.nc').unlink()
        with self.assertRaises(ValueError):compare_runs(a,b)
    def test_nonfinite_rejected(self):
        with Dataset(self.path,'a') as d:d['vatm'][4,4]=np.nan
        with self.assertRaises(ValueError):check_file(self.path,self.args)

if __name__=='__main__':unittest.main()
