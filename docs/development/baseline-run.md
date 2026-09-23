# dyntens01 baseline: September 2000 restart

## Execution record

The January initialisation check completed according to the user-supplied PBS output:

- Job: `179696710.gadi-pbs`; exit status 0.
- Output: `/g/data/gv90/da1339/cice-dirs/runs/dyntens01/baselines/control.vJ1sGPaM`.
- Walltime: 3 min 44 s; 95.82 SU; peak reported memory: 348.81 GB.
- The launcher found a completion marker and NetCDF history/restart output.

This establishes successful execution, not yet finite-field, FSD-normalisation or restart-reproducibility validation. Preserve that directory and its input/source/executable records.

## Current control

The next run starts from the user-selected `waves-floe300` restart, `iced.2000-09-01-00000.nc`. The parent is described by the user as a healthy waves run. Its configuration and restart contents have not been independently inspected.

Copy the file into:

```text
/g/data/gv90/da1339/cice-dirs/runs/dyntens01/restart/iced.2000-09-01-00000.nc
```

The launcher copies it again into a unique baseline directory under `input_restart/`, makes the copy read-only, saves its NetCDF header and records its checksum. New output goes into a separate `restart/` directory. Existing runs and the supplied parent file are not overwritten.

| Setting | Control |
|---|---|
| Start / duration | 2000-09-01; two model days; expected end 2000-09-03 |
| Restart mode | `runtype='initial'` with explicit `ice_ic='./input_restart/iced.2000-09-01-00000.nc'` |
| Saved state | `use_restart_time=.true.`, `restart_fsd=.true.` |
| Grid / parallelism | 1440 × 1080 C-grid; 1232 ranks |
| Dynamics | Standard 2-D EVP; dt=1800 s; ndtd=1; ndte=360 |
| Strength | kstrength=0; Ktens=0.2; ellipse/plastic-potential ratios 1.5 |
| Resistance | free_slip; static lateral drag; Cs=1e-3 |
| FSD / waves | 12 FSD bins, five thickness categories; CAWCR spectrum; 25 frequency bins |
| Other forcing | ERA5; AFIM/ORAS with 14-day restoring; hmix_0=60 m; tides off |
| Output | Daily double-precision history including FSD/waves; daily and final restarts |

In this code, an explicit restart filename with `runtype='initial'` reads the saved core state. Enabling `use_restart_time` also reads its date and timestep counter. This avoids relying on an external pointer file. The segment advances 96 additional timesteps, not necessarily to absolute timestep 96.

The forcing cycle remains `fyear_init=1995, ycycle=11`; the inspected year-mapping expression selects forcing year 2000 for model year 2000. Confirm the dated atmospheric, ocean and wave files in the runtime diagnostic.

No Fortran physics changed. Wave fracture still runs on even timestep counters with `2*dt`. Reading the saved timestep counter preserves its parity.

## Restart compatibility

The selected NetCDF backend stores core and enabled FSD variables in the same file. The launcher checks the header for `fsd001` through `fsd012`, a 2000-09-01 00:00 date and a saved `istep1`. It stops if these are absent rather than silently reinitialising FSD.

These checks are necessary but not sufficient. Confirm the parent used compatible grid/mask, five categories, four ice layers, one snow layer, and the same 12-bin FSD bounds. A case name containing `floe300` alone does not prove FSD was enabled. If the variables are missing, select a restart with the intended FSD state or explicitly design a separate FSD-initialisation experiment.

Retain the parent run's namelist and source identity for comparison. This is a new control initialised from that state; equivalence to continuation of the parent run remains unproven.

## Run on Gadi

After copying the parent restart:

```bash
cd /g/data/gv90/da1339/src/CICE_dyntens
git pull --ff-only origin dev
cd dyntens01
qsub cice.baseline.run
```

No rebuild is required. Do not edit the case while queued: inputs are captured at job start. The launcher reuses the case environment and existing executable, with the existing two-hour and 1200-GB resource ceilings; the healthy ice-state run may cost more than the January initialisation test.

The PBS output prints `BASELINE_RUN=...` for a fresh directory under `dyntens01/baselines/`. It records executable/input/restart checksums, source SHA and local changes, modules and compiler/MPI information. The actual build provenance of the earlier executable still depends on its original build log.

## Acceptance and next comparison

The launcher's execution checks are MPI status, completion marker and history/restart presence. After success:

1. Confirm restart reading, start/end dates, saved timestep counter, active flags and forcing year.
2. Inspect finite concentration, thickness/volume, velocity and stresses on valid cells; exclude fill values.
3. Check instantaneous restart FSD fractions per occupied thickness category for bounds and normalisation. Daily means require care when category ice appears or disappears.
4. Check finite/nonnegative wave diagnostics and plausible fracture activity; interpret the tendency with the inherited two-step cadence.
5. Repeat the identical two-day restart run in another fresh directory and compare numerical fields.
6. Prepare a one-day plus one-day restart continuation, then compare its endpoint with the continuous two-day segment, including core/FSD state and timestep parity.

Stage 0 remains open until these numerical checks pass. The successful initialisation run alone does not validate the September mechanical control.
