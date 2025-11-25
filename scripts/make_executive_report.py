#!/usr/bin/env python3
"""
make_executive_report.py

Thin wrapper around the v14 analytics layer to generate a
single-scenario executive Excel workbook plus PNG charts.

Default use (lender case):

    python make_executive_report.py

Explicit config:

    python make_executive_report.py \
        --config scenarios/dutchbay_lendercase_2025Q4.yaml

Options:
    --config / -c         Path to a single scenario config (YAML/JSON)
    --excel-output / -o   Target Excel file (defaults to exports/Executive_<stem>.xlsx)
    --allow-legacy-fx     Relax FX strictness (for old scalar fx configs)
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd

from analytics.scenario_analytics import ScenarioAnalytics
from analytics.export_helpers import ExcelExporter, ChartExporter
from analytics.kpi_normalizer import normalise_kpis_for_export

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a single-scenario executive Excel + charts from v14 analytics.",
    )

    parser.add_argument(
        "-c",
        "--config",
        default="scenarios/dutchbay_lendercase_2025Q4.yaml",
        help=(
            "Path to the scenario config (YAML/JSON). "
            "Default: scenarios/dutchbay_lendercase_2025Q4.yaml"
        ),
    )

    parser.add_argument(
        "-o",
        "--excel-output",
        dest="excel_output",
        default=None,
        help=(
            "Path to the executive Excel workbook. "
            "Default: exports/Executive_<config_stem>.xlsx"
        ),
    )

    parser.add_argument(
        "--charts-dir",
        dest="charts_dir",
        default=None,
        help=(
            "Directory for chart PNGs. "
            "Default: alongside the Excel file with '_charts' suffix."
        ),
    )

    # Default is strict FX; you can relax it explicitly.
    parser.add_argument(
        "--allow-legacy-fx",
        dest="strict_fx_config",
        action="store_false",
        help="Relax FX strictness to allow legacy scalar fx configs.",
    )
    parser.set_defaults(strict_fx_config=True)

    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Helper functions (modular, reusable)
# ---------------------------------------------------------------------------


def resolve_paths(args: argparse.Namespace) -> Tuple[Path, str, Path, Path, Path]:
    """Resolve config, scenario id, scenarios dir, Excel output and charts dir."""
    config_path = Path(args.config).expanduser().resolve()

    if not config_path.is_file():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    scenario_id = config_path.stem
    scenarios_dir = config_path.parent

    if args.excel_output:
        excel_output = Path(args.excel_output).expanduser().resolve()
    else:
        excel_output = Path("exports") / f"Executive_{scenario_id}.xlsx"
        excel_output = excel_output.resolve()

    if args.charts_dir:
        charts_dir = Path(args.charts_dir).expanduser().resolve()
    else:
        charts_dir = excel_output.with_name(excel_output.stem + "_charts")

    return config_path, scenario_id, scenarios_dir, excel_output, charts_dir


def run_analytics_for_dir(
    scenarios_dir: Path,
    strict_fx_config: bool,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Run the v14 analytics across all scenarios in a directory."""
    analytics = ScenarioAnalytics(
        scenarios_dir=str(scenarios_dir),
        output_path=None,  # Excel + charts controlled here
        strict=strict_fx_config,
    )
    return analytics.run()


def filter_for_scenario(
    summary_df: pd.DataFrame,
    timeseries_df: pd.DataFrame,
    scenario_id: str,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Filter analytics outputs to a single scenario, with safe fallbacks."""
    if "scenario_name" in summary_df.columns:
        filtered_summary = summary_df.loc[
            summary_df["scenario_name"] == scenario_id
        ].copy()
    else:
        logger.warning(
            "summary_df has no 'scenario_name' column; using full summary for export."
        )
        filtered_summary = summary_df

    if "scenario_name" in timeseries_df.columns:
        filtered_timeseries = timeseries_df.loc[
            timeseries_df["scenario_name"] == scenario_id
        ].copy()
    else:
        logger.warning(
            "timeseries_df has no 'scenario_name' column; using full timeseries for export."
        )
        filtered_timeseries = timeseries_df

    if filtered_summary.empty:
        logger.warning(
            "No rows found for scenario_name == '%s'; "
            "falling back to unfiltered summary.",
            scenario_id,
        )
        filtered_summary = summary_df

    if filtered_timeseries.empty:
        logger.warning(
            "No rows found for scenario_name == '%s'; "
            "falling back to unfiltered timeseries.",
            scenario_id,
        )
        filtered_timeseries = timeseries_df

    return filtered_summary, filtered_timeseries


def export_excel_report(
    excel_output: Path,
    summary_df: pd.DataFrame,
    timeseries_df: pd.DataFrame,
) -> None:
    """Write a board-pack-friendly Excel workbook to disk."""
    excel_output.parent.mkdir(parents=True, exist_ok=True)
    exporter = ExcelExporter(excel_output)
    exporter.export_summary_and_timeseries(
        summary_df=summary_df,
        timeseries_df=timeseries_df,
        summary_sheet="Summary",
        timeseries_sheet="Timeseries",
        add_board_views=True,
    )


def export_charts(
    charts_dir: Path,
    summary_df: pd.DataFrame,
    timeseries_df: pd.DataFrame,
) -> None:
    """Generate DSCR / IRR charts into a dedicated charts directory."""
    charts_dir.mkdir(parents=True, exist_ok=True)
    try:
        chart_exporter = ChartExporter(output_dir=str(charts_dir))

        # Preferred high-level API, if present
        if hasattr(chart_exporter, "export_charts"):
            chart_exporter.export_charts(summary_df, timeseries_df)
            return

        # Fallback: call low-level helpers individually
        chart_exporter.export_dscr_chart(timeseries_df)
        chart_exporter.export_irr_histogram(summary_df)
    except Exception as exc:  # belt-and-braces
        logger.warning("Chart export failed: %s", exc)


# ---------------------------------------------------------------------------
# Main entry point (wafer-thin wrapper)
# ---------------------------------------------------------------------------


def main(argv: Optional[list[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args(argv)

    try:
        (
            config_path,
            scenario_id,
            scenarios_dir,
            excel_output,
            charts_dir,
        ) = resolve_paths(args)
    except FileNotFoundError as exc:
        logger.error(str(exc))
        return 1

    print(f"Using config:      {config_path}")
    print(f"Scenarios dir:     {scenarios_dir}")
    print(f"Excel output:      {excel_output}")
    print(f"Chart output dir:  {charts_dir}")
    print(f"Strict FX config:  {args.strict_fx_config}")
    print("============================================================")
    print("Running batch analysis on scenario directory")
    print("============================================================")

    # 1) Run analytics across the scenarios dir
    summary_df, timeseries_df = run_analytics_for_dir(
        scenarios_dir=scenarios_dir,
        strict_fx_config=args.strict_fx_config,
    )

    # 2) Filter to the requested scenario
    filtered_summary, filtered_timeseries = filter_for_scenario(
        summary_df=summary_df,
        timeseries_df=timeseries_df,
        scenario_id=scenario_id,
    )

    # 3) Normalise KPIs and scenario_name for export
    filtered_summary, filtered_timeseries = normalise_kpis_for_export(
        filtered_summary,
        filtered_timeseries,
        scenario_id=scenario_id,
    )

    # 4) Generate Excel workbook
    export_excel_report(
        excel_output=excel_output,
        summary_df=filtered_summary,
        timeseries_df=filtered_timeseries,
    )

    # 5) Generate DSCR / IRR charts
    export_charts(
        charts_dir=charts_dir,
        summary_df=filtered_summary,
        timeseries_df=filtered_timeseries,
    )

    print("Executive report generated.")
    print(f"  Excel:  {excel_output}")
    print(f"  Charts: {charts_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
