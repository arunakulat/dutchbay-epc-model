from __future__ import annotations

from pathlib import Path
from typing import Any, List, Optional

from analytics.contracts_v14 import ShockSpec, SensitivitySuite, StandardShockLibrary, ShockResult
from analytics.evaluate_scenario import evaluate_with_overrides
from analytics.scenario_loader import load_scenario_config

def run_sensitivity_analysis(
    base_config_path: str | Path,
    metric: str = "project_irr",
    shock_specs: Optional[List[ShockSpec]] = None,
    *,
    validation_mode: str = "strict",
    validation_modules: List[str] | None = None,
) -> SensitivitySuite:
    """
    Run sensitivity analysis for a given scenario configuration.
    """
    base_path = Path(base_config_path)
    # 1. Load base scenario config
    base_cfg: dict[str, Any] = load_scenario_config(base_path)
    # 2. Evaluate base scenario to get baseline metric
    base_kpis: dict[str, Any] = evaluate_with_overrides(
        base_config_path,
        overrides=None,
        validation_mode=validation_mode,
        validation_modules=validation_modules or ["cashflow", "debt"],
    )
    scenario_name = str(base_kpis.get("scenario_name", base_path.stem))
    base_metric_value = float(base_kpis.get(metric, 0.0))
    # 3. Build default shock specifications if none provided
    if shock_specs is None:
        shock_specs = []
        cfg = base_cfg
        def _get_cfg_value(keys: List[str]) -> Optional[float]:
            """Get nested config value by list of keys (case-insensitive)."""
            d = cfg
            for key in keys:
                if not isinstance(d, dict):
                    return None
                # Try exact key first, then case-insensitive match
                if key in d:
                    d = d[key]
                else:
                    match = next((k for k in d if str(k).lower() == key.lower()), None)
                    d = d.get(match) if match else None
                if d is None:
                    return None
            return float(d) if isinstance(d, (int, float)) else None
        # Standard shock base values
        capex_base = _get_cfg_value(["project", "capex_usd_per_kw"])
        if capex_base is not None:
            shock_specs.append(StandardShockLibrary.capex_overrun(capex_base))
        opex_base = _get_cfg_value(["project", "opex_usd_per_kw"])
        if opex_base is not None:
            shock_specs.append(StandardShockLibrary.opex_variation(opex_base))
        cf_base = _get_cfg_value(["project", "capacity_factor"])
        if cf_base is not None:
            shock_specs.append(StandardShockLibrary.capacity_factor(cf_base))
        tariff_base = _get_cfg_value(["project", "tariff_usd_per_kwh"])
        if tariff_base is not None:
            shock_specs.append(StandardShockLibrary.power_price(tariff_base))
        tenor_base = _get_cfg_value(["finance", "debt", "tenor_years"])
        if tenor_base is not None:
            shock_specs.append(StandardShockLibrary.debt_tenor(tenor_base))
        interest_base = _get_cfg_value(["finance", "debt", "interest_rate"])
        if interest_base is not None and interest_base > 0:
            shock_specs.append(StandardShockLibrary.interest_rate(interest_base))
    # 4. Evaluate scenario for each shock at low and high values
    shock_results: List[ShockResult] = []
    for shock in shock_specs:
        # Low shock run
        low_override: dict[str, Any] = {}
        keys = shock.variable_name.split(".")
        current = low_override
        for key in keys[:-1]:
            current[key] = {}
            current = current[key]
        current[keys[-1]] = shock.low_value
        low_kpis = evaluate_with_overrides(
            base_config_path,
            overrides=low_override,
            validation_mode=validation_mode,
            validation_modules=validation_modules or ["cashflow", "debt"],
        )
        low_metric_value = float(low_kpis.get(metric, 0.0))
        # High shock run
        high_override: dict[str, Any] = {}
        current = high_override
        for key in keys[:-1]:
            current[key] = {}
            current = current[key]
        current[keys[-1]] = shock.high_value
        high_kpis = evaluate_with_overrides(
            base_config_path,
            overrides=high_override,
            validation_mode=validation_mode,
            validation_modules=validation_modules or ["cashflow", "debt"],
        )
        high_metric_value = float(high_kpis.get(metric, 0.0))
        # Construct shock result
        shock_result = ShockResult(
            variable_name=shock.variable_name,
            metric_name=metric,
            base_value=float(shock.base_value),
            low_value=float(shock.low_value),
            high_value=float(shock.high_value),
            base_metric=base_metric_value,
            low_metric=low_metric_value,
            high_metric=high_metric_value,
            label=shock.label,
        )
        shock_results.append(shock_result)
    # 5. Create SensitivitySuite with results
    suite = SensitivitySuite(
        metric_name=metric,
        base_metric_value=base_metric_value,
        scenario_name=scenario_name,
        shock_results=shock_results,
        base_config_path=str(base_path),
    )
    return suite
