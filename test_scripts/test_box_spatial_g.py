"""Small fixtures check that the diagnostic gate detects errors, not just success."""
import tempfile
import shutil
import unittest
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from netCDF4 import Dataset
from check_box_spatial_g import check_file, compare_runs, variable
from contextlib import redirect_stdout
import io

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
    def test_uniform_east_control(self):
        self.args.wind = 'uniform_east'
        self.args.tensile = False
        with Dataset(self.path, 'a') as d: d['uatm'][:] = 5.
        check_file(self.path, self.args)
    def test_tensile_rejected_for_uniform_control(self):
        self.args.wind = 'uniform_east'
        self.args.tensile = False
        with self.assertRaises(ValueError): check_file(self.path, self.args)
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
    def instant_file(self):
        with Dataset(self.path,'a') as d:
            v=d.createVariable('divu','f8',('nj','ni'));v[:]=.2;v.units='%/day'
            for name in ['dyntens_g','ktens_eff','uatm','vatm','divu']:
                d.renameVariable(name,name+'_1')
    def test_instantaneous_suffix_and_divergence(self):
        self.instant_file()
        out=io.StringIO()
        with redirect_stdout(out):check_file(self.path,self.args)
        self.assertIn('central divu [%/day]',out.getvalue())
    def test_instantaneous_bad_wind_rejected(self):
        self.instant_file()
        with Dataset(self.path,'a') as d:d['uatm_1'][:]=0
        with self.assertRaises(ValueError):check_file(self.path,self.args)
    def test_instantaneous_bad_coefficient_rejected(self):
        self.instant_file()
        with Dataset(self.path,'a') as d:d['dyntens_g_1'][4,5]=1
        with self.assertRaises(ValueError):check_file(self.path,self.args)
    def test_missing_field_still_rejected(self):
        with Dataset(self.path,'a') as d:d.renameVariable('dyntens_g','unrelated')
        with self.assertRaises(ValueError):check_file(self.path,self.args)
    def test_both_streams_select_base(self):
        p=self.ic_file()
        with Dataset(p,'a') as d:
            for name in ['dyntens_g','ktens_eff','uatm','vatm']:
                d.createVariable(name+'_1','f8',('nj','ni'))[:]=d[name][:]
        with Dataset(p) as d:
            self.assertEqual(variable(d,'dyntens_g').name,'dyntens_g')
        check_file(p,self.args)
    def test_bad_base_not_hidden_by_good_suffix(self):
        p=self.ic_file()
        with Dataset(p,'a') as d:
            d.createVariable('dyntens_g_1','f8',('nj','ni'))[:]=d['dyntens_g'][:]
            d['dyntens_g'][4,5]=1
        with self.assertRaises(ValueError):check_file(p,self.args)
    def ic_file(self):
        p = self.path.with_name('iceh_ic.2005-01-01-00000.nc')
        self.path.rename(p)
        with Dataset(p,'a') as d:d['uatm'][:]=0
        return p
    def test_initial_wind_not_yet_applied(self):
        check_file(self.ic_file(),self.args)
    def test_initial_bad_coefficient_still_rejected(self):
        p=self.ic_file()
        with Dataset(p,'a') as d:d['ktens_eff'][4,5]=.2
        with self.assertRaises(ValueError):check_file(p,self.args)
    def test_initial_nonfinite_still_rejected(self):
        p=self.ic_file()
        with Dataset(p,'a') as d:d['uatm'][4,5]=np.nan
        with self.assertRaises(ValueError):check_file(p,self.args)
    def test_unforced_regular_history_rejected(self):
        with Dataset(self.path,'a') as d:d['uatm'][:]=0
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
