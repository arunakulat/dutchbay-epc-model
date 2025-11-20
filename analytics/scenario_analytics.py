
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

import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd

from analytics.core import metrics as metrics_mod
from analytics.scenario_loader import load_scenario_config
from analytics.core.epc_helper import epc_breakdown_from_config
from dutchbay_v14chat.finance.cashflow import build_annual_rows
from dutchbay_v14chat.finance.debt import apply_debt_layer

try:
    from analytics.export_helpers import ExcelExporter, ChartExporter
except Exception:  # pragma: no cover - soft dependency for CLI use
    ExcelExporter = None  # type: ignore[assignment]
    ChartExporter = None  # type: ignore[assignment]


logger = logging.getLogger(__name__)


@dataclass
class ScenarioResult:
    """Container for per-scenario results."""

    name: str
    config_path: Path
    kpis: Dict[str, Any]
    annual_rows: List[Dict[str, Any]]
    debt_result: Dict[str, Any]


class ScenarioAnalytics:
    """V14-style orchestrator for batch scenario analytics.

    Responsibilities:
      * discover scenario definitions under a directory,
      * load each config via analytics.scenario_loader.load_scenario_config,
      * run v14 CFADS and debt layers,
      * compute KPIs via analytics.core.metrics,
      * (optionally) derive EPC breakdowns via analytics.core.epc_helper,
      * collate outputs into summary/timeseries DataFrames,
      * (optionally) hand off to ExcelExporter/ChartExporter.
    """

    def __init__(
        self,
        scenarios_dir: Path,
        output_path: Optional[Path] = None,
        strict: bool = False,
    ) -> None:
        self.scenarios_dir = Path(scenarios_dir)
        self.output_path = output_path
        self.strict = strict

    # ------------------------------------------------------------------
    # Config loading
    # ------------------------------------------------------------------
    def load_config(self, path: str) -> Dict[str, Any]:
        """Load a scenario config via the shared loader.

        This wraps analytics.scenario_loader.load_scenario_config so that:
          * All v14 analytics code goes through a single, validated entrypoint.
          * YAML/JSON handling, defaults, and basic schema checks are centralised.
          * Future changes to the config schema only need to be taught in one place.
        """
        return load_scenario_config(path)

    # ------------------------------------------------------------------
    # Scenario discovery
    # ------------------------------------------------------------------
    def discover_scenarios(self) -> List[Path]:
        """Return a sorted list of scenario files (YAML / JSON) under scenarios_dir."""
        if not self.scenarios_dir.exists():
            raise FileNotFoundError(f"Scenarios directory not found: {self.scenarios_dir}")

        candidates: List[Path] = []
        for ext in ("*.yaml", "*.yml", "*.json"):
            candidates.extend(self.scenarios_dir.glob(ext))

        return sorted(candidates)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _scenario_name_from_path(path: Path) -> str:
        """Derive a human-friendly scenario name from the file path."""
        return path.stem

    @staticmethod
    def _summarise_dscr(dscr_series: Iterable[float]) -> Dict[str, float]:
        """Return min / max / mean / median DSCR stats from a series-like input."""
        import math
        import statistics

        values = [float(v) for v in dscr_series if v is not None]
        if not values:
            return {
                "dscr_min": math.nan,
                "dscr_max": math.nan,
                "dscr_mean": math.nan,
                "dscr_median": math.nan,
            }

        return {
            "dscr_min": min(values),
            "dscr_max": max(values),
            "dscr_mean": statistics.fmean(values),
            "dscr_median": statistics.median(values),
        }

    # ------------------------------------------------------------------
    # Core per-scenario pipeline
    # ------------------------------------------------------------------
    def process_scenario(self, config_path: Path) -> ScenarioResult:
        """Run the full v14 pipeline for a single scenario.

        Steps:
          1. Load config via the shared loader.
          2. Build v14 annual cashflow rows (CFADS, revenue, etc.).
          3. Apply the v14 debt layer on top of CFADS.
          4. Compute scenario KPIs via analytics.core.metrics.
          5. Optionally derive EPC breakdown via analytics.core.epc_helper
             and merge it into the KPIs payload.
        """
        name = self._scenario_name_from_path(config_path)
        logger.info("Processing scenario: %s", name)

        # Load config
        config = self.load_config(str(config_path))

        # Cashflow: v14 annual rows
        annual_rows = build_annual_rows(config)

        # Debt: v14 layer
        debt_result = apply_debt_layer(config, annual_rows)

        # Optional: derive an EPC cost breakdown for reporting.
        # This uses the v14-compatible helper and is purely additive;
        # failures here must not break the main analytics pipeline.
        try:
            epc_breakdown = epc_breakdown_from_config(config)
        except Exception:
            epc_breakdown = {}

        # KPIs – this is where NPV/IRR/DSCR/CFADS stats are computed.
        kpis = metrics_mod.calculate_scenario_kpis(
            annual_rows=annual_rows,
            debt_result=debt_result,
            config=config,
        )

        # Enrich KPI payload with any EPC breakdown (if available).
        if epc_breakdown:
            kpis.update(epc_breakdown)

        return ScenarioResult(
            name=name,
            config_path=config_path,
            kpis=kpis,
            annual_rows=annual_rows,
            debt_result=debt_result,
        )

    # ------------------------------------------------------------------
    # Batch runner
    # ------------------------------------------------------------------
    def run(
        self,
        export_excel: bool = True,
        export_charts: bool = False,
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Run batch analytics over all discovered scenarios.

        Returns:
          (summary_df, timeseries_df)
        """
        scenario_files = self.discover_scenarios()
        if not scenario_files:
            raise RuntimeError(f"No scenario files found under {self.scenarios_dir}")

        results: List[ScenarioResult] = []
        failures: List[Tuple[Path, Exception]] = []

        logger.info("=" * 60)
        logger.info("Running batch analysis on %d scenario(s)", len(scenario_files))
        logger.info("=" * 60)

        for path in scenario_files:
            try:
                result = self.process_scenario(path)
                results.append(result)
            except Exception as exc:
                logger.error("ERROR processing %s: %s", path.name, exc)
                failures.append((path, exc))
                if self.strict:
                    raise

        if not results:
            raise RuntimeError("All scenarios failed; no results to summarise")

        summary_df, timeseries_df = self._build_dataframes(results)

        logger.info("Batch analysis complete")
        logger.info("  Successful scenarios: %d", len(results))
        logger.info("  Failed scenarios:     %d", len(failures))
        if failures:
            for path, exc in failures:
                logger.info("    - %s: %s", path.name, exc)

        if export_excel and self.output_path is not None:
            self._export_to_excel(summary_df, timeseries_df)

        if export_charts and self.output_path is not None:
            self._export_charts(summary_df, timeseries_df)

        return summary_df, timeseries_df

    # ------------------------------------------------------------------
    # DataFrame construction
    # ------------------------------------------------------------------
    def _build_dataframes(
        self,
        results: Sequence[ScenarioResult],
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Build summary and timeseries DataFrames from results."""
        summary_records: List[Dict[str, Any]] = []
        timeseries_records: List[Dict[str, Any]] = []

        for result in results:
            rec = dict(result.kpis)
            rec["scenario_name"] = result.name
            summary_records.append(rec)

            for row in result.annual_rows:
                row_rec = dict(row)
                row_rec["scenario_name"] = result.name
                timeseries_records.append(row_rec)

        summary_df = pd.DataFrame(summary_records).set_index("scenario_name")
        timeseries_df = pd.DataFrame(timeseries_records)

        return summary_df, timeseries_df

    # ------------------------------------------------------------------
    # Excel & chart export
    # ------------------------------------------------------------------
    def _export_to_excel(
        self,
        summary_df: pd.DataFrame,
        timeseries_df: pd.DataFrame,
    ) -> None:
        """Export summary + timeseries to Excel via ExcelExporter if available.

        Falls back to a basic pandas.ExcelWriter-based export if the richer helper
        is not present, so that the CLI remains usable in minimal installs.
        """
        if self.output_path is None:
            logger.warning("No output_path configured; skipping Excel export")
            return

        if ExcelExporter is None:
            logger.warning(
                "ExcelExporter not available; writing basic Excel workbook to %s",
                self.output_path,
            )
            with pd.ExcelWriter(self.output_path) as writer:
                summary_df.to_excel(writer, sheet_name="Summary")
                timeseries_df.to_excel(writer, sheet_name="Timeseries")
            return

        exporter = ExcelExporter(self.output_path)
        exporter.export_summary_and_timeseries(summary_df, timeseries_df)

    def _export_charts(
        self,
        summary_df: pd.DataFrame,
        timeseries_df: pd.DataFrame,
    ) -> None:
        """Export charts via ChartExporter if available."""
        if self.output_path is None:
            logger.warning("No output_path configured; skipping chart export")
            return

        if ChartExporter is None:
            logger.warning("ChartExporter not available; skipping chart export")
            return

        exporter = ChartExporter(self.output_path)
        exporter.export_charts(summary_df, timeseries_df)


# ----------------------------------------------------------------------
# CLI integration
# ----------------------------------------------------------------------
def _build_arg_parser() -> "argparse.ArgumentParser":
    import argparse

    parser = argparse.ArgumentParser(
        description="DutchBay v14 scenario analytics runner",
    )
    parser.add_argument(
        "--scenarios-dir",
        type=str,
        default="scenarios",
        help="Directory containing scenario YAML/JSON files",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="exports/scenario_analytics.xlsx",
        help="Path to Excel output file",
    )
    parser.add_argument(
        "--no-excel",
        action="store_true",
        help="Do not write Excel output",
    )
    parser.add_argument(
        "--charts",
        action="store_true",
        help="Export charts (requires ChartExporter)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail fast on first scenario error",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase logging verbosity (-v, -vv)",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse

    parser = _build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    # Logging setup
    level = logging.WARNING
    if args.verbose == 1:
        level = logging.INFO
    elif args.verbose >= 2:
        level = logging.DEBUG
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    scenarios_dir = Path(args.scenarios_dir)
    output_path = Path(args.output) if not args.no_excel else None

    sa = ScenarioAnalytics(
        scenarios_dir=scenarios_dir,
        output_path=output_path,
        strict=bool(args.strict),
    )

    summary_df, timeseries_df = sa.run(
        export_excel=not args.no_excel,
        export_charts=bool(args.charts),
    )

    logger.info("Summary head:\n%s", summary_df.head())
    logger.info("Timeseries head:\n%s", timeseries_df.head())

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main(sys.argv[1:]))