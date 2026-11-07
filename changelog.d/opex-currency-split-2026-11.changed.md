- Opex split by currency (15.19.0 -> 15.20.0). Owner rule of 2 Nov 2026: "all CAPEX is fixed at
  project start in LKR. The debt will be in LKR. However, a percentage of OPEX will be in USD".
  Work item #1353 comment 6702129557.
  - `finance.cashflow_v14_params` reads an optional `opex.currency_split`: `usd_share` (or
    amount-weighted `components`, each `usd_per_year` or `usd_per_unit_year` x `units`, with its
    own `usd_share`), `usd_escalation_pct`, `lkr_escalation_pct` (percent, always) and an optional
    `usd_lkr_depreciation_pct`: a percent, or `relative_ppp` to derive it from the two inflation
    inputs, `(1 + lkr) / (1 + usd) - 1`. It fails loud on unknown keys, out-of-range values, both or
    neither of `usd_share` and `components`, and an `opex.escalation_pct` that disagrees with
    `lkr_escalation_pct`.
  - `finance.cashflow_v14_production.opex_for_year` is the one opex line both row builders call.
    The USD share escalates in USD and is translated at the year's model FX, or on its own path
    (the financial-close spot depreciating at `usd_lkr_depreciation_pct`, advanced through
    construction as the model curve is). The LKR share is fixed in LKR at the financial-close FX
    and escalates at LKR inflation. Without the block the line is the original expression; a
    repr-exact KPI comparison over all 32 runnable committed scenarios is identical.
  - Blue Whale wind v0.4: wind O&M 350k at 70% USD, insurance, land and SPV 150k LKR (49% USD);
    USD 2.5%/yr, LKR 5%/yr, USD share on relative PPP, 2.44%/yr (owner, 2026-11-07). Project IRR
    10.81% -> 12.41%, equity IRR 8.63% -> 10.54%, project NPV USD 69,109 -> 1,342,632
    (construction period +1,312,984; opex split -39,461).
  - Blue Whale solar + BESS v0.5: BESS O&M at USD 1.80/kWh-yr on 22,000 kWh DC (39,600; was
    USD 2.5/kWh-yr on 20,000 kWh), converted to LKR at the wind project's value date (333.79,
    LKR 13,218,084/yr; owner, 2026-11-07); every line in LKR; total 256,655 -> 246,255.2.
    Against 15.19.0 (with the turbine's shadow): project NPV USD -4,997,611 -> -4,517,261
    (construction period +389,782; opex +90,568); equity IRR -8.44% -> -7.00%.
  - Both Blue Whale projects set `Financing_Terms.construction_periods: 1`, equal to their
    `timeline.construction_years` (input B30). The engine reads the period only from
    `Financing_Terms` and had defaulted to 2 for the debt drawdown, interest during
    construction and the FX start (owner, 2026-11-07: "Set 1 year for the whole model now").
    The superseded hybrid keeps the default. The sizing runs are
    not re-run; the test that ties the scenario to them now evaluates it on their opex basis.
