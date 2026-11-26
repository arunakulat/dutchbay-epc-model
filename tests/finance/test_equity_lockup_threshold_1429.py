"""Strict config-first guards for the equity lock-up DSCR threshold (#1429, E01)."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict

import pytest

from analytics.pipeline_v14_enhanced import run_v14_pipeline
from analytics.scenario_loader import load_scenario_config
from analytics.schema_guard import ConfigValidationError, validate_config_for_v14
from finance.equity_distribution_v14_hydra import resolve_equity_min_dscr_threshold

LENDER = str(
    Path(__file__).resolve().parents[2]
    / "scenarios"
    / "dutchbay_lendercase_2025Q4.yaml"
)


def _lender_cfg() -> Dict[str, Any]:
    return copy.deepcopy(dict(load_scenario_config(LENDER)))


def test_lender_scenario_resolves_from_constraints_covenant() -> None:
    val, src = resolve_equity_min_dscr_threshold(_lender_cfg())
    assert val == pytest.approx(1.30)
    assert src == "constraints.min_dscr_covenant"


def test_explicit_equity_threshold_overrides_constraints_covenant() -> None:
    cfg = _lender_cfg()
    cfg["equity_distribution"] = {"min_dscr_threshold": 1.35}
    val, src = resolve_equity_min_dscr_threshold(cfg)
    assert val == pytest.approx(1.35)
    assert src == "equity_distribution.min_dscr_threshold"


def test_missing_lockup_threshold_is_refused_by_resolver_and_preflight() -> None:
    cfg = _lender_cfg()
    cfg.get("constraints", {}).pop("min_dscr_covenant", None)
    with pytest.raises(ValueError, match="no code default"):
        resolve_equity_min_dscr_threshold(cfg)
    with pytest.raises(ConfigValidationError, match="no code default"):
        validate_config_for_v14(cfg, "missing_lockup.yaml", ["cashflow", "debt"])


@pytest.mark.parametrize("bad", [None, True, False, "1.25x", -0.1, 6.0, float("nan")])
def test_invalid_lockup_threshold_is_refused_naming_path(bad: Any) -> None:
    cfg = _lender_cfg()
    cfg["constraints"]["min_dscr_covenant"] = bad
    with pytest.raises(ValueError, match=r"constraints\.min_dscr_covenant"):
        resolve_equity_min_dscr_threshold(cfg)


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


def test_lender_pipeline_runs_cleanly_in_strict_mode() -> None:
    result = run_v14_pipeline(config=LENDER, validation_mode="strict")
    assert result["status"] == "success"
    assert result["equity_distribution"]["equity_summary"][
        "min_dscr_threshold"
    ] == pytest.approx(1.30)
