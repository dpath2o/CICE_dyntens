# Global development of dynamic tensile strength

The [box01 tests](box01_dev_dynamic_tensile_strength.md) checked that the coefficient calculation and its effect on momentum were implemented as intended. We now return to the global grid, with the usual atmosphere, ocean and thermodynamics, to ask whether the model still works and whether the new tensile strength produces a sensible sea-ice response.

## Test questions

| Task | Question | Work to answer it | Status | README link |
|---|---|---|---|---|
| [G0](G0.md) | After the box01 code changes, can the global model still run, and does $g=1$ give the same results as switching the new option off? | Run two days from the same restart using the same executable; compare all history and restart output. | Complete for this two-day comparison | [R0–R1](../../README.md#development-stages) |
| [G1](G1.md) | Can we calculate $g$ from the evolving global FSD without changing the physical results, and are the FSD checks suitable for these model values? | Inspect the FSD, decide how its numerical departures should be handled, then compare diagnostic-only output with the control. | Incomplete | [R3](../../README.md#development-stages) |
| [G2](G2.md) | When tensile strength depends on floe size, does the ice respond mechanically as expected, and do changes in growth, melt and ocean heat exchange make physical sense? | Add supported global feedback, compare matched runs, and assess the mechanical response and mass/energy budgets before longer experiments. | Incomplete | [R4–R5](../../README.md#development-stages) |

Last update to this document: 8 October 2026. G0's exact comparison passed. That is a short-run result, not evidence of seasonal performance or a complete heat-budget assessment.

## Reference configuration

Use [ice_in.off](../../global_tests/G0/reference/off/ice_in) as the reference for this first global comparison. [ice_in.unity](../../global_tests/G0/reference/unity/ice_in) enables the constant unity coefficient. The off copy matches the namelist hash supplied with the completed run. The [original global template](../../global_tests/G0/dyntens01/ice_in) remains available, but may be edited during later development; the reference copies identify what G0 used.

The prepared run folders contain their own `ice_in` and `g0-input.json`. Keep those records with the executable, input restart and completed outputs. The [G0 results](G0.md#results--8-october-2026) record the hashes and job numbers.

| Part of the model | G0 setting or input | What this means |
|---|---|---|
| Grid | `/g/data/gv90/da1339/grids/ACCESS-OM3-025_Cgrid.nc`; 1440×1080, C-grid, tripole | The normal global grid, not the 12×12 box. |
| Ocean mask | `/g/data/gv90/da1339/grids/ACCESS-OM3-025_kmt.nc` | Identifies the ocean cells used by the model. |
| Start | `/g/data/gv90/da1339/cice-dirs/runs/dyntens01/restart/iced.2000-09-01-00000.nc` | Both runs start from exactly the same ice state, including FSD and thermal tracers. |
| Dates | 1–3 September 2000; `dt=1800`, `npt=2`, `npt_unit='d'` | Two days, 96 half-hour timesteps. The restart supplies the model clock. |
| Atmosphere | `atm_data_type='ERA5'`; `/g/data/gv90/da1339/afim_input/ERA5/0p25/bilinear/monthly_cice6_fast` | Use the existing ERA5 files and reader. Keep `era5_mod_var='none'`, `era5_mod_fac=1` and `precip_units='mks'`. |
| Ocean | `ocn_data_type='AFIM'`; `/g/data/gv90/da1339/afim_input/ORAS/daily/sfc/fin/`; `oceanmixed_file='ORAS_.nc'` | Use the existing ORAS inputs through the AFIM reader. |
| Ocean/ice heat exchange | `oceanmixed_ice=.true.`, `restore_ocn=.true.`, `trestore=14`, `hmix_0=60` | Retain the original mixed-layer/restore settings; do not substitute the calm-ocean box setup. |
| Thermodynamics | `ktherm=2`, `kitd=1`, `calc_Tsfc=.true.` | Ice thermodynamics and surface-temperature calculation remain active. |
| Rheology | `Ktens=0.2`, `e_yieldcurve=1.5`, `e_plasticpot=1.5`, `Pstar=2.75e4`, `Cstar=20` | Keep the same EVP/strength settings in both runs. |
| Coast and lateral drag | `boundary_condition='free_slip'`, `lateral_drag=.true.`, `form_func='static'`, `Cs=1e-3`, `Cq=0`, `C_L=0` | Retain the original free-slip boundary and quadratic lateral drag. |
| Coast/grounded-iceberg form factors | `/g/data/gv90/da1339/form_factors/FF_combined_meth-max_cst-v7p9-Liu_GIB-v1p2-perimeter_Liu_CICE.nc`; `FFx`, `FFy`; mapping `max` | Grounded-iceberg and coastal obstacles enter through these form factors. |
| Seabed stress | `seabed_stress=.false.`, `use_bathymetry=.false.` | Seabed-stress parameterisation is off here; do not describe it as active grounding physics. |
| Waves and FSD | `wave_spec_type='constant'`, `tr_fsd=.true.`, `restart_fsd=.true.`, `nfreq=25` | The FSD evolves, but the wave spectrum is constant. This run does not read WHACS merely because a wave-file path is present. |
| Tides | `tide_data_type='none'`, current/SSH switches false | Tides remain off in this reference. |
| Forcing calendar | `fyear_init=1995`, `ycycle=11`; 365-day years with leap years enabled | Retain the original forcing-cycle settings. Check the model's reported forcing year and input coverage for each new period. |
| Output | Daily means and daily restarts; `history_precision=8`; initial history written | G0 compares three histories and two restarts. `hs` and `Tsfc` history output are off, although thermal tracers are retained in restart files. |

The paths and switches come from the reference namelist. They do not independently verify every forcing-file unit or date. For a changed period or dataset, inspect the actual NetCDF units/time coordinates and the reader's expectations before starting; confirm that the run loaded the intended files. Do not infer a data pathway from a directory name or an unused filename.

### Where to check these settings in the code

- [ice_forcing.F90](../../cicecore/cicedyn/general/ice_forcing.F90) contains the atmosphere/ocean and wave-forcing setup. Use it with the namelist when checking filenames, dates and conversions.
- [MPI WHACS reader](../../cicecore/cicedyn/infrastructure/comm/mpi/ice_whacs_io.F90) is relevant when we explicitly select WHACS in a later comparison. Keep that forcing change separate from enabling tensile feedback.
- [Icepack FSD calculations](../../icepack/columnphysics/icepack_fsd.F90) and [wave fracture](../../icepack/columnphysics/icepack_wavefracspec.F90) describe the floe-size state and its wave response.
- [EVP implementation](../../cicecore/cicedyn/dynamics/ice_dyn_evp.F90) applies the effective tensile coefficient; [G0](G0.md#code-changed-during-box01-development) lists the box-development source edits.

## What remains to be tested

For G1, retain the G0 physical settings and keep the coefficient used by momentum at its control value. First inspect the existing/control FSD without relying on the strict live mapping to stay running. Then establish the diagnostic policy and verify that adding diagnostics leaves the physical results unchanged.

For G2, the global FSD feedback path still needs a supported implementation. The current `box_fsd` and `box_constant` options are restricted to box01 and must not simply be used on the global grid. Once supported feedback is available, assess the mechanical response and the resulting growth, melt, ocean exchange and conservation behaviour. Changed ice area/thickness can legitimately change thermal fluxes; explain those changes rather than requiring two physically different runs to be identical.

The [G0 notebook](../../CICE_testing/notebooks/G0.ipynb) provides regional tables from the completed daily files. G1/G2 notebooks remain preparation for later work. Case configurations are indexed under [global_tests](../../global_tests/README.md).
