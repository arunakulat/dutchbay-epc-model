"""FX sensitivity analysis compatibility surface."""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Sequence, cast

import numpy as np
import yaml

logger = logging.getLogger(__name__)

VALID_TARGET_METRICS = {
    "project_irr",
    "equity_irr",
    "dscr_min",
    "project_npv",
    "equity_npv",
}


@dataclass(frozen=True)
class FXSensitivityConfig:
    fx_rate_shocks: list[float] = field(default_factory=lambda: [-0.10, -0.05, 0.0, 0.05, 0.10])
    hedge_ratio_values: list[float] = field(default_factory=lambda: [0.0, 0.5, 1.0])
    spread_shocks_bps: list[float] = field(default_factory=lambda: [-100, 0, 100])
    target_metric: str = "project_irr"
    confidence_level: float = 0.95

    def __post_init__(self) -> None:
        if not 0.0 < self.confidence_level < 1.0:
            raise ValueError("confidence_level must be between 0 and 1")
        if self.target_metric not in VALID_TARGET_METRICS:
            raise ValueError(
                "target_metric must be one of "
                f"{sorted(VALID_TARGET_METRICS)}, got {self.target_metric!r}"
            )


@dataclass(frozen=True)
class SensitivityCoefficient:
    parameter: str
    coefficient: float
    std_error: float
    r_squared: float
    variance_contribution: float | None = None


@dataclass(frozen=True)
class FXSensitivityResult:
    coefficients: list[SensitivityCoefficient]
    base_value: float
    total_variance: float | None = None
    explained_variance: float | None = None


@dataclass(frozen=True)
class FXSensitivityPoint:
    fx_rate: float
    hedge_ratio: float
    spread_bps: float
    project_irr: Optional[float] = None
    project_npv: float = 0.0
    equity_irr: Optional[float] = None
    equity_npv: float = 0.0
    min_dscr: float = 0.0
    avg_dscr: float = 0.0
    irr_change_pct: Optional[float] = None
    npv_change_usd: float = 0.0
    dscr_change: float = 0.0


@dataclass
class RealFXSensitivityResult:
    base_fx_rate: float
    base_hedge_ratio: float
    base_spread_bps: float
    base_project_irr: Optional[float] = None
    base_project_npv: float = 0.0
    base_equity_irr: Optional[float] = None
    base_min_dscr: float = 0.0
    fx_rate_points: list[FXSensitivityPoint] = field(default_factory=list)
    hedge_ratio_points: list[FXSensitivityPoint] = field(default_factory=list)
    spread_points: list[FXSensitivityPoint] = field(default_factory=list)
    fx_rate_irr_sensitivity: float = 0.0
    fx_rate_npv_sensitivity: float = 0.0
    hedge_ratio_irr_sensitivity: float = 0.0
    hedge_ratio_npv_sensitivity: float = 0.0
    spread_irr_sensitivity: float = 0.0
    spread_npv_sensitivity: float = 0.0
    fx_volatility_contribution_pct: float = 0.0
    fx_cost_of_hedging_annual: float = 0.0

    def calculate_summary_metrics(self) -> None:
        if self.base_project_irr is None:
            return
        if len(self.fx_rate_points) >= 2:
            xs = [p.fx_rate for p in self.fx_rate_points]
            ys = [p.project_irr for p in self.fx_rate_points if p.project_irr is not None]
            if len(xs) == len(ys) and len(ys) >= 2:
                coef, _variance = _linear_fit("fx_rate", xs, [float(y) for y in ys])
                self.fx_rate_irr_sensitivity = coef.coefficient


def evaluate_with_overrides(base_config_path: str, overrides: dict[str, Any]) -> dict[str, Any]:
    from analytics.evaluation_v14 import evaluate_with_overrides as _evaluate

    return cast(dict[str, Any], _evaluate(base_config_path, overrides))


def _metric_from_result(result: dict[str, Any], metric: str) -> float:
    direct = result.get(metric)
    if direct is not None:
        return float(direct)
    for key in ("kpis", "baseline_kpis", "metrics"):
        nested = result.get(key)
        if isinstance(nested, dict) and nested.get(metric) is not None:
            return float(nested[metric])
    analytics = result.get("analytics_result")
    if isinstance(analytics, dict):
        returns = analytics.get("returns_analysis")
        if isinstance(returns, dict):
            for bucket in ("project_returns", "equity_returns"):
                data = returns.get(bucket, {})
                if isinstance(data, dict) and data.get(metric) is not None:
                    return float(data[metric])
    raise KeyError(f"Metric {metric!r} not found in pipeline result")


def _linear_fit(parameter: str, xs: Sequence[float], ys: Sequence[float]) -> tuple[SensitivityCoefficient, float]:
    x = np.asarray([float(value) for value in xs], dtype=float)
    y = np.asarray([float(value) for value in ys], dtype=float)
    if len(x) != len(y) or len(x) == 0:
        raise ValueError("x and y must have equal non-zero length")

    x_mean = float(np.mean(x))
    y_mean = float(np.mean(y))
    x_delta = x - x_mean
    y_delta = y - y_mean
    denominator = float(np.sum(x_delta * x_delta))

    if len(x) == 1 or denominator == 0.0:
        slope = 0.0
        intercept = y_mean
    else:
        slope = float(np.sum(x_delta * y_delta) / denominator)
        intercept = y_mean - slope * x_mean

    fitted = slope * x + intercept
    residuals = y - fitted
    ss_res = float(np.sum(residuals * residuals))
    ss_tot = float(np.sum(y_delta * y_delta))
    r2 = 1.0 if ss_tot == 0.0 else max(0.0, min(1.0, 1.0 - ss_res / ss_tot))
    stderr = float(np.std(residuals, ddof=1)) if len(residuals) > 1 else 0.0
    variance = float(np.var(y))
    return SensitivityCoefficient(parameter, slope, stderr, r2), variance


class FXSensitivityAnalyzer:
    def __init__(
        self,
        config_path: str | Path | None = None,
        *,
        base_config_path: str | Path | None = None,
        config: FXSensitivityConfig | None = None,
    ) -> None:
        resolved = base_config_path if base_config_path is not None else config_path
        if resolved is None:
            raise ValueError("Either config_path or base_config_path is required")
        self.base_config_path = str(resolved)
        self.config_path = Path(resolved)
        self.config = config or FXSensitivityConfig()
        self.base_config: dict[str, Any] = {}
        if self.config_path.exists():
            loaded = yaml.safe_load(self.config_path.read_text())
            if isinstance(loaded, dict):
                self.base_config = loaded

    def run(self) -> FXSensitivityResult:
        metric = self.config.target_metric
        base = evaluate_with_overrides(self.base_config_path, {"fx": {"fx_shock": 0.0}})
        base_value = _metric_from_result(base, metric)
        pairs: list[tuple[SensitivityCoefficient, float]] = []

        fx_values = []
        for shock in self.config.fx_rate_shocks:
            out = evaluate_with_overrides(
                self.base_config_path,
                {"fx": {"fx_shock": float(shock), "spot_rate_lkr_usd": 320.0 * (1.0 + float(shock))}},
            )
            fx_values.append(_metric_from_result(out, metric))
        pairs.append(_linear_fit("fx_rate", self.config.fx_rate_shocks, fx_values))

        hedge_values = []
        for hedge_ratio in self.config.hedge_ratio_values:
            out = evaluate_with_overrides(self.base_config_path, {"fx": {"hedge_ratio": float(hedge_ratio)}})
            hedge_values.append(_metric_from_result(out, metric))
        pairs.append(_linear_fit("hedge_ratio", self.config.hedge_ratio_values, hedge_values))

        spread_values = []
        for spread_bps in self.config.spread_shocks_bps:
            out = evaluate_with_overrides(self.base_config_path, {"fx": {"spread_shock_bps": float(spread_bps)}})
            spread_values.append(_metric_from_result(out, metric))
        pairs.append(_linear_fit("spread", self.config.spread_shocks_bps, spread_values))

        total_variance = float(sum(variance for _, variance in pairs))
        coefficients = [
            SensitivityCoefficient(
                parameter=coef.parameter,
                coefficient=coef.coefficient,
                std_error=coef.std_error,
                r_squared=coef.r_squared,
                variance_contribution=(variance / total_variance if total_variance > 0 else 0.0),
            )
            for coef, variance in pairs
        ]
        explained = float(np.mean([coef.r_squared for coef in coefficients]))
        return FXSensitivityResult(coefficients, base_value, total_variance, explained)

    def _run_pipeline_with_fx_params(self, fx_rate: float, hedge_ratio: float, spread_bps: float) -> dict[str, Any]:
        config = copy.deepcopy(self.base_config)
        config.setdefault("fx", {})
        config["fx"].update(
            {"spot_rate": float(fx_rate), "hedge_ratio": float(hedge_ratio), "spread_bps": float(spread_bps)}
        )
        from analytics.pipeline_analytics_v14 import run_v14_pipeline_with_analytics

        return cast(
            dict[str, Any],
            run_v14_pipeline_with_analytics(config=config, enable_returns=True, enable_risk=False),
        )

    def _extract_metrics(self, pipeline_result: dict[str, Any]) -> tuple[Optional[float], float, Optional[float], float, float]:
        kpis = pipeline_result.get("kpis", {})
        project_irr = kpis.get("project_irr", pipeline_result.get("project_irr"))
        project_npv = float(kpis.get("project_npv", pipeline_result.get("project_npv", 0.0)))
        equity_irr = kpis.get("equity_irr", pipeline_result.get("equity_irr"))
        equity_npv = float(kpis.get("equity_npv", pipeline_result.get("equity_npv", 0.0)))
        debt = pipeline_result.get("debt_result", {})
        min_dscr = float(debt.get("min_dscr", pipeline_result.get("dscr_min", 0.0)))
        return project_irr, project_npv, equity_irr, equity_npv, min_dscr

    def analyze_fx_sensitivity(
        self,
        fx_variation_pct: float = 10.0,
        fx_steps: int = 5,
        hedge_ratio_steps: Optional[list[float]] = None,
        spread_variation_bps: float = 100.0,
        spread_steps: int = 5,
    ) -> RealFXSensitivityResult:
        fx_config = self.base_config.get("fx", {})
        base_fx = float(fx_config.get("spot_rate", fx_config.get("start_lkr_per_usd", 300.0)))
        base_hedge = float(fx_config.get("hedge_ratio", 0.0))
        base_spread = float(fx_config.get("spread_bps", 0.0))
        base_result = self._run_pipeline_with_fx_params(base_fx, base_hedge, base_spread)
        base_irr, base_npv, base_equity_irr, _, base_dscr = self._extract_metrics(base_result)
        result = RealFXSensitivityResult(base_fx, base_hedge, base_spread, base_irr, base_npv, base_equity_irr, base_dscr)
        for fx_rate in np.linspace(base_fx * (1 - fx_variation_pct / 100), base_fx * (1 + fx_variation_pct / 100), fx_steps):
            out = self._run_pipeline_with_fx_params(float(fx_rate), base_hedge, base_spread)
            irr, npv, equity_irr, equity_npv, dscr = self._extract_metrics(out)
            result.fx_rate_points.append(FXSensitivityPoint(float(fx_rate), base_hedge, base_spread, irr, npv, equity_irr, equity_npv, dscr))
        result.calculate_summary_metrics()
        return result


__all__ = [
    "FXSensitivityConfig",
    "SensitivityCoefficient",
    "FXSensitivityResult",
    "FXSensitivityPoint",
    "RealFXSensitivityResult",
    "FXSensitivityAnalyzer",
    "evaluate_with_overrides",
]
