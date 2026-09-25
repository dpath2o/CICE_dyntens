# Developing dynamic tensile strength on box01

Historical run records and staged validation. Original baseline run: 260924-202649.

## Status and scope

Step 0 passes the reviewed run-log and initial, first-hour and day-five spatial checks. This establishes a useful mechanics baseline; it does not yet validate dynamic tensile scaling, restart reproducibility or an analytical solution. No claim is made that all intermediate output fields have been checked.

Run timestamp is taken literally from `cice.runlog.260924-202649` (24 September 2026, 20:26:49; timezone not independently verified). Model interval: 1 January 2005 00:00 to 6 January 2005 00:00, 360-day calendar, 120 hourly timesteps.

Case: `/g/data/gv90/da1339/src/CICE_dyntens/dyntens_box01`

Run: `/g/data/gv90/da1339/cice-dirs/runs/dyntens_box01`

Source revision and executable checksum were not supplied with the output. Capture these when archiving the baseline. These notes were prepared from uploaded output, not direct access to Gadi.

## Configuration

- Rectangular 12×12 C-grid, 16 km spacing. History mask confirms 64 active ocean T cells: indices i,j=3..10 (1-based), an 8×8 ocean interior. Two land rows/columns surround it.
- Free-slip closed walls: no normal flow; tangential motion permitted. Communication boundaries labelled `open` do not remove the land mask.
- Uniform eastward atmospheric forcing; calm ocean; zero Coriolis. No external global restart.
- Initial concentration 0.9; initial grid-cell mean ice volume per area `hi=0.9 m`, hence ice-covered thickness `hi/aice=1 m`; ice initially at rest.
- Standard 2-D EVP; `avg_zeta`; `ndte=1200`; `Pstar=1e4`; `Ktens=0`; ellipse aspect ratios 2; `elasticDamp=0.09`; `deltaminEVP=2e-9`; sum capping.
- Remap transport and ridging enabled; `ktherm=-1`; FSD, lateral drag, tides and dynamic tensile scaling disabled.
- `oceanmixed_ice=.false.` for this accepted run.
- Daily and hourly history; double-precision history requested. Instantaneous stream variables have suffix `_1`.

## Setup issues resolved

1. Generated setup initially selected B-grid, parabolic concentration and disabled transport/ridging. Case namelist was adjusted to the recovered C-grid experiment.
2. Copied the working `dyntens01/env.gadi1_intel` to initialise modules in noninteractive csh and use its compiler stack.
3. Serial build failed because `ice_forcing` imports the MPI-only WHACS reader. Added a serial interface with matching arguments that aborts if WHACS is requested. MPI reader unchanged; user confirmed compilation succeeded.
4. Run `260924-200806` completed but contained SST NaNs with the mixed layer enabled. Disabling mixed-layer evolution eliminated reported NaNs in run `260924-202649`. This supports the configuration correction; the precise arithmetic origin of the earlier NaNs was not diagnosed. Snow-temperature work remains out of scope.

## Evidence reviewed

- `cice.runlog.260924-202649`
- `iceh_ic.2005-01-01-00000.nc`
- `iceh_inst.2005-01-01-03600.nc`
- `iceh_inst.2005-01-06-00000.nc`

The log reports `CICE COMPLETED SUCCESSFULLY`, final step 120 and final restart dated 2005-01-06-00000. It confirms free-slip, `Ktens=0`, `use_dyntens=F`, and mixed-layer evolution disabled. No NaN tokens were found; diagnostic SST remains −1.836°C. The BGC restart-flags warning accompanies initialisation and is not a model abort.

## Spatial results

Ranges below use active ocean T-cell indices. Velocity history is staggered; these ranges are not a complete face-by-face boundary-condition proof.

| Quantity | Initial | First hour | Day 5 |
|---|---:|---:|---:|
| Concentration | 0.9 | 0.887405–0.910943 | 0.678257–0.958043 |
| `hi`, grid-cell ice volume/area (m) | 0.9 | 0.887428–0.912513 | 0.678341–0.976533 |
| Maximum reported `uvel` (m/s) | 0 | 0.0620842 | 0.001200285 |
| Maximum absolute reported `vvel` (m/s) | 0 | 0 | 2.865e-9 |
| Strength (N/m) | 0 at initial output | 1218.02 | 10.9278–4216.86 |
| Divergence (%/day) | 0 | −33.3668 to +33.5255 | −0.117907 to +0.648155 |
| Integrated ice volume (m³) | 1.47456e10 | 1.47456e10 | 1.474559999999999e10 |
| Integrated ice area (km²) | 14745.6 | 14742.3225 | 14637.5721 |

Integrals use `sum(hi*tarea)` and `sum(aice*tarea)`, with `tarea` in m² and land excluded by the history mask/fill values. Ice volume is conserved to roundoff. Ice area decreases by approximately 108.03 km² (0.733%); with volume conserved, this is consistent with mechanical redistribution/ridging rather than ice-volume loss.

At day 5:

- Western-column mean concentration: 0.678257; eastern-column mean: 0.958043.
- Western-column mean divergence: +0.648153 %/day; eastern-column mean: −0.117907 %/day.
- Ice-covered thickness `hi/aice`: 1.000124–1.019300 m.
- Concentration and `hi` mirror differences across the north–south centreline are below 2.5e-15; divergence mirror difference is below 1.7e-14 %/day.
- Concentration, `hi`, `uvel`, `vvel`, strength, divergence and shear are finite on all 64 active ocean T-cell indices in the final snapshot.

The pattern is consistent with wind-driven eastward displacement, western opening and eastern compression. The log's declining maximum speed is consistent with developing internal resistance. This is physical consistency evidence, not proof of a converged steady solution. Initial zero strength is an initial-output value; the first-hour strength is nonzero.

## Next experiment: nonzero Ktens, disabled versus g=1

Preserve step 0 before changing the namelist or rerunning. Archive history, restarts, run log, the actual run `ice_in`, executable, case scripts, source revision and local source changes. Keep the earlier mixed-layer-on run separate.

Use the same executable for both new runs, both starting from the same internal initial state on 1 January 2005. Do not start one from the other's final restart.

| Setting | Step 0 | Step 1 control | Step 1 g=1 |
|---|---:|---:|---:|
| `Ktens` | 0 | 0.2 | 0.2 |
| `use_dyntens` | false | false | true |
| Effective tensile factor | 0 | 0.2 | 0.2 |

`Ktens=0.2` is the proposed nonzero test value, not a claim of calibration. Keep all other physical, numerical and output settings identical. FSD remains disabled because the current enabled implementation supplies fixed g=1.

Acceptance checks:

1. Both runs complete all 120 steps; active mechanical fields remain finite.
2. Logs show the intended flags, and the enabled run reports fixed g=1.
3. Executable checksums match. Input namelists differ only in `use_dyntens` (and necessary output paths if isolated directories are used).
4. All corresponding history and restart numerical fields match exactly, including IC and hourly history; compare decoded values and masks, not whole-file checksums containing metadata.
5. Preserve this pair before adding prescribed g below 1. Confirm the comparison utility supports this FSD-disabled case before using it; the existing global FSD-normalisation requirement is not applicable here.

A successful identity pair validates the enabled pathway, not sensitivity to tensile strength. Follow it with constant g<1 versus an equivalent reduced scalar Ktens, then spatial g under deliberate tensile loading. Uniform eastward wind mainly tests compression/opening and boundaries; opposing outward winds are a proposed later tensile-loading experiment and are not implemented by these notes.

Restart reproducibility (continuous versus split integration) remains a separate pending check. Global FSD drift investigations remain paused.

## Follow-on analysis — Ktens=0.2 disabled control

Added after reviewing the three follow-on snapshots supplied by the user. The document filename continues to identify the original step-0 run; this section records the subsequent control separately.

### Provenance and verification limits

The user reported changing `Ktens` to 0.2 and was instructed to retain `use_dyntens=.false.` and `oceanmixed_ice=.false.`. The following results are therefore labelled **reported Ktens=0.2 disabled control**. The actual run namelist, log, executable checksum and source revision have not been supplied for this run, so its flags and executable identity are not independently confirmed by these history files.

Uploaded filenames (the `(1)` suffix distinguishes uploads, not model experiment names):

- `iceh_ic.2005-01-01-00000(1).nc`
- `iceh_inst.2005-01-01-03600(1).nc`
- `iceh_inst.2005-01-06-00000(1).nc`

The IC file records creation at `2026-09-24 21:07:55.0`; the final snapshot records `2026-09-24 21:08:00.2`. These are file-creation metadata, not a verified run-log timestamp. Model times confirm the original initial time, first hour and day-five endpoint.

### Results relative to step 0

All common numeric IC data variables compare exactly after decoding, including matching NaN/fill locations. This supports identical initial conditions; metadata such as file-creation time differ.

| Diagnostic | Ktens=0, hour 1 | Reported Ktens=0.2, hour 1 | Ktens=0, day 5 | Reported Ktens=0.2, day 5 |
|---|---:|---:|---:|---:|
| Minimum concentration | 0.887405 | 0.888168 | 0.678257 | 0.681523 |
| Maximum concentration | 0.910943 | 0.910291 | 0.958043 | 0.957503 |
| Maximum reported uvel (m/s) | 0.0620842 | 0.0583330 | 0.001200285 | 0.001191054 |
| Maximum absolute reported vvel (m/s) | 0 | 0 | 2.865e-9 | 2.285e-9 |
| Minimum divergence (%/day) | −33.3668 | −31.3803 | −0.117907 | −0.117926 |
| Maximum divergence (%/day) | 33.5255 | 31.4943 | 0.648155 | 0.643170 |
| Maximum strength (N/m) | 1218.018 | 1218.018 | 4216.858 | 4167.608 |
| Ice area (km²) | 14742.3225 | 14742.5205 | 14637.5721 | 14640.1727 |

For the follow-on control:

- Ice volume is 1.47456e10 m³ initially and conserved to roundoff at both inspected output times; final value is 1.474559999999999e10 m³.
- The seven inspected mechanical fields (`aice`, `hi`, `uvel`, `vvel`, `strength`, `divu`, `shear`) are finite at all active ocean T-cell indices at both times.
- Day-five concentration retains north–south symmetry, with maximum reflected difference 2.22e-16.
- Day-five western/eastern mean concentrations are 0.6815233 and 0.9575027. Western opening and eastern compression persist.
- Maximum reported eastward velocity is approximately 6.04% lower at hour 1 and 0.77% lower at day 5 than the zero-Ktens baseline.
- Final ice area is 2.6006 km² greater than step 0, consistent with slightly less area reduction under the reported parameter change.

### Interpretation

The response is a modest, resolved change from the zero-tensile-factor experiment: reduced early motion and western opening, with slightly less concentration increase at the eastern wall. This is consistent with the reported nonzero tensile coefficient affecting the constitutive response. It is not yet an isolated test of tensile failure: changing Ktens also changes the EVP constitutive expressions, and this forcing produces both opening and compression.

The identical first-hour `strength` field does not imply that Ktens has no effect. This diagnostic is the base compressive strength; it is not the effective tensile coefficient. Later strength differences can arise from the evolving concentration and thickness.

No enabled g=1 output has been supplied in this follow-on set. These differences are **Ktens=0 versus reported Ktens=0.2**, not a failure of the required disabled-versus-g=1 identity test.

### Immediate next action

1. Archive this completed nonzero-Ktens disabled control, including its actual run-directory `ice_in`, history, restarts, run log and executable; record its SHA-256 checksum.
2. Keep `Ktens=0.2`, `oceanmixed_ice=.false.`, all other settings and the executable unchanged. Change only `use_dyntens` to `.true.` for the enabled experiment.
3. Start again from internal initial conditions on 1 January 2005, not from this control's final restart. No rebuild is needed for this namelist switch.
4. Verify the enabled log's fixed-g=1 message and compare the complete corresponding history/restart sets against the archived nonzero-Ktens control. The expected result is exact numerical equality with matching masks.

Current status: step-0 checks passed; follow-on nonzero-Ktens snapshots are finite and physically consistent; run provenance confirmation, full off/g=1 comparison and split-run restart reproducibility remain pending.

## Enabled g=1 identity check — run 260925-065019

### New evidence

Reviewed `cice.runlog.260925-065019`, the supplied `ice_in`, and the initial, first-hour and day-five history files uploaded with `(2)` suffixes. The suffix denotes the upload copy, not a model configuration.

The run log confirms `Ktens=0.20`, `use_dyntens=T`, and explicitly reports:

> Dynamic tensile stage 1: g=1; Ktens_eff=Ktens at all T points

It also confirms `oceanmixed_ice=F` and successful completion. No NaN or abort matches were found in the log. The supplied namelist confirms `runtype='initial'`, `ice_ic='internal'`, `Ktens=0.2`, `use_dyntens=.true.` and mixed-layer evolution disabled.

### Exact comparison with the reported disabled control

Compared the `(2)` files against the corresponding `(1)` control uploads using NetCDF decoded arrays. Compared variable inventories, dimension names, masks and all unmasked values, including coordinate/time variables. Equality was exact, with no numerical tolerance. File-creation metadata was excluded from numerical equality; file-byte identity was not tested.

| Model snapshot | Variables compared | Numerical differences | Mask differences | Result |
|---|---:|---:|---:|---|
| 2005-01-01 00:00, initial | 137 | 0 | 0 | PASS |
| 2005-01-01 01:00 | 72 | 0 | 0 | PASS |
| 2005-01-06 00:00 | 72 | 0 | 0 | PASS |

No extra variables were present in the enabled files. These matching outputs inherit the previously measured control results: conserved ice volume at the inspected times, finite inspected mechanical fields, western opening, eastern compression and scalar north–south symmetry.

### Conclusion and limits

**The supplied snapshots pass the g=1 identity check.** The enabled log confirms that the new pathway executed, and its output matches the reported disabled nonzero-Ktens control exactly at the initial time, first hour and five-day endpoint. This is stronger evidence than visual similarity.

This is still a three-snapshot comparison, not a claim that the full run is bit-for-bit validated. Outstanding evidence is the disabled control's actual namelist/log, matching executable checksums, comparison of every intervening history file and all restart fields, and continuous-versus-split restart reproducibility. Matching initial history supports identical initial state but does not establish executable identity.

### Next gate and development step

Preserve the enabled run separately from the disabled control and retain their executables, namelists, logs and source provenance. Complete the full history/restart comparison on Gadi before marking the entire identity gate passed. No additional physics changes or repeated baseline runs are indicated by these results.

Once that gate passes, implement a prescribed constant-g test. For example, enabled `Ktens=0.2, g=0.5` should match disabled `Ktens=0.1` under the same executable and initial conditions. The present stage-1 implementation fixes g=1; changing g to 0.5 requires a deliberate code/configuration extension, not an existing namelist option assumed by these notes. Follow scalar equivalence with controlled tensile loading and spatial g, then a known fixed FSD. Full evolving FSD remains a later stage.

Latest status: step-0 reviewed checks passed; reported nonzero-Ktens control is physically consistent; enabled g=1 is confirmed and all three supplied snapshot pairs match exactly. Full-output identity, executable provenance and restart reproducibility remain pending.


## Development update — prescribed constant g (25 September 2026)

### Archive provenance supplied by the user

Archive root: `~/AFIM_archive/LFI-waves-dyntens/`.

| Archive directory | Experiment |
|---|---|
| `dyntens-box01.mixedlayer-on.20260924-202016/` | Earlier mixed-layer-on run containing SST NaNs |
| `dyntens-box01.step1.20260924-213915/` | Reported Ktens=0.2 disabled control |
| `dyntens-box01.step2.20260925-110235/` | Enabled g=1 run, log 260925-065019 |

The user confirms that the accepted Ktens=0 step-0 run was not archived. Its uploaded snapshots, run log and measurements above are the available evidence; a complete archived run must not be implied. Archive names `step1` and `step2` identify runs, while both are parts of the conceptual g=1 identity test. The archive paths have not been accessed directly here.

### What changed in the Fortran

- `ice_init.F90`: the original stage-1 edit imports, reads, defaults, broadcasts and logs `use_dyntens`. It rejects enabled combinations outside C-grid, standard 2-D EVP, avg_zeta, ellipse, revised EVP off, and Ktens in [0,1]. The new extension similarly handles `dyntens_g_const` (default 1), validates it in [0,1] when enabled, and logs g and Ktens_eff.
- `ice_dyn_shared.F90`: owns the public switch and now the prescribed scalar. The earlier optional `ktens_local` argument in `visc_replpress` substitutes the local coefficient in both `(1+Ktens)` viscosity and `(1-Ktens)` replacement-pressure expressions. Calls without that argument retain the original scalar expressions.
- `ice_dyn_evp.F90`: allocates private T-cell `ktens_effT` only when enabled, fills the full array including halo/land cells on initialisation and each EVP step, passes the block index to the C-grid stress routine, and supplies the local optional argument. The two former `Ktens*c1` assignments now use `Ktens*dyntens_g_const`. Existing avg_zeta interpolation propagates the resulting viscosity to U points. No FSD feedback or new prognostic/restart field is added.

### Next run pair: prescribed g=0.5

This source update needs one clean rebuild. Then use that same executable for both runs, with identical internal initial conditions, forcing and numerics.

```fortran
! In dynamics_nml: scaled run
Ktens = 0.2
use_dyntens = .true.
dyntens_g_const = 0.5
```

```fortran
! In dynamics_nml: equivalent scalar control
Ktens = 0.1
use_dyntens = .false.
dyntens_g_const = 1.0
```

Both represent Ktens_eff=0.1 and should match numerically. Do not compare g=0.5 against the old Ktens=0.2 control expecting equality. Keep mixed-layer evolution, waves, FSD and lateral drag disabled. Preserve each run before reusing the run directory.

The new scalar is ignored when use_dyntens is false. g=1 remains the default; g=0 is also allowed. This is a prescribed-coefficient test only. Validate full history/restart identity and executable provenance for the existing pair; repeat g=1 after rebuilding to check this extension retains that property. The new Fortran has not yet been compiled on Gadi.
