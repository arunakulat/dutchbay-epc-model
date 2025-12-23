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

from typing import Any, Dict, Mapping, Optional, Sequence, Union

try:
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover
    pd = None  # type: ignore

from analytics.contracts_v14 import SensitivitySuite, MultiMetricSensitivitySuite


def suite_to_records(
    suite: Union[SensitivitySuite, MultiMetricSensitivitySuite],
) -> Dict[str, Any]:
    """
    Convert suite into JSON-friendly records.
    """
    out: Dict[str, Any] = {"metadata": dict(getattr(suite, "metadata", {}) or {})}

    if hasattr(suite, "tornado"):
        tornado = getattr(suite, "tornado")
        cases = getattr(tornado, "cases", [])
        metric_key = getattr(tornado, "metric_key", None)
        base_value = getattr(tornado, "base_value", None)

        rows = []
        for c in cases:
            rows.append(
                {
                    "label": c.get("label"),
                    "metric": metric_key,
                    "value": c.get("value"),
                    "base_value": base_value,
                    "overrides": c.get("overrides", {}),
                }
            )
        out["tornado_rows"] = rows
        return out

    # multi-metric
    tornados = getattr(suite, "tornados", [])
    rows = []
    for t in tornados:
        metric_keys = list(getattr(t, "metric_keys", []))
        base_values = dict(getattr(t, "base_values", {}) or {})
        cases = getattr(t, "cases", [])
        param = getattr(t, "parameter", None)
        pname = getattr(param, "name", None) if param is not None else None

        for c in cases:
            values = c.get("values", {}) or {}
            for mk in metric_keys:
                rows.append(
                    {
                        "parameter": pname,
                        "label": c.get("label"),
                        "metric": mk,
                        "value": values.get(mk),
                        "base_value": base_values.get(mk),
                        "overrides": c.get("overrides", {}),
                    }
                )
    out["tornado_rows"] = rows
    return out


def suite_to_tables(
    suite: Union[SensitivitySuite, MultiMetricSensitivitySuite],
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
    md = rec.get("metadata", {}) or {}
    tr = md.get("tail_risk", None)
    if isinstance(tr, list):
        tables["tail_risk"] = pd.DataFrame(tr)

    return tables
