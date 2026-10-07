# Analysis notes — dyntens_box01 — 260924-202649

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
