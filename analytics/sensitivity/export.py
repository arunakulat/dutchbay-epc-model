from __future__ import annotations

"""
analytics.sensitivity.export

Suite -> tables (dataframes / records) suitable for CSV/Excel/JSON exports.

Design:
- Pure transforms only (no evaluation)
- Optional pandas dependency (guarded import)
- CASPER-friendly: return dict-of-tables

Public API (keep stable):
- suite_to_tables(...)
- suite_to_records(...)
"""

from typing import Any, Dict
from analytics.contracts_v14 import SensitivitySuite

try:
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover
    pd = None  # type: ignore


def suite_to_records(
    suite: SensitivitySuite,
) -> Dict[str, Any]:
    """
    Convert SensitivitySuite to JSON-friendly records.
    
    Adapted for contracts_v14.SensitivitySuite structure:
    - suite.metric: str (target metric)
    - suite.base_config_path: str
    - suite.tornado_results: List[TornadoResult]
    - suite.base_kpis: Optional[Dict[str, float]]
    
    TornadoResult structure:
    - metric_name: str (parameter name)
    - base_metric: float
    - shock_results: List[ShockResult]
    - label: Optional[str]
    - impact_abs: float
    
    ShockResult structure:
    - low_case: float
    - high_case: float
    - impact: float
    """
    out: Dict[str, Any] = {
        "metadata": {
            "metric": suite.metric,
            "base_config_path": suite.base_config_path,
        }
    }
    
    if suite.base_kpis:
        out["metadata"]["base_kpis"] = dict(suite.base_kpis)

    rows = []
    for t in suite.tornado_results:
        # Extract shock results
        if t.shock_results and len(t.shock_results) > 0:
            shock = t.shock_results[0]
            rows.append(
                {
                    "parameter": t.metric_name,
                    "label": t.label or t.metric_name,
                    "metric": suite.metric,
                    "base_value": t.base_metric,
                    "low_value": shock.low_case,
                    "high_value": shock.high_case,
                    "impact": shock.impact,
                    "impact_abs": t.impact_abs,
                }
            )
        else:
            # No shock results - create placeholder
            rows.append(
                {
                    "parameter": t.metric_name,
                    "label": t.label or t.metric_name,
                    "metric": suite.metric,
                    "base_value": t.base_metric,
                    "low_value": t.base_metric,
                    "high_value": t.base_metric,
                    "impact": 0.0,
                    "impact_abs": 0.0,
                }
            )
    
    out["tornado_rows"] = rows
    return out


def suite_to_tables(
    suite: SensitivitySuite,
) -> Dict[str, Any]:
    """
    Convert suite into a dict-of-tables. If pandas is available, returns DataFrames.
    Otherwise returns records.
    """
    rec = suite_to_records(suite)

    if pd is None:
        return rec

    tables: Dict[str, Any] = {"metadata": rec.get("metadata", {})}

    rows = rec.get("tornado_rows", [])
    tables["tornado_rows"] = pd.DataFrame(rows)

    # If tail risk was attached, include it as a table
    # Note: contracts_v14.SensitivitySuite doesn't have .metadata field
    # so tail risk enrichment may need separate handling

    return tables
