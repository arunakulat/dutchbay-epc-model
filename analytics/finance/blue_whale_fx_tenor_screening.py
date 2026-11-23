"""Single-site adapter for :mod:`analytics.finance.fx_tenor_screening` (#1578 U4).

The dual-currency FX and tenor screening now runs for any scenario that declares a
``financing_screening`` block (owner ruling of 2026-11-16; contract #1754), through
``scripts/run_fx_tenor_screening_v14.py scenario=<path>``. The arithmetic moved to
:mod:`analytics.finance.fx_tenor_screening`, and every name is re-exported here, so existing
imports keep working (``REFACTOR-01`` SHIM).

This module keeps the original single-config entry point, :func:`run_comprehensive_screening`,
so ``scripts/run_blue_whale_fx_tenor_screening_v14.py`` prints the same bytes as before. The
config must now name its scenario (``governed_scenario_path``): no scenario is assumed in code
(#1759 U9). It holds no arithmetic of its own, and it goes once its inputs are read from the
scenario block alone (the block-driven run reproduces it exactly; see
``tests/finance/test_fx_tenor_screening.py``). #1799 owns that retirement, with this module's
config, script and single-site defaults.

HOLD (F-5, #1110, v15.6.1): screening indicators only, NOT a lender verdict, bankability
determination or credit commitment (#1629).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import yaml

from analytics.finance.fx_tenor_screening import (  # noqa: F401 - re-exported (SHIM)
    DEFAULT_ENGINE_PATH_NOTE,
    DEFAULT_ENGINE_PATH_STATUS,
    DEFAULT_F5_HOLD_CAVEAT,
    REPO_ROOT,
    amortize,
    amortize_tranche,
    annuity,
    cagr,
    complete_total,
    compute_coverage_metrics,
    compute_fx_cagr,
    compute_fx_history_metrics,
    energy_scaled_price,
    evaluate,
    evaluate_dual_currency_screening,
    metrics,
    run_fixed_debt_stress,
    scenario_screening_inputs,
    size_debt,
    size_debt_screening,
    validate_debt_tenor_against_ppa,
)


def load_governed_basecase_inputs(scenario_path: Path | str) -> Dict[str, Any]:
    """Load the screening inputs a scenario file carries.

    Args:
        scenario_path: Path to the scenario YAML (relative to repo root or absolute). It
            is required: no scenario is assumed (#1578 U4).

    Returns:
        Dictionary of screening-compatible inputs derived from the scenario.

    Raises:
        FileNotFoundError: If the scenario file does not exist.
        KeyError: If required scenario fields are absent.
        ValueError: If the loaded YAML is not a mapping.
    """
    resolved = Path(scenario_path)
    if not resolved.is_absolute():
        resolved = REPO_ROOT / resolved
    if not resolved.is_file():
        raise FileNotFoundError(f"Governed scenario file not found: {resolved}")

    data = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in governed scenario YAML: {resolved}")
    from analytics.evaluation_v14 import evaluated_scenario_config

    # #1899: the capex the engine finances, with a declared price date applied.
    return scenario_screening_inputs(evaluated_scenario_config(data))


def run_comprehensive_screening(raw_cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Execute complete screening suite across governed and sensitivity configs.

    Reads governed basecase inputs (capex, tariff, O&M, FX-at-close, etc.) from the
    scenario named by ``raw_cfg["governed_scenario_path"]``, which is required: no scenario
    is assumed (#1578 U4). Labels any divergent case as an explicit sensitivity.

    Args:
        raw_cfg: Loaded and validated configuration mapping.

    Returns:
        Structured summary mapping suitable for JSON emission.
    """
    scenario_path = raw_cfg["governed_scenario_path"]
    governed_inputs = load_governed_basecase_inputs(scenario_path)
    params = raw_cfg["screening_parameters"]
    cases = raw_cfg["cases"]

    # FX CAGR benchmark windows
    fx_metrics: List[Dict[str, Any]] = []
    for window in raw_cfg.get("fx_cagr_benchmark_windows", []):
        cagr_val = compute_fx_cagr(
            float(window["start"]),
            float(window["end"]),
            str(window["start_date"]),
            str(window["end_date"]),
        )
        fx_metrics.append(
            {
                "label": window["label"],
                "start": window["start"],
                "end": window["end"],
                "start_date": window["start_date"],
                "end_date": window["end_date"],
                "is_assumption": bool(window.get("is_assumption", True)),
                "evidence_status": window.get(
                    "evidence_status", "unverified_assumption_unverified_endpoint_rates"
                ),
                "annualized_quote_change_decimal": cagr_val,
            }
        )

    # Governed basecase 14-turbine screening (#1587, 15-year DFI / 20-year PPA)
    governed_15_cfg = {
        **governed_inputs,
        **params,
        **cases["14_governed_basecase"],
    }
    sized_governed_15 = size_debt_screening(governed_15_cfg)

    # Governed basecase 14-turbine screening (10-year DFI / 12-year PPA / 2-year tail)
    governed_10_cfg = {
        **governed_15_cfg,
        "dfi_tenor_years": 10,
        "ppa_years": 12,
        "lender_tail_years": 2,
    }
    sized_governed_10 = size_debt_screening(governed_10_cfg)

    # Explicit sensitivity (14 turbines, handoff PUCSL tariff / assumed O&M / 333.79 FX)
    sensitivity_15_cfg = {
        **governed_inputs,
        **params,
        **cases["14_handoff_sensitivity"],
    }
    sized_sensitivity_15 = size_debt_screening(sensitivity_15_cfg)

    # Fixed debt stress grid on governed 14-turbine basecase
    stress_cfg = raw_cfg["stress_grid"]
    held_debt = float(stress_cfg["held_debt_usd"])
    depreciation_rates = [float(r) for r in stress_cfg["depreciation_rates"]]
    shock_decimals = [float(s) for s in stress_cfg["shock_decimals"]]
    stress_results = run_fixed_debt_stress(
        governed_15_cfg, held_debt, depreciation_rates, shock_decimals
    )

    def _format_screening_block(
        sized: Dict[str, Any], case_meta: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {
            "case_type": case_meta.get("case_type", "governed_basecase_screening"),
            "turbine_count": int(case_meta.get("turbine_count", 14)),
            "debt_usd": sized["debt_usd"],
            "gearing_decimal": sized["gearing_decimal"],
            "equity_capex_balance_usd": sized["equity_capex_balance_usd"],
            "p50": sized["p50"],
            "assumed_downside": sized["assumed_downside"],
            "status": sized["status"],
            "lender_rates_are_assumptions": sized["lender_rates_are_assumptions"],
        }

    return {
        "schema_version": raw_cfg["schema_version"],
        "status": "complete",
        "governed_scenario_source": str(scenario_path),
        "governed_inputs_applied": governed_inputs,
        "f5_hold_caveat": raw_cfg.get("f5_hold_caveat", DEFAULT_F5_HOLD_CAVEAT),
        "engine_path_status": raw_cfg.get(
            "engine_path_status", DEFAULT_ENGINE_PATH_STATUS
        ),
        "engine_path_note": raw_cfg.get("engine_path_note", DEFAULT_ENGINE_PATH_NOTE),
        "fx_metrics": fx_metrics,
        "governed_basecase_14turbine_15year_screening": _format_screening_block(
            sized_governed_15, cases["14_governed_basecase"]
        ),
        "governed_basecase_14turbine_10year_screening": _format_screening_block(
            sized_governed_10, cases["14_governed_basecase"]
        ),
        "sensitivity_14turbine_15year_screening": _format_screening_block(
            sized_sensitivity_15, cases["14_handoff_sensitivity"]
        ),
        "fixed_debt_fx_stress_count": len(stress_results),
        "fixed_debt_fx_stress_summary": stress_results,
        "limitations_count": len(raw_cfg.get("limitations", [])),
        "disclaimer": (
            "HOLD (F-5, #1110, v15.6.1): Standalone screening indicator only; not a "
            "governed v14 lender commitment, lender verdict, or legal tax advice. "
            "The core v14 engine carries FX to the USD OPEX share (BW-5 / L-12 D-2); "
            "this screening does not call it."
        ),
    }
