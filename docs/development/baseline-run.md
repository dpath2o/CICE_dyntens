# dyntens01: first baseline execution

## Purpose and status

This is a **two-day initialisation and numerical control**, starting 1995-01-01 with the inherited constant tensile coefficient. It is prepared, not yet run or validated on Gadi. No Fortran physics changed.

The uploaded namelist at commit `56e5dcda4dfeb606320ea770054b213b0c5342fd` establishes the actual global configuration; the older box templates are not the active namelist.

| Setting | Baseline |
|---|---|
| Grid | 1440 × 1080 tripolar C-grid |
| Decomposition | 1232 MPI ranks, 20 × 20 blocks, max_blocks=8, rake distribution |
| Dynamics | Standard 2-D EVP, dt=1800 s, ndtd=1, ndte=360 |
| Strength | kstrength=0; Ktens=0.2; ellipse and plastic-potential ratios 1.5 |
| Resistance | free_slip; static lateral drag; Cs=1e-3 |
| FSD | Enabled, 12 bins, five thickness categories |
| Waves | CAWCR monthly filename template; 25 frequency bins; inherited propagation/fracture |
| Tides | Disabled |
| Atmosphere | ERA5, unmodified forcing factor |
| Ocean | AFIM/ORAS forcing; restoring timescale 14 days; hmix_0=60 m |
| Initial condition | runtype=initial, ice_ic=none; no existing restart supplied |
| Duration | Two model days (96 timesteps), ending 1995-01-03 if successful |

The inherited fracture schedule is every second timestep with 2*dt: hourly at this timestep. Preserve it for the control.

## What changed from the uploaded namelist

- Shortened one month to two days.
- Daily restarts and a final dump; initial-condition output enabled.
- Daily double-precision history with coordinates, area and mask.
- Enabled daily FSD fractions (aggregate and per category), category area, floe radius/perimeter, wave tendency and significant wave height.
- Removed inactive hourly requests from field flags; the configured stream is daily.
- Enabled global diagnostic summaries.
- Set restart_fsd=false explicitly: initialisation already overrides it to false for ice_ic=none.

All inherited physical parameters and forcing paths remain as supplied. Dynamic tensile strength is not implemented yet.

The repository no longer ignores files named `ice_in`. Newly created namelists can now be staged normally; inspect `git status` before broad adds to avoid tracking unwanted generated cases.

## Run on Gadi

From a clean working tree:

```bash
cd /g/data/gv90/da1339/src/CICE_dyntens
git pull --ff-only origin dev
cd dyntens01
qsub cice.baseline.run
```

A rebuild is not required for these namelist, documentation and launcher changes. Use the executable already compiled from the uploaded source. Do not edit the case while the job is queued: the launcher snapshots inputs and source metadata when execution begins.

The launcher uses the existing case environment and executable, 1232 ranks, a two-hour walltime ceiling and the original ordinary launcher's 1200 GB memory request. The walltime is a cap, not a performance estimate. It checks the rank count, selected namelist values and static-input paths before starting. The model checks dated forcing files when it opens them.

Each invocation gets a new directory under:

```text
/g/data/gv90/da1339/cice-dirs/runs/dyntens01/baselines/control.XXXXXXXX/
```

The PBS output prints `BASELINE_RUN=...`. Existing history and restart files in the main run directory are not overwritten. The run directory contains the executable/input checksums, source SHA/status/diff, loaded modules, compiler/MPI information, namelist, stdout log, diagnostic file, history and restart output.

The binary checksum identifies the tested executable; the source SHA alone does not prove how an earlier binary was built. Preserve the original successful build log with the baseline evidence. If local source modifications or untracked source files are listed, reconcile them before treating the run as a reproducible source control.

## Acceptance checks

The launcher checks MPI exit status, a completion marker, and the presence of NetCDF history and restart files. These are execution checks, not scientific acceptance.

After completion, verify:

1. Initialisation reports the intended C-grid, rank count, physical switches and input files.
2. The simulation reaches 1995-01-03 with 96 timesteps; daily outputs have the expected dates.
3. Concentration, volume/thickness, velocities and stresses are finite on valid ocean/ice cells; distinguish NetCDF fill values from invalid model values.
4. FSD category fractions are finite and normalised where category ice exists. Ice-free categories may be zero. Use per-category fractions for this check; normalisation of time-mean fields needs care when category ice appears/disappears.
5. Wave spectra and significant wave height are finite/nonnegative, and fracture diagnostics occur only where eligible. The inherited two-step fracture cadence can affect daily tendency interpretation.
6. The output restart includes the enabled FSD state and can support a restart comparison.

First repeat the same initial two-day job using the same executable and inputs in a fresh directory. Compare numerical arrays rather than file hashes alone, since metadata can differ. Then prepare a one-day-plus-one-day continuation from the day-one restart and compare its endpoint with the continuous two-day run. Include core and FSD restart state, model date, timestep parity and applicable accumulators; do not overwrite the original control.

## Limit of this baseline

An initial run with ice_ic=none is not an established Antarctic fast-ice state. Even a successful two-day run may provide little coverage of tensile response or wave fracture. After this execution check, select an existing compatible restart with established ice and documented FSD state for the mechanical control. Do not invent a restart path or treat a short initialisation run as a validated fast-ice response experiment.

Stage 0 remains open until runtime outputs and restart reproducibility have been checked.
