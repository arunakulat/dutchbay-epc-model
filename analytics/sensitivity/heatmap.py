# ruff: noqa: E402
from __future__ import annotations

"""
analytics.sensitivity.heatmap

Heatmap data preparation for sensitivity results.

Placeholder:
- Builds a rectangular table suitable for a heatmap
- No plotting; visualization is handled in viz.py (optional)

Expected input:
- MultiMetricSensitivitySuite (preferred) or SensitivitySuite

Output:
- dict with keys:
  - "index": list of parameter labels
  - "columns": list of metric keys
  - "values": 2D list (float) aligned to index/columns

The exact semantics depend on how you want to reduce cases (e.g. low/high deltas).
"""

from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

from analytics.contracts_v14 import SensitivitySuite, MultiMetricSensitivitySuite


def suite_to_heatmap_matrix(
    suite: Union[SensitivitySuite, MultiMetricSensitivitySuite],
    *,
    reduce: str = "delta_from_base",
) -> Dict[str, Any]:
    """
    Minimal heatmap matrix builder.

    reduce:
      - "delta_from_base": value - base_value per metric (default)
      - "value": raw value
    """
    if hasattr(suite, "tornado"):
        # single metric tornado: return a 1-column matrix
        t = getattr(suite, "tornado")
        metric = getattr(t, "metric_key", "metric")
        base = getattr(t, "base_value", None)
        cases = getattr(t, "cases", []) or []

        idx = [str(c.get("label", "")) for c in cases]
        vals: List[float] = []
        for c in cases:
            v = c.get("value", None)
            if v is None:
                vals.append(float("nan"))
                continue
            fv = float(v)
            if reduce == "delta_from_base" and base is not None:
                fv = fv - float(base)
            vals.append(fv)

        return {"index": idx, "columns": [metric], "values": [[v] for v in vals]}

    # Multi-metric: rows by parameter (or case label), cols by metric
    tornados = getattr(suite, "tornados", []) or []
    rows: List[Dict[str, float]] = []
    index: List[str] = []
    columns: List[str] = []

    # Build union of metric keys
    metric_set: set[str] = set()
    for t in tornados:
        metric_set.update(list(getattr(t, "metric_keys", []) or []))
    columns = sorted(metric_set)

    for t in tornados:
        param = getattr(t, "parameter", None)
        pname = getattr(param, "name", None) if param is not None else None
        base_values = dict(getattr(t, "base_values", {}) or {})
        cases = getattr(t, "cases", []) or []
        # Minimal: pick the "high" case if present, else first case
        chosen = None
        for c in cases:
            lbl = str(c.get("label", "")).lower()
            if "high" in lbl:
                chosen = c
                break
        if chosen is None and cases:
            chosen = cases[0]
        if chosen is None:
            continue

        values = chosen.get("values", {}) or {}
        row: Dict[str, float] = {}
        for m in columns:
            v = values.get(m, None)
            if v is None:
                row[m] = float("nan")
                continue
            fv = float(v)
            if reduce == "delta_from_base":
                bv = base_values.get(m, None)
                if bv is not None:
                    fv = fv - float(bv)
            row[m] = fv

        index.append(str(pname) if pname is not None else "parameter")
        rows.append(row)

    # Convert to 2D
    matrix: List[List[float]] = []
    for r in rows:
        matrix.append([float(r.get(m, float("nan"))) for m in columns])

    return {"index": index, "columns": columns, "values": matrix}
