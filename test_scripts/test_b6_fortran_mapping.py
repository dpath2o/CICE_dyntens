#!/usr/bin/env python3
# dpath2o: dyntens
# Compile the production routine and compare it with analytical fixtures.
import argparse
import math
import os
from pathlib import Path
import shlex
import subprocess
import tempfile


def fixtures():
    cases = []

    def add(name, a=(.9,), f=((.5, .5),), d=(100., 1000.),
            threshold=300., gmin=.2, ktens=.2, status=0, fraction=.5):
        cases.append((name, a, f, d, threshold, gmin, ktens, status, fraction))

    add('small', f=((1., 0.),), fraction=0.)
    add('large', f=((0., 1.),), fraction=1.)
    add('mixture')
    for x in (0., .1, .25, .5, .75, .9, 1.):
        add(f'sweep_{x}', f=((1-x, x),), fraction=x)
    for a in ((.3, .6), (.1, .2)):
        add(f'area_{a}', a=a, f=((1., 0.), (0., 1.)), fraction=2/3)
    add('empty_ignored', a=(0., .9), f=((math.nan, -1.), (0., 1.)), fraction=1.)
    for a in (0., 1.e-13, 1.e-12):
        add(f'inactive_{a}', a=(a,), f=((math.nan, math.nan),), status=1)
    add('tiny_positive_category_checked', a=(1.e-15, .9),
        f=((0., 0.), (0., 1.)), status=6)
    add('unity', gmin=1.)
    add('zero_ktens', ktens=0.)
    for d in (100., 299., 300., 301., 1000.):
        add(f'diameter_{d}', d=(d,), f=((1.,),), fraction=float(d>300))
    edges = (.0665,5.31030847,14.2865861,29.0576686,52.4122136,
             87.8691405,139.518470,211.635752,308.037274,431.203059,
             581.277225,755.141047,945.812834)
    diam = tuple(x+y for x,y in zip(edges, edges[1:]))
    for k in range(12):
        f = tuple(float(j==k) for j in range(12))
        add(f'native_bin_{k+1}', d=diam, f=(f,), fraction=float(k>=6))
    add('roundoff_no_renormalisation', f=((.5, .5+5.e-11),), fraction=.5+5.e-11)
    add('roundoff_clip', f=((0., 1.+5.e-11),), fraction=1.)
    for a in (-.1, math.nan, math.inf, 1.01):
        add(f'bad_area_{a}', a=(a,), status=5)
    add('bad_total_area', a=(.6, .6), f=((.5,.5),(.5,.5)), status=5)
    for f in ((0.,0.),(-1.e-15,1.),(math.nan,1.),(math.inf,0.),(.5,.50001)):
        add(f'bad_fsd_{f}', f=(f,), status=6)
    for d in ((1000.,100.),(100.,100.),(0.,1000.),(math.nan,1000.),(100.,math.inf)):
        add(f'bad_diameter_{d}', d=d, status=4)
    for v in (0., -1., math.nan, math.inf):
        add(f'bad_threshold_{v}', threshold=v, status=3)
    for v in (-.1, 1.1, math.nan, math.inf):
        add(f'bad_gmin_{v}', gmin=v, status=3)
        add(f'bad_ktens_{v}', ktens=v, status=3)
    add('bad_bin_shape', d=(100.,), status=2)
    add('bad_category_shape', a=(.4,.5), status=2)
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fc', default=os.environ.get('FC', 'gfortran'))
    parser.add_argument('--fflags', default=os.environ.get('FFLAGS', '-O0 -g'))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sources = [root/'cicecore/cicedyn/dynamics/ice_dyntens_mapping.F90',
               root/'test_scripts/b6_mapping_driver.F90']
    with tempfile.TemporaryDirectory(prefix='b6-fortran-') as tmp:
        exe = Path(tmp)/'mapping_test'
        command = shlex.split(args.fc)+shlex.split(args.fflags)+[str(p) for p in sources]+['-o',str(exe)]
        print('BUILD:', ' '.join(shlex.quote(arg) for arg in command), flush=True)
        subprocess.run(command, cwd=tmp, check=True)
        cases = fixtures()
        for name,a,f,d,threshold,gmin,ktens,status,fraction in cases:
            lines = [f'{len(d)} {len(a)} {len(f[0])} {len(f)}',
                     f'{threshold} {gmin} {ktens}',
                     ' '.join(map(str,a)), ' '.join(map(str,d))]
            lines += [' '.join(map(str,row)) for row in f]
            result = subprocess.run([str(exe)], input='\n'.join(lines)+'\n',
                                    universal_newlines=True, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, check=True)
            fields = result.stdout.split()
            if len(fields)!=4 or int(fields[0])!=status:
                raise AssertionError((name, 'status/output', result.stdout, status))
            actual = [float(x.replace('D','E')) for x in fields[1:]]
            if status==0:
                g = gmin+(1-gmin)*fraction
                expected = [fraction,g,ktens*g]
            elif status==1:
                expected = [-1.,1.,ktens]
            else:
                expected = [-1.,-1.,-1.]
            if any(not math.isfinite(x) or abs(x-y)>1.e-12 for x,y in zip(actual,expected)):
                raise AssertionError((name, actual, expected))
            print('PASS',name, *actual)
        print(f'PASS: {len(cases)} production Fortran fixtures (absolute tolerance 1e-12)')


if __name__ == '__main__':
    main()
# dpath2o: dyntens
