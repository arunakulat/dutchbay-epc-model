from __future__ import annotations

from typing import Any, Dict, Mapping, Sequence

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
    base_config_path: str,
    scenario_name: str,
    monte_carlo_config_path: str | None = None,
    overrides: Mapping[str, Any] | None = None,
) -> Dict[str, MonteCarloResult]:
    """
    Lightweight fake for run_monte_carlo_analysis used in CASPER/tail-risk tests.

    The real engine currently only requires:
      - base_config_path
      - scenario_name

    but the public contract is future-proofed to accept:
      - monte_carlo_config_path
      - overrides

    This fake therefore accepts all four keyword-only arguments, with the latter
    two optional, so that:

    - evaluation_v14 can call it with just base_config_path + scenario_name
    - tests can still exercise the full CASPER signature without breaking.
    """
    _ = (base_config_path, monte_carlo_config_path, overrides)

    mc = MonteCarloResult(
        iterations=10,
        # IRR stats
        project_irr_mean=0.12,
        project_irr_std=0.01,
        project_irr_p10=0.11,
        project_irr_p50=0.12,
        project_irr_p90=0.13,
        # NPV stats
        project_npv_mean=1_000_000.0,
        project_npv_p10=900_000.0,
        project_npv_p50=1_000_000.0,
        project_npv_p90=1_100_000.0,
        # DSCR distribution
        dscr_min_p10=1.25,
        dscr_min_p50=1.35,
        # Engine bookkeeping
        failed_iterations=0,
        raw_results=[
            {"project_irr": 0.11, "project_npv": 900_000.0, "dscr_min": 1.25},
            {"project_irr": 0.12, "project_npv": 1_000_000.0, "dscr_min": 1.35},
            {"project_irr": 0.13, "project_npv": 1_100_000.0, "dscr_min": 1.45},
        ],
        scenario_name=scenario_name,
        # SEs – just non-zero toy values for downstream maths
        project_irr_se=0.002,
        project_npv_se=10_000.0,
        dscr_min_se=0.02,
    )

    return {scenario_name: mc}
