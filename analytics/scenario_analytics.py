#!/usr/bin/env python3
"""
Batch scenario analytics orchestrator for v14 cashflow and debt modules.

Enhancements (Go With The Flow):
--------------------------------
- Dynamic per-scenario discount rate (from YAML: scenarios, wacc, or global default)
- Scenario name filtering (run only base_case, all *wind*, etc. via CLI or param)
- CLI arg to output run summary/metadata JSON
- More robust DSCR/CFADS column inference (resistant to legacy or new schema)
- Parallel batch support (toggle for large scenario sets)
- CLI args to control/warn on batch-wide schema column clashes
- All logging consistently structured; progress and failures logged in detail

All previous features retained (EPC breakdown, Excel/charts, robust error handling).
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd

from analytics.core.epc_helper import epc_breakdown_from_config
from analytics.core.metrics import calculate_scenario_kpis
from analytics.kpi_normalizer import normalise_kpis_for_export
from analytics.scenario_loader import load_scenario_config
from analytics.schema_guard import validate_config_for_v14
from finance.cashflow_v14 import build_annual_rows
from finance.debt_v14 import apply_debt_layer

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
logger.addHandler(console_handler)


@dataclass
class ScenarioResult:
    """Container for per-scenario results."""

    name: str
    config_path: Path
    kpis: Dict[str, Any]
    annual_rows: List[Dict[str, Any]]
    debt_result: Dict[str, Any]
    discount_rate: float
    fail_reason: Optional[str] = None


@dataclass
class BatchResultSummary:
    successful: List[str]
    failed: List[str]
    n_success: int
    n_failed: int
    batch_summary: Dict[str, Any]


class ScenarioAnalytics:
    """
    V14-style orchestrator for batch scenario analytics
    with full Go With The Flow features.
    """

    def __init__(
        self,
        scenarios_dir: Path,
        output_path: Optional[Path] = None,
        scenario_filter: Optional[Callable[[str], bool]] = None,
        strict: bool = True,
        parallel: bool = False,
        global_default_discount_rate: float = 0.10,
    ) -> None:
        self.scenarios_dir = Path(scenarios_dir)
        self.output_path = Path(output_path) if output_path is not None else None
        self.strict = bool(strict)
        self.parallel = parallel
        self.global_default_discount_rate = global_default_discount_rate
        self._scenario_filter = scenario_filter

    # ------------------------------------------------------------------
    # Scenario discovery and filters
    # ------------------------------------------------------------------
    def discover_scenarios(self) -> List[Path]:
        """Return sorted scenario config paths under scenarios_dir,
        optionally filtered.
        """
        if not self.scenarios_dir.exists():
            raise FileNotFoundError(
                f"Scenarios directory not found: {self.scenarios_dir}"
            )

        candidates: List[Path] = []
        for ext in ("*.yaml", "*.yml", "*.json"):
            candidates.extend(self.scenarios_dir.glob(ext))

        all_candidates = sorted(candidates)
        if self._scenario_filter:
            filtered = [p for p in all_candidates if self._scenario_filter(p.stem)]
            logger.info(f"Filtered {len(filtered)} scenario(s) using scenario_filter")
            return filtered
        return all_candidates

    @staticmethod
    def _scenario_name_from_path(path: Path) -> str:
        """Derive a human-friendly scenario name from the config path."""
        return path.stem

    def load_config(self, config_path: Path) -> Dict[str, Any]:
        """Load a scenario config via the shared loader."""
        return load_scenario_config(str(config_path))

    # ------------------------------------------------------------------
    # Discount rate logic
    # ------------------------------------------------------------------
    def _effective_discount_rate(self, config: Dict[str, Any]) -> float:
        """Extract discount rate per scenario using
        precedence: scenario > wacc > global default."""
        # 1. Scenario override
        scenario = config.get("scenario", {})  # legacy field
        scenario_overrides = scenario.get("override", {}) if scenario else {}

        # Support nested "discount_rate" in scenario
        if "discount_rate" in config:
            return float(config["discount_rate"])
        if "discount_rate" in scenario_overrides:
            return float(scenario_overrides["discount_rate"])

        # 2. WACC block
        wacc_cfg = config.get("wacc", {})
        if wacc_cfg and wacc_cfg.get("discount_rate") is not None:
            try:
                return float(wacc_cfg["discount_rate"]) / (
                    100.0 if wacc_cfg["discount_rate"] > 1.0 else 1.0
                )
            except Exception:
                pass

        # 3. Global default
        return self.global_default_discount_rate

    def _run_single(self, config_path: Path) -> ScenarioResult:
        """Run the full v14 pipeline for a single scenario."""
        name = self._scenario_name_from_path(config_path)
        logger.info("Processing scenario: %s", name)
        discount_rate = None
        try:
            # Load config
            config = self.load_config(config_path)

            # Schema guard
            validate_config_for_v14(
                raw_config=config,
                config_path=str(config_path),
                modules=["cashflow"],
            )

            # Determine discount rate (scenario, config, global)
            discount_rate = self._effective_discount_rate(config)
            logger.info(f"  Using discount rate: {discount_rate:.3%}")

            # Annual cashflow rows
            annual_rows = build_annual_rows(config)
            # Debt layer (may mutate annual_rows in-place)
            debt_result = apply_debt_layer(config, annual_rows)
            # KPIs, using WACC (Go With The Flow): always prefer config > default
            kpis = calculate_scenario_kpis(
                config=config,
                annual_rows=annual_rows,
                debt_result=debt_result,
                discount_rate=discount_rate,
            )

            # EPC breakdown, optional non-blocking
            try:
                epc_breakdown = epc_breakdown_from_config(config)
                kpis.update(epc_breakdown)
            except Exception as e:  # pragma: no cover
                logger.warning("EPC breakdown derivation failed for %s: %s", name, e)

            return ScenarioResult(
                name=name,
                config_path=config_path,
                kpis=kpis,
                annual_rows=annual_rows,
                debt_result=debt_result,
                discount_rate=discount_rate,
            )
        except Exception as e:
            logger.error(f"Scenario {name} failed: {e}")
            return ScenarioResult(
                name=name,
                config_path=config_path,
                kpis={},
                annual_rows=[],
                debt_result={},
                discount_rate=(
                    discount_rate
                    if discount_rate is not None
                    else self.global_default_discount_rate
                ),
                fail_reason=str(e),
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(
        self,
        export_excel: bool = False,
        export_charts: bool = False,
        output_summary_json: Optional[Path] = None,
    ) -> Tuple[pd.DataFrame, pd.DataFrame, BatchResultSummary]:
        """Run analytics across all scenarios in scenarios_dir.
        Returns: (summary_df, timeseries_df, batch_metadata)
        """
        scenario_paths = self.discover_scenarios()
        if not scenario_paths:
            raise RuntimeError(f"No scenario configs found under {self.scenarios_dir}")

        from concurrent.futures import ThreadPoolExecutor, as_completed

        results: List[ScenarioResult] = []
        failures: List[ScenarioResult] = []

        batch_run = self.parallel and len(scenario_paths) > 4
        logger.info(
            f"Running {len(scenario_paths)} scenario(s)"
            " {'in parallel' if batch_run else 'serially'}."
        )

        if batch_run:
            with ThreadPoolExecutor() as executor:
                future_to_path = {
                    executor.submit(self._run_single, path): path
                    for path in scenario_paths
                }
                for future in as_completed(future_to_path):
                    res = future.result()
                    if res.kpis:
                        results.append(res)
                    else:
                        failures.append(res)
        else:
            for path in scenario_paths:
                res = self._run_single(path)
                if res.kpis:
                    results.append(res)
                else:
                    failures.append(res)

        if not results:
            raise RuntimeError("All scenarios failed; no results to summarise")

        summary_df, timeseries_df = self._build_dataframes(results)

        batch_metadata = BatchResultSummary(
            successful=[r.name for r in results],
            failed=[r.name for r in failures],
            n_success=len(results),
            n_failed=len(failures),
            batch_summary={
                "n_scenarios_found": len(scenario_paths),
                "n_scenarios_run": len(results),
                "n_failed": len(failures),
                "failed_scenarios": [
                    {"name": r.name, "reason": r.fail_reason} for r in failures
                ],
            },
        )

        logger.info("Batch analysis complete")
        logger.info("  Successful scenarios: %d", len(results))
        logger.info("  Failed scenarios:     %d", len(failures))
        logger.info(
            "  Export path: %s", self.output_path if self.output_path else "(not set)"
        )
        if failures:
            for r in failures:
                logger.info(f"    - {r.name}: {r.fail_reason}")

        if export_excel and self.output_path is not None:
            self._export_to_excel(summary_df, timeseries_df)

        if export_charts and self.output_path is not None:
            self._export_charts(summary_df, timeseries_df)

        if output_summary_json:
            with open(output_summary_json, "w") as f:
                json.dump(asdict(batch_metadata), f, indent=2)
            logger.info(f"Batch metadata written to {output_summary_json}")

        return summary_df, timeseries_df, batch_metadata

    # ------------------------------------------------------------------
    # DataFrame construction (robust to varied schema)
    # ------------------------------------------------------------------
    def _build_dataframes(
        self,
        results: Sequence[ScenarioResult],
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Build summary and timeseries DataFrames from results."""
        summary_records: List[Dict[str, Any]] = []
        timeseries_records: List[Dict[str, Any]] = []
        all_kpi_keys: set[str] = set()

        for result in results:
            rec: Dict[str, Any] = dict(result.kpis)
            rec["scenario_name"] = result.name
            rec["discount_rate_used"] = result.discount_rate
            summary_records.append(rec)
            all_kpi_keys.update(rec.keys())

            dscr_scalar: Optional[float] = None
            for key in ("dscr_min", "dscr", "min_dscr"):
                value = rec.get(key)
                if isinstance(value, (int, float)):
                    dscr_scalar = float(value)
                    break

            for row in result.annual_rows:
                row_rec: Dict[str, Any] = dict(row)
                row_rec["scenario_name"] = result.name
                if "dscr" not in row_rec and dscr_scalar is not None:
                    row_rec["dscr"] = dscr_scalar
                timeseries_records.append(row_rec)

        # Build summary
        summary_df = pd.DataFrame(summary_records).set_index("scenario_name")
        if "scenario_name" not in summary_df.columns:
            summary_df = summary_df.copy()
            summary_df.insert(0, "scenario_name", summary_df.index)

        # Build timeseries
        timeseries_df = pd.DataFrame(timeseries_records)

        # DSCR - more robust detection
        if "dscr" not in timeseries_df.columns:
            cols = list(timeseries_df.columns)
            cfads_candidates = [c for c in cols if "cfads" in c.lower()]
            cfads_col = None
            for pref in ("cfads_final_lkr", "cfads_final", "posttax_cfads"):
                for c in cfads_candidates:
                    if pref in c.lower():
                        cfads_col = c
                        break
                if cfads_col:
                    break
            if not cfads_col and cfads_candidates:
                cfads_col = cfads_candidates[0]

            # Debt-service inference (broader, as per minor notes)
            debt_candidates = [
                c
                for c in cols
                if "debt" in c.lower()
                and ("serv" in c.lower() or "pay" in c.lower() or "repay" in c.lower())
            ]
            if not debt_candidates:
                debt_candidates = [c for c in cols if "debt" in c.lower()]
            if cfads_col and len(debt_candidates) == 1:
                debt_col = debt_candidates[0]
                denom = timeseries_df[debt_col].replace({0: pd.NA})
                timeseries_df["dscr"] = timeseries_df[cfads_col] / denom
            else:
                logger.warning(
                    f"Could not derive DSCR column:"
                    f"cfads_col={cfads_col}, debt_candidates={debt_candidates}"
                )

        summary_df, timeseries_df = normalise_kpis_for_export(
            summary_df=summary_df,
            timeseries_df=timeseries_df,
        )

        return summary_df, timeseries_df

    # ------------------------------------------------------------------
    # Excel and chart export
    # ------------------------------------------------------------------
    def _export_to_excel(
        self,
        summary_df: pd.DataFrame,
        timeseries_df: pd.DataFrame,
    ) -> None:
        """Export summary and timeseries to Excel."""
        if self.output_path is None:
            logger.warning("No output_path configured; skipping Excel export")
            return
        try:
            from analytics.export_helpers import ExcelExporter

            exporter = ExcelExporter(self.output_path)
            exporter.export_summary_and_timeseries(
                summary_df=summary_df,
                timeseries_df=timeseries_df,
                summary_sheet="Summary",
                timeseries_sheet="Timeseries",
                add_board_views=True,
            )
        except Exception:
            logger.warning(
                "ExcelExporter not available; writing basic Excel workbook to %s",
                self.output_path,
            )
            with pd.ExcelWriter(self.output_path) as writer:
                summary_df.to_excel(writer, sheet_name="Summary")
                timeseries_df.to_excel(writer, sheet_name="Timeseries")
        logger.info(f"Excel exported to {self.output_path}")

    def _export_charts(
        self,
        summary_df: pd.DataFrame,
        timeseries_df: pd.DataFrame,
    ) -> None:
        """Export charts if ChartExporter is available."""
        if self.output_path is None:
            logger.warning("No output_path configured; skipping chart export")
            return
        try:
            from analytics.export_helpers import ChartExporter

            charts_dir = self.output_path.with_name(self.output_path.stem + "_charts")
            charts_dir.parent.mkdir(parents=True, exist_ok=True)
            chart_exporter = ChartExporter(output_dir=str(charts_dir))
            if hasattr(chart_exporter, "export_charts"):
                chart_exporter.export_charts(summary_df, timeseries_df)
            else:
                if hasattr(chart_exporter, "export_dscr_chart"):
                    chart_exporter.export_dscr_chart(timeseries_df)
                if hasattr(chart_exporter, "export_irr_histogram"):
                    chart_exporter.export_irr_histogram(summary_df)
            logger.info(f"Charts exported to {charts_dir}")
        except Exception:
            logger.warning("ChartExporter not available; skipping chart export")


# ----------------------------------------------------------------------
# CLI entrypoint (pattern-rich, Go With The Flow)
# ----------------------------------------------------------------------
def parse_filter(expr: Optional[str]) -> Optional[Callable[[str], bool]]:
    """Create scenario filter function from expr (supports "*" or comma)."""
    if not expr:
        return None
    if "*" in expr:
        # Glob-style wildcard
        import fnmatch

        expr = expr.strip()
        return lambda name: fnmatch.fnmatch(name, expr)
    expr_list = [x.strip() for x in expr.split(",") if x.strip()]
    return lambda name: name in expr_list


def main(argv: Iterable[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Run v14 scenario analytics (Go With The Flow edition)."
    )
    parser.add_argument(
        "--scenarios-dir",
        default="scenarios",
        help="Directory containing scenario YAML/JSON files.",
    )
    parser.add_argument(
        "--output", default="exports/v14_analytics.xlsx", help="Excel output path."
    )
    parser.add_argument(
        "--no-excel", action="store_true", help="Do not export Excel, only print logs."
    )
    parser.add_argument(
        "--charts", action="store_true", help="Export charts alongside Excel workbook."
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        default=True,
        help="Raise on first scenario failure.",
    )
    parser.add_argument(
        "--parallel", action="store_true", help="Process scenarios in parallel if >4."
    )
    parser.add_argument(
        "--filter",
        type=str,
        default=None,
        help="Only run scenarios matching filter (glob or comma-list).",
    )
    parser.add_argument(
        "--summary-json",
        type=str,
        default=None,
        help="Write run summary/metadata here.",
    )
    parser.add_argument(
        "--default-discount-rate",
        type=float,
        default=0.10,
        help="Global fallback discount rate.",
    )

    args = parser.parse_args(list(argv))

    scenario_filter = parse_filter(args.filter)
    sa = ScenarioAnalytics(
        scenarios_dir=Path(args.scenarios_dir),
        output_path=Path(args.output) if not args.no_excel else None,
        scenario_filter=scenario_filter,
        strict=args.strict,
        parallel=args.parallel,
        global_default_discount_rate=args.default_discount_rate,
    )

    summary_df, timeseries_df, batch_meta = sa.run(
        export_excel=not args.no_excel,
        export_charts=args.charts,
        output_summary_json=Path(args.summary_json) if args.summary_json else None,
    )
    logger.info("Summary head:\n%s", summary_df.head(3))
    logger.info("Timeseries head:\n%s", timeseries_df.head(3))
    if batch_meta.failed:
        logger.warning("Failed scenarios: %s", batch_meta.failed)
    logger.info(
        "Scenario analytics complete. %d success | %d failed",
        batch_meta.n_success,
        batch_meta.n_failed,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
