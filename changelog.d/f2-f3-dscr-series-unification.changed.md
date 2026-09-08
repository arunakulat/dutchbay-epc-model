- **F2/F3 DSCR contract:** `plan_debt.dscr_series` now spans the full debt
  timeline; `dscr_periods` associates each period with its operating year and
  folded per-year covenant coverage. The raw alias and compact ScenarioResult
  series remain compatible. Missing or invalid published labels fail loudly.
  Headline DSCR preserves both the operating-period minimum and the per-year
  fold. Covenant breach years/counts and status can change; the CEB capacity-charge
  case now reports FAIL after recognizing its year-one folded breach. Model
  version 15.5.0 records this public-contract and covenant-reporting change.
  No canon rebaseline, release, or existing HOLD is authorized by this change.
