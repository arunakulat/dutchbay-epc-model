#!/usr/bin/env python3
"""
Regression tests for v14 debt construction / IDC / grace-period behaviour.

These tests pin the high-level outputs that we already verified manually via
the console logs from `make_executive_report.py`, so future refactors of the
debt engine can't silently change construction years, tenor or IDC totals
without breaking CI.

Scenarios covered:
- dutchbay_lendercase_2025Q4      → standard lender case
- edge_extreme_stress             → stressed construction + IDC profile
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest

from analytics.scenario_loader import load_scenario_config
from dutchbay_v14chat.finance.cashflow import build_annual_rows
from dutchbay_v14chat.finance import debt as debt_mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


ROOT_DIR = Path(__file__).parent.parent.parent  # repo root
SCENARIOS_DIR = ROOT_DIR / "scenarios"


def _load_config(name: str) -> Dict[str, Any]:
    """
    Load a scenario config from the canonical `scenarios/` directory.

    `name` is the bare scenario file name (e.g. 'dutchbay_lendercase_2025Q4.yaml').
    """
    path = SCENARIOS_DIR / name
    assert path.exists(), f"Scenario file not found: {path}"
    return load_scenario_config(str(path))


def _plan_debt_for_config(config_name: str) -> Dict[str, Any]:
    """
    Convenience helper: load config, build annual rows, and invoke the v14
    debt planning function.

    This mirrors the path used by the analytics / executive report flow.
    """
    config = _load_config(config_name)
    annual_rows = build_annual_rows(config)

    # NOTE: If the public API in debt_mod has a different name, adjust here.
    # We assume v14 exposes a `plan_debt(...)`-style function that returns
    # a mapping with tranche-level principal + IDC and summary fields.
    result = debt_mod.plan_debt(annual_rows=annual_rows, config=config)  # type: ignore[attr-defined]

    assert isinstance(
        result, dict
    ), "Expected plan_debt(...) to return a dict-like result"
    return result


def _extract_tranche(result: Dict[str, Any], key: str) -> Dict[str, Any]:
    """
    Extract a single tranche (e.g. 'lkr', 'usd', 'dfi') from the debt plan.

    We assert keys exist so the test fails loudly if the shape changes.
    """
    assert key in result, f"Tranche {key!r} missing in debt result keys={list(result.keys())}"
    tranche = result[key]
    assert isinstance(tranche, dict), f"Expected tranche {key!r} to be a dict, got {type(tranche)!r}"
    return tranche


# ---------------------------------------------------------------------------
# Regression tests – lender case
# ---------------------------------------------------------------------------


def test_lendercase_construction_and_tenor_pinned() -> None:
    """
    P0 regression: lender case construction years and tenor must remain stable.

    From the known-good console output:

        V14 Debt Planning: 2-year construction, 15-year tenor
    """
    result = _plan_debt_for_config("dutchbay_lendercase_2025Q4.yaml")

    # We expect the planning result to expose these high-level fields.
    construction_years = result.get("construction_years")
    tenor_years = result.get("tenor_years")

    assert construction_years == 2, f"Expected 2-year construction, got {construction_years!r}"
    assert tenor_years == 15, f"Expected 15-year tenor, got {tenor_years!r}"


def test_lendercase_idc_totals_pinned() -> None:
    """
    P0 regression: lender case IDC per tranche pinned to known-good values.

    From the console log:

        LKR: Principal $53071200.00M (IDC: $5821200.00M)
        USD: Principal $52698515.62M (IDC: $5448515.62M)
        DFI: Principal $11545931.25M (IDC: $1045931.25M)
        V14 Results: Min DSCR=1.30, Total IDC=$12315646.88M
    """
    result = _plan_debt_for_config("dutchbay_lendercase_2025Q4.yaml")

    lkr = _extract_tranche(result, "lkr")
    usd = _extract_tranche(result, "usd")
    dfi = _extract_tranche(result, "dfi")

    # Use a small tolerance to avoid false positives from minor rounding.
    tol = 1e-2

    # Principal amounts (millions)
    assert lkr.get("principal_m") == pytest.approx(53_071_200.00, rel=0, abs=tol)
    assert usd.get("principal_m") == pytest.approx(52_698_515.62, rel=0, abs=tol)
    assert dfi.get("principal_m") == pytest.approx(11_545_931.25, rel=0, abs=tol)

    # IDC amounts (millions)
    assert lkr.get("idc_m") == pytest.approx(5_821_200.00, rel=0, abs=tol)
    assert usd.get("idc_m") == pytest.approx(5_448_515.62, rel=0, abs=tol)
    assert dfi.get("idc_m") == pytest.approx(1_045_931.25, rel=0, abs=tol)

    # Total IDC – either explicit field, or derived from tranches
    total_idc_from_tranches = (
        lkr.get("idc_m", 0.0) + usd.get("idc_m", 0.0) + dfi.get("idc_m", 0.0)
    )
    expected_total_idc = 12_315_646.88

    if "total_idc_m" in result:
        assert result["total_idc_m"] == pytest.approx(expected_total_idc, rel=0, abs=tol)
    else:
        # Fall back to derived sum if no explicit total is stored.
        assert total_idc_from_tranches == pytest.approx(expected_total_idc, rel=0, abs=tol)


# ---------------------------------------------------------------------------
# Regression tests – edge_extreme_stress
# ---------------------------------------------------------------------------


def test_edge_stress_construction_and_tenor_pinned() -> None:
    """
    Regression: stressed case construction years and tenor must remain stable.

    From the known-good console output:

        V14 Debt Planning: 3-year construction, 15-year tenor
    """
    result = _plan_debt_for_config("edge_extreme_stress.yaml")

    construction_years = result.get("construction_years")
    tenor_years = result.get("tenor_years")

    assert construction_years == 3, f"Expected 3-year construction, got {construction_years!r}"
    assert tenor_years == 15, f"Expected 15-year tenor, got {tenor_years!r}"


def test_edge_stress_idc_totals_pinned() -> None:
    """
    Regression: stressed case IDC per tranche pinned to known-good values.

    From the console log:

        LKR: Principal $69199951.80M (IDC: $18199951.80M)
        USD: Principal $31534559.70M (IDC: $6034559.70M)
        DFI: Principal $25500000.00M (IDC: $0.00M)
        V14 Results: Min DSCR=0.32, Total IDC=$24234511.50M
    """
    result = _plan_debt_for_config("edge_extreme_stress.yaml")

    lkr = _extract_tranche(result, "lkr")
    usd = _extract_tranche(result, "usd")
    dfi = _extract_tranche(result, "dfi")

    tol = 1e-2

    # Principal amounts (millions)
    assert lkr.get("principal_m") == pytest.approx(69_199_951.80, rel=0, abs=tol)
    assert usd.get("principal_m") == pytest.approx(31_534_559.70, rel=0, abs=tol)
    assert dfi.get("principal_m") == pytest.approx(25_500_000.00, rel=0, abs=tol)

    # IDC amounts (millions)
    assert lkr.get("idc_m") == pytest.approx(18_199_951.80, rel=0, abs=tol)
    assert usd.get("idc_m") == pytest.approx(6_034_559.70, rel=0, abs=tol)
    assert dfi.get("idc_m") == pytest.approx(0.00, rel=0, abs=tol)

    # Total IDC – explicit or derived
    total_idc_from_tranches = (
        lkr.get("idc_m", 0.0) + usd.get("idc_m", 0.0) + dfi.get("idc_m", 0.0)
    )
    expected_total_idc = 24_234_511.50

    if "total_idc_m" in result:
        assert result["total_idc_m"] == pytest.approx(expected_total_idc, rel=0, abs=tol)
    else:
        assert total_idc_from_tranches == pytest.approx(expected_total_idc, rel=0, abs=tol)
