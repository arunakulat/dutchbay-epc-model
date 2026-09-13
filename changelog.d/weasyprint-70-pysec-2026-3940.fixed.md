- Raise the `[report]` extra's WeasyPrint pin from 69.0 to 70.0, closing PYSEC-2026-3940, and add the
  CESSPIT pre-flight controls that make a half-applied pin bump fail fast rather than at render time
  or deep in a slow shard. The advisory is a `url_fetcher` bypass: `write_pdf(xmp_metadata=[url])` and
  `write_pdf(stylesheets=[url])` built a fresh default `URLFetcher()` instead of the document's, so a
  restrictive fetcher was silently ignored, giving arbitrary local file read and a transitive SSRF
  through the `@import`/`url()` graph. Only the URL form of `stylesheets=` was ever fetcher-mediated;
  a bare path went to `open()` in both versions. Reproduced against the pinned 69.0 on both channels
  and confirmed fixed on 70.0, alongside a control showing the same sheet loaded via
  `<link rel=stylesheet>` was correctly blocked on both — so the difference is the patched channel,
  not a misconfigured fetcher. This repository was not exposed: no `url_fetcher` is configured
  anywhere, so there is no restriction to bypass; `xmp_metadata` is never passed; and the single
  `stylesheets=` call site in `app/reports/dbpl/print_core.py` passes already-constructed `CSS`
  objects, which skips the vulnerable branch. The bump was taken because the advisory is real and the
  fix is cheap, not because an exploit path was found — though it is not discretionary either: the
  pre-bump lock fails `make security` outright, so this restores a mandatory CI gate.
- The pin lives in **five** places, and the count was wrong twice before it was right. Three are the
  dependency files — `requirements.txt`, `constraints.txt` and the `pyproject.toml` `[report]` extra —
  which must move together because the third is executable: it is baked into distribution metadata
  that `app.ops.extras.probe_extra` reads back as `declared_spec`, so leaving it behind would not be a
  paperwork mismatch but a `DbplDependencyError` from `require_dbpl_stack()` on every DBPL PDF, per
  DBPL-01. The fourth is a string literal in an integration guard,
  `tests/integration/test_report_jobs_tooling.py`, which broke CI on this change's first push. The
  fifth is prose in `docs/MODULE_REFERENCE.md`, a lender/DFI due-diligence surface that is kept in
  sync with `pyproject` — its `[jobs]` and `[grid]` entries match exactly — so `[report]` alone was
  left contradicting. All five are updated here.
- Operational note for anyone pulling this: re-run `pip install -e '.[report]'`. An editable install
  does not refresh `METADATA` when `pyproject.toml` changes, so refreshing only the lock leaves stale
  metadata and `require_dbpl_stack()` raises on every DBPL PDF until the reinstall. CI is unaffected —
  every workflow installs the lock and then the editable extras, which regenerates it.
- Rendering is equivalent, not identical, and the difference is a fix. Across the DBPL call surface
  the two versions agree on `%PDF-1.7`, PDF/UA marking, `/StructTreeRoot`, `/Lang`, page count,
  MediaBoxes portrait and landscape, the structure-tree tag sequence and the embedded font subsets.
  They necessarily differ in `/Producer` and the XMP packet, because WeasyPrint stamps its own version
  into both — an earlier draft of this note claimed "identical output" off an equal byte *count*,
  which holds only because "69.0" and "70.0" are the same length. The one layout difference found is a
  line-breaking bug fix in 70.0: 69.0 subtracted an offset twice against an already-sliced
  `log_attrs`, so it stopped hyphenating a line early. Page and line counts were unchanged across
  every configuration tested.
- `weasyprint` 70.0 declares requirements byte-identical to 69.0, so no transitive pin moves and every
  existing lock line still satisfies it.
- The controls, and what they do not reach. `tests/lint/test_extra_pin_consistency.py` asserts that
  constraints never contradict the lock — ceilings such as `pandas<3` included, not only `==` pins —
  that every declared extra specifier is satisfied by the locked version, that the complete DBPL stack
  is locked and within its pin, and that no integration guard asserts a version the lock contradicts.
  Parsing goes through `packaging` and PEP 503 normalisation, and a line it cannot parse is a hard
  failure: a first version matched only `^name==version$`, and three independent reviewers defeated it
  with an environment marker, an extras group, a `--hash=` suffix, spaces around `==`, a `-r` include,
  and a name respelling — each hiding a real disagreement while every control passed. Integration
  literals are read with `ast` rather than a regex, so a comment mentioning an old version no longer
  turns the suite red and a stale assert followed by a correct one no longer hides behind it. Two
  extras, `[pareto]` and `[solar]`, check nothing because their packages are deliberately absent from
  the lock; that gap is now declared in the control and fails in both directions rather than
  presenting as two passing checks. The prose declaration in `docs/MODULE_REFERENCE.md` is outside any
  automated check and stays a review responsibility.
- Each control was observed to fail before being relied on. Reverting `requirements.txt` alone fails
  four controls, `constraints.txt` alone one, the `pyproject` extra alone two, and the integration
  literal alone one; nineteen further mutants drawn from three independent reviews are each killed,
  and two guard-the-guard controls reject a parser or scanner that has gone blind.
