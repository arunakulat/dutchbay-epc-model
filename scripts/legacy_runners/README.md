# scripts/legacy_runners/

Holding pen for pre-Sprint-19 Hydra CLIs that were never wired into the
canonical v14 production flow.

## Current contents

| Script | Purpose | Status |
|---|---|---|
| `run_wind_download_v14.py` | ERA5 download only (no analysis, no AEP, no export) | Legacy — Hydra `config_path="conf"` points to a non-existent directory; only usable from a working directory that aliases `./conf/`. Kept for git-history reference. |
| `run_complete_analysis_fixed.py` | Pre-Sprint-9 "do everything" wind runner | Legacy — superseded by `wind_resource.WindPipeline` + `scripts/run_wind_analysis_v14.py`. |

## What moved out

`run_wind_analysis_v14.py` was promoted in Sprint 19 (W.5) to:

```
scripts/run_wind_analysis_v14.py
```

That script is now the **canonical wind-export producer** — it emits a
frozen JSON consumed by `wind_resource.cashflow_adapter` and (in W.6) by
`run_full_pipeline_v14.py`.

## Should I use anything in this directory?

Probably not. If you need ERA5 data, use `WindPipeline.fetch_era5_data()`.
If you need the full assessment, use the promoted runner above.

This directory is preserved purely to keep `git log --follow` working
for archaeology against the Palette refactor (commit `979520b`,
Feb 24 2026) which is the lineage of most Sprint 18 defects.
