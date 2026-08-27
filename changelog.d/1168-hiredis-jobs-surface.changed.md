- **`hiredis` 3.4.0 → 3.4.1 — the jobs surface re-cleared, not just re-pinned** (#1168) —
  `hiredis` is frozen by name in `constraints.txt` as part of the report/jobs closure
  "cleared together under Python 3.12", so lifting it is a migration dolphin rather than a
  bot chore. The freeze is enforced in **three** places, not the two the issue anticipated:
  `constraints.txt`, `requirements.txt`, and a hardcoded `version("hiredis") == "3.4.0"`
  assertion in `tests/integration/test_report_jobs_tooling.py` — which is what caught the
  install before the pins were updated. All three now agree. Re-clearance exercised the
  surface the freeze names rather than asserting it: the async job store, worker, backend
  gate and analysis router all pass against a live Redis, and a real round-trip confirms
  `_HiredisParser` is the parser actually serving the connection, so the accelerated C path
  is genuinely in use rather than silently falling back to pure Python. `redis==5.3.1` still
  satisfies arq's `redis[hiredis]<6,>=4.2.0` ceiling and the pinned transitive closure does
  not move — the resolver plan is `hiredis-3.4.1` alone.
