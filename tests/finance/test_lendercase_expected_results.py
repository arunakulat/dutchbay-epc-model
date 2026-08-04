"""Bind the lender case's financial-KPI targets to the actual engine output.

The lender scenario once advertised an ``expected_results`` block "For Pipeline
Validation", but its financial metrics had drifted to discredited fiction
(project IRR 14.5% / equity IRR 18.5% / NPV $45M / min DSCR 1.45) while the
engine produced 8.35% / 1.31% / $1.18M / 1.30 — and **no test asserted them**, so
the lender case shipped systematically-more-bankable numbers than the model
yields.

This test makes those targets a real, enforced validation target (CESSPIT
pre-flight integrity): it reads the financial targets and asserts the live
canonical pipeline reproduces them, so they can never silently diverge from the
engine again.

Per #996 D3 the numeric financial-KPI targets now live in a test-only golden
fixture (``tests/fixtures/finance/lendercase_expected_kpis.json``) rather than in
the scenario's own ``expected_results`` block — a runtime-input scenario must not
double as its own regression oracle. The scenario keeps only the values the engine
and reconciliation guard actually consume at runtime (``net_aep_p50_gwh`` /
``net_aep_p90_gwh`` / ``capacity_factor``); ``test_lendercase_scenario_retains_aep_inputs``
locks that in. The loose absolute tolerances here absorb the 4-sig-fig rounding in
the fixture; the full-precision byte-identity gate is
``tests/finance/test_multitech_generation.py::test_canonical_lendercase_economics_unchanged``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from analytics.pipeline_v14_enhanced import run_v14_pipeline

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"
EXPECTED_KPIS = (
    REPO_ROOT / "tests" / "fixtures" / "finance" / "lendercase_expected_kpis.json"
)

# fixture key -> (live KPI key, scale, absolute tolerance).
# Tolerances absorb the 4-sig-fig rounding in the fixture, nothing more.
FINANCIAL_TARGETS = {
    "project_irr": ("project_irr", 1.0, 0.005),
    "equity_irr": ("equity_irr", 1.0, 0.005),
    "project_npv_m_usd": ("project_npv", 1e-6, 0.10),  # KPI is USD; target is $M
    "min_dscr": ("min_dscr", 1.0, 0.02),
    "avg_dscr": ("avg_dscr", 1.0, 0.02),
    "llcr": ("llcr", 1.0, 0.02),
    "plcr": ("plcr", 1.0, 0.02),
}


def _expected_kpis() -> dict[str, Any]:
    with EXPECTED_KPIS.open("r", encoding="utf-8") as fh:
        kpis = json.load(fh)
    assert isinstance(kpis, dict), "lender-case expected-KPIs fixture is malformed"
    return kpis


def test_lendercase_financials_match_expected_results() -> None:
    """The live pipeline must reproduce every financial target in the fixture."""
    expected = _expected_kpis()
    kpis = run_v14_pipeline(config=str(LENDER))["kpis"]

    mismatches = []
    for fx_key, (kpi_key, scale, tol) in FINANCIAL_TARGETS.items():
        assert fx_key in expected, f"fixture missing {fx_key}"
        target = float(expected[fx_key])
        actual_scaled = float(kpis[kpi_key]) * scale
        if abs(actual_scaled - target) > tol:
            mismatches.append(
                f"{fx_key}: fixture={target}, engine={actual_scaled:.5f} "
                f"(|Δ|={abs(actual_scaled - target):.5f} > {tol})"
            )

    assert not mismatches, (
        "lender-case KPIs no longer match the engine — regenerate the fixture "
        "tests/fixtures/finance/lendercase_expected_kpis.json from the canonical run "
        "(do NOT hand-edit toward a rosier number):\n  " + "\n  ".join(mismatches)
    )


def test_expected_results_are_not_the_discredited_fiction() -> None:
    """Guard specifically against the old inflated placeholders creeping back."""
    expected = _expected_kpis()
    # Guard against the pre-honest-baseline FICTION (0.145 / 0.185 / $45M / 1.45),
    # distinct from the legitimate 15x10MW re-model (~0.111 / 0.062 / $27M / 1.30).
    # Thresholds sit between the two so the discredited fiction can't creep back.
    assert (
        float(expected["project_irr"]) < 0.13
    ), "project_irr looks like the old fiction"
    assert float(expected["equity_irr"]) < 0.10, "equity_irr looks like the old fiction"
    assert float(expected["min_dscr"]) < 1.40, "min_dscr looks like the old fiction"
    assert float(expected["project_npv_m_usd"]) < 35.0, "NPV looks like the old fiction"


def test_lendercase_scenario_retains_aep_inputs() -> None:
    """#996 D3: the split must keep the AEP values the RUNTIME path consumes.

    ``net_aep_p50_gwh`` / ``net_aep_p90_gwh`` are read at runtime by the AEP
    reconciliation guard (``analytics/aep_reconciliation.py``) and downside-debt
    sizing (``finance/debt_v14.py::_resolve_downside_ratio``). Extracting the
    financial-KPI oracle to a fixture must NOT strip these — removing them would
    flip the downside ratio to the flat fallback and silently disarm the guard.
    """
    with LENDER.open("r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    er = cfg.get("expected_results")
    assert isinstance(er, dict), "lender scenario is missing expected_results"
    assert "net_aep_p50_gwh" in er, "runtime input net_aep_p50_gwh was stripped"
    assert "net_aep_p90_gwh" in er, "runtime input net_aep_p90_gwh was stripped"
    # None of the moved financial-KPI oracle keys may remain in the scenario (dual-use
    # guard — all seven, so re-adding avg_dscr/llcr/plcr is caught too).
    for moved in FINANCIAL_TARGETS:
        assert moved not in er, (
            f"{moved} is back in the scenario expected_results — it must live only in "
            "the golden fixture (a runtime-input scenario must not be its own oracle)"
        )
