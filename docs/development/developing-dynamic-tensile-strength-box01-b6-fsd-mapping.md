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

**B6.2's 67 production Fortran fixtures and the full CICE build have passed
according to the supplied run evidence. B6.3 is now PASS for the matched
candidate-only history test: 19 checker regressions, all 126 history files,
and exact decoded control comparison. B6.4's diagnostic-only continuation gate has now passed, including independent
restart IC mapping and exact continuous-versus-split comparison. The timing/halo
contract is specified below; controlled spatial and mapped-feedback validation
remain pending.**
The existing executable supports prescribed constant and box_band modes.
Changing floediam alone does not currently exercise this mapping.

The reference repository revision inspected for this plan is
8dc6aa64bac99651cc302ed08f6eb47812ec82b1. The B6.1 audit references are pinned below; the B6.2 addition is recorded separately.

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


### B6.1 audit results — 5 October 2026

**Source/interface audit complete at revision c7c8770055196406eccfb3f47e01ddceafdf4160. Runtime adapter validation
remains pending under B6.2–B6.5.** This audit does not diagnose the origin of
the inherited global normalisation errors and makes no physics changes.

#### Live state, indexing and weighting

The adapter input for one owned ocean T cell is:

~~~fortran
! Interface sketch; not implemented by this audit.
a(n)   = aicen(i,j,n,iblk)
f(k,n) = trcrn(i,j,nt_fsd+k-1,n,iblk)
D(k)   = 2.0_dbl_kind * floe_rad_c(k)
~~~

Obtain nt_fsd through icepack_query_tracer_indices(nt_fsd_out=nt_fsd);
obtain/check tr_fsd through the tracer-flag interface. Require tr_fsd before
reading this slice, validate nt_fsd:nt_fsd+nfsd-1 against the tracer extent, and
check ncat/nfsd and bound-array availability. Do not hardcode a tracer offset.
The descriptive nt_nfsd comment near the top of icepack_fsd.F90 is not the
actual interface name: executable code uses nt_fsd.

CICE allocates nfsd consecutive tracers when tr_fsd is enabled
([ice_init_column.F90:1998–2002](https://github.com/dpath2o/CICE_dyntens/blob/c7c8770055196406eccfb3f47e01ddceafdf4160/cicecore/shared/ice_init_column.F90#L1998-L2002)).
The FSD dependency is explicitly area-weighted, trcr_depend=0
([ice_init.F90:3174–3178](https://github.com/dpath2o/CICE_dyntens/blob/c7c8770055196406eccfb3f47e01ddceafdf4160/cicecore/cicedyn/general/ice_init.F90#L3174-L3178)).

The tracer is already an integrated bin fraction. Initialisation constructs
number distribution times representative floe area times radius-bin width,
then normalises the bin sum
([icepack_fsd.F90:325–340](https://github.com/dpath2o/CICE_dyntens/blob/c7c8770055196406eccfb3f47e01ddceafdf4160/icepack/columnphysics/icepack_fsd.F90#L325-L340)).
Therefore sum the selected f(k,n) directly. **Do not multiply by width or floe
area again, and do not divide by aicen to recover the live tracer.**
Weight categories once by aicen, and use sum(aicen) for the denominator.

#### Radius bounds and diameter conversion

The source defines radius lower/upper bounds in metres, arithmetic midpoint
radius floe_rad_c=(lower+upper)/2, and radius width upper-lower
([icepack_fsd.F90:192–206](https://github.com/dpath2o/CICE_dyntens/blob/c7c8770055196406eccfb3f47e01ddceafdf4160/icepack/columnphysics/icepack_fsd.F90#L192-L206)).
The mapped representative diameter is twice that midpoint radius.
The separately defined representative floe area is the midpoint of endpoint
areas; it is not the definition of the radius centre and must not replace it.

Supported source bin counts are 1, 12, 16 and 24; other counts abort during
bound initialisation
([icepack_fsd.F90:127–169](https://github.com/dpath2o/CICE_dyntens/blob/c7c8770055196406eccfb3f47e01ddceafdf4160/icepack/columnphysics/icepack_fsd.F90#L127-L169)).
For the 12-bin scheme, the following values were calculated from the source
bounds; classification uses unrounded values and D>300 m:

| Bin | Lower radius (m) | Upper radius (m) | Representative diameter (m) | Classification |
|---|---:|---:|---:|---|
| 1 | 0.066500 | 5.310308 | 5.376808 | small |
| 2 | 5.310308 | 14.286586 | 19.596895 | small |
| 3 | 14.286586 | 29.057669 | 43.344255 | small |
| 4 | 29.057669 | 52.412214 | 81.469882 | small |
| 5 | 52.412214 | 87.869141 | 140.281354 | small |
| 6 | 87.869141 | 139.518470 | 227.387610 | small |
| 7 | 139.518470 | 211.635752 | 351.154222 | large |
| 8 | 211.635752 | 308.037274 | 519.673026 | large |
| 9 | 308.037274 | 431.203059 | 739.240333 | large |
| 10 | 431.203059 | 581.277225 | 1012.480284 | large |
| 11 | 581.277225 | 755.141047 | 1336.418272 | large |
| 12 | 755.141047 | 945.812834 | 1700.953881 | large |

Bin 7 spans diameters 279.036940–423.271504 m. Its centre is above 300 m,
so the entire bin is classified large despite straddling the threshold.
This is the agreed centre-based approximation, not a resolved partial-bin
integral. A 12-bin adapter fixture can place small mass in bin 6 and large
mass in bin 7; the exact D=300 boundary test belongs in the standalone routine
because this bin grid has no centre at exactly 300 m.

The one-bin default spans radii 0.0665–300 m, giving representative diameter
300.0665 m. It would classify all normalised tracer mass as large at this
threshold. **It cannot exercise the desired small/large mixture test.**
Use a 12-bin, tr_fsd-enabled case for the eventual live adapter tests; preserve
the existing tr_fsd-disabled box controls. The synthetic two-bin unit driver
does not require changing Icepack's supported grids.

#### Restart and history are different representations

Restart routines write/read fsd001...fsdNNN directly from/to
trcrn(:,:,nt_fsd+k-1,:,:), with ncat and centre/scalar location on read
([ice_restart_column.F90:599–660](https://github.com/dpath2o/CICE_dyntens/blob/c7c8770055196406eccfb3f47e01ddceafdf4160/cicecore/shared/ice_restart_column.F90#L599-L660)).
There is no bin-width conversion in those FSD wrapper routines. With valid
occupied-category state, the appropriate restart check is sum_k fsd_k≈1.

By contrast, the history accumulation uses:

- afsd(k): sum_n[aicen(n)*f(k,n)] / floe_binwidth(k).
- afsdn(k,n): aicen(n)*f(k,n) / floe_binwidth(k).

See [ice_history_fsd.F90:459–471](https://github.com/dpath2o/CICE_dyntens/blob/c7c8770055196406eccfb3f47e01ddceafdf4160/cicecore/cicedyn/analysis/ice_history_fsd.F90#L459-L471) and
[ice_history_fsd.F90:491–505](https://github.com/dpath2o/CICE_dyntens/blob/c7c8770055196406eccfb3f47e01ddceafdf4160/cicecore/cicedyn/analysis/ice_history_fsd.F90#L491-L505).
These are radius-density diagnostics at accumulation, not the raw restart
fractions. For instantaneous unmasked data, reconstruct category fractions
from afsdn by multiplying by radius width and dividing by the corresponding
positive aicen. Do not use that inversion on averaged quantities and assume
it reconstructs the instantaneous mapping. Verify time_rep, units and masks
in actual output before an offline comparison. Width must remain in radius
coordinates unless the density itself is transformed to diameter coordinates.

Existing fsdrad is an area-weighted radius diagnostic
([ice_history_fsd.F90:418–433](https://github.com/dpath2o/CICE_dyntens/blob/c7c8770055196406eccfb3f47e01ddceafdf4160/cicecore/cicedyn/analysis/ice_history_fsd.F90#L418-L433)).
diam_ww is a number-weighted mean diameter
([ice_history_fsd.F90:380–394](https://github.com/dpath2o/CICE_dyntens/blob/c7c8770055196406eccfb3f47e01ddceafdf4160/cicecore/cicedyn/analysis/ice_history_fsd.F90#L380-L394)).
Neither mean determines the large-floe tail fraction uniquely; neither is a
substitute for summing the category FSD.

#### Initialisation and restart ordering

The standalone driver calls init_evp before initialising FSD bounds and before
init_state ([CICE_InitMod.F90:133–169](https://github.com/dpath2o/CICE_dyntens/blob/c7c8770055196406eccfb3f47e01ddceafdf4160/cicecore/drivers/standalone/cice/CICE_InitMod.F90#L133-L169)).
In the driver's init_restart routine, an enabled FSD is read from restart when requested (forced for
runtype=continue), otherwise init_fsd populates it
([CICE_InitMod.F90:426–434](https://github.com/dpath2o/CICE_dyntens/blob/c7c8770055196406eccfb3f47e01ddceafdf4160/cicecore/drivers/standalone/cice/CICE_InitMod.F90#L426-L434)).
The driver writes IC history later, at line 197.

Consequently, retain allocation/neutral defaults in init_evp, but initialise
the FSD-derived candidate **after init_restart returns and before IC history**.
The existing prescribed-g call inside init_evp must not simply be changed to
dereference the FSD. Recompute the candidate after restart restoration; do not
store it as an additional prognostic tracer. Disabled tr_fsd is “input
unavailable”, not an all-small distribution.

#### Update timing for the standalone driver

The inspected driver runs thermodynamics before wave fracture; fracture is
called only on even istep, with 2*dt, when tr_fsd and wave_spec are enabled.
It then loops over ndtd: horizontal dynamics/transport, ridging, update_state
([CICE_RunMod.F90:219–319](https://github.com/dpath2o/CICE_dyntens/blob/c7c8770055196406eccfb3f47e01ddceafdf4160/cicecore/drivers/standalone/cice/CICE_RunMod.F90#L219-L319)).
Inside step_dyn_horiz, EVP precedes horizontal transport
([ice_step_mod.F90:1313–1362](https://github.com/dpath2o/CICE_dyntens/blob/c7c8770055196406eccfb3f47e01ddceafdf4160/cicecore/cicedyn/general/ice_step_mod.F90#L1313-L1362)).

Use the current category areas/tracers immediately before each EVP call for the
future mapped coefficient, then hold that field fixed over the EVP subcycles.
For ndtd>1, recompute before each horizontal dynamics call: subsequent calls
see the preceding transport/ridging updates. With ndtd=1, this is once per
model timestep. On fracture timesteps it sees the just-updated fracture state;
on other timesteps no new wave fracture occurs in this driver.

This specifies a pre-dynamics candidate, not an end-of-timestep FSD diagnostic.
Record that sampling phase in history metadata. If an end-of-step diagnostic is
later needed for offline FSD comparisons, give it a separate definition rather
than overwriting the coefficient that was applied to momentum.

#### Cleanup and validity implications

icepack_cleanup_fsdn zeroes values below Icepack puny and normalises by the sum
when it exceeds puny, otherwise sets the distribution to zero
([icepack_fsd.F90:384–410](https://github.com/dpath2o/CICE_dyntens/blob/c7c8770055196406eccfb3f47e01ddceafdf4160/icepack/columnphysics/icepack_fsd.F90#L384-L410)).
Initial FSD setup invokes cleanup
([ice_init_column.F90:665–695](https://github.com/dpath2o/CICE_dyntens/blob/c7c8770055196406eccfb3f47e01ddceafdf4160/cicecore/shared/ice_init_column.F90#L665-L695)).
Wave fracture also invokes cleanup
([icepack_wavefracspec.F90:278–305](https://github.com/dpath2o/CICE_dyntens/blob/c7c8770055196406eccfb3f47e01ddceafdf4160/icepack/columnphysics/icepack_wavefracspec.F90#L278-L305) and
[icepack_wavefracspec.F90:552–553](https://github.com/dpath2o/CICE_dyntens/blob/c7c8770055196406eccfb3f47e01ddceafdf4160/icepack/columnphysics/icepack_wavefracspec.F90#L552-L553)).
The CICE wave wrapper explicitly documents retaining cleanup for cells skipped
by its cheap fracture eligibility checks
([ice_step_mod.F90:1030–1044](https://github.com/dpath2o/CICE_dyntens/blob/c7c8770055196406eccfb3f47e01ddceafdf4160/cicecore/cicedyn/general/ice_step_mod.F90#L1030-L1044)).

These existing operations do not justify assuming normalisation at every
adapter call. Validate the state actually sampled, and do not call cleanup from
the adapter: it would modify the control state and conceal invalid-input tests.
The B6 contract tolerance and inactive threshold are explicit mapping choices,
not claims that Icepack puny equals those values.

For NetCDF offline checks, decode fill/missing masks before numerical testing.
For the live adapter, use owned ocean cells and validate availability, finite
values, bounds and sums directly. Do not feed history fill sentinels into
the arithmetic routine. Preserve invalid/inactive distinctions in diagnostics.

#### B6.1 deliverable and remaining validation

The source contract is now established: category-area weights, integrated
fractions, queried tracer offset, radius-to-diameter conversion, native-bin
classification, and safe initialisation/update locations. No extra width
factor or hidden normalisation is required.

B6.2 must verify this with the production routine and adapter fixtures:
unequal category areas, bins 6/7 on the actual 12-bin grid, disabled-tracer
rejection, invalid occupied categories, zero-area handling, initialization
and restart reconstruction. The inherited global FSD departures remain an
observed separate issue; this source audit does not identify their cause.


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

#### B6.2 routine added — 5 October 2026

New source: `cicecore/cicedyn/dynamics/ice_dyntens_mapping.F90`.
It exports the pure `dyntens_map_fsd` routine with inputs
`area(ncat), fsd(nbin,ncat), diameter(nbin), threshold, gmin, ktens`.
It returns `large_fraction, g, ktens_eff, status`; all inputs are intent(in).
The kind uses selected_real_kind(13), matching this repository's Icepack double
precision definition, while keeping the arithmetic module independently compilable.
There are no calls from the model yet and no new namelist options.

Status codes are named public constants: 0 valid, 1 inactive, 2 bad shape,
3 bad parameter, 4 bad diameter, 5 bad area, 6 bad occupied FSD.
Invalid outputs remain -1; inactive outputs are fraction=-1, g=1 and
ktens_eff=ktens. The negative sentinel is internal, not a history fill value.
Callers must inspect status before using results. Integration must translate
undefined fractions into masked diagnostics and implement collective error handling.

The routine does not repair FSDs or alter live state. It validates sums to 1e-10,
uses A<=1e-12 for inactive cells, classifies diameter strictly above the threshold,
and clips only accepted roundoff excursions in the derived fraction.

The new `test_scripts/test_b6_fortran_mapping.py` compiles the production source
with `b6_mapping_driver.F90` and checks 67 analytical and invalid-input fixtures.
It does not replace the user's local Python contract file. Native 12-bin fixtures
use the B6.1 audited bounds, but are not a test of live tracer extraction.
Python syntax, fixture names and Fortran line lengths were checked locally.
No Fortran compiler was available in the editing environment; compilation and
runtime results must be recorded after running the following on Gadi.

~~~bash
cd /g/data/gv90/da1339/src/CICE_dyntens
git pull --ff-only origin dev
# Load the same Intel compiler environment used for your CICE builds first.
bash <<'BASH'
set -euo pipefail
stamp=$(date +%Y%m%d-%H%M%S)
log="/g/data/gv90/da1339/cice-dirs/runs/b6-mapping-${stamp}.log"
python3 test_scripts/test_b6_fortran_mapping.py \\
    --fc ifort --fflags '-O0 -g -check all -traceback' 2>&1 | tee "$log"
BASH
~~~

Use --fc ifx if that is the loaded Intel compiler. For GNU use
--fc gfortran --fflags '-O0 -g -Wall -Wextra -fcheck=all'.
Do not use fast-math flags: finite/NaN rejection is part of the contract.
The runner needs Python's standard library only, builds in a temporary directory,
and exits nonzero on compilation or comparison failure. No PBS/CICE submission
is needed for these small routine tests. A successful result verifies this routine,
not the adapter, diagnostics, MPI halos, restart reconstruction or feedback.

### B6.3 — add candidate diagnostics with feedback disabled

Implemented candidate diagnostics (matched-history runtime validation PASS; see acceptance record below):

| Diagnostic | Purpose | Units |
|---|---|---|
| dtens_flarge | Derived F_L on active, valid T cells | 1 |
| dtens_gcand | Candidate multiplier | 1 |
| ktens_cand | K_t times candidate g | 1 |
| dtens_status | Distinguish valid, inactive and invalid input | 1 |

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
The implemented namelist names and constraints are recorded below.

#### B6.3 implementation — 5 October 2026

The standalone driver now initializes candidates after init_restart, when the
FSD bounds and initialized/restarted tracers exist. EVP refreshes candidates
before its dynamics work. The adapter uses aicen, the queried nt_fsd slice of
trcrn, and twice floe_rad_c; it never changes those inputs.

New dynamics_nml options:

~~~fortran
! dpath2o: dyntens
! Diagnose live FSD without changing the momentum coefficient.
    use_dyntens_diagnostics = .true.
    dyntens_diameter_threshold = 300.0
    dyntens_g_min = 0.2
! dpath2o: dyntens
~~~

Keep use_dyntens=.false. and Ktens=0.2. Diagnostic mode rejects use_dyntens=T,
and is restricted to the tested C-grid standard_2d EVP / avg_zeta / ellipse /
revised_evp=F configuration. It requires tr_fsd=T. The switch defaults to false;
the old prescribed-g experiments retain their existing behaviour.

For a new 12-bin initial-state test, set nfsd=12 in grid_nml and tr_fsd=T,
restart_fsd=F in tracer_nml. Both the matched control and diagnostic case must
use the same FSD-enabled configuration, initial state, forcing and executable.
Do not compare against the older tr_fsd-disabled control to infer neutrality:
enabling FSD itself is a separate model change. Do not copy a global restart
into this box test. The live adapter reads evolving FSD; it does not impose the
synthetic analytical mixtures. Those controlled fixtures remain B6.5 work.

Candidate history fields are now implemented in icefields_nml. For example,
with daily means and hourly snapshots configured identically in both cases:

~~~fortran
! In setup_nml, for both cases:
    histfreq   = 'd','h','x','x','x'
    histfreq_n = 1,1,1,1,1
    hist_avg = .true.,.false.,.true.,.true.,.true.

! In icefields_nml, for both cases:
    f_dyntens_g = 'dh'
    f_ktens_eff = 'dh'

! In icefields_nml, diagnostic case only:
! dpath2o: dyntens
! Match these frequency letters to the configured streams.
    f_dyntens_large_fraction = 'dh'
    f_dyntens_g_candidate = 'dh'
    f_ktens_eff_candidate = 'dh'
    f_dyntens_mapping_status = 'dh'
! dpath2o: dyntens
~~~

These are entries for existing groups, not a complete ice_in. If retaining a
timestep stream ('1') instead of hourly ('h'), use 'd1' for the field selectors.
Do not request candidate fields in the control: keep their default 'x' and
use_dyntens_diagnostics=F. Requesting candidate fields with the switch off
aborts rather than writing misleading zeros.

All four fields have units 1. Candidates describe the state before the latest
EVP call in each model timestep; they remain fixed through the subcycles.
With ndtd>1, history samples the last such call, not an average of all dynamics
calls. Use ndtd=1 for the first matched test. IC fields use the initialized or
restored state, not atmospheric-forcing initialization.

Inactive cells have g_candidate=1 and ktens_eff_candidate=Ktens, with the
large fraction masked. On averaged streams, large fraction is masked if any
sample was inactive; candidate coefficients include the neutral inactive
samples. dyntens_mapping_status is 0 for valid active and 1 for inactive
snapshots; its time mean is the inactive sample fraction. It must not be read
as an averaged categorical error code. Invalid occupied inputs log the first
rank/block/local-i/local-j/status failure per rank, complete a global count
reduction, then abort collectively. They are never repaired or fed to momentum.

Candidate arrays have neutral defaults outside owned ocean cells. History
accumulates owned cells only, so no candidate halo exchange is required yet.
This does not establish the B6.4 feedback halo contract. No prognostic restart
fields were added. Only the standalone CICE initialization driver is wired;
other coupling drivers are outside this implementation's supported scope.

Validation available now:

~~~bash
cd /g/data/gv90/da1339/src/CICE_dyntens
git pull --ff-only origin dev
# First complete the B6.2 compiler-driven routine test above.
python3 test_scripts/test_b63_candidates.py -v

# After clean-building and running matched FSD-enabled cases:
python3 test_scripts/check_b63_candidates.py "$diagnostic_run" \
    --control "$control_run" --ktens 0.2 --gmin 0.2
~~~

The checker handles base and suffixed IC/stream variables, requires all candidate
fields and applied coefficient diagnostics, validates masks, bounds and mapping
identities, and checks applied g=1 and ktens_eff=Ktens. With --control it requires
matching history file/variable sets (excluding only the four candidate families)
and exact decoded values and masks. It does not compare file bytes, global
attributes or restart files; retain the existing restart comparison workflow.
It does not independently reconstruct pre-EVP FSD from end-step history.
Analytical native-bin fixtures and the later controlled inputs supply the
independent mapping checks.

Initial local verification consisted of a preprocessed Fortran 2008 syntax
parse and ten synthetic NetCDF checker tests. Subsequent user-supplied evidence
establishes the full build, 67 B6.2 compiler fixtures, 19 checker regressions,
and B6.3's IC/daily/instantaneous diagnostics and matched-control history
identity. Restart-file equality and mapped restart reproducibility are separate
checks and are not established by the B6.3 history checker.

The separate mapping module remains the development arrangement. It can later
move unchanged into ice_dyn_shared's contains section, using dbl_kind and
shared status constants, while ice_dyn_evp retains state adaptation and field
updates. That organisational option does not change the equations or fixtures;
no consortium approval is assumed.


### B6.4 — specify timing, halo and restart semantics

**Contract specified from source at dev revision
311e9a1b6a6c6a561c77b179a675bb5562334f86. This is a source audit and implementation
contract, not a mapped-feedback or restart runtime PASS.** No new namelist mode
or momentum change is introduced by this documentation update.

#### Timing and the state being sampled

| Phase | Required behaviour |
|---|---|
| init_evp | Keep allocation/neutral defaults; do not read uninitialized FSD |
| After init_restart, before IC history | Recompute from initialized/restored aicen and trcrn and initialized bin bounds |
| Each entry to EVP | Evaluate once from the current pre-EVP state |
| EVP subcycles | Hold the derived multiplier and effective coefficient fixed |
| Next horizontal dynamics call | Re-evaluate after preceding transport, ridging and update_state |
| History accumulation | Retain the latest pre-EVP sample; do not replace it with an end-step mapping |

The standalone driver executes thermodynamics and update_state, then wave
fracture on even istep when tr_fsd and wave_spec are enabled, then the ndtd
horizontal-dynamics/ridging/update_state loop
([CICE_RunMod.F90](https://github.com/dpath2o/CICE_dyntens/blob/311e9a1b6a6c6a561c77b179a675bb5562334f86/cicecore/drivers/standalone/cice/CICE_RunMod.F90#L219-L319)).
Inside step_dyn_horiz, EVP precedes transport
([ice_step_mod.F90](https://github.com/dpath2o/CICE_dyntens/blob/311e9a1b6a6c6a561c77b179a675bb5562334f86/cicecore/cicedyn/general/ice_step_mod.F90#L1313-L1365)).
Thus a fracture call's updated FSD is available to the next EVP in that same
model timestep. There is no fracture call on the intervening odd timesteps.
Use ndtd=1 first; with ndtd>1 this is once per horizontal dynamics call,
not once per full model timestep.

The implemented candidate call is at EVP entry, before the prescribed
coefficient update
([ice_dyn_evp.F90](https://github.com/dpath2o/CICE_dyntens/blob/311e9a1b6a6c6a561c77b179a675bb5562334f86/cicecore/cicedyn/dynamics/ice_dyn_evp.F90#L478-L482)).
The IC call is after init_restart
([CICE_InitMod.F90](https://github.com/dpath2o/CICE_dyntens/blob/311e9a1b6a6c6a561c77b179a675bb5562334f86/cicecore/drivers/standalone/cice/CICE_InitMod.F90#L184-L188)).

#### Owned cells, halos and physical boundaries

B6.3 maps owned ocean T cells only. Candidate arrays have neutral defaults
elsewhere and are not exchanged, because history reads owned cells and no
momentum stencil consumes them. This remains sufficient for diagnostic-only
mode. Do not infer mapped halo correctness from its history PASS.

For a future mapped-feedback path, use this order:

1. Evaluate and validate every owned ocean T cell.
2. Complete the existing global invalid-count reduction. Abort collectively
   before any coefficient exchange if an occupied input is invalid.
3. Initialize the applied multiplier array to one, then copy valid/inactive
   candidate values into owned ocean cells.
4. Exchange that applied scalar with ice_HaloUpdate, halo_info,
   field_loc_center, field_type_scalar and fillValue=1.
5. Derive ktens_effT=Ktens*dyntens_gT over the whole exchanged array, including
   halos, before any EVP stress calculation.

Inactive ocean cells and owned land use neutral g=1 and effective Ktens.
Unconnected physical ghost boundaries use the same neutral fill; internal
block/rank boundaries receive their neighbour's values, and periodic boundaries
follow the configured halo topology. Do not fill an internal boundary with a
local default or apply vector sign changes to g. F_L remains undefined for
inactive cells; the multiplier alone is the finite scalar needed by momentum.

The prescribed path already exchanges g before multiplying by Ktens
([ice_dyn_evp.F90](https://github.com/dpath2o/CICE_dyntens/blob/311e9a1b6a6c6a561c77b179a675bb5562334f86/cicecore/cicedyn/dynamics/ice_dyn_evp.F90#L143-L166)).
Its fillValue is dyntens_g_const. A mapped mode must use the neutral mapped
boundary policy above rather than inherit an unrelated prescribed constant.
The current update_dyntens_coefficients overwrites the applied field from the
prescribed configuration: a future mapped mode must select a distinct branch
there, otherwise a copied candidate would be overwritten.

Use global indices for controlled spatial inputs. The first spatial fixture
must put unlike coefficients across global columns 6/7, then compare one block,
two local blocks and two MPI ranks. Compare candidates, applied coefficients
and physical fields; require exact decoded values and masks for equivalent
layouts unless a numerical-policy change is explicitly documented.

#### Restart reconstruction and sampling alignment

Do not add g or F_L as prognostic restart tracers. Restore aicen, the raw FSD
tracers and the usual model state, initialize/check the same bin definitions,
then recompute the derived candidate before IC history. Mapping parameters,
source/build provenance, FSD restart settings and synthetic-input definitions
must be identical between continuous and split paths. A continuation must
restore FSD; it must not silently reinitialize it.

A restart contains end-step prognostic state, whereas the continuous run's
last stored candidate describes the earlier pre-EVP state. Consequently, a
restart IC candidate is a new evaluation of restored state and need not equal
the continuous run's last pre-EVP candidate at that timestamp. This phase
difference must be documented, not hidden by loosening tolerances.

For the two-day plus three-day test, compare matching physical restart state
at the split, verify the restart IC mapping independently from its restored
raw FSD, and compare candidate/applied/physical history at matching phases
after the first resumed EVP. Handle duplicate split-time IC output explicitly.
For daily means, use completed, aligned averaging intervals; do not compare a
partial restarted average with a full continuous average.

#### Next execution gates

| Gate | First evidence required |
|---|---|
| Live-FSD diagnostic continuation | Five-day continuous versus two-day plus three-day split; restored-FSD/IC checks and phase-aligned history comparison |
| Controlled spatial adapter | Native-bin small/large fixture across global columns 6/7; exact one-block/local-block/MPI agreement |
| Mapped momentum integration | Explicit mode selection, collective validation, scalar halo exchange and no prescribed-field overwrite |
| Feedback equivalence | B6.5 endpoint/equal-mixture cases versus independently prescribed g controls |

Keep feedback disabled for the first continuation test. Preserve accepted B6.3
outputs and use new cases/build directories when code changes become necessary.
The existing checker verifies neutrality against a matched control; it is not
a general continuous-versus-split comparator and must not be used to certify
restart coverage without a phase-aware comparison.

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

#### B6.5 reported Gadi results — 6 October 2026

Source of evidence: the user-supplied shell transcript from Gadi, with
`conda/analysis3-26.08`. All fourteen cases contain a model log with
`CICE COMPLETED SUCCESSFULLY`; the final continuation log is
`dt_b65_sp_b_m2/cice.runlog.261006-153202`. The other thirteen completion logs
are timestamped 261006-105654 through 261006-105723.

The six synthetic B6.5 checker regressions passed in 0.617 s. The actual matrix
analysis **FAILED**, with:

```text
FAIL: inactive interval has unmasked large fraction
```

| Case | Reported runtime analysis evidence |
|---|---|
| dt_b65_ctl_s1 | PASS line after coverage of 126 history files and five restart clocks |
| dt_b65_small_s1 | PASS analytical/neutrality; 126 history files and five restarts |
| dt_b65_large_s1 | PASS analytical/neutrality; 126 history files and five restarts |
| dt_b65_mix_s1 | PASS analytical/neutrality; 126 history files and five restarts |
| dt_b65_uneq_s1 | PASS analytical/neutrality; 126 history files and five restarts |
| dt_b65_dil_s1 | PASS analytical/neutrality; 126 history files and five restarts |
| dt_b65_zero_s1 | Next row in the checker order; inactive-fraction check failed before a case PASS line |
| Remaining spatial/control/split cases | Model completion reported, but matrix validation not reached |

The checked restart clocks are 2–6 January 2005 at steps 24, 48, 72, 96 and
120. The failing file, field/stream suffix, values and NetCDF fill metadata were
not included in the supplied transcript. Case attribution to the inactive
fixture follows the implementation's row order; it is not a file-level diagnosis.
`CICE_testing` now includes the history path and the offending fraction field/stream name
in fixture exceptions to locate the
first failure on a repeat analysis.

The history contract requires undefined large fractions to be masked whenever
any contributing sample is inactive. A negative internal sentinel or an unmasked
zero/fill-like number is not an acceptable substitute. Retain this check and
inspect the actual failing IC/daily/hourly record and its `_FillValue` before
attributing the failure to history output, decoding or the checker. No model
source fix or relaxed mask rule is implied by this results entry.

The leading FAIL line appears before the buffered PASS transcript because the
workflow captures stdout and emits the transcript on failure while the CLI writes
its failure message to stderr. It does not negate the earlier completed checks.

**Gate status:** the full B6.5 diagnostic shadow matrix remains FAIL/unresolved.
Spatial/decomposition/split-restart comparisons were not reached. B6.5-F mapped
feedback remains pending. Model completion and synthetic checker PASS do not
close these gates; retain `test_scripts`, `tools` and the accepted run archives.
The evidence paths generated by this command are
`validation_report/box/evidence/b65-validation.json`,
`validation_report/box/evidence/b65-analysis.txt`, and
`dt_b65_ctl_s1/b65-analysis.log`. Their actual contents/checksums have not been
supplied here. Keep the FAIL record with the run provenance.

#### B6.5 IC hourly masking correction — 6 October 2026

The repeat user-supplied analysis passed all six synthetic tests in 0.564 s and
again passed the six matrix rows through `dt_b65_dil_s1`. It then identified:

```text
FAIL: /g/data/gv90/da1339/cice-dirs/runs/dt_b65_zero_s1/history/iceh_ic.2005-01-01-00000.nc: inactive interval has unmasked large fraction: dtens_flarge_h
```

Source inspection identifies an IC history serialization defect. The candidate
accumulator stores undefined fractions as a negative sentinel. The regular
history conversion changes that sentinel to `spval_dbl` for the current stream.
During IC output, however, `nstrm=1` restricts conversion to the first stream,
while `ice_write_hist` writes all streams when `write_ic` is true. Consequently
the hourly IC fraction bypasses the sentinel-to-fill conversion. The transcript
identifies the unmasked field; its exact stored values and fill metadata have
not yet been supplied.

`ice_history.F90` now converts negative fraction accumulations for every enabled
nonprimary IC stream before serialization. It guards disabled field indices and
changes only those fraction copies. Existing ordinary-stream conversion,
candidate coefficients, applied coefficients, mapping and momentum are unchanged.
The checker still rejects unmasked inactive fractions. New regressions reject
the raw hourly sentinel, accept its masked replacement and guard the IC source
conversion before the writer. Python regressions pass locally; no Fortran
compiler is available in the editing environment. Full model compilation and
runtime validation must be performed on Gadi.

Preserve the failed cases, runs, executable hashes and evidence as a dated
archive. Prepare fresh B6.5 cases with the same canonical names after archiving,
rebuild each of the s1/s2/m2 control executables from the corrected source, and
use `distribute` to share that layout executable across its matched tests. Run
the thirteen initial cases first, then `stage` and run `dt_b65_sp_b_m2` from the
new `dt_b65_sp_a_m2` restart. Do not edit NetCDF evidence or reuse the old
continuation input. Analyse the complete fresh matrix and archive its results.
**The correction is not a runtime PASS:** B6.5 remains unresolved until this
matrix is validated; B6.5-F mapped-feedback equivalence remains pending, and
B6.6 jobs should wait.

#### B6.5 diagnostic matrix acceptance — 6 October 2026

**PASS for the diagnostic-only shadow-fixture matrix.** The latest user-supplied
Gadi transcript supersedes the unresolved masking outcome above. All fourteen
rows passed analytical/neutrality checks, including `dt_b65_zero_s1` with its
hourly IC fraction mask. The continuation completed in
`dt_b65_sp_b_m2/cice.runlog.261006-214427`.

| Coverage | Accepted evidence |
|---|---|
| Twelve five-day cases | 126 history files and five restart clocks/inventories per case |
| Two-day spatial segment, m2 | 51 history files; restarts at steps 24 and 48 |
| Three-day spatial continuation, m2 | 76 history files; restarts at steps 72, 96 and 120 |
| Uniform fixtures | All-small, all-large, equal mixture, unequal category area and dilution match analytical candidates |
| Inactive fixture | Masked undefined fraction and neutral candidates; IC/hourly masking failure resolved |
| Diagnostic neutrality | Exact decoded physical histories and restarts against corresponding layout controls; continuation IC has no same-phase physical control snapshot |
| Decomposition | Control and spatial histories/restarts agree between s1, s2 and m2; only history blkmask ownership values excluded |
| Spatial split continuation | 51 segment-one and 75 segment-two exact history pairs; matching restarts and unchanged staged input |

The continuation's extra IC file is validated analytically but excluded from
continuous history comparison because it represents restart initialization at a
different sampling phase. All applied coefficients remain in the physical
comparison; candidate fields remain in equivalent-layout/split comparisons.

The supplied build/distribution transcript records these SHA-256 executable
hashes, shared by every case within its layout:

| Layout | Executable SHA-256 |
|---|---|
| s1: one serial block | `11f45d2da012ff9d3872371fa602c1a3badfbba281bb34e63c974fd755697379` |
| s2: two local serial blocks | `a87b94b90b98d015725fb7bdca44697b2556ecd11b60018b50e50f6c565be448` |
| m2: two MPI ranks | `9e71b2fd4e88d4050f5bb2bf55a9be5644027aabfc6c67700dfab7c91ad595b1` |

The m2 build reports COMPILE SUCCESSFUL in `cice.bldlog.261006-161816`.
The thirteen initial submissions were jobs 180599370–180599382. The history
correction is repository commit `28a4a44be31b4343b39099462fcce06cb013ffb5`;
archive the actual per-case source revision/local diff, build logs, namelists,
launchers, hashes, restarts and full checker output. This acceptance is based on
the supplied transcript, not independent access to the Gadi files. Retain the
previous failed matrix archive alongside the accepted rerun.

```text
PASS B6.5 diagnostic shadow-fixture matrix: analytical, neutrality, decomposition, spatial continuation
B6.5-F mapped-feedback equivalence and B6.6 live invalid-state tests remain pending.
```

The evidence files are `validation_report/box/evidence/b65-validation.json`,
`validation_report/box/evidence/b65-analysis.txt` and
`dt_b65_ctl_s1/b65-analysis.log`. Preserve them with this accepted matrix.
B6.5-F has not been implemented/validated by this diagnostic-only result.
Neither applied mapped-momentum halo exchange nor the global FSD adapter is
certified by a shadow fixture. Keep `test_scripts` and `tools` until migration
of their remaining workflows/tests is separately complete.

### B6.6 — invalid-state tests and regression checks

Deliberately invalid occupied-category inputs must produce the expected
failure/status. Include zero-area and negligible-total-area cases as successful
inactive outcomes. Test the MPI failure path as well as the arithmetic routine.

Repeat the meaningful B4 unity/null controls and the B5-style restart comparison
with the new build. Check candidate and applied fields separately. Archive the
source revision, local diff, executable hashes, namelists, mapping parameters,
bin definitions, job logs and comparison output for every accepted result.

#### B6.6 restart-entry subset implemented — 6 October 2026

`CICE_testing/workflows/invalid_state.py` provides `InvalidStateWorkflow` and
`CICE_testing/scripts/b66_invalid_state_workflow.py` (`cice-test-invalid`).
This is a diagnostic-only **restart-entry subset** of B6.6, not completion of
all B6.6/B6 acceptance requirements. It can investigate the live failure path
following acceptance of the corrected B6.5 diagnostic matrix.

It creates fresh cases using `dt_b65_ctl_s1` and `dt_b65_ctl_m2`, reusing each
layout's existing executable, launcher and machine configuration. It first
requires a valid owned-ocean raw FSD source throughout the copied 3 January /
step 48 restart, accepting only the audited 12x12 or 14x14 extended-halo layout.
If that source check fails, stop and diagnose it rather than normalising it.

A selected occupied ocean cell in **global column 7** supplies one occupied
category for invalid-FSD tests; that column is in the second x block of the
6+6 decomposition. The actual task/block/local coordinates are read from the
model's status log, not assumed from rank numbering. Only a copied input restart
is edited. Accepted B6.5 inputs, outputs and executables are untouched.
All tests use `use_dyntens=F`, `use_dyntens_diagnostics=T`,
`dyntens_box_fixture='none'`, `restart_fsd=T` and a one-day continuation.

| Mode (each on s1 and m2) | Copied restart change | Required outcome |
|---|---|---|
| valid | None | One-day completion; independent restart IC mapping; exact physical continuity against B6.5 control |
| negative | One occupied fsd001 value = -0.1 | Logged mapping status 6 and explicit collective mapping abort; no successful completion/output restart |
| nonfinite | One occupied fsd001 value = NaN | Same expected status/abort; a generic floating-point or scheduler failure is not sufficient |
| bad_sum | All twelve bins in one occupied category = 0 | Same expected status/abort; no hidden repair |
| zero_area | All category areas/ice/snow volumes at selected cell scaled to zero; FSD bins zeroed | Inactive IC status 1, masked large fraction, neutral candidates and one-day completion |
| negligible_area | Areas/volumes scaled to total 5e-13; FSD bins zeroed | Same inactive IC outcome; later evolution is allowed and checked separately |

The valid case checks 26 histories (one IC, one daily and 24 hourly), one final
restart (4 January / step 72), 25 aligned non-IC physical history comparisons,
and exact decoded final restart equality. Its IC is reconstructed independently
from the raw restart. Inactive cases are not compared physically against the
unmodified control because their area/volume inputs differ. Successful cases
retain candidate/applied-field checks on all history files.

A malformed-input case must show the named collective abort and status 6 from
exactly one reporting task; the status log identifies the injected task. Cases
that complete, merely time out, or omit the expected reason fail the checker.
Archive PBS output/accounting and verify all jobs have left the queue before
analysis: the model-log check alone is not a general proof of absence of MPI
hangs. No runtime results for these new cases have been supplied yet.

**Still pending:** B6.5-F mapped feedback, explicit in-timestep invalid-input injection, and the complete
B4 unity/null and B5-style regression controls. The new evidence JSON names the
gate `B6.6-entry` and records these pending requirements; a PASS is only for this
restart-entry subset. Synthetic local tests of mutation isolation, area/volume
scaling and expected-abort recognition passed, but are not Gadi runtime evidence.

##### Prepare fresh B6.6-entry cases

No new model build is required for this Python-only restart perturbation
workflow. Use the existing B6.5 executables by layout. Preparation refuses
existing destination cases/runs and records source/executable/input hashes,
source revision/diff and copies of the namelist/launcher/environment.

```bash
(
set -euo pipefail
cd /g/data/gv90/da1339/src/CICE_dyntens
git pull --ff-only origin dev
load_modules
python -c 'import sys; assert sys.version_info >= (3, 10), "Activate Python 3.10+"'
runs=/g/data/gv90/da1339/cice-dirs/runs
python -m unittest discover -s CICE_testing/tests -p 'test_invalid_state.py' -v
python CICE_testing/scripts/b66_invalid_state_workflow.py prepare \
    --repo "$PWD" --runs "$runs"
)
```

Inspect the generated PBS project/queue/storage, resource counts and launchers.
The serial case must retain the serial layout executable; the m2 case must
retain its two-rank executable and launcher. Do not rebuild or copy one layout's
binary into the other.

##### Submit positive controls first

```bash
(
set -euo pipefail
cd /g/data/gv90/da1339/src/CICE_dyntens
for layout in s1 m2; do
    ( cd "dt_b66_valid_$layout"; qsub ./cice.run | tee b66-job-id.txt )
done
)
```

Wait for these two jobs to finish and confirm success before submitting the
perturbed cases. If a valid live-FSD continuation aborts, investigate the source
state/adapter and do not treat the negative cases as isolated tests.

```bash
(
set -euo pipefail
cd /g/data/gv90/da1339/src/CICE_dyntens
runs=/g/data/gv90/da1339/cice-dirs/runs
for layout in s1 m2; do
    rg -l 'CICE COMPLETED SUCCESSFULLY' "$runs/dt_b66_valid_$layout"/cice.runlog.*
done
for layout in s1 m2; do
    for mode in negative nonfinite bad_sum zero_area negligible_area; do
        ( cd "dt_b66_${mode}_${layout}"; qsub ./cice.run | tee b66-job-id.txt )
    done
done
)
```

The negative/nonfinite/bad_sum jobs are **expected to abort**. Do not apply a
success-marker loop to those cases. Retain their failure logs and PBS accounting.
Check `qstat -u da1339`; analyse only after every submitted job has finished.

##### Analyse the full restart-entry subset

```bash
(
set -euo pipefail
cd /g/data/gv90/da1339/src/CICE_dyntens
load_modules
runs=/g/data/gv90/da1339/cice-dirs/runs
python CICE_testing/scripts/b66_invalid_state_workflow.py analyse \
    --repo "$PWD" --runs "$runs" \
    --evidence validation_report/box/evidence \
    2>&1 | tee dt_b66_valid_s1/b66-entry-analysis.log
)
```

Archive `b66-entry-validation.json`, `b66-entry-analysis.txt`, the twelve
`b66-provenance/input.json` manifests, PBS logs/accounting and analysis output.
Do not mark the full B6.6 gate complete from this subset or discard B6.5 evidence.

## 6. Acceptance and scope of the conclusion

| Gate | Current status |
|---|---|
| Controlled mathematical definition and test parameters | Agreed for B6; not global calibration |
| Python analytical reference, ten reported tests | PASS |
| Inherited Icepack representation and adapter verified | Source audit complete (B6.1); runtime adapter tests pending |
| Production Fortran routine matches analytical fixtures | PASS: 67 user-reported compiler fixtures, absolute tolerance 1e-12 |
| Candidate-only diagnostics preserve control dynamics | PASS: 126 history files and exact decoded matched-control comparison |
| Live-FSD diagnostic restart continuity | PASS: independent restart IC mapping; 126 exact history pairs and five exact restart pairs |
| Controlled shadow-fixture spatial/decomposition/restart tests | PASS: B6.5 exact s1/s2/m2 and spatial continuation checks |
| Applied mapped-coefficient halo exchange | Pending mapped-feedback implementation |
| Uniform mapped-feedback cases match prescribed controls | Pending |
| Invalid/inactive inputs handled explicitly | PASS inactive shadow fixture and analytical routine; deliberate live/MPI failure tests pending |

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

B6.2 compiler fixtures and B6.3 matched-history evidence are now recorded as
PASS. The next work follows the B6.4 contract: phase-aligned diagnostic
continuation, controlled native-bin spatial inputs, and then mapped-feedback
integration/equivalence. Full B6 acceptance remains pending.


## B6.3 initialization-order correction — 5 October 2026

The first diagnostic run (job 180528071) aborted with mapping status 6 before
IC history. The candidate call had incorrectly been placed after init_state.
FSD initialization/read occurs later inside the standalone driver's init_restart,
including runtype=initial. The call is now after init_restart and before IC
history. The earlier B6.1 statement attributing FSD population to init_state
was incorrect and has been corrected above. No tolerance, mapping formula,
FSD state or momentum code changed.

User-supplied evidence before this correction: the full model built successfully;
all 67 production Fortran fixtures passed at absolute tolerance 1e-12; the
matched control completed with the expected history coverage. The diagnostic
run did not complete, so B6.3 has not passed. Rebuild and rerun both matched
cases with the same corrected executable, preserving the previous outputs.
A source-order regression check guards the call placement; runtime verification
on Gadi remains required.

## B6.3 history-name correction — 5 October 2026

After the initialization fix, job 180531265 reached IC history but aborted at
NetCDF variable definition. History metadata stores vname in 16 characters.
The original long candidate names lost their frequency suffixes on truncation,
creating duplicate names when daily and hourly fields shared the IC file.
The four output names are now short enough to preserve suffixes:

| Unchanged namelist selector | NetCDF base name |
|---|---|
| f_dyntens_large_fraction | dtens_flarge |
| f_dyntens_g_candidate | dtens_gcand |
| f_ktens_eff_candidate | ktens_cand |
| f_dyntens_mapping_status | dtens_status |

The Fortran array/index identifiers and namelist selectors remain unchanged.
The checker now expects these short names and their stream suffixes. A regression
test reads the Fortran field definitions and metadata name width, checks suffix
uniqueness, and defines the resulting names in NetCDF. No mapping or momentum
calculation changed. A full model rebuild and fresh matched runs are required;
B6.3 runtime acceptance remains pending.

## B6.3 IC ocean-domain checker correction — 5 October 2026

Both corrected model runs completed with expected history coverage. Five daily
files passed candidate validation and exact control comparison. The checker
then rejected the IC hourly candidate copy because it treated unmasked land
zeros as ocean values. User-supplied inspection showed 64 ocean cells in each
copy, all with g=0.32273816251731574, and 80 unmasked zero-valued non-ocean cells
only in dtens_gcand_h. There were no ocean bound violations in that inspection.

Candidate and applied-coefficient invariant checks now select ocean explicitly
from the box tmask: finite binary 0/1, with masked locations excluded. All ocean
coefficient/status values must be present and finite, including inactive ice
cells. Ocean bounds, equations and inactive-fraction masking remain enforced.
The exact control comparison remains unchanged across all stored unmasked
values and masks, including land. This is a checker-only correction; no rebuild
or model rerun is required.

Nineteen synthetic checker tests pass, including the observed IC land-zero
layout, rejection of ocean zeros and missing ocean values, missing/nonbinary
tmask rejection, and detection of control differences on land. Full 126-file
comparison remains pending; this partial result is not a B6.3 acceptance PASS.

## B6.3 matched-history acceptance — 5 October 2026

**PASS for candidate-only history validation and matched-control trajectory
identity over the supplied five-day box run.** The final user-supplied transcript
reports:

~~~
Ran 19 tests in 0.227s

OK
PASS B6.3 candidate history: 126 files
PASS exact decoded control history comparison (candidate diagnostics excluded)
~~~

Coverage is five daily files (1–5 January 2005), one IC file at 1 January
00:00 and 120 hourly instantaneous files from 1 January 01:00 through
6 January 00:00. All 126 files passed candidate validation. The comparison
excludes only the four candidate diagnostic families; applied coefficients and
all remaining decoded history values/masks, including stored land values,
remain part of the exact control comparison.

The 19 regressions cover mapping identities, validity/masks, stream names and
suffixes, inactive cells, ocean-domain enforcement, feedback rejection and
control differences including land. The earlier IC land-zero rejection was a
checker-domain error, resolved without changing the model mapping or momentum.

The inspected repository checker revision is
311e9a1b6a6c6a561c77b179a675bb5562334f86; this is not a claim that the supplied
transcript independently identifies the local source SHA or executable hash.
Archive the actual source revision/local diff, executable hash, both namelists,
job logs and full checker output with the accepted cases. Those provenance
values are not present in this final transcript and must not be invented.

This closes B6.3's matched-history gate. It does not compare restart files,
independently reconstruct evolving pre-EVP FSD from end-step history, establish
native-bin synthetic-fixture answers, verify mapped halos/feedback, or calibrate
the closure. Earlier failure/pending entries above are historical records;
this final acceptance entry supersedes their B6.3 history-gate status.

## B6.4 Bash workflow — diagnostic-only continuation

The helper `test_scripts/b64_restart_workflow.py` prepares new cases from the
accepted B6.3 diagnostic case, copies its executable without rebuilding, stages
the split restart and checks the complete expected inventory. It retains the
accepted layout and launcher; this is a continuation gate, not a new MPI/halo
test. Preparation refuses existing destinations and requires the accepted
12-bin daily/hourly five-day configuration.

Eight synthetic regression tests pass locally. They cover complete phase-aligned
comparison, missing output, physical/candidate differences, wrong restart clocks,
changed staging, wrong IC mapping and safe staging. These tests do not establish
a Gadi run PASS.

### Prepare and submit the initial runs

Run from Bash. Load the usual analysis environment providing numpy/netCDF4.
No compiler build is needed because only setup and checking are added.

~~~bash
(
set -euo pipefail
cd /g/data/gv90/da1339/src/CICE_dyntens
git pull --ff-only origin dev
load_modules
python3 test_scripts/test_b64_restart_workflow.py -v
python3 test_scripts/b64_restart_workflow.py prepare

# Auto-detection requires exactly one dt_b63* diagnostic case.
# If ambiguous, repeat prepare with --base-case /absolute/path/to/accepted/case.

for name in dt_b64_cont dt_b64_seg1 dt_b64_seg2; do
    echo "$name"
    rg '^#PBS|mpirun|^\\./cice|ICE_NTASKS|ICE_NTHRDS' "$name/cice.run" "$name/cice.settings"
done
)
~~~

Inspect the copied PBS header/launcher for the accepted rank count, working
queue/storage and new case paths. Then submit the five-day continuous path and
two-day initial segment:

~~~bash
(
set -euo pipefail
cd /g/data/gv90/da1339/src/CICE_dyntens
for name in dt_b64_cont dt_b64_seg1; do
    ( cd "$name"; qsub ./cice.run | tee b64-job-id.txt )
done
)
~~~

These submissions are asynchronous. Wait for both to finish. Confirm
CICE COMPLETED SUCCESSFULLY in each run log; the helper checks the dates,
step counts, FSD and complete output inventories during analysis.

### Stage and submit the three-day continuation

Do this only after segment 1 completes:

~~~bash
(
set -euo pipefail
cd /g/data/gv90/da1339/src/CICE_dyntens
load_modules
runs=/g/data/gv90/da1339/cice-dirs/runs
rg -l 'CICE COMPLETED SUCCESSFULLY' "$runs/dt_b64_seg1"/cice.runlog.*
python3 test_scripts/b64_restart_workflow.py stage
( cd dt_b64_seg2; qsub ./cice.run | tee b64-job-id.txt )
)
~~~

Staging requires 3 January 2005 00:00 / step 48 and all twelve raw fsd bins.
The staged copy is verified by SHA-256 and its absolute path is written to
the continuation run's ice.restart_file. The continuation namelist uses
runtype=continue, use_restart_time=T, restart_fsd=T and npt=3 days.

### Analyse after all three jobs finish

~~~bash
(
set -euo pipefail
cd /g/data/gv90/da1339/src/CICE_dyntens
load_modules
runs=/g/data/gv90/da1339/cice-dirs/runs
for name in dt_b64_cont dt_b64_seg1 dt_b64_seg2; do
    rg -l 'CICE COMPLETED SUCCESSFULLY' "$runs/$name"/cice.runlog.*
done
python3 test_scripts/b64_restart_workflow.py analyse \
    2>&1 | tee dt_b64_cont/b64-analysis.log
)
~~~

Expected history inventories are 126 continuous, 51 segment-1 and 76
segment-2 files. Candidate/applied invariants are checked in all of them,
including the continuation IC. The independent IC reconstruction uses restart
aicen and raw fsd001–fsd012, selecting audited native bins 7–12 for D>300 m.
It validates occupied-bin normalization and ignores empty categories; it does
not renormalize invalid input.

Exact comparison includes every decoded field and mask, including all candidate
diagnostics and land values. No blkmask exception is needed for an unchanged
layout. Variable units/calendar/bounds/time_rep are also compared. Pre-split
comparison covers 51 histories plus two restarts; post-split comparison covers
75 histories plus three restarts. Only the extra continuation IC is outside
that comparison and is instead checked against restored FSD, at mapping
absolute tolerance 1e-10. All equivalent-path comparisons use zero tolerance.

A final PASS establishes this diagnostic-only continuation gate. It does not
close controlled native-bin spatial, mapped momentum, halo or feedback gates.
Preserve the three runs, b64-provenance directories, job logs and analysis output.

## B6.4 restart_ext IC reconstruction correction — 5 October 2026

The supplied first analysis confirms matching executable SHA-256
4c86d2a6af83d57ffdfc6f0c5e473f7f8382e77b989f28b0e0689fec7ffd421f,
candidate/applied history PASS for 126/51/76 files, and all expected restart
dates/counters through 6 January / step 120. The continuation job
180538921 completed successfully. Analysis stopped at the independent IC
reconstruction because the checker incorrectly required identical restart
and history horizontal shapes. The printed dimension names were correct;
the old error message omitted the shapes that actually failed.

CICE's NetCDF restart writer uses nx_global+2*nghost and ny_global+2*nghost
when restart_ext=T (ice_restart.F90, init_restart_write). The audited
ice_blocks.F90 declares nghost=1. gather_global_ext offsets global i/j by
nghost; thus the matching global interior is [1:-1,1:-1] in Python.
The IC reconstruction now accepts either identical global shapes or exactly
one extra halo cell on each restart edge, applying the same interior selection
to aicen and all raw fsd bins. Unexpected shapes remain errors and are printed
explicitly. This is not an arbitrary crop to force matching dimensions.

All eleven synthetic workflow tests pass, including extended restart alignment,
rejection of invalid occupied ocean FSD after alignment, and rejection of
unsupported shape differences. No mapping tolerance changed. Exact split-run
restart comparisons still include every stored cell, including extended halos.
This is a checker-only correction: rerun analysis on the completed cases;
no preparation, rebuild, staging or model submission is required.
Full B6.4 continuation acceptance remains pending the final comparison output.

## B6.4 diagnostic-only continuation acceptance — 5 October 2026

**PASS for the five-day continuous versus two-day plus three-day live-FSD
diagnostic-only continuation gate.** This is user-supplied Gadi execution and
analysis evidence. It does not complete B6's controlled spatial or mapped-feedback
tests.

| Check | Supplied result |
|---|---|
| Workflow regression tests | 11 tests in 44.845 s; OK |
| Continuous candidate/applied history | 126 files PASS |
| Segment-1 candidate/applied history | 51 files PASS |
| Segment-2 candidate/applied history, including restart IC | 76 files PASS |
| Restart clocks and twelve-bin FSD inventories | All expected daily restarts PASS |
| Split clock | 3 January 2005, 00:00, step 48 |
| Final clock | 6 January 2005, 00:00, step 120 |
| Extended restart alignment | 14×14 restart interior aligned with 12×12 history |
| Restart IC candidate from restored raw FSD | PASS at mapping absolute tolerance 1e-10 |
| Segment 1 versus continuous | 51 history pairs and two restart pairs, exact |
| Segment 2 versus continuous | 75 history pairs and three restart pairs, exact |

All three executables have the supplied SHA-256:

~~~
4c86d2a6af83d57ffdfc6f0c5e473f7f8382e77b989f28b0e0689fec7ffd421f
~~~

The final checker summary is:

~~~
PASS restart IC candidate independently reconstructed from raw FSD (atol=1e-10)
PASS exact comparison dt_b64_seg1 51 histories + 2 restarts
PASS exact comparison dt_b64_seg2 75 histories + 3 restarts
PASS B6.4 diagnostic-only continuation: 126 history pairs and 5 restart pairs; atol=rtol=0
Restart IC checked independently; mapped-feedback/halo validation remains pending.
~~~

Exact comparisons include candidates, applied coefficients, physical fields,
stored values and masks, and the full restart arrays including halos.
The continuation's additional IC is validated independently from restored
aicen/raw FSD at the correct phase. It is not compared with the continuous
path's earlier pre-EVP diagnostic at the same timestamp. Candidate mapping
tolerance and exact-path comparison policy were not relaxed.

The checked helper is available at repository revision
33576d89cb1b01883bba46dc91fdb796e7b19985. The supplied output establishes
executable equality but does not independently print its build source revision
or compiler provenance; retain the b64-provenance directories with the outputs.
The earlier restart_ext failure is resolved as a checker layout error.

Next: B6.5 controlled native-bin fixtures and spatial adapter tests across global
columns 6/7 and equivalent decompositions, followed by mapped-feedback
integration and independently prescribed-coefficient equivalence. This accepted
diagnostic path supplies no FSD-derived coefficient to momentum, so its PASS
cannot establish the future mapped halo or feedback path.

## B6.5 diagnostic shadow-fixture implementation and Bash workflow

Added 5 October 2026. **Implementation and local syntax/checker tests are complete;
Gadi runtime evidence is now partially reported above: all jobs completed, but
the matrix failed the inactive-fraction mask check. B6.5-F feedback
equivalence remains a separate implementation/run gate.**

An explicit dynamics_nml option, dyntens_box_fixture, supplies controlled
diagnostic inputs: none (default live adapter), small, large, mixed, unequal,
dilute, inactive or spatial. These are **shadow category areas/FSD arrays** passed
to the existing production mapping routine with the actual native
2*floe_rad_c diameters. They do not overwrite aicen, trcrn, FSD restart fields or
any prognostic state. The fixture's status/large-fraction fields describe the
synthetic input rather than the model's evolving ice. This controlled replay
tests native-bin mapping and global indexing; it is not an evolving-tracer
perturbation experiment or proof of a physical closure.

The option is restricted to diagnostics=T, feedback=F, rectangular box_tensile,
12x12, nfsd=12, ncat>=2, threshold=300, g_min=0.2, Ktens=0.2 and the previously
supported EVP configuration. Configuration is MPI-broadcast and the selected
fixture is printed in the startup log. Invalid names/configurations abort.
The default none branch retains the live-FSD adapter used in B6.3/B6.4.

Fixture arrays are reconstructed at initialization and every pre-EVP call;
the spatial input uses global column indices, never rank-local i. Coefficients
are held fixed through EVP subcycles. No new prognostic restart variable or
candidate halo exchange is introduced.

| Fixture | Synthetic inputs | Expected F_L | Expected g | Expected Ktens candidate |
|---|---|---:|---:|---:|
| small | area 0.9, native bin 6 | 0 | 0.2 | 0.04 |
| large | area 0.9, native bin 7 | 1 | 1 | 0.2 |
| mixed | area 0.9, half in bins 6 and 7 | 0.5 | 0.6 | 0.12 |
| unequal | areas 0.3/0.6, bins 6/7 respectively | 2/3 | 11/15 | 11/75 |
| dilute | areas 0.1/0.2, same fractions | 2/3 | 11/15 | 11/75 |
| inactive | zero areas | masked | 1 | 0.2 |
| spatial | bin 6 at global column 6; bin 7 elsewhere | 0 at column 6, 1 elsewhere | 0.2 at column 6, 1 elsewhere | 0.04 at column 6, 0.2 elsewhere |

Native bin 6 is below the 300 m diameter threshold; bin 7 is above it.
The exact D=300 boundary remains a standalone analytical routine test in the
B6.2 suite, since the native grid has no representative diameter exactly there.

### Create new cases

Use the usual model-build shell. No accepted B6.3/B6.4 directory is modified.
The prepare helper requires fresh destinations. It invokes cice.setup, preserves
each generated domain_nml and launcher, copies the accepted machine environment/
macros and physics, and sets the explicit fixture option. Its --base-case is
the original case directory under src/CICE_dyntens, not a run directory.

~~~bash
(
set -euo pipefail
cd /g/data/gv90/da1339/src/CICE_dyntens
git pull --ff-only origin dev
python3 test_scripts/b65_box_workflow.py prepare \
    --base-case /g/data/gv90/da1339/src/CICE_dyntens/dt_b63_diag
)
~~~

There are fourteen cases: three controls (ctl_s1, ctl_s2, ctl_m2), six uniform
analytical cases on s1, three spatial cases (sp_s1, sp_s2, sp_m2), and
sp_a_m2/sp_b_m2 split segments. All names have the dt_b65_ prefix.
Layouts are 1x1x12x12x1, 1x1x6x12x2 and 2x1x6x12x1 respectively.
Full runs use five days; split segments use two and three days.

### Compiler checks, builds and executable distribution

Run the routine tests in the generated case's actual compiler environment:

~~~bash
(
set -euo pipefail
cd /g/data/gv90/da1339/src/CICE_dyntens
csh -f <<'CSH'
source /etc/profile.d/modules.csh
cd dt_b65_ctl_s1
source ./cice.settings
source ./env.gadi1_intel
cd ..
python3 test_scripts/test_b6_fortran_mapping.py --fc ifort --fflags '-O0 -g -check all -traceback'
if ($status != 0) exit 1
python3 test_scripts/test_b65_fortran_fixtures.py --fc ifort --fflags '-O0 -g -check all -traceback'
if ($status != 0) exit 1
CSH

for layout in s1 s2 m2; do
    (
        cd "dt_b65_ctl_$layout"
        ./cice.build > build.b65.log 2>&1
    )
done
python3 test_scripts/b65_box_workflow.py distribute
)
~~~

Use ifx in both compiler commands if that is the loaded compiler. Do not use
fast-math flags. The new compiler check derives native bin diameters from the
Icepack source, tests 84 mode/column answers and three invalid fixture guards.
Each layout gets one fresh executable; distribute copies it to every matching
case and records hashes. Full model compilation is required because the fixture
adapter/namelist source has changed.

Before submission inspect PBS queue/project/storage, rank count, new case paths
and the generated MPI launcher. The helper sets 1/2 CPUs, 9 GB and 30 minutes;
it retains the generator's queue, storage and launcher. Do not copy a serial
launcher or executable into an MPI case.

### Submit the full matrix and first split segment

~~~bash
(
set -euo pipefail
cd /g/data/gv90/da1339/src/CICE_dyntens

cases=(
dt_b65_ctl_s1 dt_b65_small_s1 dt_b65_large_s1
dt_b65_mix_s1 dt_b65_uneq_s1 dt_b65_dil_s1 dt_b65_zero_s1
dt_b65_sp_s1 dt_b65_ctl_s2 dt_b65_sp_s2
dt_b65_ctl_m2 dt_b65_sp_m2 dt_b65_sp_a_m2
)
for name in "${cases[@]}"; do
    ( cd "$name"; qsub ./cice.run | tee b65-job-id.txt )
done
)
~~~

Wait for completion. Confirm each model log says CICE COMPLETED SUCCESSFULLY.

### Stage and submit the spatial continuation

~~~bash
(
set -euo pipefail
cd /g/data/gv90/da1339/src/CICE_dyntens
load_modules
runs=/g/data/gv90/da1339/cice-dirs/runs
rg -l 'CICE COMPLETED SUCCESSFULLY' "$runs/dt_b65_sp_a_m2"/cice.runlog.*
python3 test_scripts/b65_box_workflow.py stage
( cd dt_b65_sp_b_m2; qsub ./cice.run | tee b65-job-id.txt )
)
~~~

This checks the 3 January / step 48 clock, stages a checksum-identical spatial
restart and writes its pointer. The deterministic shadow fixture is reconstructed
from the continuation namelist/global index, without modifying restored FSD.

### Analyse after all fourteen jobs finish

~~~bash
(
set -euo pipefail
cd /g/data/gv90/da1339/src/CICE_dyntens
load_modules
runs=/g/data/gv90/da1339/cice-dirs/runs
for name in dt_b65_ctl_s1 dt_b65_small_s1 dt_b65_large_s1 \
            dt_b65_mix_s1 dt_b65_uneq_s1 dt_b65_dil_s1 dt_b65_zero_s1 \
            dt_b65_sp_s1 dt_b65_ctl_s2 dt_b65_sp_s2 \
            dt_b65_ctl_m2 dt_b65_sp_m2 dt_b65_sp_a_m2 dt_b65_sp_b_m2; do
    rg -l 'CICE COMPLETED SUCCESSFULLY' "$runs/$name"/cice.runlog.*
done
python3 test_scripts/test_b65_box_workflow.py -v
python3 test_scripts/b65_box_workflow.py analyse \
    2>&1 | tee dt_b65_ctl_s1/b65-analysis.log
)
~~~

The checker requires complete 126-file full histories and five daily restarts,
51-file/two-restart segment 1 and 76-file/three-restart segment 2.
Every candidate IC/daily/hourly family must match the independent table at
absolute tolerance 1e-10, including inactive masking. Applied g=1/Ktens=0.2
remains required.

Against each layout's control, only the four candidate history families are
excluded; other decoded values/masks and all restart fields match exactly.
Across equivalent decompositions, candidates and physical fields match exactly;
only history blkmask ownership values are exempted, retaining dimensions,
masks and finiteness checks. Full restart equality includes extended halos.

Spatial split/continuous comparison covers 51+75 history pairs and two+three
restart pairs exactly. The extra continuation IC is checked against the
analytical spatial fixture at initialization, since that fixture is explicitly
reconstructed rather than inferred from the evolving prognostic FSD.

Local verification: four preprocessed Fortran files passed an F2008 syntax
parse; six synthetic checker regressions passed. The compiler-driven fixture
test and full CICE build/runtime tests must be run on Gadi. No runtime PASS is
claimed by this implementation entry.

Passing this matrix closes the implemented **diagnostic shadow-fixture**
analytical/spatial/restart gates. It does not establish raw-tracer perturbation
fixtures, mapped coefficient halo exchange or B6.5-F momentum feedback
equivalence. Implement that explicit mapped mode after this matrix passes,
then compare endpoints/equal mixtures against independently prescribed controls.
