#!/usr/bin/env python3
"""
Batch scenario analytics orchestrator for v14 cashflow and debt modules.

Enhancements (Go With The Flow):
--------------------------------
- Dynamic per-scenario discount rate (from YAML: scenario override, WACC, or global default)
- Scenario name filtering (via injected filter callable)
- Optional JSON batch summary/metadata
- Robust DSCR/CFADS inference (resistant to legacy or new schema)
- Parallel batch support (toggle for large scenario sets)
- Structured logging of progress and failures
- CLI compatibility with a `strict` flag (plumbed in but behaviour owned by schema guard)

All previous features retained (EPC breakdown, Excel/charts, robust error handling).

Note:
- CLI concerns are handled by run_scenario_analytics_v14.py (Hydra-based).
- This module is a library-only orchestrator in line with Go-with-the-Flow v3.0.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import pandas as pd

from analytics.core.epc_helper import epc_breakdown_from_config
from analytics.core.metrics import calculate_scenario_kpis
from analytics.cost.benchmark import lcos_benchmark
from analytics.export_helpers import DSCR_HIGHLIGHT_THRESHOLD
from analytics.run_manifest import build_run_manifest
from analytics.scenario_loader import load_scenario_config
from analytics.schema_guard import validate_config_for_v14
from finance.bess_lcos import compute_lcos_suite
from finance.cashflow_v14 import build_annual_rows
from finance.debt_v14 import apply_debt_layer

logger = logging.getLogger(__name__)
if not logger.handlers:
    _handler = logging.StreamHandler()
    logger.addHandler(_handler)
logger.setLevel(logging.INFO)

#: Machine-readable provenance marker for batch-path economics (#611). The batch
#: comparison path (this module, behind ``run_scenario_analytics_v14.py``) computes
#: DSCR/IRR on a deliberately lighter basis than the canonical pipeline (PIPE-1,
#: #472): no build-up WACC, no two-pass interest tax shield, no equity-distribution
#: waterfall. This marker is stamped into every emitted batch JSON payload so a
#: consumer cannot mistake batch numbers for the authoritative
#: ``run_full_pipeline_v14.py`` economics.
BATCH_ECONOMICS_BASIS = "comparison_snapshot"


# ---------------------------------------------------------------------------
# Discount-rate default (single source of truth for the code-level fallback)
# ---------------------------------------------------------------------------

#: Code-level fallback for the batch-wide default discount rate, used ONLY when
#: :class:`ScenarioAnalytics` is constructed directly without an explicit
#: ``global_default_discount_rate``. For batch runs via the blessed CLI
#: (``run_scenario_analytics_v14.py``) the authoritative value is the
#: ``default_discount_rate`` key in ``conf/run_scenario_analytics_v14.yaml``
#: (0.12 as committed) and the CLI fails loudly if that key is missing rather
#: than silently falling back to this constant (CESSPIT: config explicit, no
#: silent defaults). Consolidated here per #586 — the default was previously
#: stated three times with two different values.
DEFAULT_GLOBAL_DISCOUNT_RATE: float = 0.10


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------


@dataclass
class BatchScenarioResult:
    """Container for one scenario's results in a batch ScenarioAnalytics comparison.

    Distinct from the canonical :class:`analytics.contracts_v14.ScenarioResult`
    (the single-scenario lender-grade contract): this is the lighter batch-comparison
    container produced by :class:`ScenarioAnalytics`. It was previously also named
    ``ScenarioResult`` with a different structure and no alias, colliding with the
    canonical contract and breaking CCCDIR centralization (audit D9, #578); renamed to
    make the two surfaces unambiguous.
    """

    name: str
    config_path: Path
    kpis: Dict[str, Any]
    annual_rows: List[Dict[str, Any]]
    debt_result: Dict[str, Any]
    discount_rate: float
    fail_reason: Optional[str] = None
    #: Per-BESS Levelised Cost of Storage view (read-only; finance.bess_lcos). One
    #: ``LcosResult.as_dict()`` per ``type: bess`` technology, each carrying an additive
    #: ``benchmark`` advisory (analytics.cost.benchmark.lcos_benchmark, #605: the PNNL
    #: ESGC 2024 / Lazard LCOS v10.0 non-ITC band); empty for wind/solar-only
    #: scenarios, so non-storage scenarios are unaffected.
    lcos: List[Dict[str, Any]] = field(default_factory=list)
    #: Reproducibility stamp (analytics.run_manifest): resolved-config SHA-256 + engine
    #: version + commit for this scenario. ``None`` for a scenario that failed before the
    #: manifest could be built.
    run_manifest: Optional[Dict[str, Any]] = None


@dataclass
class BatchResultSummary:
    """Summary and metadata for a batch ScenarioAnalytics run."""

    successful: List[str]
    failed: List[str]
    n_success: int
    n_failed: int
    batch_summary: Dict[str, Any]
    #: Provenance of the batch economics (#611): always
    #: :data:`BATCH_ECONOMICS_BASIS` (``"comparison_snapshot"``) — these numbers
    #: are ranking/comparison snapshots, NOT the canonical lender-grade economics
    #: (use ``run_full_pipeline_v14.py`` for those). Serialised into both the
    #: persisted ``output_summary_json`` payload and the CLI stdout JSON. Additive
    #: field: no existing key is renamed or removed.
    basis: str = BATCH_ECONOMICS_BASIS


# ---------------------------------------------------------------------------
# Core orchestrator
# ---------------------------------------------------------------------------


class ScenarioAnalytics:
    """
    V14-style orchestrator for batch scenario analytics
    with full Go With The Flow features.

    Responsibilities:
    - Discover scenario config files under a directory.
    - Load configs via the shared loader.
    - Enforce v14 schema guard on each config (validate_config_for_v14).
    - Run cashflow_v14 + debt_v14 for each scenario.
    - Compute KPIs via analytics.core.metrics.
    - Aggregate per-scenario summary_df and timeseries_df.
    - Optionally export Excel/charts/JSON via export_helpers.

    Notes on schema validation (R5, R22):
    - validate_config_for_v14 is always applied; scenarios that violate v14
      schema (e.g. missing FX mapping) are considered invalid and will fail.
    - The `strict` flag is accepted for CLI compatibility and may be used
      by callers to select validation modes; this class itself does not
      reinterpret schema_guard defaults.
    """

    def __init__(
        self,
        scenarios_dir: Path,
        output_path: Optional[Path] = None,
        scenario_filter: Optional[Callable[[str], bool]] = None,
        parallel: bool = False,
        global_default_discount_rate: float = DEFAULT_GLOBAL_DISCOUNT_RATE,
        strict: bool = True,
    ) -> None:
        self.scenarios_dir = Path(scenarios_dir)
        self.output_path = Path(output_path) if output_path is not None else None
        self.parallel = bool(parallel)
        self.global_default_discount_rate = float(global_default_discount_rate)
        self._scenario_filter = scenario_filter
        # Keep a strict flag for callers / CLIs; schema_guard owns semantics.
        self.strict = bool(strict)

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
        for ext in (".yaml", ".yml", ".json"):
            candidates.extend(self.scenarios_dir.rglob(f"*{ext}"))

        all_candidates = sorted(candidates)
        if self._scenario_filter:
            filtered = [p for p in all_candidates if self._scenario_filter(p.stem)]
            logger.info("Filtered %d scenario(s) using scenario_filter", len(filtered))
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
        """
        Extract discount rate per scenario.

        Precedence:
        1. config["scenario"]["override"]["discount_rate"] (if present & valid)
        2. config["wacc"]["project_discount_rate"] (if present & valid)
        3. config["discount_rate"] at top-level (if present & valid)
        4. global_default_discount_rate

        In line with FIN-02, this routine does NOT attempt to infer whether
        values are in percent vs fraction; configs are expected to use
        fraction form (e.g. 0.10 for 10%) or explicitly-named *_pct fields
        elsewhere.
        """
        # 1. Scenario override (legacy but explicit)
        scenario = config.get("scenario", {})
        scenario_overrides = (
            scenario.get("override", {}) if isinstance(scenario, dict) else {}
        )

        if "discount_rate" in scenario_overrides:
            try:
                return float(scenario_overrides["discount_rate"])
            except (TypeError, ValueError):
                logger.warning(
                    "Invalid discount_rate in scenario.override; falling back.",
                )

        # 2. WACC block (canonical v14 naming)
        wacc_cfg = config.get("wacc", {})
        if isinstance(wacc_cfg, dict) and "project_discount_rate" in wacc_cfg:
            try:
                return float(wacc_cfg["project_discount_rate"])
            except (TypeError, ValueError):
                logger.warning(
                    "Invalid project_discount_rate in wacc; falling back.",
                )

        # 3. Top-level discount_rate (if present, treat as fraction)
        if "discount_rate" in config:
            try:
                return float(config["discount_rate"])
            except (TypeError, ValueError):
                logger.warning(
                    "Invalid top-level discount_rate; falling back to default.",
                )

        # 4. Global default
        return self.global_default_discount_rate

    # ------------------------------------------------------------------
    # Single-scenario execution
    # ------------------------------------------------------------------
    def _run_single(self, config_path: Path) -> BatchScenarioResult:
        """Run the full v14 pipeline for a single scenario."""
        name = self._scenario_name_from_path(config_path)
        logger.info("Processing scenario: %s", name)
        discount_rate: Optional[float] = None
        try:
            # Load config
            config = self.load_config(config_path)

            # Schema guard – always enforced (R5, R22)
            validate_config_for_v14(
                raw_config=config,
                config_path=str(config_path),
                modules=["cashflow"],
            )

            # Determine discount rate (scenario, config, global)
            discount_rate = self._effective_discount_rate(config)
            logger.info("  Using discount rate: %.3f%%", discount_rate * 100.0)

            # Annual cashflow rows
            annual_rows = build_annual_rows(config)

            # Debt layer. NB: apply_debt_layer only READS annual_rows (verified
            # #789 review) — the fee rebuild below depends on that staying true,
            # since rebuilt rows would silently discard any in-place enrichment.
            debt_result = apply_debt_layer(config, annual_rows)

            # Senior credit-support fees (#789, mirroring the canonical pipeline's
            # #737 step): apply_debt_layer nets the Financing_Terms.fees fee
            # (rate x opening outstanding) from its DSCR/LLCR/PLCR, so the rows
            # this surface reports must bear the SAME fee — otherwise its
            # IRR/NPV/CFADS would be pre-fee while its coverage ratios are
            # fee-netted (internally inconsistent). Translate the engine's USD fee
            # at each operating row's spot FX via the canonical row->debt-period
            # map and rebuild the rows with it. No fees configured -> the original
            # rows pass through untouched (byte-identical). NB: this surface stays
            # non-canonical by design (fixed debt_ratio — no gearing autosolve;
            # config/default discount, not the build-up WACC).
            senior_fee_usd = [
                float(v or 0.0) for v in (debt_result.get("senior_fee_usd") or [])
            ]
            if any(fee > 0.0 for fee in senior_fee_usd):
                fee_row_to_period: Dict[int, int] = {}
                for mapping in debt_result.get("annual_row_debt_period_map") or []:
                    try:
                        fee_row_to_period[int(mapping["annual_row_index"])] = int(
                            mapping["debt_period"]
                        )
                    except (KeyError, TypeError, ValueError):
                        continue
                senior_fee_lkr_series = []
                for row_idx, row in enumerate(annual_rows):
                    period_idx = fee_row_to_period.get(row_idx, row_idx)
                    fee_usd = (
                        senior_fee_usd[period_idx]
                        if 0 <= period_idx < len(senior_fee_usd)
                        else 0.0
                    )
                    senior_fee_lkr_series.append(
                        fee_usd * float(row.get("fx_rate") or 0.0)
                    )
                annual_rows = build_annual_rows(
                    config, senior_fee_lkr_series=senior_fee_lkr_series
                )

            # KPIs. This batch surface uses a config/default discount, NOT the
            # computed build-up WACC, so report wacc_is_real=False explicitly:
            # otherwise the metrics config-fallback would label the basis "real"
            # from wacc.drives_discount_rate while the rate is not the WACC.
            kpis = calculate_scenario_kpis(
                config=config,
                annual_rows=annual_rows,
                debt_result=debt_result,
                discount_rate=discount_rate,
                wacc_is_real=False,
                wacc_label="base",
            )

            # EPC breakdown, optional non-blocking
            try:
                epc_breakdown = epc_breakdown_from_config(config)
                # epc_breakdown is expected to be a flat mapping of EPC-related
                # metrics; we merge it into the KPI surface.
                kpis.update(epc_breakdown)
            except Exception as exc:  # pragma: no cover
                logger.warning("EPC breakdown derivation failed for %s: %s", name, exc)

            # Levelised Cost of Storage — a READ-ONLY view for any type: bess technology
            # (empty for wind/solar-only scenarios). Best-effort (CASPER), like the report
            # tornado/global-SA adapters: an LCOS failure logs and yields no view rather
            # than sinking the scenario, and it feeds no KPI. The discount rate is this
            # batch's effective rate (the same basis the KPIs use), and the horizon is the
            # number of operating years actually built.
            try:
                lcos = []
                for res in compute_lcos_suite(
                    config,
                    wacc=discount_rate,
                    project_years=len(annual_rows),
                ):
                    entry = res.as_dict()
                    # Advisory literature-band disclosure (#605), ADDITIVE only: the
                    # computed lcos_usd_per_mwh and the fixed-dispatch limitation
                    # notes (#596) it joins are untouched. An out-of-band LCOS logs a
                    # WARNING inside lcos_benchmark, citing PNNL ESGC 2024 / Lazard
                    # LCOS v10.0 (non-ITC); an undefined LCOS gets an explicit
                    # not-comparable note. The advisory itself is best-effort: if it
                    # fails, the LCOS view still surfaces without it.
                    try:
                        entry["benchmark"] = lcos_benchmark(
                            entry.get("lcos_usd_per_mwh")
                        )
                    except Exception as exc:  # pragma: no cover - advisory only
                        logger.warning(
                            "LCOS benchmark advisory failed for %s: %s", name, exc
                        )
                    lcos.append(entry)
            except Exception as exc:  # pragma: no cover - read-only, non-blocking
                logger.warning("LCOS computation failed for %s: %s", name, exc)
                lcos = []

            # Reproducibility stamp (resolved-config SHA-256 + engine version + commit) so
            # every batch scenario is auditable/tamper-evident (ICAEW posture), matching the
            # run_full_pipeline_v14 CLI and the web service gateway. The config hash is
            # per-scenario; engine version and commit are batch-constant. Metadata only.
            run_manifest = build_run_manifest(
                config,
                validation_mode="strict" if self.strict else "off",
            ).as_dict()

            return BatchScenarioResult(
                name=name,
                config_path=config_path,
                kpis=kpis,
                annual_rows=annual_rows,
                debt_result=debt_result,
                discount_rate=discount_rate,
                lcos=lcos,
                run_manifest=run_manifest,
            )
        except Exception as exc:
            logger.error("Scenario %s failed: %s", name, exc)
            return BatchScenarioResult(
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
                fail_reason=str(exc),
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
        """
        Run analytics across all scenarios in scenarios_dir.

        Returns:
            summary_df: per-scenario summary (index: scenario_name)
            timeseries_df: annual rows (column: scenario_name)
            batch_metadata: BatchResultSummary with success/failure lists

        Behaviour:
        - Bad scenarios do not crash the batch; they are logged and included
          in batch_metadata.failed but excluded from result DataFrames.
        - If *all* scenarios fail, raises RuntimeError.
        """
        scenario_paths = self.discover_scenarios()
        if not scenario_paths:
            raise RuntimeError(f"No scenario configs found under {self.scenarios_dir}")

        from concurrent.futures import ThreadPoolExecutor, as_completed

        results: List[BatchScenarioResult] = []
        failures: List[BatchScenarioResult] = []

        batch_run = self.parallel and len(scenario_paths) > 4
        logger.info(
            "Running %d scenario(s) %s. strict=%s",
            len(scenario_paths),
            "in parallel" if batch_run else "serially",
            self.strict,
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
            # All scenarios invalid → hard failure (VAL-02)
            raise RuntimeError("All scenarios failed; no results to summarise")

        # Build DataFrames
        summary_df, timeseries_df = self._build_dataframes(results)

        # Build batch metadata with explicit per-scenario failure reasons
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
                # Read-only per-BESS LCOS view (finance.bess_lcos); only scenarios with a
                # storage (bess-typed) technology contribute, so this is [] for a
                # wind/solar batch and the summary_json is otherwise byte-identical.
                "bess_lcos": [
                    {"scenario": r.name, "results": r.lcos} for r in results if r.lcos
                ],
                # Per-scenario reproducibility manifests (analytics.run_manifest), stamping
                # the batch CLI's summary_json the way run_full_pipeline_v14 stamps its own.
                "run_manifests": [
                    {"scenario": r.name, "manifest": r.run_manifest}
                    for r in results
                    if r.run_manifest is not None
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
                logger.info("    - %s: %s", r.name, r.fail_reason)

        # Exports.
        # When charts are enabled we generate the PNGs FIRST so the board-deck
        # workbook can embed them inline (#662); a live conditional-formatting
        # rule is then applied to the DSCR_View sheet at the SAME 1.2 threshold
        # the pre-existing static highlight fill uses (the static fill is kept —
        # the live rule is additive, so highlighting also survives user edits).
        # When charts are OFF (the default), the Excel path is unchanged and the
        # workbook is byte-identical to before (no cover sheet / no Charts sheet).
        chart_images: List[Path] = []
        if export_charts and self.output_path is not None:
            chart_images = self._export_charts(summary_df, timeseries_df)

        if export_excel and self.output_path is not None:
            self._export_to_excel(
                summary_df,
                timeseries_df,
                chart_images=chart_images or None,
                dscr_conditional_threshold=(
                    DSCR_HIGHLIGHT_THRESHOLD if export_charts else None
                ),
            )

        if output_summary_json is not None:
            output_summary_json = Path(output_summary_json)
            output_summary_json.parent.mkdir(parents=True, exist_ok=True)
            with output_summary_json.open("w", encoding="utf-8") as f:
                json.dump(asdict(batch_metadata), f, indent=2)
            logger.info("Batch metadata written to %s", output_summary_json)

        return summary_df, timeseries_df, batch_metadata

    # ------------------------------------------------------------------
    # DataFrame construction (robust to varied schema)
    # ------------------------------------------------------------------
    def _build_dataframes(
        self,
        results: Sequence[BatchScenarioResult],
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Build summary and timeseries DataFrames from results."""
        summary_records: List[Dict[str, Any]] = []
        timeseries_records: List[Dict[str, Any]] = []

        for result in results:
            rec: Dict[str, Any] = dict(result.kpis)
            rec["scenario_name"] = result.name
            rec["discount_rate_used"] = result.discount_rate
            # At-a-glance storage LCOS (USD/MWh) of the first BESS, surfaced only when the
            # scenario has one — so the column is absent for wind/solar-only batches.
            if result.lcos:
                rec["bess_lcos_usd_per_mwh"] = result.lcos[0].get("lcos_usd_per_mwh")
            summary_records.append(rec)

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
            cfads_col: Optional[str] = None

            for pref in ("cfads_final_lkr", "cfads_final", "posttax_cfads"):
                for c in cfads_candidates:
                    if pref in c.lower():
                        cfads_col = c
                        break
                if cfads_col:
                    break

            if not cfads_col and cfads_candidates:
                cfads_col = cfads_candidates[0]

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
                # pd.NA is the intended replacement (0 debt-service -> NA so DSCR is
                # NaN, not inf); widen the mapping value to Any so newer pandas-stubs
                # accept the NAType value while the runtime stays identical (#992).
                na_sentinel: Any = pd.NA
                denom = timeseries_df[debt_col].replace({0: na_sentinel})
                timeseries_df["dscr"] = timeseries_df[cfads_col] / denom
            else:
                logger.warning(
                    "Could not derive DSCR column: cfads_col=%s, debt_candidates=%s",
                    cfads_col,
                    debt_candidates,
                )

        # NOTE: a normalise_kpis_for_export() pass was referenced here (#135) but
        # the function was never implemented, which broke the import of this
        # blessed entrypoint (run_scenario_analytics_v14). The summary/timeseries
        # frames built above are already export-ready, so return them directly.
        return summary_df, timeseries_df

    # ------------------------------------------------------------------
    # Excel and chart export
    # ------------------------------------------------------------------
    def _build_export_metadata(self, summary_df: pd.DataFrame) -> Dict[str, Any]:
        """Assemble the MRM-02 provenance block that stamps every board artefact.

        MRM-02 requires exported artefacts (Excel / PNG / JSON) to carry the
        scenario name(s), config source, and model VERSION so any reported KPI
        set can be reconstructed. This batch surface fans out over many scenarios,
        so it records the scenario list and their source directory (the per-run
        config-SHA manifests are already stamped into the summary_json by
        :meth:`run`). The engine version is the single-source-of-truth repo
        ``VERSION`` file, reused via :func:`analytics.run_manifest.engine_version`.
        """
        from analytics.run_manifest import engine_version, git_sha

        if "scenario_name" in summary_df.columns:
            scenarios = [str(s) for s in summary_df["scenario_name"].tolist()]
        else:
            scenarios = [str(s) for s in summary_df.index.tolist()]

        return {
            "Model Version": engine_version(),
            "Commit": git_sha(),
            "Economics Basis": BATCH_ECONOMICS_BASIS,
            "Scenarios Directory": str(self.scenarios_dir),
            "Scenario Count": len(scenarios),
            "Scenarios": ", ".join(scenarios),
        }

    def _export_to_excel(
        self,
        summary_df: pd.DataFrame,
        timeseries_df: pd.DataFrame,
        chart_images: Optional[Sequence[Path]] = None,
        dscr_conditional_threshold: Optional[float] = None,
    ) -> None:
        """Export summary and timeseries to Excel.

        ``chart_images`` / ``dscr_conditional_threshold`` are ADDITIVE opt-in
        board-deck enrichments (#662), populated only on the charts-enabled path
        via :meth:`run`. Both default to ``None`` so the default (charts-off)
        Excel deliverable — the one existing callers get — is byte-identical.
        """
        if self.output_path is None:
            logger.warning("No output_path configured; skipping Excel export")
            return
        try:
            from analytics.export_helpers import ExcelExporter

            exporter = ExcelExporter(self.output_path)
            # MRM-02 cover sheet is only added when a board-deck enrichment is
            # requested, so the vanilla workbook stays byte-identical.
            scenario_metadata: Optional[Dict[str, Any]] = None
            if chart_images or dscr_conditional_threshold is not None:
                scenario_metadata = self._build_export_metadata(summary_df)

            exporter.export_summary_and_timeseries(
                summary_df=summary_df,
                timeseries_df=timeseries_df,
                summary_sheet="Summary",
                timeseries_sheet="Timeseries",
                add_board_views=True,
                scenario_metadata=scenario_metadata,
                dscr_conditional_threshold=dscr_conditional_threshold,
                embed_chart_images=(
                    [str(p) for p in chart_images] if chart_images else None
                ),
            )
        except Exception:
            logger.warning(
                "ExcelExporter not available; writing basic Excel workbook to %s",
                self.output_path,
            )
            with pd.ExcelWriter(self.output_path) as writer:
                summary_df.to_excel(writer, sheet_name="Summary")
                timeseries_df.to_excel(writer, sheet_name="Timeseries")
        logger.info("Excel exported to %s", self.output_path)

    def _export_charts(
        self,
        summary_df: pd.DataFrame,
        timeseries_df: pd.DataFrame,
    ) -> List[Path]:
        """Export board-deck charts and return the PNG paths that were written.

        Emits, into the ``*_charts`` sidecar directory:
          - the existing per-scenario DSCR series + IRR histogram (ChartExporter);
          - richer cross-scenario board visuals (ChartGenerator, #662): a KPI
            comparison bar (equity/project IRR), a DSCR comparison line with the
            covenant floor, and an end-of-horizon debt waterfall — all
            matplotlib-optional (return no path if matplotlib is absent);
          - an MRM-02 ``charts_metadata.json`` provenance sidecar
            (scenario/config/VERSION).

        The returned list feeds :meth:`_export_to_excel`, which embeds the PNGs
        into the single .xlsx deliverable when charts are enabled.
        """
        if self.output_path is None:
            logger.warning("No output_path configured; skipping chart export")
            return []
        written: List[Path] = []
        try:
            from analytics.export_helpers import ChartExporter

            charts_dir = self.output_path.with_name(self.output_path.stem + "_charts")
            charts_dir.parent.mkdir(parents=True, exist_ok=True)
            chart_exporter = ChartExporter(output_dir=str(charts_dir))
            if hasattr(chart_exporter, "export_charts"):
                produced = chart_exporter.export_charts(summary_df, timeseries_df)
                if isinstance(produced, dict):
                    written.extend(p for p in produced.values() if p is not None)
            else:
                if hasattr(chart_exporter, "export_dscr_chart"):
                    p = chart_exporter.export_dscr_chart(timeseries_df)
                    if p is not None:
                        written.append(p)
                if hasattr(chart_exporter, "export_irr_histogram"):
                    p = chart_exporter.export_irr_histogram(summary_df)
                    if p is not None:
                        written.append(p)

            # Richer cross-scenario board visuals (#662). Best-effort (CASPER):
            # a failure here logs and yields no extra chart rather than sinking
            # the whole chart export, and it never touches KPIs.
            written.extend(
                self._export_board_comparison_charts(
                    summary_df, timeseries_df, charts_dir
                )
            )

            # MRM-02 provenance sidecar for the charts directory.
            self._write_charts_metadata(summary_df, charts_dir)

            logger.info("Charts exported to %s", charts_dir)
        except Exception:
            logger.warning("ChartExporter not available; skipping chart export")
        return written

    def _export_board_comparison_charts(
        self,
        summary_df: pd.DataFrame,
        timeseries_df: pd.DataFrame,
        charts_dir: Path,
    ) -> List[Path]:
        """Emit the ChartGenerator cross-scenario board visuals (#662)."""
        extra: List[Path] = []
        try:
            from analytics.export_helpers import ChartGenerator

            generator = ChartGenerator(output_dir=str(charts_dir))

            # (1) KPI comparison bar — pick the first available IRR column.
            irr_col: Optional[str] = None
            for candidate in ("equity_irr", "project_irr"):
                if candidate in summary_df.columns:
                    irr_col = candidate
                    break
            if irr_col is not None:
                extra.append(
                    generator.plot_kpi_comparison(
                        summary_df, irr_col, "kpi_comparison.png"
                    )
                )

            # (2) DSCR comparison line with the covenant floor drawn in.
            if {"scenario_name", "dscr"}.issubset(timeseries_df.columns):
                dscr_by_scenario: Dict[str, List[float]] = {}
                for name, grp in timeseries_df.groupby("scenario_name"):
                    series = pd.to_numeric(grp["dscr"], errors="coerce")
                    dscr_by_scenario[str(name)] = [
                        float(v) for v in series.tolist() if pd.notna(v)
                    ]
                if dscr_by_scenario:
                    extra.append(
                        generator.plot_dscr_comparison(
                            dscr_by_scenario,
                            "dscr_comparison.png",
                            threshold=1.0,
                        )
                    )

                    # (3) Debt waterfall (end-of-horizon) reuses the same
                    # per-scenario DSCR projection as a stand-in trajectory.
                    extra.append(
                        generator.plot_debt_waterfall(
                            dscr_by_scenario, "debt_waterfall.png"
                        )
                    )
        except Exception as exc:  # pragma: no cover - additive, best-effort
            logger.warning("Board comparison charts failed: %s", exc)
        return extra

    def _write_charts_metadata(
        self,
        summary_df: pd.DataFrame,
        charts_dir: Path,
    ) -> None:
        """Write the MRM-02 provenance sidecar into the charts directory."""
        try:
            charts_dir.mkdir(parents=True, exist_ok=True)
            metadata = self._build_export_metadata(summary_df)
            meta_path = charts_dir / "charts_metadata.json"
            with meta_path.open("w", encoding="utf-8") as fh:
                json.dump(metadata, fh, indent=2, sort_keys=True)
        except Exception as exc:  # pragma: no cover - additive, best-effort
            logger.warning("Charts metadata sidecar failed: %s", exc)


# EOF
