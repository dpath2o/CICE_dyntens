# Box01 development of dynamic tensile strength

The purpose of these box01 tests is to check that $K_{T,\mathrm{eff}}=K_T\,g(\mathrm{FSD})$ has been implemented correctly in CICE/Icepack before returning to the global grid. The small box lets us prescribe the wind, ice and floe sizes, then compare the model results with what we expect from the calculation.

We need to show that switching the new option off, or setting $g=1$, preserves the existing model results; that changing $g$ gives the expected mechanical response; and that the calculation works across processors and when restarting a run. These tests do not establish which floe-size relationship best represents real sea ice. With thermodynamics switched off, they also cannot tell us whether the implementation affects thermodynamic behaviour on the global grid.

B6.5 and B6.5-F are complete for the cases tested. **The box review is complete through B6.6 for the agreed scope. B0 remains incomplete because the full baseline results are unavailable.** B0 has the recorded baseline run and three sets of results; its incomplete status refers to the missing full comparison, not a demonstrated model failure. Any additional baseline work should be limited to what is needed to interpret the later comparisons.

## Questions answered by each test

Complete means the stated question has been answered for the documented box cases. It does not mean the implementation has been validated for the global model. The linked case documents contain the procedures, figures, results and limitations. R0–R5 refer to the development stages in the repository README; the B6 substeps share the link in the B6 row.

| Task | Question | Work to answer the question | Status | README link |
|---|---|---|---|---|
| [B0](B0.md) — Baseline | How does the ice behave in this box before introducing dynamic tensile strength? | Run the mechanics-only control; check ice movement, deformation and volume, and retain the results for comparison. | Incomplete | [R0](../../README.md#development-stages) |
| [B1](B1.md) — Unity multiplier | If $g=1$, do we get the same results as the existing model? | Compare the unity case with the existing model. The early results are supported by the full B4 comparison. | Complete | [R1](../../README.md#development-stages) |
| [B2](B2.md) — Constant multiplier | If we prescribe a constant $g$, is this the same as changing $K_T$ by that amount? | Compare both ways of setting the same effective tensile coefficient using the same executable, including all history and restart files. | Complete | [R1](../../README.md#development-stages) |
| [B3](B3.md) — Spatial variation | Can tensile strength vary across the box and give the same results with different processor layouts? | Prescribe bands of different $g$, apply winds that pull the ice apart, and compare the stresses, ice response and results across layouts. | Complete | [R1](../../README.md#development-stages) |
| [B4](B4.md) — Control comparisons | After adding spatial variation, do the off, unity and constant cases still give the expected results? | Compare the disabled and unity cases, a spatial case that should make no difference, and the equivalent half-strength cases on the same build. | Complete | [R1](../../README.md#development-stages) |
| [B5](B5.md) — Restart | If we stop and restart the model, do we get the same results as a continuous run? | Compare a five-day run with a two-day run followed by a three-day restart, using the prescribed spatial coefficient. | Complete | [R1](../../README.md#development-stages) |
| [B6](B6.md) — FSD-dependent strength | Does the model calculate $g$ from the FSD correctly and apply the intended change in tensile strength? | Check the FSD inputs and calculation, compare diagnostics with independent calculations, and compare controlled FSD feedback with equivalent prescribed coefficients. Finish with the focused B6.6 review below. | Complete | [R2–R4](../../README.md#development-stages) |
| [B6.1](B6.1.md) — FSD inputs | What do Icepack's FSD values represent, and which values should we use to calculate $g$? | Check the floe-size bins, category fractions, weighting and the point in the model where the values are read. | Complete | — |
| [B6.2](B6.2.md) — Calculation | For FSDs with a known answer, does the model calculate the expected $g$? | Run 67 tests through the production Fortran calculation and compare with independently calculated answers. | Complete | — |
| [B6.3](B6.3.md) — Diagnostics | Can we calculate and write the FSD-based coefficient without changing the physical results? | Calculate the coefficient with momentum feedback switched off and compare all physical output with the control. | Complete | — |
| [B6.4](B6.4.md) — FSD restart | After a restart, is the FSD-based coefficient reconstructed correctly without changing the physical results? | Calculate the expected initial coefficient from the restart, then compare the continued history and restart output with the control. | Complete | — |
| [B6.5](B6.5.md) — Controlled FSDs | Do small, large, mixed and spatially varying floe distributions give the expected coefficient? | Compare 14 controlled cases with analytical answers; also check unchanged physical results with feedback off, processor layouts and restart continuation. | Complete | — |
| [B6.5-F](B6.5-F.md) — Applied feedback | When we apply the FSD-based coefficient, do we get the same results as independently prescribing that coefficient? | Compare 21 controlled cases, including small, large and mixed floes, unity/off controls and processor layouts. | Complete | — |
| [B6.6](B6.6.md) — Final box review | Does the new calculation handle invalid FSD and effectively ice-free cells sensibly, without stopping on ordinary numerical behaviour? | Review the existing invalid-input and inactive-cell results; record the tiny-area transport limitation; decide which checks are needed before global testing. Repeat relevant control comparisons if the model code changes. | Complete | — |

## Finishing box01 and returning to the global grid

The negligible-area case starts with an artificial ice area of $5\times10^{-13}$. It is initially below the new calculation's active-area threshold. After transport, the cell becomes active and its FSD fractions sum to about $0.999999967$, outside the current $10^{-10}$ tolerance. The calculation then stops the run. This result is recorded in [B6.6](B6.6.md); it is not evidence that the controlled FSD-to-strength calculation is wrong.

We have stopped expanding that artificial case. B6.6 records what the existing checks establish, what remains uncertain, and the FSD checking policy for the box and next global work. We should not change CICE's transport scheme merely to make this one test pass. Equally, the new option must not stop realistic runs because of ordinary numerical differences. We will assess that behaviour using the evolving FSD on the global grid before enabling its effect on momentum.

The previously proposed extra timestep injections and repeat B4/B5 runs are no longer automatic requirements for finishing box01. Repeat a control only where a code change could affect the result it checks. Retain the earlier test results and the unresolved transport result so that this change in scope is clear; do not relabel the failed continuation as a pass.

The remaining sequence is:

1. **Complete:** record the B6.6 review, the unchanged controlled-box FSD checks and the unresolved transport limitation. The original twelve-case runtime test has not passed. The missing B0 results remain documented; the later matched comparisons are sufficient to proceed to G0 without repeating B0 solely to fill the archive.
2. Return to the global control in G0, with thermodynamics and the normal forcing active.
3. In G1, calculate $g$ from the evolving FSD with its effect on momentum switched off. Check the coefficient and whether its input checks are suitable for the numerical behaviour of the global model.
4. In G2, enable supported global FSD feedback and assess both the mechanical response and the thermodynamic behaviour.

The three questions guiding that global work are:

- **If we switch dynamic tensile strength off, or set $g=1$, do we get the same mechanical and thermodynamic results as the existing global model?** This belongs to G0.
- **When tensile strength depends on floe size, does the ice respond mechanically in the way we expect?** This belongs to G2, after checking the evolving FSD in G1.
- **Do any resulting changes in ice growth, melt and ocean heat exchange make physical sense, and does the model still conserve mass and energy to an acceptable level?** This also belongs to G2, with the control and required output established in G0/G1.

These are global questions, so they do not create new B6.7 or B6.8 box tests. The [global test documents](global_dev_dynamic_tensile_strength.md) hold the detailed work. The current mapped-feedback option is restricted to box01; global feedback still requires a supported implementation.

## Common box configuration

- Case root: `/g/data/gv90/da1339/src/CICE_dyntens`; original case `dyntens_box01`.
- Run root: `/g/data/gv90/da1339/cice-dirs/runs`; archive root:
  `~/AFIM_archive/LFI-waves-dyntens/`.
- Rectangular 12×12 C-grid; 16 km spacing; 64 active ocean T cells at global
  i,j=3..10; two land rows/columns at each edge. Free-slip closed walls.
- Initial aice=0.9 and grid-cell volume/area hi=0.9 m (ice-covered thickness 1 m),
  at rest; internal initial state, not a global restart.
- Calm ocean, zero Coriolis, thermodynamics and mixed-layer evolution off;
  lateral drag, tides, waves and FSD off. Transport/remap and ridging retained.
- Standard 2-D EVP, avg_zeta, ellipse, revised EVP off, ndte=1200, Pstar=1e4,
  Cstar=20, ellipse ratio 2, elasticDamp=0.09, deltaminEVP=2e-9, sum capping.
- Five days from 2005-01-01 to 2005-01-06, 360-day calendar, 120 hourly steps;
  one IC, five daily and 120 hourly histories; five daily restarts.
- B0–B2 use uniform eastward wind. B3 tensile runs prescribe uatm=-5 m/s on
  columns 1–6, +5 m/s on 7–12, vatm=0; `atmbndy='constant'`,
  `calc_strair=.false.`, `rotate_wind=.false.`.

`dyntens_g` and `ktens_eff` are dimensionless; ktens_eff=Ktens*g. `strength`
is the base compressive strength (N/m). `sig1`/`sig2` are normalised principal
stresses, positive in tension; `sigP=-0.5*stressp` is positive in compression
(N/m). Positive divergence shows that the ice is opening. It does not tell us that a
particular fracture threshold has been reached. Changing g changes the viscosity
and replacement-pressure expressions; these tests do not prescribe an opening
ratio or require the model to produce a literal crack.


B0–B5 test mechanics with FSD switched off. B6 uses twelve floe-size bins, first
calculating the coefficient without changing momentum, then applying controlled
FSD inputs. B6.5-F applies their calculated coefficient in the box-only mode.
Global thermodynamic behaviour remains to be tested.

Configuration folders are indexed by [box01_tests/cases.json](../../box01_tests/cases.json); the migration procedure is [case_organisation.md](case_organisation.md). The earlier B0–B2 results remain in their historical archives. The original
`dyntens_box01` folder is now under B0, but it has been edited during development;
its current namelist should not be taken as the namelist used for the baseline.

Global tests have a separate [global development contents page](global_dev_dynamic_tensile_strength.md). The original consolidated documents are preserved in [archive](archive/README.md); these per-stage pages are now the active record.
