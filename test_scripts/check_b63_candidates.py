#!/usr/bin/env python3
# dpath2o: dyntens
# Check candidate diagnostics and optionally compare a matching control history.
import argparse
from pathlib import Path
import re
import numpy as np
from netCDF4 import Dataset

BASES = ('dyntens_large_fraction', 'dyntens_g_candidate',
         'ktens_eff_candidate', 'dyntens_mapping_status')


def is_candidate(name):
    return any(re.fullmatch(re.escape(b)+r'(?:_\w+)?', name) for b in BASES)


def close(actual, expected, tol, label):
    if not np.all(np.isfinite(actual)) or not np.all(np.abs(actual-expected) <= tol):
        raise ValueError(label)


def check_dataset(ds, ktens, gmin, tol):
    families = [{n[len(b):]: n for n in ds.variables
                 if re.fullmatch(re.escape(b)+r'(?:_\w+)?', n)} for b in BASES]
    if not families[0] or any(set(f)!=set(families[0]) for f in families):
        raise ValueError('missing candidate field or mismatched stream suffixes')
    for suffix in families[0]:
        variables = [ds.variables[f[suffix]] for f in families]
        if any(v.dimensions!=variables[0].dimensions for v in variables):
            raise ValueError('candidate dimensions differ')
        frac,g,k,status = [np.ma.asarray(v[:]) for v in variables]
        if any(x.shape!=g.shape for x in (frac,k,status)):
            raise ValueError('candidate shapes differ')
        mask = np.ma.getmaskarray(g)
        if not np.array_equal(mask,np.ma.getmaskarray(k)) or not np.array_equal(mask,np.ma.getmaskarray(status)):
            raise ValueError('candidate coefficient/status masks differ')
        valid = ~mask
        if not np.any(valid):
            raise ValueError('no unmasked candidate cells')
        gv,kv,sv = [np.asarray(x)[valid] for x in (g,k,status)]
        if any(not np.all(np.isfinite(x)) for x in (gv,kv,sv)):
            raise ValueError('nonfinite candidate')
        if np.any((sv < -tol) | (sv > 1+tol)):
            raise ValueError('inactive sample fraction outside [0,1]')
        if np.any((gv < gmin-tol) | (gv > 1+tol)):
            raise ValueError('candidate g outside bounds')
        close(kv,ktens*gv,tol,'candidate ktens != Ktens*g')
        fm = np.ma.getmaskarray(frac)
        if np.any(~fm & mask):
            raise ValueError('fraction unmasked outside coefficient mask')
        # Any inactive sample poisons the fraction interval, even if very rare.
        if np.any(valid & (np.asarray(status)>0) & ~fm):
            raise ValueError('inactive interval has unmasked large fraction')
        if np.any(valid & (np.asarray(status)==0) & fm):
            raise ValueError('valid interval has masked large fraction')
        active = valid & ~fm
        fv = np.asarray(frac)[active]
        if np.any((fv < -tol) | (fv > 1+tol)):
            raise ValueError('large fraction outside bounds')
        close(np.asarray(g)[active],gmin+(1-gmin)*fv,tol,'candidate mapping equation')
        inactive = valid & (np.asarray(status)==1)
        close(np.asarray(g)[inactive],1.,tol,'inactive g != 1')
    for base,value in [('dyntens_g',1.),('ktens_eff',ktens)]:
        names=[n for n in ds.variables if re.fullmatch(re.escape(base)+r'(?:_\w+)?',n) and not is_candidate(n)]
        if not names:
            raise ValueError(f'missing applied coefficient {base}')
        for name in names:
            data=np.ma.asarray(ds[name][:]).compressed()
            if data.size==0:
                raise ValueError(f'applied coefficient entirely masked: {name}')
            close(data,value,tol,f'applied {name} differs from control')


def compare_history(left,right):
    names = [{n for n in ds.variables if not is_candidate(n)} for ds in (left,right)]
    if names[0]!=names[1]:
        raise ValueError('control variable sets differ outside candidate diagnostics')
    for name in sorted(names[0]):
        a,b=left[name],right[name]
        if a.dimensions!=b.dimensions or a.shape!=b.shape:
            raise ValueError(f'control dimensions differ: {name}')
        x,y=np.ma.asarray(a[:]),np.ma.asarray(b[:])
        if not np.array_equal(np.ma.getmaskarray(x),np.ma.getmaskarray(y)):
            raise ValueError(f'control masks differ: {name}')
        if not np.array_equal(x.compressed(),y.compressed()):
            raise ValueError(f'control values differ: {name}')


def history(path):
    path=Path(path)
    return path/'history' if (path/'history').is_dir() else path


def main():
    p=argparse.ArgumentParser()
    p.add_argument('run')
    p.add_argument('--control')
    p.add_argument('--ktens',type=float,default=.2)
    p.add_argument('--gmin',type=float,default=.2)
    p.add_argument('--atol',type=float,default=1.e-10)
    args=p.parse_args()
    if not all(np.isfinite(x) for x in (args.ktens,args.gmin,args.atol)) or args.atol<0:
        p.error('parameters must be finite and tolerance nonnegative')
    if not (0<=args.ktens<=1 and 0<=args.gmin<=1):
        p.error('coefficients must be in [0,1]')
    files=sorted(history(args.run).glob('iceh*.nc'))
    if not files:
        p.error('no iceh*.nc files')
    if args.control:
        if {f.name for f in files}!={f.name for f in history(args.control).glob('iceh*.nc')}:
            p.error('control history file sets differ')
    for file in files:
        with Dataset(file) as ds:
            check_dataset(ds,args.ktens,args.gmin,args.atol)
            if args.control:
                with Dataset(history(args.control)/file.name) as control:
                    compare_history(ds,control)
        print('PASS',file.name)
    print(f'PASS B6.3 candidate history: {len(files)} files')
    if args.control:
        print('PASS exact decoded control history comparison (candidate diagnostics excluded)')


if __name__=='__main__':
    main()
# dpath2o: dyntens
