! dpath2o: dyntens
! Read one fixture and report the production routine's result.
program b6_mapping_driver
  use ice_dyntens_mapping
  implicit none
  integer :: nk, nc, nf, mf, n, status
  real(dyntens_kind), allocatable :: a(:), f(:,:), d(:)
  real(dyntens_kind) :: threshold, gmin, ktens, fraction, g, effective
  read(*,*) nk,nc,nf,mf
  allocate(a(nc),f(nf,mf),d(nk))
  read(*,*) threshold,gmin,ktens
  read(*,*) a
  read(*,*) d
  do n=1,mf
    read(*,*) f(:,n)
  enddo
  call dyntens_map_fsd(a,f,d,threshold,gmin,ktens,fraction,g,effective,status)
  write(*,'(i0,3(1x,es25.16e3))') status,fraction,g,effective
end program b6_mapping_driver
! dpath2o: dyntens
