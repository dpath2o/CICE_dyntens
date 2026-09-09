 !=======================================================================
 subroutine wave_spec_data_hourly
   !
   ! Rolling two-record WHACS forcing cache.
   !
   ! Only the two hourly spectra required for temporal interpolation are
   ! retained:
   !
   !     slot 1 : current forcing hour
   !     slot 2 : following forcing hour
   !
   ! At an hourly rollover, slot 2 becomes slot 1 and exactly one new
   ! WHACS record is read.
   !
   ! This removes the previous complete-month cache and the burst of
   ! 672--744 global spectral reads at each month transition.
   !

   use ice_whacs_io, only: &
        ice_read_nc_xyf_whacs

   use ice_arrays_column, only: &
        wave_spectrum

   use ice_domain, only: &
        nblocks

   integer (kind=int_kind) :: &
        curr_year, &
        curr_month, &
        curr_rec, &
        next_year, &
        next_month, &
        next_rec, &
        nhours, &
        hour_index, &
        modadj, &
        iblk

   real (kind=dbl_kind) :: &
        secday, &
        sec1hr, &
        frac

   character(char_len_long) :: &
        curr_file, &
        next_file

   logical (kind=log_kind) :: &
        current_cached, &
        current_in_slot2, &
        next_cached, &
        did_read

   !--------------------------------------------------------------------
   ! Two local float32 forcing records.
   !
   ! Dimensions:
   !
   !   i,j,frequency,time_slot,block
   !--------------------------------------------------------------------
   real (kind=real_kind), dimension(:,:,:,:,:), &
        allocatable, save :: &
        wave_pair_cache

   integer (kind=int_kind), save :: &
        cache_year_1  = -9999, &
        cache_month_1 = -9999, &
        cache_rec_1   = -9999, &
        cache_year_2  = -9999, &
        cache_month_2 = -9999, &
        cache_rec_2   = -9999

   integer (kind=int_kind), save :: &
        wave_records_read = 0_int_kind

   logical (kind=log_kind), parameter :: &
        wave_io_debug = .true.

   character(len=*), parameter :: &
        subname = '(wave_spec_data_hourly)'

   !--------------------------------------------------------------------
   ! Allocate exactly two local forcing records.
   !--------------------------------------------------------------------
   if (.not. allocated(wave_pair_cache)) then

      allocate( &
           wave_pair_cache( &
                nx_block, &
                ny_block, &
                nfreq, &
                2, &
                max_blocks))

      wave_pair_cache = real(c0,kind=real_kind)

   endif

   !--------------------------------------------------------------------
   ! Obtain CICE day length.
   !--------------------------------------------------------------------
   call icepack_query_parameters(secday_out=secday)

   call icepack_warnings_flush(nu_diag)

   if (icepack_warnings_aborted()) then
      call abort_ice( &
           error_message=subname, &
           file=__FILE__, line=__LINE__)
   endif

   sec1hr = secday / 24.0_dbl_kind

   !--------------------------------------------------------------------
   ! Resolve model year onto configured forcing cycle.
   !--------------------------------------------------------------------
   if (ycycle == 0) then

      curr_year = myear

   else

      modadj = abs( &
           (min(0,myear-fyear_init)/ycycle+1)*ycycle)

      curr_year = fyear_init + &
           mod(myear-fyear_init+modadj,ycycle)

   endif

   curr_month = mmonth

   !--------------------------------------------------------------------
   ! Current forcing-hour record.
   !--------------------------------------------------------------------
   nhours = 24 * daymo(curr_month)

   hour_index = int( &
        real(msec,kind=dbl_kind) / sec1hr)

   hour_index = &
        max(0_int_kind, &
        min(23_int_kind,hour_index))

   curr_rec = &
        24 * (mday - 1) + &
        hour_index + 1

   curr_rec = &
        max(1_int_kind, &
        min(nhours,curr_rec))

   !--------------------------------------------------------------------
   ! Following forcing-hour record.
   !--------------------------------------------------------------------
   if (curr_rec < nhours) then

      next_year  = curr_year
      next_month = curr_month
      next_rec   = curr_rec + 1

   else

      next_year  = curr_year
      next_month = curr_month + 1
      next_rec   = 1

      if (next_month > 12) then

         next_month = 1
         next_year  = curr_year + 1

         if (ycycle > 0 .and. &
             next_year > fyear_final) then

            next_year = fyear_init

         endif

      endif

   endif

   call whacs_monthly_wave_file( &
        curr_year, &
        curr_month, &
        curr_file)

   call whacs_monthly_wave_file( &
        next_year, &
        next_month, &
        next_file)

   !--------------------------------------------------------------------
   ! Is the desired current record already in slot 1?
   !--------------------------------------------------------------------
   current_cached = &
        cache_year_1  == curr_year  .and. &
        cache_month_1 == curr_month .and. &
        cache_rec_1   == curr_rec

   !--------------------------------------------------------------------
   ! Normal hourly rollover:
   !
   ! previous slot 2 becomes the desired slot 1.
   !--------------------------------------------------------------------
   current_in_slot2 = &
        cache_year_2  == curr_year  .and. &
        cache_month_2 == curr_month .and. &
        cache_rec_2   == curr_rec

   did_read = .false.

   if (.not. current_cached) then

      if (current_in_slot2) then

         wave_pair_cache(:,:,:,1,:) = &
              wave_pair_cache(:,:,:,2,:)

         cache_year_1  = cache_year_2
         cache_month_1 = cache_month_2
         cache_rec_1   = cache_rec_2

      else

         call ice_read_nc_xyf_whacs( &
              trim(curr_file), &
              curr_rec, &
              wave_pair_cache(:,:,:,1,:))

         cache_year_1  = curr_year
         cache_month_1 = curr_month
         cache_rec_1   = curr_rec

         wave_records_read = &
              wave_records_read + 1_int_kind

         did_read = .true.

      endif

   endif

   !--------------------------------------------------------------------
   ! Ensure slot 2 is the following hourly record.
   !--------------------------------------------------------------------
   next_cached = &
        cache_year_2  == next_year  .and. &
        cache_month_2 == next_month .and. &
        cache_rec_2   == next_rec

   if (.not. next_cached) then

      call ice_read_nc_xyf_whacs( &
           trim(next_file), &
           next_rec, &
           wave_pair_cache(:,:,:,2,:))

      cache_year_2  = next_year
      cache_month_2 = next_month
      cache_rec_2   = next_rec

      wave_records_read = &
           wave_records_read + 1_int_kind

      did_read = .true.

   endif

   !--------------------------------------------------------------------
   ! Fraction through current forcing hour.
   !--------------------------------------------------------------------
   frac = ( &
        real(msec,kind=dbl_kind) - &
        real(hour_index,kind=dbl_kind)*sec1hr) / &
        sec1hr

   frac = max(c0,min(c1,frac))

   !--------------------------------------------------------------------
   ! Interpolate the two resident hourly spectra.
   !--------------------------------------------------------------------
   wave_spectrum = c0

   if (nblocks > 0) then

      do iblk = 1, nblocks

         wave_spectrum(:,:,:,iblk) = &
              (c1-frac) * &
              real( &
                   wave_pair_cache(:,:,:,1,iblk), &
                   kind=dbl_kind) + &
              frac * &
              real( &
                   wave_pair_cache(:,:,:,2,iblk), &
                   kind=dbl_kind)

      enddo

   endif

   where (wave_spectrum < c0)
      wave_spectrum = c0
   end where

   !--------------------------------------------------------------------
   ! Sparse rolling-cache diagnostics.
   !--------------------------------------------------------------------
   if (wave_io_debug .and. &
       my_task == master_task .and. &
       did_read) then

      if (wave_records_read <= 6_int_kind .or. &
          mod(wave_records_read,24_int_kind) == 0_int_kind) then

         write(nu_diag,*) &
              'WAVEIO ROLLING date=', &
              myear,mmonth,mday, &
              ' sec=',msec, &
              ' curr=', &
              cache_year_1,cache_month_1,cache_rec_1, &
              ' next=', &
              cache_year_2,cache_month_2,cache_rec_2, &
              ' frac=',frac, &
              ' records_read=',wave_records_read

         call flush(nu_diag)

      endif

   endif

 end subroutine wave_spec_data_hourly
