- **Four dependency bumps in one lock change, two frozen surfaces re-cleared** — `pymupdf`
  1.28.2 → 2.0 with `markitdown` 0.1.8 → 0.1.9 (the ingestion surface), `hiredis` 3.4.2 → 3.5.0
  (the report/jobs surface), `soupsieve` 2.9.2 → 3.0.4 and `pandera` 0.32.1 → 0.34.1. They replace
  Dependabot's #1440, #1441, #1443 and #1444 so the lock costs one full CI run instead of four.
  `pymupdf`, `markitdown` and `hiredis` are frozen by name in `constraints.txt`, so all three
  freeze sites move together: `constraints.txt`, `requirements.txt` and the hardcoded `version()`
  assertions in `tests/integration/test_ingestion_tooling.py` and
  `tests/integration/test_report_jobs_tooling.py`.
- **`pymupdf` 2.0 adds three packages to the lock**: `pymupdf_layout==2.0` and `pymupdf4llm==2.0`
  (empty compatibility shells, since 2.0 now carries the layout and 4llm code itself) and
  `tabulate==0.10.0`. Its other new requirements (`networkx`, `numpy`, `onnxruntime`, `pyyaml`,
  `psutil`) were already pinned. #1440 omitted all three, so its lock was not closed. 2.0 fixes
  CVE-2026-82035 (path traversal in the PyMuPDF command-line font extraction, which this
  repository does not call). The `[ingestion]` range in `pyproject.toml` moves from
  `pymupdf>=1.28,<1.29` to `pymupdf>=2.0,<2.1`. Licence is unchanged (AGPL-3.0 or Artifex
  commercial). `import pymupdf` now loads the layout analyser and `onnxruntime` eagerly.
- **`soupsieve` 3.0 is a major release.** Its two breaking changes (strict `:has()` and ordered
  custom selectors) touch no code path here: this repository never imports `bs4` or `soupsieve`,
  and no installed dependent passes a `:has()` selector or custom selectors.
- `pandera` arrives only through `pandapower` (`pandera~=0.32`), which admits 0.34.1.
