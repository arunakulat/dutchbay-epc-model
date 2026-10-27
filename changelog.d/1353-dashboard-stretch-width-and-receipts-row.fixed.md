- **The sensitivity dashboard stops passing `use_container_width`** — both call sites in
  `analytics/dashboard/streamlit_app.py` now pass `width="stretch"`, the replacement Streamlit's
  own deprecation notice prescribes. The pinned `1.66.1` still accepts the old parameter, so
  nothing was broken, but it warned on every render and its announced removal date, 2025-12-31,
  had already passed; a later minor release may drop it outright. (#1353 P-8, with the reason
  corrected under D-9 before this fragment compiled.)
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
