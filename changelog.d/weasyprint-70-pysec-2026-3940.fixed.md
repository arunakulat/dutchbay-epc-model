- Raise the `[report]` extra's WeasyPrint pin from 69.0 to 70.0, closing PYSEC-2026-3940, and add
  the CESSPIT pre-flight controls that make a half-applied pin bump fail fast rather than at render
  time or deep in a slow shard. The advisory is a `url_fetcher` bypass: `write_pdf(xmp_metadata=[url])`
  and `write_pdf(stylesheets=[url_or_path])` built a fresh default `URLFetcher()` instead of the
  document's, so a restrictive fetcher was silently ignored, giving arbitrary local file read and a
  transitive SSRF through the `@import`/`url()` graph. Reproduced against the pinned 69.0 and
  confirmed fixed on 70.0 with the same script, alongside a control showing the same sheet loaded
  via `<link rel=stylesheet>` was correctly blocked on both — so the difference is the patched
  channel, not a misconfigured fetcher. This repository was not exposed: no `url_fetcher` is
  configured anywhere, `xmp_metadata` is never passed, and the single `stylesheets=` call site in
  `app/reports/dbpl/print_core.py` passes already-constructed `CSS` objects, which skips the
  vulnerable branch. The bump was taken because the advisory is real and the fix is cheap, not
  because an exploit path was found. WeasyPrint 70.0 declares requirements byte-identical to 69.0,
  so no transitive pin moves; the rendered call surface the DBPL print core uses produces identical
  output, still PDF/UA-marked, tagged and language-set.
- The pin turned out to live in **four** places, not three, and the fourth is what broke CI. Three
  are the dependency files — `requirements.txt`, `constraints.txt` and the `pyproject.toml`
  `[report]` extra — and those must move together because the third is executable: it is baked into
  distribution metadata that `app.ops.extras.probe_extra` reads back as `declared_spec`, so leaving
  it behind would not be a paperwork mismatch but a `DbplDependencyError` from `require_dbpl_stack()`
  on every DBPL PDF, per DBPL-01. The fourth is a string literal in an integration guard,
  `tests/integration/test_report_jobs_tooling.py`, which asserted `version("weasyprint") == "69.0"`;
  it is updated here. Nothing checked either kind of agreement before, so
  `tests/lint/test_extra_pin_consistency.py` now asserts both: that constraints never contradict the
  lock and that every declared extra specifier is satisfied by it, and separately that no integration
  guard asserts a version the lock contradicts. Each control was observed to fail before being relied
  on — the three half-applied dependency bumps fail two, one and two controls respectively, and
  reverting the integration literal reproduces the CI failure in the fast lint suite instead of a
  40-minute shard. Two guard-the-guard controls reject a parser or scanner that silently matched
  nothing.
