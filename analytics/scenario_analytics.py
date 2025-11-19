"""Batch scenario analytics orchestrator for v14 cashflow / debt / metrics.

This module:
  * scans a scenarios directory for YAML / JSON configs,
  * loads each config via the shared analytics.scenario_loader,
  * runs the v14 cashflow + debt stack,
  * computes KPIs via analytics.core.metrics,
  * aggregates everything into a summary DataFrame,
  * optionally exports Excel and charts.

It is intentionally light on business logic – the heavy lifting lives in:
  * dutchbay_v14chat.finance.cashflow
  * dutchbay_v14chat.finance.debt
  * analytics.core.metrics
  * analytics.export_helpers
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import sys
from pathlib import Path

# Ensure project root (parent of the 'analytics' package) is on sys.path
THIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = THIS_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import argparse
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


from analytics.core import metrics as metrics_mod
from analytics.export_helpers import ExcelExporter, ChartGenerator
from analytics.scenario_loader import load_scenario_config

from dutchbay_v14chat.finance.cashflow import build_annual_rows  # type: ignore
from dutchbay_v14chat.finance.debt import apply_debt_layer  # type: ignore

try:
    from analytics.export_helpers import ExcelExporter, ChartExporter  # type: ignore
except ImportError:  # pragma: no cover
    from analytics.export_helpers import ExcelExporter  # type: ignore
    ChartExporter = None  # type: ignore[assignment]

@dataclass
class ScenarioResult:
    """Container for per-scenario results."""

    name: str
    config_path: Path
    kpis: Dict[str, Any]
    annual_rows: List[Dict[str, Any]]
    debt_result: Dict[str, Any]


class ScenarioAnalytics:
    """V14-style orchestrator for batch scenario analysis."""

    def __init__(
        self,
        scenarios_dir: Path,
        output_path: Path,
        charts_dir: Optional[Path] = None,
    ) -> None:
        self.scenarios_dir = scenarios_dir
        self.output_path = output_path
        self.charts_dir = charts_dir or output_path.parent / "charts"

        self.results: List[ScenarioResult] = []
        self.failed: List[Tuple[str, str]] = []

    # ------------------------------------------------------------------
    # Core helpers
    # ------------------------------------------------------------------
    def load_config(self, path: Path) -> Dict[str, Any]:
        """Load and normalise a scenario config via the shared loader."""
        return load_scenario_config(str(path))

    def _iter_scenario_files(self) -> List[Path]:
        exts = {".yml", ".yaml", ".json"}
        files = [
            p
            for p in sorted(self.scenarios_dir.iterdir())
            if p.is_file() and p.suffix.lower() in exts
        ]
        return files
    def _summarise_dscr(raw_dscr: pd.Series) -> dict:
        """
        Clean and summarise DSCR values.

        - Treat +/-inf as NaN (e.g. years with zero debt service).
        - Drop NaNs before computing stats.
        - If nothing left, return None for all stats.
        """
        if not isinstance(raw_dscr, pd.Series):
            raw_dscr = pd.Series(raw_dscr)

        # Replace +/-inf with NaN
            dscr = raw_dscr.replace([np.inf, -np.inf], np.nan)

        # Drop NaNs (no debt service or missing)
        dscr = dscr.dropna()

        if dscr.empty:
            return {
                "min": None,
                "max": None,
                "mean": None,
                "median": None,
        }

        return {
        "min": float(dscr.min()),
        "max": float(dscr.max()),
        "mean": float(dscr.mean()),
        "median": float(dscr.median()),
    }

    # ------------------------------------------------------------------
    # Per-scenario processing
    # ------------------------------------------------------------------
    def process_scenario(self, config_path: Path) -> Optional[ScenarioResult]:
        """Run the full analytics chain for a single scenario."""
        scenario_name = config_path.stem
        print(f"Processing scenario: {scenario_name}")

        try:
            config = self.load_config(config_path)
            annual_rows = build_annual_rows(config)
            debt_result = apply_debt_layer(config, annual_rows)
            kpis = metrics_mod.calculate_scenario_kpis(
                annual_rows=annual_rows,
                debt_result=debt_result,
                config=config,
            )
        except Exception as exc:  # pragma: no cover (defensive)
            msg = f"{type(exc).__name__}: {exc}"
            print(f"ERROR processing {scenario_name}: {msg}")
            self.failed.append((scenario_name, msg))
            return None

        # Pretty console dump to wake up sleepy reviewers
        self._print_debt_summary(scenario_name, debt_result, kpis)
        self._print_kpi_summary(scenario_name, kpis)

        return ScenarioResult(
            name=scenario_name,
            config_path=config_path,
            kpis=kpis,
            annual_rows=annual_rows,
            debt_result=debt_result,
        )

    # ------------------------------------------------------------------
    # Batch orchestration
    # ------------------------------------------------------------------
    def run(
        self,
        export_excel: bool = True,
        export_charts: bool = True,
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Run analytics over all scenarios in the directory."""
        start = datetime.now()
        scenario_files = self._iter_scenario_files()
        if not scenario_files:
            raise SystemExit(f"No scenario files found in: {self.scenarios_dir}")

        print("=" * 60)
        print(f"Running batch analysis on {len(scenario_files)} scenario(s)")
        print("=" * 60)

        self.results.clear()
        self.failed.clear()

        all_rows: List[Dict[str, Any]] = []

        for path in scenario_files:
            result = self.process_scenario(path)
            if not result:
                continue
            self.results.append(result)

            for row in result.annual_rows:
                row_with_name = dict(row)
                row_with_name["scenario_name"] = result.name
                all_rows.append(row_with_name)

        if not self.results:
            raise SystemExit("All scenarios failed – nothing to report.")

        # Build summary + timeseries frames
        summary_records = []
        for r in self.results:
            record = dict(r.kpis)
            record["scenario_name"] = r.name
            summary_records.append(record)

        summary_df = pd.DataFrame(summary_records).set_index("scenario_name")
        timeseries_df = pd.DataFrame(all_rows)

        elapsed = (datetime.now() - start).total_seconds()
        print()
        print(f"Batch analysis complete in {elapsed:.2f}s")
        print(f"  Successful scenarios: {len(self.results)}")
        print(f"  Failed scenarios:     {len(self.failed)}")
        if self.failed:
            for name, msg in self.failed:
                print(f"    - {name}: {msg}")

        # Optional exports
        if export_excel or export_charts:
            self._export_outputs(summary_df, timeseries_df, export_excel, export_charts)

        return summary_df, timeseries_df

        # ------------------------------------------------------------------
    # Output helpers (Excel + charts)
    # ------------------------------------------------------------------
    def _export_outputs(
        self,
        summary_df,
        timeseries_df,
        export_excel: bool,
        export_charts: bool,
    ) -> None:
        """Write Excel + charts using export_helpers, with a safe fallback."""
        if summary_df is None:
            print("\nNo summary dataframe generated; skipping exports.")
            return

        # Excel export
        if export_excel:
            output_path = self.output_path  # <- use the existing attribute
            if output_path is None:
                print("No Excel output path provided; skipping Excel export.")
            else:
                try:
                    excel = ExcelExporter(output_path)
                except Exception as exc:  # pragma: no cover (defensive)
                    print(
                        f"WARNING: ExcelExporter init failed ({exc!r}); "
                        "falling back to bare pandas ExcelWriter."
                    )
                    excel = None

                if excel is not None and hasattr(
                    excel, "export_summary_and_timeseries"
                ):
                    excel.export_summary_and_timeseries(
                        summary_df=summary_df,
                        timeseries_df=timeseries_df,
                        scenario_results=self.scenario_results,
                    )
                else:
                    with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
                        summary_df.to_excel(
                            writer,
                            sheet_name="Summary",
                            index=False,
                        )
                        if timeseries_df is not None:
                            timeseries_df.to_excel(
                                writer,
                                sheet_name="Timeseries",
                                index=False,
                            )
                    print(
                        "ExcelExporter.export_summary_and_timeseries not found; "
                        "wrote basic Summary/Timeseries sheets via pandas."
                    )

                print(f"Excel workbook saved to: {output_path}")

               # 2) Charts (optional)
        chart_paths: List[Path] = []
        if export_charts and timeseries_df is not None:
            # Only attempt chart export if we have an exporter available
            if "ChartExporter" in globals() and ChartExporter is not None:  # type: ignore[name-defined]
                chart_paths = self._generate_charts(summary_df, timeseries_df)
            else:
                print(
                    "ChartExporter not found; skipping chart export. "
                    "Summary/Timeseries Excel has still been written."
                )
    def _generate_charts(
        self,
        summary_df: pd.DataFrame,
        timeseries_df: Optional[pd.DataFrame],
    ) -> List[Path]:
        """
        Generate charts for a scenario using ChartExporter, if available.

        Returns a list of output paths for the generated chart files.
        If ChartExporter is missing or timeseries_df is None, returns [].
        """
        if timeseries_df is None:
            return []

        if "ChartExporter" not in globals() or ChartExporter is None:  # type: ignore[name-defined]
            # Should not be hit if caller has already checked, but be defensive.
            print("ChartExporter unavailable inside _generate_charts; returning no charts.")
            return []

        exporter = ChartExporter(output_dir=self.output_dir)  # type: ignore[call-arg]
        try:
            # Adjust this to whatever API your ChartExporter actually exposes.
            return exporter.export_all(
                summary_df=summary_df,
                timeseries_df=timeseries_df,
            )
        except Exception as exc:  # pragma: no cover
            print(f"ERROR while generating charts: {exc!r}")
            return []

    def export_summary_and_timeseries(
        self,
        summary_df,
        timeseries_df,
        summary_sheet: str = "Summary",
        timeseries_sheet: str = "Timeseries",
        qc_df=None,
        qc_sheet: str = "QC",
        **_,
    ) -> None:
        """
        Back-compat shim for analytics.scenario_analytics.

        Writes summary and timeseries DataFrames to dedicated sheets and,
        if provided, a QC DataFrame to a third sheet.
        """
        # Summary sheet
        self.add_dataframe_sheet(
            summary_sheet,
            summary_df,
            freeze_header=True,
            format_headers=True,
            auto_filter=True,
        )

        # Timeseries sheet
        self.add_dataframe_sheet(
            timeseries_sheet,
            timeseries_df,
            freeze_header=True,
            format_headers=True,
            auto_filter=True,
        )

        # Optional QC / diagnostics sheet
        if qc_df is not None:
            self.add_dataframe_sheet(
                qc_sheet,
                qc_df,
                freeze_header=True,
                format_headers=True,
                auto_filter=True,
            )
    def export_summary_and_timeseries(
        self,
        summary_df: "pd.DataFrame",
        timeseries_df: "pd.DataFrame",
        output_path: Optional[Path] = None,
    ) -> None:
        """
        Convenience helper used by scenario_analytics to dump both tables.

        - Optionally overrides the export path for this call.
        - Writes a 'Summary' sheet if summary_df is non-empty.
        - Writes a 'Timeseries' sheet if timeseries_df is non-empty.
        - Calls save() at the end.

        Args:
            summary_df: Scenario-level KPIs (one row per scenario).
            timeseries_df: Year-by-year / period-by-period CFADS & debt profile.
            output_path: Optional path override for the XLSX file.
        """
        # Allow caller to override where this workbook will be written.
        if output_path is not None:
            self.output_path = Path(output_path)

        # Defensive: handle None and empty frames gracefully.
        if summary_df is not None and not summary_df.empty:
            self.add_dataframe_sheet(
                sheet_name="Summary",
                df=summary_df,
                freeze_panes="B2",
                format_headers=True,
                auto_filter=True,
            )

        if timeseries_df is not None and not timeseries_df.empty:
            self.add_dataframe_sheet(
                sheet_name="Timeseries",
                df=timeseries_df,
                freeze_panes="B2",
                format_headers=True,
                auto_filter=True,
            )

        # Persist to disk using the existing save() logic.
        self.save()

    # ------------------------------------------------------------------
    # Console pretty-printing helpers
    # ------------------------------------------------------------------
    def _print_debt_summary(
        self,
        scenario_name: str,
        debt_result: Dict[str, Any],
        kpis: Dict[str, Any],
    ) -> None:
        """Print v14-style debt planning summary."""
        years_construction = debt_result.get("construction_years")
        tenor_years = debt_result.get("tenor_years")

        print(
            f"V14 Debt Planning: {years_construction}-year construction, "
            f"{tenor_years}-year tenor"
        )

        def _fmt_m(v: Optional[float]) -> str:
            if v is None:
                return "n/a"
            try:
                return f"${v/1e6:,.2f}M"
            except Exception:
                return str(v)

        for bucket in ("lkr", "usd", "dfi"):
            principal = debt_result.get(f"{bucket}_principal")
            idc = debt_result.get(f"{bucket}_idc")
            label = bucket.upper()
            print(f"  {label}: Principal {_fmt_m(principal)} (IDC: {_fmt_m(idc)})")

        total_idc = debt_result.get("total_idc")
        min_dscr = kpis.get("dscr_min")
        if isinstance(min_dscr, (int, float)):
            min_dscr_str = f"{min_dscr:.2f}"
        else:
            min_dscr_str = "n/a"

        print(
            f"V14 Results: Min DSCR={min_dscr_str}, "
            f"Total IDC={_fmt_m(total_idc)}"
        )

    def _print_kpi_summary(self, scenario_name: str, kpis: Dict[str, Any]) -> None:
        """Print headline valuation + DSCR stats for a scenario."""
        npv = kpis.get("npv")
        irr = kpis.get("irr")
        dscr_min = kpis.get("dscr_min")
        dscr_max = kpis.get("dscr_max")
        dscr_mean = kpis.get("dscr_mean")
        dscr_median = kpis.get("dscr_median")
        total_cfads = kpis.get("total_cfads")
        final_cfads = kpis.get("final_cfads")
        mean_operational = kpis.get("mean_operational_cfads")
        max_debt = kpis.get("max_debt")
        final_debt = kpis.get("final_debt")
        total_idc = kpis.get("total_idc")

        def _fmt(v: Any) -> str:
            if v is None:
                return "n/a"
            if isinstance(v, float):
                return f"{v:,.2f}"
            return str(v)

        print("  Valuation:")
        print(f"    NPV:      {_fmt(npv)}")
        print(f"    IRR:      {_fmt(irr)}")
        print()
        print("  DSCR stats:")
        print(f"    Min:      {_fmt(dscr_min)}")
        print(f"    Max:      {_fmt(dscr_max)}")
        print(f"    Mean:     {_fmt(dscr_mean)}")
        print(f"    Median:   {_fmt(dscr_median)}")
        print()
        print("  CFADS / Debt:")
        print(f"    Total CFADS:          {_fmt(total_cfads)}")
        print(f"    Final year CFADS:     {_fmt(final_cfads)}")
        print(f"    Mean operational CFADS: {_fmt(mean_operational)}")
        print(f"    Max debt outstanding: {_fmt(max_debt)}")
        print(f"    Final debt balance:   {_fmt(final_debt)}")
        print(f"    Total IDC:            {_fmt(total_idc)}")
        print()


# ----------------------------------------------------------------------
# CLI entrypoint
# ----------------------------------------------------------------------
def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run batch v14 scenario analytics and export Excel/charts.",
    )
    parser.add_argument(
        "--dir",
        dest="scenarios_dir",
        required=True,
        help="Directory containing YAML/JSON scenario configs.",
    )
    parser.add_argument(
        "--output",
        dest="output_path",
        required=True,
        help="Path to Excel workbook to write (e.g. exports/summary.xlsx).",
    )
    parser.add_argument(
        "--no-excel",
        action="store_true",
        help="Skip Excel export (console-only run).",
    )
    parser.add_argument(
        "--no-charts",
        action="store_true",
        help="Skip PNG chart generation.",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    scenarios_dir = Path(args.scenarios_dir).expanduser().resolve()
    output_path = Path(args.output_path).expanduser().resolve()

    orchestrator = ScenarioAnalytics(
        scenarios_dir=scenarios_dir,
        output_path=output_path,
    )

    summary_df, _ = orchestrator.run(
        export_excel=not args.no_excel,
        export_charts=not args.no_charts,
    )

    # Small sanity print at the end so CI / humans see a compact snapshot.
    print("Final KPI summary (head):")
    with pd.option_context("display.max_columns", 20, "display.width", 140):
        print(summary_df.head())

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
