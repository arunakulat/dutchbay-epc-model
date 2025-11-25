#!/usr/bin/env python3
"""Scenario Analytics Master Suite.

    Batch scenario processing, KPI calculation, and board-ready Excel reporting.

    Usage:
        python analytics/scenario_analytics.py --dir ./scenarios --output ./exports/report.xlsx
        """

import os
import sys
import glob
import json
import yaml
import argparse
from datetime import datetime
from typing import Dict, List, Any, Optional
import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dutchbay_v14chat.finance.cashflow import build_annual_rows_v14
from dutchbay_v14chat.finance.debt import apply_debt_layer
from analytics.core.metrics import calculate_scenario_kpis, format_kpi_summary
from analytics.export_helpers import ExcelExporter, ChartGenerator


class ScenarioAnalytics:
    """Main orchestrator for batch scenario analytics."""
    
    def __init__(
            self,
            scenarios_dir: str,
            output_path: str,
            discount_rate: float = 0.08,
            dscr_threshold: float = 1.25
        ):
            """
            Initialize scenario analytics suite.
            
            Args:
                scenarios_dir: Directory containing scenario YAML/JSON files
                output_path: Path for output Excel file
                discount_rate: Discount rate for NPV calculations
                dscr_threshold: DSCR threshold for QC checks
            """
            self.scenarios_dir = scenarios_dir
            self.output_path = output_path
            self.discount_rate = discount_rate
            self.dscr_threshold = dscr_threshold
            
            # Initialize results storage
            self.scenario_results = []
            self.scenario_timeseries = []
            self.failed_scenarios = []
            
            # Initialize exporters
            self.excel_exporter = ExcelExporter(output_path)
            self.chart_gen = ChartGenerator(output_dir=os.path.join(os.path.dirname(output_path), "charts"))
        
    def load_config(self, path: str) -> Dict[str, Any]:
            """Load scenario config from JSON or YAML file."""
            if path.endswith('.json'):
                with open(path, 'r') as f:
                    return json.load(f)
            elif path.endswith(('.yaml', '.yml')):
                with open(path, 'r') as f:
                    return yaml.safe_load(f)
            else:
                raise ValueError(f"Unsupported file extension: {path}")
        
    def get_scenario_files(self) -> List[str]:
            """Get all scenario config files from directory."""
            patterns = ['*.json', '*.yaml', '*.yml']
            files = []
            for pattern in patterns:
                files.extend(glob.glob(os.path.join(self.scenarios_dir, pattern)))
            return sorted(files)
        
    def process_scenario(self, scenario_path: str) -> Optional[Dict[str, Any]]:
            """Process a single scenario and return results."""
            scenario_name = os.path.splitext(os.path.basename(scenario_path))[0]
            
            try:
                print(f"Processing scenario: {scenario_name}")
                
                # Load config
                config = self.load_config(scenario_path)
                
                # Run finance engine
                annual_rows = build_annual_rows_v14(config)
                debt_result = apply_debt_layer(config, annual_rows)
                
                # Calculate KPIs
                kpis = calculate_scenario_kpis(
                    annual_rows=annual_rows,
                    debt_result=debt_result,
                    discount_rate=self.discount_rate
                )
                
                # Add scenario metadata
                result = {
                    "scenario": scenario_name,
                    "file": os.path.basename(scenario_path),
                    **kpis
                }
                
                # Store timeseries data
                dscr_series = debt_result.get("dscr_series", [])
                debt_series = debt_result.get("debt_outstanding", [])
                
                for i, row in enumerate(annual_rows):
                    ts_row = {
                        "scenario": scenario_name,
                        "year": row.get("year", i + 1),
                        "label": row.get("label", ""),
                        "revenue_usd": row.get("revenue_usd", 0.0),
                        "opex_usd": row.get("opex_usd", 0.0),
                        "cfads_usd": row.get("cfads_usd", 0.0),
                        "equity_fcf_usd": row.get("equity_fcf_usd", 0.0),
                        "dscr": dscr_series[i] if i < len(dscr_series) else None,
                        "debt_outstanding": debt_series[i] if i < len(debt_series) else None
                    }
                    self.scenario_timeseries.append(ts_row)
                
                print(format_kpi_summary(kpis, scenario_name))
                
                return result
                
            except Exception as e:
                print(f"ERROR processing {scenario_name}: {e}")
                self.failed_scenarios.append({
                    "scenario": scenario_name,
                    "error": str(e)
                })
                return None
        
    def run_batch_analysis(self) -> pd.DataFrame:
            """Run batch analysis on all scenarios."""
            scenario_files = self.get_scenario_files()
            
            if not scenario_files:
                print(f"No scenario files found in {self.scenarios_dir}")
                sys.exit(1)
            
            print(f"\n{'='*60}")
            print(f"Running batch analysis on {len(scenario_files)} scenarios")
            print(f"{'='*60}\n")
            
            for scenario_file in scenario_files:
                result = self.process_scenario(scenario_file)
                if result:
                    self.scenario_results.append(result)
            
            print(f"\n{'='*60}")
            print(f"Batch analysis complete: {len(self.scenario_results)} succeeded, {len(self.failed_scenarios)} failed")
            print(f"{'='*60}\n")
            
            return pd.DataFrame(self.scenario_results)
        
    def run_qc_checks(self, summary_df: pd.DataFrame) -> None:
            """Run QC checks and print diagnostics."""
            print(f"\n{'='*60}")
            print("QC DIAGNOSTICS")
            print(f"{'='*60}\n")
            
            # Check for DSCR violations
            if 'dscr_min' in summary_df.columns:
                violations = summary_df[summary_df['dscr_min'] < self.dscr_threshold]
                if not violations.empty:
                    print(f"⚠️  DSCR Violations (< {self.dscr_threshold}):")
                    for _, row in violations.iterrows():
                        print(f"  - {row['scenario']}: Min DSCR = {row['dscr_min']:.2f}")
                else:
                    print(f"✓ All scenarios meet DSCR threshold of {self.dscr_threshold}")
            
            # Check for negative final CFADS
            if 'final_cfads' in summary_df.columns:
                neg_cfads = summary_df[summary_df['final_cfads'] < 0]
                if not neg_cfads.empty:
                    print(f"\n⚠️  Negative Final Year CFADS:")
                    for _, row in neg_cfads.iterrows():
                        print(f"  - {row['scenario']}: Final CFADS = ${row['final_cfads']:,.0f}")
                else:
                    print(f"\n✓ All scenarios have positive final year CFADS")
            
            # Check for failed IRR calculations
            if 'irr' in summary_df.columns:
                failed_irr = summary_df[summary_df['irr'].isna()]
                if not failed_irr.empty:
                    print(f"\n⚠️  IRR Calculation Failed:")
                    for _, row in failed_irr.iterrows():
                        print(f"  - {row['scenario']}")
            
            # Report failed scenarios
            if self.failed_scenarios:
                print(f"\n⚠️  Failed Scenarios ({len(self.failed_scenarios)}):")
                for failed in self.failed_scenarios:
                    print(f"  - {failed['scenario']}: {failed['error']}")
            
            print(f"\n{'='*60}\n")
        
    def generate_charts(self, summary_df: pd.DataFrame, timeseries_df: pd.DataFrame) -> Dict[str, str]:
        """Generate all charts and return paths."""
        chart_paths = {}

        print("Generating charts...")

        # DSCR comparison chart
        dscr_data = {}
        for scenario in summary_df['scenario']:
            scenario_ts = timeseries_df[timeseries_df['scenario'] == scenario]
            dscr_series = scenario_ts['dscr'].dropna().tolist()
            if dscr_series:
                dscr_data[scenario] = dscr_series

        if dscr_data:
            chart_paths['dscr'] = self.chart_gen.plot_dscr_comparison(
                dscr_data,
                threshold=self.dscr_threshold
            )

        # Debt waterfall chart
        debt_data = {}
        for scenario in summary_df['scenario']:
            scenario_ts = timeseries_df[timeseries_df['scenario'] == scenario]
            debt_series = scenario_ts['debt_outstanding'].dropna().tolist()
            if debt_series:
                debt_data[scenario] = debt_series

        if debt_data:
            chart_paths['debt'] = self.chart_gen.plot_debt_waterfall(debt_data)

        # NPV comparison
        if 'npv' in summary_df.columns and not summary_df['npv'].isna().all():
            chart_paths['npv'] = self.chart_gen.plot_kpi_comparison(
                summary_df[['scenario', 'npv']].dropna(),
                'npv',
                'npv_comparison.png'
            )

        # IRR comparison
        if 'irr' in summary_df.columns and not summary_df['irr'].isna().all():
            # Convert IRR to percentage for display
            irr_df = summary_df[['scenario', 'irr']].dropna().copy()
            irr_df['irr_pct'] = irr_df['irr'] * 100
            chart_paths['irr'] = self.chart_gen.plot_kpi_comparison(
                irr_df[['scenario', 'irr_pct']],
                'irr_pct',
                'irr_comparison.png'
            )

        return chart_paths


        
    def export_excel(self, summary_df: pd.DataFrame, timeseries_df: pd.DataFrame, chart_paths: Dict[str, str]) -> None:
            """Export all results to Excel workbook."""
            print(f"\nExporting to Excel: {self.output_path}")
            
            # Sheet 1: Summary
            self.excel_exporter.add_dataframe_sheet(
                "Summary",
                summary_df,
                freeze_panes="B2",
                format_headers=True,
                auto_filter=True
            )
            
            # Add conditional formatting for DSCR
            if 'dscr_min' in summary_df.columns:
                last_row = len(summary_df) + 1
                dscr_col = summary_df.columns.get_loc('dscr_min') + 1
                col_letter = chr(64 + dscr_col)  # Convert to Excel column letter
                self.excel_exporter.add_conditional_formatting(
                    "Summary",
                    f"{col_letter}2:{col_letter}{last_row}",
                    rule_type="lessThan",
                    threshold=self.dscr_threshold,
                    format_color="F8696B"
                )
            
            # Sheet 2: Timeseries (Long format)
            self.excel_exporter.add_dataframe_sheet(
                "Timeseries_Long",
                timeseries_df,
                freeze_panes="B2",
                format_headers=True,
                auto_filter=True
            )
            
            # Sheet 3: Wide format (pivot-ready)
            wide_df = self.create_wide_format(timeseries_df)
            if wide_df is not None:
                self.excel_exporter.add_dataframe_sheet(
                    "Wide_Format",
                    wide_df,
                    freeze_panes="B2",
                    format_headers=True,
                    auto_filter=True
                )
            
            # Sheet 4: Charts
            if chart_paths:
                self.excel_exporter.wb.create_sheet("Charts")
                row_offset = 2
                for chart_name, chart_path in chart_paths.items():
                    if os.path.exists(chart_path):
                        self.excel_exporter.add_chart_image(
                            "Charts",
                            chart_path,
                            f"B{row_offset}"
                        )
                        row_offset += 35  # Space between charts
            
            # Save workbook
            self.excel_exporter.save()
        
    def create_wide_format(self, timeseries_df: pd.DataFrame) -> Optional[pd.DataFrame]:
        """Create wide format DataFrame for pivot analysis."""
        if timeseries_df.empty:
            return None
        
        scenarios = timeseries_df['scenario'].unique()
        max_years = timeseries_df.groupby('scenario')['year'].max().max()
        
        wide_rows = []
        for scenario in scenarios:
            scenario_data = timeseries_df[timeseries_df['scenario'] == scenario].sort_values('year')
            row = {"scenario": scenario}
            
            # Add CFADS columns
            for i, cfads in enumerate(scenario_data['cfads_usd'].tolist(), 1):
                row[f"cfads_y{i}"] = cfads
            
            # Add DSCR columns
            for i, dscr in enumerate(scenario_data['dscr'].tolist(), 1):
                row[f"dscr_y{i}"] = dscr
            
            # Add Debt columns
            for i, debt in enumerate(scenario_data['debt_outstanding'].tolist(), 1):
                row[f"debt_y{i}"] = debt
            
            wide_rows.append(row)
        
        return pd.DataFrame(wide_rows)
        
    def export_csv_backups(self, summary_df: pd.DataFrame, timeseries_df: pd.DataFrame) -> None:
            """Export CSV backups."""
            output_dir = os.path.dirname(self.output_path)
            
            summary_csv = os.path.join(output_dir, "scenario_summary.csv")
            summary_df.to_csv(summary_csv, index=False)
            print(f"Summary CSV saved to: {summary_csv}")
            
            timeseries_csv = os.path.join(output_dir, "scenario_timeseries.csv")
            timeseries_df.to_csv(timeseries_csv, index=False)
            print(f"Timeseries CSV saved to: {timeseries_csv}")
        
    def run(self, generate_charts: bool = True, export_csv: bool = True) -> None:
            """Run complete analytics pipeline."""
            start_time = datetime.now()
            
            # Run batch analysis
            summary_df = self.run_batch_analysis()
            
            if summary_df.empty:
                print("No scenarios processed successfully. Exiting.")
                sys.exit(1)
            
            # Convert to DataFrame
            timeseries_df = pd.DataFrame(self.scenario_timeseries)
            
            # Run QC checks
            self.run_qc_checks(summary_df)
            
            # Generate charts
            chart_paths = {}
            if generate_charts:
                chart_paths = self.generate_charts(summary_df, timeseries_df)
            
            # Export to Excel
            self.export_excel(summary_df, timeseries_df, chart_paths)
            
            # Export CSV backups
            if export_csv:
                self.export_csv_backups(summary_df, timeseries_df)
            
            # Summary
            elapsed = (datetime.now() - start_time).total_seconds()
            print(f"\n{'='*60}")
            print(f"Analytics pipeline complete in {elapsed:.1f}s")
            print(f"  Scenarios processed: {len(self.scenario_results)}")
            print(f"  Excel report: {self.output_path}")
            print(f"  Charts generated: {len(chart_paths)}")
            print(f"{'='*60}\n")




def main():
    parser = argparse.ArgumentParser(
        description="DutchBay Analytics Master Suite - Batch scenario processing and reporting",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python analytics/scenario_analytics.py --dir ./scenarios --output ./exports/report.xlsx\n"
            "  python analytics/scenario_analytics.py --dir ./scenarios --output ./exports/report.xlsx --discount 0.10 --dscr 1.30\n"
            "  python analytics/scenario_analytics.py --dir ./scenarios --output ./exports/report.xlsx --no-charts --no-csv\n"
        ),
    )

    parser.add_argument(
        "--dir", "-d",
        required=True,
        help="Directory containing scenario YAML/JSON files",
    )
    parser.add_argument(
        "--output", "-o",
        required=True,
        help="Path to Excel report output file",
    )
    parser.add_argument(
        "--discount",
        type=float,
        default=0.08,
        help="Discount rate for NPV calculations (default: 0.08)",
    )
    parser.add_argument(
        "--dscr",
        type=float,
        default=1.25,
        help="DSCR threshold for highlighting (default: 1.25)",
    )
    parser.add_argument(
        "--no-charts",
        action="store_true",
        help="Disable chart generation",
    )
    parser.add_argument(
        "--no-csv",
        action="store_true",
        help="Disable CSV exports",
    )

    args = parser.parse_args()

    # Ensure output directory exists
    output_dir = os.path.dirname(args.output)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    analytics = ScenarioAnalytics(
        scenarios_dir=args.dir,
        output_path=args.output,
        discount_rate=args.discount,
        dscr_threshold=args.dscr,
    )

    analytics.run(
        generate_charts=not args.no_charts,
        export_csv=not args.no_csv,
    )


if __name__ == "__main__":
    main()