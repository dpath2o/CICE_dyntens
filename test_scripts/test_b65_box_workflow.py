#!/usr/bin/env python3
"""Synthetic B6.5 analytical and neutrality/decomposition checker regressions."""
import tempfile
from pathlib import Path
import unittest
import numpy as np
from netCDF4 import Dataset
import b65_box_workflow as w


class BoxWorkflow(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def history(self, mode, filename, control=False):
        p=self.root/filename
        with Dataset(p,'w') as d:
            for name,size in [('time',1),('nj',12),('ni',12)]:
                d.createDimension(name,size)
            ocean=np.zeros((12,12))
            ocean[2:10,2:10]=1.
            d.createVariable('tmask','f8',('nj','ni'))[:]=ocean
            vals={'small':0.,'large':1.,'mixed':.5,'unequal':2/3,'dilute':2/3,'inactive':0.}
            fraction=np.full((12,12),vals.get(mode,1.))
            if mode=='spatial': fraction[:,5]=0.
            g=np.ones((12,12)) if mode=='inactive' else .2+.8*fraction
            fields={'dyntens_g':np.ones((12,12)),'ktens_eff':np.full((12,12),.2),
                    'uvel':np.full((12,12),2.),'blkmask':np.ones((12,12))}
            if not control:
                fields.update(dtens_flarge=fraction,dtens_gcand=g,ktens_cand=.2*g,
                              dtens_status=np.full((12,12),1. if mode=='inactive' else 0.))
            for name,data in fields.items():
                x=d.createVariable(name,'f8',('time','nj','ni'),fill_value=-999.)
                if name=='dtens_flarge' and mode=='inactive':
                    x[:]=np.ma.masked_all((1,12,12))
                else:
                    x[:]=data[None,:,:]
            if not control:
                for name in ['dtens_flarge','dtens_gcand','ktens_cand','dtens_status']:
                    v=d.createVariable(name+'_h','f8',('time','nj','ni'),fill_value=-999.)
                    v[:]=d[name][:]
        return p

    def test_all_analytical_fixtures_and_inactive_masks(self):
        for mode in ['small','large','mixed','unequal','dilute','inactive','spatial']:
            with Dataset(self.history(mode,mode+'.nc')) as d:
                w.check_fixture(d,mode)

    def test_inactive_hourly_ic_requires_netcdf_fill(self):
        path=self.history('inactive','iceh_ic.nc')
        with Dataset(path,'a') as d:
            # The production accumulator uses a negative sentinel, distinct
            # from the positive output fill value. It must be converted.
            v=d['dtens_flarge_h']
            v[:]=-1.e30
        with Dataset(path) as d:
            with self.assertRaisesRegex(ValueError,'unmasked large fraction: dtens_flarge_h'):
                w.check_fixture(d,'inactive')
        with Dataset(path,'a') as d:
            d['dtens_flarge_h'][:]=np.ma.masked_all((1,12,12))
        with Dataset(path) as d:
            w.check_fixture(d,'inactive')

    def test_initial_history_masks_nonprimary_fraction_streams(self):
        repo=Path(__file__).resolve().parents[1]
        source=(repo/'cicecore/cicedyn/analysis/ice_history.F90').read_text()
        guard=source.index('if (write_ic .and. use_dyntens_diagnostics) then')
        writer=source.index('call ice_write_hist (ns)',guard)
        block=source[guard:source.index('! dpath2o: dyntens',guard)]
        self.assertIn('do ns = 2, nstreams',block)
        self.assertIn('n = n_dyntens_large_fraction(ns)',block)
        self.assertIn('if (n > 0)',block)
        self.assertIn('where (a2D(:,:,n,:) < c0) a2D(:,:,n,:) = spval_dbl',block)
        self.assertLess(guard,writer)

    def test_spatial_rank_local_pattern_rejected(self):
        path=self.history('spatial','bad.nc')
        with Dataset(path,'a') as d:
            for suffix in ['', '_h']:
                d['dtens_flarge'+suffix][0,:,5]=1.
                d['dtens_gcand'+suffix][0,:,5]=1.
                d['ktens_cand'+suffix][0,:,5]=.2
        with Dataset(path) as d:
            with self.assertRaisesRegex(ValueError,'wrong analytical fixture'):
                w.check_fixture(d,'spatial')

    def test_neutral_control_and_physical_difference(self):
        fixture=self.history('mixed','fixture.nc')
        control=self.history('mixed','control.nc',control=True)
        w.compare(fixture,control,candidates=False)
        with Dataset(fixture,'a') as d:
            d['uvel'][0,5,5]+=1.
        with self.assertRaisesRegex(ValueError,'exact values differ uvel'):
            w.compare(fixture,control,candidates=False)

    def test_candidate_equality_required_for_equivalent_layout(self):
        a=self.history('small','a.nc')
        b=self.history('large','b.nc')
        with self.assertRaisesRegex(ValueError,'exact values differ'):
            w.compare(a,b,layout=True)

    def test_layout_exception_is_only_blkmask_values(self):
        a=self.history('spatial','a.nc')
        b=self.history('spatial','b.nc')
        with Dataset(b,'a') as d:
            d['blkmask'][:]=2.
        w.compare(a,b,layout=True)
        with self.assertRaisesRegex(ValueError,'exact values differ blkmask'):
            w.compare(a,b)
        with Dataset(b,'a') as d:
            d['uvel'][0,5,5]+=1.
        with self.assertRaisesRegex(ValueError,'exact values differ uvel'):
            w.compare(a,b,layout=True)

    def test_live_path_and_box_guards_are_present(self):
        root=Path(__file__).resolve().parents[1]
        evp=(root/'cicecore/cicedyn/dynamics/ice_dyn_evp.F90').read_text()
        init=(root/'cicecore/cicedyn/general/ice_init.F90').read_text()
        self.assertIn("if (trim(dyntens_box_fixture)=='none') then",evp)
        self.assertIn('i_global(i,blocks_ice(iblk))',evp)
        self.assertIn('nx_global/=12 .or. ny_global/=12 .or. nfsd/=12',evp)
        self.assertIn('Box FSD fixture requires diagnostics=T; feedback only in box_fsd',init)
        self.assertIn("(use_dyntens .and. trim(dyntens_g_mode)/='box_fsd')",init)


if __name__=='__main__':
    unittest.main()
