- **F5-01 construction-period parity restored** — an explicitly present empty
  `debt: {}` mapping again keeps the historical two-period debt default instead of
  falling through to a conflicting top-level `construction_periods` value.
