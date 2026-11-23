- Widen the DFI workbook (`analytics/dfi_workbook/foundation.py`) quoted unit-token
  grammar to accept any transactional ISO 4217 currency code, SI energy/power/electrical
  unit, time unit, magnitude word (`k`, `m`, `mn`, `bn`, `tn`, etc.), ratio unit (`%`,
  `x`, `bps`), `<currency> <magnitude>` pair, or `X/Y` per-unit expression instead of a
  narrow hardcoded allowlist (#1906).
- Close four display-format residuals from the #1902 review: refuse numeric formats
  whose sections mix `%` or trailing scaling commas, restrict booleans to `General` only
  (while keeping `General` and `@` for text), require a `0` placeholder in every numeric
  section's integer part, and require trailing scaling commas to pair with a matching
  magnitude unit token.
- Commit a LibreOffice Calc displayed-value oracle fixture
  (`tests/fixtures/analytics/dfi_workbook_libreoffice_display_oracle.json`) verified in
  always-run parity tests and against live `soffice --headless` when available.
- Zero KPI or shipped pipeline impact (`analytics.dfi_workbook` is reached from no
  pipeline root). HOLD union unchanged: F-5, #1110, v15.6.1.
