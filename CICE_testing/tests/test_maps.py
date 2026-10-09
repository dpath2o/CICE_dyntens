"""Conditioning and plotting boundary checks without a GMT dependency."""
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from CICE_testing.plotting.maps import prepare_map_points, plot_scalar_map


def test_joint_mask_wrap_zero_and_dateline():
    points = prepare_map_points(
        [[0., 2., 3., np.nan, 5.]], [[181., 175., np.nan, 178., 179.]],
        [[-60., -60., -60., -60., -60.]], region=[170, -170, -90, -50],
        ocean_mask=[[1, 1, 1, 1, 0]])
    np.testing.assert_array_equal(points, [[-179., -60., 0.], [175., -60., 2.]])
    assert points.dtype == np.float64 and points.flags.c_contiguous


def test_masked_values_and_shapes():
    values = np.ma.array([[1., 2.]], mask=[[False, True]])
    points = prepare_map_points(values, [[0., 1.]], [[-60., -60.]],
                                region=[-180, 180, -90, -50])
    assert points.shape == (1, 3)
    with pytest.raises(ValueError, match='matching 2-D'):
        prepare_map_points([1], [0], [-60], region=[-180, 180, -90, -50])


def test_plot_uses_table_and_two_cpt_limits(monkeypatch):
    calls = []
    class Figure:
        def __getattr__(self, name):
            return lambda **kwargs: calls.append((name, kwargs))
    monkeypatch.setitem(sys.modules, 'pygmt', SimpleNamespace(
        Figure=Figure, makecpt=lambda **kwargs: calls.append(('makecpt', kwargs))))
    plot_scalar_map([[0.]], [[0.]], [[-60.]], region=[-180, 180, -90, -50], limits=[-1, 1])
    cpt = next(kwargs for name, kwargs in calls if name == 'makecpt')
    assert cpt == {'cmap': 'cmocean/amp', 'series': [-1., 1.]}
    plot = next(kwargs for name, kwargs in calls if name == 'plot')
    assert set(plot) == {'data', 'style', 'cmap'}
    assert plot['data'].shape == (1, 3)


def test_marker_tables_and_file_labels():
    from pathlib import Path
    from CICE_testing.plotting.maps import plot_map_markers
    calls = []
    class Figure:
        def plot(self, **kwargs):
            calls.append(('plot', kwargs))
        def text(self, **kwargs):
            calls.append(('text', kwargs))
            calls.append(('contents', Path(kwargs['textfiles']).read_text()))
    markers = [dict(longitude=181, latitude=-60, cell='SH_1'),
               dict(longitude=0, latitude=60, cell='NH_1'),
               dict(longitude=np.nan, latitude=-60, cell='invalid')]
    fig = Figure()
    plot_map_markers(fig, markers, region=[-180, 180, -90, -50],
                     projection='S0/-90/13c')
    points = calls[0][1]['data']
    np.testing.assert_array_equal(points, [[-179, -60]])
    assert points.dtype == np.float64 and points.flags.c_contiguous
    assert calls[2] == ('contents', '-179 -60 SH_1\n')
    assert not Path(calls[1][1]['textfiles']).exists()
    calls.clear()
    plot_map_markers(fig, markers, region=[-180, 180, -90, -50],
                     projection='S0/-90/13c', labels=False)
    assert [name for name, _ in calls] == ['plot']
