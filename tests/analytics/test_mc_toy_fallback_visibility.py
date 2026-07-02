"""Regression: toy-fallback usage must be visible, not silent (monte-carlo-6).

The MC engine substitutes deterministic toy KPIs when a trial's real v14
evaluation raises. That is a sanctioned smoke-test mechanism, but it used to be
silent (logged at DEBUG, indistinguishable in the result), so an all-failing
production run reported success_rate=100% with fabricated KPIs. The engine now
tags toy trials and aggregate_trials surfaces ``metadata['toy_fallback_count']``,
so a degenerate run is detectable.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from analytics.mc.engine import run_monte_carlo_analysis

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"


def test_canonical_scenario_uses_no_toy_fallback() -> None:
    """A real run on the canonical scenario must not touch the toy path."""
    base = yaml.safe_load(LENDER.read_text(encoding="utf-8"))
    result = run_monte_carlo_analysis(base_config=base, n_trials=12, seed=42)
    assert result.metadata["toy_fallback_count"] == 0
    assert result.failed_iterations == 0
    assert result.success_rate() == 100.0


def test_degenerate_all_toy_run_is_detectable() -> None:
    """A config that can't satisfy the v14 schema falls entirely to toy — and
    that is now surfaced via toy_fallback_count == n_trials, instead of being a
    silent success."""
    # The param name must RESOLVE (capex.usd_total exists) so the engine doesn't reject it
    # up-front (round-3 guard); the rest of the config is schema-incomplete, so every trial's
    # real v14 eval fails and falls to toy — which is what this test detects.
    minimal = {
        "capex": {"usd_total": 100.0},
        "monte_carlo": {
            "parameters": [{"name": "capex.usd_total", "low": 80, "high": 120}]
        },
    }
    result = run_monte_carlo_analysis(base_config=minimal, n_trials=8, seed=1)
    assert result.metadata["toy_fallback_count"] == 8


# --------------------------------------------------------------------------- #
# MC-9 (#473): opt-in fail-loud — a production run can refuse the toy fallback
# --------------------------------------------------------------------------- #
def test_allow_toy_fallback_false_raises_on_failed_trial() -> None:
    """With monte_carlo.allow_toy_fallback: false, the first failed trial RAISES instead of
    silently substituting fabricated toy KPIs — so a broken production scenario fails loud.
    """
    minimal = {
        "capex": {"usd_total": 100.0},
        "monte_carlo": {
            "parameters": [{"name": "capex.usd_total", "low": 80, "high": 120}],
            "allow_toy_fallback": False,
        },
    }
    with pytest.raises(RuntimeError, match="allow_toy_fallback"):
        run_monte_carlo_analysis(base_config=minimal, n_trials=8, seed=1)


def test_allow_toy_fallback_defaults_true_and_is_surfaced() -> None:
    """Absent the flag the engine keeps the back-compatible fallback AND records the resolved
    value in metadata so a consumer can see which mode produced the result."""
    base = yaml.safe_load(LENDER.read_text(encoding="utf-8"))
    result = run_monte_carlo_analysis(base_config=base, n_trials=8, seed=42)
    assert result.metadata["allow_toy_fallback"] is True
    assert (
        result.metadata["toy_fallback_count"] == 0
    )  # canonical run uses no fallback anyway


def test_allow_toy_fallback_false_is_a_noop_when_no_trial_fails() -> None:
    """Fail-loud must not change a healthy run: the canonical scenario evaluates every trial
    for real, so allow_toy_fallback: false simply never fires."""
    base = yaml.safe_load(LENDER.read_text(encoding="utf-8"))
    base = dict(base)
    base["monte_carlo"] = {**base.get("monte_carlo", {}), "allow_toy_fallback": False}
    result = run_monte_carlo_analysis(base_config=base, n_trials=8, seed=42)
    assert result.metadata["allow_toy_fallback"] is False
    assert result.metadata["toy_fallback_count"] == 0
    assert result.success_rate() == 100.0


# --------------------------------------------------------------------------- #
# CLI status no longer hardcoded "success" (Wave-2 fix)
# --------------------------------------------------------------------------- #
from analytics.cli.cli_monte_carlo_hydra import _derive_run_status  # noqa: E402


def test_cli_status_degenerate_when_all_toy() -> None:
    """All trials toy (no real eval) -> degenerate, never a clean success."""
    assert (
        _derive_run_status(iterations=200, failed_iterations=0, toy_fallback_count=200)
        == "degenerate"
    )


def test_cli_status_degraded_when_some_toy_or_failed() -> None:
    assert (
        _derive_run_status(iterations=200, failed_iterations=0, toy_fallback_count=5)
        == "degraded"
    )
    assert (
        _derive_run_status(iterations=200, failed_iterations=3, toy_fallback_count=0)
        == "degraded"
    )


def test_cli_status_success_only_when_all_real() -> None:
    assert (
        _derive_run_status(iterations=200, failed_iterations=0, toy_fallback_count=0)
        == "success"
    )


def test_mc_warns_on_non_resolving_parameter_name(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A monte_carlo.parameters name that does not resolve to a real config path is a likely
    dead key. Contrary to the old story it does NOT fall to the toy metric — the override is
    merged as an unread key, so trials succeed with real KPIs but the lever moves nothing.
    The MC engine WARNS at construction (round-3) and the dead name is recorded; whether the
    sweep actually collapsed is confirmed post-run by metadata['degenerate_sweep'] (round-5).
    (Not a hard raise: non-dotted aliases are an accepted legacy input.)"""
    import logging

    from analytics.mc.engine import MonteCarloEngine

    cfg = {
        "fx": {"start_lkr_per_usd": 333.79},
        "monte_carlo": {
            "parameters": [{"name": "not.a.real.key", "low": 0.1, "high": 0.2}]
        },
    }
    with caplog.at_level(logging.WARNING, logger="analytics.mc.engine"):
        MonteCarloEngine(base_config=cfg)  # constructs (no raise)
    assert "does not resolve" in caplog.text


def test_dead_param_name_flags_degenerate_sweep() -> None:
    """Round-5: a non-resolving (dead) dotted param name silently merges as an unread config
    key, so every real trial succeeds with IDENTICAL KPIs (toy_fallback_count == 0,
    failed_iterations == 0) and the risk distribution is fake-stable. The prior warn-only fix
    did not reach the result object; the run is now flagged in-band so a lender can see it.
    """
    base = yaml.safe_load(LENDER.read_text(encoding="utf-8"))

    dead = dict(base)
    dead["monte_carlo"] = {
        "parameters": [{"name": "project.capacity_factorr", "low": 0.30, "high": 0.34}]
    }
    r = run_monte_carlo_analysis(base_config=dead, n_trials=8, seed=1)
    # Real evaluation succeeded on every trial (NOT a toy-fallback degeneracy)...
    assert r.metadata["toy_fallback_count"] == 0
    assert r.failed_iterations == 0
    # ...but the sweep moved nothing -> zero dispersion, now surfaced in the result.
    assert r.project_irr_std == 0.0
    assert r.metadata["degenerate_sweep"] is True
    assert "project.capacity_factorr" in r.metadata["dead_param_names"]
    assert "project_irr" in r.metadata["zero_variance_metrics"]


def test_live_param_name_is_not_flagged_degenerate() -> None:
    """The control: a resolving dotted lever moves outputs, so degenerate_sweep stays False
    and nothing lands in dead_param_names (guards against false positives that would cry wolf
    on every real sweep)."""
    base = yaml.safe_load(LENDER.read_text(encoding="utf-8"))

    live = dict(base)
    live["monte_carlo"] = {
        "parameters": [{"name": "project.capacity_factor", "low": 0.30, "high": 0.34}]
    }
    r = run_monte_carlo_analysis(base_config=live, n_trials=8, seed=1)
    assert r.project_irr_std is not None and r.project_irr_std > 0.0
    assert r.metadata["degenerate_sweep"] is False
    assert r.metadata["dead_param_names"] == []


# --------------------------------------------------------------------------- #
# Scenario monte_carlo reporting config is honored (Wave-2 fix)
# --------------------------------------------------------------------------- #
def test_scenario_percentiles_and_var_cvar_are_honored() -> None:
    """The canonical scenario declares monte_carlo.percentiles [10,25,50,75,90] +
    var_confidence/cvar_confidence. The engine previously ignored them (hardcoded
    [5,10,50,90,95], no VaR/CVaR). It must now emit exactly the requested percentiles and
    surface downside VaR/CVaR per metric in metadata."""
    cfg = yaml.safe_load(LENDER.read_text())
    result = run_monte_carlo_analysis(base_config=cfg, n_trials=40, seed=42)
    assert set(result.percentiles) == {10, 25, 50, 75, 90}
    assert result.metadata.get("var_confidence") == 0.95
    var_cvar = result.metadata.get("var_cvar", {})
    assert "project_irr" in var_cvar
    # downside: VaR (5th pctile) <= CVaR is false; CVaR (mean of worst tail) <= VaR.
    assert var_cvar["project_irr"]["cvar"] <= var_cvar["project_irr"]["var"]


def test_absent_percentiles_falls_back_to_default_levels() -> None:
    """A scenario without monte_carlo.percentiles keeps the documented default levels.

    Since #599 the default is DEFAULT_PERCENTILES = (1, 5, 10, 50, 90, 95, 99):
    P99 first-class for senior-debt loan-size capping, with the raw 1st percentile
    alongside because for higher-is-better metrics the lender exceedance "P99" is
    the RAW 1st percentile (the raw 99th is the upside tail — #563 convention).
    """
    cfg = yaml.safe_load(LENDER.read_text())
    cfg["monte_carlo"].pop("percentiles", None)
    result = run_monte_carlo_analysis(base_config=cfg, n_trials=40, seed=42)
    assert set(result.percentiles) == {1, 5, 10, 50, 90, 95, 99}
    # Raw-percentile monotonicity across the new tail levels: the downside
    # (lender-P99 = raw 1st) sits at or below every other level, the raw 99th
    # at or above.
    for metric, levels in result.summary.items():
        pct = levels["percentiles"]
        assert (
            pct[1] <= pct[5] <= pct[50] <= pct[95] <= pct[99]
        ), f"{metric} percentile ordering violated: {pct}"
