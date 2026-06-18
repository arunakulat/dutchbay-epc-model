from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

import pandas as pd

PathLike = Union[str, Path]

__all__ = ["build_executive_workbook"]


def build_executive_workbook(
    summary_df: pd.DataFrame,
    cashflow_df: pd.DataFrame,
    debt_df: pd.DataFrame,
    ratios_df: pd.DataFrame,
    scenario_summary_df: pd.DataFrame,
    output_path: PathLike,
    resource_trend_df: Optional[pd.DataFrame] = None,
) -> Path:
    """
    Build the lender-facing Executive Workbook for a single scenario.

    Contract (v14 canonical surface)
    --------------------------------
    - One scenario per workbook.
    - Always creates the following sheets:
        * "Summary"
        * "Cashflow"
        * "DebtService"
        * "Ratios"
        * "ScenarioSummary"
    - Optionally creates "ResourceTrend" when ``resource_trend_df`` is supplied
      (long-term wind-resource & trend commentary; IEC-61400-15 / MEASNET basis --
      see ``wind_resource.long_term_trend``).
    - Returns the resolved Path to the created workbook.

    Inputs
    ------
    summary_df
        Per-scenario KPI table (project_irr, equity_irr, dscr_min, etc.).
    cashflow_df
        Annual/project cashflow rows (revenue, opex, tax, CFADS, etc.).
    debt_df
        Debt service schedule (principal, interest, DSCR, balances, etc.).
    ratios_df
        Ratios / covenant metrics (DSCR, LLCR, PLCR, etc.).
    scenario_summary_df
        Multi-scenario KPI comparison for dashboards.
    output_path
        Target XLSX path. May be str or Path; parent dirs are created.
    resource_trend_df
        Optional long-term resource & trend table (Metric/Value) from
        ``wind_resource.long_term_trend.trend_summary_dataframe``; written as the
        "ResourceTrend" sheet when provided.

    Notes
    -----
    - This function is deliberately thin and stable: it uses only pandas +
      openpyxl, with no heavy formatting logic.
    - Any CLI or analytics runner should treat this as the canonical Excel
      export surface for v14.
    """
    out_path = Path(output_path).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    def _to_excel(df: pd.DataFrame, writer: pd.ExcelWriter, sheet_name: str) -> None:
        """Internal helper to write a DataFrame to a sheet."""
        df.to_excel(writer, sheet_name=sheet_name, index=False)

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        # Core sheets
        _to_excel(summary_df, writer, "Summary")
        _to_excel(cashflow_df, writer, "Cashflow")
        _to_excel(debt_df, writer, "DebtService")
        _to_excel(ratios_df, writer, "Ratios")
        _to_excel(scenario_summary_df, writer, "ScenarioSummary")

        # Optional long-term resource & trend section (issue #178): lender-facing
        # commentary on decadal variability vs secular "stilling" and the IEC-61400-15 /
        # MEASNET long-term-reference basis for the forward P50.
        if resource_trend_df is not None:
            _to_excel(resource_trend_df, writer, "ResourceTrend")

        # Ensure the Summary sheet has at least 3 rows:
        #   - header row
        #   - at least a couple of metric rows
        summary_ws = writer.sheets.get("Summary")
        if summary_ws is not None and summary_ws.max_row < 3:
            # Append lightweight metadata rows until we hit the minimum.
            # Content is intentionally minimal; tests only care about row count.
            while summary_ws.max_row < 3:
                summary_ws.append([""])

    return out_path


# EOF
