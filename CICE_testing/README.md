# CICE_testing

An object-oriented Python toolbox for reproducible CICE validation. The package
lives inside `CICE_dyntens` for now, but receives the **model checkout and run
paths explicitly** and can move to its own repository without relocating model
source, changing scientific checks, or depending on `shuga`.

The framework follows shuga's `core/types.py`, `core/paths.py`, domain modules,
workflow scripts and notebook pattern. Import spelling is `CICE_testing`.
Python 3.10+ is required; use the analysis environment on Gadi rather than the
system Python 3.6. Numerical checks need NumPy/netCDF4; **all figures use PyGMT**.
PyGMT also needs a compatible installed GMT shared library and Ghostscript for
PNG/PDF export. Preparation and numerical validation do not import PyGMT.

## Install and configure

From the CICE_dyntens checkout:

```bash
python -m pip install -e ./CICE_testing
# In an environment with GMT and Ghostscript:
python -m pip install -e './CICE_testing[figures]'
export CICE_MODEL_REPO="$PWD"
export CICE_TEST_RUNS=/g/data/gv90/da1339/cice-dirs/runs
```

`--repo`, `--runs` and `--base-case` override defaults. The model checkout is
found from `CICE_MODEL_REPO` or the working directory's ancestors, never from
this package's install location. For compatibility, the existing Gadi run root
remains the fallback; portable workflows should always set `--runs` or
`CICE_TEST_RUNS`. Generated case directories stay in the model checkout. Moving
this entire `CICE_testing/` directory to a new repository gives it its own
`pyproject.toml`, docs, scripts, notebook and package; install it with `pip -e .`.

A GMT-enabled environment can also be created from the included specification:

```bash
conda env create -f CICE_testing/environment.yml
conda activate cice-testing
python -m pip install -e './CICE_testing[figures]'
```

Let conda resolve compatible PyGMT/GMT versions; if using an existing environment,
select a PyGMT release compatible with its installed GMT.

## Python objects and workflows

| Component | Role |
|---|---|
| `WorkflowSpec`, `TestingPaths` | Explicit model/run configuration; separate box/global figure and evidence paths |
| `RestartWorkflow` | B6.4 preparation, restart staging and continuous/split validation |
| `InvalidStateWorkflow` | B6.6 restart-entry subset: copied invalid/inactive inputs and serial/MPI abort evidence |
| `BoxWorkflow` | B6.5 shadow-fixture preparation, executable distribution, staging and analytical/neutrality/decomposition checks |
| `FeedbackWorkflow` | B6.5-F controlled box feedback, independent prescribed controls and exact physical equivalence |
| `CandidateValidator` | Diagnostic-only FSD candidates, streams, masks, mapping bounds and unchanged applied coefficients |
| `SpatialValidator` | Prescribed coefficients/winds and history/restart comparison |
| `RestartFSDDiagnostic` | Read-only global/hemispheric FSD classification and ice-area weighting |
| `MappingFixtures`, `NativeBinFixtures` | Compile the production Fortran source from an explicit model checkout |
| `ValidationFigures` | PyGMT mapping reference, fixture points, spatial fields, time series, comparison errors and FSD class areas |

```python
from pathlib import Path
from CICE_testing import WorkflowSpec, FigureSpec
from CICE_testing.workflows.box import BoxWorkflow
from CICE_testing.plotting.validation import ValidationFigures

workflow = BoxWorkflow(WorkflowSpec(
    repo=Path('/path/to/CICE_dyntens'), runs=Path('/path/to/runs'),
    base_case=Path('/path/to/CICE_dyntens/dt_b63_diag')))
# Call prepare/distribute/stage at the appropriate point in the documented sequence.
# After the fourteen model jobs finish:
workflow.run_with_evidence('analyse', Path('/path/to/report/box/evidence'))
plots = ValidationFigures(FigureSpec(Path('/path/to/report'), scope='box'))
plots.mapping()  # Analytical reference, not a measured result.
plots.snapshot(Path('/path/to/runs/dt_b65_sp_s1/history/iceh.2005-01-01.nc'))
```

## Workflow scripts and compatibility

| Installed command | Workflow script under `CICE_testing/scripts/` |
|---|---|
| `cice-test-restart` | `b64_restart_workflow.py` |
| `cice-test-invalid` | `b66_invalid_state_workflow.py` |
| `cice-test-box` | `b65_box_workflow.py` |
| `cice-test-feedback` | `b65_feedback_workflow.py` |
| `cice-test-candidates` | `check_b63_candidates.py` |
| `cice-test-spatial` | `check_box_spatial_g.py` |
| `cice-test-fsd` | `diagnose_restart_fsd.py` |
| `cice-test-mapping` | `b6_fortran_mapping.py` |
| `cice-test-fixtures` | `b65_fortran_fixtures.py` |
| `cice-test-figures` | `generate_validation_figures.py` |

Existing `python test_scripts/<script>.py ...` commands and helper imports stay
available as compatibility adapters; there is one implementation in the package.
The existing unit tests remain in `test_scripts/`. New package tests live in
`CICE_testing/tests/` and can travel with the package.

```bash
cice-test-box prepare --repo "$CICE_MODEL_REPO" --runs "$CICE_TEST_RUNS" \
  --base-case "$CICE_MODEL_REPO/dt_b63_diag"
# Build the three controls and submit/run jobs using the existing B6.5 procedure.
cice-test-box distribute --repo "$CICE_MODEL_REPO" --runs "$CICE_TEST_RUNS"
# After segment A completes; then submit segment B:
cice-test-box stage --repo "$CICE_MODEL_REPO" --runs "$CICE_TEST_RUNS"
# After all runs complete:
cice-test-box analyse --repo "$CICE_MODEL_REPO" --runs "$CICE_TEST_RUNS" \
  --evidence /path/to/report/box/evidence
cice-test-figures snapshot --history "$CICE_TEST_RUNS/dt_b65_sp_s1/history/iceh.2005-01-01.nc" \
  --field dtens_gcand --output /path/to/report
```

Building/submitting remains explicit; preparation refuses existing destinations.
The B6.4 and B6.5 workflows retain their audited box layout, dates, coefficients,
file inventories, strict zero-tolerance comparisons and limited `blkmask`
ownership exceptions. They are **not general global-grid experiment generators**.
Global output can use generic figures and the FSD diagnostic now; global gate
specifications and model experiment workflows will be added with actual runs.

## Figures and development records

Open [validation_figures.ipynb](notebooks/validation_figures.ipynb). Its configuration
cell selects actual run paths, daily/hourly streams and `box` or `global` scope.
Every plot is exported as PNG and PDF alongside a JSON input-checksum manifest.
Measured time series and comparisons also export CSV tables. Figure generation
is read-only with respect to CICE runs and never awards a validation PASS.

The comparison figure records every variable/file in a CSV, including mask
mismatches and any explicit history block-ownership exclusion. Max-error plots
alone do not establish exact equivalence. Global snapshots use geographic
cell-centre symbols, not a silently interpolated regular grid. Large global
runs are read one file/variable at a time; figure provenance hashes the inputs.

The [report handoff plan](docs/development_reports.md) maps evidence to the planned
`box_tensile_dev_procedure_results_validation_notes.md` and a parallel global
record. The active record is now split into [box01 case documents](../docs/development/box01_dev_dynamic_tensile_strength.md) and [global case documents](../docs/development/global_dev_dynamic_tensile_strength.md); B6.6 is complete as the agreed box review; the original restart-entry matrix remains failed on the tiny-area case. Historical development
notes remain the authoritative stage-by-stage record in the meantime.

## G0 short global control

`python CICE_testing/scripts/g0_global_workflow.py prepare|analyse --repo ... --runs ...`
prepares isolated two-day global off/unity cases from the migrated global template.
Build off once and copy its executable to unity. The [G0 instructions](../docs/development/G0.md)
provide the Bash commands. Analysis checks output equality and restart clocks;
global FSD sum policy belongs to G1. The inherited wave mode is constant, not WHACS. The two-day comparison passed on 8 October 2026. `notebooks/G0.ipynb` now creates regional totals and field-statistics tables from the actual final daily files without importing plotting libraries.

## Verification

```bash
python -m unittest discover -s test_scripts -v
python -m pytest CICE_testing/tests -q
cice-test-mapping --repo "$CICE_MODEL_REPO" --fc ifort --fflags '-O0 -g -check all -traceback'
cice-test-fixtures --repo "$CICE_MODEL_REPO" --fc ifort --fflags '-O0 -g -check all -traceback'
```

Synthetic and compiler fixture results validate checker behaviour and production
mapping routines, not full CICE runtime results. B6.5-F has passed its controlled
feedback comparisons. B6.6 records the completed review and retained runtime limitations.

The package workflow in `.github/workflows/cice-testing.yml` runs the numerical
regressions, production Fortran fixtures, real PyGMT export checks and packaging.
The figure smoke checks were exercised with PyGMT 0.16.0 / GMT 6.5.0; synthetic
fixtures are labelled as such and are not committed as model-result figures.

The B6.6 restart-entry subset and its phased Bash commands are documented in the
[model development record](../docs/development/B6.6.md).
Its analyser retains the original twelve-case criteria and still fails on the
tiny-area continuation. Completing the revised B6.6 review does not override
that runtime result or certify unverified MPI comparisons.

## Organised cases and per-stage figures

[Case organisation](../docs/development/case_organisation.md) defines stable run IDs, case directory migration, backup/provenance and Git inclusion. `organise_test_cases.py plan|apply` moves only configurations and legacy caselists; completed runs stay fixed. Workflows resolve root or nested configurations and preserve input-hash checks through a reproducible relocation ledger.

`notebooks/B0.ipynb` through `B6.6.ipynb`, including `B6.5-F.ipynb`, and `G0.ipynb`–`G2.ipynb` generate conceptual PyGMT diagrams and expose optional actual-history plotting. Recreate all designs with `python -m CICE_testing.plotting.development --case all --output docs/development/figures`. No conceptual figure is labelled as measured output or a validation PASS.
