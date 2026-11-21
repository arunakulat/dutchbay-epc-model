"""Wind-resource AEP sensitivity in the lender report (#1615 step B).

The AEP cluster's tornado and Monte Carlo reach the report through one seam, as a labelled
resource sensitivity beside the committed basis, reconciled against it, never in its place.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping

import pytest

from analytics.scenario_loader import load_scenario_config
from app.reports.aep_resource_sensitivity import (
    AEP_MC_N_SAMPLES,
    SECTION_AEP_RESOURCE,
    build_aep_resource_sensitivity,
)
from app.reports.renderer import render_report_html
from app.reports.report_model import AepResourceSensitivityBlock

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LENDER_CFG = _REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"

#: The committed basis the finance run carries, as the pipeline records it.
_RUN_RESULT: Dict[str, Any] = {
    "yield_reconciliation": {
        "implied_net_aep_gwh": 433.0,
        "p90": {"frozen_net_aep_p90_gwh": 377.3},
    }
}


@pytest.fixture(scope="module")
def scenario() -> Dict[str, Any]:
    return dict(load_scenario_config(str(_LENDER_CFG)))


@pytest.fixture(scope="module")
def block(scenario: Dict[str, Any]) -> AepResourceSensitivityBlock:
    built = build_aep_resource_sensitivity(scenario, _RUN_RESULT)
    assert isinstance(built, AepResourceSensitivityBlock), built
    return built


# ── the figures ───────────────────────────────────────────────────────────────


def test_the_cluster_base_reconciles_to_the_committed_basis_before_the_haircut(
    scenario: Dict[str, Any], block: AepResourceSensitivityBlock
) -> None:
    haircut = float(scenario["resource"]["uncertainty"]["p50_haircut_pct"])
    pre_haircut = 433.0 / (1.0 - haircut / 100.0)
    # The analytic integral lands on the committed modelled P50 within 0.5%: two AEP
    # figures in one report, and the reason they differ is the stated haircut.
    assert abs(block.base_net_aep_gwh - pre_haircut) / pre_haircut < 0.005
    assert block.committed_p50_gwh == 433.0
    assert block.committed_p90_gwh == 377.3


def test_the_tornado_sweeps_every_resource_driver_widest_first(
    block: AepResourceSensitivityBlock,
) -> None:
    drivers = [r.driver for r in block.tornado]
    assert sorted(drivers) == sorted(
        ["Mean wind speed", "Shear exponent", "Loss stack (relative)", "Power curve"]
    )
    swings = [r.swing_gwh for r in block.tornado]
    assert swings == sorted(swings, reverse=True)
    for row in block.tornado:
        assert row.swing_gwh == pytest.approx(abs(row.high_gwh - row.low_gwh), abs=0.01)


def test_the_monte_carlo_uses_the_scenario_uncertainty_and_exceedance_order(
    scenario: Dict[str, Any], block: AepResourceSensitivityBlock
) -> None:
    assert block.weibull_uncertainty_pct == float(
        scenario["monte_carlo"]["weibull_uncertainty_pct"]
    )
    assert block.mc_n_samples == AEP_MC_N_SAMPLES
    # Exceedance convention: P50 >= P75 >= P90 >= P99.
    assert block.mc_p50_gwh >= block.mc_p75_gwh >= block.mc_p90_gwh >= block.mc_p99_gwh
    # The MC centre sits on the cluster base: the spread is resource uncertainty, not a
    # shifted basis.
    assert (
        abs(block.mc_p50_gwh - block.base_net_aep_gwh) / block.base_net_aep_gwh < 0.01
    )


def test_the_section_is_reproducible(scenario: Dict[str, Any]) -> None:
    first = build_aep_resource_sensitivity(scenario, _RUN_RESULT)
    second = build_aep_resource_sensitivity(scenario, _RUN_RESULT)
    assert first == second


def test_the_reconciliation_says_why_the_figures_differ(
    block: AepResourceSensitivityBlock,
) -> None:
    text = " ".join(block.reconciliation)
    assert "pre-construction over-prediction haircut" in text
    assert "IEC 61400-15-2" in text
    assert "monte_carlo.weibull_uncertainty_pct" in text
    assert "the report basis stays the committed figure" in text


def test_without_a_committed_basis_no_comparison_is_claimed(
    scenario: Dict[str, Any],
) -> None:
    built = build_aep_resource_sensitivity(scenario, {})
    assert isinstance(built, AepResourceSensitivityBlock)
    assert built.committed_p50_gwh is None and built.committed_p90_gwh is None
    assert len(built.reconciliation) == 1  # the method line only


# ── not run, with a reason ────────────────────────────────────────────────────


def _without(scenario: Mapping[str, Any], dotted: str) -> Dict[str, Any]:
    import copy

    out = copy.deepcopy(dict(scenario))
    *head, last = dotted.split(".")
    node: Any = out
    for key in head:
        node = node[key]
    node.pop(last)
    return out


@pytest.mark.parametrize(
    ("dropped", "named"),
    [
        ("wind_resource", "wind_resource"),
        ("wind_resource.weibull_k", "weibull_k"),
        ("resource.losses", "resource.losses"),
        ("resource.power_curve.curve_key", "curve_key"),
        ("monte_carlo.weibull_uncertainty_pct", "weibull_uncertainty_pct"),
    ],
)
def test_a_missing_input_is_a_stated_reason_not_a_default(
    scenario: Dict[str, Any], dropped: str, named: str
) -> None:
    built = build_aep_resource_sensitivity(_without(scenario, dropped), _RUN_RESULT)
    assert isinstance(built, str)
    assert built.startswith("not run:")
    assert named in built


def test_the_section_name_is_stable() -> None:
    assert SECTION_AEP_RESOURCE.startswith("Wind resource sensitivity")


# ── the rendered section ──────────────────────────────────────────────────────


def _render(block: AepResourceSensitivityBlock | None) -> str:
    from app.models.inputs import WindFarmInputs
    from app.reports.report_orchestration import (
        ORDINARY_REPORT_SENSITIVITY_PROFILE,
        build_report_context_from_case,
        compute_report_sensitivity,
        run_report_case,
    )

    inputs = WindFarmInputs(
        site_name="Report seam",
        capacity_mw=148.9,  # reconciles with the frozen AEP (tests/app/test_api.py)
        capacity_factor=0.332,
        project_life_years=20,
        ppa_price_lkr_per_kwh=20.30,
        ppa_term_years=20,
        capex_total_usd=159_600_000.0,
        opex_annual_usd=5_000_000.0,
        fx_start_lkr_per_usd=333.79,
    )
    case = run_report_case(inputs, generated_at="2026-11-21T00:00:00+00:00")
    bundle = compute_report_sensitivity(
        case.scenario_config,
        profile=ORDINARY_REPORT_SENSITIVITY_PROFILE,
        tornado_computer=lambda _s: None,
        morris_computer=lambda _s, *, n_trajectories: None,
        pawn_computer=lambda _s, *, n, s: None,
    )
    return render_report_html(
        build_report_context_from_case(case, bundle, aep_resource_sensitivity=block)
    )


def test_the_section_is_labelled_and_carries_f5(
    block: AepResourceSensitivityBlock,
) -> None:
    html = _render(block)
    section = html.split("Wind Resource Sensitivity &mdash; Net AEP", 1)[1].split(
        "</section>", 1
    )[0]
    section = " ".join(section.split())
    assert "not the report basis" in section
    assert "no bankable resource claim" in section
    assert "Mean wind speed" in section
    assert "Committed basis" in section
    assert "377.3 GWh" in section
    assert "Why the figures differ" in section
    assert '<p class="muted f5-caption"><strong>F-5:</strong>' in section


def test_no_block_means_no_section() -> None:
    html = _render(None)
    assert "Wind Resource Sensitivity" not in html
