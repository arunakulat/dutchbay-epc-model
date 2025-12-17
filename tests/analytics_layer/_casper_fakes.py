from __future__ import annotations

from typing import Any, Dict, Mapping, Sequence

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
) -> Dict[str, Any]:
    """
    Lightweight fake for run_monte_carlo_analysis used in CASPER/tail-risk tests.

    CRITICAL FIX v4: Returns SAME structure as real monte_carlo_v14.MonteCarloEngine.run()
    which includes 'success' key and matches expected field names.

    Real function (analytics.monte_carlo_v14.MonteCarloEngine.run()) returns:
        {
            'scenario_name': str,
            'n_iterations': int,  ← NOTE: 'n_iterations', NOT 'iterations'
            'statistics': {
                'irr_p10_pct': float,
                'irr_median_pct': float,
                'irr_p90_pct': float,
                'npv_p10_usd': float,
                'npv_median_usd': float,
                'npv_p90_usd': float,
                ...
            },
            'success': True,  ← CRITICAL: checked by evaluation_v14.py:492
            ...
        }

    Test config stores scenario name in config["project"]["name"].
    This matches the real function signature in evaluation_v14.py line 485.
    """
    # Extract scenario name from config - check multiple locations
    scenario_name = "default_scenario"

    if isinstance(config, DictConfig):
        # Try monte_carlo.scenario_name first
        if (
            hasattr(config, "monte_carlo")
            and hasattr(config.monte_carlo, "scenario_name")
        ):
            scenario_name = config.monte_carlo.scenario_name
        # Try scenario.scenario_name
        elif hasattr(config, "scenario") and hasattr(config.scenario, "scenario_name"):
            scenario_name = config.scenario.scenario_name
        # Try project.name (test configs use this)
        elif hasattr(config, "project") and hasattr(config.project, "name"):
            scenario_name = str(config.project.name)

    elif isinstance(config, dict):
        # Try monte_carlo.scenario_name first
        mc_cfg = config.get("monte_carlo", {})
        if isinstance(mc_cfg, dict) and "scenario_name" in mc_cfg:
            scenario_name = mc_cfg["scenario_name"]
        # Try scenario.scenario_name
        else:
            scenario_cfg = config.get("scenario", {})
            if isinstance(scenario_cfg, dict) and "scenario_name" in scenario_cfg:
                scenario_name = scenario_cfg["scenario_name"]
            # Fallback to project.name (test configs store scenario name here)
            else:
                project_cfg = config.get("project", {})
                if isinstance(project_cfg, dict) and "name" in project_cfg:
                    scenario_name = str(project_cfg["name"])

    # Generate fake Monte Carlo statistics matching real engine output
    # Note: Field names match exactly what real engine returns in 'statistics' dict
    statistics = {
        "npv_mean_usd": 1_000_000.0,
        "npv_std_usd": 100_000.0,
        "npv_median_usd": 1_000_000.0,
        "npv_p10_usd": 900_000.0,
        "npv_p90_usd": 1_100_000.0,
        "irr_mean_pct": 12.0,
        "irr_std_pct": 1.0,
        "irr_median_pct": 12.0,
        "irr_p10_pct": 11.0,
        "irr_p90_pct": 13.0,
    }

    # Return EXACT structure that real MonteCarloEngine.run() returns
    # This is what evaluation_v14.py expects when calling run_monte_carlo_analysis()
    return {
        "scenario_name": scenario_name,
        "n_iterations": n_iterations,  # ← Must be 'n_iterations' (real engine field)
        "project_life_years": 25,
        "discount_rate_pct": 8.0,
        "capex_total_usd": 50_000_000.0,
        "statistics": statistics,  # ← evaluation_v14.py uses this to build MonteCarloResult
        "iterations": [],  # Empty for fake
        "success": True,  # ← CRITICAL: must be present for evaluation_v14.py validation
    }
