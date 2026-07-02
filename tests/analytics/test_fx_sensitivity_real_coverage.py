"""Coverage harness for ``analytics.fx_sensitivity_real``.

Exercises the FX-sensitivity compatibility surface end-to-end without paying for
the real (heavy) v14 evaluation pipeline: ``evaluate_with_overrides`` and
``run_v14_pipeline_with_analytics`` are monkeypatched with deterministic stubs so
we can assert the module's own arithmetic — linear fits, variance attribution,
metric extraction, the VaR/CVaR-shaped tail direction of the FX sweep, and the
documented ``ValueError`` / ``KeyError`` raises.

All repo paths resolve relative to this file (CI checks out the repo at a
different absolute root), and every file write lands under ``tmp_path``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from analytics import fx_sensitivity_real as mod
from analytics.fx_sensitivity_real import (
    FXSensitivityAnalyzer,
    FXSensitivityConfig,
    FXSensitivityPoint,
    FXSensitivityResult,
    RealFXSensitivityResult,
    SensitivityCoefficient,
    evaluate_with_overrides,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"


# ---------------------------------------------------------------------------
# FXSensitivityConfig validation
# ---------------------------------------------------------------------------
def test_config_defaults_are_populated() -> None:
    cfg = FXSensitivityConfig()
    assert cfg.target_metric == "project_irr"
    assert cfg.confidence_level == 0.95
    assert cfg.fx_rate_shocks == [-0.10, -0.05, 0.0, 0.05, 0.10]
    assert cfg.hedge_ratio_values == [0.0, 0.5, 1.0]
    # DELTAS around the scenario's base fx.spread_bps — non-negative by default so no
    # committed (unhedged, base-spread-0) path can trip the engine's >= 0 gate (#659).
    assert cfg.spread_shocks_bps == [0.0, 50.0, 100.0]


def test_config_rejects_out_of_range_confidence() -> None:
    with pytest.raises(ValueError, match="confidence_level must be between 0 and 1"):
        FXSensitivityConfig(confidence_level=1.0)
    with pytest.raises(ValueError, match="confidence_level must be between 0 and 1"):
        FXSensitivityConfig(confidence_level=0.0)


def test_config_rejects_unknown_target_metric() -> None:
    with pytest.raises(ValueError, match="target_metric must be one of"):
        FXSensitivityConfig(target_metric="bogus_metric")


def test_config_accepts_all_valid_metrics() -> None:
    for metric in mod.VALID_TARGET_METRICS:
        assert FXSensitivityConfig(target_metric=metric).target_metric == metric


# ---------------------------------------------------------------------------
# evaluate_with_overrides delegation
# ---------------------------------------------------------------------------
def test_evaluate_with_overrides_delegates(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake(
        path: str, overrides: dict[str, Any], *, return_full_result: bool = False
    ) -> dict[str, Any]:
        captured["path"] = path
        captured["overrides"] = overrides
        captured["return_full_result"] = return_full_result
        return {"project_irr": 0.07}

    monkeypatch.setattr("analytics.evaluation_v14.evaluate_with_overrides", fake)
    # KPIs-only by default ...
    out = evaluate_with_overrides("cfg.yaml", {"fx": {"fx_shock": 0.1}})
    assert out == {"project_irr": 0.07}
    assert captured["path"] == "cfg.yaml"
    assert captured["overrides"] == {"fx": {"fx_shock": 0.1}}
    assert captured["return_full_result"] is False
    # ... and the return_full_result flag is forwarded to the real gateway.
    evaluate_with_overrides("cfg.yaml", {"fx": {}}, return_full_result=True)
    assert captured["return_full_result"] is True


# ---------------------------------------------------------------------------
# _metric_from_result — every resolution branch
# ---------------------------------------------------------------------------
def test_metric_from_result_direct_key() -> None:
    assert mod._metric_from_result({"project_irr": 0.08}, "project_irr") == 0.08


def test_metric_from_result_nested_kpis() -> None:
    result = {"kpis": {"equity_irr": 0.12}}
    assert mod._metric_from_result(result, "equity_irr") == 0.12


def test_metric_from_result_nested_baseline_kpis() -> None:
    result = {"baseline_kpis": {"dscr_min": 1.31}}
    assert mod._metric_from_result(result, "dscr_min") == 1.31


def test_metric_from_result_analytics_returns_bucket() -> None:
    result = {
        "analytics_result": {
            "returns_analysis": {
                "project_returns": {"project_irr": 0.054},
                "equity_returns": {"equity_irr": 0.0},
            }
        }
    }
    assert mod._metric_from_result(result, "project_irr") == 0.054
    assert mod._metric_from_result(result, "equity_irr") == 0.0


def test_metric_from_result_equity_returns_bucket_when_project_missing() -> None:
    result = {
        "analytics_result": {
            "returns_analysis": {
                "project_returns": {"other": 1.0},
                "equity_returns": {"equity_irr": 0.033},
            }
        }
    }
    assert mod._metric_from_result(result, "equity_irr") == 0.033


def test_metric_from_result_missing_raises_keyerror() -> None:
    with pytest.raises(KeyError, match="project_irr"):
        mod._metric_from_result({"unrelated": 1.0}, "project_irr")


def test_metric_from_result_ignores_non_dict_nested() -> None:
    # nested keys present but not dicts -> falls through to KeyError
    result = {"kpis": "not-a-dict", "analytics_result": "nope"}
    with pytest.raises(KeyError):
        mod._metric_from_result(result, "project_irr")


# ---------------------------------------------------------------------------
# _linear_fit — slope, degenerate cases, r2, stderr
# ---------------------------------------------------------------------------
def test_linear_fit_positive_slope() -> None:
    coef, variance = mod._linear_fit("fx_rate", [0.0, 1.0, 2.0], [1.0, 3.0, 5.0])
    assert coef.parameter == "fx_rate"
    assert coef.coefficient == pytest.approx(2.0)
    assert coef.r_squared == pytest.approx(1.0)
    assert variance > 0.0


def test_linear_fit_single_point_zero_slope() -> None:
    coef, variance = mod._linear_fit("p", [3.0], [9.0])
    assert coef.coefficient == 0.0
    assert coef.std_error == 0.0
    assert variance == 0.0


def test_linear_fit_zero_denominator_constant_x() -> None:
    coef, _ = mod._linear_fit("p", [2.0, 2.0, 2.0], [1.0, 2.0, 3.0])
    assert coef.coefficient == 0.0


def test_linear_fit_constant_y_r2_is_one() -> None:
    coef, _ = mod._linear_fit("p", [0.0, 1.0, 2.0], [4.0, 4.0, 4.0])
    assert coef.r_squared == 1.0


def test_linear_fit_mismatched_lengths_raises() -> None:
    with pytest.raises(ValueError, match="equal non-zero length"):
        mod._linear_fit("p", [0.0, 1.0], [1.0])


def test_linear_fit_empty_raises() -> None:
    with pytest.raises(ValueError, match="equal non-zero length"):
        mod._linear_fit("p", [], [])


# ---------------------------------------------------------------------------
# RealFXSensitivityResult.calculate_summary_metrics
# ---------------------------------------------------------------------------
def test_calculate_summary_metrics_no_base_irr_is_noop() -> None:
    res = RealFXSensitivityResult(333.79, 0.0, 0.0, base_project_irr=None)
    res.fx_rate_points.append(FXSensitivityPoint(300.0, 0.0, 0.0, project_irr=0.05))
    res.fx_rate_points.append(FXSensitivityPoint(360.0, 0.0, 0.0, project_irr=0.07))
    res.calculate_summary_metrics()
    assert res.fx_rate_irr_sensitivity == 0.0  # untouched


def test_calculate_summary_metrics_fits_slope() -> None:
    res = RealFXSensitivityResult(333.79, 0.0, 0.0, base_project_irr=0.06)
    res.fx_rate_points.append(FXSensitivityPoint(300.0, 0.0, 0.0, project_irr=0.04))
    res.fx_rate_points.append(FXSensitivityPoint(400.0, 0.0, 0.0, project_irr=0.10))
    res.calculate_summary_metrics()
    # slope = (0.10 - 0.04) / (400 - 300) = 6e-4
    assert res.fx_rate_irr_sensitivity == pytest.approx(6e-4)


def test_calculate_summary_metrics_too_few_points_is_noop() -> None:
    res = RealFXSensitivityResult(333.79, 0.0, 0.0, base_project_irr=0.06)
    res.fx_rate_points.append(FXSensitivityPoint(300.0, 0.0, 0.0, project_irr=0.04))
    res.calculate_summary_metrics()
    assert res.fx_rate_irr_sensitivity == 0.0


def test_calculate_summary_metrics_skips_when_irrs_missing() -> None:
    # two points, but project_irr is None on one -> ys shorter than xs -> skipped
    res = RealFXSensitivityResult(333.79, 0.0, 0.0, base_project_irr=0.06)
    res.fx_rate_points.append(FXSensitivityPoint(300.0, 0.0, 0.0, project_irr=None))
    res.fx_rate_points.append(FXSensitivityPoint(400.0, 0.0, 0.0, project_irr=0.10))
    res.calculate_summary_metrics()
    assert res.fx_rate_irr_sensitivity == 0.0


# ---------------------------------------------------------------------------
# FXSensitivityAnalyzer constructor
# ---------------------------------------------------------------------------
def test_analyzer_requires_a_path() -> None:
    with pytest.raises(ValueError, match="Either config_path or base_config_path"):
        FXSensitivityAnalyzer()


def test_analyzer_loads_real_lender_scenario() -> None:
    analyzer = FXSensitivityAnalyzer(str(LENDER))
    assert analyzer.base_config_path == str(LENDER)
    assert isinstance(analyzer.base_config, dict)
    assert "fx" in analyzer.base_config
    # lender scenario declares its own top-level fx.start_lkr_per_usd
    assert analyzer._base_fx() == pytest.approx(333.79)


def test_analyzer_base_config_path_keyword_alias(tmp_path: Path) -> None:
    cfg = tmp_path / "scenario.yaml"
    cfg.write_text("fx:\n  spot_rate: 320.0\n")
    analyzer = FXSensitivityAnalyzer(base_config_path=cfg)
    assert analyzer._base_fx() == pytest.approx(320.0)


def test_analyzer_missing_file_leaves_empty_base_config(tmp_path: Path) -> None:
    analyzer = FXSensitivityAnalyzer(str(tmp_path / "does_not_exist.yaml"))
    assert analyzer.base_config == {}


def test_analyzer_non_dict_yaml_ignored(tmp_path: Path) -> None:
    cfg = tmp_path / "list.yaml"
    cfg.write_text("- a\n- b\n")
    analyzer = FXSensitivityAnalyzer(str(cfg))
    assert analyzer.base_config == {}


def test_base_fx_falls_back_to_config_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = tmp_path / "no_fx.yaml"
    cfg.write_text("project:\n  name: x\n")
    analyzer = FXSensitivityAnalyzer(str(cfg))
    monkeypatch.setattr("analytics.fx.fx_fetch.default_fx_lkr_per_usd", lambda: 305.0)
    assert analyzer._base_fx() == pytest.approx(305.0)


# ---------------------------------------------------------------------------
# FXSensitivityAnalyzer.run — full path with stubbed evaluation
# ---------------------------------------------------------------------------
def _stub_evaluate_with_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> list[dict[str, Any]]:
    """Patch the module-level ``evaluate_with_overrides`` with a deterministic
    monotone response so the linear fits have real, non-degenerate slopes."""
    calls: list[dict[str, Any]] = []

    def fake(path: str, overrides: dict[str, Any]) -> dict[str, Any]:
        calls.append(overrides)
        fx = overrides.get("fx", {})
        # The fx_rate sweep now drives the LIVE key start_lkr_per_usd (base 333.79); derive
        # the implied shock from it. The base eval (fx_shock=0.0, no start) -> shock 0.
        shock = float(fx.get("fx_shock", 0.0))
        start = fx.get("start_lkr_per_usd")
        if start is not None:
            shock = float(start) / 333.79 - 1.0
        hedge = float(fx.get("hedge_ratio", 0.0))
        # The spread sweep drives the LIVE key fx.spread_bps (#659); the hedge term is a
        # CONSTANT offset within that sweep (ref hedge 1.0 on an unhedged base), so it
        # shifts the intercept, never the spread slope.
        spread = float(fx.get("spread_bps", 0.0))
        # IRR falls as LKR weakens (higher LKR/USD = positive shock), rises with hedging,
        # falls as the spread widens — a plausible, monotone tail.
        irr = 0.06 - 0.20 * shock + 0.01 * hedge - 0.00001 * spread
        return {"project_irr": irr}

    monkeypatch.setattr(mod, "evaluate_with_overrides", fake)
    return calls


def test_run_produces_three_coefficients_and_variance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _stub_evaluate_with_overrides(monkeypatch)
    analyzer = FXSensitivityAnalyzer(str(LENDER))
    result = analyzer.run()

    assert isinstance(result, FXSensitivityResult)
    assert result.base_value == pytest.approx(0.06)
    params = {c.parameter for c in result.coefficients}
    assert params == {"fx_rate", "hedge_ratio", "spread"}

    # fx_rate IRR sensitivity is negative (weaker LKR -> lower IRR): tail direction
    fx_coef = next(c for c in result.coefficients if c.parameter == "fx_rate")
    assert fx_coef.coefficient < 0.0
    # variance contributions sum to ~1 across the three drivers
    contribs = [c.variance_contribution or 0.0 for c in result.coefficients]
    assert sum(contribs) == pytest.approx(1.0)
    assert result.total_variance is not None and result.total_variance > 0.0
    assert result.explained_variance is not None

    # the base evaluation anchors at the unshocked case
    assert calls[0] == {"fx": {"fx_shock": 0.0}}
    # fx shocks re-price the LIVE engine key start_lkr_per_usd relative to base fx (333.79):
    # the first sweep point is the -10% shock -> 333.79 * 0.90.
    fx_call = calls[1]["fx"]
    assert fx_call["start_lkr_per_usd"] == pytest.approx(333.79 * (1.0 + (-0.10)))


def test_run_constant_metric_has_flat_sensitivities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # a constant metric makes every linear fit flat (zero slope) and the
    # per-driver variance effectively zero (float dust only).
    monkeypatch.setattr(
        mod, "evaluate_with_overrides", lambda path, overrides: {"project_irr": 0.05}
    )
    analyzer = FXSensitivityAnalyzer(str(LENDER))
    result = analyzer.run()
    assert result.base_value == pytest.approx(0.05)
    assert result.total_variance is not None
    assert result.total_variance < 1e-20
    assert all(c.coefficient == pytest.approx(0.0) for c in result.coefficients)


def test_run_exact_zero_variance_takes_zero_contribution_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # single-element shock lists -> each np.var over one value is exactly 0.0,
    # so total_variance == 0.0 and the `else 0.0` contribution branch fires.
    monkeypatch.setattr(
        mod, "evaluate_with_overrides", lambda path, overrides: {"project_irr": 0.05}
    )
    cfg = FXSensitivityConfig(
        fx_rate_shocks=[0.0], hedge_ratio_values=[0.0], spread_shocks_bps=[0.0]
    )
    analyzer = FXSensitivityAnalyzer(str(LENDER), config=cfg)
    result = analyzer.run()
    assert result.total_variance == 0.0
    assert all(c.variance_contribution == 0.0 for c in result.coefficients)


# ---------------------------------------------------------------------------
# _run_pipeline_with_fx_params / _extract_metrics / analyze_fx_sensitivity
# ---------------------------------------------------------------------------
def _patch_pipeline(
    monkeypatch: pytest.MonkeyPatch, fixed: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """Patch the path-based gateway seam (``mod.evaluate_with_overrides``) that
    ``_run_pipeline_with_fx_params`` routes through, capturing the OVERRIDES passed for
    each swept point and returning a deterministic full-result payload.

    (Previously this patched ``run_v14_pipeline_with_analytics`` and passed a whole config
    dict — which masked the fact that the real method always raised ``TypeError`` on the
    dict config the callee now rejects; round-2 audit fixed the method to use the gateway.)
    """
    captured: list[dict[str, Any]] = []

    def fake(
        path: str, overrides: dict[str, Any], *, return_full_result: bool = False
    ) -> dict[str, Any]:
        captured.append(overrides)
        if fixed is not None:
            return fixed
        spot = float(overrides["fx"]["start_lkr_per_usd"])
        # IRR/NPV decline as LKR weakens (spot rises): VaR/CVaR tail lives at high spot.
        return {
            "kpis": {
                "project_irr": 0.06 - 0.0002 * (spot - 333.79),
                "project_npv": -31.9e6 - 1.0e5 * (spot - 333.79),
                "equity_irr": 0.0 - 0.0001 * (spot - 333.79),
                "equity_npv": -10.0e6,
            },
            "debt_result": {"min_dscr": 1.30},
        }

    monkeypatch.setattr(mod, "evaluate_with_overrides", fake)
    return captured


def test_run_pipeline_with_fx_params_passes_fx_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _patch_pipeline(monkeypatch)
    analyzer = FXSensitivityAnalyzer(str(LENDER))
    base_rate = analyzer.base_config["fx"]["start_lkr_per_usd"]  # 333.79
    analyzer._run_pipeline_with_fx_params(400.0, 0.5, 100.0)  # a DISTINCT rate
    # The FX params are passed as gateway OVERRIDES against the base_config_path (no config
    # dict is built or mutated), and reach the gateway with the live start_lkr_per_usd key.
    fx = captured[0]["fx"]
    assert fx["start_lkr_per_usd"] == pytest.approx(400.0)
    assert fx["hedge_ratio"] == pytest.approx(0.5)
    assert fx["spread_bps"] == pytest.approx(100.0)
    # The analyzer's own base_config is never touched (overrides go to the gateway).
    assert analyzer.base_config["fx"]["start_lkr_per_usd"] == pytest.approx(base_rate)


def test_run_pipeline_with_fx_params_override_is_independent_of_base_fx(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Even a scenario with no fx block gets a well-formed fx override carrying the swept rate.
    captured = _patch_pipeline(monkeypatch)
    cfg = tmp_path / "no_fx.yaml"
    cfg.write_text("project:\n  name: x\n")
    analyzer = FXSensitivityAnalyzer(str(cfg))
    analyzer._run_pipeline_with_fx_params(310.0, 0.0, 0.0)
    assert captured[0]["fx"]["start_lkr_per_usd"] == pytest.approx(310.0)


def test_extract_metrics_from_kpis() -> None:
    analyzer = FXSensitivityAnalyzer(str(LENDER))
    result = {
        "kpis": {
            "project_irr": 0.054,
            "project_npv": -31.9e6,
            "equity_irr": 0.0,
            "equity_npv": -10.0e6,
        },
        "debt_result": {"min_dscr": 1.30},
    }
    pirr, pnpv, eirr, enpv, dscr = analyzer._extract_metrics(result)
    assert pirr == 0.054
    assert pnpv == pytest.approx(-31.9e6)
    assert eirr == 0.0
    assert enpv == pytest.approx(-10.0e6)
    assert dscr == pytest.approx(1.30)


def test_extract_metrics_falls_back_to_top_level() -> None:
    analyzer = FXSensitivityAnalyzer(str(LENDER))
    result = {
        "project_irr": 0.05,
        "project_npv": 1.0,
        "equity_irr": 0.02,
        "equity_npv": 2.0,
        "dscr_min": 1.25,
    }
    pirr, pnpv, eirr, enpv, dscr = analyzer._extract_metrics(result)
    assert pirr == 0.05
    assert pnpv == 1.0
    assert eirr == 0.02
    assert enpv == 2.0
    assert dscr == pytest.approx(1.25)


def test_extract_metrics_defaults_when_empty() -> None:
    analyzer = FXSensitivityAnalyzer(str(LENDER))
    pirr, pnpv, eirr, enpv, dscr = analyzer._extract_metrics({})
    assert pirr is None
    assert pnpv == 0.0
    assert eirr is None
    assert enpv == 0.0
    assert dscr == 0.0


def test_analyze_fx_sensitivity_sweeps_and_orders_tail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_pipeline(monkeypatch)
    analyzer = FXSensitivityAnalyzer(str(LENDER))
    result = analyzer.analyze_fx_sensitivity(fx_variation_pct=10.0, fx_steps=5)

    assert isinstance(result, RealFXSensitivityResult)
    assert result.base_fx_rate == pytest.approx(333.79)
    assert len(result.fx_rate_points) == 5

    rates = [p.fx_rate for p in result.fx_rate_points]
    # symmetric sweep around base: spans 90%..110% of base fx
    assert rates[0] == pytest.approx(333.79 * 0.9)
    assert rates[-1] == pytest.approx(333.79 * 1.1)

    # VaR/CVaR tail direction: IRR worst at the weakest-LKR (highest spot) point
    irrs = [p.project_irr for p in result.fx_rate_points if p.project_irr is not None]
    assert irrs[-1] < irrs[0]
    # summary slope is negative (declining IRR as LKR weakens)
    assert result.fx_rate_irr_sensitivity < 0.0


def test_analyze_fx_sensitivity_tolerates_explicit_null_hedge(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An explicit YAML `hedge_ratio: null` resolves to the null hedge instead of
    crashing float(None) (Fable review of 9cafb41)."""
    _patch_pipeline(monkeypatch)
    cfg = tmp_path / "null_hedge.yaml"
    cfg.write_text("fx:\n  spot_rate: 300.0\n  hedge_ratio: null\n  spread_bps: null\n")
    analyzer = FXSensitivityAnalyzer(str(cfg))
    result = analyzer.analyze_fx_sensitivity(fx_steps=3, spread_steps=2)
    assert result.base_hedge_ratio == 0.0
    assert result.base_spread_bps == 0.0
    # unhedged base -> spread sweep at the reference full hedge
    assert all(p.hedge_ratio == pytest.approx(1.0) for p in result.spread_points)


def test_analyze_fx_sensitivity_rejects_negative_spread_variation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A negative spread_variation_bps fails loud at the analyzer's named pre-check,
    not deep in the engine's >= 0 gate (Fable review of 9cafb41)."""
    _patch_pipeline(monkeypatch)
    analyzer = FXSensitivityAnalyzer(str(LENDER))
    with pytest.raises(ValueError, match="spread_variation_bps must be >= 0"):
        analyzer.analyze_fx_sensitivity(spread_variation_bps=-50.0)


def test_analyze_fx_sensitivity_respects_scenario_hedge_and_spread(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured = _patch_pipeline(monkeypatch)
    cfg = tmp_path / "with_fx.yaml"
    cfg.write_text(
        "fx:\n  spot_rate: 300.0\n  hedge_ratio: 0.75\n  spread_bps: 120.0\n"
    )
    analyzer = FXSensitivityAnalyzer(str(cfg))
    result = analyzer.analyze_fx_sensitivity(fx_steps=3, spread_steps=3)
    assert result.base_hedge_ratio == pytest.approx(0.75)
    assert result.base_spread_bps == pytest.approx(120.0)
    # The FX-RATE sweep respects the scenario hedge/spread — only spot varies there.
    # (calls: 1 base + fx_steps fx-rate points, in order, before the hedge/spread sweeps)
    for config in captured[: 1 + 3]:
        assert config["fx"]["hedge_ratio"] == pytest.approx(0.75)
        assert config["fx"]["spread_bps"] == pytest.approx(120.0)
    # The SPREAD sweep runs at the scenario's OWN hedge (0.75, not the h=1.0 reference)
    # and sweeps upward deltas from the scenario's OWN base spread (120 -> 220).
    assert all(p.hedge_ratio == pytest.approx(0.75) for p in result.spread_points)
    assert result.spread_points[0].spread_bps == pytest.approx(120.0)
    assert result.spread_points[-1].spread_bps == pytest.approx(220.0)
    # The HEDGE sweep varies hedge_ratio at the scenario's own base spread.
    assert all(p.spread_bps == pytest.approx(120.0) for p in result.hedge_ratio_points)
    assert [p.hedge_ratio for p in result.hedge_ratio_points] == [
        pytest.approx(h) for h in [0.0, 0.25, 0.5, 0.75, 1.0]
    ]


# ---------------------------------------------------------------------------
# Dataclass surfaces / __all__
# ---------------------------------------------------------------------------
def test_sensitivity_coefficient_fields() -> None:
    c = SensitivityCoefficient("fx_rate", -0.2, 0.01, 0.99, 0.4)
    assert c.parameter == "fx_rate"
    assert c.variance_contribution == 0.4


def test_public_exports() -> None:
    for name in mod.__all__:
        assert hasattr(mod, name)


def test_fx_rate_sweep_is_live_against_the_real_engine() -> None:
    """End-to-end, NO mock: all THREE sweeps now drive live engine keys on the real
    lender scenario.

    - fx_rate drives start_lkr_per_usd: IRR falls as the LKR/USD rate rises (negative).
    - hedge_ratio is engine-driven (FX forward hedging, #652): the lender case's CIP
      forward drift sits just below its spot drift, so hedging raises project IRR — a
      real, POSITIVE coefficient.
    - spread drives the live fx.spread_bps under the reference full hedge (#659, the
      lender case is unhedged so ref h=1.0): a wider spread is a hedging COST — a real,
      NEGATIVE coefficient (per bp)."""
    cfg = FXSensitivityConfig(
        fx_rate_shocks=[-0.05, 0.0, 0.05],
        hedge_ratio_values=[0.0, 1.0],
        spread_shocks_bps=[0.0, 100.0],
    )
    analyzer = FXSensitivityAnalyzer(str(LENDER), config=cfg)
    result = analyzer.run()
    fx_coef = next(c for c in result.coefficients if c.parameter == "fx_rate")
    assert abs(fx_coef.coefficient) > 1e-6  # REAL sensitivity, not a fake ~0
    assert fx_coef.coefficient < 0.0  # weaker LKR (higher rate) -> lower IRR
    # hedge_ratio is a live lever: forward below spot -> hedging raises IRR (positive).
    hedge_coef = next(c for c in result.coefficients if c.parameter == "hedge_ratio")
    assert hedge_coef.coefficient > 1e-6
    # spread is a live lever under the ref hedge: a cost -> negative slope per bp.
    spread_coef = next(c for c in result.coefficients if c.parameter == "spread")
    assert spread_coef.coefficient < 0.0
    assert abs(spread_coef.coefficient) > 1e-9  # engine-driven, not the old inert ~0


def test_spread_sweep_negative_absolute_fails_loud(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A spread delta that takes base + shock below zero raises (never clamps) —
    mirroring the engine's fail-loud >= 0 gate (#659 / CESSPIT)."""
    _stub_evaluate_with_overrides(monkeypatch)
    cfg = FXSensitivityConfig(spread_shocks_bps=[-100.0, 0.0])
    analyzer = FXSensitivityAnalyzer(str(LENDER), config=cfg)  # base spread 0
    with pytest.raises(ValueError, match="below zero"):
        analyzer.run()


def test_spread_sweep_uses_reference_full_hedge_on_unhedged_base(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """On an unhedged scenario (base hedge 0) the spread sweep runs at the documented
    reference FULL hedge (h=1.0) — spread is inert at h=0, so sweeping there would
    reintroduce the fake-zero coefficient the wiring removed (#659)."""
    calls = _stub_evaluate_with_overrides(monkeypatch)
    cfg = FXSensitivityConfig(
        fx_rate_shocks=[0.0], hedge_ratio_values=[0.0], spread_shocks_bps=[0.0, 50.0]
    )
    analyzer = FXSensitivityAnalyzer(str(LENDER), config=cfg)  # lender case: unhedged
    analyzer.run()
    spread_calls = [c["fx"] for c in calls if "spread_bps" in c.get("fx", {})]
    assert len(spread_calls) == 2
    for fx in spread_calls:
        assert fx["hedge_ratio"] == pytest.approx(1.0)  # reference full hedge
    # deltas around base spread 0 -> absolute values equal the shocks
    assert [fx["spread_bps"] for fx in spread_calls] == [
        pytest.approx(0.0),
        pytest.approx(50.0),
    ]


def test_spread_sweep_uses_base_hedge_when_scenario_hedges(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """On a hedged scenario the spread sweep runs at the scenario's OWN hedge ratio and
    deltas apply around the scenario's OWN base spread (#659)."""
    calls = _stub_evaluate_with_overrides(monkeypatch)
    cfg_file = tmp_path / "hedged.yaml"
    cfg_file.write_text(
        "fx:\n  start_lkr_per_usd: 333.79\n  annual_depr: 0.0589\n"
        "  hedge_ratio: 0.75\n  spread_bps: 20.0\n"
    )
    cfg = FXSensitivityConfig(
        fx_rate_shocks=[0.0], hedge_ratio_values=[0.0], spread_shocks_bps=[0.0, 30.0]
    )
    analyzer = FXSensitivityAnalyzer(str(cfg_file), config=cfg)
    analyzer.run()
    spread_calls = [c["fx"] for c in calls if "spread_bps" in c.get("fx", {})]
    assert len(spread_calls) == 2
    for fx in spread_calls:
        assert fx["hedge_ratio"] == pytest.approx(0.75)  # scenario's own hedge
    # deltas around the scenario's base 20 bps -> absolute 20 and 50
    assert [fx["spread_bps"] for fx in spread_calls] == [
        pytest.approx(20.0),
        pytest.approx(50.0),
    ]


def test_analyze_fx_sensitivity_is_live_against_the_real_engine() -> None:
    """End-to-end, NO mock: analyze_fx_sensitivity now routes through the path-based
    gateway, so it actually runs on the real lender scenario instead of raising TypeError
    on a dict config.

    Round-2 audit: the method built an inline dict config and passed it to
    run_v14_pipeline_with_analytics, which hard-guards config to (str | Path), so it always
    raised before returning — the public method was dead in production and only ever
    exercised under a monkeypatched pipeline. This drives it unmocked so the fix is real.
    """
    analyzer = FXSensitivityAnalyzer(str(LENDER))
    result = analyzer.analyze_fx_sensitivity(
        fx_variation_pct=10.0,
        fx_steps=3,
        hedge_ratio_steps=[0.0, 0.5, 1.0],
        spread_variation_bps=100.0,
        spread_steps=3,
    )
    assert isinstance(result, RealFXSensitivityResult)
    assert result.base_fx_rate == pytest.approx(333.79)
    assert len(result.fx_rate_points) == 3
    irrs = [p.project_irr for p in result.fx_rate_points if p.project_irr is not None]
    assert len(irrs) == 3  # every swept point produced a real IRR (no TypeError)
    # weaker LKR (higher spot) -> lower project IRR: a real, monotone tail
    assert irrs[-1] < irrs[0]

    # hedge/spread sweeps are now POPULATED and engine-driven (#652/#659): previously
    # the step params were accepted but never used and both point lists stayed empty.
    assert len(result.hedge_ratio_points) == 3
    assert len(result.spread_points) == 3
    # the lender case is unhedged -> the spread sweep runs at the reference full hedge
    assert all(p.hedge_ratio == pytest.approx(1.0) for p in result.spread_points)
    # engine-driven summary sensitivities: hedging helps (forward below spot), and a
    # wider spread is a hedging cost (negative per-bp slope on IRR and NPV)
    assert result.hedge_ratio_irr_sensitivity > 0.0
    assert result.hedge_ratio_npv_sensitivity > 0.0
    assert result.spread_irr_sensitivity < 0.0
    assert result.spread_npv_sensitivity < 0.0
    # fx_rate NPV sensitivity is also fitted now (weaker LKR -> lower NPV)
    assert result.fx_rate_npv_sensitivity < 0.0
