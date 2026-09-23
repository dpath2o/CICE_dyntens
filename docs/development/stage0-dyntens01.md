# Stage 0: dyntens01 control audit

Audited source: [35f83468e141d0b199e3ebcadfaf1d5f1e41e563](https://github.com/dpath2o/CICE_dyntens/blob/35f83468e141d0b199e3ebcadfaf1d5f1e41e563/) on `dev`.
Case: `dyntens01`. Audit date: 2026-09-23.

**Status: source inspection complete for the initial integration targets; runnable control verification remains open.** No model physics or case settings were changed by this audit.

## Build evidence and provenance

The user reports a successful Gadi compilation. [README.case](https://github.com/dpath2o/CICE_dyntens/blob/35f83468e141d0b199e3ebcadfaf1d5f1e41e563/dyntens01/README.case) records:

```text
Wed Sep 23 20:55:02 AEST 2026 ./cice.build:dyntens01 build completed cice.bldlog.260923-205333
```

The build log and executable are not tracked, so compiler invocation, warnings, binary identity and exact correspondence of the binary to the uploaded commit have not been independently verified. A successful build does not establish a successful initialisation or integration.

| Item | Committed evidence |
|---|---|
| Source directory | `/g/data/gv90/da1339/src/CICE_dyntens` |
| Case directory | `/g/data/gv90/da1339/src/CICE_dyntens/dyntens01` |
| Run directory | `/g/data/gv90/da1339/cice-dirs/runs/dyntens01` |
| Driver | `standalone/cice` |
| Parallel settings | `ICE_NTASKS=1232`, one thread, MPI |
| Build environment | Intel LLVM 2025.1.1, OpenMPI 4.1.7, HDF5 1.12.2, NetCDF 4.9.2 |
| Case Makefile flags | Macros select `-O2 -fp-model precise` when debug is off |
| Environment flag caveat | `FFLAGS_OPT="-O3 -fp-model fast=2"` is set, but the inspected Makefile recipes use `FFLAGS`; establish actual flags from the build log |
| Clean build setting | `ICE_CLEANBUILD=false`; archive the existing successful binary and log before any later clean rebuild |

Sources: [settings](https://github.com/dpath2o/CICE_dyntens/blob/35f83468e141d0b199e3ebcadfaf1d5f1e41e563/dyntens01/cice.settings), [environment](https://github.com/dpath2o/CICE_dyntens/blob/35f83468e141d0b199e3ebcadfaf1d5f1e41e563/dyntens01/env.gadi1_intel), [Macros](https://github.com/dpath2o/CICE_dyntens/blob/35f83468e141d0b199e3ebcadfaf1d5f1e41e563/dyntens01/Macros.gadi1_intel), [Makefile](https://github.com/dpath2o/CICE_dyntens/blob/35f83468e141d0b199e3ebcadfaf1d5f1e41e563/dyntens01/Makefile).

## Blocking configuration gap

**The actual `dyntens01/ice_in` is absent from this commit.** The root [.gitignore](https://github.com/dpath2o/CICE_dyntens/blob/35f83468e141d0b199e3ebcadfaf1d5f1e41e563/.gitignore#L9) excludes `ice_in`. The run script copies that file into the run directory, so the templates alone cannot identify the actual experiment.

The committed `casescripts/ice_in.mods` describes a 12×12, one-process, five-day closed-box setup with uniform eastward atmospheric forcing, calm ocean, `kstrength=0`, and disabled thermodynamics, ridging and transport. The base template has `grid_ice='B'`, `Ktens=0`, `tr_fsd=.false.`, `nfsd=1` and `wave_spec_type='none'`.

These are **template values, not verified active settings**. Meanwhile, `cice.settings` retains `ICE_GRID=gbox12` but requests 1,232 tasks. The actual namelist must resolve this discrepancy before classifying the case as a box test or Antarctic control. Do not submit the template-derived configuration with the large task count.

Required active values include:

- Grid, dimensions, decomposition and bathymetry/grounded-iceberg inputs.
- `kdyn`, EVP algorithm, viscosity method, `Ktens`, ellipse parameters, compressive strength and free-slip/lateral-drag controls.
- `tr_fsd`, `nfsd`, `restart_fsd`, `floediam`, wave spectrum type and filename.
- Start date, timestep, dynamics subcycling, run length, restart mode and resolved restart path.
- Atmospheric/ocean forcing, tide switches, mixed-layer settings and output frequencies.

## Launcher observations

The ordinary [cice.run](https://github.com/dpath2o/CICE_dyntens/blob/35f83468e141d0b199e3ebcadfaf1d5f1e41e563/dyntens01/cice.run):

- Changes directory through `/home/581/da1339/AFIM/src/CICE_dyntens/dyntens01`, while settings use the `/g/data/...` path. Check whether this is a valid symlink; equivalence was not established remotely.
- Loads Intel 2024.2.1 initially, then sources the case environment, which purges modules and loads 2025.1.1. The latter is the intended final stack; capture the loaded modules at execution.
- Hard-codes 1,232 MPI ranks and has two PBS storage directives. Consolidate storage requirements after resolving the actual input paths.

The continuous launcher uses `ICE_NTASKS` and accepts a separate `ICE_IN_SRC` snapshot. Stage 0 should use a single bounded run, not the multi-year submission wrapper. No launcher was changed here.

## Tensile-strength integration map

| Location | Finding and implication |
|---|---|
| [ice_init.F90](https://github.com/dpath2o/CICE_dyntens/blob/35f83468e141d0b199e3ebcadfaf1d5f1e41e563/cicecore/cicedyn/general/ice_init.F90#L479) | Defaults, reads and broadcasts scalar `Ktens`; new controls will need equivalent handling and validation |
| [visc_replpress](https://github.com/dpath2o/CICE_dyntens/blob/35f83468e141d0b199e3ebcadfaf1d5f1e41e563/cicecore/cicedyn/dynamics/ice_dyn_shared.F90#L3525) | Uses module scalar `Ktens` in both `zetax2=(1+Ktens)*tmpcalc` and `rep_prs=(1-Ktens)*tmpcalc*Delta`; shear viscosity follows bulk viscosity |
| [ice_dyn_evp.F90](https://github.com/dpath2o/CICE_dyntens/blob/35f83468e141d0b199e3ebcadfaf1d5f1e41e563/cicecore/cicedyn/dynamics/ice_dyn_evp.F90#L1683) | Multiple calls at different stress locations; audit the selected grid before threading the local coefficient |
| [stressCD_U](https://github.com/dpath2o/CICE_dyntens/blob/35f83468e141d0b199e3ebcadfaf1d5f1e41e563/cicecore/cicedyn/dynamics/ice_dyn_evp.F90#L2264) | CD-grid `avg_zeta` branch directly uses `(1-Ktens)/(1+Ktens)`; this is not automatically an active C-grid path |
| [ice_dyn_core1d.F90](https://github.com/dpath2o/CICE_dyntens/blob/35f83468e141d0b199e3ebcadfaf1d5f1e41e563/cicecore/cicedyn/dynamics/ice_dyn_core1d.F90#L223) and [ice_dyn_vp.F90](https://github.com/dpath2o/CICE_dyntens/blob/35f83468e141d0b199e3ebcadfaf1d5f1e41e563/cicecore/cicedyn/dynamics/ice_dyn_vp.F90#L1214) | Also call the shared routine; interface changes must preserve their disabled-mode behaviour |
| [step_dyn_horiz](https://github.com/dpath2o/CICE_dyntens/blob/35f83468e141d0b199e3ebcadfaf1d5f1e41e563/cicecore/cicedyn/general/ice_step_mod.F90#L1319) | Dispatches `kdyn=1` to EVP, 2 to EAP, 3 to the implicit solver |

A candidate minimal implementation is an explicitly passed local coefficient at the supported solver's stress locations, with the original scalar calculation retained when disabled. Do not overwrite a shared module scalar inside a cell loop. Spatial interpolation and the CD-grid averaged-viscosity pressure relation require a defined discretisation, not a blind scalar-to-array replacement.

## Wave/FSD integration map

1. [Initialisation](https://github.com/dpath2o/CICE_dyntens/blob/35f83468e141d0b199e3ebcadfaf1d5f1e41e563/cicecore/cicedyn/general/ice_init.F90#L2035) enables `wave_spec` when FSD is enabled and the spectrum type is not `none`.
2. [Standalone forcing](https://github.com/dpath2o/CICE_dyntens/blob/35f83468e141d0b199e3ebcadfaf1d5f1e41e563/cicecore/drivers/standalone/cice/CICE_RunMod.F90#L101) calls `get_wave_spec` under those flags.
3. [get_wave_spec](https://github.com/dpath2o/CICE_dyntens/blob/35f83468e141d0b199e3ebcadfaf1d5f1e41e563/cicecore/cicedyn/general/ice_forcing.F90#L5895) routes `constant`/`random` plus a filename containing `YYYYMM` to hourly WHACS ingestion and propagation. The static-file route reads `efreq`; these mode names alone do not establish constant-in-time forcing.
4. [Driver ordering](https://github.com/dpath2o/CICE_dyntens/blob/35f83468e141d0b199e3ebcadfaf1d5f1e41e563/cicecore/drivers/standalone/cice/CICE_RunMod.F90#L279) applies fracture **only on even `istep`**, passing **`2*dt`**, after the thermodynamic section and before dynamics/transport/ridging. This inherited cadence must be retained in the initial control and checked across restarts.
5. [step_dyn_wave](https://github.com/dpath2o/CICE_dyntens/blob/35f83468e141d0b199e3ebcadfaf1d5f1e41e563/cicecore/cicedyn/general/ice_step_mod.F90#L1072) resets the wave tendency on its calls, tests concentration and significant wave height, and passes category tracers to Icepack. On skipped driver steps, check the interpretation of the retained tendency in history output.
6. [Icepack FSD](https://github.com/dpath2o/CICE_dyntens/blob/35f83468e141d0b199e3ebcadfaf1d5f1e41e563/icepack/columnphysics/icepack_fsd.F90#L327) initialises bin-integrated area fractions and normalises them. Bin centres are **radii**; use twice the radius for a diameter threshold. Do not multiply these already-integrated fractions by bin width again when summing a large-floe fraction.

The first diagnostic cohesion evaluation should use category-area-weighted FSD after the relevant physics updates and before the momentum solve. Specify whether it is refreshed at each dynamics subcycle, then hold it fixed within EVP iterations. This remains a design decision pending the active namelist.

## Close-out requirements

- [x] Record uploaded source SHA and case build-completion entry.
- [x] Inspect initial tensile and wave/FSD integration targets.
- [ ] Commit the actual `dyntens01/ice_in` and reconcile it with launcher/decomposition settings.
- [ ] Record binary checksum, compiler command/module versions and build log.
- [ ] Resolve and record restart identity, forcing paths, grid/mask files and active physics.
- [ ] Complete a short bounded control run with successful initialisation, finite diagnostics, history output and a usable restart.
- [ ] Repeat from that restart and compare with a continuous control segment, including even/odd fracture cadence.

Do not mark Stage 0 complete or attribute an active wave/FSD configuration from compilation alone. No long experiment or new physics is required to resolve the configuration gap.
