#!/usr/bin/env python3
"""
Exact code to replace in analytics/sensitivity_v14.py around line 489.

This is the CORRECT way to construct TornadoResult.
"""

# ═══════════════════════════════════════════════════════════════════════════
# FIND THIS CODE (lines ~470-495):
# ═══════════════════════════════════════════════════════════════════════════
"""
    logger.debug(
        "_analyze_single_parameter: variable=%s label=%s "
        "base=%s low=%s high=%s impact=%s dir=%s",
        variable_name,
        label,
        base_metric_value,
        low_metric,
        high_metric,
        impact_abs,
        impact_dir,
    )

    return TornadoResult({
        "variable": label,
        "base_irr": base_metric_value,
        "low_irr": low_metric,
        "high_irr": high_metric,
    })
"""

# ═══════════════════════════════════════════════════════════════════════════
# REPLACE WITH THIS CODE:
# ═══════════════════════════════════════════════════════════════════════════
"""
    logger.debug(
        "_analyze_single_parameter: variable=%s label=%s "
        "base=%s low=%s high=%s impact=%s dir=%s",
        variable_name,
        label,
        base_metric_value,
        low_metric,
        high_metric,
        impact_abs,
        impact_dir,
    )

    # Create ShockResult object for this single parameter shock
    from analytics.contracts_v14 import ShockResult

    shock = ShockResult(
        variable_name=variable_name,
        base_value=base_value,
        low_value=low_value,
        high_value=high_value,
        base_metric=base_metric_value,
        low_metric=low_metric,
        high_metric=high_metric,
        metric_name=metric_name,
        label=label,
    )

    # TornadoResult expects: metric_name, base_metric, shock_results (List[ShockResult])
    return TornadoResult(
        metric_name=metric_name,
        base_metric=base_metric_value,
        shock_results=[shock],
        low_case_metric=low_metric,
        high_case_metric=high_metric,
    )
"""

# ═══════════════════════════════════════════════════════════════════════════
# WHY THIS WORKS:
# ═══════════════════════════════════════════════════════════════════════════
"""
1. TornadoResult is a DATACLASS with this signature:

   @dataclass
   class TornadoResult:
       metric_name: str
       base_metric: float
       shock_results: List[ShockResult]
       low_case_metric: Optional[float] = None
       high_case_metric: Optional[float] = None

2. It expects a LIST of ShockResult objects, not a flat dict

3. ShockResult is also a dataclass:

   @dataclass
   class ShockResult:
       variable_name: str
       base_value: float
       low_value: float
       high_value: float
       base_metric: float
       low_metric: float
       high_metric: float
       metric_name: str
       label: Optional[str] = None

4. All required values are available in analyze_single_parameter() function:
   - variable_name, base_value, low_value, high_value (from param)
   - base_metric_value, low_metric, high_metric (from evaluations)
   - metric_name (passed as argument)
   - label (computed from override_labels)
"""

print(__doc__)
print("\n" + "=" * 70)
print("Copy the REPLACEMENT code above and paste into")
print("analytics/sensitivity_v14.py at line ~489")
print("=" * 70)
