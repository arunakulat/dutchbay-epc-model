- Raise the `certifi` pin in the reproducibility lock from `2026.7.22` to `2026.10.19`, which
  fixes PYSEC-2026-4320 (GHSA-6q48-6c7w-9gw2) and clears it from the `pip-audit` leg of the
  `Security Scan` gate. No abstract dependency changes: `pyproject.toml` does not constrain
  `certifi`, and nothing else in the lock caps it.
- Allowlist the eight advisories against `pillow==12.3.0` in `PIP_AUDIT_IGNORES`, the variable the
  `Makefile` reserves for a genuinely capped CVE, so the gate stops failing every pull request on
  a finding none of them can fix. The eight are fixed only in `pillow 13.0.0`; every `streamlit`
  release up to `1.66.0`, the latest on PyPI, requires `pillow<13`; and PyPI has no `pillow`
  release between `12.3.0` and `13.0.0`. The entries carry their reason in the `Makefile` and come
  out the moment `streamlit` lifts the cap.
- Each of the eight needs attacker-chosen TIFF, GIF, PPM/PGM or EPS input, or a third-party PDF
  appended to through `Image.save(..., format="PDF", append=True)`, and no untrusted-input path in
  this repository reaches them. No module here imports PIL, and both `pdfplumber.open` calls read
  PDFs this repository generated itself; `contextily` does decode fetched basemap tiles through
  `PIL.Image.open`, which sniffs format from the response bytes, so that path depends on the tile
  service rather than on the tile type. The allowlist records a capped finding, not an accepted
  exposure.
