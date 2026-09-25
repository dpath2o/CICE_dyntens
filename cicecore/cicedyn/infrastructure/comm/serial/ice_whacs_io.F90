! Serial interface for the MPI-only WHACS reader.
! Non-WHACS cases need this module because ice_forcing imports its interface.
! Do not silently substitute zero waves if WHACS is requested in serial mode.
module ice_whacs_io
   use ice_kinds_mod, only: int_kind, real_kind
   use ice_blocks, only: nx_block, ny_block
   use ice_domain_size, only: nfreq, max_blocks
   use ice_exit, only: abort_ice
   implicit none
   private
   public :: ice_read_nc_xyf_whacs
contains
   subroutine ice_read_nc_xyf_whacs(filename, nrec, work)
      character(len=*), intent(in) :: filename
      integer(kind=int_kind), intent(in) :: nrec
      real(kind=real_kind), intent(out) :: work(nx_block,ny_block,nfreq,max_blocks)

      call abort_ice('WHACS spectral forcing requires the MPI communication build', &
                     file=__FILE__, line=__LINE__)
   end subroutine ice_read_nc_xyf_whacs
end module ice_whacs_io
