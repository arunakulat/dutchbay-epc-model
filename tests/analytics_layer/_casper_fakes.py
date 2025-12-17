from __future__ import annotations

from typing import Any, Dict, Mapping, Sequence

from analytics.contracts_v14 import MonteCarloResult
from omegaconf import DictConfig


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
    config: DictConfig | Mapping[str, Any],
    n_iterations: int = 1000,
    **kwargs: Any,
) -> Dict[str, MonteCarloResult]:
    """
    Lightweight fake for run_monte_carlo_analysis used in CASPER/tail-risk tests.

    FIXED: Now accepts config (DictConfig or dict) and n_iterations parameters
    instead of base_config_path, scenario_name, and scenario_config_path.

    This matches the real function signature in evaluation_v14.py line 485:
        mc_kwargs: Dict[str, Any] = {
            "config": mc_config,
            "n_iterations": mc_config.monte_carlo.get("n_iterations", 1000),
        }
        mc_result = run_monte_carlo_analysis(**mc_kwargs)

    Includes raw_results for tail-risk analysis compatibility.
    """
    # Extract scenario name from config if available
    scenario_name = "default_scenario"
    if isinstance(config, DictConfig):
        if (
            hasattr(config, "monte_carlo")
            and hasattr(config.monte_carlo, "scenario_name")
        ):
            scenario_name = config.monte_carlo.scenario_name
        elif hasattr(config, "scenario") and hasattr(config.scenario, "scenario_name"):
            scenario_name = config.scenario.scenario_name
    elif isinstance(config, dict):
        mc_cfg = config.get("monte_carlo", {})
        if isinstance(mc_cfg, dict):
            scenario_name = mc_cfg.get("scenario_name", "default_scenario")
        scenario_cfg = config.get("scenario", {})
        if isinstance(scenario_cfg, dict):
            scenario_name = scenario_cfg.get("scenario_name", scenario_name)

    # Generate fake Monte Carlo samples for tail-risk analysis
    # These must match the summary statistics (p10, p50, p90, mean, etc.)
    raw_results = [
        {"project_irr": 0.11, "project_npv": 900000.0, "dscr_min": 1.25},
        {"project_irr": 0.115, "project_npv": 950000.0, "dscr_min": 1.27},
        {"project_irr": 0.12, "project_npv": 1000000.0, "dscr_min": 1.30},
        {"project_irr": 0.12, "project_npv": 1000000.0, "dscr_min": 1.30},
        {"project_irr": 0.12, "project_npv": 1000000.0, "dscr_min": 1.30},
        {"project_irr": 0.12, "project_npv": 1000000.0, "dscr_min": 1.30},
        {"project_irr": 0.12, "project_npv": 1000000.0, "dscr_min": 1.30},
        {"project_irr": 0.125, "project_npv": 1050000.0, "dscr_min": 1.32},
        {"project_irr": 0.13, "project_npv": 1100000.0, "dscr_min": 1.35},
        {"project_irr": 0.13, "project_npv": 1100000.0, "dscr_min": 1.35},
    ]

    mc = MonteCarloResult(
        scenario_name=scenario_name,
        iterations=n_iterations,
        failed_iterations=0,
        # IRR stats
        project_irr_mean=0.12,
        project_irr_std=0.01,
        project_irr_p10=0.11,
        project_irr_p50=0.12,
        project_irr_p90=0.13,
        project_irr_se=0.001,
        # NPV stats
        project_npv_mean=1000000.0,
        project_npv_p10=900000.0,
        project_npv_p50=1000000.0,
        project_npv_p90=1100000.0,
        project_npv_se=10000.0,
        # DSCR stats
        dscr_min_p10=1.25,
        dscr_min_p50=1.30,
        dscr_min_se=0.01,
        # Raw results for tail-risk analysis
        raw_results=raw_results,
    )

    # Return dict keyed by scenario name (matching real function behavior)
    return {scenario_name: mc}
