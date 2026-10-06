"""Real PyGMT smoke tests against small, explicitly synthetic NetCDF fixtures."""
from pathlib import Path
import json
import shutil

import numpy as np
import pytest
from netCDF4 import Dataset
from CICE_testing import FigureSpec
from CICE_testing.plotting.validation import ValidationFigures


def gmt_available():
    try:
        import pygmt
        pygmt.Figure()
        return shutil.which('gs') is not None
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not gmt_available(), reason='PyGMT/GMT/Ghostscript unavailable')


def history(path, t=0):
    path.parent.mkdir(parents=True,exist_ok=True)
    with Dataset(path,'w') as ds:
        for key,size in [('time',1),('nj',4),('ni',4)]: ds.createDimension(key,size)
        v=ds.createVariable('time','f8',('time',));v.units='days since 2005-01-01';v[:]=t
        for name,data,units in [('tmask',np.ones((4,4)),''),
                                ('TLAT',np.tile(np.linspace(-80,-65,4)[:,None],(1,4)),'degrees_north'),
                                ('TLON',np.tile(np.linspace(10,40,4),(4,1)),'degrees_east'),
                                ('tarea',np.ones((4,4)),'km2')]:
            v=ds.createVariable(name,'f8',('nj','ni'));v.units=units;v[:]=data
        v=ds.createVariable('dtens_gcand','f8',('time','nj','ni'));v.units='1';v[:]=.6
        a=ds.createVariable('ktens_eff','f8',('time','nj','ni'));a.units='1';a[:]=.2
        for name,value in [('dtens_flarge',.5),('ktens_cand',.12),('dtens_status',0.),('dyntens_g',1.)]:
            v=ds.createVariable(name,'f8',('time','nj','ni'));v.units='1';v[:]=value
    return path


def test_pygmt_mapping_snapshot_series_comparison_and_global(tmp_path):
    plots=ValidationFigures(FigureSpec(tmp_path/'report'))
    outputs=plots.mapping()
    run=tmp_path/'run';ref=tmp_path/'ref'
    paths=[history(run/'history'/f'iceh.2005-01-0{k+1}.nc',k) for k in range(2)]
    for p in paths:
        q=ref/'history'/p.name;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
    outputs+=plots.fixture_matrix({'mixed': paths[0]})
    restart=tmp_path/'restart.nc'
    with Dataset(restart,'w') as ds:
        for key,size in [('ncat',2),('nj',4),('ni',4)]: ds.createDimension(key,size)
        ds.createVariable('aicen','f8',('ncat','nj','ni'))[:]=.3
        for k in range(1,13): ds.createVariable(f'fsd{k:03d}','f8',('ncat','nj','ni'))[:]=1. if k==1 else 0.
    outputs+=plots.fsd_classes(restart,paths[0])
    outputs+=plots.snapshot(paths[0],names=('dtens_gcand',))
    outputs+=plots.timeseries(run,stream='daily')
    outputs+=plots.comparison(run,ref)
    global_plots=ValidationFigures(FigureSpec(tmp_path/'report',scope='global'))
    outputs+=global_plots.snapshot(paths[0],names=('dtens_gcand',))
    with Dataset(paths[0],'a') as ds: ds['dtens_gcand'][0,0,0]=np.nan
    with pytest.raises(ValueError,match='nonfinite'): plots.snapshot(paths[0],names=('dtens_gcand',))
    assert all(p.stat().st_size > 100 for p in outputs)
    for manifest in (tmp_path/'report').glob('*/evidence/*.json'):
        result=json.loads(manifest.read_text())
        assert result['backend']=='PyGMT'
        assert result['validation_status']=='not_assessed'
        assert all('sha256' in r for r in result['inputs'])
