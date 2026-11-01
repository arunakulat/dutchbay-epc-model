- The levered tax pass now deducts the interest paid on the balloon after maturity
  (#1505). It deducted only scheduled interest (`interest_usd`), so the interest inside
  `balloon_resolution` (the refinanced tranche's, a sweep's or a bullet's) reduced no
  taxable income, although the three-statement P&L books it as an expense. The basis is
  a new scenario input, `tax.balloon_interest_tax_basis`: `paid` (the owner's decision
  and the default when the key is absent: deducted in the year it is settled in cash,
  so interest a sweep capitalises counts in the later year that pays it), `accrued`
  (deducted as it accrues) or `none` (the treatment before). `tax.interest_deductibility:
  false` still switches every interest deduction off. `debt_result` gains
  `balloon_interest_paid`, the per-period interest settled inside `balloon_resolution`
  (capitalised interest first), and each enriched row gains `balloon_interest_accrued_usd`
  and `balloon_interest_paid_usd`. The non-resident interest WHT gross-up now also charges
  the balloon interest paid (off in every committed scenario). The deduction reaches the
  sizing pass and the equity pass. The levered-CFADS sizing loop's iteration ceiling rises
  from 25 to 200, because a sweep's tax saving is swept again as interest paid, so that
  correction shrinks only by the marginal tax rate per pass (17 passes on the base case
  at 30%, about 90 at a 90% stress rate). On the canonical lender case equity IRR moves -26.44%
  to -23.01%, LLCR 1.2875 to 1.2905 and PLCR 1.3283 to 1.3342; project IRR, NPV, CFADS,
  min DSCR and the facility do not move. Cash-swept cases that clear their balloon gain a
  little equity (sinohydro_lean -6.26% to -6.06%, kalpitiya -6.07% to -5.87%,
  eia_prudent -8.89% to -8.81%) and those that never clear retire more of it. None of
  these figures supports a lender, IC, covenant or Board representation while the F-5
  and #1110 holds stand.
