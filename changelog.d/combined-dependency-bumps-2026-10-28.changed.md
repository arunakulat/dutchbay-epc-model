- **Five dependency bumps in one lock change** — `starlette` 1.9.0 → 1.10.0, `types-pytz`
  2026.3.1.20260727 → 2026.5.0.20261006, `cryptography` 50.0.0 → 50.0.2, `debugpy` 1.8.21 →
  1.8.22 and `fonttools` 4.63.0 → 4.67.0. They supersede Dependabot's #1467, #1468, #1469, #1470
  and #1471 so the lock costs one full CI run instead of five. None of the five is frozen or
  capped in `constraints.txt`, and the lock gains and loses no package.
- **`cryptography` 50.0.2** only rebuilds its wheels against OpenSSL 4.0.3 (50.0.1 was 4.0.2).
- **`starlette` 1.10.0** stays inside streamlit's `<2` ceiling. Its behaviour changes (multidict
  equality keeps the order of repeated values, `FormMessage` is deprecated, `Config` strips one
  pair of outer quotes, `url_path_for()` keeps placeholder-like values) touch no code path here:
  the application never parses forms through Starlette, never compares `QueryParams` or
  `FormData`, and does not use `starlette.config`.
- `types-pytz` reaches the lock only through `pandas-stubs`; this repository never imports
  `pytz`. `debugpy` arrives through `ipykernel`. `fonttools` arrives through WeasyPrint
  (`>=4.59.2`) and matplotlib (`>=4.28.2`), both of which admit 4.67.0.
