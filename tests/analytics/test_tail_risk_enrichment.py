"""enrich_tail_risk=True must actually enrich the suite — it used to be a no-op.

Roadmap gap #4 (part c). The sensitivity engine had two ``if run_cfg.enrich_tail_risk:
pass`` branches, so opting in silently dropped the work (decorative config / CASPER
violation). The enricher's contract (SensitivitySuite carries .metadata) was always
compatible; this asserts the opt-in now populates the tail-risk metadata, and that
the default leaves it clean.
"""

from __future__ import annotations

from pathlib import Path

from analytics.core.sensitivity_runner import run_sensitivity_analysis
from analytics.sensitivity.engine import SensitivityRunConfig

BASECASE = Path("scenarios/dutchbay_basecase_2025Q4.yaml")


def test_enrich_tail_risk_populates_metadata() -> None:
    suite = run_sensitivity_analysis(
        str(BASECASE),
        metric="project_irr",
        run_cfg=SensitivityRunConfig(enrich_tail_risk=True),
    )
    # The enricher attaches both the per-parameter table and the summary view.
    assert "tail_risk" in suite.metadata
    assert "tail_risk_summary" in suite.metadata


def test_default_leaves_tail_risk_metadata_clean() -> None:
    suite = run_sensitivity_analysis(
        str(BASECASE),
        metric="project_irr",
        run_cfg=SensitivityRunConfig(enrich_tail_risk=False),
    )
    assert "tail_risk" not in suite.metadata
