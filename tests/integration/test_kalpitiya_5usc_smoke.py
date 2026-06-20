"""Smoke test for the Kalpitiya 159.6 MW lender case at a 5 US-cent/kWh tariff (fixed LKR).

A tariff variant of dutchbay_lendercase_2025Q4.yaml: IDENTICAL in every respect (15x IEA
Reference 10 MW @150m, IEA 10.6 MW power + Ct curve, ERA5-fitted Weibull A=8.199/k=2.665,
FX 333.79, net AEP 473.8 GWh) EXCEPT the unit price. The PPA is benchmarked at 5.0 US
cents/kWh (0.05 USD) but SETTLED IN LKR with no USD cashflow; the LKR tariff is FIXED at
signing FX (0.05 x 333.79 = 16.69 LKR/kWh) with NO escalation.

Honest finding this guards: at 5c/kWh the deal is UNECONOMIC — equity IRR turns NEGATIVE
and project NPV is deeply negative — vs the canonical 20.3 LKR/kWh (6.1c) case's +$2.0M.
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


def test_everything_else_equals_the_canonical(cfg: dict) -> None:
    """All non-tariff inputs match the canonical lender case (only the price differs)."""
    assert cfg["resource"]["power_curve"]["curve_key"] == "iea_reference_10mw"  # IEA 10.6 MW
    assert float(cfg["fx"]["start_lkr_per_usd"]) == pytest.approx(333.79, abs=0.001)
    assert float(cfg["wind_resource"]["weibull_a"]) == pytest.approx(8.199, abs=0.01)
    assert float(cfg["wind_resource"]["weibull_k"]) == pytest.approx(2.665, abs=0.01)
    assert cfg["resource"]["turbines"]["count"] == 15
    # AEP is unchanged from the canonical (shared 10MW summary mock).
    assert float(cfg["expected_results"]["net_aep_p50_gwh"]) == pytest.approx(473.8, abs=0.5)


def test_scenario_passes_schemas(cfg: dict) -> None:
    validate_config_for_v14(cfg, str(SCENARIO), ["era5", "wind"])  # must not raise


def test_pipeline_runs_config_driven_and_is_uneconomic(cfg: dict) -> None:
    """The live pipeline reproduces the pinned economics — and the deal is UNDERWATER.

    At 5c/kWh (a -17.8% revenue cut from the canonical 6.1c) the project IRR (4.80%)
    falls well below the ~8.94% WACC, equity IRR turns NEGATIVE, and project NPV is
    deeply negative. The DSCR sculpt still floors min DSCR at 1.30 by deleveraging.
    """
    from analytics.pipeline_v14_enhanced import run_v14_pipeline

    kpis = run_v14_pipeline(config=str(SCENARIO))["kpis"]
    assert kpis["project_irr"] == pytest.approx(0.0480, abs=0.005)
    assert kpis["equity_irr"] == pytest.approx(-0.0206, abs=0.005)
    assert kpis["equity_irr"] < 0.0  # NEGATIVE — the headline finding
    assert kpis["project_npv"] == pytest.approx(-31.45e6, rel=0.05)
    assert kpis["project_npv"] < 0.0  # deeply underwater
    assert kpis["min_dscr"] == pytest.approx(1.30, abs=0.02)
    assert kpis["max_debt_usd"] == pytest.approx(80.2e6, rel=0.02)  # deleveraged (DSCR-bound)


def test_expected_results_match_live_engine(cfg: dict) -> None:
    """The scenario's expected_results block is bound to the live engine (no silent drift)."""
    from analytics.pipeline_v14_enhanced import run_v14_pipeline

    er = cfg["expected_results"]
    kpis = run_v14_pipeline(config=str(SCENARIO))["kpis"]
    assert kpis["project_irr"] == pytest.approx(float(er["project_irr"]), abs=0.005)
    assert kpis["equity_irr"] == pytest.approx(float(er["equity_irr"]), abs=0.005)
    assert kpis["project_npv"] / 1e6 == pytest.approx(float(er["project_npv_m_usd"]), abs=0.5)
    assert kpis["min_dscr"] == pytest.approx(float(er["min_dscr"]), abs=0.02)
