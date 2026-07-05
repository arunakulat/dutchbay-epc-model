"""#737: annual credit-support fees on outstanding senior debt (fee-inside-sculpt).

The lendercase pays a DFI partial-credit-guarantee fee (75 bps/yr) and a PRI premium
(100 bps/yr), each on the OUTSTANDING (declining) senior debt balance
(``Financing_Terms.fees``). The combined 175 bps is:

- charged SENIOR to debt service (reduces CFADS),
- operations-period only (0 in construction and the synthetic bridge period),
- tax-deductible (it comes out at the EBITDA line, which feeds the tax engine),
- and sized INSIDE the DSCR sculpt — the gearing solve re-sizes the debt so the
  per-period DSCR series still holds the 1.30 target fee-inclusively (the rigorous
  "A" treatment). The CONSERVATIVE per-year covenant table reads year 1 slightly
  below target (~1.288) because it folds the orphaned bridge service into year 1 —
  reported honestly, see test_a_signature_dscr_holds_with_smaller_debt.

The empirical A-signature this file pins: with fees ON the per-period min DSCR
lands on target while CFADS / NPV / equity IRR drop AND the sized debt is SMALLER;
a pre-fee sizing ("B") would instead keep the debt and let the DSCR fall.

The fee-OFF variant must reproduce the pre-#737 canonical economics bit-for-bit —
the proof the feature is inert for every scenario that does not declare the keys.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict

import pytest

from analytics.pipeline_v14_enhanced import run_v14_pipeline
from analytics.scenario_loader import load_scenario_config
from finance.cashflow_v14 import build_annual_rows
from finance.debt_v14 import apply_debt_layer

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"

# Combined annual fee rate committed in the lendercase (75 bps PCG + 100 bps PRI).
FEE_RATE = 0.0075 + 0.01

# Pre-#737 canonical lendercase economics (the committed pins before the fees were
# switched on). The fee-OFF variant must reproduce them exactly: the #737 code path
# is a no-op without the config keys.
PRE_737_PROJECT_IRR = 0.02683686114665262
PRE_737_EQUITY_IRR = -0.048585780806075674
PRE_737_PROJECT_NPV = -65455817.14404039
PRE_737_TOTAL_CFADS = 202332872.38974944
PRE_737_DEBT_TOTAL = 71820000.0


def _fee_off_config() -> Dict[str, Any]:
    cfg = copy.deepcopy(dict(load_scenario_config(str(LENDER))))
    fees = cfg["Financing_Terms"]["fees"]
    del fees["guarantee_fee_pct_per_year"]
    del fees["pri_premium_pct_per_year"]
    return cfg


@pytest.fixture(scope="module")
def res_on() -> Dict[str, Any]:
    return run_v14_pipeline(config=str(LENDER), validation_mode="strict")


@pytest.fixture(scope="module")
def res_off() -> Dict[str, Any]:
    return run_v14_pipeline(config=_fee_off_config())


def test_fee_off_reproduces_pre_737_canon(res_off: Dict[str, Any]) -> None:
    """Deleting the fee keys reproduces the pre-#737 canonical economics exactly."""
    kpis = res_off["kpis"]
    assert kpis["project_irr"] == pytest.approx(PRE_737_PROJECT_IRR, abs=1e-12)
    assert kpis["equity_irr"] == pytest.approx(PRE_737_EQUITY_IRR, abs=1e-12)
    assert kpis["project_npv"] == pytest.approx(PRE_737_PROJECT_NPV, rel=1e-12)
    assert kpis["total_cfads_usd"] == pytest.approx(PRE_737_TOTAL_CFADS, rel=1e-12)
    debt = res_off["debt_result"] or {}
    assert debt["debt_total"] == pytest.approx(PRE_737_DEBT_TOTAL, rel=1e-12)
    # And the engine reports a zero fee stream.
    assert debt["senior_fee_rate"] == 0.0
    assert all(f == 0.0 for f in debt["senior_fee_usd"])


def test_fee_math_declining_outstanding_ops_only(res_on: Dict[str, Any]) -> None:
    """fee_t == 175 bps x the OPENING outstanding; 0 in construction + bridge."""
    debt = res_on["debt_result"] or {}
    fees = list(debt["senior_fee_usd"])
    outstanding = list(debt["debt_outstanding"])
    construction = int(debt["construction_years"])
    bridge = debt.get("cfads_bridge_debt_period")
    assert len(fees) == len(outstanding)
    positive = 0
    for period, (fee, bal) in enumerate(zip(fees, outstanding, strict=True)):
        if period < construction or (bridge is not None and period == int(bridge)):
            assert fee == 0.0, f"period {period} must carry no fee"
        else:
            assert fee == pytest.approx(FEE_RATE * bal, rel=1e-12), f"period {period}"
            positive += fee > 0.0
    assert positive >= 10  # the fee is live across the amortising life
    # Declining base: the outstanding balance never grows post-close, so the fee
    # is non-increasing across the live periods.
    live = [f for f in fees if f > 0.0]
    assert all(a >= b - 1e-9 for a, b in zip(live, live[1:], strict=False))


def test_a_signature_dscr_holds_with_smaller_debt(
    res_on: Dict[str, Any], res_off: Dict[str, Any]
) -> None:
    """Rigorous fee-inside-sculpt: min DSCR stays ON target while the debt shrinks."""
    on, off = res_on["kpis"], res_off["kpis"]
    debt_on = res_on["debt_result"] or {}
    debt_off = res_off["debt_result"] or {}
    # The per-period DSCR series holds the sculpt target fee-inclusively (the solver
    # re-sizes the gearing against the fee-netted series) — surfaced as
    # min_dscr_period since #790...
    assert on["min_dscr_period"] == pytest.approx(1.30, abs=1e-6)
    # ...and the KPI HEADLINE now agrees with the engine's fold-corrected covenant
    # minimum (#790): the two lender-facing surfaces can no longer diverge.
    assert on["min_dscr"] == pytest.approx(1.288, abs=0.005)
    # ...while the CONSERVATIVE per-year covenant table reads operating year 1 slightly
    # below it: year 1 covers its own service PLUS the orphaned half-year bridge service
    # out of fee-netted CFADS, and the fee consumed the pre-fee slack there (~1.306 ->
    # ~1.288). plan_debt's headline min_dscr (round-5 #3 fail-safe) reports that fold
    # honestly rather than hiding it behind the at-target per-period floor. (Binding the
    # fold in the gearing solve was tried and rejected — at interest_only_years=0 the
    # fold is quasi-insensitive to gearing and the solve degenerates; see
    # _solve_gearing_for_dscr.)
    assert debt_on["min_dscr"] == pytest.approx(1.288, abs=0.005)
    by_year = [v for v in debt_on["dscr_by_year"].values() if v is not None]
    assert min(by_year) >= 1.28
    # ...while the structure de-levers (the fee is inside the sizing)...
    assert debt_on["debt_total"] < debt_off["debt_total"]
    # ...and the economics honestly bear the fee.
    assert on["total_cfads_usd"] < off["total_cfads_usd"]
    assert on["project_npv"] < off["project_npv"]
    assert on["project_irr"] < off["project_irr"]
    assert on["equity_irr"] < off["equity_irr"]
    # Coverage ratios use the fee-netted CFADS numerator over the fee-sized debt.
    assert on["llcr"] < off["llcr"]
    assert on["plcr"] < off["plcr"]
    # Magnitude sanity: a 175 bps fee on a ~$70M declining facility is a
    # single-digit-percent CFADS haircut, not a rounding artifact and not a collapse.
    haircut = 1.0 - on["total_cfads_usd"] / off["total_cfads_usd"]
    assert 0.01 < haircut < 0.10


def test_rows_carry_the_fx_translated_fee(res_on: Dict[str, Any]) -> None:
    """senior_fee_lkr on each row == the engine's USD fee x that row's spot FX."""
    debt = res_on["debt_result"] or {}
    fees_usd = list(debt["senior_fee_usd"])
    row_to_period = {
        int(m["annual_row_index"]): int(m["debt_period"])
        for m in debt["annual_row_debt_period_map"]
    }
    rows = res_on["annual_rows"]
    total_fee_lkr = 0.0
    for idx, row in enumerate(rows):
        period = row_to_period[idx]
        expected = fees_usd[period] * float(row["fx_rate"])
        assert row["senior_fee_lkr"] == pytest.approx(expected, rel=1e-12), f"row {idx}"
        total_fee_lkr += row["senior_fee_lkr"]
    assert total_fee_lkr > 0.0
    # Year 1 hand-check: 175 bps on the post-IDC opening balance at year-1 spot FX.
    year1_period = row_to_period[0]
    year1_expected = (
        FEE_RATE * debt["debt_outstanding"][year1_period] * float(rows[0]["fx_rate"])
    )
    assert rows[0]["senior_fee_lkr"] == pytest.approx(year1_expected, rel=1e-12)


def test_fee_is_tax_deductible(res_on: Dict[str, Any], res_off: Dict[str, Any]) -> None:
    """The fee reduces taxable income year-by-year and total tax overall."""
    rows_on, rows_off = res_on["annual_rows"], res_off["annual_rows"]
    assert len(rows_on) == len(rows_off)
    for r_on, r_off in zip(rows_on, rows_off, strict=True):
        assert r_on["taxable_income_lkr"] <= r_off["taxable_income_lkr"] + 1e-6
    tax_on = sum(r["tax_lkr"] for r in rows_on)
    tax_off = sum(r["tax_lkr"] for r in rows_off)
    assert tax_on < tax_off
    # The aggregate saving is bounded by the statutory 30% CIT on the aggregate fee
    # (equality when every fee LKR is eventually deducted inside the horizon; less
    # when loss-carry-forward expiry forfeits some of the shield).
    total_fee_lkr = sum(r["senior_fee_lkr"] for r in rows_on)
    saving = tax_off - tax_on
    assert 0.0 < saving <= total_fee_lkr * 0.30 * 1.001
    # A no-tax year still bears the fee in CFADS: year 1 pays zero tax either way
    # (loss carry-forward) yet its CFADS is lower with the fee on.
    assert rows_on[0]["tax_lkr"] == rows_off[0]["tax_lkr"] == 0.0
    assert rows_on[0]["cfads_usd"] < rows_off[0]["cfads_usd"]


def test_builder_zero_series_is_byte_identical() -> None:
    """An explicit all-zero fee series builds bit-identical rows to None."""
    cfg = _fee_off_config()
    rows_none = build_annual_rows(cfg)
    rows_zero = build_annual_rows(cfg, senior_fee_lkr_series=[0.0] * len(rows_none))
    assert len(rows_none) == len(rows_zero)
    for r_a, r_b in zip(rows_none, rows_zero, strict=True):
        assert r_a == r_b


def test_negative_or_absurd_fee_rates_fail_loud() -> None:
    """CESSPIT: a negative or >=100%/yr fee is a config error, not a silent input."""
    base: Dict[str, Any] = {
        "Financing_Terms": {
            "construction_periods": 1,
            "tenor_years": 2,
            "debt_ratio": 0.5,
            "rates": {"usd_nominal": 0.08},
            "mix": {"usd_commercial_min": 1.0},
            "fees": {"guarantee_fee_pct_per_year": -0.0075},
        },
        "capex": {"usd_total": 1_000_000.0},
    }
    rows = [{"year": 1, "cfads_usd": 500_000.0}]
    with pytest.raises(ValueError, match="fees"):
        apply_debt_layer(params=base, annual_rows=rows)
    absurd = copy.deepcopy(base)
    absurd["Financing_Terms"]["fees"] = {"pri_premium_pct_per_year": 1.5}
    with pytest.raises(ValueError, match="fees"):
        apply_debt_layer(params=absurd, annual_rows=rows)
