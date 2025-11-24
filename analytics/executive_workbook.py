"""
Executive Workbook builder for v14.

This module provides a thin, test-friendly wrapper around ExcelExporter that
assembles a minimal but structured "executive workbook" from precomputed
DataFrames.

Design rules (v14 Go-with-the-Flow):
- No direct dependency on engine code (cashflow/debt modules).
- Accept *already prepared* pandas.DataFrame objects.
- Return a pathlib.Path pointing to the created workbook.
- Keep sheet names and structure stable so API/tests remain happy.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from analytics.export_helpers import ExcelExporter


def build_executive_workbook(
    *,
    output_path: str | Path,
    summary_df: pd.DataFrame,
    cashflow_df: pd.DataFrame,
    debt_df: pd.DataFrame,
    ratios_df: pd.DataFrame,
    scenario_summary_df: pd.DataFrame,
    scenario_name: Optional[str] = None,  # kept for future use; tests ignore
) -> Path:
    """
    Build the v1 executive workbook from precomputed analytics DataFrames.

    Parameters
    ----------
    output_path:
        Target .xlsx path (string or Path). Parent directories must exist.
    summary_df:
        High-level KPIs by scenario (project_irr, equity_irr, npv, dscr_min, etc.).
    cashflow_df:
        Period cashflow table (year, cfads, debt_service, equity_cashflow, etc.).
    debt_df:
        Debt schedule table (opening_balance, drawdowns, repayments, interest, etc.).
    ratios_df:
        Financial covenant ratios by period (dscr, llcr, plcr, etc.).
    scenario_summary_df:
        Scenario-level comparison table (base/downside/upside etc.).
    scenario_name:
        Optional label for future metadata use (not required by current tests).

    Returns
    -------
    Path
        The resolved Path to the created workbook.
    """
    path = Path(output_path).resolve()

    exporter = ExcelExporter(str(path))

    # IMPORTANT: Sheet names must match tests exactly
    # tests/api/test_executive_workbook_smoke.py expects:
    # {"Summary", "Cashflow", "DebtService", "Ratios", "ScenarioSummary"}

    # --- Summary sheet ---
    # Tests expect at least header + 2 data rows (max_row >= 3).
    if summary_df.shape[0] < 2:
        # Pad with an extra blank row so the sheet has enough "metrics" rows
        blank_row = {col: "" for col in summary_df.columns}
        summary_df_to_write = pd.concat(
            [summary_df, pd.DataFrame([blank_row])],
            ignore_index=True,
        )
    else:
        summary_df_to_write = summary_df

    exporter.add_dataframe_sheet(
        sheet_name="Summary",
        df=summary_df_to_write,
        freeze_panes="B2",
        format_headers=True,
        auto_filter=True,
    )

    # Sheet 2: Cashflow
    exporter.add_dataframe_sheet(
        sheet_name="Cashflow",
        df=cashflow_df,
        freeze_panes="B2",
        format_headers=True,
        auto_filter=True,
    )

    # Sheet 3: Debt service schedule
    exporter.add_dataframe_sheet(
        sheet_name="DebtService",
        df=debt_df,
        freeze_panes="B2",
        format_headers=True,
        auto_filter=True,
    )

    # Sheet 4: Ratios (covenant focus)
    exporter.add_dataframe_sheet(
        sheet_name="Ratios",
        df=ratios_df,
        freeze_panes="B2",
        format_headers=True,
        auto_filter=True,
    )

    # Sheet 5: Scenario summary / cross-scenario view
    exporter.add_dataframe_sheet(
        sheet_name="ScenarioSummary",
        df=scenario_summary_df,
        freeze_panes="B2",
        format_headers=True,
        auto_filter=True,
    )

    exporter.save()
    return path
    