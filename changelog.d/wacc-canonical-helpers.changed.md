# changelog.d/wacc-canonical-helpers.changed.md
- **WACC helpers consolidated onto the engine's canonical implementations** —
  `finance/wacc_v14.py` no longer carries private mirrors of `_as_float_or_none`,
  `_pct_to_decimal` and `get_nested`; it imports them from `finance.cashflow_v14_utils`
  (the cfb3908 "reuse the engine's exact resolution" doctrine). The mirrors had drifted:
  wacc's `_pct_to_decimal` still silently mapped impossible `>100` inputs (`150 → 1.5`,
  pre-#573 heuristic) where the canonical helper fail-louds, and its `get_nested` was
  case-sensitive where the cashflow engine resolves case-insensitively — so a title-case
  scenario (`Tax:`) priced tax into cashflow but silently dropped it from the WACC
  build-up. Byte-identical for every valid input (≤ 100) on canonical lower-case configs;
  canon oracle pins pass. Three coverage tests updated to assert both the new early
  out-of-range gate and wacc's own (still-reachable) range checks.
