from __future__ import annotations

from typing import Any, Mapping, Sequence

from analytics.contracts_v14 import MonteCarloResult


def fake_run_v14_pipeline(
    *,
    config: Mapping[str, Any],
    validation_mode: str = "strict",
    validation_modules: Sequence[str] | None = None,
) -> Mapping[str, Any]:
    """
    Lightweight fake for run_v14_pipeline used in CASPER/tail-risk tests.

    - Ignores validation knobs (mode/modules).
    - Synthesizes a minimal scenario_result dict that can be hydrated into
      contracts_v14.ScenarioResult.
    - Provides a small KPI dict for normalize_kpi_dict().
    """
    _ = (validation_mode, validation_modules)

    project_cfg = config.get("project") or {}
    scenario_name = str(project_cfg.get("name", "Toy Scenario"))

    return {
        "scenario_result": {
            "scenario_name": scenario_name,
            "config_path": "conf/toy.yaml",
            "project_npv": 1_000_000.0,
            "project_irr": 0.12,
            "dscr_series": [1.30, 1.35, 1.40],
            "min_dscr": 1.30,
            "max_debt_usd": 10_000_000.0,
        },
        "kpis": {
            "project_irr": 0.12,
            "project_npv": 1_000_000.0,
            "dscr_min": 1.30,
        },
    }


def fake_run_monte_carlo_analysis(
    *,
    base_config: Mapping[str, Any],
    n_trials: int = 1000,
    seed: int = 42,
    **kwargs: Any,
) -> MonteCarloResult:
    """Faithful fake for the canonical Monte Carlo engine.

    Matches the real ``analytics.mc.engine.run_monte_carlo_analysis`` signature
    (keyword-only ``base_config`` / ``n_trials`` / ``seed``) and returns a real
    :class:`contracts_v14.MonteCarloResult` dataclass — NOT a dict. This is
    deliberate: the previous fake accepted ``config=`` / ``n_iterations=`` and
    returned a ``{'success': ..., 'statistics': ...}`` dict, a contract the
    engine never had, which let the orchestrator's dead wiring pass tests. With
    this faithful fake the test fails unless the orchestrator calls the engine
    with the correct kwargs and consumes the dataclass result.
    """
    _ = (seed, kwargs)
    project_cfg = base_config.get("project") or {} if isinstance(base_config, Mapping) else {}
    scenario_name = str(project_cfg.get("name", "Toy Scenario"))

    return MonteCarloResult(
        scenario_name=scenario_name,
        iterations=int(n_trials),
        n_iterations=int(n_trials),
        failed_iterations=0,
        raw_results=None,
        project_irr_mean=0.12,
        project_irr_std=0.01,
        project_irr_p10=0.11,
        project_irr_p50=0.12,
        project_irr_p90=0.13,
        project_npv_mean=1_000_000.0,
        project_npv_p10=900_000.0,
        project_npv_p50=1_000_000.0,
        project_npv_p90=1_100_000.0,
        dscr_min_p10=1.25,
        dscr_min_p50=1.30,
    )
