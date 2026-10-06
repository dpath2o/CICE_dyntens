# Box01 test configurations

[Development contents and results](../docs/development/box01_dev_dynamic_tensile_strength.md) · [Migration procedure](../docs/development/case_organisation.md)

`cases.json` maps historical run IDs to stage folders. Each stage keeps reference settings and its actual migrated case configurations. Case outputs and executables remain in the external run root. The 66 supplied settings records are configuration references, not full namelist/build provenance. B0–B2 archives are retained as historical evidence rather than invented new experiments.

The old `dt_b67_*` and `dt_b6_*` names are B3 bands, columns 6–7 and 6 respectively. There is no B6.7. The migration replaces their configuration names with `dt_b3_band67_*` and `dt_b3_band6_*`, preserving old run archive paths.
