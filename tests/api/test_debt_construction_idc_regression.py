#!/usr/bin/env python3
"""
DutchBay V14 Debt Construction/IDC Regression Test Suite

Version: 2025-11-26 (Sprint 2, Go With The Flow refactor)

Purpose
-------
- Regression-pin principal and IDC values for standard and edge scenarios.
- Pins reflect the *current* scenario YAMLs, mix percentages, and v14 engine outputs.
- Changing the YAML or engine logic requires updating these pins. This script
  should always travel in sync with scenario+business assumptions.

Testing Approach: Go With The Flow
----------------------------------
- Pin values must match those produced by the canonical v14 engine for scenarios as shipped.
- Pins are verified using a tight but not brittle relative tolerance (rel=0.002).
- This ensures that future refactoring or scenario evolution causes CI to fail
  only when actual results "move," not on spurious floating-point changes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest

from analytics.scenario_loader import load_scenario_config
from finance import debt_v14 as debt_mod
from finance.cashflow_v14 import build_annual_rows

ROOT_DIR = Path(__file__).parent.parent.parent  # repo root
SCENARIOS_DIR = ROOT_DIR / "scenarios"


def _load_config(name: str) -> Dict[str, Any]:
    path = SCENARIOS_DIR / name
    assert path.exists(), f"Scenario file not found: {path}"
    return load_scenario_config(str(path))


def _plan_debt_for_config(config_name: str) -> Dict[str, Any]:
    config = _load_config(config_name)
    annual_rows = build_annual_rows(config)
    result = debt_mod.plan_debt(annual_rows=annual_rows, config=config)
    assert isinstance(
        result, dict
    ), "Expected plan_debt(...) to return a dict-like result"
    return result


def _extract_tranche(result: Dict[str, Any], key: str) -> Dict[str, Any]:
    assert (
        key in result
    ), f"Tranche {key!r} missing in debt result keys={list(result.keys())}"
    tranche = result[key]
    assert isinstance(
        tranche, dict
    ), f"Expected tranche {key!r} to be a dict, got {type(tranche)!r}"
    return tranche


def test_lendercase_construction_and_tenor_pinned() -> None:
    result = _plan_debt_for_config("dutchbay_lendercase_2025Q4.yaml")
    construction_years = result.get("construction_years")
    tenor_years = result.get("tenor_years")
    assert (
        construction_years == 2
    ), f"Expected 2-year construction, got {construction_years!r}"
    assert tenor_years == 15, f"Expected 15-year tenor, got {tenor_years!r}"


def test_lendercase_idc_totals_pinned() -> None:
    result = _plan_debt_for_config("dutchbay_lendercase_2025Q4.yaml")
    lkr = _extract_tranche(result, "lkr")
    usd = _extract_tranche(result, "usd")
    dfi = _extract_tranche(result, "dfi")
    tol = 0.002  # 0.2% robust regression tolerance

    # These pins reflect the lendercase scenario and its mix.
    # (Update these values only if scenario/config changes.)
    assert lkr.get("principal_m") == pytest.approx(53_071_200.00, rel=tol)
    assert usd.get("principal_m") == pytest.approx(52_698_515.62, rel=tol)
    assert dfi.get("principal_m") == pytest.approx(11_545_931.25, rel=tol)
    assert lkr.get("idc_m") == pytest.approx(5_821_200.00, rel=tol)
    assert usd.get("idc_m") == pytest.approx(5_448_515.62, rel=tol)
    assert dfi.get("idc_m") == pytest.approx(1_045_931.25, rel=tol)
    total_idc_from_tranches = (
        lkr.get("idc_m", 0.0) + usd.get("idc_m", 0.0) + dfi.get("idc_m", 0.0)
    )
    expected_total_idc = 12_315_646.88
    if "total_idc_m" in result:
        assert result["total_idc_m"] == pytest.approx(expected_total_idc, rel=tol)
    else:
        assert total_idc_from_tranches == pytest.approx(expected_total_idc, rel=tol)


def test_edge_stress_construction_and_tenor_pinned() -> None:
    result = _plan_debt_for_config("edge_extreme_stress.yaml")
    construction_years = result.get("construction_years")
    tenor_years = result.get("tenor_years")
    assert (
        construction_years == 2
    ), f"Expected 2-year construction, got {construction_years!r}"
    assert tenor_years == 15, f"Expected 15-year tenor, got {tenor_years!r}"


def test_edge_stress_idc_totals_pinned() -> None:
    """
    This regression pin reflects the *current* edge_extreme_stress.yaml scenario,
    with mix: lkr_max=0.44, usd_commercial_min=0.20, dfi_max=0.36 on 157.5M total debt.

    If this scenario changes, pins must be updated based on new model outputs.
    """
    result = _plan_debt_for_config("edge_extreme_stress.yaml")
    lkr = _extract_tranche(result, "lkr")
    usd = _extract_tranche(result, "usd")
    dfi = _extract_tranche(result, "dfi")
    tol = 0.002  # 0.2% robust regression tolerance

    # Update these pins when scenario or mix changes
    assert lkr.get("principal_m") == pytest.approx(69_300_000.0, rel=tol)
    assert usd.get("principal_m") == pytest.approx(31_500_000.0, rel=tol)
    assert dfi.get("principal_m") == pytest.approx(56_700_000.0, rel=tol)

    # For IDC values, either pin current outputs or keep these as placeholders:
    assert lkr.get("idc_m") == pytest.approx(0.0, rel=tol)  # update when IDC modeled
    assert usd.get("idc_m") == pytest.approx(0.0, rel=tol)  # update as needed
    assert dfi.get("idc_m") == pytest.approx(0.0, rel=tol)  # update as needed

    total_idc_from_tranches = (
        lkr.get("idc_m", 0.0) + usd.get("idc_m", 0.0) + dfi.get("idc_m", 0.0)
    )
    expected_total_idc = 0.0  # update pin if model calculates IDC
    if "total_idc_m" in result:
        assert result["total_idc_m"] == pytest.approx(expected_total_idc, rel=tol)
    else:
        assert total_idc_from_tranches == pytest.approx(expected_total_idc, rel=tol)
