#!/usr/bin/env python3
"""Compile production shadow fixtures/mapping against audited native 12-bin radii."""
import argparse
import os
from pathlib import Path
from importlib.resources import files
from ..core.paths import model_repo
import re
import shlex
import subprocess
import tempfile


class NativeBinFixtures:
    """Compile the production model source and check independent analytical answers."""
    def __init__(self, repo, fc="gfortran", fflags="-O0 -g"):
        self.repo = Path(repo).expanduser().resolve()
        self.fc = fc
        self.fflags = fflags

    def run(self):
        repo = self.repo
        source=(repo/'icepack/columnphysics/icepack_fsd.F90').read_text()
        section=source.split('else if (nfsd.eq.12) then',1)[1].split('else if',1)[0]
        bounds=section.split('lims = (/',1)[1].split('/)',1)[0]
        radii=[float(x) for x in re.findall(r'[0-9]+\.[0-9]+e[+-][0-9]+',bounds,re.I)]
        assert len(radii)==13, 'native 12-bin radius bounds not found'
        diam=[radii[k]+radii[k+1] for k in range(12)]
        assert diam[5]<300<diam[6], 'native bin classification changed'
        values=', &\n'.join('    '+format(x,'.17e')+'_dyntens_kind' for x in diam)
        driver='''program fixtures
      use ice_dyntens_mapping
      implicit none
      character(len=16), parameter :: modes(7)=[character(len=16):: &
           'small','large','mixed','unequal','dilute','inactive','spatial']
      real(dyntens_kind) :: a(5), f(12,5), d(12), fraction, g, k
      integer :: mode, col, status
      d=[ &
    DIAMETERS ]
      do mode=1,7
        do col=1,12
          call dyntens_box_inputs(modes(mode),col,a,f,status)
          if(status/=dyntens_ok) stop 1
          call dyntens_map_fsd(a,f,d,300._dyntens_kind,0.2_dyntens_kind,0.2_dyntens_kind, &
                              fraction,g,k,status)
          write(*,'(a,1x,i2,1x,i2,3(1x,es24.16))') trim(modes(mode)),col,status,fraction,g,k
        enddo
      enddo
      call dyntens_box_inputs('unknown',1,a,f,status)
      if(status/=dyntens_bad_parameter) stop 2
      call dyntens_box_inputs('spatial',0,a,f,status)
      if(status/=dyntens_bad_parameter) stop 3
      call dyntens_box_inputs('small',1,a(:1),f(:,:1),status)
      if(status/=dyntens_bad_shape) stop 4
    end program fixtures
    '''.replace('DIAMETERS',values)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'driver.F90').write_text(driver)
            command=shlex.split(self.fc)+shlex.split(self.fflags)+[
                str(repo/'cicecore/cicedyn/dynamics/ice_dyntens_mapping.F90'),
                str(root/'driver.F90'),'-o',str(root/'fixtures')]
            subprocess.run(command,cwd=root,check=True)
            output=subprocess.check_output([str(root/'fixtures')],cwd=root,universal_newlines=True)
        lines=output.splitlines()
        assert len(lines)==84, 'expected 84 fixture/column results'
        for line in lines:
            mode,column,status,frac,g,k=line.split()
            column,status=int(column),int(status)
            frac,g,k=map(float,(frac,g,k))
            expected={'small':0.,'large':1.,'mixed':.5,'unequal':2/3,'dilute':2/3,
                      'inactive':-1.,'spatial':0. if column==6 else 1.}[mode]
            expected_g=1. if mode=='inactive' else .2+.8*expected
            assert status==(1 if mode=='inactive' else 0), line
            assert max(abs(frac-expected),abs(g-expected_g),abs(k-.2*expected_g))<=1e-12,line
        print('PASS 84 production native-bin fixture/column answers plus three invalid fixture guards; atol=1e-12')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path)
    parser.add_argument('--fc', default=os.environ.get('FC', 'gfortran'))
    parser.add_argument('--fflags', default=os.environ.get('FFLAGS', '-O0 -g'))
    args = parser.parse_args()
    NativeBinFixtures(args.repo or model_repo(), args.fc, args.fflags).run()


if __name__=='__main__':
    main()
