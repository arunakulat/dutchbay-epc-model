- Size the senior facility, and report DSCR, LLCR and PLCR, on CFADS bearing the levered
  tax the SPV actually pays (#1397, audit P2-F4-01). The pipeline built its sizing rows
  with `interest_expense=0`, so `plan_debt` sculpted against — and coverage was published
  from — CFADS carrying tax computed with no interest deduction. On the lender case the
  pre-change schedule carried LKR 36.76bn of interest over its 20 operating rows, deducted
  nowhere in that pass (the corrected, larger schedule carries LKR 39.38bn). It is worth
  USD 16.44M of coverage CFADS: the sizer saw USD 175.55M before and sees USD 191.99M now,
  both pre-fee. Sizing now runs as a fixed point: each pass feeds the
  previous schedule's interest back into the tax calculation and re-sizes, until the CFADS
  series settles to within USD 0.01 (the lender case converges in 7 passes); a schedule
  that has not settled within 25 passes is refused rather than published.
- **The interest is the only input that changed.** The sizing rows still carry no senior
  credit-support fee, exactly as before, so a scenario with `tax.interest_deductibility`
  off is byte-identical to the pre-change engine — every KPI to the last digit, pinned by
  a committed test. Sizing on pre-fee rows does overstate debt capacity, because the fee
  is senior to debt service, but that is architecture pointer RS-A8's finding and fixing
  it here would make the KPI delta below impossible to attribute.
- The project pass keeps its unlevered tax basis. A DSCR is a cash-coverage ratio with no
  WACC in it, so there is nothing for the interest shield to double count against; project
  NPV and IRR are discounted at an after-tax WACC that already carries the shield inside
  the cost of debt, and taking the deduction again there would double count it. Every
  annual row now publishes both bases: `cfads_usd` (unlevered, what the project pass
  discounts) and `cfads_coverage_usd` (levered, what the facility was sized and covenanted
  on).
- Canon re-baseline on `dutchbay_lendercase_2025Q4`: solved facility $59.59M → $63.37M
  (nine 0.0025 gearing steps), structural balloon $31.55M → $28.63M (fraction 0.458 →
  0.391), equity IRR -7.85% → -9.99%, project NPV -$91.81M → -$91.57M, prudential rate
  11.2858% → 11.1772%, prudential NPV -$96.44M → -$96.23M, project IRR -0.1166% →
  -0.1421%, total CFADS $166.08M → $165.69M, total equity distributed $44.49M → $32.64M
  and equity MOIC 0.4109 → 0.3124. Project IRR and total CFADS move **down**, and through
  the senior fee rather than the tax: a larger facility costs a larger credit-support fee,
  and the project rows bear it. The equity figures fall for the same reason compounded by
  the larger debt service the extra leverage carries. The headline `total_cfads_usd` stays on the project basis;
  emitting the coverage total as a KPI of its own would change the KPI contract and is not
  done here.
- Other committed scenarios move too, all through coverage rather than tax, because none
  of them declares a credit-support fee: Mullikulam equity IRR -18.59% → -19.20% with LLCR
  1.3109 → 1.3197, the 5 US-cent case equity IRR -15.62% → -16.18%, the two capex
  sensitivities LLCR 1.290 → 1.381 and 1.365 → 1.397, and the eight NSO250 LTL variants
  LLCR ≈1.873 → ≈1.898. In the NSO250 bid-implied variants `avg_dscr` reads 1.407 → 1.989
  on an unchanged facility: every sculpted period stays pinned at 1.30 and the whole move
  is the final amortising period, where the residual service is small enough that more
  CFADS multiplies the ratio (2.15 → 6.81).
- Known consequence, owner decision 2026-10-27, tracked as its own work item (#1353,
  issuecomment-6433557550): the headline `min_dscr` falls from 1.30 to 1.2196.
  `min_dscr_period` stays pinned at the 1.30 sculpt target; what reads low is the
  conservative annual `dscr_by_year` fold in operating year 1, which also carries the
  orphaned bridge service. The gearing solver `_solve_gearing_for_dscr` targets the
  per-period floor and does not bind that fold, so the nine steps the extra capacity buys
  all clear the floor while year 1 sits below it. The steps alone are not the whole
  account: the dip needs the senior credit-support fee too. At the pre-change facility
  with the fee the fold reads 1.30, and at the new larger facility with the guarantee and
  PRI rates zeroed it reads 1.30 again — only the larger facility together with the larger
  fee it costs drops it. That is the RS-A8 pre-fee/post-fee seam: the solve sculpts on
  pre-fee coverage CFADS while the year-1 fold nets the fee out of the cash and divides by
  that year's service plus the orphaned bridge period's. The owner's decision was to correct the
  CFADS basis and report the year-1 figure honestly rather than hold 1.30 by constraining
  the solver. The gap is pre-existing: `tests/finance/test_senior_fees.py` already recorded
  year 1 reading ~1.288 for the same reason.
- `analytics.optimization_v14` no longer dies mid-sweep on a candidate it cannot score.
  The KPI surface drops `equity_irr` when the waterfall ran and no rate solves the equity
  cashflows (#1436's deliberate `None`, distinct from "not computed"), and the optimizer
  read it with `kpis[key]`, so one such candidate raised `KeyError` and took the whole
  optimization with it. A deeply geared point whose every operating year is covenant-locked
  is exactly that candidate, and the levered-tax basis brings more of them into reach — the
  solar assessment report's gearing sweep to 0.75 hit one. An unscorable candidate now reads
  `nan` and is marked infeasible, which is the vocabulary the bounded search and the
  infeasibility diagnostics already speak; a warning names the KPI and the parameter value,
  so a mistyped `objective_key` surfaces rather than disappearing into "no feasible optimum".
  No substituted 0.0: a 0.0 equity IRR reads as break-even (#782).
