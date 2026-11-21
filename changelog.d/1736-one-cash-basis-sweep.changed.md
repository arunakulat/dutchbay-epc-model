- One cash basis now decides a cash sweep's post-maturity balloon payments and its senior-fee
  deferral, and the debt engine and the equity waterfall agree on it (#1736, owner ruling
  2026-11-15). The basis is the cash the SPV actually has: the year's cash after scheduled
  service and grossed-up interest WHT, on the equity-facing rows (the tax the SPV pays, every
  deduction taken), plus the cash it holds for the sponsor (the reserve, lockup-trapped cash
  and retentions). Before this the engine swept on the sizing-basis CFADS, which carries no
  senior fee and no fee deduction, while the waterfall paid from its own cash: in the year the
  balloon fell due the reserve release and any trapped cash went to equity while the balloon
  stayed unpaid, and the waterfall settled fee arrears the engine did not know about (and could
  hand them back to equity later). `plan_debt` takes the cash as `sweep_cash_usd`, the
  waterfall publishes it per year as `cash_available_for_balloon_usd`
  (`waterfall_sweep_cash`), and the pipeline iterates the two to a fixed point (USD 0.01 a
  period). On a cash sweep the waterfall now funds the balloon payment from lockup-trapped
  cash and then retentions before any sponsor cash call; other treatments are unchanged.
  Every fee paid is the engine's, so the tax deduction, project NPV, PLCR and the statements
  all carry it, and the `senior_fee_deferred_residual` KPI equals the engine's figure (no
  rename; the 43-key schema is unchanged). `plan_debt` warns when a deferred fee is still
  unpaid at the horizon, so a run with the waterfall off still says so. The reported
  `wht_on_interest` row column is now on the interest paid, whatever
  `tax.balloon_interest_tax_basis` deducts (#1539 DOM-4; the same figure on the default
  `paid` basis).
- **Equity KPIs move on the six committed scenarios that sweep a balloon after maturity**:
  `dutchbay_basecase_2025Q4` (equity IRR -3.14% to -7.52%, balloon residual USD 120.74M to
  104.46M), `dutchbay_master_config_v14` (2.07% to 1.51%), `dutchbay_optimistic_2025Q4` (1.71%
  to 1.11%), `dutchbay_lendercase_5usc_fixed_lkr` (-16.44% to -17.59%),
  `mullikulam_2x50mw_mannar` (-19.24% to -20.61%) and `kalpitiya_lendercase_160m_fitted`
  (-5.87% to -5.72%). Project IRR, DSCR and the sized debt do not move; LLCR and PLCR move in
  the fourth decimal place on some. The refinance lender case does not move. On the base
  case the equity IRR no longer responds to the corporate tax rate: its only taxed years are
  locked up, and their cash now pays the unpaid balloon (the tax lands on the balloon
  residual instead). Released as 15.29.0.
- Limit: a fee deferred and still unpaid is not accrued in the three statements (they carry
  the fee paid, as before).
