- **`BANKABLE_MIN_CONCURRENT` no longer claims bankability at a third of the required
  campaign (#961)** — the ~4-month (2880-sample) constant was named for bankability while
  its own docstring conceded that a bankable campaign needs at least 12 months, so the name
  overclaimed against MEASNET v3.1 / IEC 61400-15-1:2025 by a factor of three. It is now
  `LENDER_DISCLOSURE_MIN_CONCURRENT` — the floor below which an estimate must not be shown
  to a lender at all — with the deprecated name kept as an alias. The real standard is now
  a named constant, `IEC_BANKABLE_MIN_CONCURRENT = 8760`. `MCPResult` gained
  `campaign_adequacy` and `concurrent_shortfall_to_iec_bankable`, so a campaign that clears
  the disclosure floor but falls short of the standards says so on the result and in
  `as_dict()` instead of passing silently. Gate behaviour is unchanged.
