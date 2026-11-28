"""Strict config-first guards for the equity lock-up DSCR threshold (#1429, E01)."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict, List

import pytest
from pydantic_core import ValidationError

from analytics.pipeline_v14_enhanced import PipelineValidationError, run_v14_pipeline
from analytics.scenario_loader import load_scenario_config
from analytics.schema_guard import ConfigValidationError, validate_config_for_v14
from finance.equity_distribution_v14_hydra import (
    EquityDistributionConfig,
    calculate_equity_distribution_from_pipeline,
    resolve_equity_min_dscr_threshold,
    waterfall_sweep_cash,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = REPO_ROOT / "scenarios"
LENDER = str(SCENARIOS / "dutchbay_lendercase_2025Q4.yaml")

_NOT_ENGINE_SCENARIOS = {
    "bad_missing_tax.yaml",
    "contracts_edgecase_base_v14.yaml",
    "dscr_sensitivity_example.yaml",
    "dutchbay_mc_enhanced_2025Q4.yaml",
    "dutchbay_sprint17_enhanced.yaml",
    "example_fx_structured_blocks.yaml",
    "kolonnawa_epc_100mw.yaml",
    "sensitivity_parameters_examples.yaml",
}
_PARTIAL_DIRS = {"overrides", "what_if", "_scrtch"}


def _engine_scenarios() -> List[Path]:
    paths: List[Path] = []
    for path in sorted(SCENARIOS.rglob("*.y*ml")):
        if _PARTIAL_DIRS.intersection(path.relative_to(SCENARIOS).parts):
            continue
        if path.name in _NOT_ENGINE_SCENARIOS:
            continue
        paths.append(path)
    return paths


def _lender_cfg() -> Dict[str, Any]:
    return copy.deepcopy(dict(load_scenario_config(LENDER)))


def test_census_finds_engine_scenarios() -> None:
    assert len(_engine_scenarios()) >= 30


@pytest.mark.parametrize(
    "path", _engine_scenarios(), ids=lambda p: str(p.relative_to(SCENARIOS))
)
def test_every_engine_scenario_declares_lockup_threshold(path: Path) -> None:
    """Every committed engine scenario (including subdirectories) resolves without fallback."""
    cfg = dict(load_scenario_config(str(path)))
    val, src = resolve_equity_min_dscr_threshold(cfg)
    assert 0.0 <= val <= 5.0
    assert src


def test_lender_scenario_resolves_from_constraints_covenant() -> None:
    val, src = resolve_equity_min_dscr_threshold(_lender_cfg())
    assert val == pytest.approx(1.30)
    assert src == "constraints.min_dscr_covenant"


@pytest.mark.parametrize(
    ("section_name", "expected_prefix"),
    [
        ("equity_distribution", "equity_distribution"),
        ("Equity_Distribution", "equity_distribution"),
        ("equity", "equity"),
    ],
)
def test_explicit_equity_threshold_overrides_constraints_covenant(
    section_name: str,
    expected_prefix: str,
) -> None:
    cfg = _lender_cfg()
    cfg[section_name] = {"min_dscr_threshold": 1.35}
    val, src = resolve_equity_min_dscr_threshold(cfg)
    assert val == pytest.approx(1.35)
    assert src == f"{expected_prefix}.min_dscr_threshold"


def test_missing_lockup_threshold_is_refused_by_resolver_and_preflight() -> None:
    cfg = _lender_cfg()
    cfg.get("constraints", {}).pop("min_dscr_covenant", None)
    with pytest.raises(ValueError, match="no code default"):
        resolve_equity_min_dscr_threshold(cfg)
    with pytest.raises(ConfigValidationError, match="no code default"):
        validate_config_for_v14(cfg, "missing_lockup.yaml", ["cashflow", "debt"])


def test_point_of_use_refuses_when_preflight_bypassed() -> None:
    """Direct waterfall/pipeline calls with validation_mode='off' still refuse missing threshold."""
    cfg = _lender_cfg()
    cfg.get("constraints", {}).pop("min_dscr_covenant", None)
    with pytest.raises(ValueError, match="no code default"):
        waterfall_sweep_cash(
            config=cfg,
            annual_rows=[{"year": 1, "cf_pre_debt": 100.0, "debt_service_total": 50.0}],
            debt_result={
                "balloon_treatment": "cash_sweep",
                "senior_fee_deferred_usd": [0.0],
            },
        )
    with pytest.raises(PipelineValidationError, match="no code default"):
        run_v14_pipeline(config=cfg, validation_mode="off")


@pytest.mark.parametrize(
    "bad",
    [None, True, False, "1.25x", -0.1, 6.0, float("nan"), float("inf"), float("-inf")],
)
def test_invalid_lockup_threshold_is_refused_naming_path(bad: Any) -> None:
    cfg = _lender_cfg()
    cfg["constraints"]["min_dscr_covenant"] = bad
    with pytest.raises(ValueError, match=r"constraints\.min_dscr_covenant"):
        resolve_equity_min_dscr_threshold(cfg)
    with pytest.raises(ConfigValidationError, match=r"constraints\.min_dscr_covenant"):
        validate_config_for_v14(cfg, "invalid_lockup.yaml", ["cashflow", "debt"])


def test_disabled_equity_distribution_skips_preflight_lockup_check() -> None:
    cfg = _lender_cfg()
    cfg.get("constraints", {}).pop("min_dscr_covenant", None)
    cfg["equity_distribution"] = {"enabled": False}
    validate_config_for_v14(cfg, "disabled_equity.yaml", ["cashflow", "debt"])


def test_case_insensitive_equity_threshold_overrides_constraints_covenant() -> None:
    cfg = _lender_cfg()
    cfg["equity_distribution"] = {"MIN_DSCR_THRESHOLD": 1.35}
    val, src = resolve_equity_min_dscr_threshold(cfg)
    assert val == pytest.approx(1.35)
    assert src == "equity_distribution.MIN_DSCR_THRESHOLD"


def test_explicit_null_equity_threshold_shadows_constraints_and_fails_loud() -> None:
    cfg = _lender_cfg()
    cfg["equity_distribution"] = {"min_dscr_threshold": None}
    with pytest.raises(ValueError, match=r"equity_distribution\.min_dscr_threshold"):
        resolve_equity_min_dscr_threshold(cfg)


def test_direct_equity_distribution_config_requires_min_dscr_threshold() -> None:
    """EQD-01: direct EquityDistributionConfig() must not silently default to 1.25."""
    with pytest.raises(ValidationError, match="min_dscr_threshold"):
        EquityDistributionConfig()  # type: ignore[call-arg]


def test_constraints_covenant_drives_waterfall_lockup_responsiveness() -> None:
    """Independent counterfactual oracle: varying constraints.min_dscr_covenant toggles lock-up."""
    annual_rows = [
        {"year": 1, "cfads_usd": 120.0, "debt_service_usd": 100.0, "dscr": 1.20},
        {"year": 2, "cfads_usd": 140.0, "debt_service_usd": 100.0, "dscr": 1.40},
    ]
    debt_result = {
        "total_debt_usd": 100.0,
        "debt_service_series": [100.0, 100.0],
        "interest_series": [50.0, 40.0],
        "principal_series": [50.0, 60.0],
    }
    base_cfg: Dict[str, Any] = {
        "project": {"project_life_years": 2},
        "equity_distribution": {"min_reserve_months": 0, "equity_investment_usd": 50.0},
    }

    locked_cfg = {**copy.deepcopy(base_cfg), "constraints": {"min_dscr_covenant": 1.30}}
    locked_res = calculate_equity_distribution_from_pipeline(
        config=locked_cfg, annual_rows=annual_rows, debt_result=debt_result
    )
    assert locked_res["annual_distributions"][0]["covenant_locked"] is True
    assert locked_res["equity_cashflows_usd"][1] == pytest.approx(0.0)

    unlocked_cfg = {
        **copy.deepcopy(base_cfg),
        "constraints": {"min_dscr_covenant": 1.15},
    }
    unlocked_res = calculate_equity_distribution_from_pipeline(
        config=unlocked_cfg, annual_rows=annual_rows, debt_result=debt_result
    )
    assert unlocked_res["annual_distributions"][0]["covenant_locked"] is False
    assert unlocked_res["equity_cashflows_usd"][1] > 0.0


def test_lender_pipeline_runs_cleanly_in_strict_mode() -> None:
    result = run_v14_pipeline(config=LENDER, validation_mode="strict")
    assert result["status"] == "success"
    assert result["equity_distribution"]["equity_summary"][
        "min_dscr_threshold"
    ] == pytest.approx(1.30)
