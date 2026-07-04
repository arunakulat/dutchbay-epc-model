"""Opt-in production caller for the capital-risk (Monte-Carlo) report section (#779).

The lender report already *renders* a :class:`~app.reports.report_model.CapitalRiskBlock`
render-when-present (#776, surfacing #657) — but nothing ran the Monte-Carlo and supplied a
:class:`~analytics.capital_risk_layer_v14.CapitalRiskReport` in production, so the section never
appeared for a lender. This module is the missing "separate call": it runs the **canonical** MC
engine (``analytics.mc.engine`` — LHS + Iman-Conover correlation, reading the scenario's
``monte_carlo.parameters``), assembles the report, and renders a lender HTML report that includes
the capital-risk section.

It follows the ``analytics.executive_workbook.emit_executive_workbook_from_pipeline`` precedent:
a pure emitter, invoked opt-in and default-off from the batch CLI (``run_full_pipeline_v14.py``)
after a successful finance run. The heavy MC belongs in the batch / async-job path — never the
synchronous HTTP report route (that route passes ``capital_risk=None`` → section omitted → fast,
byte-identical). Leaving the CLI flag off keeps committed-scenario output byte-identical.

Lender-grade posture:
    - The MC runs with ``monte_carlo.allow_toy_fallback: false`` **forced on** regardless of the
      scenario's default: a failed trial then RAISES rather than substituting a fabricated toy
      metric that would poison the covenant-breach / VaR-CVaR / NPV numbers with no disclosure.
      :func:`~analytics.capital_risk_layer_v14.build_capital_risk_report_from_mc_result`
      double-guards by refusing any ``toy_fallback_count > 0`` result.
    - The trial count is a **bounded** report-appropriate ``n`` (config-first), NOT the scenario's
      ``monte_carlo.n_scenarios`` (100k) — a lender report needs a stable VaR/CVaR tail, not a
      research-grade sample.

Scope (deliberately narrow — this is the capital-risk caller, not a full report-parity build):
    the assembled context carries the core lender sections + the capital-risk block; the local
    sensitivity tornado and the Morris / PAWN global-SA screenings (each a heavy multi-evaluation
    sweep the synchronous API report computes) are **not** recomputed here and render omitted.

GWTF:
    - CESSPIT: fail-loud on a scenario without a ``monte_carlo.parameters`` list; the caller opted
      in, so an error surfaces rather than a silently empty report.
    - CCCDIR/ARCH: consumes the canonical engine + the ``build_report_context`` gateway only.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

from analytics.capital_risk_layer_v14 import (
    NPV_METRICS,
    CapitalRiskReport,
    build_capital_risk_report_from_mc_result,
)
from analytics.mc.engine import run_monte_carlo_analysis
from analytics.scenario_loader import load_scenario_config
from app.api.responses import CaseResult
from app.reports.renderer import render_report_html
from app.reports.report_model import build_report_context

__all__ = [
    "DEFAULT_CAPITAL_RISK_N_TRIALS",
    "LENDER_GRADE_MIN_TRIALS",
    "build_capital_risk_report_for_scenario",
    "emit_capital_risk_report_from_pipeline",
]

#: Lender-grade minimum trial count (CESSPIT floor). A capital-risk report shown to a lender must
#: not be built on a statistically inadequate sample — below this the ~5% VaR/CVaR tail is too thin
#: for a defensible number (the engine's own :data:`analytics.capital_risk_layer_v14._MIN_TRIALS`
#: = 20 only guards against an index crash, not statistical adequacy).
#: :func:`build_capital_risk_report_for_scenario` fails loud when ``n_trials`` is below ``min_trials``
#: (this floor by default). A caller may lower ``min_trials`` ONLY for a deliberately
#: sub-lender-grade wiring smoke (e.g. the fast integration test) — never on the production CLI path,
#: which always applies this floor.
LENDER_GRADE_MIN_TRIALS = 1000

#: Bounded, report-appropriate default trial count (config-first override:
#: ``capital_risk_report.n_trials``). Deliberately far below the scenario's research-grade
#: ``monte_carlo.n_scenarios`` (100k) — a lender report needs a stable ~5% VaR/CVaR tail, not a
#: converged research sample, and every trial is a full v14 evaluation. Sits comfortably above
#: :data:`LENDER_GRADE_MIN_TRIALS`.
DEFAULT_CAPITAL_RISK_N_TRIALS = 2000


def build_capital_risk_report_for_scenario(
    scenario_config_path: str | Path,
    output_dir: str | Path,
    *,
    n_trials: int = DEFAULT_CAPITAL_RISK_N_TRIALS,
    min_trials: int = LENDER_GRADE_MIN_TRIALS,
    seed: Optional[int] = None,
    npv_metric: str = "equity_npv",
) -> CapitalRiskReport:
    """Run the canonical MC on a scenario and assemble its :class:`CapitalRiskReport` (#779).

    Loads the resolved scenario, runs ``analytics.mc.engine`` with
    ``monte_carlo.allow_toy_fallback: false`` forced on (lender-grade — no fabricated trials) over
    a bounded ``n_trials``, and feeds the result to
    :func:`~analytics.capital_risk_layer_v14.build_capital_risk_report_from_mc_result` (covenant
    floors sourced config-first from the same scenario). The NPV-distribution PNG is written under
    ``output_dir``.

    Args:
        scenario_config_path: Path to the scenario YAML/JSON (resolved via
            :func:`analytics.scenario_loader.load_scenario_config`).
        output_dir: Directory for the NPV-distribution PNG (created if absent).
        n_trials: Bounded trial count for the report tail; must be >= ``min_trials``.
        min_trials: Lender-grade floor below which the report refuses to build (CESSPIT); defaults
            to :data:`LENDER_GRADE_MIN_TRIALS`. Lower it ONLY for a deliberately sub-lender-grade
            wiring smoke — the production CLI path always uses the default.
        seed: MC seed; defaults to the scenario's ``monte_carlo.seed`` (else the engine default).
        npv_metric: Which NPV bucket the distribution plots (``equity_npv`` or ``project_npv``).

    Returns:
        The unified :class:`CapitalRiskReport`.

    Raises:
        ValueError: if ``n_trials`` is below ``min_trials`` (a lender-grade VaR/CVaR tail needs an
            adequate sample), or if the scenario carries no ``monte_carlo.parameters`` list to
            sample (a lender-grade capital-risk report needs sampled risk drivers).
    """
    if int(n_trials) < int(min_trials):
        # Fail loud (CESSPIT) rather than emit a lender-grade risk number off a thin tail.
        raise ValueError(
            f"capital-risk report needs >= {min_trials} trials for a lender-grade VaR/CVaR tail; "
            f"got n_trials={n_trials}. Raise capital_risk_report.n_trials (only a non-lender-grade "
            "smoke may lower min_trials explicitly)."
        )
    # Fail FAST (CESSPIT pre-flight) on a mistyped npv_metric — before the bounded MC runs, rather
    # than after (the downstream renderer guards the same NPV_METRICS set, but only post-run).
    if npv_metric not in NPV_METRICS:
        raise ValueError(f"npv_metric must be one of {NPV_METRICS}; got {npv_metric!r}")
    scenario_dict = dict(load_scenario_config(str(scenario_config_path)))
    mc_block = scenario_dict.get("monte_carlo")
    if not isinstance(mc_block, Mapping) or not mc_block.get("parameters"):
        raise ValueError(
            "capital-risk report needs a monte_carlo.parameters list to sample lender risk "
            f"drivers; scenario {scenario_config_path} declares none"
        )

    # Force fail-loud (no fabricated toy trials) regardless of the scenario default, via a shallow
    # copy so ``scenario_dict`` (fed to the report context below) is left untouched.
    mc_base = {
        **scenario_dict,
        "monte_carlo": {**dict(mc_block), "allow_toy_fallback": False},
    }
    mc_seed = int(seed) if seed is not None else int(mc_block.get("seed", 123))

    mc_result = run_monte_carlo_analysis(
        base_config=mc_base, n_trials=int(n_trials), seed=mc_seed
    )

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    return build_capital_risk_report_from_mc_result(
        mc_result,
        out_dir,
        config_path=str(scenario_config_path),
        npv_metric=npv_metric,
    )


def emit_capital_risk_report_from_pipeline(
    result: Mapping[str, Any],
    scenario_config_path: str | Path,
    output_html_path: str | Path,
    *,
    n_trials: int = DEFAULT_CAPITAL_RISK_N_TRIALS,
    min_trials: int = LENDER_GRADE_MIN_TRIALS,
    seed: Optional[int] = None,
    npv_metric: str = "equity_npv",
    scenario_variant: Optional[str] = None,
    generated_at: Optional[str] = None,
) -> Path:
    """Render a lender HTML report with the capital-risk section from a finance run (#779).

    The opt-in production caller wired into ``run_full_pipeline_v14.py``: it runs the canonical MC
    on the scenario (:func:`build_capital_risk_report_for_scenario`) and renders a lender report
    that includes the resulting capital-risk block, alongside the core KPI / finance /
    readiness / three-statement sections built from the already-computed pipeline ``result``.

    Args:
        result: The finance pipeline result dict (``kpis`` / ``debt_result`` / ``annual_rows`` …),
            as produced by ``run_v14_pipeline`` and consumed by the executive-workbook emitter.
        scenario_config_path: Path to the (possibly wind/solar-patched) effective scenario.
        output_html_path: Where to write the rendered HTML report (parents created).
        n_trials: Bounded MC trial count (see :func:`build_capital_risk_report_for_scenario`).
        min_trials: Lender-grade floor; the report refuses to build below it (see
            :data:`LENDER_GRADE_MIN_TRIALS`). Lower only for a sub-lender-grade smoke.
        seed: MC seed; defaults to the scenario's ``monte_carlo.seed``.
        npv_metric: NPV bucket for the distribution chart.
        scenario_variant: Report label; defaults to the scenario file stem.
        generated_at: ISO timestamp stamped on the report; defaults to ``now(UTC)`` (this is a
            production edge, so the wall-clock is stamped here rather than inside the pure builder).

    Returns:
        The path the HTML report was written to.
    """
    report = build_capital_risk_report_for_scenario(
        scenario_config_path,
        Path(output_html_path).parent,
        n_trials=n_trials,
        min_trials=min_trials,
        seed=seed,
        npv_metric=npv_metric,
    )

    variant = scenario_variant or Path(str(scenario_config_path)).stem
    case_result = CaseResult.from_pipeline_result(result, scenario_variant=variant)
    stamp = generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds")

    # Re-load a clean scenario dict for the report context (the MC copy forced
    # allow_toy_fallback:false, but the report layer never reads the monte_carlo block, so a fresh
    # load keeps provenance honest). Tornado / global-SA are intentionally omitted (see module
    # docstring) — this caller's remit is the capital-risk surface.
    scenario_dict = dict(load_scenario_config(str(scenario_config_path)))
    context = build_report_context(
        case_result,
        generated_at=stamp,
        scenario_config=scenario_dict,
        debt_result=result.get("debt_result"),
        annual_rows=result.get("annual_rows"),
        capital_risk=report,
        run_result=result,
    )
    html = render_report_html(context)

    out_path = Path(output_html_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path
