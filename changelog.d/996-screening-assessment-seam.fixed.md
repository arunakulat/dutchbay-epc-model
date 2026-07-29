- **Async location assessment no longer collides with the frozen lender-case P50 (#996)** —
  the async wind job (`app/jobs/runner.py`) seeds its finance scenario from the frozen
  lender-case base, so a freshly computed P75 tripped BOTH frozen guards:
  `WindAdapterDriftError` (fresh capacity factor vs the frozen `0.332`) and
  `AepReconciliationError` (vs the frozen `464.3` P50). The assessment now declares its run
  `screening`-grade (config-first via `resolve_run_mode`), so the service seam adopts the
  assessment's own capacity factor (overwrite) and skips the frozen-bankable reconciliation
  — a live screening assessment computes its own AEP and has no frozen bankable reference.
  The wind adapter gains a `physical_only` mode so a (possibly stale) wind export can never
  overwrite or veto the scenario's own tariff/FX (#996 Problem #2; mirrors the solar
  adapter, which carries no commercial fields). Authored lender/developer runs are unchanged
  and byte-identical: they keep the strict drift-check and reconciliation. This is the first
  dolphin toward the versioned ResourceAssessment/CaseSnapshot layer; production
  `expected_results` and the downside-debt P90/P50 wiring are untouched and follow in later
  dolphins (D3–D5).
