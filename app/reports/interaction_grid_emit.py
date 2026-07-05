"""Opt-in production caller for the two-factor sensitivity interaction-grid report section (#739).

Slice-1 (the ENGINE PRIMITIVE, ``analytics.sensitivity.interaction``) evaluates a KPI over the
cross-product of two driver sweeps and quantifies their INTERACTION (deviation from one-way
additivity). Slice-2 (this module + the report projection + template) SURFACES that grid in the
lender report — latency-gated.

Why a separate, opt-in caller (the #645 latency ledger): a grid is ``N x M`` full-pipeline
evaluations plus a base evaluation (10 for the default 3x3), each a full v14 run. That heavy compute
must NEVER run in the synchronous HTTP report route — it stays here, in the batch / async-job path,
mirroring ``app.reports.capital_risk_emit`` exactly. The synchronous route passes
``interaction_grid=None`` -> the section is omitted -> fast and byte-identical.

Config-first, fail-loud (CESSPIT). The two drivers and the metric are CONFIG-REQUIRED — this module
imposes no default driver pair (that would silently choose a scenario's analytical content). A
scenario that opts in must declare an ``interaction_grid`` block:

    interaction_grid:
      metric: project_irr            # required — KPI key extracted per cell
      param_a:                       # required — first driver (grid rows)
        variable_name: tariff.lkr_per_kwh
        base_value: 27.5
        low_pct: -0.10               # OR low_value / high_value (absolute)
        high_pct: 0.10
        label: PPA tariff            # optional display label
      param_b:                       # required — second driver (grid columns)
        variable_name: fx.usdlkr_depreciation_pct
        base_value: 0.059
        low_pct: -0.30
        high_pct: 0.30
        label: FX depreciation

Missing block, missing driver/metric, a malformed driver spec, or a driver that does not resolve to
a config path all RAISE — the caller explicitly opted in, so an error surfaces rather than a
silently degenerate grid. Driver resolution reuses the slice-1 primitive's strict resolve guard
(``run_cfg.strict=True``), so the report path can never disagree with the engine on what "resolves".

GWTF:
    - CESSPIT: fail-loud on an absent/malformed ``interaction_grid`` block.
    - CCCDIR/ARCH: consumes the slice-1 primitive + the ``build_report_context`` gateway only; no
      finance or IRR logic lives here.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

from analytics.contracts_v14 import ParameterRangeConfig, TwoFactorInteractionGrid
from analytics.scenario_loader import load_scenario_config
from analytics.sensitivity.engine import (
    _DEFAULT_SENSITIVITY_RUN_CONFIG,
    SensitivityRunConfig,
)
from analytics.sensitivity.interaction import build_two_factor_interaction_grid
from app.api.responses import CaseResult
from app.reports.renderer import render_report_html
from app.reports.report_model import build_report_context

__all__ = [
    "build_interaction_grid_for_scenario",
    "emit_interaction_grid_report_from_pipeline",
]

#: Keys a driver sub-dict may carry (mirrors ``ParameterRangeConfig``'s public fields). An unknown
#: key is rejected (CESSPIT — a typo like ``low_percent`` would otherwise be silently dropped and
#: flatten the axis).
_ALLOWED_DRIVER_KEYS = {
    "variable_name",
    "base_value",
    "low_pct",
    "high_pct",
    "low_value",
    "high_value",
    "label",
    "points",
}


def _parse_driver(spec: Any, *, which: str) -> ParameterRangeConfig:
    """Build a :class:`ParameterRangeConfig` from a config driver sub-dict (fail-loud).

    Args:
        spec: The raw ``interaction_grid.param_a`` / ``param_b`` mapping from config.
        which: ``"param_a"`` / ``"param_b"`` — for error messages.

    Raises:
        ValueError: ``spec`` is not a mapping, omits ``variable_name`` / ``base_value``, carries an
            unknown key, or does not declare a sweep range (neither pct nor absolute bounds) — each
            of which would otherwise yield a silently flat axis (audit-R1).
    """
    if not isinstance(spec, Mapping):
        raise ValueError(
            f"interaction_grid.{which} must be a mapping with variable_name/base_value/"
            f"low_pct+high_pct (or low_value+high_value); got {type(spec).__name__}"
        )
    unknown = set(spec) - _ALLOWED_DRIVER_KEYS
    if unknown:
        raise ValueError(
            f"interaction_grid.{which} has unknown key(s) {sorted(unknown)}; allowed: "
            f"{sorted(_ALLOWED_DRIVER_KEYS)} (a typo would silently flatten the sweep axis)"
        )
    if "variable_name" not in spec:
        raise ValueError(f"interaction_grid.{which} must declare 'variable_name'")
    if "base_value" not in spec:
        raise ValueError(f"interaction_grid.{which} must declare 'base_value'")
    has_pct = spec.get("low_pct") is not None and spec.get("high_pct") is not None
    has_abs = spec.get("low_value") is not None and spec.get("high_value") is not None
    if not (has_pct or has_abs):
        raise ValueError(
            f"interaction_grid.{which} must declare a sweep range: either low_pct+high_pct "
            "(relative) or low_value+high_value (absolute); a driver with no range is a flat axis"
        )
    return ParameterRangeConfig(**{k: spec[k] for k in spec})


def build_interaction_grid_for_scenario(
    scenario_config_path: str | Path,
    *,
    run_cfg: SensitivityRunConfig = _DEFAULT_SENSITIVITY_RUN_CONFIG,
) -> TwoFactorInteractionGrid:
    """Resolve the two drivers + metric from a scenario's config and build the interaction grid.

    Loads the resolved scenario, reads its CONFIG-REQUIRED ``interaction_grid`` block (fail-loud on
    absence — no default driver pair is imposed), parses the two driver specs, and calls the
    slice-1 primitive :func:`analytics.sensitivity.interaction.build_two_factor_interaction_grid`.
    The primitive's strict resolve guard (``run_cfg.strict=True`` by default) raises on a driver
    that does not resolve to a config path, so the report path never disagrees with the engine.

    Args:
        scenario_config_path: Path to the scenario YAML/JSON (resolved via
            :func:`analytics.scenario_loader.load_scenario_config`).
        run_cfg: Engine knobs; ``strict`` (default True) gates the resolve-validation fail-loud.

    Returns:
        The :class:`TwoFactorInteractionGrid` (raw metric surface + interaction surface + honesty
        metadata) — heavy: ``N x M`` full-pipeline evaluations plus one base evaluation.

    Raises:
        ValueError: the scenario declares no ``interaction_grid`` block, or the block omits
            ``metric`` / ``param_a`` / ``param_b``, or a driver spec is malformed — the caller
            opted in, so the failure is loud (CESSPIT).
    """
    scenario_dict = dict(load_scenario_config(str(scenario_config_path)))
    ig_block = scenario_dict.get("interaction_grid")
    if not isinstance(ig_block, Mapping):
        raise ValueError(
            "interaction-grid report needs an 'interaction_grid' config block declaring "
            "metric/param_a/param_b; scenario "
            f"{scenario_config_path} declares none (no default driver pair is imposed)"
        )
    metric = ig_block.get("metric")
    if not isinstance(metric, str) or not metric:
        raise ValueError(
            "interaction_grid.metric must be a non-empty KPI key (e.g. 'project_irr')"
        )
    if "param_a" not in ig_block:
        raise ValueError("interaction_grid must declare 'param_a' (grid rows)")
    if "param_b" not in ig_block:
        raise ValueError("interaction_grid must declare 'param_b' (grid columns)")

    param_a = _parse_driver(ig_block["param_a"], which="param_a")
    param_b = _parse_driver(ig_block["param_b"], which="param_b")

    return build_two_factor_interaction_grid(
        base_config=scenario_dict,
        base_config_path=str(scenario_config_path),
        param_a=param_a,
        param_b=param_b,
        metric_key=metric,
        run_cfg=run_cfg,
    )


def emit_interaction_grid_report_from_pipeline(
    result: Mapping[str, Any],
    scenario_config_path: str | Path,
    output_html_path: str | Path,
    *,
    run_cfg: SensitivityRunConfig = _DEFAULT_SENSITIVITY_RUN_CONFIG,
    scenario_variant: Optional[str] = None,
    generated_at: Optional[str] = None,
) -> Path:
    """Render a lender HTML report with the two-factor interaction-grid section (#739 slice-2).

    The opt-in production caller wired into ``run_full_pipeline_v14.py``: it builds the grid on the
    scenario (:func:`build_interaction_grid_for_scenario`, the heavy N×M compute) and renders a
    lender report that includes the resulting interaction-grid block, alongside the core KPI /
    finance / readiness / three-statement sections built from the already-computed pipeline
    ``result``.

    The heavy N×M compute lives ONLY on this path — never the synchronous HTTP report route (the
    #645 lesson). The other heavy report blocks (tornado, global-SA, capital-risk) are not
    recomputed here; this caller's remit is the interaction grid, so those render omitted.

    Args:
        result: The finance pipeline result dict (``kpis`` / ``debt_result`` / ``annual_rows`` …),
            as produced by ``run_v14_pipeline``.
        scenario_config_path: Path to the (possibly wind/solar-patched) effective scenario.
        output_html_path: Where to write the rendered HTML report (parents created).
        run_cfg: Engine knobs for the grid build (``strict`` gates the resolve fail-loud).
        scenario_variant: Report label; defaults to the scenario file stem.
        generated_at: ISO timestamp stamped on the report; defaults to ``now(UTC)`` (production
            edge — the wall-clock is stamped here, not in the pure builder).

    Returns:
        The path the HTML report was written to.
    """
    grid = build_interaction_grid_for_scenario(scenario_config_path, run_cfg=run_cfg)

    variant = scenario_variant or Path(str(scenario_config_path)).stem
    case_result = CaseResult.from_pipeline_result(result, scenario_variant=variant)
    stamp = generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds")

    scenario_dict = dict(load_scenario_config(str(scenario_config_path)))
    context = build_report_context(
        case_result,
        generated_at=stamp,
        scenario_config=scenario_dict,
        debt_result=result.get("debt_result"),
        annual_rows=result.get("annual_rows"),
        interaction_grid=grid,
        run_result=result,
    )
    html = render_report_html(context)

    out_path = Path(output_html_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path
