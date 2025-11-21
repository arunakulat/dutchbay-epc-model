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
    # Rich exports are optional – we degrade gracefully if absent.
    from analytics.export_helpers import ExcelExporter, ChartExporter
except Exception:  # pragma: no cover - optional dependency
    ExcelExporter = None
    ChartExporter = None

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
        strict: bool = True,
    ) -> None:
        self.scenarios_dir = Path(scenarios_dir)
        self.output_path = Path(output_path) if output_path is not None else None
        self.strict = bool(strict)

    # ------------------------------------------------------------------
    # Scenario discovery
    # ------------------------------------------------------------------
    def discover_scenarios(self) -> List[Path]:
        """Return a sorted list of scenario config paths under scenarios_dir."""
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
        """Derive a human-friendly scenario name from the config path."""
        return path.stem

    def load_config(self, config_path: Path) -> Dict[str, Any]:
        """Load a scenario config via the shared loader."""
        return load_scenario_config(str(config_path))

    def _run_single(
        self,
        config_path: Path,
    ) -> ScenarioResult:
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
        config = self.load_config(config_path)

        # Build annual cashflow rows
        annual_rows = build_annual_rows(config)

        # Apply debt layer
        debt_result = apply_debt_layer(config, annual_rows)

        # Compute KPIs
        kpis = metrics_mod.compute_kpis(
            config=config,
            annual_rows=annual_rows,
            debt_result=debt_result,
        )

        # Optionally enrich KPIs with EPC breakdown (non-fatal if this fails)
        try:
            epc_breakdown = epc_breakdown_from_config(config)
            kpis.update(epc_breakdown)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("EPC breakdown derivation failed for %s: %s", name, exc)

        return ScenarioResult(
            name=name,
            config_path=config_path,
            kpis=kpis,
            annual_rows=annual_rows,
            debt_result=debt_result,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(
        self,
        export_excel: bool = False,
        export_charts: bool = False,
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Run analytics across all scenarios in scenarios_dir.

        Returns:
          (summary_df, timeseries_df)
        """
        paths = self.discover_scenarios()
        if not paths:
            raise RuntimeError(f"No scenario configs found under {self.scenarios_dir}")

        results: List[ScenarioResult] = []
        failures: List[Tuple[Path, Exception]] = []

        for path in paths:
            try:
                result = self._run_single(path)
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
        """Build summary and timeseries DataFrames from results.

        Shapes the analytics outputs into the two canonical layers used by
        the executive report, and derives a per-period DSCR series when
        CFADS and debt-service columns are available.

        Fallback behaviour:
          * If no debt-service series is present but KPIs expose a dscr_min,
            we propagate that dscr_min as a flat 'dscr' line across periods
            for that scenario so that DSCR charts and exports remain usable.
        """
        summary_records: List[Dict[str, Any]] = []
        timeseries_records: List[Dict[str, Any]] = []

        for result in results:
            # One KPI row per scenario
            rec = dict(result.kpis)
            rec["scenario_name"] = result.name
            summary_records.append(rec)

            # Try to pick a DSCR scalar we can fall back to if needed
            dscr_scalar = None
            for key in ("dscr_min", "dscr", "min_dscr"):
                if key in rec:
                    dscr_scalar = rec[key]
                    break

            # One annual row per (scenario, period)
            for row in result.annual_rows:
                row_rec = dict(row)
                row_rec["scenario_name"] = result.name
                # If the annual rows don't already have a DSCR, attach the
                # scalar as a horizontal line – better than having no series
                # at all for charting/export.
                if "dscr" not in row_rec and dscr_scalar is not None:
                    row_rec["dscr"] = dscr_scalar
                timeseries_records.append(row_rec)

        # ------------------------------------------------------------------
        # Summary layer
        # ------------------------------------------------------------------
        summary_df = pd.DataFrame(summary_records).set_index("scenario_name")
        # Preserve scenario_name both as index (for existing callers) and as
        # an explicit column (for filters / exporters that expect it).
        if "scenario_name" not in summary_df.columns:
            summary_df = summary_df.copy()
            summary_df.insert(0, "scenario_name", summary_df.index)

        # ------------------------------------------------------------------
        # Timeseries layer + DSCR derivation
        # ------------------------------------------------------------------
        timeseries_df = pd.DataFrame(timeseries_records)

        # If we already have a dscr column (e.g. from the scalar fallback
        # above or from the underlying finance layer), we don't attempt to
        # derive it again.
        if "dscr" not in timeseries_df.columns:
            cols = list(timeseries_df.columns)

            # CFADS candidates
            cfads_candidates = [c for c in cols if "cfads" in c.lower()]

            # Prefer final / LKR / post-tax CFADS if present
            cfads_col: Optional[str] = None
            preferred_order = ("cfads_final_lkr", "cfads_final", "posttax_cfads")
            for pref in preferred_order:
                for c in cfads_candidates:
                    if pref in c.lower():
                        cfads_col = c
                        break
                if cfads_col:
                    break
            if cfads_col is None and cfads_candidates:
                cfads_col = cfads_candidates[0]

            # Debt-service candidates – progressively widen the net:
            #   1) '*debt_service*'
            #   2) 'debt' plus 'serv' or 'pay'
            #   3) any 'debt' column if still unique
            debt_candidates = [
                c
                for c in cols
                if "debt_serv" in c.lower() or "debt_service" in c.lower()
            ]
            if len(debt_candidates) != 1:
                debt_candidates = [
                    c
                    for c in cols
                    if "debt" in c.lower()
                    and ("serv" in c.lower() or "pay" in c.lower())
                ]
            if len(debt_candidates) != 1:
                debt_candidates = [c for c in cols if "debt" in c.lower()]

            if cfads_col is not None and len(debt_candidates) == 1:
                debt_col = debt_candidates[0]
                logger.info(
                    "Deriving per-period DSCR from %r / %r into 'dscr' column",
                    cfads_col,
                    debt_col,
                )
                timeseries_df = timeseries_df.copy()
                denom = timeseries_df[debt_col].replace({0: pd.NA})
                timeseries_df["dscr"] = timeseries_df[cfads_col] / denom
            else:
                logger.warning(
                    "Could not derive DSCR series: cfads_col=%r, cfads_candidates=%r, debt_candidates=%r",
                    cfads_col,
                    cfads_candidates,
                    debt_candidates,
                )

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
        exporter.export_summary_and_timeseries(
            summary_df=summary_df,
            timeseries_df=timeseries_df,
            summary_sheet="Summary",
            timeseries_sheet="Timeseries",
            add_board_views=True,
        )

    def _export_charts(
        self,
        summary_df: pd.DataFrame,
        timeseries_df: pd.DataFrame,
    ) -> None:
        """Export DSCR / IRR charts if ChartExporter is available."""
        if self.output_path is None:
            logger.warning("No output_path configured; skipping chart export")
            return

        if ChartExporter is None:
            logger.warning("ChartExporter not available; skipping chart export")
            return

        charts_dir = self.output_path.with_name(self.output_path.stem + "_charts")
        charts_dir.parent.mkdir(parents=True, exist_ok=True)

        chart_exporter = ChartExporter(output_dir=str(charts_dir))

        # Preferred API if present
        if hasattr(chart_exporter, "export_charts"):
            chart_exporter.export_charts(summary_df, timeseries_df)
            return

        # Fallback: call helpers individually if available
        if hasattr(chart_exporter, "export_dscr_chart"):
            chart_exporter.export_dscr_chart(timeseries_df)
        if hasattr(chart_exporter, "export_irr_histogram"):
            chart_exporter.export_irr_histogram(summary_df)


# ----------------------------------------------------------------------
# CLI entrypoint (optional, used for quick local smokes)
# ----------------------------------------------------------------------
def main(argv: Iterable[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Run v14 scenario analytics.")
    parser.add_argument(
        "--scenarios-dir",
        default="scenarios",
        help="Directory containing scenario YAML/JSON files.",
    )
    parser.add_argument(
        "--output",
        default="exports/v14_analytics.xlsx",
        help="Excel output path (for summary + timeseries).",
    )
    parser.add_argument(
        "--no-excel",
        action="store_true",
        help="Do not export Excel, only print logs.",
    )
    parser.add_argument(
        "--charts",
        action="store_true",
        help="Export charts alongside the Excel workbook.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        default=True,
        help="Raise on first scenario failure instead of continuing.",
    )

    args = parser.parse_args(list(argv))

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
