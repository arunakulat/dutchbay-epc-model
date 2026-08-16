"""
analytics.sensitivity.adapters

Adapter layer between sensitivity.engine and contracts_v14.py.

Problem:
--------
The new sensitivity engine was designed with a generic parameter interface,
but contracts_v14.py uses specific Pydantic models with different field names:

- ParameterRangeConfig uses: variable_name, base_value, low_pct, high_pct
- TornadoResult uses: metric_name, base_metric, shock_results[], label
- SensitivitySuite uses: metric, base_config_path, tornado_results[]

Solution:
---------
This adapter provides bidirectional conversion:
1. contracts_v14 → engine format (for input)
2. engine format → contracts_v14 (for output)

This keeps engine.py clean and contract-agnostic while ensuring
full compliance with the established Pydantic contracts.

GWTF: Single conversion layer, no scattered adaptations.
CASPER: Contract-explicit transformations.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from analytics.contracts_v14 import (
    ParameterRangeConfig,
    SensitivitySuite,
    ShockResult,
    TornadoResult,
)

# ═══════════════════════════════════════════════════════════════════════════
# Parameter Adapters (contracts_v14 → engine)
# ═══════════════════════════════════════════════════════════════════════════


def parameter_to_engine_spec(param: ParameterRangeConfig) -> Dict[str, Any]:
    """
    Convert contracts_v14.ParameterRangeConfig to engine-compatible dict.

    Conversion:
    -----------
    ParameterRangeConfig fields:
        - variable_name: str (dotted path, e.g., 'finance.capex_usd')
        - base_value: float
        - low_pct / high_pct: Optional[float] (percentage mode, e.g. -10.0/10.0)
        - low_value / high_value: Optional[float] (absolute mode; takes
          precedence over the percentage fields when both are supplied)
        - label: Optional[str]

    Engine expects:
        - name: str
        - override_key: str (same as variable_name)
        - base: float
        - low: float (absolute value = base_value * (1 + low_pct/100))
        - high: float (absolute value = base_value * (1 + high_pct/100))

    Example:
    --------
    >>> param = ParameterRangeConfig(
    ...     variable_name="finance.capex_usd",
    ...     base_value=1000.0,
    ...     low_pct=-10.0,
    ...     high_pct=10.0,
    ...     label="CAPEX"
    ... )
    >>> spec = parameter_to_engine_spec(param)
    >>> spec['low']  # 1000 * (1 - 0.10) = 900.0
    900.0
    >>> spec['high']  # 1000 * (1 + 0.10) = 1100.0
    1100.0
    """
    base = float(param.base_value)

    # ParameterRangeConfig accepts EITHER absolute (low_value, high_value) OR
    # percentage (low_pct, high_pct) bounds. Prefer absolute when supplied;
    # otherwise derive from percentages (treating a missing pct as 0 = base).
    # The previous code assumed pct-mode unconditionally and crashed with
    # float(None) whenever a caller used absolute mode.
    if param.low_value is not None and param.high_value is not None:
        low = float(param.low_value)
        high = float(param.high_value)
    else:
        low_pct = param.low_pct if param.low_pct is not None else 0.0
        high_pct = param.high_pct if param.high_pct is not None else 0.0
        low = base * (1.0 + low_pct / 100.0)
        high = base * (1.0 + high_pct / 100.0)

    return {
        "name": param.label or param.variable_name,
        "override_key": param.variable_name,
        "base": base,
        "low": low,
        "high": high,
    }


def iter_param_cases_from_contract(
    param: ParameterRangeConfig,
) -> List[Tuple[str, Dict[str, Any]]]:
    """
    Generate (label, overrides) cases from ParameterRangeConfig.

    This is the contract-aware version of engine._iter_param_cases.

    Returns:
    --------
    List of (label, overrides) tuples:
        [("capex=base", {"finance.capex_usd": 1000.0}),
         ("capex=low", {"finance.capex_usd": 900.0}),
         ("capex=high", {"finance.capex_usd": 1100.0})]
    """
    spec = parameter_to_engine_spec(param)
    name = spec["name"]
    key = spec["override_key"]
    base = spec["base"]
    low = spec["low"]
    high = spec["high"]

    return [
        (f"{name}=base", {key: base}),
        (f"{name}=low", {key: low}),
        (f"{name}=high", {key: high}),
    ]


# ═══════════════════════════════════════════════════════════════════════════
# Result Adapters (engine → contracts_v14)
# ═══════════════════════════════════════════════════════════════════════════


def engine_to_tornado_result(
    *,
    parameter: ParameterRangeConfig,
    metric_key: str,
    base_value: float,
    cases: List[Dict[str, Any]],
) -> TornadoResult:
    """
    Convert engine tornado output to contracts_v14.TornadoResult.

    Engine format:
    --------------
    cases = [
        {"label": "capex=base", "value": 0.142, "overrides": {...}},
        {"label": "capex=low", "value": 0.155, "overrides": {...}},
        {"label": "capex=high", "value": 0.128, "overrides": {...}},
    ]

    TornadoResult expects:
    ----------------------
    - metric_name: str (parameter name, e.g., "CAPEX")
    - base_metric: float (base case value)
    - shock_results: List[ShockResult]
    - label: Optional[str]
    - impact_abs: float

    ShockResult expects:
    --------------------
    - variable_name: str (canonical dotted config path)
    - label: Optional[str] (human-readable driver label)
    - low_case: float
    - high_case: float
    - base_case: float
    - impact: float (high - low)
    - impact_abs: float (absolute high/low swing)
    - metric_name: str (target metric key)
    """
    # Extract low/high cases
    low_case = None
    high_case = None

    for c in cases:
        label = str(c.get("label", "")).lower()
        if "low" in label:
            low_case = float(c.get("value", 0.0))
        elif "high" in label:
            high_case = float(c.get("value", 0.0))

    # Fallback if not found
    if low_case is None:
        low_case = base_value
    if high_case is None:
        high_case = base_value

    impact = high_case - low_case
    shock = ShockResult(
        variable_name=parameter.variable_name,
        label=parameter.label,
        low_case=low_case,
        high_case=high_case,
        base_case=base_value,
        impact=impact,
        impact_abs=abs(impact),
        metric_name=metric_key,
    )

    return TornadoResult(
        metric_name=parameter.label or parameter.variable_name,
        base_metric=base_value,
        shock_results=[shock],
        label=parameter.label,
        impact_abs=abs(impact),
    )


def engine_to_sensitivity_suite(
    *,
    base_config_path: str,
    metric_key: str,
    tornado_results: List[TornadoResult],
    base_kpis: Dict[str, float],
) -> SensitivitySuite:
    """
    Convert engine suite output to contracts_v14.SensitivitySuite.

    SensitivitySuite expects:
    -------------------------
    - metric: str (target metric, e.g., "project_irr")
    - base_config_path: str (path to scenario config)
    - tornado_results: List[TornadoResult]
    - base_kpis: Optional[Dict[str, float]]
    """
    return SensitivitySuite(
        metric=metric_key,
        base_config_path=base_config_path,
        tornado_results=tornado_results,
        base_kpis=base_kpis,
    )
