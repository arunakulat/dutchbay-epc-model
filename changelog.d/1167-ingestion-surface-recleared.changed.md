- **`markitdown` 0.1.6 → 0.1.7 and `pymupdf` 1.28.0 → 1.28.2 — ingestion surface re-cleared;
  `magika` held, upstream-blocked** (#1167) — both are frozen by name in `constraints.txt` as
  document-ingestion reproducibility surfaces held "until a dedicated upgrade dolphin revalidates
  conversion, extraction, rendering, hooks, audit, and the suite", so this is a migration dolphin
  rather than the bot chore #1064 proposed. As with #1168, the freeze turned out to be enforced in
  **three** places — `constraints.txt`, `requirements.txt`, and hardcoded `version()` assertions in
  `tests/integration/test_ingestion_tooling.py` — and the third fired first, catching the install
  before the pins were updated. `pyproject.toml`'s ranges (`markitdown[pdf]>=0.1.6,<0.2`,
  `pymupdf>=1.28,<1.29`) already admit both targets and are unchanged. Re-clearance exercised the
  three surfaces the freeze names on one generated PDF: conversion through `MarkItDown().convert()`,
  extraction through `pdfplumber.extract_text()`, and rendering through `pymupdf.get_pixmap()`.
  **`magika` stays at 0.6.3**: every published markitdown release, 0.1.2 through the current latest
  0.1.7, pins `magika~=0.6.1`, so magika 1.x cannot enter the lock at any markitdown version — the
  half of #1064 that was never mergeable. It is now blocked at source by a Dependabot ceiling rule.
