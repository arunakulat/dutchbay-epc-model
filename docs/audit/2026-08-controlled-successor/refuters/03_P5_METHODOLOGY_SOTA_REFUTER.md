# Independent Refuter — P5 Methodology and State-of-the-Art Claims

**Cutoff:** 2026-08-12
**Audit source:** `/Users/aruna/Downloads/DutchBay_Comprehensive_Audit_2026-08`
**Repository:** `arunakulat/dutchbay-epc-model@7e99f34d75b9c3d44a5c5b260cedbe403d2f79e8`
**Posture:** read-only adversarial source-and-code review

## Headline disposition

The P5 assertions that DutchBay is at-to-above state of the art across all four dimensions, deserves 9/10, was directly benchmarked to primary sources throughout, contains no surviving methodological overclaim, and cannot affect any canonical KPI are **refuted**.

Several mechanics do conform to conventional formulas or locked library behavior. That is materially narrower than research or transaction state of the art. The pack lacks replicated RQMC error estimation, project-specific convergence and sample-adequacy evidence, calibrated dependence/tail analysis, exact empirical expected-shortfall treatment for atoms, a defensible lender percentile convention, complete wind-uncertainty taxonomy/covariance, and transaction-specific DSCR/LLCR definitions. It also failed to adjudicate all ten architecture pointers assigned to P5.

## Claim-level dispositions

| Claim | Disposition | Corrected conclusion |
|---|---|---|
| P5-HDL-001 — all dimensions at/above SOTA | `refuted` | Selected mechanics conform to common published or library implementations; no research-SOTA or bankability conclusion follows. |
| P5-HDL-002 — 9/10 and primary-source benchmarked | `refuted` | Withdraw the score; use claim-level evidence, versions, sections, hashes, status, limitations, and reproductions. |
| P5-HDL-003 — no canon KPI affected | `refuted` | Potential effects on Pxx, DSCR, LLCR, IRR, and tail metrics have not been excluded. |
| P5-MC-001 — default `iman_conover` is substantively correct | `partially_confirmed` | The default is approximate Gaussian-score rank reordering, not the corrected Iman–Conover implementation implied by its label. |
| P5-MC-002 — scrambled Sobol proves a positive differentiator | `partially_confirmed` | The locked version uses a scrambled, power-of-two design correctly; declared SciPy floor compatibility, independent scrambles, error estimates, and project convergence remain gaps. |
| P5-MC-003 — Gaussian dependence is sufficient | `deferred` | Zero-tail-dependence is an unvalidated simplifying assumption; calibration or approved stress design is required. |
| P5-SA-001 — wrapper hardening is above SOTA | `partially_confirmed` | Useful engineering guards are present; output-dependent deletion can still bias the population, and hardening is not research SOTA. |
| P5-SA-002 — SA sample sizes/noise floor adequate | `deferred` | Sample adequacy and PAWN noise floor have no documented convergence or acceptance basis. |
| P5-RISK-001 — CVaR paths are exact and immaterial | `refuted` | The paths approximate lower-tail mean for continuous samples but are not exact probability-weighted expected shortfall with ties, floors, or mass points. Trial count does not cure the definition mismatch. |
| P5-RISK-002 — raw percentile labels match lender Pxx | `refuted` | Every KPI needs an explicit raw-quantile versus exceedance convention and adverse direction. |
| P5-WIND-001 — six-of-seven one-to-one IEC taxonomy mapping | `refuted` | The taxonomy is a simplified project-specific construct inspired by published work, not a complete IEC or Lee-and-Fields implementation. |
| P5-WIND-002 — one-rho formula is exact IEC/MEASNET convention | `refuted` | It is an optional non-negative equicorrelation special-case stress, not a general covariance model or confirmed standard prescription. |
| P5-WIND-003 — P50-to-P90 formula has no gap | `partially_confirmed` | The arithmetic is correct conditional on Gaussian relative error; the distribution choice is unvalidated. |
| P5-FIN-001 — pro-rata tranche sculpt is sufficient | `deferred` | It is the current assumption, neither cost-optimized nor confirmed against facility/intercreditor terms. |
| P5-FIN-002 — IRR/XIRR bisection has no gap | `confirmed` as a gap | Bisection is defensible with a valid bracket, but the fixed range and absolute USD-NPV tolerance are scale-sensitive; ordinary well-bracketed roots can return `None`. |
| P5-FIN-003 — DSCR convention is transaction-complete | `partially_confirmed` | The high-level identity is conventional; exact CFADS, fee, tax, reserve, working-capital, and DSRA treatment needs financing-document confirmation. |
| P5-FIN-004 — LLCR exactly matches textbook convention | `partially_confirmed` | The high-level identity is present, but loan-life window, bridge, rate, date, and DSRA conventions require transaction reconciliation. |
| P5-COV-001 — all ten assigned P5 pointers were completed | `refuted` | P5 closes no such full allocation; the controlled crosswalk below must be retained. |

## Ten-pointer P5 crosswalk

| Pointer | Disposition | Basis |
|---|---|---|
| RS-A14 | `deferred` | Pro-rata allocation implemented; facility/intercreditor and comparative schedule evidence absent. |
| RS-A15 | `confirmed` | Scale-sensitive IRR solver gap reproduced. |
| RS-B9 | `not_examined` | No dedicated contracts-surface or invariant review. |
| RS-C1 | `deferred` | Scrambled Sobol mechanics seen; replicated convergence/error performance unproved. |
| RS-C2 | `deferred` | Label mismatch and Gaussian limitations seen; calibrated dependence choice unproved. |
| RS-C8 | `deferred` | SALib wrapper conformance seen; sample sufficiency and bias controls unproved. |
| RS-D4 | `deferred` | Gaussian arithmetic conditionally correct; distribution choice unproved. |
| RS-D12 | `not_examined` | No pooled-versus-monsoon fit or AEP-tail comparison. |
| RS-E13 | `not_examined` | No Redis/ARQ integration execution or source adjudication. |
| RS-F10 | `not_examined` | No Hydra/composition claim adjudication. |

**Controlled totals:** one `confirmed`, five `deferred`, four `not_examined`.

## Minimum reproduction programme

1. Compare LHS with at least eight independent scrambled-Sobol replicates at increasing powers of two; report bias, RMSE, tail-quantile error, achieved dependence, error estimates, and runtime.
2. Measure achieved Pearson and Spearman matrices for default and corrected rank reordering; stress Gaussian versus t-copula or vine joint downside using calibrated data or an approved scenario design.
3. Run Sobol, Morris, and PAWN convergence and rank-stability tests over increasing sample size and seeds, including non-finite exclusion diagnostics and null-factor controls.
4. Test VaR/CVaR on arrays with ties, floors, clipped outcomes, zeros, and mass points against a fractional-boundary expected-shortfall implementation.
5. Build a complete wind uncertainty register and heterogeneous covariance matrix; compare Gaussian, lognormal, and defensible positive/skew alternatives for P90/P95/P99 and finance KPIs.
6. Reconcile LLCR period by period against transaction-defined maturity, outstanding debt, CFADS window, bridge, DSRA, and discount convention.

Until these are completed, P5 may describe specific implementation mechanics but must not restore a blanket SOTA score or numerical-immateriality assertion.
