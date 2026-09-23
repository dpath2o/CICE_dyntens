# Stage 1: local tensile coefficient with g = 1

This stage introduces the optional local coefficient
`Ktens_effT(i,j,iblk) = Ktens * 1`. It is a plumbing/equivalence test, not
FSD-dependent feedback. The September control remains the reference; snow
thermodynamics, waves, FSD evolution and compressive strength are unchanged.

## Implementation

`use_dyntens` is a logical in `dynamics_nml`, defaulting to `.false.`. It is
broadcast to all ranks and printed in `ice_diag.d`. With `.true.`, startup
also prints `Dynamic tensile stage 1: g=1`.

The enabled path currently requires `grid_ice='C'`, `kdyn=1`,
`evp_algorithm='standard_2d'`, `visc_method='avg_zeta'`,
`yield_curve='ellipse'`, `revised_evp=.false.`, and `0 <= Ktens <= 1`.
Other combinations abort rather than silently using the scalar path.
These restrictions apply only when the switch is enabled.

- `ice_dyn_evp.F90` allocates a private T-point coefficient field only when
  enabled. It fills every cell, including halos and land, with `Ktens*1`
  at initialisation and once per dynamics step, outside the EVP subcycles
  and OpenMP regions.
- `stressC_T` passes the corresponding cell value to the new optional
  `ktens_local` argument of `visc_replpress`.
- `ice_dyn_shared.F90` uses that value in both `(1+Ktens_eff)` for viscosity
  and `(1-Ktens_eff)` for replacement pressure. Calls without the optional
  argument retain the original scalar expressions.
- The existing `avg_zeta` path exchanges T-point viscosities and averages
  shear viscosity to U points. `stressC_U` consequently receives the
  modified viscosity through its existing interface. The direct scalar
  expression in `stressCD_U` belongs to the unsupported CD-grid path.

The coefficient is derived, not prognostic: no restart variable is added.
A uniform g=1 field needs no separate halo exchange. Spatial g will require
explicit boundary/halo treatment and diagnostics before feedback is enabled.
No non-unit g option is provided at this stage.

## Build and run on Gadi

Preserve the completed reference directory:

```text
/g/data/gv90/da1339/cice-dirs/runs/dyntens01/baselines/control.nV1DLnlV
```

It contains the old executable, input namelist and restart snapshot. The
user-supplied log records September 1–3, 2000, steps 99360–99456, job
179698538, exit 0. Numerical equality and split-run restart reproducibility
have not yet been established. Snow-temperature warnings remain a known,
deferred baseline limitation.

Rebuild because Fortran interfaces have changed:

```bash
cd /g/data/gv90/da1339/src/CICE_dyntens
git pull --ff-only origin dev
cd dyntens01
./cice.build clean
./cice.build
```

Only after `COMPILE SUCCESSFUL`, submit the paired tests:

```bash
qsub -N dyntens01-off -v DYNTENS_MODE=control cice.baseline.run
qsub -N dyntens01-g1  -v DYNTENS_MODE=g1      cice.baseline.run
```

The tracked `ice_in` stays disabled and explicitly records the existing
`yield_curve='ellipse'` default. The launcher changes only `use_dyntens`
in the g1 run's private input copy. Each job prints `BASELINE_RUN=...`, using
`control.XXXXXXXX` or `g1.XXXXXXXX` directories, and records the selected mode.
Both start from the same September input restart and should run 96 steps.
Do not change the executable, input restart or case files until both jobs
have captured their inputs and completed. Run them sequentially if preferred.
The new namelist is not compatible with the old executable, which does not
recognise `use_dyntens`.

Check the runtime switch and g=1 diagnostic, completion, forcing dates,
and final restart date/counter. Reuse the baseline's existing compiler,
MPI, rank count and forcing environment.

## Numerical acceptance

Use a Python environment containing `numpy` and `netCDF4`. Substitute the
new paths printed by PBS; the original reference path below is literal.

```bash
cd /g/data/gv90/da1339/src/CICE_dyntens
old=/g/data/gv90/da1339/cice-dirs/runs/dyntens01/baselines/control.nV1DLnlV
off=/g/data/gv90/da1339/cice-dirs/runs/dyntens01/baselines/control.REPLACE_ME
g1=/g/data/gv90/da1339/cice-dirs/runs/dyntens01/baselines/g1.REPLACE_ME
python3 tools/compare_dyntens_runs.py "$old" "$off"
python3 tools/compare_dyntens_runs.py --same-executable "$off" "$g1"
```

The first comparison tests the disabled path against the old build. The
second tests local g=1 against the disabled path using the same executable.
The checker requires matching input-restart checksums, MPI exit 0, identical
output file sets, dimensions, variable types, selected interpretation
metadata, and restart date/counter attributes. It compares every output
variable with exact numerical equality and matching masks; it rejects
unmasked NaNs/infinities. NetCDF container bytes and incidental provenance
attributes need not match.

For each output restart it also checks all 12 FSD fractions in categories
with `aicen > 1e-12`: no masked/nonfinite occupied bins, fractions within
`[-1e-12, 1+1e-12]`, and a sum within `1e-10` of one. Those thresholds
are numerical tolerances for this check, not model parameter changes.
It reads bounded latitude chunks rather than loading entire files.

Any failure blocks the equivalence claim. Inspect it before changing a
tolerance or proceeding to non-unit g. A passing pair does not establish
one-day plus one-day restart reproducibility, which remains a separate
baseline check. It also does not diagnose the deferred snow warnings.

## Validation of this change

The three edited Fortran modules passed preprocessing and Fortran 2008
syntax parsing. `bash -n` passed for the launcher. The numerical checker
passed nine synthetic regression tests covering equality, changed fields,
masks, nonfinite fields, FSD sums, missing output, timestep differences,
input restart differences and executable differences.

A full Intel/MPI CICE build and the physical off/on comparisons must run
on Gadi. No runtime equivalence is claimed from local syntax tests.

To repeat the checker tests:

```bash
python3 -m unittest discover -s tools/tests -v
```
