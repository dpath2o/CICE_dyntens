# Developing dynamic tensile strength on box01: results and route to the global grid

Updated 4 October 2026. This is the single development record for the idealised
box tests and their transition to global testing. It consolidates the former
box01 and box01-step3 documents. Historical archive names are retained verbatim;
they are not a reliable guide to the numbering of the development tasks.

## Current position

**Prescribed constant and spatial g work in the tested 12×12 C-grid EVP setup.**
The new Gadi transcript confirms six complete history checks and four exact
history/restart comparisons across one-block, two-local-block and two-MPI-rank
layouts, including a coefficient jump at the internal block boundary.

This is not yet an FSD-dependent implementation. Current `constant` and `box_band`
modes prescribe g directly. The remaining immediate tasks are a matched identity/
spatial-null comparison and continuous-versus-split restart verification. Then
verify the size/FSD mapping in controlled inputs and return to global ERA5, ORAS
and WHACS forcing with the proposed g diagnosed but **not used by momentum**.
That global diagnostic milestone is **README development stage 3**.

All evidence here comes from supplied archives, output and Gadi transcripts;
there is no direct access to Gadi. A transcript PASS is recorded as such, without
implying that the six new NetCDF archives or their build provenance were inspected
independently here.

## One numbering scheme for the work

Use **B0–B6** for box tasks, **G0–G2** for global tasks, and **R0–R5** only when
referring to the README development stages. Existing filenames such as `step2`
and `step3-C` remain historical run identifiers.

| Task | Work and evidence | Status | README stage |
|---|---|---|---|
| B0 | Mechanics baseline, uniform eastward wind, Ktens=0 | Reviewed log and three snapshots pass; complete archive unavailable | R0 |
| B1 | Disabled Ktens=0.2 versus enabled g=1 | Three supplied snapshots match exactly; full identity comparison still to close under B4 | R1 |
| B2 | Enabled Ktens=0.2, g=0.5 versus disabled Ktens=0.1 | Same executable; all 131 history/restart pairs match exactly | R1 |
| B3 | Prescribed spatial g, tensile loading and decomposition | A–C physical response reviewed; six layout field checks and four 131-pair comparisons pass | R1 |
| B4 | Matched tensile controls and spatial-null on accepted build | **Next; pending** | Close R1 |
| B5 | Continuous versus split restart under spatial g | Pending | Close R1 restart requirement |
| B6 | Prescribed size-to-g mapping and synthetic category/FSD tests | Pending implementation and tests | R2; controlled preparation for R3 |
| G0 | Re-establish short global disabled/g=1 controls with ERA5, ORAS, WHACS | Pending, after B4–B5; may precede B6 completion to verify forcing plumbing | R0–R1 on global grid |
| G1 | Diagnose evolving FSD metrics and candidate g globally, feedback off | Pending B6 and G0 | **R3: next broader milestone** |
| G2 | Enable FSD feedback; short stability/restart/decomposition tests, then seasonal assessment | Pending G1 | R4, then R5 |

B2's prescribed g=0.5 test does **not** implement R2's diameter-to-g mapping.
B3's spatial-band experiment does **not** implement R3's evolving-FSD diagnosis.
Global geometry and active forcing introduce new interfaces, so successful box
exchange does not eliminate the short global checks.

## Common box configuration and interpretation

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

## B0–B2: established baseline and scalar evidence

### B0: zero-tensile-factor baseline

Accepted log `cice.runlog.260924-202649`; inspected initial, first-hour and final
history snapshots. The complete accepted baseline was not archived. Source
revision/executable checksum were not supplied. Successful completion and finite
inspected mechanical fields were confirmed; this is a mechanics baseline, not
an analytical-solution or full-output verification.

| Quantity | Initial | Hour 1 | Hour 120 |
|---|---:|---:|---:|
| aice range | 0.9 | 0.887405–0.910943 | 0.678257–0.958043 |
| hi range (m) | 0.9 | 0.887428–0.912513 | 0.678341–0.976533 |
| Maximum reported uvel (m/s) | 0 | 0.0620842 | 0.001200285 |
| Divergence range (%/day) | 0 | -33.3668 to 33.5255 | -0.117907 to 0.648155 |
| Ice volume (m³) | 1.47456e10 | 1.47456e10 | 1.474559999999999e10 |
| Ice area (km²) | 14745.6 | 14742.3225 | 14637.5721 |

Volume conservation to roundoff and western opening/eastern compression support
the intended mechanics. An earlier mixed-layer-on run (`260924-200806`, archive
`dyntens-box01.mixedlayer-on.20260924-202016`) contained SST NaNs; disabling the
mixed layer removed those reported NaNs. Their precise origin was not diagnosed.

### B1: nonzero Ktens and g=1 identity

Reported disabled control: `dyntens-box01.step1.20260924-213915`.
Enabled g=1: `dyntens-box01.step2.20260925-110235`, log `260925-065019`.
Both are parts of B1 despite the archive names. The enabled log confirms Ktens=0.2,
use_dyntens=T, g=1 and successful completion. The disabled control's full provenance
was not supplied with the initial snapshot review.

Initial, hour-1 and hour-120 pairs match all decoded values and masks exactly
(137, 72 and 72 variables respectively). This is a three-snapshot identity result,
not a complete five-day comparison. Relative to B0, the reported Ktens=0.2 control
has hour-1 maximum speed 0.0583330 m/s and day-five 0.001191054 m/s; day-five
ice area 14640.1727 km². It remains mechanically consistent with the same forcing.
B4 closes the full identity check on the accepted spatial implementation.

### B2: constant-g equivalence

Complete archives reviewed:

- `dyntens-box01.step2-run1.20260925-131357`: log `260925-124634`, disabled Ktens=0.1.
- `dyntens-box01.step2-run2.20260925-132240`: log `260925-131803`, enabled Ktens=0.2, g=0.5.

The namelists differ only in Ktens, use_dyntens and the ignored/enabled scalar g.
Both executable SHA-256 hashes are
`253cb3b95dd2b2ae99609f98ec1bebe633a66bb62b5a9e03528ff53ab376bbfe`.
All 126 histories and five restarts match exactly: **131 file pairs, 9,462
variable pairs, zero value/mask differences and no unmasked nonfinite numeric
values**. This establishes scalar equivalence for the tested setup. It is not
a stopped/resumed restart test. At day five, volume is 1.474559999999999e10 m³
and area 14638.8138 km².

## B3: tensile loading and spatial coefficients

| Archive under `~/AFIM_archive/LFI-waves-dyntens/` | Archived wind | Coefficient | History gate |
|---|---|---|---|
| `dyntens-box01.step3-0.20260927-130227` | uniform_east | disabled; effective 0.2 | 126/126 pass with uniform-east assertion |
| `dyntens-box01.step3-A.20260927-142925` | box_tensile | constant g=1; effective 0.2 | 126/126 pass |
| `dyntens-box01.step3-B.20260927-143430` | box_tensile | constant g=0.5; effective 0.1 | 126/126 pass |
| `dyntens-box01.step3-C.20260927-154047` | box_tensile | g=0.5 in columns 6–7, 1 elsewhere | 126/126 pass |

All four hourly inventories cover hours 1–120 with one-hour time-coordinate
spacing. All five restart files per archive pass an independent scan of every
unmasked numeric value for finiteness. This does not establish split-run restart
reproducibility. Masked storage and arbitrary missing-field completeness are not
certified by the finite scan.

3-0 is a uniform-east reference, not a matched disabled-path tensile control.
Its `uatm` is +5 m/s throughout the active ocean. Applying `--tensile` correctly
rejects it. Preserve it; obtain a separate disabled `box_tensile` run for the
identity comparison. A and B namelists differ only in `dyntens_g_const`; A and C
namelists differ only in `dyntens_g_mode`.

Executable SHA-256:

- 3-0, A, B: `9703f37187a64e717873c63c0dc145f6114c58aab8e6ca7565b51c463c5c2202`
- C: `24b9df36e1c01fb9e1093b2a4369c9838ac716f9f616db755e18d49d1da18158`

The C executable differs following the startup-validation rebuild. The hashes
alone cannot establish that this is its only source/build difference. Repeat the
matched tensile controls using the accepted C executable before attributing all
A–C differences exclusively to the coefficient map.

### Measured tensile response

Values below are instantaneous snapshots, sampled over active T cells in global
columns 6–7. Spatial differences within that central set are below the displayed
precision. `sig1` is dimensionless principal stress normalised by strength;
`sigP` is vertically integrated pressure, positive in compression (N/m).

| Quantity | 3A: g=1 | 3B: g=0.5 | 3C: weak band |
|---|---:|---:|---:|
| Hour 1 central divergence (%/day) | 11.547084 | 15.001759 | 14.825436 |
| Hour 1 central sig1 | 0.269396 | 0.164093 | 0.164092 |
| Hour 1 central sigP (N/m) | -165.574497 | -50.821862 | -50.821324 |
| Hour 120 central divergence (%/day) | 0.138509 | 0.143498 | 0.142564 |
| Hour 120 central sig1 | 0.243639 | 0.148884 | 0.148790 |
| Hour 120 central aice | 0.883963 | 0.878667 | 0.879060 |

At hour 1, the ocean velocity extrema have opposing signs: ±0.0213835 m/s
(A), ±0.0277810 (B), and ±0.0274545 (C). Positive central divergence and
principal stress, negative central pressure, and compression elsewhere support
the intended extensional loading. Reduced g produces greater initial opening and
lower central tensile stress. By hour 120, transport and strength feedback have
substantially reduced opening rates. A and B form the clean same-executable
comparison; C gives consistent spatial-case evidence subject to the rebuild
qualification above. These diagnostics do not by themselves certify a yield
surface, a crack threshold or resolution convergence.

Do not interpret the small central-divergence values printed for daily files as
the magnitude of the initial transient: the first hourly snapshot resolves a
much larger response. Some CICE stress/divergence fields are snapshots even in
daily output; consult their variable comments rather than assuming every field
in a daily file is a daily mean.


### Decomposition results supplied 4 October 2026

Evidence: `Pasted text(7).txt`, containing the complete ordered checker loop over
b67 then b6, and s1 then s2 then m2. The transcript reports the checkout up to
date and shows the blkmask exclusion from checker revision `a3ea8c8`; it does not
print the model source revision or executable hashes. Case attribution follows
the displayed loop order. Preserve the actual case namelists, job/build logs and
checksums with these results, including confirmation of the two-rank launches.

| Case | Prescribed band | History checks | Reference comparison | Result |
|---|---|---:|---|---|
| dt_b67_s1 | columns 6–7 | 126/126 | Reference | PASS |
| dt_b67_s2 | columns 6–7 | 126/126 | 131 pairs vs b67_s1 | PASS, atol=rtol=0 |
| dt_b67_m2 | columns 6–7 | 126/126 | 131 pairs vs b67_s1 | PASS, atol=rtol=0 |
| dt_b6_s1 | column 6 | 126/126 | Reference | PASS |
| dt_b6_s2 | column 6 | 126/126 | 131 pairs vs b6_s1 | PASS, atol=rtol=0 |
| dt_b6_m2 | column 6 | 126/126 | 131 pairs vs b6_s1 | PASS, atol=rtol=0 |

Total: **756 history-file checks and 524 pairwise file comparisons**. Each
comparison covers 126 histories and five restarts; these counts include repeated
use of the references. Histories check prescribed coefficient maps, finite
unmasked numeric fields and the outward wind (except pre-forcing IC wind).
Reference comparisons check inventories, dimensions, masks and decoded unmasked
values. NetCDF metadata and masked storage are excluded. **Only history blkmask
value equality is exempt**, because CICE defines it as mytask + iblk/100; its
inventory/dimensions/masks/finiteness remain checked. No physical-field tolerance
was relaxed. This is exact decoded numerical agreement, not byte-identical files.

| Band | Central divergence at hour 1 (%/day) | At hour 120 (%/day) |
|---|---:|---:|
| 6–7 | 14.825436 to 14.825436 | 0.14256394 to 0.14256394 |
| 6 only | 0.20074359 to 26.469676 | 0.0035674161 to 0.30690565 |

The same printed ranges occur for all three layouts within each band. The
one-column case deliberately breaks east–west symmetry and puts unequal g
values across the internal 6/7 boundary. Agreement includes the physical fields
and restarts, not merely the coefficient map. **The prescribed-g decomposition
gate passes for these tested layouts. Do not rerun it simply because this record
has been consolidated.** It does not establish global-grid or FSD-dependent
exchange, restart continuation, or physical yield-surface convergence.

## B4 -- Matched controls results

Results supplied 4 October 2026 in `Pasted text(8).txt` close the B4
matched-controls gate. This subsection supersedes the earlier B4 “pending/next”
status above and the original B4 acceptance recipe below; those sections are
retained unchanged as requested. **B5 restart continuation is now the next gate.**

The four cases used separate run directories under
`/g/data/gv90/da1339/cice-dirs/runs/`. The displayed namelists specify fresh
internal initial conditions, five days, `box_tensile` forcing and `Ktens=0.2`;
the job scripts request one CPU. The preparation procedure reused the accepted
`dt_b67_s1` executable without rebuilding. The supplied transcript does not print
executable checksums, so retain the generated `cice.sha256` and `README.case`
records with the actual run namelists and logs.

| Case | PBS job | Enabled / mode | Prescribed g | Effective coefficient | History check | Reference comparison |
|---|---|---|---|---|---|---|
| dt_b4_off | 180464581 | false / constant | 1 | 0.2 | PASS, 126 files | Reference |
| dt_b4_one | 180464582 | true / constant | 1 | 0.2 | PASS, 126 files | PASS vs off, 131 pairs |
| dt_b4_null | 180464583 | true / box_band | background 1, band 1, columns 6–7 | 0.2 | PASS, 126 files | PASS vs one, 131 pairs |
| dt_b4_half | 180464584 | true / constant | 0.5 | 0.1 | PASS, 126 files | PASS vs archived 3-B, 131 pairs |

The half reference is
`/home/581/da1339/AFIM_archive/LFI-waves-dyntens/dyntens-box01.step3-B.20260927-143430`.
All three distinct reference comparisons report **atol=0.0, rtol=0.0** across
126 history files and five restart files. This establishes exact decoded,
unmasked numerical agreement under the existing comparison rules, not binary
file identity. History `blkmask` value equality remains the sole field-value
exception; physical-field tolerances were not relaxed.

The transcript contains six 126-file checker passes and four 131-pair comparison
passes because null was checked twice (first as a uniform field, then explicitly
with `--mode box_band --background 1 --band 1 --ilo 6 --ihi 7`), and half was
checked both alone and against 3-B. Count these as **four distinct runs and three
distinct reference comparisons**, not six independent experiments.

| Cases | Central divergence at hour 1 (%/day) | At hour 120 (%/day) |
|---|---:|---:|
| off / one / null | 11.547084 | 0.1385088 |
| half | 15.001759 | 0.14349826 |

The three unity-g controls agree across the full compared physical state.
Uniform half-g reproduces the earlier 3-B solution. Thus enabling g=1 and
selecting a spatial band with no contrast introduce no detected numerical
change in this tested tensile-loading setup. This does not yet demonstrate
restart continuation or FSD-dependent behaviour.

The displayed off-job report records `CICE COMPLETED SUCCESSFULLY` and exit
status 0. It also prints a missing `/g/data/xp65/public/modules` directory
message before execution; this did not prevent that run completing. These
results are recorded from the supplied transcript; the four new NetCDF datasets
were not independently inspected here.

## B5 -- Restart continuation results

Results supplied 5 October 2026 in `Pasted text(9).txt` establish successful
split-run execution and restart staging. The subsequent `Pasted text(10).txt`,
`pre_split.log` and `post_split.log` establish prescribed-field checks and
exact continuous-versus-split agreement. **The B5 numerical restart comparison
passes for this tested prescribed-g box configuration: 53 pairs before the
split and 78 pairs after it, with atol=rtol=0.** This supersedes earlier
pending B5 wording elsewhere in this document; B6 is the next box-development
task. The rest of this document is retained unchanged.

The agreed setup uses the accepted `dt_b6_m2` two-rank, one-column-band case:
`box_tensile` forcing, `Ktens=0.2`, background g=1 and g=0.5 at global
column 6. Three separate cases were prepared for a five-day continuous run,
a two-day initial segment, and a three-day continuation. These are the intended
settings from the preparation procedure; the new transcript does not print the
actual run namelists or executable checksums.

| Case | Intended experiment | Evidence supplied | Status |
|---|---|---|---|
| dt_b5_cont | Five days from internal initial conditions | 126-file prescribed-field check; reference for both comparison windows | History checks PASS; reference comparisons PASS |
| dt_b5_seg1 | Two days from the same internal state | Job 180508707.gadi-pbs; CICE completed successfully; exit status 0 | Execution and 53-pair comparison PASS |
| dt_b5_seg2 | Three further days from the segment-1 restart | Job 180509882.gadi-pbs; CICE completed successfully; exit status 0 | Execution and 78-pair comparison PASS |

Both supplied job reports request two CPUs and 9 GB memory, with a 30-minute
walltime limit. Segment 1 ran on 5 October 2026 from 14:19:58 to 14:20:11 AEDT
(`cice.runlog.261005-141958`); segment 2 ran from 14:49:00 to 14:49:07 AEDT
(`cice.runlog.261005-144900`). Each reports 0.01 service units.
Both print the missing `/g/data/xp65/public/modules` directory message before
execution, but subsequently report successful model completion.

The segment-1 directory listing contains daily histories for 1–2 January,
hourly histories through `iceh_inst.2005-01-03-00000.nc`, and restarts
`iced.2005-01-02-00000.nc` and `iced.2005-01-03-00000.nc`.
This inventory is consistent with the intended two-day segment; the restart
header and step counter were not printed.

The transcript shows the following restart transfer under
`/g/data/gv90/da1339/cice-dirs/runs/`:

- Source: `dt_b5_seg1/restart/iced.2005-01-03-00000.nc`.
- Staged input: `dt_b5_seg2/input_restart/iced.2005-01-03-00000.nc`.
- `cmp` completed successfully under `set -euo pipefail`, confirming that the
  staged copy is byte-identical to the source.
- The printed `dt_b5_seg2/ice.restart_file` points to that staged input by
  absolute path. Segment 2 was then submitted and completed successfully.

### Numerical validation supplied 5 October 2026

The complete-run checker transcript `Pasted text(10).txt` reports prescribed
coefficient/loading and finite-history PASS results for 126 continuous files,
51 segment-1 files and 76 segment-2 files. The segment-2 total includes its
restart-time IC snapshot; that additional snapshot is excluded from the
continuous-versus-split comparison.

| Comparison log | Split output versus continuous reference | History checks | Restart pairs | Total comparison | Result |
|---|---|---:|---:|---:|---|
| pre_split.log | Segment 1: initial snapshot, daily histories for 1–2 January and hourly histories through 3 January 00:00 | 51 | 2 | 53 pairs | PASS, atol=0.0, rtol=0.0 |
| post_split.log | Segment 2: daily histories for 3–5 January and 72 hourly histories from 3 January 01:00 through 6 January 00:00 | 75 | 3 | 78 pairs | PASS, atol=0.0, rtol=0.0 |

Case attribution and restart-date selection follow the supplied comparison
procedure. Together these windows compare 126 histories and five restarts
against the continuous run, including the split-time and final restart states.
The two logs report no comparison failures. Coefficients and finite history
pass after continuation, and the compared physical fields retain exact
decoded, unmasked numerical agreement. This is not a claim of byte-identical
NetCDF files.

The checker retains its history `blkmask` value exception (51 pre-split and
75 post-split history pairs), because those values identify block/rank ownership.
Variable inventories, dimensions and masks remain checked; physical-field
tolerances were not relaxed.

| Instantaneous output | Central divergence minimum (%/day) | Maximum (%/day) |
|---|---:|---:|
| Split boundary: 3 January 00:00 | 0.0049842222 | 0.38701003 |
| First post-restart hour: 3 January 01:00 | 0.0049583075 | 0.38524518 |
| Final output: 6 January 00:00 | 0.0035674161 | 0.30690565 |

The exact comparisons support restart reproducibility across the tested
two-day plus three-day split with a prescribed spatial coefficient jump.
They also support correct reconstruction of the diagnostic g and ktens_eff
fields after restart. They do not establish evolving-FSD or global-forcing
restart behaviour.

Provenance qualification: these uploaded comparison logs contain the checker
output only. The preparation script separately checks executable hashes,
restart headers (3 January/step 48 and 6 January/step 120), the staged copy,
and daily time units/calendar/bounds before invoking the checker. Its preflight
stdout is not included in these two log files, so the actual hash values,
header values and interval-check messages are not independently recorded here.
Preserve that stdout, actual namelists, launch settings and model startup logs
with the experiment archive. Numerical comparison PASS results are directly
present in the supplied logs; the new NetCDF datasets were not independently
inspected here.

## Remaining work: explicit acceptance gates

### B4 — close the matched controls (next)

Use the accepted one-block executable and identical internal initial conditions,
box_tensile forcing, numerical settings and five-day output for these controls.
Archive separately; only the entries listed below change.

| Control | use_dyntens | mode | background | band | Ktens | Expected comparison |
|---|---|---|---:|---:|---:|---|
| off | false | constant | 1 | ignored | 0.2 | Reference |
| one | true | constant | 1 | ignored | 0.2 | Exact full history/restart match to off |
| null | true | box_band | 1 | 1 | 0.2 | Exact full match to one; bounds 6–7 |
| half | true | constant | 0.5 | ignored | 0.2 | Check continuity with archived 3B across the rebuild |

Use `check_box_spatial_g.py --tensile --ktens 0.2` with the matching mode and
background/band, and `--reference-run` for equal-solution pairs. Expected identity
comparisons: 131 pairs at zero tolerance. Do not compare half against one expecting
equality. Existing archives may satisfy a row if their configuration, executable
and full comparison evidence establish it; the original 3-0 cannot because it
used uniform_east. Record source revision, local diff and executable SHA-256.

### B5 — restart continuation

Use a spatial case, preferably the tested two-rank one-column band, with the
same executable, layout and forcing for both paths:

- Continuous path: five days from internal initial conditions (existing accepted
  output can serve if provenance matches).
- Split path: two days from the same initial state, then three days from its
  2005-01-03 restart with restart time honoured. Preserve both segments.

Confirm restart date and step count before continuing; final time must be
2005-01-06, step 120. Compare matching post-restart instantaneous fields and
final restart values/masks exactly; compare daily averages only over aligned
intervals. Exclude a second-segment IC snapshot from the continuous inventory.
The existing full-directory comparator requires identical file inventories, so
prepare explicitly matched comparison sets or add a time-selection facility
before using it for this split test. Do not interpret an inventory mismatch as
a physics failure. Verify g and ktens_eff reconstruct from configuration and
are not stale/missing after restart. Publish the exact restart namelist and
comparison commands when implementing this task; no new restart switches are
assumed here.

### B6 — size/FSD mapping in controlled inputs

This is development still to implement. Agree a bounded mapping and parameters
first; the README large-floe-area fraction is a candidate, not a settled closure.
For a prescribed diameter test, define radius-versus-diameter units and the
expected g analytically. Check endpoints, intermediate values, monotonicity and
limits. Then test synthetic category FSDs: all-small, all-large, mixed, unequal
category areas, negligible/zero ice, and invalid/missing distributions. Verify
category-area weighting and the chosen bin-threshold convention against explicit
expected values. Do not silently renormalise materially invalid state.

Initially diagnose the metric and g without changing momentum. Distinguish
**candidate** g/ktens_eff from the coefficient actually supplied to dynamics:
currently the disabled path reports g=1, so it cannot by itself provide this new
FSD diagnostic mode. Define update timing relative to fracture, transport and
dynamics. These tests should be cheap controlled tests, not a new climate campaign.

### G0 — restore the global forcing control

After B4–B5, return to the inherited global MPI configuration with a short
control, initially a few days, using the same grid, restart and ERA5 atmosphere,
ORAS ocean and WHACS wave setup as the selected wave-forcing reference. Verify
actual namelist switches, file coverage, variable units and model/forcing dates;
do not infer an active pathway from the presence of reader code. The serial
box WHACS stub intentionally aborts if used; global WHACS must use the MPI reader.

Retain the chosen global free-slip, grounded-iceberg, lateral-drag, ocean and
wave/FSD settings across comparisons. Box mixed-layer-off and calm-ocean settings
are not a global template. Compare disabled and g=1 using a common executable;
where available compare the disabled build with the inherited control. Keep
inherited initial-history wave differences separately identified. Check active
fields, dates, forcing loading, restart continuity and representative global
decompositions before extending duration. This is verification of the inherited
configuration, not an invitation to retune snow or other baseline physics.

### G1 — global evolving-FSD diagnostics: README stage 3

Requires B6 and G0. Evolve the FSD under the selected ERA5/ORAS/WHACS setup and
record category sums, ice-area-weighted size metric, candidate g, bounds/masks,
wave/fracture context and update timing. Keep the coefficient used by momentum
at the control value. A diagnostic-only run should reproduce the control's
physical state within the established comparison criterion; extra diagnostics
require an explicit variable comparison list.

The earlier global restarts already contained normalisation departures, shared
by original, disabled and g=1 runs. That is not evidence that dynamic tensile
strength caused them, but the mapping must handle their meaning explicitly before
feedback. Quantify extent and area weighting, verify tracer semantics and locate
material invalid states. Avoid both a blanket tolerance that conceals them and
an unrelated model-optimisation campaign. **R3 is reached only when these global
diagnostics and their lack of momentum feedback are verified.**

### G2 — feedback, seasonal pilots and long experiments

After G1, supply FSD-derived g to the supported rheology (R4). Repeat bounds,
finite-state, restart and decomposition checks because the coefficient now
evolves; hold g fixed through each dynamics solve initially and document any lag.
Then assess attributable seasonal response (R5) before choosing the control and
two to three ten-year experiments. Keep forcing, initial states, classification
and reference rheology aligned; vary only the declared feedback/closure choice.
Exact closure parameters, integration years and experiment matrix remain to be
agreed. Ten-year runs are not required to close R3.

## Implementation and resolved setup issues

- `ice_init.F90`: reads/broadcasts/validates enabled mode, constants and band;
  supported path is C-grid, standard_2d EVP, avg_zeta, ellipse, revised EVP off.
- `ice_dyn_shared.F90`: owns controls and optional local coefficient in both
  viscosity and replacement-pressure expressions.
- `ice_dyn_evp.F90`: constructs public T-cell g/ktens_eff arrays when enabled,
  exchanges scalar g halos then derives ktens_eff; updates at initialisation and
  each dynamics step. Existing viscosity/stress exchange before T-to-U averaging
  remains necessary. Coefficients are derived, not prognostic restart fields.
- `ice_forcing.F90`: box_tensile winds are prescribed from global column indices.
- `ice_history*.F90`: dimensionless coefficient diagnostics; daily base names,
  instantaneous `_1` names, both in IC. IC precedes atmospheric initialisation.
- Band upper-bound validation moved after domain initialisation (commit a321096).
  The subsequent successful 3C archives resolve the startup failure.
- Checker corrections handle pre-forcing IC winds, dual-stream names and
  layout-specific blkmask (a3ea8c8). Twenty-four fixture tests passed when the
  final correction was made; the six new runs supply runtime evidence.
- Generated cases need the accepted physics namelist plus their own domain and
  paths. Working env/Macros must be copied before building; initialise modules
  inside noninteractive csh. The successful s1 build uses -O2 -fp-model precise.
  The analysis3 `test` wrapper interfered with module initialisation: use a fresh
  build/submission environment and load the analysis environment for Python only.
- Serial WHACS compatibility stub supports the box build but aborts on actual
  WHACS use. No serial wave-forcing validation is implied.

## Decomposition check

The following recipe is retained for reproducibility. **Its six reported cases
have now passed; it is not the next task. Continue with B4 above.**

#### 1. Define the six cases

The setup's explicit `-p` format is tasks × threads × block-x × block-y ×
maximum-blocks-per-rank. Global dimensions remain 12×12 in every case.

| Case name | Band columns | `-p` | Purpose |
|---|---|---|---|
| `dt_b67_s1` | 6–7 | `1x1x12x12x1` | Fresh one-block 3C reference |
| `dt_b67_s2` | 6–7 | `1x1x6x12x2` | Two blocks on one rank; local copies |
| `dt_b67_m2` | 6–7 | `2x1x6x12x1` | One block per rank; MPI exchange |
| `dt_b6_s1` | 6 only | `1x1x12x12x1` | One-column-band reference |
| `dt_b6_s2` | 6 only | `1x1x6x12x2` | Coefficient jump across local block edge |
| `dt_b6_m2` | 6 only | `2x1x6x12x1` | Coefficient jump across MPI boundary |

The internal boundary lies between global columns 6 and 7. With the two-column
band, both sides have g=0.5. With the one-column band, column 6 has g=0.5 and
column 7 has g=1: this explicitly tests copying unlike neighbour values. A halo
is a neighbour's copied value, not an extra physical cell. Compare each split
layout with its matching one-block reference; do not compare b6 with b67 or
require east–west symmetry in b6.

#### 2. Generate separate cases from the same source revision

Run from Bash on Gadi. Use the working compiler/module environment established
for the successful build. Case creation must complete without unresolved module
errors. The guard prevents accidental regeneration of an existing case.

```bash
cd /g/data/gv90/da1339/src/CICE_dyntens
git pull --ff-only origin dev
git rev-parse HEAD
for band in b67 b6; do
    for layout in s1 s2 m2; do
        case "$layout" in
            s1) pes=1x1x12x12x1 ;;
            s2) pes=1x1x6x12x2 ;;
            m2) pes=2x1x6x12x1 ;;
        esac
        case_name="dt_${band}_${layout}"
        if [ -e "$case_name" ]; then
            echo "Already exists: $case_name; inspect it before proceeding"
            break 2
        fi
        ./cice.setup -c "$case_name" -m gadi1 -e intel \
            -g gbox12 -p "$pes" -s boxforcee,boxclosed,buildclean || break 2
    done
done
```

Do not update model source between these builds/runs. Record `git diff` as well
as the commit if there are uncommitted model changes. Different serial/MPI
executables are expected; identical source and compiler flags are the controls.

#### 3. Apply the verified physics without losing the generated decomposition

The setup options alone do not recreate the accepted experiment. Use the
**archived successful 3C `ice_in`**, not an actively edited working namelist.
The following one-time preparation copies that configuration while retaining
**each generated `domain_nml` in full**. The archived output paths are relative
and therefore resolve inside each case's own run directory. It saves the
original generated namelist for inspection and refuses to overwrite that backup.

```bash
python3 - <<'PY'
from pathlib import Path
import re

source = Path.home() / 'AFIM_archive/LFI-waves-dyntens/dyntens-box01.step3-C.20260927-154047/ice_in'
accepted = source.read_text()
domain = re.compile(r'(?ms)^\s*&domain_nml\b.*?^\s*/\s*$')
assert len(domain.findall(accepted)) == 1, 'expected one archived domain_nml'
for key, value in [('ice_ic', "'internal'"), ('npt', '5'),
                   ('atm_data_type', "'box_tensile'"),
                   ('use_dyntens', '.true.'), ('dyntens_g_mode', "'box_band'")]:
    match = re.search(r'(?mi)^\s*' + key + r'\s*=\s*([^!\n]+)', accepted)
    assert match and match[1].strip() == value, (key, 'unexpected template')
for key in ['restart_dir', 'history_dir', 'incond_dir', 'pointer_file']:
    match = re.search(r'(?mi)^\s*' + key + r"\s*=\s*'([^']+)'", accepted)
    assert match and match[1].startswith('./'), (key, 'expected case-relative path')

prepared = []
for band, upper in [('b67', 7), ('b6', 6)]:
    for layout in ['s1', 's2', 'm2']:
        case = Path(f'dt_{band}_{layout}')
        target = case / 'ice_in'
        generated = target.read_text()
        matches = domain.findall(generated)
        assert len(matches) == 1, (case, 'expected one generated domain_nml')
        backup = case / 'ice_in.setup-original'
        assert not backup.exists(), (backup, 'already prepared')
        result = domain.sub(lambda m: matches[0], accepted)
        result, count = re.subn(r'(?mi)^(\s*dyntens_band_ihi\s*=).*$',
                               lambda m: m[1] + f' {upper}', result)
        assert count == 1
        prepared.append((target, backup, generated, result))
# Validate all six before writing any of them.
for target, backup, generated, result in prepared:
    backup.write_text(generated)
    target.write_text(result)
    print('Prepared', target)
PY
```

Check that these settings are present in each prepared case:

- `use_dyntens=.true.`, mode `box_band`, background 1, band 0.5,
  `Ktens=0.2`, lower column 6; upper column 7 or 6 as above.
- `atm_data_type='box_tensile'`; free-slip C-grid; lateral drag, waves,
  thermodynamics and mixed-layer evolution remain as in archived 3C.
- Internal initial conditions, five days, one-hour timestep, the same EVP
  subcycling; daily plus hourly coefficient/stress/velocity output.

```bash
for case_name in dt_b67_s1 dt_b67_s2 dt_b67_m2 dt_b6_s1 dt_b6_s2 dt_b6_m2; do
    echo "$case_name"
    sed -n '/&domain_nml/,/^\//p' "$case_name/ice_in"
    grep -E 'ICE_(CASEDIR|RUNDIR|NTASKS|NTHRDS|COMMDIR)' "$case_name/cice.settings"
done
```

Expected `nprocs/block_size_x/block_size_y/max_blocks` are `1/12/12/1`
for s1, `1/6/12/2` for s2, and `2/6/12/1` for m2. Keep global nx/ny=12,
`roundrobin` and the generated processor-shape settings. Verify the actual
block/rank allocation in the model startup diagnostic too; a launch with only
one rank does not test MPI.

#### 4. Preserve the working build environment; check the launcher

Reuse the accepted environment and compiler macros, but keep the newly generated
`cice.settings`, `cice.run`, `cice.submit` and case paths. For example, after
confirming these are still the working files from the successful box build:

```bash
for case_name in dt_b67_s1 dt_b67_s2 dt_b67_m2 dt_b6_s1 dt_b6_s2 dt_b6_m2; do
    cp dyntens_box01/env.gadi1_intel "$case_name/"
    cp dyntens_box01/Macros.gadi1_intel "$case_name/"
done
```

In each generated `cice.run`, inspect the PBS header and executable launch line:

| Setting | s1 and s2 | m2 |
|---|---|---|
| `ICE_NTASKS` in settings | 1 | 2 |
| `ICE_NTHRDS` | 1 | 1 |
| Effective `ICE_COMMDIR` | serial | mpi |
| PBS `ncpus` | 1 | 2 |
| PBS memory / walltime | 4gb / 00:30:00 | 4gb / 00:30:00 |
| Launch | `./cice >&! $ICE_RUNLOG_FILE` | `mpirun -np 2 ./cice >&! $ICE_RUNLOG_FILE` |

Retain project `gv90`, queue `normalbw`, working storage directives and each
case's own PBS output path. The generator may already supply the correct MPI
launcher: inspect it rather than adding a second launch. Never copy the old
serial `cice.run` into an MPI case. The generated `cice.settings` selects the
communication directory from `ICE_NTASKS`; do not force it to serial for m2.

#### 5. Build, submit and retain each run

Start with `dt_b67_s1`. After its check passes, do s2 then m2; repeat for b6.
Build each generated case: do not copy the old serial executable into m2.

```bash
case_name=dt_b67_s1    # change to the next case from the table
(
    cd "$case_name" || exit
    ./cice.build > build.decomp.log 2>&1 && ./cice.submit
)
```

Submission is asynchronous. Wait for completion before checking or changing
anything. Confirm `CICE COMPLETED SUCCESSFULLY`, final step 120 / 2005-01-06,
and the intended rank/block count in the log/diagnostics. Keep the build log.
Each case should have its own `ICE_RUNDIR` under
`/g/data/gv90/da1339/cice-dirs/runs/`; verify that path in `cice.settings`.
If a chosen run directory already contains results, archive those and use a
fresh directory before submitting. Do not mix old and new NetCDF output.

Archive each completed run using the established workflow, retaining executable,
`ice_in`, `cice.settings`, compiler environment/macros, build/run logs, history,
restarts and source revision. Record the executable SHA-256. Keep the six run
directories intact until their comparisons are complete.

#### 6. Check maps and compare all decoded fields

After all six jobs complete, run from the repository root. Use the actual
`ICE_RUNDIR` paths if yours differ from those below. `load_modules` is for the
Python checks, after the model build/run environment has done its job.

```bash
load_modules
runs=/g/data/gv90/da1339/cice-dirs/runs
for band in b67 b6; do
    if [ "$band" = b67 ]; then upper=7; else upper=6; fi
    reference="$runs/dt_${band}_s1"
    python3 test_scripts/check_box_spatial_g.py "$reference" \
        --mode box_band --ktens 0.2 --background 1 --band 0.5 \
        --ilo 6 --ihi "$upper" --tensile || break
    for layout in s2 m2; do
        python3 test_scripts/check_box_spatial_g.py "$runs/dt_${band}_${layout}" \
            --mode box_band --ktens 0.2 --background 1 --band 0.5 \
            --ilo 6 --ihi "$upper" --tensile \
            --reference-run "$reference" || break 2
    done
done
```

Expected for this five-day configuration: six summaries of
`PASS prescribed fields/finite history: 126 files`, plus four summaries of
`PASS reference comparison: 131 file pairs; atol=0.0, rtol=0.0` (126 histories
and five restarts). Compare only runs with the same band. Record the actual
counts and any first failing field. If arithmetic differences occur, measure
and explain them before considering a tolerance; do not loosen tolerances simply
to obtain a pass. Equal g maps alone cannot verify stress/velocity exchange.

Optionally compare the fresh b67/s1 with archived 3C using the same
`--reference-run` option to establish continuity with the accepted archive.
A difference across builds is a separate question from decomposition equivalence.

**Acceptance criterion (met by the supplied transcript):** both band profiles pass across local and remote block
boundaries, with physical history and restarts matching the appropriate reference.
This closes the decomposition gate only. A continuous versus split-run comparison
and the matched-control/spatial-null checks remain required; FSD feedback and
global experiments follow the box acceptance sequence below.

