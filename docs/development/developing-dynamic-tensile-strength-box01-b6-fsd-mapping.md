# B6 — Developing the size/FSD mapping for dynamic tensile strength

Updated 5 October 2026.

This document develops the controlled size/FSD-to-g calculation for
CICE_dyntens. The [box01 development record](developing-dynamic-tensile-strength-box01.md)
retains the B0–B5 evidence and the route back to global forcing. B6 is the final
planned controlled mapping stage in the box programme, but it includes several
implementation and validation steps. It is not a single additional namelist run.

## Current position and purpose

B4 established matched-control identity and B5 established exact agreement
between continuous and split runs for prescribed spatial g. Those tests verify
the coefficient pathway for the tested box configuration. They do not establish
how an FSD should determine that coefficient.

The next task is to replace a prescribed multiplier with a derived candidate
whose result can be calculated independently. First verify the calculation
without changing momentum. Then test a small number of equivalent solutions
with feedback enabled.

**The Python mapping contract has passed all 10 reported tests. The corresponding
Fortran mapping and CICE diagnostic integration remain to be implemented.**
The existing executable supports prescribed constant and box_band modes.
Changing floediam alone does not currently exercise this mapping.

The reference repository revision inspected for this plan is
8dc6aa64bac99651cc302ed08f6eb47812ec82b1. No model-source changes are made by
this documentation update.

## 1. Agreed controlled-test mapping

For this development test, adopt the README's large-floe-area-fraction candidate:

$$
L_n = \sum_{k:D_k>D_*} f_{k,n}, \qquad
A = \sum_n a_n,
$$

$$
F_L = \frac{\sum_n a_n L_n}{A}, \qquad
g_{\mathrm{candidate}} = g_{\min}+(1-g_{\min})F_L,
$$

$$
K_{t,\mathrm{candidate}} = K_t g_{\mathrm{candidate}}.
$$

| Symbol | Meaning | Units |
|---|---|---|
| a_n | Grid-cell ice-area fraction in thickness category n | 1 |
| f_{k,n} | Fraction of category n's ice area in floe bin k, integrated over the bin | 1 |
| D_k | Representative floe diameter for bin k | m |
| D_* | Large-floe diameter threshold | m |
| A | Total grid-cell ice concentration | 1 |
| L_n | Large-floe fraction within category n | 1 |
| F_L | Large-floe fraction of the ice-covered area | 1 |
| g, g_min | Tensile multipliers | 1 |
| K_t, K_{t,candidate} | Tensile coefficients in the rheology | 1 |

K_t times g is a dimensionless coefficient, not a stress in N/m or Pa.

The denominator is ice area, not total cell area and not the number of occupied
categories. Thus open water does not dilute F_L, and thick/thin categories
contribute in proportion to their areas, not their volumes.

### Test parameters and threshold convention

Use D_*=300 m, g_min=0.2 and K_t=0.2 for the analytical tests.
These are test choices, not calibrated global parameters or a settled physical
closure. They can be revised through a separately documented sensitivity study.

Use a strict representative-diameter threshold: D_k > D_*.
A representative diameter exactly equal to D_* is classified as small.
This is a whole-bin classification, not a partial integral through a bin that
straddles the threshold. Record this approximation when connecting real bins.

For a single prescribed diameter, all ice occupies that diameter. The response
is a step from g_min to one at the threshold. It is monotone but not smooth.
Intermediate g values arise from mixed distributions. A smooth diameter response
would be a different mapping and must not be introduced implicitly.

A Python diameter input must not be interpreted directly as an Icepack radius.
The adapter must establish the source convention before applying D=2r.
Do not relabel radius as diameter or double it twice.

## 2. Input validity and inactive cells

The reference contract implements the following behaviour.

| Input condition | Required controlled-test behaviour |
|---|---|
| Finite nonnegative category areas, total A > 1e-12 | Evaluate the occupied-category FSDs |
| A <= 1e-12 | Inactive result; F_L undefined; neutral g=1 and K_t,candidate=K_t |
| Exactly zero category area | Ignore its FSD values after checking array shape |
| Positive category area in an active cell | Require finite nonnegative bins and abs(sum(f)-1) <= 1e-10 |
| Zero-sum FSD in an occupied category | Reject |
| Negative, missing or nonfinite occupied-category bin | Reject |
| Material normalisation error | Reject; do not silently renormalise |
| Negative or nonfinite category area | Reject |
| Total concentration > 1 + 1e-10 | Reject |
| Missing/mismatched categories or bins | Reject |
| Nonpositive/nonfinite or unordered representative diameters | Reject |
| Invalid threshold or g_min/K_t outside [0,1] | Reject |

The inactive-cell test occurs before occupied-FSD numerical validation when
total A <= 1e-12. For an active cell, every positive-area category is checked,
even if that particular category has very small area. These choices must match
between the reference and production calculation.

The accepted sum tolerance is a numerical test tolerance, not permission to
repair inherited global FSD errors. The reference only clips F_L into [0,1]
after verifying that any excursion is within the declared tolerance. It does
not divide each category by its bin sum.

NaN is used for undefined F_L in the Python reference. In CICE history output,
use a proper masked/fill value and an explicit validity/inactive indicator;
do not emit an unmasked NaN that would violate finite-field checks. Neutral g=1
in an inactive cell is a computational convention, not evidence of cohesive ice.

For deliberately invalid controlled inputs, require an explicit error/status
and no successful mapping result. In MPI integration, arrange a collective
failure path so a local invalid cell does not leave other ranks waiting in a
halo exchange. The global diagnostic policy for inherited invalid states needs
a separate decision; never silently supply a candidate to momentum from invalid
data.

## 3. Analytical cases and expected answers

Use representative diameters [100,1000] m for the two-bin algebraic cases.
These are synthetic inputs to the calculation, not a claim about the inherited
Icepack bin grid.

| Case | Areas and category FSDs | F_L | g | K_t,candidate |
|---|---|---:|---:|---:|
| All small | a=[0.9]; f=[[1,0]] | 0 | 0.2 | 0.04 |
| All large | a=[0.9]; f=[[0,1]] | 1 | 1 | 0.2 |
| Equal mixture | a=[0.9]; f=[[0.5,0.5]] | 1/2 | 0.6 | 0.12 |
| Unequal areas | a=[0.3,0.6]; f=[[1,0],[0,1]] | 2/3 | 11/15 | 11/75 |
| More open water | a=[0.1,0.2]; same category FSDs | 2/3 | 11/15 | 11/75 |
| Empty category | a=[0,0.9]; f=[[NaN,NaN],[0,1]] | 1 | 1 | 0.2 |
| No/negligible ice | A=0 or 1e-13 | Undefined | 1, inactive | 0.2 |
| Unity limit | g_min=1; any valid FSD | As calculated | 1 | 0.2 |

For a single diameter, test 100, 299, 300, 301 and 1000 m. Expected g is
0.2, 0.2, 0.2, 1 and 1 respectively. Sweep the large-floe mixture fraction from
0 to 1 to test the intermediate values and monotonicity.

## 4. Reference-test results supplied 5 October 2026

The user ran test_scripts/test_b6_mapping_contract.py on Gadi and supplied:

~~~
Ran 10 tests in 0.001s

OK
~~~

| Test | Result |
|---|---|
| test_empty_category_is_ignored | PASS |
| test_invalid_area | PASS |
| test_invalid_occupied_fsd | PASS |
| test_monotonic_mixture | PASS |
| test_open_water_does_not_dilute_fraction | PASS |
| test_prescribed_diameter_threshold | PASS |
| test_small_large_and_mixed | PASS |
| test_unequal_category_areas | PASS |
| test_unity_limit | PASS |
| test_zero_and_negligible_ice | PASS |

This is user-supplied evidence for the local Python reference. It does not
certify the Fortran implementation, the Icepack adapter, history diagnostics,
MPI exchange, restart behaviour or physical calibration. This documentation
change does not add or replace the user's local Python file.

Repeat locally with:

~~~bash
cd /g/data/gv90/da1339/src/CICE_dyntens
bash <<'BASH'
set -euo pipefail
python3 test_scripts/test_b6_mapping_contract.py \
    2>&1 | tee test_scripts/b6_mapping_contract.log
BASH
~~~

Before using it as a tracked regression reference, preserve the exact test
source and its revision/checksum. Extend negative tests to cover bad parameters,
shape errors and diameter ordering as well as the ten reported tests.
Those input checks exist in the reference function but do not all have dedicated
tests in the reported suite.

## 5. Implementation sequence

### B6.1 — audit the inherited FSD interface

Trace the actual tracer access, bin definitions and normalisation convention
through the inherited Icepack and CICE source. Record file/function references
at the implementation revision.

Establish whether the exposed tracer is already a bin-integrated category
fraction, a density requiring bin widths, or a differently weighted quantity.
Check category and bin indexing, radius/diameter units, missing-value handling,
and tracer availability at initialisation and restart.

Produce an adapter contract with explicit array dimensions and conversions.
Do not infer this from fsd001-style restart names alone. If the actual
representation differs from the analytical input, convert it explicitly and
test that conversion independently.

### B6.2 — implement and test the production calculation

Implement one reusable calculation that accepts category areas, integrated
bin fractions, representative diameters and mapping parameters. Return F_L,
candidate g, active/valid status and an identifiable failure reason.

Keep file I/O, namelist parsing and halo operations outside the arithmetic
routine. Test the actual routine used by CICE with a small Fortran driver.
The driver should emit inputs/results/status in a simple machine-readable form
that Python can compare to analytical expectations.

Use tight floating-point tolerances for Python-versus-Fortran formula checks
(e.g. 1e-12 absolute for these dimensionless fixtures); do not demand binary
identity across languages. Check bounds and expected failures separately.
Preserve zero-tolerance comparisons for equivalent CICE trajectories where
the arithmetic path warrants them.

The Python suite passing against itself is not sufficient for this step.

### B6.3 — add candidate diagnostics with feedback disabled

Proposed diagnostics, not currently available variables:

| Diagnostic | Purpose | Units |
|---|---|---|
| dyntens_large_fraction | Derived F_L on active, valid T cells | 1 |
| dyntens_g_candidate | Candidate multiplier | 1 |
| ktens_eff_candidate | K_t times candidate g | 1 |
| dyntens_mapping_status | Distinguish valid, inactive and invalid input | 1 |

Retain existing dyntens_g and ktens_eff as the applied coefficients.
When candidate-only diagnostics are enabled, applied g remains one and applied
Ktens remains the control value. Candidate calculation needs an independent
enable path: the existing disabled dynamics path, which reports g=1, is not
by itself a candidate diagnostic mode.

Target integration points include ice_init.F90 for configuration/validation,
ice_dyn_shared.F90 for shared configuration, ice_dyn_evp.F90 for coefficient
application, and the history modules for output. Choose the calculation's module
location after the interface audit; do not duplicate the mapping in several
dynamics routines.

Make candidate diagnostics available on daily and instantaneous streams.
Define the IC snapshot behaviour so fields are initialised before output.
No new namelist names are prescribed here until their implementation exists.

### B6.4 — specify timing, halo and restart semantics

For a first implementation, target one candidate evaluation per dynamics
timestep from the current pre-dynamics ice/FSD state, held fixed during EVP
subcycling. Confirm the actual driver ordering before coding and document
whether transport, thermodynamics and fracture have already updated that state.
Do not promise a same-timestep fracture response without tracing that ordering.

Compute owned T-cell values, then exchange the derived scalar field needed by
the dynamics stencil using the established centre/scalar halo pathway.
Define physical-boundary fill and inactive-cell behaviour explicitly. Use
global indices only for controlled spatial fixtures, never rank-local band
positions. Compare the 6/7 boundary across decompositions.

Recompute derived candidates after restart from restored inputs and unchanged
parameters. Do not make g a prognostic restart tracer. Synthetic prescribed
inputs must also be reconstructed reproducibly; otherwise a passing restart
test would not exercise the same mapping input.

### B6.5 — run the controlled box matrix

Use new cases and build directories for this implementation. Keep the accepted
B4/B5 archives and executables. Reuse one new executable across matched tests
within each layout; serial and MPI layouts may require separate builds.

| Experiment | Inputs | Required evidence |
|---|---|---|
| B6-A | Prescribed diameter below, at and above threshold | Endpoint classification; candidate bounds; applied g=1 in diagnostic mode |
| B6-B | Uniform all-small, all-large and mixed synthetic FSD | Candidate diagnostics agree with analytical answers |
| B6-C | Unequal category areas and scaled total concentration | Correct area weighting and invariance to open-water fraction |
| B6-D | Spatial small/large pattern crossing global columns 6/7 | One-block and two-rank candidate/physical-field agreement |
| B6-E | Two-day plus three-day restart of spatial case | Reconstructed candidates and aligned outputs match the continuous path |
| B6-F | Uniform mapping with feedback enabled | Equivalent solution to an independently prescribed constant g |

Diagnostic-only runs must match the corresponding g=1 physical control.
Use an explicit, narrow list of newly added candidate diagnostics when comparing
different candidate inputs: those fields are expected to differ. Do not exempt
applied coefficients or physical fields. Compare candidate diagnostics exactly
across equivalent layouts/restarts, subject to the declared numerical policy.

For B6-F, choose endpoint and equal-mixture inputs whose expected candidate
matches the prescribed control. Inspect the computed coefficient before
interpreting a trajectory difference; do not casually replace a computed
fraction with a rounded decimal and assume exact arithmetic identity.

The controlled fixture mechanism must be explicit and confined to the box
test path. Preserve a prescribed input for the mapping tests; do not silently
overwrite evolving model FSD every timestep in a production configuration.
In a later adapter test, populate actual Icepack bins with known normalised
fractions and verify the adapter separately from the synthetic two-bin driver.

### B6.6 — invalid-state tests and regression checks

Deliberately invalid occupied-category inputs must produce the expected
failure/status. Include zero-area and negligible-total-area cases as successful
inactive outcomes. Test the MPI failure path as well as the arithmetic routine.

Repeat the meaningful B4 unity/null controls and the B5-style restart comparison
with the new build. Check candidate and applied fields separately. Archive the
source revision, local diff, executable hashes, namelists, mapping parameters,
bin definitions, job logs and comparison output for every accepted result.

## 6. Acceptance and scope of the conclusion

| Gate | Current status |
|---|---|
| Controlled mathematical definition and test parameters | Agreed for B6; not global calibration |
| Python analytical reference, ten reported tests | PASS |
| Inherited Icepack representation and adapter verified | Pending |
| Production Fortran routine matches analytical fixtures | Pending |
| Candidate-only diagnostics preserve control dynamics | Pending |
| Spatial/halo and restart tests of the mapped coefficient | Pending |
| Uniform mapped-feedback cases match prescribed controls | Pending |
| Invalid/inactive inputs handled explicitly | Python evidence only; production checks pending |

B6 is complete when the production mapping and its adapter have passed these
checks in the controlled box environment. Passing B6 validates the implementation
of this candidate, not the proposition that floe size alone determines physical
tensile strength. It also does not explain or repair the inherited global FSD
normalisation departures.

After B6, combine the verified mapping with G0's restored global forcing control.
G1 is the global evolving-FSD diagnostic experiment with momentum feedback off,
using ERA5, ORAS and WHACS. Diagnose the occurrence and impact of invalid FSDs
before deciding whether the global candidate is fit for feedback. G2 then tests
feedback over short controlled periods before seasonal and ten-year experiments.
Snow-temperature optimisation and unrelated physics changes remain outside B6.

## 7. Results log for subsequent implementation

Append each result with the case/fixture name, source and executable provenance,
input convention, candidate and applied coefficients, expected answer, observed
answer, tolerance and pass/fail outcome. Keep diagnostic-only and feedback
results distinguishable. Record any change to the mapping contract before
running replacement tests.

The next concrete deliverable is the inherited-FSD interface audit and a tested
production calculation, followed by candidate diagnostics. CICE case-generation
and output-check commands should be added once those interfaces exist; no
unimplemented namelist switches should be presented as runnable instructions.
