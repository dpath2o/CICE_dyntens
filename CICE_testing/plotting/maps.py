"""General scalar maps of curvilinear cell centres; no interpolation or repair."""
from pathlib import Path

import numpy as np


def prepare_map_points(values, longitude, latitude, *, region, ocean_mask=None):
    """Return a contiguous float64 lon/lat/value table with one joint mask.

    Longitudes wrap to [-180, 180); dateline-crossing regions are supported.
    Zero scalar values are retained. Coordinates must already be in degrees.
    An optional CICE hm mask selects finite values greater than 0.5.
    """
    z, x, y = [np.ma.asarray(a, dtype=np.float64).filled(np.nan)
               for a in (values, longitude, latitude)]
    if z.ndim != 2 or not (z.shape == x.shape == y.shape):
        raise ValueError('Expected matching 2-D field, longitude and latitude arrays')
    west, east, south, north = map(float, region)
    if not np.isfinite([west, east, south, north]).all() or not (-90 <= south < north <= 90):
        raise ValueError('Invalid geographic region')
    if not (-180 <= west <= 180 and -180 <= east <= 180):
        raise ValueError('Region longitudes must be in [-180,180]')
    x = (x + 180.) % 360. - 180.
    lon_ok = ((x >= west) & (x <= east) if west <= east
              else (x >= west) | (x <= east))
    good = np.isfinite(x) & np.isfinite(y) & np.isfinite(z)
    good &= lon_ok & (y >= south) & (y <= north)
    if ocean_mask is not None:
        wet = np.ma.asarray(ocean_mask, dtype=float).filled(np.nan)
        if wet.shape != z.shape:
            raise ValueError('Ocean mask shape differs from field')
        if np.any(np.isfinite(wet) & ((wet < 0) | (wet > 1))):
            raise ValueError('Ocean mask must contain values in [0,1] or missing values')
        good &= np.isfinite(wet) & (wet > .5)
    return np.ascontiguousarray(np.column_stack((x[good], y[good], z[good])), dtype=np.float64)


def plot_scalar_map(values, longitude, latitude, *, region, limits,
                    projection=None, cmap='cmocean/amp', ocean_mask=None,
                    title='', color_label='', markers=(), symbol='c0.025c',
                    output_stem=None, show=False, dpi=180):
    """Plot a 2-D scalar field using GMT's three-column table input.

    Pass already transformed values (e.g. log10 error); this helper does not
    transform, threshold, normalise or clip scientific data. ``limits`` is
    [minimum, maximum], with no CPT increment or continuous flag. Markers are
    dictionaries with longitude, latitude and optional label/cell keys.
    Returns the PyGMT Figure; imports PyGMT only when plotting is requested.
    """
    points = prepare_map_points(values, longitude, latitude, region=region,
                                ocean_mask=ocean_mask)
    lo, hi = map(float, limits)
    if not np.isfinite([lo, hi]).all() or lo >= hi:
        raise ValueError('CPT limits must be finite and increasing')
    import pygmt
    if projection is None:
        pole = -90 if (region[2] + region[3]) < 0 else 90
        projection = f'S0/{pole}/13c'
    fig = pygmt.Figure()
    frame = ['af'] + ([f'+t{title}'] if title else [])
    fig.basemap(region=list(region), projection=projection, frame=frame)
    fig.coast(land='grey85', shorelines='0.3p')
    pygmt.makecpt(cmap=cmap, series=[lo, hi])
    if len(points):
        fig.plot(data=points, style=symbol, cmap=True)
    for marker in markers:
        mx = (float(marker['longitude']) + 180.) % 360. - 180.
        my = float(marker['latitude'])
        west, east, south, north = region
        inside = (west <= mx <= east if west <= east else mx >= west or mx <= east)
        if not (np.isfinite([mx, my]).all() and inside and south <= my <= north):
            continue
        fig.plot(x=[mx], y=[my], style='a0.3c', fill='yellow', pen='0.5p,black')
        label = marker.get('label', marker.get('cell', ''))
        if label:
            fig.text(x=mx, y=my, text=str(label), offset='0.15c/0.15c', font='9p,Helvetica,black')
    fig.colorbar(frame=f'xaf+l{color_label}' if color_label else 'xaf')
    if output_stem is not None:
        stem = Path(output_stem)
        stem.parent.mkdir(parents=True, exist_ok=True)
        for extension in ('png', 'pdf'):
            fig.savefig(str(stem) + '.' + extension, dpi=dpi)
    if show:
        fig.show()
    return fig
