## Fixed

- Added a governed Python 3.12 document-ingestion extra with MarkItDown PDF
  conversion, pdfplumber extraction, and PyMuPDF inspection/rendering; added the
  pre-commit runner to the declared development toolchain.
- Made the lock recipe preserve its controlled header and pinned the cleared
  ingestion and hook versions so a clean environment reconstructs the same tools.

## Financial impact

None. This changes environment and document-ingestion tooling only; financial
logic, scenario inputs, and canonical KPI calculations are unchanged.
