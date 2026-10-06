# Evidence handoff: box validation followed by global validation

This is a reporting plan, not a consolidated results document. Complete B6.5-F
and B6.6, collect actual model outputs and checker evidence, then consolidate
`docs/development/developing-dynamic-tensile-strength-box01*.md` into
`docs/development/box_tensile_dev_procedure_results_validation_notes.md`.
Update the model README to link that completed document. Preserve links to the
stage notes until their procedures, findings and limitations have been carried
across; do not replace pending tasks with inferred PASS statements.

## Proposed box report

1. Hypothesis, scope, fixed rheology/forcing and transition criteria to the global grid.
2. Model source/compiler provenance and the small-box grid, loading, layouts,
   namelists, diagnostic streams and temporal ordering.
3. Prescribed constant/spatial coefficients: disabled/g=1 equivalence,
   decomposition and restart continuity, including IC-before-forcing semantics.
4. FSD mapping audit: native radius/diameter convention, strict diameter threshold,
   category ice-area weighting, inactive states, masks and error policy.
5. B6.2 production-routine fixtures and B6.3 diagnostic neutrality.
6. B6.4 continuous versus 2+3-day restart evidence and reconstructed continuation IC.
7. B6.5 shadow-fixture matrix and explicit B6.5-F mapped-feedback controls/results.
8. B6.6 live invalid-state/abort tests, log evidence, supported configuration and limits.
9. Gate table: expected criterion, measured result, tolerance, source/run IDs,
   verdict and remaining limitations. State why progression to the global grid is justified.

## Figure-to-evidence mapping (all PyGMT)

| Figure | Inputs/API | What it supports |
|---|---|---|
| Mapping curve and fixture reference points | `ValidationFigures.mapping()` | Analytical expectation only; clearly labelled reference |
| Uniform fixture expectations versus output | `fixture_matrix({mode: actual_history})` | Measured candidate points; selected snapshots checked against the audited B6.5 table |
| Candidate fraction/g/Ktens maps | `snapshot(actual_history)` | Global column indexing and expected spatial structure |
| Applied g/Ktens and divergence/wind maps | `snapshot(..., names=(...))` | Prescribed/applied fields and loading; wind IC handled separately |
| Separate daily/hourly time series | `timeseries(run, field, stream)` | Time coverage and evolving candidates/applied fields; IC excluded |
| Continuous/split or decomposition errors | `comparison(run, reference, folder)` | Measured differences with CSV mask/value records; full gate verdict comes from validators |
| Restart FSD class ice areas | `fsd_classes(restart, matching_history)` | Diagnostic classification, not physical ice gain/loss or a PASS |
| Feedback-response/invalid-state figures | Add after B6.5-F/B6.6 output exists | Do not substitute shadow-fixture figures for live-feedback evidence |

Export a report root with `box/figures`, `box/evidence`, `global/figures` and
`global/evidence`. Copy selected PNG/PDFs into the model's
`docs/development/figures/box/` or `figures/global/` when assembling the documents.
Keep relative Markdown image links and retain the matching evidence JSON/CSV
and source/run provenance. Figure manifests hash every input and exported file.

B6.4/B6.5 `analyse --evidence DIR` captures the complete transcript and a JSON gate
result. A failed analysis writes FAIL and re-raises; a successful analysis records
only that stage's verdict and names the pending tests. Figures never change the
verdict. A diagnostic that merely completes (e.g. restart FSD diagnosis) is not a
validation gate. Record full model build/launcher logs and successful completion
logs separately alongside these numerical checks.

## Parallel global report

Use `global_tensile_dev_procedure_results_validation_notes.md` when the global
experiments are defined. Reuse the same report sections, provenance and plotting
interfaces with `scope='global'`, but specify the real global-grid masks, extended
restart halos, domains, forcing, spin-up, run periods, coverage and tolerances.
The current box generators cannot certify those global gates. Establish disabled
and g=1 equivalence first, then diagnostic FSD behaviour and feedback comparisons
on the global grid. Physical plausibility, fast-ice impacts and sensitivity tests
remain separate from numerical consistency. Extend adapters/gates for actual
global data shapes rather than removing checks to make a figure render.
