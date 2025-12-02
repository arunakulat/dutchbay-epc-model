"""
Debt construction + IDC regression pins for the v14 debt engine.

Canonical suite (v14)
---------------------
- This is the **single source of truth** for v14 debt/IDC regression pins.
- All expectations here are based on the CURRENT v14 engine behaviour and the
  shipped scenario YAMLs.

Scenarios covered
-----------------
1) dutchbay_lendercase_2025Q4.yaml  (“Lender case”)
   - 2-year construction
   - 15-year tenor
   - Three active tranches: LKR / USD / DFI
   - Principals and IDC pinned to ACTUAL v14 values
   - Total IDC and min DSCR pinned

2) edge_extreme_stress.yaml  (“Edge stress”)
   - 2-year construction
   - 17-year tenor
   - All debt in the USD tranche (LKR/DFI empty)
   - USD principal + IDC pinned to ACTUAL v14 values
   - Total IDC pinned
   - Min DSCR checked for sanity band (not absurd)

If you change either scenario YAML or the debt engine, you must DELIBERATELY
re-baseline these pins by:
  - Re-running `_plan_debt_for_config(...)` for the scenario, and
  - Updating the constants and comments below.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from finance.cashflow_v14 import build_annual_rows
from finance.debt_v14 import plan_debt

# ============================================================================
# Helpers
# ============================================================================


def _plan_debt_for_config(scenario_filename: str) -> dict:
    """Load scenario, build cashflows, and run the v14 debt planner."""
    from analytics.scenario_loader import load_scenario_config

    scenario_path = Path("scenarios") / scenario_filename
    cfg = load_scenario_config(str(scenario_path))
    annual_rows = build_annual_rows(cfg)
    return plan_debt(annual_rows=annual_rows, config=cfg)


def _extract_tranche(debt_result: dict, tranche: str) -> dict:
    """Extract a tranche dict (lkr / usd / dfi) from plan_debt result."""
    if tranche not in debt_result:
        raise KeyError(f"Tranche '{tranche}' not found in debt result")
    return debt_result[tranche]


# ============================================================================
# Lendercase regression pins (DutchBay 2025Q4 – 3-tranche structure)
# ============================================================================


def test_lendercase_construction_and_tenor_pinned() -> None:
    """
    Lendercase timeline pin:
    - 2-year construction
    - 15-year tenor
    """
    result = _plan_debt_for_config("dutchbay_lendercase_2025Q4.yaml")
    construction_years = result.get("construction_years")
    tenor_years = result.get("tenor_years")

    assert (
        construction_years == 2
    ), f"Expected 2-year construction, got {construction_years!r}"
    assert tenor_years == 15, f"Expected 15-year tenor, got {tenor_years!r}"


def test_lendercase_idc_totals_pinned() -> None:
    """
    Regression pin: lendercase 2025Q4 IDC + principal by tranche.

    Pins reflect ACTUAL v14 engine output for dutchbay_lendercase_2025Q4.yaml
    (including capitalised IDC).

    As of the current v14 snapshot:
      - LKR principal_m ≈  53,071,200.00
      - USD principal_m ≈  52,698,515.62
      - DFI principal_m ≈  11,545,931.25
        => total principal_m ≈ 117,315,646.88

      - LKR idc_m       ≈   5,821,200.00
      - USD idc_m       ≈   5,448,515.62
      - DFI idc_m       ≈   1,045,931.25
        => total_idc     ≈  12,315,646.88

      - min_dscr        ≈   1.30
      - audit_status    ==  "REVIEW"
    """
    result = _plan_debt_for_config("dutchbay_lendercase_2025Q4.yaml")
    lkr = _extract_tranche(result, "lkr")
    usd = _extract_tranche(result, "usd")
    dfi = _extract_tranche(result, "dfi")
    tol = 0.002  # 0.2% relative tolerance

    # Principals by tranche (absolute USD amounts, not "millions")
    assert float(lkr.get("principal_m", 0.0)) == pytest.approx(53_071_200.00, rel=tol)
    assert float(usd.get("principal_m", 0.0)) == pytest.approx(52_698_515.62, rel=tol)
    assert float(dfi.get("principal_m", 0.0)) == pytest.approx(11_545_931.25, rel=tol)

    total_principal = (
        float(lkr.get("principal_m", 0.0))
        + float(usd.get("principal_m", 0.0))
        + float(dfi.get("principal_m", 0.0))
    )
    assert total_principal == pytest.approx(117_315_646.88, rel=tol)

    # IDC by tranche
    assert float(lkr.get("idc_m", 0.0)) == pytest.approx(5_821_200.00, rel=tol)
    assert float(usd.get("idc_m", 0.0)) == pytest.approx(5_448_515.62, rel=tol)
    assert float(dfi.get("idc_m", 0.0)) == pytest.approx(1_045_931.25, rel=tol)

    total_idc = float(result.get("total_idc", 0.0))
    assert total_idc == pytest.approx(12_315_646.88, rel=tol)

    # Min DSCR and audit status
    min_dscr = float(result.get("min_dscr"))
    assert min_dscr == pytest.approx(1.30, rel=tol)

    audit_status = str(result.get("audit_status", "")).upper()
    assert audit_status == "REVIEW"


# ============================================================================
# Edge stress regression pins (edge_extreme_stress – USD-only tranche)
# ============================================================================


def test_edge_stress_construction_and_tenor_pinned() -> None:
    """
    Edge stress timeline pin.

    With the CURRENT edge_extreme_stress.yaml, the engine resolves to:
    - 2-year construction
    - 17-year tenor
    """
    result = _plan_debt_for_config("edge_extreme_stress.yaml")
    construction_years = result.get("construction_years")
    tenor_years = result.get("tenor_years")

    assert (
        construction_years == 2
    ), f"Expected 2-year construction, got {construction_years!r}"
    assert tenor_years == 17, f"Expected 17-year tenor, got {tenor_years!r}"


def test_edge_stress_idc_totals_pinned() -> None:
    """
    Edge stress regression pin – CURRENT v14 behaviour.

    The present edge_extreme_stress.yaml drives:
      - All debt into the USD tranche
      - LKR and DFI tranches empty
      - 2-year construction, 17-year tenor

    Canonical v14 outputs (from engine snapshot):
      - usd.principal_m ≈ 100,344,600.00
      - usd.idc_m       ≈ 10,344,600.00
      - total_idc       ≈ 10,344,600.00
    """
    result = _plan_debt_for_config("edge_extreme_stress.yaml")
    lkr = _extract_tranche(result, "lkr")
    usd = _extract_tranche(result, "usd")
    dfi = _extract_tranche(result, "dfi")
    tol = 0.002  # 0.2% relative tolerance

    # LKR and DFI tranches are empty in this edge case
    assert float(lkr.get("principal_m", 0.0)) == pytest.approx(0.0, rel=tol)
    assert float(lkr.get("idc_m", 0.0)) == pytest.approx(0.0, rel=tol)

    assert float(dfi.get("principal_m", 0.0)) == pytest.approx(0.0, rel=tol)
    assert float(dfi.get("idc_m", 0.0)) == pytest.approx(0.0, rel=tol)

    # All debt lives in the USD tranche.
    assert float(usd.get("principal_m", 0.0)) == pytest.approx(100_344_600.0, rel=tol)
    assert float(usd.get("idc_m", 0.0)) == pytest.approx(10_344_600.0, rel=tol)

    # Total IDC should essentially be the USD IDC.
    total_idc = float(result.get("total_idc", 0.0))
    assert total_idc == pytest.approx(10_344_600.0, rel=tol)

    # DSCR sanity band – we don't pin an exact number here, just "not insane".
    min_dscr = float(result.get("min_dscr"))
    assert -50.0 < min_dscr < 50.0
