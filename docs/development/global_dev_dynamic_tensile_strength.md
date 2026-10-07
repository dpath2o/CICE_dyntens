# Global development of dynamic tensile strength

Restore the inherited global forcing control, diagnose the evolving FSD without momentum feedback, and only then assess supported feedback. Box implementation identities are prerequisites, not proof of global mechanical or thermodynamic realism.

## Test contents

| Task | Purpose | Status | README stage |
|---|---|---|---|
| [G0](G0.md) | Global forcing and unity controls | PLANNED: inherited global evidence is context, not acceptance of this new gate. | R0–R1 |
| [G1](G1.md) | Global evolving-FSD diagnostics without feedback | PLANNED: global diagnostics and the invalid-FSD policy remain to be established. | R3 |
| [G2](G2.md) | Global feedback, physical budgets and seasonal assessment | PLANNED: live global feedback is not enabled by the box-only mapped mode. | R4, then R5 |

Use ERA5 atmosphere, ORAS ocean and the selected WHACS/wave/FSD pathway with actual baseline namelists, dates, units and file coverage. Retain the chosen global free-slip, grounded-iceberg and lateral-drag settings. Thermodynamics and ocean evolution must be active as required by the global control.

G0 can verify inherited forcing while box development continues. G1 requires a supported diagnostic adapter and explicit policy for inherited invalid FSD. G2 requires G0/G1 and supported live/global feedback; the current `box_fsd` guard must not be bypassed. Neither a mechanical opening plot nor a successful process exit demonstrates a closed thermodynamic budget.

Configuration records live under [global_tests](../../global_tests/README.md). Every stage has a PyGMT notebook for its conceptual design and optional real-output figures. No global PASS or invented numerical acceptance bound is added here. See [box01 contents](box01_dev_dynamic_tensile_strength.md) for the completed B6.6 review and the FSD checking work carried into G1.
