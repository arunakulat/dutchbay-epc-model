# Legacy Scripts Archive

**Date:** 2025-12-13  
**Reason:** Cleanup for v14 focus

This directory contains:
- Experimental scripts from development phases
- Duplicate versions of production files (e.g., cashflow_v14.py, evaluation_v14.py)
- One-off debugging/testing utilities
- Phase artifacts and SWIMLANE process documentation

## Status

These files are kept for **historical reference only** and should NOT be used in production.

For v14 production work, use the canonical files in:
- `run_full_pipeline_v14.py` (repo root)
- `run_scenario_analytics_v14.py` (repo root)
- `analytics/pipeline_v14.py`
- `analytics/evaluation_v14.py`

## If You Need Something

Check if the file exists in the main directories first. If you genuinely need a legacy version, 
restore from git history: `git log --all --full-history -- <filename>`
