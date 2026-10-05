! dpath2o: dyntens
! Map integrated category FSD fractions to a candidate tensile coefficient.
module ice_dyntens_mapping
  use, intrinsic :: ieee_arithmetic, only: ieee_is_finite
  implicit none
  private
  integer, parameter, public :: dyntens_kind = selected_real_kind(13)
  integer, parameter, public :: dyntens_ok=0, dyntens_inactive=1, &
       dyntens_bad_shape=2, dyntens_bad_parameter=3, dyntens_bad_diameter=4, &
       dyntens_bad_area=5, dyntens_bad_fsd=6
  real(dyntens_kind), parameter :: sum_tol=1.e-10_dyntens_kind, &
       area_min=1.e-12_dyntens_kind
  public :: dyntens_map_fsd
contains
  pure subroutine dyntens_map_fsd(area, fsd, diameter, threshold, gmin, ktens, &
                                 large_fraction, g, ktens_eff, status)
    real(dyntens_kind), intent(in) :: area(:), fsd(:,:), diameter(:)
    real(dyntens_kind), intent(in) :: threshold, gmin, ktens
    real(dyntens_kind), intent(out) :: large_fraction, g, ktens_eff
    integer, intent(out) :: status
    real(dyntens_kind) :: total_area, fraction, bin_sum
    integer :: n

    ! Undefined outputs stay negative; callers must inspect status.
    large_fraction=-1._dyntens_kind
    g=-1._dyntens_kind
    ktens_eff=-1._dyntens_kind
    status=dyntens_bad_shape
    if (size(area)<1 .or. size(diameter)<1) return
    if (size(fsd,1)/=size(diameter) .or. size(fsd,2)/=size(area)) return

    status=dyntens_bad_parameter
    if (.not.ieee_is_finite(threshold)) return
    if (.not.ieee_is_finite(gmin) .or. .not.ieee_is_finite(ktens)) return
    if (threshold<=0._dyntens_kind) return
    if (gmin<0._dyntens_kind .or. gmin>1._dyntens_kind) return
    if (ktens<0._dyntens_kind .or. ktens>1._dyntens_kind) return

    status=dyntens_bad_diameter
    if (.not.all(ieee_is_finite(diameter))) return
    if (any(diameter<=0._dyntens_kind)) return
    if (any(diameter(2:)<=diameter(:size(diameter)-1))) return

    status=dyntens_bad_area
    if (.not.all(ieee_is_finite(area))) return
    if (any(area<0._dyntens_kind) .or. any(area>1._dyntens_kind+sum_tol)) return
    total_area=sum(area)
    if (.not.ieee_is_finite(total_area)) return
    if (total_area>1._dyntens_kind+sum_tol) return
    if (total_area<=area_min) then
      status=dyntens_inactive
      g=1._dyntens_kind
      ktens_eff=ktens
      return
    endif

    ! Validate every occupied category without repairing the input.
    status=dyntens_bad_fsd
    fraction=0._dyntens_kind
    do n=1,size(area)
      if (area(n)==0._dyntens_kind) cycle
      if (.not.all(ieee_is_finite(fsd(:,n)))) return
      if (any(fsd(:,n)<0._dyntens_kind)) return
      if (any(fsd(:,n)>1._dyntens_kind+sum_tol)) return
      bin_sum=sum(fsd(:,n))
      if (.not.ieee_is_finite(bin_sum)) return
      if (abs(bin_sum-1._dyntens_kind)>sum_tol) return
      fraction=fraction+(area(n)/total_area)*sum(fsd(:,n),mask=diameter>threshold)
    enddo
    if (.not.ieee_is_finite(fraction)) return
    if (fraction< -sum_tol .or. fraction>1._dyntens_kind+sum_tol) return
    large_fraction=max(0._dyntens_kind,min(1._dyntens_kind,fraction))
    g=gmin+(1._dyntens_kind-gmin)*large_fraction
    ktens_eff=ktens*g
    status=dyntens_ok
  end subroutine dyntens_map_fsd
end module ice_dyntens_mapping
! dpath2o: dyntens
