"""Bind the lender scenario's ``expected_results`` to the actual engine output.

The lender scenario advertises an ``expected_results`` block "For Pipeline
Validation", but its financial metrics had drifted to discredited fiction
(project IRR 14.5% / equity IRR 18.5% / NPV $45M / min DSCR 1.45) while the
engine produced 8.35% / 1.31% / $1.18M / 1.30 — and **no test asserted them**, so
the lender case shipped systematically-more-bankable numbers than the model
yields.

This test makes ``expected_results`` a real, enforced validation target
(CESSPIT pre-flight integrity): it reads the financial targets straight from the
YAML and asserts the live canonical pipeline reproduces them, so the block can
never silently diverge from the engine again.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from analytics.pipeline_v14_enhanced import run_v14_pipeline

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"

# expected_results key -> (live KPI key, scale, absolute tolerance).
# Tolerances absorb the 4-sig-fig rounding in the YAML, nothing more.
FINANCIAL_TARGETS = {
    "project_irr": ("project_irr", 1.0, 0.005),
    "equity_irr": ("equity_irr", 1.0, 0.005),
    "project_npv_m_usd": ("project_npv", 1e-6, 0.10),  # KPI is USD; target is $M
    "min_dscr": ("min_dscr", 1.0, 0.02),
    "avg_dscr": ("avg_dscr", 1.0, 0.02),
    "llcr": ("llcr", 1.0, 0.02),
    "plcr": ("plcr", 1.0, 0.02),
}


def _expected_results() -> dict:
    with LENDER.open("r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    er = cfg.get("expected_results")
    assert isinstance(er, dict), "lender scenario is missing expected_results"
    return er


def test_lendercase_financials_match_expected_results() -> None:
    """The live pipeline must reproduce every financial expected_results value."""
    expected = _expected_results()
    kpis = run_v14_pipeline(config=str(LENDER))["kpis"]

    mismatches = []
    for er_key, (kpi_key, scale, tol) in FINANCIAL_TARGETS.items():
        assert er_key in expected, f"expected_results missing {er_key}"
        target = float(expected[er_key])
        actual_scaled = float(kpis[kpi_key]) * scale
        if abs(actual_scaled - target) > tol:
            mismatches.append(
                f"{er_key}: expected_results={target}, engine={actual_scaled:.5f} "
                f"(|Δ|={abs(actual_scaled - target):.5f} > {tol})"
            )

    assert not mismatches, (
        "expected_results no longer matches the engine — regenerate the block "
        "from the canonical run (do NOT hand-edit toward a rosier number):\n  "
        + "\n  ".join(mismatches)
    )


def test_expected_results_are_not_the_discredited_fiction() -> None:
    """Guard specifically against the old inflated placeholders creeping back."""
    expected = _expected_results()
    # Guard against the pre-honest-baseline FICTION (0.145 / 0.185 / $45M / 1.45),
    # distinct from the legitimate 15x10MW re-model (~0.111 / 0.062 / $27M / 1.30).
    # Thresholds sit between the two so the discredited fiction can't creep back.
    assert float(expected["project_irr"]) < 0.13, "project_irr looks like the old fiction"
    assert float(expected["equity_irr"]) < 0.10, "equity_irr looks like the old fiction"
    assert float(expected["min_dscr"]) < 1.40, "min_dscr looks like the old fiction"
    assert float(expected["project_npv_m_usd"]) < 35.0, "NPV looks like the old fiction"
