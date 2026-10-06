"""PyGMT-only report figures with explicit inputs and no inferred validation PASS."""
from pathlib import Path
import argparse
import csv
import json
import re

import numpy as np
from netCDF4 import Dataset, num2date

from ..core.paths import TestingPaths
from ..core.reporting import sha256
from ..core.types import FigureSpec, CandidateSpec
from ..validation.spatial import field, variable


def _pygmt():
    # Numerical validators and preparation do not require the GMT shared library.
    try:
        import pygmt
    except Exception as exc:
        raise RuntimeError("Figure generation requires PyGMT and the GMT shared library; install the figures extra in a GMT-enabled environment") from exc
    return pygmt


def _range(values):
    values = np.asarray(values, dtype=float)
    if not values.size or not np.isfinite(values).all():
        raise ValueError("no finite plotting values")
    lo, hi = float(values.min()), float(values.max())
    pad = max((hi-lo)*0.08, abs(lo)*0.02, 1e-12)
    return [lo-pad, hi+pad]


class ValidationFigures:
    """Export PNG/PDF figures plus JSON provenance and reusable measured CSVs.

    The mapping curve is analytical reference only. History fields and differences
    are descriptive evidence; run validators separately to establish a gate.
    """
    def __init__(self, spec: FigureSpec):
        self.spec = spec
        self.paths = TestingPaths(spec.output, spec.scope)

    def _save(self, fig, name, inputs=(), notes="", extra=None):
        self.paths.figures.mkdir(parents=True, exist_ok=True)
        self.paths.evidence.mkdir(parents=True, exist_ok=True)
        outputs = []
        for extension in ("png", "pdf"):
            path = self.paths.figures / (name + "." + extension)
            fig.savefig(str(path), dpi=self.spec.dpi)
            outputs.append(path)
        record = {"schema_version": 1, "scope": self.spec.scope, "backend": "PyGMT",
                  "notes": notes, "validation_status": "not_assessed",
                  "inputs": [{"path": str(Path(x).resolve()), "sha256": sha256(x)} for x in inputs],
                  "outputs": [{"path": str(x), "sha256": sha256(x)} for x in outputs]}
        if extra:
            record.update(extra)
        (self.paths.evidence / (name + ".json")).write_text(json.dumps(record, indent=2, allow_nan=False)+"\n")
        return outputs

    def mapping(self, candidate=CandidateSpec()):
        pygmt = _pygmt()
        fraction = np.linspace(0, 1, 201)
        g = candidate.gmin + (1-candidate.gmin)*fraction
        fig = pygmt.Figure()
        fig.basemap(region=[0, 1, 0, 1.05], projection="X14c/8c",
                    frame=["xaf+lLarge-floe ice-area fraction", "yaf+lCoefficient", "+tAnalytical mapping reference"])
        fig.plot(x=fraction, y=g, pen="1.8p,#007C91", label="g candidate")
        fig.plot(x=fraction, y=candidate.ktens*g, pen="1.8p,#D2691E", label="Ktens candidate")
        for x in (0., .5, 2/3, 1.):
            fig.plot(x=[x], y=[candidate.gmin+(1-candidate.gmin)*x], style="c0.14c", fill="#007C91")
        fig.legend(position="JTL+jTL+o0.2c", box="+gwhite+p0.4p")
        return self._save(fig, "mapping_reference", notes="Analytical expectations only; not measured model output or a runtime PASS.",
                          extra={"gmin": candidate.gmin, "ktens": candidate.ktens})

    def fixture_matrix(self, histories):
        """Measured uniform shadow fixtures against B6.5 analytical expectations.

        histories maps small/large/mixed/unequal/dilute/inactive to real snapshots.
        The audited fixture validator must pass before these points are exported.
        """
        from ..workflows.box import check_fixture
        pygmt = _pygmt()
        expected = {'small': .2, 'large': 1., 'mixed': .6,
                    'unequal': 11/15, 'dilute': 11/15, 'inactive': 1.}
        if not histories or set(histories)-set(expected):
            raise ValueError("supply supported uniform fixture names")
        rows = []
        for mode, path in histories.items():
            with Dataset(path) as ds:
                check_fixture(ds, mode)
                mask = field(ds, 'tmask')
                data = field(ds, 'dtens_gcand')
                wet = ~np.ma.getmaskarray(mask) & (mask.data > .5)
                values = data.data[wet]
                rows.append([mode, expected[mode], float(values.min()), float(values.mean()), float(values.max()), str(path)])
        self.paths.evidence.mkdir(parents=True, exist_ok=True)
        with (self.paths.evidence/'fixture_matrix.csv').open('w') as out:
            writer = csv.writer(out)
            writer.writerow(['mode','expected_g','measured_min','measured_cell_mean','measured_max','source'])
            writer.writerows(rows)
        fig = pygmt.Figure()
        fig.basemap(region=[-.5,len(rows)-.5,0,1.15], projection="X15c/8c",
                    frame=["x+lFixture index (see labels)","yaf+lCandidate g","+tMeasured B6.5 uniform shadow fixtures"])
        indices = list(range(len(rows)))
        fig.plot(x=indices,y=[r[1] for r in rows],style='c0.25c',pen='1p,#D2691E',label='Analytical expectation')
        fig.plot(x=indices,y=[r[3] for r in rows],style='x0.18c',pen='1.5p,#007C91',label='Measured cell mean')
        for i,row in enumerate(rows):
            fig.text(x=i,y=.075,text=row[0],font='9p')
        fig.legend(position='JTL+jTL+o0.2c',box='+gwhite+p0.4p')
        return self._save(fig, 'fixture_matrix', list(histories.values()),
                          'Measured uniform shadow fixtures; checked at atol=1e-10. This checks selected snapshots only, not complete B6.5 coverage or feedback.',
                          extra={'snapshot_fixture_check': 'PASS', 'tolerance': 1e-10})

    def snapshot(self, history_file, names=("dtens_flarge", "dtens_gcand", "ktens_cand")):
        """Box cell-index raster, or global lon/lat cell-centre symbols (no interpolation)."""
        pygmt = _pygmt()
        source = Path(history_file)
        outputs = []
        with Dataset(source) as ds:
            mask = field(ds, "tmask")
            known = ~np.ma.getmaskarray(mask)
            if np.any(known & (~np.isfinite(mask.data) | (mask.data < 0) | (mask.data > 1))):
                raise ValueError("invalid history tmask")
            ocean = known & (mask.data > .5)
            if not ocean.any():
                raise ValueError("snapshot has no active ocean cells")
            for name in names:
                value = field(ds, name)
                if value.shape != mask.shape:
                    raise ValueError("field/grid shapes differ")
                data = np.where(ocean & ~np.ma.getmaskarray(value), value.data, np.nan)
                if np.any(ocean & ~np.ma.getmaskarray(value) & ~np.isfinite(value.data)):
                    raise ValueError("nonfinite unmasked field")
                good = np.isfinite(data)
                if not good.any():
                    raise ValueError(f"{name}: no finite occupied values to plot")
                bounds = _range(data[good])
                fig = pygmt.Figure()
                pygmt.makecpt(cmap="viridis", series=[*bounds, (bounds[1]-bounds[0])/128], continuous=True)
                title = f"{name}: {source.name}"
                if self.spec.scope == "box":
                    import xarray as xr
                    nj, ni = data.shape
                    grid = xr.DataArray(data, coords={"j": np.arange(1,nj+1), "i": np.arange(1,ni+1)}, dims=("j","i"))
                    fig.grdimage(grid=grid, projection="X13c/10c", cmap=True, nan_transparent=True,
                                 frame=["xaf+lGlobal column i", "yaf+lGlobal row j", "+t"+title])
                else:
                    lon, lat = field(ds, "TLON"), field(ds, "TLAT")
                    for key, coord in (("TLON", lon), ("TLAT", lat)):
                        units = str(getattr(variable(ds,key), "units", "")).lower().strip()
                        if units in ("radian", "radians", "rad"):
                            coord[:] = np.rad2deg(coord)
                        elif units not in ("degrees_east", "degree_east", "degrees_north", "degree_north", "degrees", "degree"):
                            raise ValueError(f"unrecognised {key} units: {units}")
                        if coord.shape != data.shape or np.any(np.ma.getmaskarray(coord)[good]) or not np.isfinite(coord.data[good]).all():
                            raise ValueError("missing or incompatible geographical grid")
                    fig.basemap(region="g", projection="W0/16c", frame=["af", "+t"+title])
                    fig.plot(x=lon.data[good], y=lat.data[good], fill=data[good], style="c0.035c", cmap=True)
                units = str(getattr(variable(ds,name), "units", "dimensionless"))
                fig.colorbar(frame=["xaf", "y+l"+units])
                outputs.extend(self._save(fig, source.stem+"_"+name, [source],
                    "Measured history; inactive/masked cells omitted. Global plots use cell-centre symbols; no remapping. Snapshot does not certify validity."))
        return outputs

    def timeseries(self, run, name="dtens_gcand", stream="hourly"):
        """Separate daily means from hourly instants; omit the pre-forcing IC stream."""
        if stream not in ("daily", "hourly"):
            raise ValueError("stream must be daily or hourly")
        pygmt = _pygmt()
        root = Path(run) / "history"
        pattern = "iceh_inst.*.nc" if stream == "hourly" else "iceh.????-??-??.nc"
        files = sorted(root.glob(pattern))
        if not files:
            raise ValueError("no matching history stream")
        records = []
        origin = None
        for path in files:
            with Dataset(path) as ds:
                mask = field(ds, "tmask")
                if np.any(~np.ma.getmaskarray(mask) & (~np.isfinite(mask.data) | (mask.data < 0) | (mask.data > 1))):
                    raise ValueError("invalid tmask")
                x = field(ds, name)
                if x.shape != mask.shape:
                    raise ValueError("time-series field/grid shapes differ")
                valid = ~np.ma.getmaskarray(mask) & (mask.data > .5) & ~np.ma.getmaskarray(x)
                values = x.data[valid]
                if not values.size or not np.isfinite(values).all():
                    raise ValueError("missing/nonfinite ocean field")
                time = ds['time']
                if time.size != 1:
                    raise ValueError("requires single-record history files")
                date = num2date(time[:], units=time.units, calendar=getattr(time,"calendar","standard"))[0]
                if origin is None:
                    origin = date
                days = (date-origin).total_seconds()/86400
                records.append([days, float(values.min()), float(values.mean()), float(values.max()), str(path)])
        rows = np.array([r[:4] for r in records], dtype=float)
        if np.any(np.diff(rows[:,0]) <= 0):
            raise ValueError("history times are not strictly increasing")
        self.paths.evidence.mkdir(parents=True, exist_ok=True)
        stem = Path(run).name+"_"+name+"_"+stream
        with (self.paths.evidence/(stem+".csv")).open('w') as out:
            writer = csv.writer(out); writer.writerow(['days_from_first_record','ocean_min','ocean_cell_mean','ocean_max','source']); writer.writerows(records)
        fig = pygmt.Figure()
        fig.basemap(region=_range(rows[:,0])+_range(rows[:,1:4].ravel()), projection="X14c/8c",
                    frame=["xaf+lDays since first record", "yaf+l"+name, "+t"+Path(run).name+": "+stream])
        for index, label, color in ((1,"Minimum","#888888"),(2,"Cell mean","#007C91"),(3,"Maximum","#D2691E")):
            fig.plot(x=rows[:,0], y=rows[:,index], pen="1.4p,"+color, label=label)
        fig.legend(position="JTR+jTR+o0.2c", box="+gwhite+p0.4p")
        return self._save(fig, stem, files, "Measured ocean-cell statistics; mean is not area-weighted. Daily means/hourly instants kept separate; IC omitted.", extra={"time_origin": str(origin)})

    def comparison(self, run, reference, folder="history", exclude_block_ownership=False):
        """Measured maximum absolute differences, plus metadata/mask discrepancies.

        Includes every variable and every file in one stream/folder. No validation
        gate is awarded. Differences of different units are drawn separately.
        """
        if folder not in ("history", "restart"):
            raise ValueError("folder must be history or restart")
        pygmt = _pygmt()
        run, reference = Path(run), Path(reference)
        files = sorted((run/folder).glob('*.nc'))
        if not files or {p.name for p in files} != {p.name for p in (reference/folder).glob('*.nc')}:
            raise ValueError("missing or different file inventories")
        rows = []
        for path in files:
            with Dataset(path) as a, Dataset(reference/folder/path.name) as b:
                if set(a.variables) != set(b.variables):
                    raise ValueError("variable inventories differ")
                if {n:len(d) for n,d in a.dimensions.items()} != {n:len(d) for n,d in b.dimensions.items()}:
                    raise ValueError("dimensions differ")
                for name in sorted(a.variables):
                    if a[name].dimensions != b[name].dimensions:
                        raise ValueError("variable dimension order differs")
                    for attr in ('units','calendar','bounds','time_rep'):
                        if getattr(a[name],attr,None) != getattr(b[name],attr,None):
                            raise ValueError(f"metadata differs: {name}:{attr}")
                    x,y = np.ma.asarray(a[name][:]),np.ma.asarray(b[name][:])
                    masks_equal = np.array_equal(np.ma.getmaskarray(x),np.ma.getmaskarray(y))
                    xx,yy=x.compressed(),y.compressed()
                    excluded = exclude_block_ownership and folder=='history' and name=='blkmask'
                    numeric = np.issubdtype(x.dtype,np.number)
                    if numeric and (not np.isfinite(xx).all() or not np.isfinite(yy).all()):
                        raise ValueError("nonfinite compared values")
                    error = float(np.max(np.abs(xx.astype(float)-yy.astype(float)))) if numeric and masks_equal and xx.size else None
                    equal = masks_equal and np.array_equal(xx,yy)
                    rows.append({'file':path.name,'variable':name,'units':str(getattr(a[name],'units','')),
                                 'max_abs_error':error,'masks_equal':masks_equal,'values_equal':equal,'excluded':excluded})
        self.paths.evidence.mkdir(parents=True, exist_ok=True)
        stem=run.name+"_vs_"+reference.name+"_"+folder
        with (self.paths.evidence/(stem+".csv")).open('w') as out:
            writer=csv.DictWriter(out,fieldnames=list(rows[0])); writer.writeheader();writer.writerows(rows)
        groups={}
        for row in rows:
            if row['max_abs_error'] is not None and not row['excluded']:
                key=(row['variable'],row['units'])
                groups[key]=max(groups.get(key,0.),row['max_abs_error'])
        outputs=[]
        # Plot only variables requested by the notebook/CLI? All numerical fields
        # are available in CSV; one figure per differing field or cohesion field.
        selected=[(key,error) for key,error in groups.items() if error>0 or re.match(r'(dtens_|dyntens_g|ktens_)',key[0])]
        if not selected:
            selected=list(groups.items())[:1]
        for (name,unit),error in selected:
            fig=pygmt.Figure()
            upper=max(error*1.15,1e-12)
            fig.basemap(region=[0,1,0,upper],projection="X11c/7c",
                        frame=["x+lAll matched file pairs", "yaf+lMaximum absolute difference", "+t"+name+" ("+unit+")"])
            fig.plot(x=[.5], y=[error], style="c0.22c", fill="#007C91")
            fig.text(x=.5,y=upper*.85,text=f"Measured max: {error:.5g}",font="11p")
            outputs.extend(self._save(fig,stem+"_"+name,files+[reference/folder/x.name for x in files],
                          "Descriptive maximum, not a gate. CSV includes mask/value equality and exclusions; zero error alone does not certify restart/decomposition validation.",
                          extra={"mask_mismatch_rows":sum(not r['masks_equal'] for r in rows),"excluded_block_ownership":exclude_block_ownership}))
        return outputs

    def fsd_classes(self, restart, grid_history):
        from ..validation.validators import RestartFSDDiagnostic
        pygmt = _pygmt()
        result, detail = RestartFSDDiagnostic(grid_history).diagnose(restart)
        stats = result[0]
        from ..validation.fsd import CLASSES
        fig = pygmt.Figure()
        with fig.subplot(nrows=1,ncols=2,figsize=(18,8),margins="0.4c"):
            for panel,region in enumerate(('SH','NH')):
                with fig.set_panel(panel=panel):
                    total=sum(r['area'] for r in stats[region].values())
                    values=[100*stats[region][c]['area']/total if total else 0 for c in CLASSES]
                    fig.basemap(region=[-.5,3.5,0,105],projection="X?",frame=["x+lClass index (0 normalised; 1 zero; 2 other; 3 invalid)","yaf+lOccupied ocean ice area (%)","+t"+region])
                    fig.plot(x=range(4),y=values,style="b0.7c",fill="#007C91")
        return self._save(fig,Path(restart).stem+"_fsd_classes",[restart,grid_history],
                          "Descriptive FSD classification; ice area is aicen*tarea, not extent. Empty hemisphere plotted as zeros. Diagnosis completion is not FSD validation.")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['mapping','snapshot','timeseries','comparison','fsd'])
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--scope',choices=['box','global'],default='box')
    parser.add_argument('--history',type=Path)
    parser.add_argument('--run',type=Path)
    parser.add_argument('--reference',type=Path)
    parser.add_argument('--restart',type=Path)
    parser.add_argument('--field',default='dtens_gcand')
    parser.add_argument('--stream',choices=['daily','hourly'],default='hourly')
    parser.add_argument('--folder',choices=['history','restart'],default='history')
    parser.add_argument('--exclude-block-ownership',action='store_true')
    args=parser.parse_args()
    plots=ValidationFigures(FigureSpec(args.output,args.scope))
    required={'mapping':(), 'snapshot':('history',), 'timeseries':('run',), 'comparison':('run','reference'), 'fsd':('restart','history')}
    for key in required[args.action]:
        if getattr(args,key) is None:
            parser.error('--'+key+' is required for '+args.action)
    if args.action=='mapping': outputs=plots.mapping()
    elif args.action=='snapshot': outputs=plots.snapshot(args.history,names=(args.field,))
    elif args.action=='timeseries': outputs=plots.timeseries(args.run,args.field,args.stream)
    elif args.action=='comparison': outputs=plots.comparison(args.run,args.reference,args.folder,args.exclude_block_ownership)
    else: outputs=plots.fsd_classes(args.restart,args.history)
    for path in outputs: print(path)

if __name__=='__main__':
    main()
