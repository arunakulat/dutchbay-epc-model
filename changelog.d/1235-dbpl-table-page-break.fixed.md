- **DBPL tables survive page breaks under PDF/UA** — WeasyPrint's PDF/UA tag builder raised
  `ValueError: Table wrapper without a table` whenever a captioned table straddled a page boundary
  (a caption-only wrapper fragment was left on the previous page with no rows), so any DBPL document
  with a page-spanning table failed to render — and the print core fails loud, so there was no
  fallback. Every table (document control, revision history and each section table) is now wrapped in
  a `.dbpl-keep` block with `break-inside: avoid`, which WeasyPrint honours on that real block box
  where it ignores the same rule on the anonymous table-wrapper box, moving the table and its caption
  to the next page as a unit. A table taller than a page still splits normally, which the tag builder
  handles correctly. Regression-guarded in `tests/app/test_dbpl.py` and documented in
  `docs/dbpl_styleguide.md`.
