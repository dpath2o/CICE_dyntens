# CICE_dyntens

Development of FSD-dependent dynamic tensile strength in standalone CICE6, derived from [CICE_forcing](https://github.com/dpath2o/CICE_forcing).

The aim is to test whether an evolving floe size distribution (FSD) can provide a physically interpretable control on effective tensile cohesion and Antarctic landfast sea-ice stability. We retain the inherited free-slip, grounded-iceberg and lateral-drag framework, and introduce a local tensile-strength coefficient that responds to floe fragmentation and subsequent FSD evolution.

**Status:** this README defines the development plan. It does not announce an implemented or validated dynamic tensile-strength capability. Inherited forcing and FSD routines must be audited in the selected configuration before coupled experiments begin.

## Why develop dynamic tensile strength?

A prescribed tensile-strength coefficient does not, by itself, distinguish coherent ice from a fragmented floe field. Wave-induced fracture can change the FSD without an explicit corresponding reduction in the tensile cohesion used by the continuum momentum solver.

The hypothesis to test is:

> Wave-driven changes in floe size can act as a proxy for changes in grid-scale ice cohesion, allowing fragmentation to weaken effective tensile resistance and influence fast-ice breakup and persistence.

Large floes do not necessarily imply a connected ice cover, and small floes do not uniquely determine its mechanical strength. FSD-dependent cohesion is therefore a parameterisation to evaluate, not an established constitutive law. It represents the effective behaviour of the ice cover at model resolution, rather than the material tensile strength of an individual floe.

The intended feedback is wave forcing → fracture → FSD evolution → effective tensile cohesion → ice motion and fast-ice stability. Recovery must also be examined: the selected FSD processes may not represent welding or reconnection adequately, so increasing floe size must not automatically be interpreted as demonstrated recovery of connectivity.

## Proposed formulation

Retain the baseline compressive-strength formulation and define

$$
T_{\mathrm{eff}} = k_{T,\mathrm{eff}}P,
\qquad
k_{T,\mathrm{eff}} = k_{T,0}\,g(\mathrm{FSD}),
$$

where:

| Quantity | Meaning |
|---|---|
| $P$ | Baseline ice-strength scale supplied to the rheology |
| $k_{T,0}$ | Prescribed reference tensile-strength coefficient, corresponding to the existing `Ktens` parameter |
| $g$ | Dimensionless cohesion factor, bounded by $g_{\min}\leq g\leq1$ |
| $g_{\min}$ | Lower bound, with $0\leq g_{\min}\leq1$ |
| $T_{\mathrm{eff}}$ | Effective tensile-strength scale |

The reference state has $g=1$. Fragmentation can reduce $g$ towards its lower bound. The development must preserve the existing yield-curve convention and apply the effective coefficient consistently wherever tensile strength enters the active solver.

### First FSD-based candidate: large-floe area fraction

A simple candidate is

$$
g = g_{\min}+(1-g_{\min})F_L.
$$

For a thickness-category FSD, define the ice-area-weighted large-floe fraction as

$$
F_L =
\frac{\displaystyle\sum_n a_n
      \displaystyle\sum_{k:D_k>D_*}f_{k,n}}
     {\displaystyle\sum_n a_n}.
$$

Here $a_n$ is the grid-cell ice-area fraction in thickness category $n$, $f_{k,n}$ is the fraction of that category's ice area in floe bin $k$, and $D_*$ is the selected large-floe diameter threshold. For valid ice-covered categories, $\sum_k f_{k,n}=1$. This definition gives $0\leq F_L\leq1$ and avoids treating open water as fragmented ice.

Before implementation, verify tracer normalisation, category weighting, bin integration and radius-versus-diameter conventions in the inherited Icepack code. A centre-based bin threshold is a first approximation; sensitivity to the threshold and FSD resolution must be documented.

This is a candidate closure. Neither $D_*$, $g_{\min}$, nor revised reference rheology parameters are fixed by this README. An effective-diameter formulation may also be evaluated, but area- and number-weighted means must be distinguished explicitly.

## Scope and scientific control

- Preserve the inherited Cs-high/Hibler control configuration, free-slip boundary treatment, grounded-iceberg representation and lateral drag.
- Retain the ERA5, tidal, ocean/mixed-layer and spectral-wave infrastructure inherited from `CICE_forcing`; record which pathways are actually active in each experiment.
- Keep baseline rheology and external forcing fixed while isolating the new cohesion feedback.
- Make dynamic tensile strength optional. With the option disabled, retain the original constant-`Ktens` calculation.
- Start with a prescribed floe-diameter test before connecting the full evolving FSD.
- Reuse and verify the inherited wave-fracture/FSD machinery before extending it.
- Defer wave-radiation stress, two-way coupling to a wave model, and additional damage/healing laws. These introduce separate physical questions.

Changing $k_{T,0}$, ellipse ratio or compressive-strength parameters belongs in a subsequent, separately attributed sensitivity study.

## Development stages

| Stage | Work | Required evidence before proceeding |
|---|---|---|
| 0. Establish the control | Record source commit, compiler, grid, namelist, forcing, restart and active physics; audit wave/FSD interfaces | Reproducible short baseline run |
| 1. Introduce the local coefficient | Add an optional cohesion field and thread `Ktens_eff` through the active rheology; initially prescribe $g$ | Disabled mode reproduces the original path; $g=1$ recovers baseline behaviour |
| 2. Prescribed floe diameter | Use a controlled diameter input and a documented bounded mapping to $g$ | Monotonic response, correct limits and finite stresses across the tested range |
| 3. Diagnose evolving FSD | Calculate ice-area-weighted FSD metrics and $g$, without feeding them back into momentum | Verified weighting, masks, bounds and temporal ordering |
| 4. Activate FSD feedback | Supply the diagnosed coefficient to the momentum solver | Stable short runs; consistent stress terms; successful restart and decomposition checks |
| 5. Evaluate fast-ice response | Run controlled seasonal experiments and selected sensitivities | Attributable changes in breakup, persistence and dynamics, with numerical checks satisfied |

Each stage should be a small, reviewable change. Long integrations follow successful short tests, not the introduction of a new option.

## Initial code map

These are inspection and integration targets, not a claim that the required interfaces are complete.

| Location | Development responsibility |
|---|---|
| [`ice_dyn_shared.F90`](cicecore/cicedyn/dynamics/ice_dyn_shared.F90) | Shared rheology: currently declares `Ktens` and uses it in viscosity and replacement-pressure expressions |
| [`ice_dyn_evp.F90`](cicecore/cicedyn/dynamics/ice_dyn_evp.F90) | EVP solver: includes an additional `Ktens`-dependent pressure expression that must remain consistent |
| [Dynamics directory](cicecore/cicedyn/dynamics) | Audit every `Ktens` use and identify supported solver/grid combinations |
| [`ice_state.F90`](cicecore/cicedyn/general/ice_state.F90) | Assess field ownership, allocation and access to category/FSD state |
| [`icepack_fsd.F90`](icepack/columnphysics/icepack_fsd.F90) | Verify FSD tracer meaning, bin geometry, normalisation and evolution |
| [`icepack_wavefracspec.F90`](icepack/columnphysics/icepack_wavefracspec.F90) | Audit the spectral wave-fracture pathway and its connection to the selected run configuration |
| [`ice_history.F90`](cicecore/cicedyn/analysis/ice_history.F90) and [`ice_history_fsd.F90`](cicecore/cicedyn/analysis/ice_history_fsd.F90) | Add the minimum diagnostics needed to verify and interpret the feedback |

The implementation audit must also locate namelist handling, initialisation, driver ordering, restart handling, halo exchange and interpolation to the active momentum-grid locations. A spatially varying coefficient cannot be introduced safely by changing only the scalar declaration.

## Numerical and interface requirements

1. **Consistent rheology:** use the same effective coefficient in related stress and pressure terms, including grid-specific calculations. Unsupported solver combinations should fail clearly when the option is requested.
2. **Explicit update timing:** document when FSD is sampled relative to thermodynamics, fracture, transport and dynamics. Initially hold the coefficient fixed during a dynamics solve; assess any timestep lag.
3. **Well-defined ice-free behaviour:** avoid division by negligible ice area. Use a documented finite value for the otherwise irrelevant ice-free diagnostic and retain the existing ice mask.
4. **No silent invalid-state repair:** reject invalid parameters and identify non-finite or materially unnormalised FSD values. Bound round-off errors without concealing state corruption.
5. **Restart consistency:** recompute diagnostic fields deterministically from restart state. Any newly introduced prognostic memory would require its own restart variables.
6. **Spatial consistency:** verify field halos, interpolation, masks and decomposition independence for the supported grid.

Proposed configuration controls are an enable flag, a closure choice, the reference coefficient, a lower bound and closure-specific size parameters. Exact namelist names will be documented when implemented.

## Validation and experiment design

First verify the mechanics of the implementation:

- Dynamic mode disabled: reproduce the inherited control, targeting bit-for-bit agreement for the same executable environment.
- Dynamic mode enabled with $g=1$: recover the constant-coefficient solution within a documented tolerance.
- Prescribed intermediate $g$: agree with a constant-`Ktens` control using the corresponding reduced coefficient.
- Synthetic FSDs: test all-small, all-large and mixed distributions, including multiple thickness categories and ice-free cells.
- Repeat a short case across a restart and more than one MPI decomposition; check bounds, finite stresses and continuity.

Then isolate the physical feedback:

| Experiment | Purpose |
|---|---|
| Constant tensile coefficient with the selected wave/FSD setup | Mechanical reference |
| Evolving FSD and diagnosed $g$, feedback disabled | Observe the proposed cohesion field without changing momentum |
| Same setup with feedback enabled | Isolate the effect of FSD-dependent cohesion |
| Matched wave-fracture sensitivity | Separate wave-driven FSD changes from other FSD processes |
| Selected closure and rheology sensitivities | Assess robustness after the main mechanism is established |

Record $g$, $k_{T,\mathrm{eff}}$, the selected FSD metric and relevant wave/fracture diagnostics alongside concentration, thickness, velocity, deformation and strength diagnostics. Evaluate fast-ice area, persistence, formation and breakup timing using common classification settings and periods.

A change in fast-ice extent alone does not establish improved physics. Assess whether the spatial and temporal response is consistent with fragmentation and whether any improvement is robust to the chosen closure.

## Repository workflow

- `main`: stable reference and reviewed milestones.
- `dev`: active development, beginning with this roadmap.
- `origin`: [CICE_dyntens](https://github.com/dpath2o/CICE_dyntens).
- `upstream`: [CICE_forcing](https://github.com/dpath2o/CICE_forcing).

Preserve source history and record the exact inherited baseline before changing model code. Keep experiment-specific forcing, restarts, executables and output separate from source control. Every experiment should identify its source commit and complete configuration.

The immediate next task is the Stage 0 code and configuration audit, followed by a minimal, optional local tensile-coefficient implementation.
