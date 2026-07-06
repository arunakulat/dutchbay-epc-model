"""4-way cross-technology comparison scenarios (#821, #745 follow-up) — tests.

#745 slice-1 shipped the comparison table over the TWO lender configs that existed then (wind +
hybrid). #821 authors the two missing bankable-input columns so the table becomes the full 4-way
(wind / solar / hybrid / hybrid+BESS) set:

  - ``scenarios/dutchbay_solar_only_2025Q4.yaml`` — a 150 MWac fixed-tilt PV lender case (CF 0.1685
    on the frozen PVGIS TMY; #529), on the same lender debt/tax/FX/WACC stack.
  - ``scenarios/dutchbay_hybrid_bess_2025Q4.yaml`` — the wind+solar hybrid with a co-located
    50 MW/200 MWh capacity-charge BESS whose $25M turnkey capex is rolled into ``capex.usd_total``
    (financed, BESS-3), booking a capacity charge additively on top of generation revenue.

These are COMPARISON scenarios (bankable inputs), NOT the committed 5th-gen canon. The load-bearing
guarantee this module pins is KPI-NEUTRALITY: adding these two configs (and their columns to the
comparison table) leaves the committed wind lendercase canon byte-identical — the wind column of the
4-way table still equals ``run_v14_pipeline`` on the lendercase EXACTLY, i.e. the frozen canonical
``project_irr`` / ``min_dscr`` / solved gearing.

These tests assert REAL evidence:
  - each new config runs through the CANONICAL strict pipeline and publishes finite, distinct KPIs;
  - the hybrid+BESS books a NON-ZERO BESS capacity charge additive to generation revenue, and the
    BESS capex is actually financed (usd_total grew by the battery cost — BESS-3, not free revenue);
  - the 4-way emitter yields four distinct columns whose wind column reconciles to the frozen canon.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from analytics.pipeline_v14_enhanced import run_v14_pipeline
from app.reports.report_model import TechComparisonBlock
from app.reports.tech_comparison_emit import build_tech_comparison_for_scenarios

REPO_ROOT = Path(__file__).resolve().parents[2]
SCEN = REPO_ROOT / "scenarios"

WIND_SCENARIO = SCEN / "dutchbay_lendercase_2025Q4.yaml"
SOLAR_SCENARIO = SCEN / "dutchbay_solar_only_2025Q4.yaml"
HYBRID_SCENARIO = SCEN / "dutchbay_hybrid_windsolar_2025Q4.yaml"
HYBRID_BESS_SCENARIO = SCEN / "dutchbay_hybrid_bess_2025Q4.yaml"

#: The frozen committed 5th-gen wind lendercase canon (must never move — the KPI-neutrality gate).
_CANON_PROJECT_IRR = 0.014551597740253388
_CANON_MIN_DSCR = 1.285740985294611
_CANON_GEARING = 0.41


# --------------------------------------------------------------------------- #
# The two new configs exist and run through the canonical strict pipeline.
# --------------------------------------------------------------------------- #
def test_new_scenario_files_exist() -> None:
    """Both #821 bankable-input configs are present on disk (the emitter fail-loud needs the paths)."""
    assert SOLAR_SCENARIO.exists()
    assert HYBRID_BESS_SCENARIO.exists()


def test_solar_only_runs_canonically_with_finite_distinct_kpis() -> None:
    """The solar-only config validates + runs; its economics are finite and distinct from wind."""
    solar = run_v14_pipeline(config=str(SOLAR_SCENARIO), validation_mode="strict")
    wind = run_v14_pipeline(config=str(WIND_SCENARIO), validation_mode="strict")
    s_irr = solar["kpis"]["project_irr"]
    assert s_irr == pytest.approx(-0.03435761479654192)
    # A real, distinct second technology — the lower-CF flat-LKR PV is materially worse than wind,
    # not a copy of it (a spurious pass would be s_irr == wind_irr).
    assert s_irr != wind["kpis"]["project_irr"]
    assert s_irr < wind["kpis"]["project_irr"]
    # The solar column carries its OWN dual-DSCR solved gearing (distinct from wind's 0.41).
    solved = solar["debt_result"]["dual_dscr"]["solved_gearing"]
    assert solved == pytest.approx(0.2025)
    assert solved != _CANON_GEARING


def test_hybrid_bess_books_financed_additive_capacity_charge() -> None:
    """The BESS capacity charge is booked ADDITIVELY on top of generation, and its capex is financed.

    Real evidence (BESS-3), not a trivially-true identity:
      - year-1 ``bess_revenue_lkr`` equals R x power_mw x 12 (5,000,000 x 50 x 12) exactly;
      - generation revenue is still positive alongside it (additive, not a replacement);
      - the financed ``capex.usd_total`` grew by the battery cost vs the base hybrid (25M), so the
        project IRR reflects a battery that was paid for, not a free revenue uplift.
    """
    out = run_v14_pipeline(config=str(HYBRID_BESS_SCENARIO), validation_mode="strict")
    rows = out["annual_rows"]
    assert rows, "hybrid+BESS produced no annual rows"
    expected_year1_charge = 5_000_000 * 50 * 12  # R x power_mw x 12 (SoH 1.0, year 1)
    assert rows[0]["bess_revenue_lkr"] == pytest.approx(expected_year1_charge)
    assert rows[0]["generation_revenue_lkr"] > 0  # additive, not a replacement

    # BESS-3: the battery is financed — the hybrid+BESS financed capex is the base hybrid's plus 25M.
    # The engine sizes debt as gearing x financed_capex, so financed_capex = debt_total / gearing
    # recovers the base the battery was actually financed against (not a config echo).
    hybrid = run_v14_pipeline(config=str(HYBRID_SCENARIO), validation_mode="strict")
    bess_total = (
        out["debt_result"]["debt_total"]
        / out["debt_result"]["dual_dscr"]["solved_gearing"]
    )
    hybrid_total = (
        hybrid["debt_result"]["debt_total"]
        / hybrid["debt_result"]["dual_dscr"]["solved_gearing"]
    )
    assert bess_total == pytest.approx(224_600_000)
    assert bess_total == pytest.approx(hybrid_total + 25_000_000)

    # The extra tolling revenue net of the financed battery lifts project IRR above the plain hybrid
    # (a distinct, non-trivial economics — the fourth column is real), and stays finite.
    b_irr = out["kpis"]["project_irr"]
    assert b_irr == pytest.approx(0.033725746189781663)
    assert b_irr > hybrid["kpis"]["project_irr"]


# --------------------------------------------------------------------------- #
# The 4-way comparison table: four distinct columns; wind reconciles to canon.
# --------------------------------------------------------------------------- #
def test_four_way_comparison_columns_are_distinct() -> None:
    """The emitter yields four distinct columns (wind / solar / hybrid / hybrid+BESS)."""
    block = build_tech_comparison_for_scenarios(
        [
            ("Wind", str(WIND_SCENARIO)),
            ("Solar", str(SOLAR_SCENARIO)),
            ("Hybrid", str(HYBRID_SCENARIO)),
            ("Hybrid+BESS", str(HYBRID_BESS_SCENARIO)),
        ]
    )
    assert isinstance(block, TechComparisonBlock)
    assert [r.label for r in block.rows] == ["Wind", "Solar", "Hybrid", "Hybrid+BESS"]
    irrs = [r.project_irr for r in block.rows]
    assert all(v is not None for v in irrs)
    # Four genuinely different economics — no fabricated / duplicated column.
    assert len(set(irrs)) == 4
    gearings = [r.gearing for r in block.rows]
    assert all(g is not None for g in gearings)
    assert len(set(gearings)) == 4


def test_four_way_wind_column_reconciles_to_frozen_canon() -> None:
    """KPI-NEUTRALITY GATE: adding the two columns leaves the wind column on the frozen canon.

    The wind column of the 4-way table must still equal ``run_v14_pipeline`` on the committed
    lendercase EXACTLY — the frozen 5th-gen ``project_irr`` / ``min_dscr`` / solved gearing. If a
    new config or a comparison change perturbed the wind lendercase, this pin fails.
    """
    block = build_tech_comparison_for_scenarios(
        [
            ("Wind", str(WIND_SCENARIO)),
            ("Solar", str(SOLAR_SCENARIO)),
            ("Hybrid", str(HYBRID_SCENARIO)),
            ("Hybrid+BESS", str(HYBRID_BESS_SCENARIO)),
        ]
    )
    wind = block.rows[0]
    wind_run = run_v14_pipeline(config=str(WIND_SCENARIO), validation_mode="strict")
    # Reconciles to the independent canonical run of the same config ...
    assert wind.project_irr == wind_run["kpis"]["project_irr"]
    assert wind.min_dscr == wind_run["kpis"]["min_dscr"]
    # ... and that run is byte-identical to the frozen committed canon.
    assert wind.project_irr == _CANON_PROJECT_IRR
    assert wind.min_dscr == pytest.approx(_CANON_MIN_DSCR)
    assert wind.gearing == pytest.approx(_CANON_GEARING)
