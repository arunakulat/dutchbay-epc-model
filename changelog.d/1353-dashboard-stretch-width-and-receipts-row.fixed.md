- **The sensitivity dashboard stops passing `use_container_width`** — both call sites in
  `analytics/dashboard/streamlit_app.py` now pass `width="stretch"`. Streamlit's announced
  removal date for the parameter was 2025-12-31; the pinned `1.66.1` still accepts it, so this
  is pre-emptive rather than a repair, and any later minor release may drop it. (#1353 P-8.)
- **The dashboard's removed-API guard now covers that name, and has a negative control** —
  `tests/integration/test_dashboard_smoke.py` reads the dashboard text against one tuple of dead
  names, which `use_container_width` now joins, and a second test demonstrates the guard failing
  on source that carries a dead name. Before this, nothing distinguished a clean dashboard from a
  guard that read nothing. (#1353 P-9.)
- **The 22 October handover record states the real check population for #1372's head** — its
  receipts row read "20 checks success, 2 skipped", which accounts for 22 of the 23 runs
  `96cf5bb1` carried and omits a `Verification receipts (VERIFY-01)` failure that was re-run green
  before the merge. Corrected against the check runs, with the amendment noted in the record.
  (#1353 D-6.)
