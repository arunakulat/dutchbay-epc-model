from __future__ import annotations

"""
End-to-end integrity tests for analytics.core.sensitivity_runner.

CESSPIT pre-flight rationale
----------------------------
The public path-based sensitivity entry point (wired to the sensitivity CLIs)
previously imported and type-checked cleanly but crashed at *call time* on a
non-existent ``StandardShockLibrary`` factory API and on ``ShockSpec`` fields
that do not exist. It had only an import smoke test, never a functional one,
so the defect survived undetected.

These tests exercise the repaired entry point against the canonical scenario
and guard the two failure modes that matter for a lender-facing tornado:
  1. a call-time crash (the original bug), and
  2. a *silent no-op* — a tornado whose shocks do not actually move the metric
     (the class of bug fixed in PR #150).
"""

from pathlib import Path

import pytest

from analytics.contracts_v14 import ParameterRangeConfig, SensitivitySuite
from analytics.core.sensitivity_runner import run_sensitivity_analysis
from analytics.sensitivity.adapters import parameter_to_engine_spec

BASECASE = Path("scenarios/dutchbay_basecase_2025Q4.yaml")


def test_default_run_returns_suite_with_live_tornados() -> None:
    """Default driver library runs end-to-end and actually moves the metric."""
    suite = run_sensitivity_analysis(str(BASECASE), metric="project_irr")

    assert isinstance(suite, SensitivitySuite)
    assert suite.metric == "project_irr"
    assert len(suite.tornado_results) >= 1
    # Anti-silent-no-op guard: at least one driver must register real impact.
    assert any(t.impact_abs > 0 for t in suite.tornado_results), (
        "all tornado bars are flat — shocks are not reaching the model "
        "(silent no-op regression)"
    )


def test_basecase_project_irr_pins() -> None:
    """Base KPIs reflect the canonical baseline, not a degenerate run."""
    suite = run_sensitivity_analysis(str(BASECASE), metric="project_irr")
    base = suite.base_kpis.get("project_irr")
    assert base is not None
    # Construction-lag-correct project IRR (audit finding 2.0): basecase ~7.9% (was ~13%
    # before the operating-year-1 off-by-one + 2-yr build lag were corrected).
    assert 0.07 < base < 0.09


def test_explicit_parameters_override_defaults() -> None:
    """Caller-supplied parameters bypass the default driver library."""
    param = ParameterRangeConfig(
        variable_name="capex.usd_total",
        base_value=150_000_000.0,
        low_pct=-10.0,
        high_pct=10.0,
        label="CAPEX",
    )
    suite = run_sensitivity_analysis(
        str(BASECASE), metric="project_irr", parameters=[param]
    )
    assert len(suite.tornado_results) == 1
    assert suite.tornado_results[0].impact_abs > 0


def test_adapter_supports_absolute_value_mode() -> None:
    """Absolute (low_value/high_value) mode must not crash — regression guard
    for the float(None) defect in parameter_to_engine_spec."""
    param = ParameterRangeConfig(
        variable_name="capex.usd_total",
        base_value=150_000_000.0,
        low_value=135_000_000.0,
        high_value=165_000_000.0,
        label="CAPEX",
    )
    spec = parameter_to_engine_spec(param)
    assert spec["low"] == pytest.approx(135_000_000.0)
    assert spec["high"] == pytest.approx(165_000_000.0)


def test_adapter_percentage_mode() -> None:
    """Percentage mode derives absolute bounds from base_value."""
    param = ParameterRangeConfig(
        variable_name="capex.usd_total",
        base_value=1000.0,
        low_pct=-10.0,
        high_pct=10.0,
    )
    spec = parameter_to_engine_spec(param)
    assert spec["low"] == pytest.approx(900.0)
    assert spec["high"] == pytest.approx(1100.0)


# ---------------------------------------------------------------------------
# Wave-2 #23: degenerate (structurally flat) metric flag. A covenant-pinned
# DSCR tornado under dual_dscr sizing returns all-zero bars; the suite must say
# so loudly instead of silently presenting a chart of zeros as "no risk".
# ---------------------------------------------------------------------------
def test_live_metric_is_not_flagged_flat() -> None:
    """project_irr genuinely moves, so flat_metric is False."""
    suite = run_sensitivity_analysis(str(BASECASE), metric="project_irr")
    assert suite.metadata.get("flat_metric") is False
    assert "flat_metric_reason" not in suite.metadata


def test_covenant_pinned_dscr_tornado_is_flagged_flat() -> None:
    """min_dscr is pinned by dual_dscr debt sizing: every bar is ~0, so the suite
    is flagged flat with a covenant-pinned reason rather than misrepresenting it."""
    suite = run_sensitivity_analysis(str(BASECASE), metric="min_dscr")
    assert max(abs(t.impact_abs) for t in suite.tornado_results) < 1e-9
    assert suite.metadata.get("flat_metric") is True
    assert "covenant" in suite.metadata.get("flat_metric_reason", "").lower()
