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

**The Python mapping contract has passed all 10 reported tests. A standalone
Fortran mapping routine and compiler-driven analytical tests have now been added.
The live candidate-only adapter and history wiring have now been added under B6.3.
Full CICE compilation and runtime validation remain pending.**
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

Implemented candidate diagnostics (runtime validation pending):

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

Local verification: all changed Fortran files passed a preprocessed Fortran
2008 syntax parse; ten synthetic NetCDF checker tests passed. These checks
are not a CICE compilation or a Gadi integration run. No B6.3 runtime PASS is
claimed. B6.2 compiler results, clean CICE build, IC/daily/instantaneous
diagnostics, matched-control trajectory identity and restart verification
remain to be supplied from the actual runs.

The separate mapping module remains the development arrangement. It can later
move unchanged into ice_dyn_shared's contains section, using dbl_kind and
shared status constants, while ice_dyn_evp retains state adaptation and field
updates. That organisational option does not change the equations or fixtures;
no consortium approval is assumed.


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
| Inherited Icepack representation and adapter verified | Source audit complete (B6.1); runtime adapter tests pending |
| Production Fortran routine matches analytical fixtures | Pending |
| Candidate-only diagnostics preserve control dynamics | Adapter/history implemented; matched-run evidence pending |
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

The next concrete evidence is the B6.2 compiler-run output and a clean B6.3
matched control/diagnostic run. The implemented candidate path must pass before
moving to the controlled spatial, restart and feedback stages.


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
