- Revenue SSCL is no longer charged in the 15 scenarios that still charged it (#1874).
  The SSCL Act First Schedule exempts the generation and supply of electricity other than by
  the Ceylon Electricity Board, so an IPP selling to CEB owes no SSCL on its revenue. The
  lender case has recorded this since #738. On 2026-11-22 the owner ruled that every scenario
  follows it. Each of the 15 now sets `statutory.social_services_levy_pct: 0.0` (was 0.025),
  and the Sri Lanka pack's disagreement inventory drops its 15 `discrepancy_for_owner` entries.
  The engine's revenue-levy mechanism stays for a scenario that does owe one.
  `regulatory.social_services_levy_pct`, which the engine does not read, is unchanged in the
  five files that carry it.
- **KPIs rise in all 15 scenarios.** Project IRR rises by 0.26 to 0.49 points, and sculpted
  debt grows where the DSCR sizing allows. Examples:
  - `dutchbay_basecase_2025Q4`: project IRR 4.20% to 4.52%, equity IRR -7.52% to -5.44%.
  - `dutchbay_lendercase_5usc_fixed_lkr`: project IRR -5.45% to -5.03%.
  - `blue_whale_wind_lot5b_2026`: project IRR 12.31% to 12.76%, project NPV USD 1.32M to 1.73M.
  - `kalpitiya_lendercase_160m_fitted`: project IRR 1.52% to 1.83%.

  The canonical lender case does not move. The PR has the full table.
- Two committed summaries are regenerated because they pin a changed scenario:
  `docs/blue_whale/wind_bess_options_summary.json` and
  `docs/blue_whale/solar_bess_project_sizing_summary.json`. Neither recommendation changes.
  Two solar + BESS alternatives, the best P50 project IRR and equity IRR, move to larger units.
  The KPI fixtures for the capex variants, the 5 US-cent case and Mullikulam are re-baselined.
- The refinanced-tranche lock-up test (#1779) changes case. The EIA-prudent variant's year 17
  now covers 1.18x, above a 1.10x threshold, so the threshold-not-floor control now uses the
  Sinohydro lean variant at 0.90x.
- Released as 15.32.0.
