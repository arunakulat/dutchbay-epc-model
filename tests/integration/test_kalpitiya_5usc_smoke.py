"""Smoke test for the Kalpitiya 159.6 MW lender case at a 5 US-cent/kWh tariff (fixed LKR)
with a GRANULAR bottom-up cost build.

Same resource/turbine as dutchbay_lendercase_2025Q4.yaml (15x IEA Reference 10 MW @150m,
IEA 10.6 MW power + Ct curve, ERA5-fitted Weibull A=8.199/k=2.665, FX 333.79, net AEP
473.8 GWh), with TWO differences: (1) tariff benchmarked at 5.0 US cents/kWh (0.05 USD)
SETTLED IN LKR, FIXED at 16.69 LKR/kWh, no escalation; (2) costs are a bottom-up build —
CAPEX $207.5M ($1,300/kW, line items summed by the engine) and OPEX $3.51M/yr ($22/kW-yr)
escalating 2.5%/yr in USD on top of the FX curve.

Honest finding this guards: at 5c/kWh on realistic costs the deal is DEEPLY UNECONOMIC —
equity IRR -6.33%, project NPV -$86.9M.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from analytics.scenario_loader import load_scenario_config
from analytics.schema_guard import validate_config_for_v14

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIO = REPO_ROOT / "scenarios" / "dutchbay_lendercase_5usc_fixed_lkr.yaml"


@pytest.fixture(scope="module")
def cfg() -> dict:
    return load_scenario_config(str(SCENARIO))


def test_tariff_is_5usc_fixed_in_lkr(cfg: dict) -> None:
    """5.0 US cents/kWh carried as a FIXED 16.69 LKR/kWh (= 0.05 x 333.79), no escalation."""
    assert float(cfg["tariff"]["lkr_per_kwh"]) == pytest.approx(16.69, abs=0.001)
    assert cfg["tariff"]["tariff_type"] == "fixed"  # no CPI/FX escalation
    # 16.69 LKR == 0.05 USD at the pinned FX
    assert float(cfg["tariff"]["lkr_per_kwh"]) == pytest.approx(
        0.05 * float(cfg["fx"]["start_lkr_per_usd"]), abs=0.01
    )


def test_payment_is_lkr_only(cfg: dict) -> None:
    """Revenue is LKR-only (no USD payment); the model is structurally LKR-primary."""
    assert str(cfg["ppa"]["primary_currency"]).upper() == "LKR"


def test_resource_and_turbine_equal_the_canonical(cfg: dict) -> None:
    """Resource/turbine inputs match the canonical lender case (costs + tariff differ)."""
    assert cfg["resource"]["power_curve"]["curve_key"] == "iea_reference_10mw"  # IEA 10.6 MW
    assert float(cfg["fx"]["start_lkr_per_usd"]) == pytest.approx(333.79, abs=0.001)
    assert float(cfg["wind_resource"]["weibull_a"]) == pytest.approx(8.199, abs=0.01)
    assert float(cfg["wind_resource"]["weibull_k"]) == pytest.approx(2.665, abs=0.01)
    assert cfg["resource"]["turbines"]["count"] == 15
    # AEP is unchanged from the canonical (shared 10MW summary mock).
    assert float(cfg["expected_results"]["net_aep_p50_gwh"]) == pytest.approx(473.8, abs=0.5)


def test_capex_is_granular_bottom_up(cfg: dict) -> None:
    """CAPEX is a bottom-up line-item build the engine sums to $207.5M ($1,300/kW)."""
    from finance.debt_v14 import _extract_capex_usd

    cx = cfg["capex"]
    assert cx["derive_from_breakdown"] is True
    line_sum = sum(v for v in cx["breakdown"].values() if isinstance(v, (int, float)))
    assert line_sum == pytest.approx(207_500_000, rel=1e-6)  # line items sum
    assert line_sum == pytest.approx(float(cx["usd_total"]), rel=0.005)  # cross-check
    # the engine derives CAPEX from the breakdown, not the flat total
    assert _extract_capex_usd(dict(cfg)) == pytest.approx(207_500_000, rel=1e-6)
    assert _extract_capex_usd(dict(cfg)) / 159_600 == pytest.approx(1300.0, abs=1.0)  # $/kW


def test_opex_is_granular_and_escalates(cfg: dict) -> None:
    """OPEX is a bottom-up build at $22/kW-yr that escalates 2.5%/yr in USD (plus FX)."""
    op = cfg["opex"]
    line_sum = sum(v for v in op["breakdown"].values() if isinstance(v, (int, float)))
    assert line_sum == pytest.approx(3_510_000, rel=1e-6)
    assert line_sum == pytest.approx(float(op["usd_per_year"]), rel=1e-6)
    assert float(op["escalation_pct"]) == pytest.approx(2.5, abs=0.01)

    # year-20 opex must exceed year-1 in USD by the compounded escalation (not flat).
    from analytics.scenario_loader import load_scenario_config
    from finance.cashflow_v14 import build_annual_rows

    rows = build_annual_rows(load_scenario_config(str(SCENARIO)))
    ops = [r for r in rows if r.get("opex_usd")]
    assert ops[-1]["opex_usd"] == pytest.approx(ops[0]["opex_usd"] * 1.025 ** 19, rel=0.01)


def test_scenario_passes_schemas(cfg: dict) -> None:
    validate_config_for_v14(cfg, str(SCENARIO), ["era5", "wind"])  # must not raise


def test_pipeline_runs_config_driven_and_is_uneconomic(cfg: dict) -> None:
    """The live pipeline reproduces the pinned economics — and the deal is UNDERWATER.

    At 5c/kWh on the granular bottom-up costs ($1,300/kW CAPEX + $22/kW-yr escalating
    OPEX) the project IRR (0.23%) falls far below the ~9.72% WACC, equity IRR is deeply
    NEGATIVE (-6.33%), and project NPV is -$86.9M. The DSCR sculpt still floors min DSCR
    at 1.30 by deleveraging.
    """
    from analytics.pipeline_v14_enhanced import run_v14_pipeline

    kpis = run_v14_pipeline(config=str(SCENARIO))["kpis"]
    assert kpis["project_irr"] == pytest.approx(0.0023, abs=0.005)
    assert kpis["equity_irr"] == pytest.approx(-0.0633, abs=0.005)
    assert kpis["equity_irr"] < 0.0  # NEGATIVE — the headline finding
    assert kpis["project_npv"] == pytest.approx(-86.89e6, rel=0.05)
    assert kpis["project_npv"] < 0.0  # deeply underwater
    assert kpis["min_dscr"] == pytest.approx(1.30, abs=0.02)
    assert kpis["max_debt_usd"] == pytest.approx(77.8e6, rel=0.02)  # deleveraged (DSCR-bound)


def test_expected_results_match_live_engine(cfg: dict) -> None:
    """The scenario's expected_results block is bound to the live engine (no silent drift)."""
    from analytics.pipeline_v14_enhanced import run_v14_pipeline

    er = cfg["expected_results"]
    kpis = run_v14_pipeline(config=str(SCENARIO))["kpis"]
    assert kpis["project_irr"] == pytest.approx(float(er["project_irr"]), abs=0.005)
    assert kpis["equity_irr"] == pytest.approx(float(er["equity_irr"]), abs=0.005)
    assert kpis["project_npv"] / 1e6 == pytest.approx(float(er["project_npv_m_usd"]), abs=0.5)
    assert kpis["min_dscr"] == pytest.approx(float(er["min_dscr"]), abs=0.02)
