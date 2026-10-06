# Organising box01 and global test cases

[Box01 contents](box01_dev_dynamic_tensile_strength.md) · [Global contents](global_dev_dynamic_tensile_strength.md)

The repository stores configuration and provenance under `box01_tests/<stage>/<case>` and `global_tests/<stage>/<case>`. NetCDF history/restart archives, object files and executables remain at the existing external `CICE_TEST_RUNS` paths. A configuration move does not invalidate a completed run or justify rerunning an accepted gate.

## Case identity and the misleading names

| Existing case | Stage | New configuration location | Existing run archive |
|---|---|---|---|
| dyntens_box01 | B0 template, mutable; B0–B2 accepted archives remain separate | box01_tests/B0/dyntens_box01 | runs/dyntens_box01 |
| dt_b67_s1/s2/m2 | B3, weak band columns 6–7 | box01_tests/B3/dt_b3_band67_s1/s2/m2 | runs/dt_b67_s1/s2/m2 |
| dt_b6_s1/s2/m2 | B3, weak band column 6 | box01_tests/B3/dt_b3_band6_s1/s2/m2 | runs/dt_b6_s1/s2/m2 |
| dt_b4_* | B4 | box01_tests/B4/dt_b4_* | runs/dt_b4_* |
| dt_b5_* | B5 | box01_tests/B5/dt_b5_* | runs/dt_b5_* |
| dt_b63_* | B6.3 | box01_tests/B6.3/dt_b63_* | runs/dt_b63_* |
| dt_b64_* | B6.4 | box01_tests/B6.4/dt_b64_* | runs/dt_b64_* |
| dt_b65_* | B6.5 | box01_tests/B6.5/dt_b65_* | runs/dt_b65_* |
| dt_b65f_* | B6.5-F | box01_tests/B6.5-F/dt_b65f_* | runs/dt_b65f_* |
| dt_b66_*, including trace | B6.6 | box01_tests/B6.6/dt_b66_* | runs/dt_b66_* |
| dyntens01 | G0 inherited template, not a new G0 PASS | global_tests/G0/dyntens01 | runs/dyntens01 |

There is **no B6.7**. In the old B3 names, `67` denoted band columns, not a decimal test number. Rename active case/PBS names for these six cases, but keep old output archive IDs and historical logs. The registry records both identities. B6.1/B6.2 are source/unit-driver stages; B1/B2 historical runs do not require invented folders with invented namelists.

The supplied `box01_dt_cice_settings.txt` contains 66 settings records. Their exact scalar settings and csh expressions are retained in stage-level `settings_reference.json` files, with machine-root paths represented as `${CICE_MODEL_REPO}`, `${CICE_TEST_RUNS}` and `${CICE_TEST_BASELINE}`. These are **reference records, not executable settings files or complete reproduction packages**: the attachment does not supply each `ice_in`, compiler macros or job launcher. Actual cases are migrated on the user's system with those files intact.

## Migration semantics

`CICE_testing/scripts/organise_test_cases.py plan` reads current settings and refuses ambiguous destinations, unclassified test names, nonexplicit run paths or unexpected case/run roots. `apply` completes preflight and a full external backup before moving configurations. It rewrites active scripts/settings/namelist case-path references, updates active absolute symlink targets and forces no changes to the model source, run archive, numerical options or executable. Existing provenance directories and result logs are historical and remain unchanged.

Each moved case has `case-migration/record.json`, original copies of changed active text files and before/after hashes. The B6.5-F verifier accepts an original input hash after a move only if the saved original matches that hash and the current text is precisely the recorded path/name transformation. Arbitrary changes to physics, resources or input files still fail. This is an auditable relocation, not a hash-check exemption.

Root `caselist*` files are moved under `box01_tests/_legacy_registry/`. Their original contents and hashes, alongside relocated path views, are exported to `case_creation_records.json` for Git tracking. Raw caselists stay ignored because they contain historical host-local paths. Root B6 mapping logs are archived there too. No history/restart files, binaries or object trees are added to Git. Old executable/object absolute paths embedded by the compiler remain historical; a future build uses the updated case settings and source.

The Python box, restart, feedback and invalid-state workflows resolve both layouts during transition. New generated cases use organised paths once the registry exists; `cice.setup -c` accepts a full directory path and retains the basename as the case ID. Run paths remain flat. No compatibility symlink leaves a second mutable root case behind.

## Apply on Gadi after the diagnostic job has finished

Finish active test jobs before moving their case directories. Pull the documentation/tool update first: this commit does not move the two already tracked root templates, so it can be pulled without relocating local template edits. Those edits are included in the migration backup. If Git reports unrelated local conflicts, retain them and resolve the checkout before applying migration.

```bash
(
set -euo pipefail
cd /g/data/gv90/da1339/src/CICE_dyntens
git pull --ff-only origin dev
load_modules
runs=/g/data/gv90/da1339/cice-dirs/runs
python CICE_testing/scripts/organise_test_cases.py plan \
    --repo "$PWD" --runs "$runs"
python CICE_testing/scripts/organise_test_cases.py apply \
    --repo "$PWD" --runs "$runs" \
    --backup "$runs/case-layout-backups/$(date +%Y%m%d-%H%M%S)"
)
```

The complete backup includes `plan.json`. If a filesystem operation fails partway through, stop and use that plan/backup to inspect or restore cases; a second invocation refuses conflicting destinations. `apply` is not a job submission or model rerun.

After moving, inspect one case and check existing accepted evidence:

```bash
rg 'ICE_(CASENAME|CASEDIR|RUNDIR|OBJDIR|LOGDIR|NTASKS)' \
    box01_tests/B6.6/dt_b66_negligible_area_s1/cice.settings
python CICE_testing/scripts/b65_box_workflow.py analyse \
    --repo "$PWD" --runs "$runs" --evidence validation_report/box/evidence
python CICE_testing/scripts/b65_feedback_workflow.py analyse \
    --repo "$PWD" --runs "$runs" --evidence validation_report/box/evidence
```

B6.6 analysis is still expected to fail on the recorded negligible-area cases; migration must not recast them as accepted. The trace log remains under the original run root. Active B6.6 build/submission commands now run from `box01_tests/B6.6/<case>`.

## Track the actual configuration files

The published registry/settings references are available immediately. The actual Gadi case namelists/environment/macros are not in the attachment and cannot be reconstructed here. After migration, review and commit them from Gadi on `dev`:

```bash
git add -A -- box01_tests global_tests dyntens_box01 dyntens01
git diff --cached --stat
git diff --cached --name-only
# Inspect configuration/provenance and confirm there are no data/binary outputs.
git commit -m "Organise box01 and global test case configurations"
git push origin dev
```

The ignore rules exclude generated output, executables, object/build directories, logs and NetCDF data. No broad `git add .` is needed. Historical source/launcher records in provenance remain useful scientific evidence. The supplied settings alone do not establish their build or physical-input provenance.

## Figures

Every case has `CICE_testing/notebooks/<stage>.ipynb`. Concept diagrams are PyGMT-generated PNG/PDFs with a manifest that labels them as analytical/design figures. Recreate all designs from the repository root:

```bash
python -m CICE_testing.plotting.development \
    --case all --output docs/development/figures
```

Use the package's GMT/PyGMT analysis environment. Optional measured figures require real NetCDF inputs and retain input/output hashes. The existing figure API separates hourly instants, daily means, masks and restart inventories. Global thermal budget plotting needs the actual diagnostics, units and signs; this migration does not invent them.
