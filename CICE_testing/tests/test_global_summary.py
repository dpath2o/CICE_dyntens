from pathlib import Path
import json
import numpy as np
import pytest
from netCDF4 import Dataset
from CICE_testing.validation.global_summary import GlobalComparisonSummary


def history(path, percent=False):
    with Dataset(path, 'w') as ds:
        for name, size in [('time', 1), ('nj', 3), ('ni', 2), ('nb', 2)]:
            ds.createDimension(name, size)
        time = ds.createVariable('time', 'f8', ('time',))
        time.units = 'days since 2000-09-01'; time.calendar = 'standard'; time.bounds = 'time_bounds'
        time[:] = [1.5]
        ds.createVariable('time_bounds', 'f8', ('time', 'nb'))[:] = [[1., 2.]]
        data = dict(tmask=[[1, 0], [1, 1], [1, 1]], TLAT=[[60, 45], [-60, -45], [0, 0]],
                    tarea=[[1e6, 2e6], [1e6, 2e6], [1e6, 1e6]],
                    aice=[[.5, 1], [.25, .1], [.8, .8]], hi=[[1, 9], [.5, .2], [2, 2]],
                    strength=[[10, 999], [20, 999], [55, 55]])
        units = dict(tmask='1', TLAT='degrees_north', tarea='m^2', aice='%' if percent else '1', hi='m', strength='N/m')
        for name, values in data.items():
            dims = ('nj', 'ni') if name in ('tmask', 'TLAT', 'tarea') else ('time', 'nj', 'ni')
            var = ds.createVariable(name, 'f8', dims, fill_value=-999.)
            var.units = units[name]
            if name == 'strength': var.coordinates = 'TLON TLAT time'
            values = np.array(values)*(100 if name == 'aice' and percent else 1)
            var[:] = values if len(dims) == 2 else values[None, :, :]


def test_polar_integrals_daily_interval_and_chunk_independence(tmp_path):
    off, unity = tmp_path/'off.nc', tmp_path/'unity.nc'
    history(off); history(unity, percent=True)
    outputs = []
    for rows in (1, 32):
        output = tmp_path/str(rows)
        totals, fields = GlobalComparisonSummary(off, unity, output, rows=rows).run()
        outputs.append((totals, fields))
        nh = {r['metric']: r['off'] for r in totals if '(NH)' in r['region']}
        sh = {r['metric']: r['off'] for r in totals if '(SH)' in r['region']}
        assert nh == dict(area=.5, extent=1., volume=.001, mean_ice_thickness=2.)
        assert sh['area'] == pytest.approx(.45)
        assert sh['extent'] == 1. and sh['mean_ice_thickness'] == 2.
        assert all(r['unity_minus_off'] == 0 for r in totals+fields)
        assert all(r['max_abs_cell_difference'] == 0 for r in fields)
        meta = json.loads((output/'g0-regional-summary.json').read_text())
        assert meta['time']['interval'] == ['2000-09-02 00:00:00', '2000-09-03 00:00:00']
        assert 'Tsfc: not written' in meta['skipped_fields']
    assert outputs[0] == outputs[1]


def test_local_differences_not_hidden_by_regional_averages(tmp_path):
    off, unity = tmp_path/'off.nc', tmp_path/'unity.nc'
    history(off); history(unity)
    with Dataset(unity, 'r+') as ds:
        ds['strength'][0, 0, 0] = 12.
    _, rows = GlobalComparisonSummary(off, unity, tmp_path/'output').run()
    nh = [r for r in rows if '(NH)' in r['region']]
    assert all(r['max_abs_cell_difference'] == 2 and r['unequal_cells'] == 1 for r in nh)


def test_nonfinite_ocean_data_rejected(tmp_path):
    off, unity = tmp_path/'off.nc', tmp_path/'unity.nc'
    history(off); history(unity)
    with Dataset(unity, 'r+') as ds: ds['hi'][0, 0, 0] = np.nan
    with pytest.raises(ValueError, match='nonfinite'):
        GlobalComparisonSummary(off, unity, tmp_path/'output').run()
