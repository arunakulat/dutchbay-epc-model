- The debt engine's tenor, construction-period count and dual-DSCR capacity discount rate
  have no code default (#1429, second step; owner decision 2026-11-14). The engine used to
  fill an absent tenor with 15 years, an absent build time with two construction periods
  and an absent `Financing_Terms.interest_rate_nominal` with 8%, all Dutch Bay figures.
  Strict pre-flight (`validate_config_for_v14` with the `debt` module) now refuses a
  scenario that omits one, naming its YAML path, through
  `finance.debt_v14.resolve_debt_sizing_terms`, and the engine refuses again at each point
  of use. The capacity rate is required only under a DSCR sizing mode, where the autosolve
  reads it. The construction-period count may still come from `timeline.construction_years`
  alone; a scenario that declares it nowhere is refused.
- A declared value that is not a finite number is refused rather than replaced, and a YAML
  boolean is no longer read as a number (`true` used to become 1.0 for the gearing, the
  target DSCR and the downside factor, and one year for the tenor).
- `Financing_Terms.term_years`, which strict pre-flight already accepted as the tenor, is
  now read by the engine as well, so the two can no longer differ. The amortised upfront
  fee in the fee-inclusive cost of debt uses the same tenor, and refuses an absent or zero
  one instead of using 15 years.
- #1733 review lows: pre-flight scales a percentage gearing alias (`debt_pct`,
  `leverage_pct`) to the fraction the engine uses, and the amortize bisection takes its
  upper bound from the gearing the debt layer used, so a gearing declared only through an
  alias is no longer refused there after pre-flight accepted it.
- No figure moves. Every committed engine scenario already declares these terms: all
  scenarios that run on `main` give byte-identical KPIs, debt and equity results. Six
  committed files that declare no build time were already refused by strict pre-flight for
  other reasons; no build time is written into them. Test fixtures that leaned on the
  fallbacks now declare the values they were given, and the D3C success digest is re-pinned
  because its fixture now declares `debt.construction_periods` (main's engine gives the same
  digest with that fixture).
- `.test_durations` is regenerated so the suite's shard balancing times the current tree
  (#1514).
