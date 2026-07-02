"""FX sensitivity analysis compatibility surface."""

from __future__ import annotations

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
    """Sweep grids for the real-engine FX sensitivity analyzer.

    - ``fx_rate_shocks``: relative shocks applied to the scenario's base
      ``fx.start_lkr_per_usd`` (e.g. -0.10 = LKR 10% stronger).
    - ``hedge_ratio_values``: absolute ``fx.hedge_ratio`` values (0-1) swept at the
      scenario's own base spread.
    - ``spread_shocks_bps``: DELTAS in basis points around the scenario's base
      ``fx.spread_bps`` (#659). The swept absolute spread is ``base + shock`` and must
      stay >= 0 — the engine fail-loud rejects negative spreads, and this analyzer
      raises (never clamps) when a delta would cross zero (CESSPIT). The default grid
      is non-negative so unhedged scenarios (base spread 0) sweep [0, +50, +100] bps.
      Spread only bites under an active hedge, so the sweep runs at the scenario's own
      ``fx.hedge_ratio`` when > 0, else at a documented reference FULL hedge (h=1.0):
      the coefficient then reads "metric change per bp of hedging cost, if fully hedged".
    """

    fx_rate_shocks: list[float] = field(
        default_factory=lambda: [-0.10, -0.05, 0.0, 0.05, 0.10]
    )
    hedge_ratio_values: list[float] = field(default_factory=lambda: [0.0, 0.5, 1.0])
    spread_shocks_bps: list[float] = field(default_factory=lambda: [0.0, 50.0, 100.0])
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

        def _slope(points: list[FXSensitivityPoint], x_attr: str, y_attr: str) -> float:
            """Linear-fit slope of y over x across swept points (None y dropped)."""
            pairs = [
                (float(getattr(p, x_attr)), float(getattr(p, y_attr)))
                for p in points
                if getattr(p, y_attr) is not None
            ]
            if len(pairs) < 2:
                return 0.0
            coef, _variance = _linear_fit(
                x_attr, [x for x, _ in pairs], [y for _, y in pairs]
            )
            return coef.coefficient

        self.fx_rate_irr_sensitivity = _slope(
            self.fx_rate_points, "fx_rate", "project_irr"
        )
        self.fx_rate_npv_sensitivity = _slope(
            self.fx_rate_points, "fx_rate", "project_npv"
        )
        # Engine-driven since the FX forward hedge landed (#652): hedge_ratio blends the
        # CIP forward into cfads_usd; spread prices the hedged fraction.
        self.hedge_ratio_irr_sensitivity = _slope(
            self.hedge_ratio_points, "hedge_ratio", "project_irr"
        )
        self.hedge_ratio_npv_sensitivity = _slope(
            self.hedge_ratio_points, "hedge_ratio", "project_npv"
        )
        self.spread_irr_sensitivity = _slope(
            self.spread_points, "spread_bps", "project_irr"
        )
        self.spread_npv_sensitivity = _slope(
            self.spread_points, "spread_bps", "project_npv"
        )


def evaluate_with_overrides(
    base_config_path: str,
    overrides: dict[str, Any],
    *,
    return_full_result: bool = False,
) -> dict[str, Any]:
    from analytics.evaluation_v14 import evaluate_with_overrides as _evaluate

    return cast(
        dict[str, Any],
        _evaluate(base_config_path, overrides, return_full_result=return_full_result),
    )


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


def _linear_fit(
    parameter: str, xs: Sequence[float], ys: Sequence[float]
) -> tuple[SensitivityCoefficient, float]:
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

    def _base_fx(self) -> float:
        """Resolve the base USD/LKR rate to anchor FX shocks.

        Reads the scenario's own ``fx`` block (``spot_rate`` / ``start_lkr_per_usd``);
        falls back to the single config-sourced reference rate
        (``config/defaults.yaml``), never a Python literal (CESSPIT / ARCH-01).
        """
        from analytics.fx.fx_fetch import default_fx_lkr_per_usd

        fx_config = self.base_config.get("fx", {})
        rates = (
            fx_config.get("rates") if isinstance(fx_config.get("rates"), dict) else {}
        )
        # Prefer the LIVE engine key (start_lkr_per_usd), then the scenario rates block,
        # then the legacy spot_rate, then the global config default.
        spot = (
            fx_config.get("start_lkr_per_usd")
            or rates.get("lkr_per_usd")
            or fx_config.get("spot_rate")
        )
        return float(spot) if spot is not None else default_fx_lkr_per_usd()

    def run(self) -> FXSensitivityResult:
        metric = self.config.target_metric
        base = evaluate_with_overrides(self.base_config_path, {"fx": {"fx_shock": 0.0}})
        base_value = _metric_from_result(base, metric)
        pairs: list[tuple[SensitivityCoefficient, float]] = []

        # FX-RATE sweep drives the LIVE engine key fx.start_lkr_per_usd (the rate the
        # cashflow actually discounts at). The old keys fx.fx_shock / fx.spot_rate_lkr_usd
        # were not consumed by the engine, so this coefficient was a fake ~0 (Wave-2 fix).
        base_fx = self._base_fx()
        fx_values = []
        for shock in self.config.fx_rate_shocks:
            out = evaluate_with_overrides(
                self.base_config_path,
                {"fx": {"start_lkr_per_usd": base_fx * (1.0 + float(shock))}},
            )
            fx_values.append(_metric_from_result(out, metric))
        pairs.append(_linear_fit("fx_rate", self.config.fx_rate_shocks, fx_values))

        # hedge_ratio is now a LIVE engine lever: the v14 cashflow engine models FX forward
        # hedging (fx.hedge_ratio blends spot with the CIP forward in cfads_usd, #652), so
        # this coefficient is genuinely engine-driven on a scenario that carries the debt
        # rates the forward is built from (Financing_Terms.rates). Its sign follows the
        # forward-vs-spot relationship for the scenario's rates.
        hedge_values = []
        for hedge_ratio in self.config.hedge_ratio_values:
            out = evaluate_with_overrides(
                self.base_config_path, {"fx": {"hedge_ratio": float(hedge_ratio)}}
            )
            hedge_values.append(_metric_from_result(out, metric))
        pairs.append(
            _linear_fit("hedge_ratio", self.config.hedge_ratio_values, hedge_values)
        )

        # SPREAD sweep drives the LIVE engine key `fx.spread_bps` (#659), jointly with an
        # ACTIVE hedge — the engine prices a spread only on the hedged fraction
        # (`forward * (1 + spread)`), so sweeping it at hedge_ratio=0 is structurally
        # inert. Convention: sweep at the scenario's own base hedge when it hedges
        # (base_hedge > 0), else at a documented reference FULL hedge (h=1.0) — the
        # coefficient then reads "metric change per bp of hedging cost, if fully hedged".
        # Shock semantics: `spread_shocks_bps` are DELTAS around the scenario's base
        # `fx.spread_bps`; a delta that takes the absolute spread below zero fails loud
        # (the engine gate rejects negative spreads — no silent clamping, CESSPIT).
        fx_cfg_raw = self.base_config.get("fx")
        fx_cfg = fx_cfg_raw if isinstance(fx_cfg_raw, dict) else {}
        base_hedge = float(fx_cfg.get("hedge_ratio") or 0.0)
        base_spread = float(fx_cfg.get("spread_bps") or 0.0)
        ref_hedge = base_hedge if base_hedge > 0.0 else 1.0
        if ref_hedge != base_hedge:
            # Surface the convention in the RUN OUTPUT stream, not just source docs: the
            # "spread" coefficient below presumes a full hedge on an unhedged scenario.
            logger.info(
                "FX spread sweep: scenario is unhedged (fx.hedge_ratio %.2f) — sweeping "
                "at the reference FULL hedge (h=1.0); the 'spread' coefficient reads "
                "'metric change per bp of hedging cost, if fully hedged'.",
                base_hedge,
            )
        spread_values = []
        for shock_bps in self.config.spread_shocks_bps:
            absolute_bps = base_spread + float(shock_bps)
            if absolute_bps < 0.0:
                raise ValueError(
                    f"spread shock {float(shock_bps):+g} bps takes the absolute "
                    f"fx.spread_bps below zero (base {base_spread:g} bps -> "
                    f"{absolute_bps:g} bps); the engine rejects negative spreads — "
                    "use deltas that keep base + shock >= 0."
                )
            out = evaluate_with_overrides(
                self.base_config_path,
                {"fx": {"spread_bps": absolute_bps, "hedge_ratio": ref_hedge}},
            )
            spread_values.append(_metric_from_result(out, metric))
        pairs.append(
            _linear_fit("spread", self.config.spread_shocks_bps, spread_values)
        )

        # NB: variance_contribution mixes sweep regimes in one total (the fx_rate sweep
        # runs at the base hedge, the spread sweep at ref_hedge) — it is a rough relative
        # attribution across the three levers, not a decomposition at a single operating
        # point (pre-existing convention; caveat per Fable review of 9cafb41).
        total_variance = float(sum(variance for _, variance in pairs))
        coefficients = [
            SensitivityCoefficient(
                parameter=coef.parameter,
                coefficient=coef.coefficient,
                std_error=coef.std_error,
                r_squared=coef.r_squared,
                variance_contribution=(
                    variance / total_variance if total_variance > 0 else 0.0
                ),
            )
            for coef, variance in pairs
        ]
        explained = float(np.mean([coef.r_squared for coef in coefficients]))
        return FXSensitivityResult(coefficients, base_value, total_variance, explained)

    def _run_pipeline_with_fx_params(
        self, fx_rate: float, hedge_ratio: float, spread_bps: float
    ) -> dict[str, Any]:
        # Route the FX overrides through the path-based contract gateway
        # (config-first / CCCDIR) -- the same seam run() uses -- rather than mutating an
        # in-memory config dict and passing it to run_v14_pipeline_with_analytics. That
        # callee hard-guards its config to (str | Path) (added #156), so the old
        # dict-config call always raised TypeError, leaving this public method dead in
        # production and only ever exercised under a monkeypatched pipeline in tests
        # (round-2 audit). start_lkr_per_usd, hedge_ratio and spread_bps are ALL live engine
        # keys now (FX forward hedging, #652): a non-zero hedge_ratio blends the CIP forward
        # into cfads_usd, and spread_bps loads the forward rate under that hedge.
        overrides: dict[str, Any] = {
            "fx": {
                "start_lkr_per_usd": float(fx_rate),
                "hedge_ratio": float(hedge_ratio),
                "spread_bps": float(spread_bps),
            }
        }
        return evaluate_with_overrides(
            self.base_config_path, overrides, return_full_result=True
        )

    def _extract_metrics(
        self, pipeline_result: dict[str, Any]
    ) -> tuple[Optional[float], float, Optional[float], float, float]:
        kpis = pipeline_result.get("kpis", {})
        project_irr = kpis.get("project_irr", pipeline_result.get("project_irr"))
        project_npv = float(
            kpis.get("project_npv", pipeline_result.get("project_npv", 0.0))
        )
        equity_irr = kpis.get("equity_irr", pipeline_result.get("equity_irr"))
        equity_npv = float(
            kpis.get("equity_npv", pipeline_result.get("equity_npv", 0.0))
        )
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
        base_fx = self._base_fx()
        # `or 0.0` (not a .get default): an explicit YAML `hedge_ratio: null` must resolve
        # to the null hedge, not crash float(None) — mirrors run() (Fable review, 9cafb41).
        base_hedge = float(fx_config.get("hedge_ratio") or 0.0)
        base_spread = float(fx_config.get("spread_bps") or 0.0)
        if spread_variation_bps < 0.0:
            # Mirror run()'s named pre-check so a negative variation fails loud HERE with
            # the offending argument named, not deep in the engine's >= 0 gate.
            raise ValueError(
                f"spread_variation_bps must be >= 0 (got {spread_variation_bps:g}); "
                "the sweep walks upward deltas from the base fx.spread_bps and the "
                "engine rejects negative spreads."
            )
        base_result = self._run_pipeline_with_fx_params(
            base_fx, base_hedge, base_spread
        )
        base_irr, base_npv, base_equity_irr, _, base_dscr = self._extract_metrics(
            base_result
        )
        result = RealFXSensitivityResult(
            base_fx,
            base_hedge,
            base_spread,
            base_irr,
            base_npv,
            base_equity_irr,
            base_dscr,
        )
        for fx_rate in np.linspace(
            base_fx * (1 - fx_variation_pct / 100),
            base_fx * (1 + fx_variation_pct / 100),
            fx_steps,
        ):
            out = self._run_pipeline_with_fx_params(
                float(fx_rate), base_hedge, base_spread
            )
            irr, npv, equity_irr, equity_npv, dscr = self._extract_metrics(out)
            result.fx_rate_points.append(
                FXSensitivityPoint(
                    float(fx_rate),
                    base_hedge,
                    base_spread,
                    irr,
                    npv,
                    equity_irr,
                    equity_npv,
                    dscr,
                )
            )

        # HEDGE-RATIO sweep (engine-driven since #652): absolute fx.hedge_ratio values
        # at the scenario's own base spread.
        hedge_steps = (
            [float(h) for h in hedge_ratio_steps]
            if hedge_ratio_steps is not None
            else [0.0, 0.25, 0.5, 0.75, 1.0]
        )
        for hedge in hedge_steps:
            out = self._run_pipeline_with_fx_params(base_fx, hedge, base_spread)
            irr, npv, equity_irr, equity_npv, dscr = self._extract_metrics(out)
            result.hedge_ratio_points.append(
                FXSensitivityPoint(
                    base_fx,
                    hedge,
                    base_spread,
                    irr,
                    npv,
                    equity_irr,
                    equity_npv,
                    dscr,
                )
            )

        # SPREAD sweep (live fx.spread_bps, #659): upward deltas from the base spread —
        # non-negative for any valid call (spread_variation_bps >= 0 is enforced above,
        # so base + delta can never cross the engine's >= 0 gate) — run under an ACTIVE
        # hedge (base hedge when > 0, else the documented reference full hedge h=1.0;
        # spread is inert at hedge_ratio=0). Same convention as run().
        ref_hedge = base_hedge if base_hedge > 0.0 else 1.0
        if ref_hedge != base_hedge:
            # Surface the convention in the RUN OUTPUT stream, not just source docs: the
            # spread sensitivities below presume a full hedge on an unhedged scenario.
            logger.info(
                "FX spread sweep: scenario is unhedged (fx.hedge_ratio %.2f) — sweeping "
                "at the reference FULL hedge (h=1.0); spread sensitivities read 'per bp "
                "of hedging cost, if fully hedged'.",
                base_hedge,
            )
        for spread in np.linspace(
            base_spread, base_spread + spread_variation_bps, spread_steps
        ):
            out = self._run_pipeline_with_fx_params(base_fx, ref_hedge, float(spread))
            irr, npv, equity_irr, equity_npv, dscr = self._extract_metrics(out)
            result.spread_points.append(
                FXSensitivityPoint(
                    base_fx,
                    ref_hedge,
                    float(spread),
                    irr,
                    npv,
                    equity_irr,
                    equity_npv,
                    dscr,
                )
            )

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
