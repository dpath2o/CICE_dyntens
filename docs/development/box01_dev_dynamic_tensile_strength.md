# Box01 development of dynamic tensile strength

The idealised box isolates the numerical implementation of a tensile multiplier before evolving FSD feedback is assessed on the global grid. It verifies identities, spatial exchange, restart reconstruction, analytical FSD mapping and controlled mapped feedback. These implementation tests do not calibrate a floe-size strength law or demonstrate thermodynamic fidelity on an actively forced global grid.

The current box gate remains **open at B6.6**. B6.5 and B6.5-F passed their stated matrices; the corrected negligible-area live continuation still fails and the isolated trace is pending. There is no B6.7 test.

## Test contents

| Task | Work and evidence | Current status | README stage |
|---|---|---|---|
| [B0](B0.md) | Mechanics baseline with zero tensile factor | Limited baseline evidence: completion and three snapshots; full archive unavailable. | R0 |
| [B1](B1.md) | Unity multiplier identity | Three historical snapshots match; full unity identity subsequently passes under B4. | R1 |
| [B2](B2.md) | Constant multiplier equivalence | PASS: 126 histories and five restarts, exact decoded equality on a common executable. | R1 |
| [B3](B3.md) | Spatial tensile loading and decomposition | PASS: six layout checks and four exact 131-file comparisons for prescribed bands. | R1 |
| [B4](B4.md) | Matched controls on the accepted spatial build | PASS: unity/off, spatial-null and half-g matched controls (4 October 2026). | R1 |
| [B5](B5.md) | Prescribed spatial coefficient restart continuation | PASS: exact 2+3-day prescribed spatial restart continuation (5 October 2026). | R1 |
| [B6](B6.md) | Controlled FSD mapping: definition and acceptance | OPEN: B6.1–B6.5-F have the recorded successes below; B6.6 is unresolved. | R2 / controlled preparation for R3 |
| [B6.1](B6.1.md) | Icepack FSD interface and bin audit | Source audit complete at c7c8770; adapter integration is tested in the later stages. | R2 / controlled preparation for R3 |
| [B6.2](B6.2.md) | Production arithmetic and analytical fixtures | PASS: 67 compiler-driven production fixtures at absolute tolerance 1e-12. | R2 / controlled preparation for R3 |
| [B6.3](B6.3.md) | Candidate diagnostics with momentum feedback disabled | PASS: 126 candidate histories and exact matched physical-control agreement. | R2 / controlled preparation for R3 |
| [B6.4](B6.4.md) | Live-FSD diagnostic restart reconstruction | PASS: independently reconstructed restart IC plus 126 exact histories and five restarts. | R2 / controlled preparation for R3 |
| [B6.5](B6.5.md) | Diagnostic shadow-fixture matrix | PASS: 14 diagnostic shadow-fixture cases, analytical, neutrality, decomposition and continuation. | R2 / controlled preparation for R3 |
| [B6.5-F](B6.5-F.md) | Mapped-feedback equivalence to independent controls | PASS: 21 controlled cases; nine exact map/reference pairs, three unity/off pairs and layout agreement. | R2 / controlled preparation for R3 |
| [B6.6](B6.6.md) | Live invalid-state tests and regression checks | OPEN / partial FAIL: corrected negligible-area serial and MPI continuations abort with status 6; trace pending. | R2 / controlled preparation for R3 |

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
(N/m). Positive divergence establishes opening, not a calibrated fracture
threshold. Changing g changes the viscosity and replacement-pressure expressions.
Do not demand a specified opening ratio or a literal crack.


B0–B5 are mechanics-only tests with FSD off. B6 enables twelve-bin FSD in declared controls, first diagnoses candidates with feedback off and then uses controlled shadow inputs. B6.5-F enables only the guarded mapped feedback path. No box result establishes that global thermodynamics is unaffected.

Configuration folders are indexed by [box01_tests/cases.json](../../box01_tests/cases.json); the migration procedure is [case_organisation.md](case_organisation.md). B0–B2 historical archives remain separate evidence and are not invented as new case directories. The mutable original `dyntens_box01` template is associated with B0 without implying its current namelist is the accepted B0 run.

Global tests have a separate [global development contents page](global_dev_dynamic_tensile_strength.md). The original consolidated documents are preserved in [archive](archive/README.md); these per-stage pages are now the active record.
