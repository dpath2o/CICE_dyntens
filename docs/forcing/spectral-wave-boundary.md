# Spectral wave forcing at the sea-ice boundary

## Status

This document describes the implemented CAWCR/WHACS spectral-wave forcing pathway in `CICE_free-slip-forcing-sensitivity`; it supersedes the earlier conceptual markdown doc.

The implementation now:

- reads hourly non-directional CAWCR/WHACS wave spectra on the native 25-frequency Icepack grid;
- linearly interpolates adjacent hourly spectra to the CICE model time;
- retains only two forcing records per MPI task in a rolling `float32` cache;
- propagates open-water spectral energy into the modeled ice cover using the existing Noah Day / Meylan et al. attenuation approach;
- passes propagated local spectra to Icepack's floe-size-distribution (FSD) wave-fracture machinery;
- pre-screens cells before the expensive Icepack fracture calculation; and
- uses a wave-specific conservative adaptive subcycling scheme that is robust for long standalone integrations.

The final numerical fix is deliberately local to wave fracture. `icepack_fsd.F90` was edited for testing but has now been returned to its original process-agnostic (i.e. coupled or standalone) behaviour.

## Scientific purpose

The wave experiment tests whether remotely generated swell and wave-induced floe breakup influence Antarctic fast-ice persistence, retreat timing, and seasonal maximum fast-ice area (FIA).

This pathway is distinct from tides:

- **tides** provide a sub-daily current/stress perturbation;
- **waves** provide spectral energy that enters from open water, attenuates into the ice cover, and can fracture the FSD.

The implementation does not directly delete fast ice or alter an online fast-ice mask. Wave effects enter through the modeled FSD and subsequent CICE/Icepack physics; fast-ice classification remains diagnostic/offline.

## Implemented forcing contract

The current WHACS preprocessing supplies monthly files of the form

```text
CAWCR_efreq_for_CICE6_YYYYMM.nc
```

containing hourly non-directional spectral energy density `efreq` on the CICE T grid and the exact 25-frequency discretisation used by Icepack.

The CICE-facing spectral quantity is

```text
E(f)  [m2 s]
```

with significant wave height diagnosed as

$$
H_s = 4\sqrt{\sum_f E(f)\,\Delta f}.
$$

The wave-fracture pre-screen currently requires

```text
aice > 0.01
Hs   > 0.1 m
```

before entering the expensive Icepack fracture calculation.

## Runtime pathway

The active pathway is:

```text
CAWCR/WHACS monthly NetCDF
        |
        v
ice_forcing.F90
  wave_spec_data_hourly
        |
        |-- rolling two-record cache
        |-- hourly interpolation
        v
  propagate_waves
        |
        |-- open-water source cells: aice < 0.15
        |-- Meylan et al. attenuation
        |-- up to 10 propagation passes
        v
wave_spectrum(i,j,f)
        |
        v
ice_step_mod.F90
  step_dyn_wave
        |
        |-- cheap aice/Hs pre-screen
        v
icepack_wavefracspec.F90
  icepack_step_wavefracture
        |
        v
FSD redistribution / fracture
```

### Fracture cadence

For the present standalone configuration the base CICE timestep is 1800 s. Wave fracture is called every second model step:

```fortran
if (tr_fsd .and. wave_spec) then
   if (mod(istep,2_int_kind) == 0_int_kind) then
      call step_dyn_wave(2.0_dbl_kind*dt)
   endif
endif
```

Thus each Icepack fracture call integrates over a 3600 s wave-fracture interval, while the spectral forcing itself continues to be updated/interpolated on the model timestep.

## Original failure: memory and I/O scaling

The first major failure appeared to be a memory problem in the WHACS reader.

The initial implementation cached a complete month of hourly spectral forcing. At 25 frequencies on the 1440 x 1080 CICE grid, that design was unnecessarily expensive in both memory and I/O. At a month transition it also implied a burst of roughly 672--744 global spectral-record reads.

### Fix: rolling two-record cache

`wave_spec_data_hourly` was rewritten to retain only the two records needed for temporal interpolation:

```text
slot 1 : current forcing hour
slot 2 : following forcing hour
```

At an hourly rollover, slot 2 becomes slot 1 and one new record is read. The resident cache is stored as `real_kind` (`float32`) and converted to `dbl_kind` only when forming the active interpolated spectrum.

This removed the complete-month cache and stabilized memory at approximately 0.5 GB per MPI rank in the tested 1232-rank configuration.

Importantly, once the memory problem was removed, subsequent failures showed that the reader was no longer the limiting issue: the model consistently reached Icepack wave fracture and failed inside FSD adaptive integration.

## Numerical failure in Icepack wave fracture

### Why the problem appeared

Icepack wave fracture computes a conservative redistribution of FSD area between floe-size bins. In simplified form,

```fortran
omega(k) = afsd(k) * sum(fracture_hist(1:k-1))
loss     = omega
gain(k)  = sum(omega * frac(:,k))
d_afsd   = gain - loss
```

so the intended operator satisfies

$$
\sum_k \frac{dF_k}{dt} = 0.
$$

Two numerical assumptions in the stock path became problematic under the externally forced spectra and long 3600 s fracture interval.

### 1. Component-wise tendency truncation

The original wave routine zeroed individual tendency components smaller than `puny`:

```fortran
WHERE (ABS(d_afsd).lt.puny) d_afsd = c0
```

Although each component was small, the positive and negative components were paired through the conservative gain/loss calculation. Truncating them independently could therefore destroy exact cancellation and make the returned tendency inconsistent with the FSD state.

The final implementation retains the raw conservative quantity:

```fortran
d_afsd(:) = gain(:) - loss(:)
```

and checks only the total conservation residual.

### 2. Generic FSD timestep limiter

The process-agnostic Icepack limiter constrains both negative and positive FSD tendencies. For wave fracture, this produced two related zero-timestep pathologies during debugging:

- a tiny donor bin with a negative tendency could be ignored by a tendency tolerance and subsequently cross below zero; and
- after floating-point round-off, a bin could be exactly `F=1` while another bin retained a positive numerical crumb. A tiny positive gain into the full bin then gave

```text
(1 - F) / dFdt = 0 / positive = 0
```

and the adaptive integration aborted with `subdt=0`.

These were numerical boundary-state problems, not evidence of invalid WHACS spectra.

## Final wave-fracture integration fix

The robust solution exploits the structure of the wave-fracture operator rather than altering the generic Icepack FSD timestep routine.

### Conservative donor-limited timestep

Because wave fracture is a conservative redistribution and the normalized FSD lies on

$$
F_k \ge 0, \qquad \sum_k F_k = 1,
$$

it is sufficient to prevent donor bins from becoming negative. If every component remains non-negative and the total remains one, no component can exceed one.

The wave routine therefore begins each subcycle with the remaining integration interval and limits only on negative tendencies:

```fortran
subdt = dt - elapsed_t

do k = 1, nfsd
   if (d_afsd_tmp(k) < c0) then
      if (afsd_tmp(k) <= c0) then
         subdt = c0
         exit
      endif

      subdt = min( &
           subdt, &
           afsd_tmp(k) / abs(d_afsd_tmp(k)))
   endif
enddo
```

Every negative donor tendency participates, irrespective of its absolute magnitude.

A zero or negative timestep from this scheme is treated as a genuine inconsistency and retains detailed failure diagnostics.

### Per-subcycle FSD canonicalisation

After every Euler update, the wave routine first checks that any bound/conservation error is smaller than `puny`. It then removes sub-`puny` numerical crumbs and renormalises:

```fortran
where (afsd_tmp < puny)
   afsd_tmp = c0
end where

afsd_tmp = afsd_tmp / sum(afsd_tmp)
```

This mirrors the semantics of `icepack_cleanup_fsdn`, but is applied *inside* the adaptive fracture loop so the next tendency is always formed from a canonical, non-negative, unit-sum FSD.

This combination addresses both previously observed zero-substep mechanisms without changing the underlying wave-fracture physics.

## Scope of source-code changes

### `ice_forcing.F90`

Implemented:

- monthly `YYYYMM` WHACS file resolution;
- rolling two-record hourly cache;
- temporal interpolation to CICE model time;
- non-negative spectrum protection;
- wave propagation into current modeled ice cover;
- sparse reader and performance diagnostics.

The high-frequency `WAVEPERF GET` message is now restricted to startup and daily checkpoints for production integrations.

### `ice_step_mod.F90`

`step_dyn_wave` now pre-screens cells using the same basic thresholds needed by Icepack:

```text
aice > 0.01
Hs   > 0.1 m
```

This avoids invoking the expensive fracture calculation over the large majority of grid cells that cannot fracture. Cells skipped by the pre-screen still receive the standard Icepack FSD cleanup so the optimisation does not bypass tracer housekeeping.

Failure diagnostics retain the MPI task, global grid indices, `aice`, `vice`, and local `Hs`.

### `icepack_wavefracspec.F90`

Implemented:

- direct externally supplied spectral forcing;
- raw conservative `gain - loss` FSD tendency;
- donor-limited adaptive timestep for wave fracture;
- finite/non-advancing timestep guard;
- hard maximum wave-subcycle guard;
- per-subcycle FSD bound and conservation checks;
- per-subcycle sub-`puny` cleanup and renormalisation;
- detailed diagnostics only on numerical failure.

The temporary per-cell

```text
WAVEFRAC ENTER
WAVEFRAC RETURN
```

messages used during debugging have been removed because they generated untenable production log volumes.

### `icepack_fsd.F90`

No final wave-specific changes are required. The generic `get_subdt_fsd` implementation has been restored to its original form.

This is intentional: the donor-limited timestep is valid because of the conservative structure of the **wave-fracture** operator and should not silently change timestep behaviour for thermodynamic growth, welding, or other FSD processes.

## Diagnostics retained for production runs

The production logging policy is deliberately sparse:

- `WAVEIO ROLLING`: first few record reads and approximately daily thereafter;
- `WAVEPERF GET`: startup and daily timing checkpoints;
- `WAVEPERF GLOBAL`: startup/daily propagation timing, including pass information;
- `WAVEFSD PERF`: startup/daily global fracture cost and eligible-cell counts;
- full FSD state diagnostics: **failure only**.

This keeps enough information to identify I/O, propagation, or fracture-performance regressions without producing multi-gigabyte logs over multi-year experiments.

## Validation

The final configuration passed the failure point that had repeatedly terminated earlier experiments at the first wave-fracture call (`istep=2`) and subsequently completed at least three model days successfully with the same forcing/cadence.

During that successful run:

- hourly WHACS interpolation continued normally;
- the rolling two-record cache remained stable;
- wave propagation completed through the configured pass depth;
- approximately O(10^4) cells per fracture call passed the `aice`/`Hs` pre-screen in the initial test period; and
- the donor-limited FSD integration did not reproduce the previous `subdt=0` failures.

Longer integrations remain the appropriate validation for scientific stability, but the observed failure mechanism is now removed rather than masked by a larger numerical tolerance.

## Interpretation for publication

The wave-fracture modifications should be described as a **numerical integration robustness change**, not a new fracture parameterisation.

The physical fracture tendency remains the Icepack gain/loss redistribution generated from the local wave spectrum and fracture histogram. The changes ensure that:

1. conservative gain/loss cancellation is preserved;
2. adaptive substeps respect donor positivity;
3. round-off does not create artificial FSD donor categories; and
4. the changes remain confined to the wave-fracture pathway.

This distinction is important when comparing the wave experiment with the no-wave control: the scientific perturbation is the propagated CAWCR/WHACS wave spectrum, while the integration changes allow that existing Icepack fracture physics to be applied robustly at the standalone CICE timestep/cadence used here.

## Remaining scientific choices

The following should remain explicit experiment/configuration choices rather than being conflated with the numerical fixes above:

- open-water source threshold (`aice < 0.15`) used for propagation;
- fracture pre-screen (`aice > 0.01`, `Hs > 0.1 m`);
- Meylan et al. attenuation formulation;
- maximum propagation depth (`max_passes = 10`);
- hourly fracture cadence (3600 s in the present configuration); and
- use of non-directional rather than directional spectra.

These should be evaluated scientifically against sensitivity experiments and observational evidence; they are not required to resolve the memory or adaptive-FSD failures documented here.

## Key references

- Horvat, C., & Tziperman, E. (2015). A prognostic model of the sea-ice floe size and thickness distribution. *The Cryosphere*, 9, 2119–2134. https://doi.org/10.5194/tc-9-2119-2015
- Roach, L. A., Horvat, C., Dean, S. M., & Bitz, C. M. (2018). An emergent sea ice floe size distribution in a global coupled ocean-sea ice model. *Journal of Geophysical Research: Oceans*, 123, 4322–4337. https://doi.org/10.1029/2017JC013692
- Meylan et al. (2014), attenuation formulation used by the existing wave-propagation pathway.
