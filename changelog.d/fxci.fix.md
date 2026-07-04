- CI: un-broke the FX Integration Tests workflow (red since the #800 freeze
  refresh first met it on PR #803, which merely woke its path filter — the
  Test Suite gate was green throughout). Root cause, empirically bisected: the
  dotted `--cov=analytics.fx` target under coverage 7.15/pytest-cov 7.1 resolves
  the package by importing it through the pip editable-install finder before
  `tests/conftest.py` runs; the conftest's `del sys.modules["analytics"]` +
  re-import then trips numpy's once-per-process extension guard at collection.
  Fixed by switching to the path-form target (`--cov=analytics/fx`, identical
  fx-only report, no import) and holding the workflow's ad-hoc test-tool pip
  line to the committed freeze via `-c constraints.txt` (#800 policy).
