#ifdef ncdf
#define USE_NETCDF
#endif
!=======================================================================
!
! MPI-only WHACS spectral forcing reader for standalone CICE.
!
! Purpose
! -------
! Read one hourly WHACS spectrum as float32 on the master MPI task,
! distribute the complete nfreq spectrum in one message per CICE block,
! and fill CICE halos using the existing boundary machinery.
!
! This module intentionally lives under comm/mpi.  The serial CICE
! communication implementation is not modified by this experiment.
!
!=======================================================================

module ice_whacs_io

   use mpi

   use, intrinsic :: ieee_arithmetic, only: &
        ieee_is_finite

   use ice_kinds_mod

   use ice_constants, only: &
        c0, &
        field_loc_center, &
        field_type_scalar

   use ice_blocks, only: &
        block, &
        nx_block, &
        ny_block, &
        nblocks_tot, &
        get_block

   use ice_domain_size, only: &
        nx_global, &
        ny_global, &
        max_blocks, &
        nfreq

   use ice_domain, only: &
        distrb_info, &
        halo_info

   use ice_communicate, only: &
        my_task, &
        master_task, &
        mpiR4, &
        mpiR8, &
        mpitag_gs, &
        MPI_COMM_ICE

   use ice_boundary, only: &
        ice_HaloUpdate

   use ice_exit, only: &
        abort_ice

   use ice_fileunits, only: &
        nu_diag

#ifdef USE_NETCDF
   use netcdf
#endif

   implicit none

   private

   public :: &
        ice_read_nc_xyf_whacs

   !--------------------------------------------------------------------
   ! Persistent master-side NetCDF state.
   !--------------------------------------------------------------------
   integer (kind=int_kind), save :: &
        whacs_fid   = -1_int_kind, &
        whacs_varid = -1_int_kind, &
        whacs_nt    = 0_int_kind

   logical (kind=log_kind), save :: &
        whacs_file_is_open = .false.

   character(char_len_long), save :: &
        whacs_open_filename = ' '

   !--------------------------------------------------------------------
   ! Persistent global read buffer.
   !
   ! Source WHACS files are float32, therefore real_kind preserves the
   ! source precision while halving the master-side forcing buffer
   ! relative to the legacy dbl_kind ice_read_nc_xyf path.
   !--------------------------------------------------------------------
   real (kind=real_kind), dimension(:,:,:), allocatable, save :: &
        whacs_global_buffer

   !--------------------------------------------------------------------
   ! Sparse diagnostic counter.
   !--------------------------------------------------------------------
   integer (kind=int_kind), save :: &
        whacs_read_count = 0_int_kind

contains

!=======================================================================

subroutine ice_read_nc_xyf_whacs(filename,nrec,work)

   character(len=*), intent(in) :: &
        filename

   integer (kind=int_kind), intent(in) :: &
        nrec

   real (kind=real_kind), &
        dimension(nx_block,ny_block,nfreq,max_blocks), &
        intent(out) :: &
        work

   logical (kind=log_kind) :: &
        report_memory

   character(len=*), parameter :: &
        subname = '(ice_read_nc_xyf_whacs)'

#ifdef USE_NETCDF

   !--------------------------------------------------------------------
   ! Allocate the persistent global slab once.
   ! Non-master tasks retain only a one-element placeholder.
   !--------------------------------------------------------------------
   if (.not. allocated(whacs_global_buffer)) then

      if (my_task == master_task) then
         allocate( &
              whacs_global_buffer( &
                   nx_global, &
                   ny_global, &
                   nfreq))
      else
         allocate(whacs_global_buffer(1,1,1))
      endif

      whacs_global_buffer = real(c0,kind=real_kind)

   endif

   !--------------------------------------------------------------------
   ! Every MPI task increments the same logical read counter because this
   ! routine is collective with respect to the ice communicator.
   !--------------------------------------------------------------------
   whacs_read_count = whacs_read_count + 1_int_kind

   report_memory = &
        whacs_read_count <= 6_int_kind .or. &
        mod(whacs_read_count,24_int_kind) == 0_int_kind

   !--------------------------------------------------------------------
   ! Open/reuse the appropriate monthly NetCDF file on master.
   !--------------------------------------------------------------------
   call whacs_open_file(trim(filename))

   if (my_task == master_task) then

      if (nrec < 1_int_kind .or. nrec > whacs_nt) then

         write(nu_diag,*) &
              subname//' invalid record: ', &
              nrec, ' valid range = 1:',whacs_nt

         call abort_ice( &
              subname//' ERROR: WHACS record outside file', &
              file=__FILE__, line=__LINE__)

      endif

   endif

   !--------------------------------------------------------------------
   ! Read exactly one global hourly spectrum on master.
   !
   ! WHACS file layout:
   !
   !     efreq(time,nfreq,nj,ni)
   !
   ! Fortran NetCDF view:
   !
   !     efreq(ni,nj,nfreq,time)
   !--------------------------------------------------------------------
   if (my_task == master_task) then

      whacs_global_buffer = real(c0,kind=real_kind)

      call whacs_nc_check( &
           nf90_get_var( &
                whacs_fid, &
                whacs_varid, &
                whacs_global_buffer, &
                start=(/1,1,1,nrec/), &
                count=(/nx_global,ny_global,nfreq,1/)), &
           subname//' ERROR reading efreq record')

   endif

   if (report_memory) then
      call whacs_report_memory( &
           'after_read', &
           trim(filename), &
           nrec)
   endif

   !--------------------------------------------------------------------
   ! Distribute the complete spectral block in one MPI message per CICE
   ! block, then populate ghost cells with CICE's halo machinery.
   !--------------------------------------------------------------------
   call whacs_scatter_spectrum( &
        work, &
        whacs_global_buffer)

   if (report_memory) then
      call whacs_report_memory( &
           'after_scatter', &
           trim(filename), &
           nrec)
   endif

#else

   work = real(c0,kind=real_kind)

   call abort_ice( &
        subname//' ERROR: USE_NETCDF cpp not defined', &
        file=__FILE__, line=__LINE__)

#endif

end subroutine ice_read_nc_xyf_whacs

!=======================================================================

subroutine whacs_open_file(filename)

   character(len=*), intent(in) :: &
        filename

#ifdef USE_NETCDF

   integer (kind=int_kind) :: &
        ndims, &
        dimlen

   integer (kind=int_kind), dimension(10) :: &
        dimids

   character(len=*), parameter :: &
        subname = '(whacs_open_file)'

   !--------------------------------------------------------------------
   ! Only the master task owns the serial NetCDF file handle.
   !--------------------------------------------------------------------
   if (my_task /= master_task) return

   if (whacs_file_is_open) then

      if (trim(filename) == trim(whacs_open_filename)) then
         return
      endif

      call whacs_nc_check( &
           nf90_close(whacs_fid), &
           subname//' ERROR closing previous WHACS file')

      whacs_file_is_open = .false.
      whacs_fid          = -1_int_kind
      whacs_varid        = -1_int_kind
      whacs_nt           = 0_int_kind

   endif

   call whacs_nc_check( &
        nf90_open( &
             trim(filename), &
             NF90_NOWRITE, &
             whacs_fid), &
        subname//' ERROR opening '//trim(filename))

   whacs_file_is_open = .true.
   whacs_open_filename = trim(filename)

   call whacs_nc_check( &
        nf90_inq_varid( &
             whacs_fid, &
             'efreq', &
             whacs_varid), &
        subname//' ERROR finding efreq')

   call whacs_nc_check( &
        nf90_inquire_variable( &
             whacs_fid, &
             whacs_varid, &
             ndims=ndims, &
             dimids=dimids), &
        subname//' ERROR inquiring efreq')

   if (ndims /= 4) then
      call abort_ice( &
           subname//' ERROR: WHACS efreq must be 4-D', &
           file=__FILE__, line=__LINE__)
   endif

   call whacs_nc_check( &
        nf90_inquire_dimension( &
             whacs_fid, &
             dimids(1), &
             len=dimlen), &
        subname//' ERROR inquiring ni')

   if (dimlen /= nx_global) then
      call abort_ice( &
           subname//' ERROR: WHACS ni != nx_global', &
           file=__FILE__, line=__LINE__)
   endif

   call whacs_nc_check( &
        nf90_inquire_dimension( &
             whacs_fid, &
             dimids(2), &
             len=dimlen), &
        subname//' ERROR inquiring nj')

   if (dimlen /= ny_global) then
      call abort_ice( &
           subname//' ERROR: WHACS nj != ny_global', &
           file=__FILE__, line=__LINE__)
   endif

   call whacs_nc_check( &
        nf90_inquire_dimension( &
             whacs_fid, &
             dimids(3), &
             len=dimlen), &
        subname//' ERROR inquiring nfreq')

   if (dimlen /= nfreq) then
      call abort_ice( &
           subname//' ERROR: WHACS nfreq mismatch', &
           file=__FILE__, line=__LINE__)
   endif

   call whacs_nc_check( &
        nf90_inquire_dimension( &
             whacs_fid, &
             dimids(4), &
             len=whacs_nt), &
        subname//' ERROR inquiring time')

   write(nu_diag,*) &
        'WAVEIO OPEN file=',trim(filename), &
        ' records=',whacs_nt, &
        ' nfreq=',nfreq

   call flush(nu_diag)

#else

   call abort_ice( &
        '(whacs_open_file) ERROR: USE_NETCDF cpp not defined', &
        file=__FILE__, line=__LINE__)

#endif

end subroutine whacs_open_file

!=======================================================================

subroutine whacs_scatter_spectrum(work,global_spectrum)

   real (kind=real_kind), &
        dimension(nx_block,ny_block,nfreq,max_blocks), &
        intent(out) :: &
        work

   real (kind=real_kind), dimension(:,:,:), intent(in) :: &
        global_spectrum

   integer (kind=int_kind) :: &
        i, j, n, &
        iglob, jglob, &
        dst_block, &
        ierr, &
        idx_freq

   integer (kind=int_kind), dimension(MPI_STATUS_SIZE) :: &
        status

   type (block) :: &
        this_block

   real (kind=real_kind), dimension(:,:,:), allocatable :: &
        msg_buffer

   character(len=*), parameter :: &
        subname = '(whacs_scatter_spectrum)'

   work = real(c0,kind=real_kind)

   !--------------------------------------------------------------------
   ! Master packs one complete nfreq spectrum for every distributed CICE
   ! block.  Boundary/ghost values are deliberately not reconstructed
   ! here; CICE's halo update below owns that logic.
   !--------------------------------------------------------------------
   if (my_task == master_task) then

      allocate(msg_buffer(nx_block,ny_block,nfreq))

      do n = 1, nblocks_tot

         if (distrb_info%blockLocation(n) > 0) then

            msg_buffer = real(c0,kind=real_kind)

            this_block = get_block(n,n)

            do j = 1, ny_block

               jglob = this_block%j_glob(j)

               if (jglob >= 1 .and. jglob <= ny_global) then

                  do i = 1, nx_block

                     iglob = this_block%i_glob(i)

                     if (iglob >= 1 .and. iglob <= nx_global) then

                        msg_buffer(i,j,:) = &
                             global_spectrum(iglob,jglob,:)

                     endif

                  enddo

               endif

            enddo

            if (distrb_info%blockLocation(n)-1 == my_task) then

               dst_block = distrb_info%blockLocalID(n)

               work(:,:,:,dst_block) = msg_buffer(:,:,:)

            else

               call MPI_SEND( &
                    msg_buffer, &
                    nx_block*ny_block*nfreq, &
                    mpiR4, &
                    distrb_info%blockLocation(n)-1, &
                    4*mpitag_gs+n, &
                    MPI_COMM_ICE, &
                    ierr)

               if (ierr /= MPI_SUCCESS) then
                  call abort_ice( &
                       subname//' ERROR: MPI_SEND failed', &
                       file=__FILE__, line=__LINE__)
               endif

            endif

         endif

      enddo

      deallocate(msg_buffer)

   else

      !-----------------------------------------------------------------
      ! Non-master tasks receive only blocks assigned to this task.
      !-----------------------------------------------------------------
      do n = 1, nblocks_tot

         if (distrb_info%blockLocation(n) == my_task+1) then

            dst_block = distrb_info%blockLocalID(n)

            call MPI_RECV( &
                 work(1,1,1,dst_block), &
                 nx_block*ny_block*nfreq, &
                 mpiR4, &
                 master_task, &
                 4*mpitag_gs+n, &
                 MPI_COMM_ICE, &
                 status, &
                 ierr)

            if (ierr /= MPI_SUCCESS) then
               call abort_ice( &
                    subname//' ERROR: MPI_RECV failed', &
                    file=__FILE__, line=__LINE__)
            endif

         endif

      enddo

   endif

   !--------------------------------------------------------------------
   ! Do not allow any task to begin halo exchange while another task is
   ! still inside the blocking spectral scatter.
   !--------------------------------------------------------------------
   call MPI_BARRIER(MPI_COMM_ICE,ierr)

   if (ierr /= MPI_SUCCESS) then
      call abort_ice( &
           subname//' ERROR: MPI_BARRIER failed', &
           file=__FILE__, line=__LINE__)
   endif

   !--------------------------------------------------------------------
   ! Clean source fill values / NaNs before halo propagation.
   !--------------------------------------------------------------------
   where (.not. ieee_is_finite(work))
      work = real(c0,kind=real_kind)
   end where

   where (abs(work) > 1.0e30_real_kind)
      work = real(c0,kind=real_kind)
   end where

   !--------------------------------------------------------------------
   ! Restore ghost cells using the native CICE T-grid scalar boundary
   ! treatment.  A single-frequency temporary may be generated by the
   ! compiler here, but it is only nx_block*ny_block*max_blocks.
   !--------------------------------------------------------------------
   do idx_freq = 1, nfreq

      call ice_HaloUpdate( &
           work(:,:,idx_freq,:), &
           halo_info, &
           field_loc_center, &
           field_type_scalar, &
           fillValue=real(c0,kind=real_kind))

   enddo

end subroutine whacs_scatter_spectrum

!=======================================================================

subroutine whacs_report_memory(stage,filename,nrec)

   character(len=*), intent(in) :: &
        stage, &
        filename

   integer (kind=int_kind), intent(in) :: &
        nrec

   integer (kind=int_kind) :: &
        ierr

   real (kind=dbl_kind) :: &
        rss_local_mb, &
        rss_max_mb, &
        rss_sum_mb

   rss_local_mb = whacs_rss_mb()

   call MPI_ALLREDUCE( &
        rss_local_mb, &
        rss_max_mb, &
        1, &
        mpiR8, &
        MPI_MAX, &
        MPI_COMM_ICE, &
        ierr)

   if (ierr /= MPI_SUCCESS) then
      call abort_ice( &
           '(whacs_report_memory) ERROR: MPI_MAX reduction failed', &
           file=__FILE__, line=__LINE__)
   endif

   call MPI_ALLREDUCE( &
        rss_local_mb, &
        rss_sum_mb, &
        1, &
        mpiR8, &
        MPI_SUM, &
        MPI_COMM_ICE, &
        ierr)

   if (ierr /= MPI_SUCCESS) then
      call abort_ice( &
           '(whacs_report_memory) ERROR: MPI_SUM reduction failed', &
           file=__FILE__, line=__LINE__)
   endif

   if (my_task == master_task) then

      write(nu_diag,*) &
           'WHACSMEM stage=',trim(stage), &
           ' read_count=',whacs_read_count, &
           ' rec=',nrec, &
           ' master_rss_mb=',rss_local_mb, &
           ' max_rank_rss_mb=',rss_max_mb, &
           ' total_rss_gb=',rss_sum_mb/1024.0_dbl_kind, &
           ' file=',trim(filename)

      call flush(nu_diag)

   endif

end subroutine whacs_report_memory

!=======================================================================

real(kind=dbl_kind) function whacs_rss_mb()

   integer :: &
        unit, &
        ios

   integer(kind=8) :: &
        rss_kb

   integer :: &
        ipos

   character(len=256) :: &
        line

   whacs_rss_mb = -1.0_dbl_kind
   rss_kb = -1_8

   open( &
        newunit=unit, &
        file='/proc/self/status', &
        status='old', &
        action='read', &
        iostat=ios)

   if (ios /= 0) return

   do

      read(unit,'(A)',iostat=ios) line

      if (ios /= 0) exit

      ipos = index(line,'VmRSS:')

      if (ipos > 0) then

         read(line(ipos+6:),*,iostat=ios) rss_kb

         if (ios == 0 .and. rss_kb >= 0_8) then
            whacs_rss_mb = &
                 real(rss_kb,kind=dbl_kind) / 1024.0_dbl_kind
         endif

         exit

      endif

   enddo

   close(unit)

end function whacs_rss_mb

!=======================================================================

#ifdef USE_NETCDF
subroutine whacs_nc_check(status,message)

   integer, intent(in) :: &
        status

   character(len=*), intent(in) :: &
        message

   if (status /= nf90_noerr) then

      if (my_task == master_task) then
         write(nu_diag,*) &
              trim(message)//': ', &
              trim(nf90_strerror(status))
      endif

      call abort_ice( &
           trim(message), &
           file=__FILE__, line=__LINE__)

   endif

end subroutine whacs_nc_check
#endif

!=======================================================================

end module ice_whacs_io

!=======================================================================
