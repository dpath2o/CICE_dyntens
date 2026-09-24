import tempfile
import unittest
from pathlib import Path
import numpy as np
from netCDF4 import Dataset
from diagnose_restart_fsd import read_grid, diagnose


class DiagnosticTests(unittest.TestCase):
    def test_partition_and_weights(self):
        with tempfile.TemporaryDirectory() as tmp:
            grid = Path(tmp)/'grid.nc'
            restart = Path(tmp)/'restart.nc'
            with Dataset(grid, 'w') as ds:
                ds.createDimension('nj', 2); ds.createDimension('ni', 3)
                for name, units, data in [
                    ('tmask', '1', [[1,1,0],[1,1,1]]),
                    ('TLAT', 'degrees_north', [[-60,-60,-60],[60,60,60]]),
                    ('tarea', 'm^2', [[1e6,2e6,9e6],[3e6,4e6,5e6]])]:
                    v=ds.createVariable(name,'f8',('nj','ni')); v.units=units; v[:]=data
            with Dataset(restart,'w') as ds:
                ds.createDimension('ncat',1); ds.createDimension('nj',2); ds.createDimension('ni',3)
                v=ds.createVariable('aicen','f8',('ncat','nj','ni')); v[:]=.5
                for k in range(1,13):
                    v=ds.createVariable(f'fsd{k:03d}','f8',('ncat','nj','ni')); v[:]=0
                    if k==1:
                        v[:]=[[[1,0,0],[.5,np.nan,1]]]
            stats,cells,excluded,samples=diagnose(restart,read_grid(grid))
            self.assertEqual(excluded['inactive_T'],1)
            self.assertEqual(stats['global']['normalised']['count'],2)
            self.assertEqual(stats['SH']['zero']['area'],1.)
            self.assertEqual(stats['NH']['other_sum']['area'],1.5)
            self.assertEqual(stats['NH']['invalid_bins']['area'],2.)
            self.assertEqual(sum(v['area'] for v in stats['global'].values()),7.5)
            self.assertEqual(cells,{'global':3,'SH':1,'NH':2})
            self.assertEqual(samples['other_sum'][0]['j'],2)
            with Dataset(grid,'a') as ds:
                ds['TLAT'][:]=np.deg2rad(ds['TLAT'][:]); ds['TLAT'].units='radians'
                ds['tarea'][:]*=1e4; ds['tarea'].units='cm^2'
            np.testing.assert_allclose(read_grid(grid)[2], [[1,2,9],[3,4,5]])
            np.testing.assert_allclose(read_grid(grid)[1], [[-60]*3,[60]*3])
            with Dataset(grid,'a') as ds:
                ds['tmask'][0,2] = .5
                ds['tmask'][0,1] = .50001
                ds['tmask'][1,2] = np.ma.masked
            converted = read_grid(grid)
            self.assertEqual(converted[0][0,2],0)
            self.assertEqual(converted[0][0,1],1)
            self.assertTrue(np.isnan(converted[0][1,2]))
            stats, cells, excluded, samples = diagnose(restart,converted)
            self.assertEqual(excluded['inactive_T'],1)
            self.assertEqual(excluded['unknown_mask'],1)
            self.assertEqual(sum(v['area'] for v in stats['global'].values()),5.)
            with Dataset(grid,'a') as ds:
                ds['tmask'][0,0] = 2
            with self.assertRaisesRegex(ValueError,'Nonbinary decoded values') as caught:
                read_grid(grid)
            self.assertIn('2.0',str(caught.exception))
            with Dataset(grid,'a') as ds:
                ds['tmask'][0,0] = 1
                ds['tarea'].units='unknown'
            with self.assertRaisesRegex(ValueError,'Unrecognised tarea units'):
                read_grid(grid)


if __name__=='__main__':
    unittest.main()
