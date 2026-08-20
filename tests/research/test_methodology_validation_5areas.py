"""External-methodology validation for the five areas that rested on the internal read only (#964).

The 2026-07-12 credibility pass confirmed four headline methods against outside sources
(debt-sizing concept, SL tax, MC correlation disclosures, global sensitivity) and flagged
one material gap (wind AEP). It left **five** areas neither externally confirmed nor
refuted, plus one unverified characterisation. This module closes that gap with executable
cross-checks: each engine method is re-derived against an INDEPENDENT external reference
(``scipy``, ``numpy_financial``, or a published closed-form) and asserted equal, so every
headline method now carries an outside citation backed by a running test — not a re-statement
of the engine's own arithmetic.

Areas covered (issue #964, credibility report §5 / §7):

1. Returns numerics (IRR / NPV robustness)
   - ``finance.irr.irr`` vs the ``numpy_financial`` reference IRR on a conventional series,
     and vs the NPV-root definition (NPV at the returned rate ≈ 0).
   - ``finance.irr.npv`` vs the textbook discounted-cashflow sum.
   - ``finance.irr.xirr`` vs a hand-solved dated example (Act/365.25).

2. Tail-risk estimators (CVaR / Wilson / Conover CIs)
   - ``TailRiskAnalyzer.calculate_var_cvar`` CVaR/ES vs the Acerbi–Tasche tail-mean
     definition AND the Rockafellar–Uryasev variational (minimisation) form.
   - ``analytics.mc.convergence._wilson_interval`` vs ``scipy.stats.binomtest`` Wilson CI.
   - ``analytics.mc.convergence._order_stat_ci_ranks`` (Conover / Hahn–Meeker order-statistic
     CI) vs the exact ``scipy.stats.binom`` coverage.

3. Solar AEP (IEC 61724-1 / IEA-PVPS Task 13)
   - ``analytics.core.exceedance.EXCEEDANCE_Z`` vs ``scipy.stats.norm.ppf``.
   - ``solar_resource.exceedance.exceedance_levels_solar`` P75/P90 vs the IEC/IEA-PVPS
     normal-quantile closed form and the root-sum-of-squares category combination.

4. FX / curtailment
   - ``finance.cashflow_v14_fx._forward_curve`` vs the covered-interest-parity closed form.
   - ``analytics.fx`` FX-VaR parametric form (residual hard-currency exposure × shock).
   - ``finance.self_curtailment_v14.resolve_self_curtailment_decimal`` — the CEB SPPA
     deemed-energy treatment: grid-instructed (deemed-paid) curtailment NEVER haircuts
     revenue; only physical self-curtailment is a real loss, and the seam is default-off.

5. Covenants / DSRA dynamics
   - A near-zero-noise breach-probability Wilson CI (the covenant-breach estimator a lender
     reads) — the numeric backing for the fund-at-close 6-month DSRA cross-check documented
     in ``docs/METHODOLOGY_VALIDATION_5AREAS.md`` (behavioural funding is already pinned by
     ``tests/finance/test_dsra_fund_at_close.py``; not duplicated here).

Every assertion compares the engine to an independent computation, never to itself. This is
verification only — it imports and exercises existing code and changes no engine number
(KPI-neutral). Citations are recorded in ``docs/METHODOLOGY_VALIDATION_5AREAS.md``.
"""

from __future__ import annotations

import math
from datetime import datetime

import numpy as np
import numpy_financial as npf
import pytest
from scipy.optimize import minimize_scalar
from scipy.stats import binom, binomtest, norm

from analytics.contracts_v14 import (
    QSTS_CONTROLLED_OUTPUT_CLASS,
    QSTS_RUN_MANIFEST_SCHEMA,
    CurtailmentShareResult,
    QSTSRunManifest,
)
from analytics.core.exceedance import EXCEEDANCE_Z
from analytics.core.risk_metrics import RiskConfig, TailRiskAnalyzer
from analytics.fx.fx_builder import compute_fx_risk_profile
from analytics.fx.fx_contracts import FXCurveOutput, FXStructuredBlock, FXVolumetry
from analytics.mc.convergence import (
    Z_95,
    _order_stat_ci_ranks,
    _wilson_interval,
    percentile_ci_diagnostic,
)
from finance.cashflow_v14_fx import _forward_curve
from finance.irr import irr, npv, xirr
from finance.self_curtailment_v14 import resolve_self_curtailment_decimal
from solar_resource.exceedance import SolarUncertaintyBudget, exceedance_levels_solar

# ═════════════════════════════════════════════════════════════════════════════
# 1. RETURNS NUMERICS — IRR / NPV / XIRR vs independent references
#    Ref: numpy-financial (reference IRR); Brealey/Myers/Allen, Principles of
#    Corporate Finance (NPV = discounted-cashflow sum, IRR = NPV root).
# ═════════════════════════════════════════════════════════════════════════════


def test_npv_matches_textbook_discounted_sum() -> None:
    """``finance.irr.npv`` equals the plain Σ CF_t / (1+r)^t discounting formula."""
    rate = 0.08
    cashflows = [-1000.0, 200.0, 300.0, 400.0, 500.0]
    reference = sum(cf / (1.0 + rate) ** t for t, cf in enumerate(cashflows))
    assert npv(rate, cashflows) == pytest.approx(reference, rel=1e-12)


def test_irr_matches_numpy_financial_and_zeros_npv() -> None:
    """Engine IRR agrees with numpy_financial on a conventional series and zeroes the NPV."""
    cashflows = [-1000.0, 300.0, 300.0, 300.0, 300.0, 300.0]
    engine = irr(cashflows)
    reference = float(npf.irr(cashflows))
    assert engine is not None
    # Two independent solvers must agree on the unique real root.
    assert engine == pytest.approx(reference, rel=1e-9)
    # And it must actually be a root: NPV at the returned rate is ~0.
    assert npv(engine, cashflows) == pytest.approx(0.0, abs=1e-6)


def test_irr_matches_numpy_financial_on_negative_return_series() -> None:
    """A value-destructive series (Σ inflows < outlay) yields the same negative IRR as npf."""
    # 5 x 150 back < 1000 out -> genuinely negative project IRR (the DutchBay regime).
    cashflows = [-1000.0, 150.0, 150.0, 150.0, 150.0, 150.0]
    engine = irr(cashflows)
    reference = float(npf.irr(cashflows))
    assert engine is not None
    assert engine < 0.0
    assert engine == pytest.approx(reference, rel=1e-9)


def test_xirr_matches_hand_solved_dated_example() -> None:
    """Dated XIRR (Act/365.25) recovers a rate that zeroes XNPV for a two-flow example."""
    dates = [datetime(2020, 1, 1), datetime(2021, 1, 1)]
    cashflows = [-1000.0, 1100.0]
    rate = xirr(cashflows, dates)
    assert rate is not None
    # Exactly one year apart at Act/365.25: (1+r)^(366/365.25) = 1.1  (2020 is a leap year).
    years = (dates[1] - dates[0]).days / 365.25
    expected = 1.1 ** (1.0 / years) - 1.0
    assert rate == pytest.approx(expected, rel=1e-6)


# ═════════════════════════════════════════════════════════════════════════════
# 2. TAIL-RISK ESTIMATORS — CVaR/ES, Wilson, Conover order-statistic CI
#    Refs: Rockafellar & Uryasev (2000) J. Risk 2(3):21-41 (CVaR minimisation);
#    Acerbi & Tasche (2002) J. Banking & Finance 26:1487-1503 (ES = tail mean);
#    Wilson (1927) JASA 22:209-212; Conover, Practical Nonparametric Statistics,
#    3rd ed.; Hahn & Meeker, Statistical Intervals (order-statistic CI).
# ═════════════════════════════════════════════════════════════════════════════


def _analyzer() -> TailRiskAnalyzer:
    return TailRiskAnalyzer(
        RiskConfig(
            confidence_level=0.95,
            target_return=0.0,
            min_dscr=1.2,
            min_llcr=1.0,
            min_plcr=1.0,
        )
    )


def test_cvar_equals_acerbi_tasche_tail_mean() -> None:
    """CVaR/ES(95%) is the mean of the worst 5% of trials (Acerbi–Tasche definition).

    On 1..100 the 5th-percentile VaR is the 6th order statistic (=6) and the ES is the
    mean of the five worst (=3). Deterministic, so this pins the estimator to the
    published definition exactly (no sampling noise, no self-reference).
    """
    returns = np.arange(1, 101, dtype=float)
    result = _analyzer().calculate_var_cvar(returns, "project_irr")
    assert result.var == pytest.approx(6.0)
    assert result.cvar == pytest.approx(np.mean([1.0, 2.0, 3.0, 4.0, 5.0]))


def test_cvar_matches_rockafellar_uryasev_minimisation() -> None:
    """Engine CVaR equals the Rockafellar–Uryasev variational form on the loss side.

    RU (2000): CVaR_α(L) = min_c [ c + E[(L-c)+] / (1-α) ], with L = -return (the loss).
    The engine reports the lower-tail ES of the returns, so engine ``-cvar`` must equal
    the RU minimum of the losses. Independent of the tail-mean check above (a different
    formula), so agreement is real evidence, not a tautology.
    """
    rng = np.random.default_rng(7)
    returns = rng.normal(0.05, 0.03, size=2000)
    alpha = 0.95
    engine = _analyzer().calculate_var_cvar(returns, "equity_irr").cvar

    losses = -returns

    def ru_objective(c: float) -> float:
        return c + float(np.mean(np.maximum(losses - c, 0.0))) / (1.0 - alpha)

    opt = minimize_scalar(
        ru_objective,
        bounds=(float(losses.min()), float(losses.max())),
        method="bounded",
    )
    ru_cvar_of_losses = ru_objective(opt.x)
    # engine CVaR is on returns; RU value is on losses -> negate to compare.
    assert -engine == pytest.approx(ru_cvar_of_losses, rel=5e-3)


def test_wilson_interval_matches_scipy_binomtest() -> None:
    """Engine Wilson score interval matches scipy's independent implementation.

    Covers a small-count rare-event proportion (3/100) and the boundary 0/n case where
    the naive Wald interval degenerates — exactly the covenant-breach regime the estimator
    exists for.
    """
    for k, n in [(3, 100), (0, 20), (17, 250), (1, 1000)]:
        lo, hi = _wilson_interval(k, n, Z_95)
        ref = binomtest(k, n).proportion_ci(confidence_level=0.95, method="wilson")
        assert lo == pytest.approx(ref.low, abs=1e-12)
        assert hi == pytest.approx(ref.high, abs=1e-12)


def test_order_statistic_ci_achieves_binomial_coverage() -> None:
    """Conover/Hahn–Meeker order-statistic ranks achieve >= nominal binomial coverage.

    For the placed 1-indexed ranks [l, u), the exact coverage of the p-quantile is
    P(l-1 <= Binomial(n,p) < u) via ``scipy.stats.binom``. The outward floor/ceil rounding
    makes it conservative (>= 0.95), never anti-conservative — the whole point of a
    lender-facing tail claim.
    """
    for n, p in [(1000, 0.90), (500, 0.95), (2000, 0.90)]:
        lo, hi = _order_stat_ci_ranks(n, p, Z_95)
        assert lo is not None and hi is not None
        coverage = float(binom.cdf(hi - 1, n, p) - binom.cdf(lo - 1, n, p))
        assert coverage >= 0.95
        # And it should not be wildly over-wide (still a usable, tight interval).
        assert coverage <= 0.99


def test_breach_probability_wilson_ci_brackets_the_point() -> None:
    """The covenant-breach Wilson CI (percentile_ci_diagnostic) brackets its own point.

    Backs the DSRA / covenant cross-check: a lender reads P(DSCR < floor) with a Wilson CI.
    Verified against scipy on the SAME breach count the diagnostic computes.
    """
    rng = np.random.default_rng(0)
    dscr = rng.normal(1.40, 0.10, size=1000)
    floor = 1.285
    out = percentile_ci_diagnostic(
        {"dscr": dscr.tolist()}, breach_thresholds={"dscr": floor}
    )
    block = out["dscr"]["breach_probability_ci"]
    n_breaches = int(block["n_breaches"])
    ref = binomtest(n_breaches, 1000).proportion_ci(
        confidence_level=0.95, method="wilson"
    )
    assert block["method"] == "wilson"
    assert block["ci_lower"] == pytest.approx(ref.low, abs=1e-12)
    assert block["ci_upper"] == pytest.approx(ref.high, abs=1e-12)
    assert block["ci_lower"] <= block["point"] <= block["ci_upper"]


# ═════════════════════════════════════════════════════════════════════════════
# 3. SOLAR AEP — IEC 61724-1 / IEA-PVPS Task 13 exceedance build-up
#    Refs: IEC 61724-1:2021 (PV system performance monitoring); IEA-PVPS Task 13,
#    "Uncertainties in Yield Assessments of PV Systems" (2018). Normal-quantile
#    exceedance P_x = P50 * (1 - z_x * sigma_pct/100); RSS category combination.
# ═════════════════════════════════════════════════════════════════════════════


def test_exceedance_z_table_matches_normal_quantiles() -> None:
    """The shared P75/P90/P95/P99 z-table equals the standard-normal inverse CDF (scipy)."""
    for level in (75, 90, 95, 99):
        assert EXCEEDANCE_Z[level] == pytest.approx(
            float(norm.ppf(level / 100.0)), abs=5e-5
        )
    assert EXCEEDANCE_Z[50] == 0.0  # the median


def test_solar_exceedance_matches_iec_normal_quantile_closed_form() -> None:
    """P75 / P90 (1-year and project-life) reproduce the IEC/IEA-PVPS closed form.

    The producer ``exceedance_levels_solar`` is compared to a reference built ENTIRELY from
    independent pieces — ``scipy.stats.norm.ppf`` for the exceedance z-quantiles and the raw
    category 1-sigmas reduced by the published root-sum-of-squares (systematic) + interannual
    (÷√N over life) combination — with NO use of the engine z-table (``EXCEEDANCE_Z``) or the
    engine ``exceedance_value`` helper. So this genuinely anchors the producer to the outside
    closed form P_x = P50·(1 − z_x·σ/100), not to the engine's own arithmetic. (The z-table
    and the RSS combination are separately anchored to scipy by the two adjacent tests.)
    """
    budget = SolarUncertaintyBudget()
    p50 = 100.0
    result = exceedance_levels_solar(p50, budget, life_years=20)

    # Independent 1-sigma: RSS of the seven systematic categories, then combined with the
    # interannual term (un-averaged at 1yr; ÷√20 over the 20-year life).
    systematic = math.sqrt(
        budget.ghi_dataset_pct**2
        + budget.transposition_pct**2
        + budget.pv_simulation_pct**2
        + budget.soiling_pct**2
        + budget.module_power_tolerance_pct**2
        + budget.thermal_model_pct**2
        + budget.availability_pct**2
    )
    sigma_1yr = math.sqrt(systematic**2 + budget.interannual_ghi_variability_pct**2)
    sigma_life = math.sqrt(
        systematic**2 + (budget.interannual_ghi_variability_pct / math.sqrt(20.0)) ** 2
    )
    z75 = float(norm.ppf(0.75))
    z90 = float(norm.ppf(0.90))

    # rel=1e-4 absorbs only the engine z-table's 4-dp rounding vs scipy's full-precision
    # ppf (~4e-6 here); any real regression (wrong z, dropped sigma, sign flip) moves these
    # by percent, far outside the tolerance.
    assert result.p75_gwh == pytest.approx(
        p50 * (1.0 - z75 * sigma_1yr / 100.0), rel=1e-4
    )
    assert result.p90_1yr_gwh == pytest.approx(
        p50 * (1.0 - z90 * sigma_1yr / 100.0), rel=1e-4
    )
    assert result.p90_life_gwh == pytest.approx(
        p50 * (1.0 - z90 * sigma_life / 100.0), rel=1e-4
    )
    # Ordering the standard guarantees: higher exceedance probability -> lower energy.
    assert result.p50_gwh > result.p75_gwh > result.p90_1yr_gwh
    # Project-life P90 sits ABOVE the 1-year P90 (interannual term averaged over sqrt(N)).
    assert result.p90_life_gwh > result.p90_1yr_gwh


def test_solar_systematic_sigma_is_root_sum_of_squares() -> None:
    """rho=0 category combination is the IEC/IEA-PVPS root-sum-of-squares of the 1-sigmas."""
    budget = SolarUncertaintyBudget()
    systematic = (
        budget.ghi_dataset_pct,
        budget.transposition_pct,
        budget.pv_simulation_pct,
        budget.soiling_pct,
        budget.module_power_tolerance_pct,
        budget.thermal_model_pct,
        budget.availability_pct,
    )
    rss = math.sqrt(sum(s**2 for s in systematic))
    assert budget.systematic_sigma_pct(0.0) == pytest.approx(rss)
    # rho=1 collapses to the fully-correlated linear sum (the upper bound).
    assert budget.systematic_sigma_pct(1.0) == pytest.approx(float(sum(systematic)))


# ═════════════════════════════════════════════════════════════════════════════
# 4. FX / CURTAILMENT
#    Refs: covered interest parity, F_t = S_0 * ((1+r_dom)/(1+r_for))^t (standard
#    international-finance relation); CEB standardised PPA deemed-energy treatment
#    (docs/knowledge_base/02_dutch_bay_project_dossier.md §4).
# ═════════════════════════════════════════════════════════════════════════════


def test_cip_forward_curve_matches_covered_interest_parity() -> None:
    """The FX forward curve is exactly the covered-interest-parity compounding path."""
    r_lkr, r_usd = 0.12, 0.06
    spot_0 = 300.0
    config = {
        "Financing_Terms": {"rates": {"lkr_nominal": r_lkr, "usd_nominal": r_usd}}
    }
    curve = _forward_curve(config, 5, spot_0)
    ratio = (1.0 + r_lkr) / (1.0 + r_usd)
    expected = [spot_0 * ratio**t for t in range(5)]
    assert curve == pytest.approx(expected, rel=1e-12)
    # t=0 forward is spot; a positive rate differential depreciates LKR (rising LKR/USD).
    assert curve[0] == pytest.approx(spot_0)
    assert curve[-1] > curve[0]


def test_fx_var_is_residual_hard_currency_exposure_times_shock() -> None:
    """Engine FX VaR = (1 - hedge) x hard-currency debt x adverse shock (USD millions).

    Calls the REAL engine (``analytics.fx.fx_builder.compute_fx_risk_profile``) on a minimal
    multi-currency debt block and compares its returned VaR/CVaR to an INDEPENDENT hand
    computation of the parametric form: the LKR leg is a natural hedge (serviced from LKR
    revenue) and is EXCLUDED; only the USD+CNY balance carries FX cash risk; the declared
    hedge reduces that exposure; CVaR is the documented normal-tail multiple of VaR.

    The LKR leg is set large and DISTINCT from the hard-currency balance so this fails on
    the historical regressions (the code comment at fx_builder.py:562-563 records a prior
    inverted-exposure bug that based VaR on the hedged LKR leg): it FAILS if someone
      * inverts the exposure to the LKR leg      (40M -> VaR 9.0, not 18.0),
      * includes the LKR leg in the exposure      (120M -> VaR 27.0, not 18.0),
      * drops the (1 - hedge) factor              (no hedge -> VaR 24.0, not 18.0), or
      * changes the CVaR multiplier off 1.5        (CVaR != 27.0).
    """
    # LKR-denominated (USD-equiv): natural hedge, serviced from LKR revenue -> EXCLUDED.
    total_debt_lkr = 40_000_000.0
    # USD (incl. DFI=USD): hard currency, mismatched vs LKR revenue -> exposed.
    total_debt_usd = 60_000_000.0
    # CNY: hard currency, mismatched vs LKR revenue -> exposed.
    total_debt_cny = 20_000_000.0
    hedge_coverage_pct = 25.0
    # Adverse LKR/USD move (fx.uncertainty_pct), as a decimal fraction.
    var_shock_pct = 0.30

    fx_block = FXStructuredBlock(
        volumetry=[
            FXVolumetry(
                period=0,
                total_debt_lkr=total_debt_lkr,
                total_debt_usd=total_debt_usd,
                total_debt_cny=total_debt_cny,
            )
        ],
        revenue_currencies=["LKR"],
        hedging_coverage_pct=hedge_coverage_pct,
    )
    fx_curve = FXCurveOutput(years=[0], lkr_usd=[300.0])

    profile = compute_fx_risk_profile(
        fx_block=fx_block, fx_curve=fx_curve, var_shock_pct=var_shock_pct
    )

    # INDEPENDENT reference: only the hard-currency (USD + CNY) balance is exposed; the LKR
    # leg is excluded as a natural hedge; the declared hedge reduces the exposed balance.
    hard_currency_exposure = total_debt_usd + total_debt_cny  # LKR deliberately omitted
    residual = hard_currency_exposure * (1.0 - hedge_coverage_pct / 100.0)
    expected_var = residual * var_shock_pct / 1e6
    expected_cvar = expected_var * 1.5  # documented normal-tail multiple

    assert expected_var == pytest.approx(18.0)  # 80M x 0.75 x 0.30 / 1e6
    assert profile.var_95_usd_million == pytest.approx(expected_var)
    assert profile.cvar_95_usd_million == pytest.approx(expected_cvar)
    assert profile.cvar_95_usd_million == pytest.approx(27.0)
    # CVaR/ES must dominate VaR (coherence) — the FXRiskProfile contract enforces this.
    assert profile.cvar_95_usd_million > profile.var_95_usd_million
    # The LKR leg is genuinely PRESENT in the block (a real, non-zero denomination share)
    # yet contributes nothing to the VaR above — that is the natural-hedge exclusion.
    assert profile.debt_lkr_pct == pytest.approx(100.0 * 40.0 / 120.0)
    assert profile.debt_usd_pct == pytest.approx(50.0)


_METHODOLOGY_FEEDER_PATH = "/real/feeder.dss"
_METHODOLOGY_EVIDENCE_PATH = "/real/qsts-evidence.json"
_METHODOLOGY_EVIDENCE_SHA256 = "d" * 64


def _methodology_qsts_receipt() -> QSTSRunManifest:
    """Return a canonical-contract receipt for this arithmetic-only test double."""

    return QSTSRunManifest(
        schema=QSTS_RUN_MANIFEST_SCHEMA,
        package_id="methodology-curtailment-contract-double",
        input_kind="engineer_prepared_site_model",
        output_class=QSTS_CONTROLLED_OUTPUT_CLASS,
        payload_sha256=(("feeder/Master.dss", "e" * 64),),
        evidence_manifest_sha256=_METHODOLOGY_EVIDENCE_SHA256,
        finance_wiring_mode="canonical",
        finance_wiring_enabled=True,
        canonical_finance_eligible=True,
    )


def _curtailment_result(self_pct: float, deemed_pct: float) -> CurtailmentShareResult:
    return CurtailmentShareResult(
        ran=True,
        feeder_source=_METHODOLOGY_FEEDER_PATH,
        feeder_input_kind="engineer_prepared_site_model",
        generated_input=False,
        observed_network_data=False,
        site_representative=True,
        canonical_finance_eligible=True,
        evidence_manifest_sha256=_METHODOLOGY_EVIDENCE_SHA256,
        qsts_run_manifest=_methodology_qsts_receipt(),
        self_curtailed_pct=self_pct,
        deemed_paid_pct=deemed_pct,
        bankable=False,
        reason="methodology arithmetic contract double; not site or lender evidence",
    )


def test_deemed_paid_curtailment_never_haircuts_and_seam_is_default_off() -> None:
    """CEB SPPA deemed-energy treatment: grid-instructed curtailment is PAID, not deducted.

    With the finance-wiring opt-in absent (every committed scenario) the resolver returns
    0.0 regardless of any curtailment — the KPI-neutral canon.
    """
    result = _curtailment_result(self_pct=5.0, deemed_pct=40.0)
    # Default-off: no enable key -> 0.0 even with 40% deemed + 5% self curtailment.
    assert resolve_self_curtailment_decimal({}, result) == 0.0
    assert resolve_self_curtailment_decimal(None, result) == 0.0


def test_only_self_curtailment_is_wired_deemed_paid_is_excluded() -> None:
    """When enabled, ONLY self_curtailed_pct feeds the loss key; deemed_paid_pct is ignored.

    Two results with identical self-curtailment but very different deemed-paid shares must
    resolve to the SAME haircut — proof the deemed-energy (paid) leg never haircuts revenue.
    """
    enabled = {
        "grid": {
            "qsts": {
                "enabled": True,
                "input_kind": "engineer_prepared_site_model",
                "feeder_model_path": _METHODOLOGY_FEEDER_PATH,
                "evidence_manifest_path": _METHODOLOGY_EVIDENCE_PATH,
                "evidence_manifest_sha256": _METHODOLOGY_EVIDENCE_SHA256,
                "finance_wiring": {
                    "enabled": True,
                    "mode": "canonical",
                    "canonical_eligible": True,
                },
            }
        }
    }
    low_deemed = _curtailment_result(self_pct=5.0, deemed_pct=0.0)
    high_deemed = _curtailment_result(self_pct=5.0, deemed_pct=60.0)

    haircut_low = resolve_self_curtailment_decimal(enabled, low_deemed)
    haircut_high = resolve_self_curtailment_decimal(enabled, high_deemed)

    assert haircut_low == pytest.approx(0.05)  # 5% self-curtailment -> 0.05 decimal
    assert haircut_low == haircut_high  # deemed-paid share has zero effect
