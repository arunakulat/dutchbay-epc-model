"""Tests for the config-first grid-outage / grid-unavailability lever (`grid_outage_pct`, #744).

An INCREMENTAL grid-unavailability haircut applied after grid loss AND curtailment in
``_calculate_net_production``. Default 0.0 → byte-identical (the embedded availability is
already in the bankable net AEP / capacity_factor); a non-zero value is the documented
grid-outage assumptions input above that base. Distinct from ``curtailment_pct`` (economic
dispatch curtailment) — this is grid downtime. Covers the engine math, config resolution,
byte-identity at default, real economic impact when stressed, and that it stacks
multiplicatively with (does not overwrite) curtailment.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from analytics.scenario_loader import load_scenario_config
from tests._canon import (
    LENDER_PROJECT_IRR,
    LENDER_PROJECT_NPV,
    LENDER_TOTAL_CFADS_USD,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")


# --- engine math ----------------------------------------------------------------------


def test_net_production_applies_grid_outage_after_curtailment() -> None:
    from finance.cashflow_v14_production import _calculate_net_production

    gross0, net0 = _calculate_net_production(100.0, 0.40, 0.0, 0.02, 0)
    gross1, net1 = _calculate_net_production(
        100.0, 0.40, 0.0, 0.02, 0, grid_outage_pct=0.10
    )
    assert gross1 == gross0  # gross is unaffected
    assert net1 == pytest.approx(net0 * (1.0 - 0.10), rel=1e-12)


def test_grid_outage_stacks_multiplicatively_with_curtailment() -> None:
    """The two levers are independent multiplicative haircuts, not either/or."""
    from finance.cashflow_v14_production import _calculate_net_production

    _, net_base = _calculate_net_production(100.0, 0.40, 0.0, 0.02, 0)
    _, net_both = _calculate_net_production(
        100.0, 0.40, 0.0, 0.02, 0, curtailment_pct=0.10, grid_outage_pct=0.05
    )
    assert net_both == pytest.approx(net_base * (1.0 - 0.10) * (1.0 - 0.05), rel=1e-12)


def test_net_production_default_grid_outage_is_zero() -> None:
    """Omitting grid_outage_pct must be identical to passing 0.0."""
    from finance.cashflow_v14_production import _calculate_net_production

    assert _calculate_net_production(
        120.0, 0.35, 0.005, 0.02, 3
    ) == _calculate_net_production(120.0, 0.35, 0.005, 0.02, 3, grid_outage_pct=0.0)


# --- config resolution ----------------------------------------------------------------


def test_grid_outage_resolved_from_project_block_and_normalized() -> None:
    from finance.cashflow_v14_params import _build_cashflow_params

    base = load_scenario_config(LENDER)
    assert _build_cashflow_params(base).grid_outage_pct == 0.0  # canonical default
    base["project"]["grid_outage_pct"] = 0.03
    assert _build_cashflow_params(base).grid_outage_pct == pytest.approx(0.03)
    base["project"]["grid_outage_pct"] = 3.0  # percent form
    assert _build_cashflow_params(base).grid_outage_pct == pytest.approx(0.03)


# --- byte-identity at default + real impact when stressed -----------------------------


def test_default_grid_outage_is_byte_identical() -> None:
    from analytics.pipeline_v14_enhanced import run_v14_pipeline

    k = run_v14_pipeline(config=LENDER)["kpis"]
    # No committed scenario declares grid_outage_pct, so the lever is 0.0 → canon.
    assert k["project_irr"] == pytest.approx(LENDER_PROJECT_IRR, abs=1e-9)
    assert k["project_npv"] == pytest.approx(LENDER_PROJECT_NPV, abs=1.0)
    assert k["total_cfads_usd"] == pytest.approx(LENDER_TOTAL_CFADS_USD, rel=1e-9)


def test_grid_outage_stress_reduces_economics() -> None:
    from analytics.pipeline_v14_enhanced import run_v14_pipeline

    base = run_v14_pipeline(config=LENDER)["kpis"]
    cfg = load_scenario_config(LENDER)
    cfg["project"]["grid_outage_pct"] = 0.05  # 5% incremental grid downtime
    stressed = run_v14_pipeline(config=cfg)["kpis"]
    assert stressed["project_irr"] < base["project_irr"]
    assert stressed["total_cfads_usd"] < base["total_cfads_usd"]
