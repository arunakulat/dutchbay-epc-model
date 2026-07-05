"""Opt-in production caller for the cross-technology headline-KPI comparison section (#745 slice-1).

The lender report renders a :class:`~app.reports.report_model.TechComparisonBlock`
render-when-present (#745) — this module is the missing "separate call" that runs the compared
configs and supplies the block. It emits a side-by-side table of the headline KPIs of MULTIPLE
scenario configs (this slice: the wind lender case + the hybrid case that exist).

Canonical basis (lender integrity — the #745 decision): each compared config is run through the
CANONICAL pipeline ``analytics.pipeline_v14_enhanced.run_v14_pipeline(config=<path>,
validation_mode="strict")`` and its ``result["kpis"]`` is read. So the wind column RECONCILES
EXACTLY to the committed lendercase headline KPIs (``project_irr`` byte-for-byte the report's own).
The non-canonical ``ScenarioAnalytics`` comparison-snapshot basis (fixed ``debt_ratio`` /
non-WACC discount) is deliberately NOT used — it would not match the report's own headline KPIs and
is a lender-facing inconsistency.

It follows the ``app.reports.interaction_grid_emit`` / ``app.reports.capital_risk_emit`` precedent:
a pure emitter, invoked opt-in and default-off from the batch CLI (``run_full_pipeline_v14.py``)
after a successful finance run. The multiple full-pipeline runs are the heavy compute and belong in
the batch / async-job path — never the synchronous HTTP report route (that route passes
``tech_comparison=None`` -> section omitted -> fast, byte-identical). Leaving the CLI flag off keeps
committed-scenario output byte-identical.

Config-first, fail-loud (CESSPIT). The comparison scenario list is CONFIG-REQUIRED — this module
imposes no default scenario pair (hardcoding one would silently choose the analytical content). A
run that opts in must declare a ``tech_comparison`` block with a non-empty ``scenarios`` list of
``{label, config}`` entries; an absent/empty list, or a listed ``config`` path that does not exist,
RAISES rather than emitting a silently degenerate comparison.

GWTF:
    - CESSPIT: fail-loud on an absent/empty scenario list or a missing scenario path.
    - CCCDIR/ARCH: consumes the canonical pipeline + the ``build_report_context`` gateway only; no
      finance or IRR logic lives here (the projection is a PURE reshape of published KPIs).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from analytics.pipeline_v14_enhanced import run_v14_pipeline
from analytics.scenario_loader import load_scenario_config
from app.api.responses import CaseResult
from app.reports.renderer import render_report_html
from app.reports.report_model import (
    TechComparisonBlock,
    _build_tech_comparison,
    build_report_context,
)

__all__ = [
    "build_tech_comparison_for_scenarios",
    "emit_tech_comparison_report_from_pipeline",
    "resolve_tech_comparison_scenarios",
]


def resolve_tech_comparison_scenarios(
    scenarios: Any,
) -> list[tuple[str, str]]:
    """Validate + normalise a config ``tech_comparison.scenarios`` list into (label, path) pairs.

    Fail-loud (CESSPIT): the caller explicitly opted in, so a malformed or empty declaration RAISES
    rather than producing a silently degenerate one-column comparison.

    Args:
        scenarios: The raw ``tech_comparison.scenarios`` value from config — expected to be a
            non-empty sequence of ``{label, config}`` mappings.

    Returns:
        The ordered ``[(label, config_path), ...]`` pairs.

    Raises:
        ValueError: ``scenarios`` is not a non-empty sequence, an entry is not a mapping, an entry
            omits ``label`` / ``config``, or a listed ``config`` path does not exist on disk.
    """
    if isinstance(scenarios, (str, bytes, Mapping)) or not isinstance(
        scenarios, Sequence
    ):
        raise ValueError(
            "tech-comparison report needs a 'tech_comparison.scenarios' list of {label, config} "
            f"entries; got {type(scenarios).__name__}"
        )
    entries = list(scenarios)
    if not entries:
        raise ValueError(
            "tech-comparison report needs a non-empty 'tech_comparison.scenarios' list of "
            "{label, config} entries; the list is empty (no default scenario pair is imposed)"
        )
    resolved: list[tuple[str, str]] = []
    for i, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            raise ValueError(
                f"tech_comparison.scenarios[{i}] must be a mapping with 'label' and 'config'; "
                f"got {type(entry).__name__}"
            )
        label = entry.get("label")
        config = entry.get("config")
        if not isinstance(label, str) or not label:
            raise ValueError(
                f"tech_comparison.scenarios[{i}] must declare a non-empty 'label'"
            )
        if not isinstance(config, str) or not config:
            raise ValueError(
                f"tech_comparison.scenarios[{i}] ('{label}') must declare a 'config' path"
            )
        if not Path(config).exists():
            raise ValueError(
                f"tech_comparison.scenarios[{i}] ('{label}') config path does not exist: "
                f"{config}"
            )
        resolved.append((label, config))
    return resolved


def build_tech_comparison_for_scenarios(
    scenario_paths_with_labels: Sequence[tuple[str, str]],
    *,
    validation_mode: str = "strict",
) -> TechComparisonBlock:
    """Run the CANONICAL pipeline per config and project headline KPIs into a comparison block (#745).

    Runs each ``(label, config_path)`` through
    :func:`analytics.pipeline_v14_enhanced.run_v14_pipeline` (strict validation by default) and reads
    its ``result["kpis"]`` — the SAME canonical basis as the report's own headline, so each column
    reconciles to that config's committed headline KPIs. The published KPI dicts are then reshaped by
    the PURE :func:`app.reports.report_model._build_tech_comparison` mapper (no finance
    recomputation here). The multiple full-pipeline runs are the heavy compute.

    Args:
        scenario_paths_with_labels: Ordered ``[(label, config_path), ...]`` pairs (already
            validated by :func:`resolve_tech_comparison_scenarios`).
        validation_mode: Pipeline validation mode; ``"strict"`` (the canonical default) so a column
            never carries a KPI from an un-validated run.

    Returns:
        The :class:`TechComparisonBlock` — one column per config.

    Raises:
        ValueError: ``scenario_paths_with_labels`` is empty (a comparison needs at least one column;
            the caller opted in — CESSPIT). Any per-config pipeline failure propagates.
    """
    if not scenario_paths_with_labels:
        raise ValueError(
            "tech-comparison report needs at least one (label, config) pair; got none"
        )
    cases: list[tuple[str, Mapping[str, Any]]] = []
    for label, config_path in scenario_paths_with_labels:
        result = run_v14_pipeline(
            config=str(config_path), validation_mode=validation_mode
        )
        kpis = dict(result.get("kpis") or {})
        # Gearing is not a top-level pipeline KPI; the report itself sources it from the
        # dual-DSCR solved gearing (api.pipeline_api gearing = dual_dscr.solved_gearing).
        # Read it from that SAME published value so the comparison column reconciles to the
        # report's own gearing instead of rendering a permanently-blank column. This is a
        # read of an already-computed value (not finance recomputation); the projection
        # mapper stays pure. Absent (a non-dual-sized config) -> stays None -> honest
        # em-dash, never fabricated.
        if kpis.get("gearing") is None:
            dual = (result.get("debt_result") or {}).get("dual_dscr") or {}
            solved_gearing = dual.get("solved_gearing")
            if solved_gearing is not None:
                kpis["gearing"] = solved_gearing
        cases.append((label, kpis))
    block = _build_tech_comparison(cases)
    if (
        block is None
    ):  # defensive — the non-empty guard above already ensures cases is non-empty.
        raise ValueError(
            "tech-comparison projection returned no rows despite a non-empty scenario list"
        )
    return block


def emit_tech_comparison_report_from_pipeline(
    result: Mapping[str, Any],
    scenario_config_path: str | Path,
    output_html_path: str | Path,
    *,
    scenarios: Any,
    validation_mode: str = "strict",
    scenario_variant: Optional[str] = None,
    generated_at: Optional[str] = None,
) -> Path:
    """Render a lender HTML report with the cross-technology comparison section (#745 slice-1).

    The opt-in production caller wired into ``run_full_pipeline_v14.py``: it runs the canonical
    pipeline on each compared config (:func:`build_tech_comparison_for_scenarios`, the heavy
    multi-run compute) and renders a lender report that includes the resulting comparison block,
    alongside the core KPI / finance / readiness / three-statement sections built from the
    already-computed pipeline ``result`` for the primary scenario.

    The heavy multi-run compute lives ONLY on this path — never the synchronous HTTP report route
    (the #645 lesson). The other heavy report blocks (tornado, global-SA, capital-risk, interaction
    grid) are not recomputed here; this caller's remit is the comparison table, so those render
    omitted.

    Args:
        result: The finance pipeline result dict (``kpis`` / ``debt_result`` / ``annual_rows`` …),
            as produced by ``run_v14_pipeline`` for the PRIMARY scenario.
        scenario_config_path: Path to the (possibly wind/solar-patched) effective primary scenario.
        output_html_path: Where to write the rendered HTML report (parents created).
        scenarios: The config-required ``tech_comparison.scenarios`` declaration (a non-empty list
            of ``{label, config}`` entries); validated fail-loud by
            :func:`resolve_tech_comparison_scenarios`.
        validation_mode: Pipeline validation mode for the compared runs; ``"strict"`` by default.
        scenario_variant: Report label; defaults to the primary scenario file stem.
        generated_at: ISO timestamp stamped on the report; defaults to ``now(UTC)`` (this is a
            production edge, so the wall-clock is stamped here rather than inside the pure builder).

    Returns:
        The path the HTML report was written to.

    Raises:
        ValueError: the ``scenarios`` declaration is absent/empty/malformed or a listed config path
            does not exist (CESSPIT — the caller opted in).
    """
    resolved = resolve_tech_comparison_scenarios(scenarios)
    block = build_tech_comparison_for_scenarios(
        resolved, validation_mode=validation_mode
    )

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
        tech_comparison=block,
        run_result=result,
    )
    html = render_report_html(context)

    out_path = Path(output_html_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path
