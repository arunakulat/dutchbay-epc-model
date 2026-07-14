# External-methodology validation: the five untested areas (#964)

Status: **Validated** (2026-07-14). This is a **provenance / verification record**, not a
decision, and it changes **no computed KPI**. It closes the gap the 2026-07-12 external
credibility pass left open: four headline methods were confirmed against outside sources and
one material gap (wind AEP) was flagged, but **five** areas "rested on the internal read
only" — neither externally confirmed nor refuted — and one characterisation (QMC
star-discrepancy) did not survive verification. This file grounds each of those five methods
in a real external source and records an **executable** cross-check that re-derives the engine
against an independent reference.

Every cross-check below is backed by a running test in
`tests/research/test_methodology_validation_5areas.py`. Each test compares the engine to an
**independent** computation (`scipy`, `numpy_financial`, or a published closed form), never to
a restatement of the engine's own arithmetic (NO SPURIOUS PASS). Where a validation surfaced a
genuine discrepancy it is **flagged here**, not silently patched into the engine (§6).

## Why this file exists

The credibility report §5 / §7 confirmed the *debt-sizing concept*, *SL tax*, *Monte-Carlo
correlation disclosures*, and *global sensitivity*, and flagged *wind AEP* as the one material
bankability gap. It explicitly listed five areas that carried no outside citation:

1. Returns numerics (IRR / NPV robustness)
2. Covenants / DSRA dynamics (the fund-at-close DSRA was **not** corroborated as a gap)
3. Tail-risk estimators (CVaR / Wilson / Conover CIs)
4. Solar AEP (IEC 61724-1 / IEA-PVPS Task 13)
5. FX / curtailment

Left uncited, a headline method is only as trustworthy as the internal read. This file supplies
the outside citation and the executable check for each.

## Validation record

| # | Area | Engine surface | External source (real) | Cross-check (test) | Verdict |
|---|------|----------------|------------------------|--------------------|---------|
| 1 | **Returns numerics** | `finance/irr.py` — `npv`, `irr`, `xirr` | `numpy-financial` reference IRR; Brealey, Myers & Allen, *Principles of Corporate Finance* (NPV = Σ CF_t/(1+r)^t; IRR = NPV root) | `test_npv_matches_textbook_discounted_sum`, `test_irr_matches_numpy_financial_and_zeros_npv`, `test_irr_matches_numpy_financial_on_negative_return_series`, `test_xirr_matches_hand_solved_dated_example` | **Confirmed.** Engine IRR agrees with `numpy_financial` to 1e-9 on both a positive and a value-destructive (negative-IRR) conventional series, and the returned rate zeroes NPV. XIRR recovers the hand-solved Act/365.25 rate. The engine's extra guards (multi-root rejection, negative-IRR bracket) are supersets of the reference, exercised elsewhere. |
| 2 | **Covenants / DSRA** | `finance/debt_v14.py` DSRA funding; `analytics/mc/convergence.py` breach-probability Wilson CI | Yescombe, *Principles of Project Finance*, 2nd ed. (DSRA funded at financial close, typically the next **6 months** of debt service, topped from the waterfall, released at maturity); NREL ATB 2024 financial-case DSCR anchors (already in `docs/knowledge_base/05_project_finance_methodology.md`, #620a) | `test_breach_probability_wilson_ci_brackets_the_point`; behavioural funding already pinned by `tests/finance/test_dsra_fund_at_close.py` | **Confirmed — NOT a gap.** Fund-at-close, 6-month, waterfall-topped DSRA is the market-standard structure, not an omission; this corroborates the open question the credibility report raised. The lender term-sheet confirmation remains a tracked business deferral in `docs/STANDARDS_WATCH.md` item 2 (that is a *confirmation*, not a methodology gap). |
| 3 | **Tail-risk estimators** | `analytics/core/risk_metrics.py` (CVaR/ES); `analytics/mc/convergence.py` (`_wilson_interval`, `_order_stat_ci_ranks`) | Rockafellar & Uryasev (2000), "Optimization of Conditional Value-at-Risk," *J. Risk* 2(3):21-41; Acerbi & Tasche (2002), "On the coherence of expected shortfall," *J. Banking & Finance* 26:1487-1503; Wilson (1927), *JASA* 22:209-212; Conover, *Practical Nonparametric Statistics*, 3rd ed.; Hahn & Meeker, *Statistical Intervals* | `test_cvar_equals_acerbi_tasche_tail_mean`, `test_cvar_matches_rockafellar_uryasev_minimisation`, `test_wilson_interval_matches_scipy_binomtest`, `test_order_statistic_ci_achieves_binomial_coverage` | **Confirmed.** CVaR/ES matches BOTH the Acerbi–Tasche tail-mean definition (deterministic, exact) and the independent Rockafellar–Uryasev variational minimisation. The Wilson interval is byte-equal to `scipy.stats.binomtest(...).proportion_ci(method="wilson")`; the Conover order-statistic CI achieves ≥ 0.95 exact binomial coverage (conservative, never anti-conservative). The small-sample tail caveats the code documents are unchanged and correct. |
| 4a | **FX** | `finance/cashflow_v14_fx.py` `_forward_curve`; `analytics/fx/fx_builder.py` `compute_fx_risk_profile` VaR | Covered interest parity, F_t = S_0·((1+r_dom)/(1+r_for))^t (Bekaert & Hodrick, *International Financial Management*, no-arbitrage forward) | `test_cip_forward_curve_matches_covered_interest_parity`, `test_fx_var_is_residual_hard_currency_exposure_times_shock` | **Confirmed.** The forward curve is exactly the CIP compounding path (t=0 = spot; positive rate differential depreciates LKR). The FX-VaR check **calls the real engine** `compute_fx_risk_profile` on a minimal multi-currency debt block and compares the returned VaR/CVaR to an INDEPENDENT hand computation of the parametric form (1−hedge)·(USD+CNY debt)·shock: the LKR leg is excluded as a natural hedge, the declared hedge reduces the exposed balance, and CVaR is the documented 1.5× normal-tail multiple. The LKR leg is set large and distinct from the hard-currency balance so the test **fails** on the historical inverted-exposure bug (recorded at `fx_builder.py:562-563`), on including or dropping the LKR leg, on dropping the (1−hedge) factor, or on changing the CVaR multiplier — each verified to break it. CVaR > VaR (coherence). |
| 4b | **Curtailment** | `finance/self_curtailment_v14.py` `resolve_self_curtailment_decimal` | CEB standardised PPA deemed-energy treatment (`docs/knowledge_base/02_dutch_bay_project_dossier.md` §4): grid-instructed curtailment PAID as deemed energy | `test_deemed_paid_curtailment_never_haircuts_and_seam_is_default_off`, `test_only_self_curtailment_is_wired_deemed_paid_is_excluded` | **Confirmed.** Grid-instructed (deemed-paid) curtailment never haircuts revenue; only physical self-curtailment is a real energy loss; two results with identical self-curtailment but very different deemed-paid shares resolve to the same haircut. The seam is default-off (byte-identical canon when the opt-in is absent). |
| 5 | **Solar AEP** | `analytics/core/exceedance.py`; `solar_resource/exceedance.py` | IEC 61724-1:2021 (PV system performance monitoring); IEA-PVPS Task 13, "Uncertainties in Yield Assessments of PV Systems" (2018) — normal-quantile exceedance P_x = P50·(1 − z_x·σ/100); root-sum-of-squares category combination | `test_exceedance_z_table_matches_normal_quantiles`, `test_solar_exceedance_matches_iec_normal_quantile_closed_form`, `test_solar_systematic_sigma_is_root_sum_of_squares` | **Confirmed.** The shared P75/P90/P95/P99 z-table equals `scipy.stats.norm.ppf`; the producer's P75/P90 (1-year and project-life) exceedance energies reproduce a closed form built ENTIRELY from independent pieces — `scipy.stats.norm.ppf` z-quantiles and the raw category 1-sigmas reduced by the published RSS + interannual (÷√N) combination, using neither the engine z-table nor the engine `exceedance_value` helper; the rho=0 category combination is exactly the RSS of the 1-sigmas (rho=1 → the fully-correlated linear sum). Ordering (P50 > P75 > P90; P90-life > P90-1yr) holds. |

## §6 — Flagged: the QMC star-discrepancy characterisation (documented, not patched)

The credibility report noted that "the QMC star-discrepancy characterisation did not survive
verification and is unconfirmed." Verified here against the LHS literature:

- **Where.** `analytics/sensitivity/optimizer.py` (the `build_lhs_plan` docstring, ~L242-244)
  describes its `scipy.stats.qmc.LatinHypercube` sampler as "formal LHS with **Koksma-Hlawka
  error bounds**."
- **The issue.** The Koksma–Hlawka inequality bounds quasi-Monte-Carlo (QMC) integration error
  by the integrand's variation × the point set's **star discrepancy**, and QMC low-discrepancy
  sequences (Sobol', Halton) achieve a star discrepancy of order (log N)^d / N. Plain Latin
  Hypercube Sampling is a **stratification / variance-reduction** scheme (Stein 1987,
  *Technometrics* 29(2):143-151, established variance reduction for additive integrands; Owen's
  scrambled-net results are a *separate* QMC construction). A generic scrambled LHS design does
  **not** attain the QMC star-discrepancy rate, so attributing "Koksma–Hlawka error bounds" to
  it conflates LHS with QMC. The **variance-reduction** benefit of LHS is real and correctly
  motivates the sampler; the **star-discrepancy / Koksma–Hlawka** framing is the unconfirmed
  part.
- **Materiality.** Cosmetic/documentation only. `build_lhs_plan` has **no** pipeline / report /
  committed-scenario caller (its sole consumer is the on-demand `run_pareto_search(plan_kind=
  "lhs")` tool), and no KPI depends on the discrepancy characterisation. The sampler itself
  (`scipy.stats.qmc.LatinHypercube`) is correct; only the docstring's justification is
  overstated.
- **Disposition.** Left for a separate, KPI-neutral docstring-wording dolphin (this issue is
  scoped to *adding* validation, not editing engine files). Recorded here so the finding is
  owned and dated rather than lost.

## Sources

- Issue #964 (audit, P2, provenance); 2026-07-12 external credibility report §5 / §7.
- `docs/STANDARDS_WATCH.md` (DSRA business-confirmation deferral, item 2).
- `docs/knowledge_base/05_project_finance_methodology.md` (DSCR / CVaR-Rockafellar-Uryasev /
  IEC exceedance citations already in the knowledge base).
- Primary literature cited inline in the table above and in
  `tests/research/test_methodology_validation_5areas.py`.
