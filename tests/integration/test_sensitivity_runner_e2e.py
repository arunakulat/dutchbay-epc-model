from __future__ import annotations

"""End-to-end integration test for the v14 SensitivityRunner audit surface (#117).

Replaces the deleted Phase 3 sensitivity-contracts integration test (removed with
the Phase 3 dead-code island in #116). Drives the canonical path entry point
(``analytics.core.sensitivity_runner.run_sensitivity_analysis``) on the basecase
scenario and asserts the Sprint 18C audit fields — ``base_kpis``,
``scenario_name`` and ``analysis_timestamp`` — are populated end-to-end on the
canonical ``SensitivitySuite`` contract, while guarding the two failure modes
that matter for a lender-facing tornado: a call-time crash, and a silent no-op
(a tornado whose shocks do not move the metric).

Framework Compliance:
    - TEST-01: integration-shaped regression pins on the canonical contract surface
    - ARCH-04: canonical contracts_v14 surface only
"""

from datetime import datetime
from pathlib import Path

import pytest

from analytics.contracts_v14 import SensitivityRequest, SensitivitySuite
from analytics.core.sensitivity_runner import run_sensitivity_analysis

BASECASE = Path("scenarios/dutchbay_basecase_2025Q4.yaml")


def _run() -> SensitivitySuite:
    return run_sensitivity_analysis(str(BASECASE), metric="project_irr")


def test_runner_returns_canonical_suite_end_to_end() -> None:
    """Runner produces a canonical SensitivitySuite with live (non-flat) tornados."""
    suite = _run()

    assert isinstance(suite, SensitivitySuite)
    assert suite.metric == "project_irr"
    assert len(suite.tornado_results) >= 1
    # Anti-silent-no-op guard: at least one driver must register real impact.
    assert any(t.impact_abs > 0 for t in suite.tornado_results), (
        "all tornado bars are flat — shocks are not reaching the model"
    )


def test_audit_fields_populated_end_to_end() -> None:
    """Sprint 18C audit surface: base_kpis + scenario_name + analysis_timestamp."""
    suite = _run()

    # base_kpis carries the canonical baseline (not a degenerate run).
    base = suite.base_kpis.get("project_irr")
    assert base is not None
    # construction-lag-correct basecase project IRR ~7.9% (audit finding 2.0)
    assert 0.07 < base < 0.09

    # scenario_name is stamped from the config for provenance.
    assert suite.scenario_name is not None
    assert suite.scenario_name != ""

    # analysis_timestamp is a parseable, timezone-aware ISO-8601 stamp.
    assert suite.analysis_timestamp is not None
    parsed = datetime.fromisoformat(suite.analysis_timestamp)
    assert parsed.tzinfo is not None


def test_request_contract_drives_runner() -> None:
    """A SensitivityRequest's fields drive the runner to the canonical suite.

    The runner is the canonical path entry point; a SensitivityRequest carries the
    same surface (base_config_path / metric / parameters), so its fields round-trip
    cleanly. Empty ``parameters`` falls back to the runner's default driver library.
    """
    request = SensitivityRequest(
        base_config_path=str(BASECASE),
        parameters=[],
        metric="project_irr",
    )

    suite = run_sensitivity_analysis(
        request.base_config_path,
        metric=request.metric,
        parameters=request.parameters or None,
    )

    assert isinstance(suite, SensitivitySuite)
    assert suite.metric == request.metric
    assert suite.scenario_name is not None
    assert len(suite.tornado_results) >= 1


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
