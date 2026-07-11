- **Documentation refresh (README, development guide, schema).** Rewrote `README.md` to
  drop non-standard styling, correct the architecture tree (`monte_carlo/` holds scenario
  YAMLs not engine code; generated outputs are git-ignored; `api/` vs `app/api/` explained),
  and add `Development` and `Deployment` sections that link the new development guide and the
  deploy runbook. Added `docs/DEVELOPMENT.md` (setup, quality gates, contribution workflow,
  concurrency/worktrees, CI topology, governance). Corrected `schema.md` to state it documents
  only the EPC cost-basis parameters and to point to the authoritative config-schema modules
  (`analytics/config_schema.py`, `analytics/schema_guard.py`). Documentation only; no engine
  or financial behaviour changed.
