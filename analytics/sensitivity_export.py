# analytics/sensitivity_export.py

"""
SensitivitySuite Export and Reporting Helpers (v14+)

- Clean tornado tables for Excel/CSV
- Breakeven table generator (tariff, capex, etc.)
- Multi-metric cross-table export for spider/radar support
"""

from typing import Optional, Sequence
import pandas as pd
from pathlib import Path
from analytics.contracts_v14 import (
    SensitivitySuite, BreakevenResult, MultiMetricSensitivitySuite
)

def tornado_suite_to_dataframe(suite: SensitivitySuite) -> pd.DataFrame:
    """DFI-compliant tornado table. One row per variable; sorted, chart-ready."""
    df = pd.DataFrame([{
        "Parameter": t.label,
        "Variable": t.variable,
        "Base Value": t.base_value,
        "Low Value": t.low_value,
        "High Value": t.high_value,
        "Base Metric": t.base_metric,
        "Low Metric": t.low_metric,
        "High Metric": t.high_metric,
        "Impact": t.impact_abs,
        "Direction": t.impact_dir
    } for t in suite.tornado_results])
    df = df.sort_values("Impact", ascending=False).reset_index(drop=True)
    return df

def breakeven_results_to_dataframe(results: Sequence[BreakevenResult]) -> pd.DataFrame:
    """Exports output of multiple breakeven runs to Excel/CSV."""
    return pd.DataFrame([{
        "Parameter": r.variable,
        "Breakeven Value": r.breakeven_value,
        "Bracket": f"[{r.bracket[0]:.4f}, {r.bracket[1]:.4f}]" if r.breakeven_value is not None else "",
        "Status": r.status
    } for r in results])

def multi_metric_suite_to_dataframe(suite: MultiMetricSensitivitySuite) -> pd.DataFrame:
    """Tabulates metrics for spider/radar input; rows are parameters, columns are metrics/impacts."""
    records = []
    for t in suite.tornado_results:
        rec = {
            "Parameter": t.label,
            "Variable": t.variable
        }
        rec.update({f"Impact_{m}": t.impacts[m] for m in suite.metrics})
        records.append(rec)
    return pd.DataFrame(records)

def export_tornado_table_csv(df: pd.DataFrame, path: Path) -> None:
    """Write tornado table to CSV."""
    df.to_csv(path, index=False)

def export_breakeven_table_csv(df: pd.DataFrame, path: Path) -> None:
    """Write breakeven table to CSV."""
    df.to_csv(path, index=False)

def export_multi_metric_table_csv(df: pd.DataFrame, path: Path) -> None:
    """Write cross-metric spider table to CSV."""
    df.to_csv(path, index=False)
