"""Tests for the first-class financed grid-curtailment risk lever (`curtailment_pct`).

The lever is an INCREMENTAL financed grid-curtailment haircut applied after grid loss in
``_calculate_net_production``. Default 0.0 → byte-identical (the ~2% physical curtailment is
already embedded in the bankable net AEP / capacity_factor); a non-zero value is a
first-class tornado + Monte-Carlo stress variable. Covers: the engine math, config
resolution, byte-identity at default, a real economic impact when stressed, the tornado
driver, the MC parameter, and that it does NOT disturb the AEP↔CF reconciliation guard.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from analytics.scenario_loader import load_scenario_config

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")


# --- engine math ----------------------------------------------------------------------


def test_net_production_applies_curtailment_after_grid_loss() -> None:
    from finance.cashflow_v14_production import _calculate_net_production

    gross0, net0 = _calculate_net_production(100.0, 0.40, 0.0, 0.02, 0)
    gross1, net1 = _calculate_net_production(
        100.0, 0.40, 0.0, 0.02, 0, curtailment_pct=0.10
    )
    assert gross1 == gross0  # gross is unaffected
    # curtailment is multiplicative on the post-grid-loss energy
    assert net1 == pytest.approx(net0 * (1.0 - 0.10), rel=1e-12)


def test_net_production_default_curtailment_is_zero() -> None:
    """Omitting curtailment_pct must be identical to passing 0.0 (positional callers)."""
    from finance.cashflow_v14_production import _calculate_net_production

    assert _calculate_net_production(
        120.0, 0.35, 0.005, 0.02, 3
    ) == _calculate_net_production(120.0, 0.35, 0.005, 0.02, 3, curtailment_pct=0.0)


# --- config resolution ----------------------------------------------------------------


def test_curtailment_resolved_from_project_block() -> None:
    from finance.cashflow_v14_params import _build_cashflow_params

    base = load_scenario_config(LENDER)
    assert _build_cashflow_params(base).curtailment_pct == 0.0  # canonical default
    base["project"]["curtailment_pct"] = 0.08
    assert _build_cashflow_params(base).curtailment_pct == pytest.approx(0.08)


def test_curtailment_percent_form_is_normalized() -> None:
    """A percent-form value (>1.0) is normalized like the other loss fields."""
    from finance.cashflow_v14_params import _build_cashflow_params

    base = load_scenario_config(LENDER)
    base["project"]["curtailment_pct"] = 8.0  # percent
    assert _build_cashflow_params(base).curtailment_pct == pytest.approx(0.08)


# --- byte-identity at default + real impact when stressed -----------------------------


def test_default_curtailment_is_byte_identical() -> None:
    from analytics.pipeline_v14_enhanced import run_v14_pipeline

    k = run_v14_pipeline(config=LENDER)["kpis"]
    # Construction-lag-correct project economics (audit finding 2.0): operating year 1
    # is discounted after the 2-yr build, not at t=0. projIRR 5.43% (< ~8.18% WACC), NPV -$31.9M.
    assert k["project_irr"] == pytest.approx(0.054338, abs=1e-5)
    assert k["project_npv"] == pytest.approx(-31926643.35, abs=1.0)
    assert k["min_dscr"] == pytest.approx(1.30, abs=1e-6)


def test_curtailment_stress_reduces_economics() -> None:
    from analytics.pipeline_v14_enhanced import run_v14_pipeline

    base = run_v14_pipeline(config=LENDER)["kpis"]
    cfg = load_scenario_config(LENDER)
    cfg["project"]["curtailment_pct"] = 0.10  # 10% incremental curtailment
    stressed = run_v14_pipeline(config=cfg)["kpis"]
    assert stressed["project_irr"] < base["project_irr"]
    assert (
        stressed["project_npv"] < base["project_npv"]
    )  # turns the marginal deal negative


# --- first-class tornado + Monte-Carlo ------------------------------------------------


def test_curtailment_is_a_tornado_driver() -> None:
    from analytics.core.sensitivity_runner import _default_parameters

    params = _default_parameters(load_scenario_config(LENDER))
    cur = [p for p in params if "Curtailment" in (p.label or "")]
    assert len(cur) == 1
    assert cur[0].variable_name == "project.curtailment_pct"
    assert (cur[0].low_value, cur[0].high_value) == (
        0.0,
        0.13,
    )  # absolute band, not relative


def test_curtailment_tornado_bar_is_not_flat() -> None:
    from analytics.core.sensitivity_runner import run_sensitivity_analysis

    suite = run_sensitivity_analysis(LENDER, metric="project_irr")
    cur = [t for t in suite.tornado_results if "Curtailment" in t.metric_name]
    assert len(cur) == 1
    assert cur[0].impact_abs > 0.005  # a real, material IRR impact (not a flat bar)


def test_curtailment_is_a_monte_carlo_parameter() -> None:
    d = yaml.safe_load(Path(LENDER).read_text())
    names = [p["name"] for p in d["monte_carlo"]["parameters"]]
    assert "project.curtailment_pct" in names


# --- does not disturb the AEP↔CF reconciliation guard ---------------------------------


def test_curtailment_does_not_affect_reconciliation() -> None:
    """curtailment is post-CF (on net_kwh), so capacity_mw×CF×8.760 is unchanged → guard ok."""
    from analytics.aep_reconciliation import reconcile_capacity_factor_with_bankable_aep

    cfg = load_scenario_config(
        LENDER
    )  # load already runs the guard; an explicit re-check:
    cfg["project"]["curtailment_pct"] = 0.13
    reconcile_capacity_factor_with_bankable_aep(cfg, LENDER)  # must NOT raise
