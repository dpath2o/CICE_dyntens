# Restart FSD diagnosis

`diagnose_restart_fsd.py` is read-only and needs Python, numpy and netCDF4.
It examines the inherited FSD issue independently of g=1 equivalence.
Use a history file from the matching run for the actual T-cell mask,
latitude and area. It checks dimension order and metadata units, converts
area to km2, and stops on unrecognised units or invalid ocean concentration.
Matching array sizes alone cannot prove that two files use the same grid;
provide the history from this baseline, not another grid configuration.

```bash
cd /g/data/gv90/da1339/src/CICE_dyntens
runs=/g/data/gv90/da1339/cice-dirs/runs/dyntens01/baselines
off="$runs/control.4DKEkGK8"
python3 test_scripts/diagnose_restart_fsd.py \
  --grid-history "$off/history/iceh.2000-09-01.nc" \
  "$off/input_restart/iced.2000-09-01-00000.nc" \
  "$off/restart/iced.2000-09-02-00000.nc" \
  "$off/restart/iced.2000-09-03-00000.nc"
```

There is no need to re-read the old and g1 outputs for this diagnosis:
the user-reported comparisons found exact equality of both output restarts
across all three runs. The input and the two disabled-run output restarts
show whether the inherited issue changes during these two days.

The report addresses:

1. Counts on ocean cells globally and by hemisphere (`tmask=1`), with
   occupied entries on land (`tmask=0`) and unknown/masked grid-mask cells
   reported separately. NH includes the equator. Categories are counted
   separately; affected grid-cell counts are also printed.
2. Four disjoint classes: normalised sums (within 1e-10 of one), effectively
   zero distributions (every bin within 1e-12 of zero), other sums, and
   invalid bins (masked/nonfinite or outside [-1e-12,1+1e-12]). Invalid bins
   take precedence, including when their sum happens to equal one. Sum
   extrema exclude nonfinite sums; `nan` means no finite sum is available.
3. Ice area, `sum(aicen*tarea)`, for each class and its percentage of the
   occupied ocean ice area in that hemisphere. This is ice area, not ice
   extent or a percentage of grid cells. Categories with aicen <= 1e-12
   are excluded. `count_a>1e-6` helps distinguish substantial from tiny
   concentrations; it does not change classification or denominators.

Up to three ocean examples per failure class show latitude, one-based
category/j/i indices, concentration and FSD sum at the same location.
These examples are the first encountered, not the worst cases. Unknown
mask entries are excluded from area denominators and must be resolved if
present before treating the totals as complete.

A successful script exit means the diagnosis completed, not that FSD passed.
No input, model state, thresholds in the model, or source physics is changed.
Do not renormalise the restart based solely on these reports.

Synthetic test of classification, land exclusion, weighting and unit conversion:

```bash
python3 -m unittest discover -s test_scripts -v
```
