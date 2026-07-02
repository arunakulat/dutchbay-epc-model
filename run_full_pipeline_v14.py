"""Hydra CLI for Complete Wind-to-Finance Pipeline.

Entrypoint for running the complete DutchBay wind farm assessment and
financial analysis. Integrates:

- Wind-resource frozen-export ingestion (consumes JSON produced by
  ``scripts/run_wind_analysis_v14.py``; never calls Copernicus directly)
- Optional auto-orchestration: when ``wind_auto_orchestrate=true`` and the
  ``[wind]`` extra is installed, this CLI subprocesses the wind producer
  to mint a fresh frozen export before the finance run
- Solar-resource frozen-export ingestion (consumes JSON produced by the
  offline :func:`solar_resource.cashflow_adapter.build_solar_cashflow_export`
  freeze; never imports ``pvlib`` and never calls ``compute_solar_aep``)
- Financial modelling (cashflow, IRR, NPV)
- Equity distribution waterfall and equity investor metrics
- Monte Carlo uncertainty analysis

The wind-resource path is OFF by default — setting neither
``wind_assessment_json`` nor ``wind_auto_orchestrate`` preserves the
pre-Sprint-19 behaviour exactly. When wind data is supplied, it flows
through :mod:`wind_resource.cashflow_adapter` in the configured
``adapter_mode`` (default ``fill_if_absent``) and the patched scenario
is written to a temp file before being handed to ``run_v14_pipeline``.
The pipeline signature is unchanged — wiring is purely additive.

Solar parity is by FROZEN EXPORT ONLY (#614)
--------------------------------------------
The solar-resource path is likewise OFF by default — leaving
``solar_assessment_json`` null skips solar entirely. When a frozen solar
export is supplied it flows through
:func:`solar_resource.cashflow_adapter.solar_export_to_scenario_patch`
(the pvlib-free adapter), patching the per-technology
``generation.technologies.<tech>`` block and re-blending
``project.capacity_factor`` — the SAME semantics the web API uses at
``app/services/pipeline_service.run_integrated_case``. It chains AFTER any
wind patch (wind writes the project headline; solar re-blends it), matching
``run_integrated_case``'s wind-then-solar order. Deliberately there is NO
solar auto-orchestrate analogue and ``compute_solar_aep`` is NEVER invoked
in the finance path: lender-grade runs consume an audited frozen export and
the base install / every CI lane runs the finance case with no ``pvlib``
dependency (the offline physics freeze happens once behind the ``[solar]``
extra). This closes issue #614's "or document" alternative — the canonical
CLI achieves hybrid solar parity via the frozen export, not by re-running
the producer at finance time.

Usage:
    Basic (uses default validation):
        python run_full_pipeline_v14.py \\
            config=scenarios/dutchbay_lendercase_2025Q4.yaml
    
    With explicit validation options:
        python run_full_pipeline_v14.py \\
            config=scenarios/dutchbay_lendercase_2025Q4.yaml \\
            validation_mode=strict \\
            validation_modules=cashflow,debt
    
    Skip validation (faster, for debugging):
        python run_full_pipeline_v14.py \\
            config=scenarios/dutchbay_lendercase_2025Q4.yaml \\
            validation_mode=off
    
    Custom artifact location (CI):
        python run_full_pipeline_v14.py \\
            config=scenarios/dutchbay_lendercase_2025Q4.yaml \\
            export_dir=_out/release_run \\
            write_artifacts=true

    Consume a frozen wind export (lender-grade default):
        python run_full_pipeline_v14.py \\
            config=scenarios/dutchbay_lendercase_2025Q4.yaml \\
            wind_assessment_json=_out/wind_assessment/dutchbay_P75.json \\
            adapter_mode=fill_if_absent

    Auto-orchestrate wind producer + finance consumer in one call:
        python run_full_pipeline_v14.py \\
            config=scenarios/dutchbay_lendercase_2025Q4.yaml \\
            wind_auto_orchestrate=true \\
            wind_export_scenario=P75

    Consume a frozen solar export into a hybrid (frozen-export parity, #614):
        python run_full_pipeline_v14.py \\
            config=scenarios/dutchbay_hybrid_windsolar_2025Q4.yaml \\
            solar_assessment_json=_out/solar_assessment/dutchbay_P50.json \\
            solar_adapter_mode=fill_if_absent \\
            solar_export_scenario=P50

Output:
    JSON to stdout with:
    - status: 'success' or 'error'
    - scenario_result: Complete ScenarioResult with lender metrics
    - kpis: All calculated KPIs (IRR, NPV, DSCR, LLCR, PLCR, equity metrics)
    - annual_rows: Annual cashflow schedule
    - debt_result: Debt structuring with DSCR series
    - equity_distribution: Equity waterfall and distribution schedule
    - metrics: Pipeline execution metrics (if monitoring enabled)
    
    Optional file artifacts (if write_artifacts=true):
    - summary.json: Full pipeline result
    - kpis.json: KPI dictionary
    - debt_result.json: Debt structuring
    - equity_distribution.json: Equity waterfall and equity metrics
    - annual_rows.csv: Cashflow schedule

GWTF Compliance:
- R3: Hydra-only (no argparse)
- CLI-01: Hydra-based architecture
- CLI-03: JSON-first outputs + optional files
- R24: Google-style docstrings
- CCCDIR: All config from YAML files

Author: Dutch Bay Wind Farm Team
Date: December 2025
Version: 2.3.0 (Lender-Grade Pipeline + Equity Distribution + Wind→Finance Integration)
"""

from __future__ import annotations

import csv
import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, cast

import hydra
import yaml
from omegaconf import DictConfig

# Canonical lender-grade pipeline (analytics.pipeline_v14_enhanced).
from analytics.executive_workbook import emit_executive_workbook_from_pipeline
from analytics.pipeline_v14_enhanced import run_v14_pipeline
from analytics.run_manifest import build_run_manifest
from analytics.scenario_loader import load_scenario_config

# W4 (#614): the solar→finance adapter is the photovoltaic analogue of the wind
# adapter — a pure function over plain dicts with no pvlib/PyWake dependency, so
# importing it unconditionally is safe even when the [solar] extra is absent. The
# canonical CLI consumes a *frozen* solar export via this adapter exactly as the API
# layer does (app/services/pipeline_service.run_integrated_case); compute_solar_aep is
# NEVER called at finance time (CASPER/frozen-export design).
from solar_resource.cashflow_adapter import (
    SolarAdapterDriftError,
    SolarAdapterMode,
    solar_export_to_scenario_patch,
)

# Sprint 19 (W.6): the wind→finance adapter is a leaf module with no
# heavy dependencies, so importing it unconditionally is safe even when
# the [wind] extra is not installed.
from wind_resource.cashflow_adapter import (
    AdapterMode,
    WindAdapterDriftError,
    wind_export_to_scenario_patch,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Artifact Writing Helpers (stdlib only - CI-safe)
# ============================================================================


def _safe_mkdir(path: Path) -> None:
    """Create directory if it doesn't exist (mkdir -p behavior).

    Args:
        path: Directory path to create.

    Returns:
        None. Creates directory with parents if needed.
    """
    path.mkdir(parents=True, exist_ok=True)


def _write_json(path: Path, payload: Any) -> None:
    """Write Python object as formatted JSON file.

    Args:
        path: File path for JSON output.
        payload: Python object to serialize (must be JSON-serializable).

    Returns:
        None. Writes file with indent=2, sorted keys.
    """
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )


def _load_manifest_config(effective_config: str | Path) -> dict[str, Any]:
    """Re-load the resolved config for manifest hashing, warning loudly on failure.

    The run manifest hashes the resolved config so ``summary.json`` is tamper-evident.
    If that re-load fails we still emit a manifest (rather than aborting a successful
    run), but bound to a non-binding ``{config_path: ...}`` fallback whose ``config_sha256``
    no longer reflects the resolved contents. This previously happened under a bare
    ``except`` with **no log line** (audit D8, #577), so a tamper-evidence-void manifest
    could ship unnoticed. The failure is now logged at WARNING with the traceback.
    """
    try:
        return dict(load_scenario_config(effective_config))
    except Exception:
        logger.warning(
            "Run manifest degraded: could not re-load %r to hash its resolved config; "
            "the manifest's config_sha256 will bind to the file path, not the resolved "
            "contents (tamper-evidence weakened).",
            str(effective_config),
            exc_info=True,
        )
        return {"config_path": str(effective_config)}


def _stamp_manifest_if_absent(
    result: Any, effective_config: str | Path, validation_mode: str
) -> None:
    """Stamp ``result['run_manifest']`` only when the engine has not already.

    The engine (``run_v14_pipeline``) stamps the manifest itself from the RESOLVED
    config it actually evaluated (#577) — that is the binding, authoritative stamp
    and it wins. This CLI-level fallback fires only when the manifest is missing
    (e.g. an error-shaped result dict, or a monkeypatched engine): it re-loads the
    config via :func:`_load_manifest_config`, whose degraded ``{config_path: ...}``
    path warns loudly (audit D8, #577) rather than silently.

    Args:
        result: The pipeline result; only mutated when it is a dict without a
            truthy ``run_manifest``.
        effective_config: The config path handed to the engine, re-loaded for
            hashing on the fallback path only.
        validation_mode: The validation mode recorded in the fallback manifest.

    Returns:
        None. Mutates ``result`` in place on the fallback path.
    """
    if isinstance(result, dict) and not result.get("run_manifest"):
        result["run_manifest"] = build_run_manifest(
            _load_manifest_config(effective_config),
            validation_mode=str(validation_mode),
        ).as_dict()


# ============================================================================
# Sprint 19 (W.6): Wind→Finance integration helpers
# ============================================================================


def _load_yaml_scenario(scenario_path: str | Path) -> dict[str, Any]:
    """Load a v14 scenario YAML/JSON file into a plain dict.

    Accepts ``.yaml``/``.yml``/``.json`` extensions transparently because
    PyYAML parses JSON-shaped YAML correctly. Pure read — no side effects.
    """
    p = Path(scenario_path)
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(
            f"Scenario {scenario_path!r} did not parse to a dict "
            f"(got {type(data).__name__})"
        )
    return data


def _load_wind_export(export_path: str | Path) -> dict[str, Any]:
    """Load a frozen wind-export JSON file produced by run_wind_analysis_v14.

    The producer emits a JSON object containing a ``cashflow_export`` key
    whose value matches the :class:`wind_resource.cashflow_adapter.WindCashflowExport`
    contract. Top-level shapes that already match the contract (no wrapper)
    are also accepted for forward-compatibility.

    No validation is performed here beyond "is a dict" — contract enforcement
    is the adapter's job (Pydantic ``WindCashflowExport`` will reject any
    payload that fails the 11-key schema with a clear ValidationError).
    """
    p = Path(export_path)
    with p.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(
            f"Wind export {export_path!r} did not parse to a dict "
            f"(got {type(payload).__name__})"
        )
    # Producer wraps under 'cashflow_export'; tolerate both shapes.
    if "cashflow_export" in payload and isinstance(payload["cashflow_export"], dict):
        return payload["cashflow_export"]
    return payload


def _read_wind_export_payload(export_path: str | Path) -> dict[str, Any]:
    """Load the FULL frozen wind-export JSON (top-level, not just cashflow_export).

    :func:`_load_wind_export` unwraps to the ``cashflow_export`` contract for the
    finance adapter; the Executive Workbook step instead needs the top-level
    payload so it can read the optional ``long_term_trend`` block that rides
    alongside ``cashflow_export`` (see
    ``analytics.executive_workbook.resource_trend_df_from_wind_export``). Pure
    read — no validation beyond "is a dict".
    """
    p = Path(export_path)
    with p.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(
            f"Wind export {export_path!r} did not parse to a dict "
            f"(got {type(payload).__name__})"
        )
    return payload


def _load_solar_export(export_path: str | Path) -> dict[str, Any]:
    """Load a frozen solar-export JSON into the SolarCashflowExport contract shape.

    The frozen export is the serialized output of
    :func:`solar_resource.cashflow_adapter.build_solar_cashflow_export` (the offline
    freeze of a :func:`solar_resource.pv_producer.compute_solar_aep` run behind the
    ``[solar]`` extra). This CLI never calls ``compute_solar_aep`` — it only ingests
    the audited frozen number, exactly as the API layer does.

    Both a bare contract-shaped object and one wrapped under ``cashflow_export`` /
    ``solar_export`` are accepted (symmetry with :func:`_load_wind_export`, which
    tolerates the producer's ``cashflow_export`` wrapper). No validation is performed
    here beyond "is a dict" — contract enforcement is the adapter's job (the Pydantic
    ``SolarCashflowExport`` rejects any payload that fails the schema with a clear
    ValidationError, incl. a CF > 1.0 mis-scaled-percent guard).
    """
    p = Path(export_path)
    with p.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(
            f"Solar export {export_path!r} did not parse to a dict "
            f"(got {type(payload).__name__})"
        )
    for wrapper in ("cashflow_export", "solar_export"):
        inner = payload.get(wrapper)
        if isinstance(inner, dict):
            return inner
    return payload


def _run_wind_producer(
    scenario_yaml_path: str | Path,
    export_scenario: str,
    output_dir: str | Path,
) -> Path:
    """Subprocess the wind-export producer; return path to the JSON it wrote.

    Used only when ``wind_auto_orchestrate=true`` AND ``wind_assessment_json``
    is unset. Requires the ``[wind]`` extra (cdsapi, xarray, netcdf4) to be
    installed in the active Python environment.

    Raises
    ------
    RuntimeError
        If ``cdsapi`` is not importable (i.e. ``[wind]`` extra missing),
        or if the subprocess exits non-zero, or if the export file cannot
        be located after a successful run.
    """
    # Probe for [wind] extra before spawning the subprocess so we fail fast
    # with a clear message rather than a cryptic subprocess error.
    try:
        import cdsapi  # type: ignore[import-not-found,import-untyped,unused-ignore]  # noqa: F401  (availability probe; the ignore lists every code mypy may raise across envs — import-not-found without the [wind] extra vs import-untyped once cdsapi is installed, as it ships no stubs — plus unused-ignore so the suppression is silent in whichever env doesn't need the other two)
    except ImportError as exc:
        raise RuntimeError(
            "wind_auto_orchestrate=true requires the [wind] extra. "
            "Install with: pip install -e '.[wind]'  "
            "Alternatively, provide a pre-computed wind_assessment_json."
        ) from exc

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_json = output_dir / f"wind_export_{export_scenario}.json"

    # The producer reads location from its own Hydra config; we extract it
    # from the scenario YAML so the two CLIs stay aligned.
    scenario_dict = _load_yaml_scenario(scenario_yaml_path)
    location = (
        scenario_dict.get("wind_resource", {}).get("location")
        or scenario_dict.get("project", {}).get("location")
        or "dutchbay"
    )

    # Producer prints JSON to stdout per its CLI contract; capture it.
    repo_root = Path(__file__).resolve().parent
    producer = repo_root / "scripts" / "run_wind_analysis_v14.py"
    if not producer.exists():
        raise RuntimeError(f"Wind producer not found at {producer}")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root) + os.pathsep + env.get("PYTHONPATH", "")

    logger.info(
        "Auto-orchestrate: invoking wind producer (location=%s, scenario=%s)",
        location,
        export_scenario,
    )
    proc = subprocess.run(
        [
            sys.executable,
            str(producer),
            f"location={location}",
            f"export_scenario={export_scenario}",
        ],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"Wind producer exited {proc.returncode}. "
            f"stderr (last 500 chars): ...{proc.stderr[-500:]}"
        )

    # Persist the captured stdout JSON so subsequent consumers can audit it.
    output_json.write_text(proc.stdout, encoding="utf-8")
    logger.info("Auto-orchestrate: wrote wind export to %s", output_json)
    return output_json


def _apply_wind_to_scenario(
    scenario_path: str | Path,
    wind_export_path: str | Path,
    adapter_mode: str,
    tolerance_pct: float,
    scenario_name: str,
) -> Path:
    """Patch the scenario with the wind export; return path to patched copy.

    Returns the path of a *new* temp file containing the patched scenario.
    The original scenario file on disk is never touched.
    """
    scenario_dict = _load_yaml_scenario(scenario_path)
    export_dict = _load_wind_export(wind_export_path)

    patched = wind_export_to_scenario_patch(
        export_dict,
        scenario_dict,
        scenario_name=scenario_name,
        # adapter_mode is validated for membership inside the callee (it raises
        # on an unknown mode); cast is a no-op at runtime, so the same string
        # value flows through unchanged.
        adapter_mode=cast(AdapterMode, adapter_mode),
        tolerance_pct=float(tolerance_pct),
    )

    # Write to a temp file alongside the original scenario so any relative
    # paths inside the YAML still resolve correctly. delete=False because we
    # hand the path to run_v14_pipeline; cleanup is performed by the
    # ``finally`` block in :func:`cli` (see end of this module).
    # The original scenario YAML on disk is never mutated.
    src_dir = Path(scenario_path).resolve().parent
    tmp = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".patched.yaml",
        dir=str(src_dir),
        delete=False,
    )
    try:
        yaml.safe_dump(patched, tmp, sort_keys=False)
    finally:
        tmp.close()
    logger.info(
        "Wind→scenario patch applied (mode=%s, tolerance=%.3f%%, scenario=%s)",
        adapter_mode,
        tolerance_pct,
        scenario_name,
    )
    return Path(tmp.name)


def _apply_solar_to_scenario(
    scenario_path: str | Path,
    solar_export_path: str | Path,
    adapter_mode: str,
    tolerance_pct: float,
    scenario_name: str,
    technology: str,
) -> Path:
    """Patch the scenario with a frozen solar export; return path to patched copy.

    Photovoltaic analogue of :func:`_apply_wind_to_scenario`. Consumes a frozen solar
    export via the pvlib-free ``solar_resource.cashflow_adapter.solar_export_to_scenario_patch``
    — the SAME adapter and semantics the API seam uses
    (``app/services/pipeline_service.run_integrated_case``): it patches the per-tech
    ``generation.technologies.<technology>`` block and re-blends
    ``project.capacity_factor``, whereas the wind adapter writes the wind-only
    project headline. No ``pvlib`` import and no ``compute_solar_aep`` call.

    Returns the path of a *new* temp file containing the patched scenario. The original
    scenario file on disk is never touched.
    """
    scenario_dict = _load_yaml_scenario(scenario_path)
    export_dict = _load_solar_export(solar_export_path)

    patched = solar_export_to_scenario_patch(
        export_dict,
        scenario_dict,
        scenario_name=scenario_name,
        # adapter_mode is validated for membership inside the callee (it raises on an
        # unknown mode); cast is a no-op at runtime, so the same string value flows
        # through unchanged.
        adapter_mode=cast(SolarAdapterMode, adapter_mode),
        tolerance_pct=float(tolerance_pct),
        technology=technology,
    )

    # Write to a temp file alongside the original scenario so any relative paths inside
    # the YAML still resolve correctly. delete=False because we hand the path to
    # run_v14_pipeline; cleanup is performed by the ``finally`` block in :func:`cli`.
    # The original scenario YAML on disk is never mutated.
    src_dir = Path(scenario_path).resolve().parent
    tmp = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".patched.yaml",
        dir=str(src_dir),
        delete=False,
    )
    try:
        yaml.safe_dump(patched, tmp, sort_keys=False)
    finally:
        tmp.close()
    logger.info(
        "Solar→scenario patch applied (mode=%s, tolerance=%.3f%%, scenario=%s, tech=%s)",
        adapter_mode,
        tolerance_pct,
        scenario_name,
        technology,
    )
    return Path(tmp.name)


def _cleanup_patched_scenarios(paths: list[Path]) -> None:
    """Best-effort remove temp patched-scenario files; never raises.

    Shared by the pipeline ``finally`` (success/pipeline-error path) and the solar
    ingestion error branches (which ``raise SystemExit`` before the pipeline ``try`` is
    entered, so its ``finally`` would not run and any earlier wind temp file would leak).
    """
    for p in paths:
        try:
            p.unlink(missing_ok=True)
        except OSError as cleanup_exc:  # pragma: no cover (best-effort)
            logger.warning(
                "Could not remove temp patched scenario %s: %s", p, cleanup_exc
            )


def _write_annual_rows_csv(path: Path, annual_rows: Any) -> None:
    """Write annual cashflow rows as CSV (stdlib csv module - no pandas).

    Args:
        path: File path for CSV output.
        annual_rows: List of dicts representing annual cashflow rows.

    Returns:
        None. Writes CSV with header row derived from all dict keys.

    Notes:
        - Uses stdlib csv module for CI stability (no pandas dependency)
        - Handles heterogeneous row schemas (union of all keys)
        - Sorts fieldnames for deterministic column order
        - Skips non-dict entries silently
    """
    if not isinstance(annual_rows, list) or not annual_rows:
        return

    dict_rows = [row for row in annual_rows if isinstance(row, dict)]
    if not dict_rows:
        return

    fieldnames: list[str] = sorted({k for row in dict_rows for k in row.keys()})

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in dict_rows:
            writer.writerow(row)


# ============================================================================
# Hydra CLI Entry Point
# ============================================================================


@hydra.main(
    version_base="1.3",
    config_path="conf",
    config_name="run_full_pipeline_v14",
)
def cli(cfg: DictConfig) -> None:
    """Hydra CLI entry point for complete lender-grade pipeline.

    Args:
        cfg: Hydra configuration from conf/run_full_pipeline_v14.yaml.
            Required fields:
                - config: Path to scenario YAML file.
            Optional fields (finance):
                - validation_mode: 'strict' or 'off' (default: 'strict').
                - validation_modules: Comma-separated string or array of
                  modules to validate (default: None → all modules).
                - export_dir: Artifact output directory
                  (default: '_out/run_full_pipeline_v14').
                - write_artifacts: Write JSON/CSV files (default: false;
                  the runtime reads bool(cfg.get("write_artifacts", False))).
            Optional fields (Sprint 19 W.6 — wind→finance ingestion;
            OFF by default — setting neither of the first two preserves
            pre-Sprint-19 behaviour exactly):
                - wind_assessment_json: Path to a frozen wind-export JSON
                  produced by scripts/run_wind_analysis_v14.py. When set,
                  the finance run consumes this export via
                  wind_resource.cashflow_adapter. Mutually exclusive with
                  wind_auto_orchestrate — an explicit path always wins.
                - wind_auto_orchestrate: If true AND wind_assessment_json
                  is null, subprocess the wind producer to mint a fresh
                  export before the finance run. Requires the [wind] extra
                  (cdsapi, xarray, netcdf4). Default false — lender-grade
                  runs should consume an audited frozen export.
                - adapter_mode: 'overwrite' | 'fill_if_absent' |
                  'validate_only' (default: 'fill_if_absent'). See
                  wind_resource.cashflow_adapter module docstring.
                - wind_tolerance_pct: Symmetric relative drift tolerance
                  in percent for fill_if_absent and validate_only modes
                  (default: 0.5).
                - wind_export_scenario: P-level selector ('P50' | 'P75' |
                  'P90'); must match the scenario field of the export JSON
                  (default: 'P75').
            Optional fields (W4 #614 — solar→finance ingestion; OFF by
            default — leaving solar_assessment_json null skips solar entirely
            and preserves behaviour exactly. Frozen-export only: there is NO
            solar auto-orchestrate analogue and compute_solar_aep is never
            called — the finance path stays pvlib-free, matching the
            'lender-grade runs consume audited frozen exports' design and
            app/services/pipeline_service.run_integrated_case):
                - solar_assessment_json: Path to a frozen solar-export JSON
                  (the serialized output of
                  solar_resource.cashflow_adapter.build_solar_cashflow_export).
                  When set, the finance run consumes this export via
                  solar_resource.cashflow_adapter — it patches the per-tech
                  generation.technologies.<tech> block and re-blends
                  project.capacity_factor. Chains AFTER any wind patch.
                - solar_adapter_mode: 'overwrite' | 'fill_if_absent' |
                  'validate_only' (default: 'fill_if_absent').
                - solar_tolerance_pct: Symmetric relative drift tolerance in
                  percent for fill_if_absent and validate_only (default: 0.5).
                - solar_export_scenario: P-level selector ('P50' | 'P75' |
                  'P90'); must match the scenario field of the export JSON
                  (default: 'P50' — the producer is deterministic P50 today).
                - solar_technology: generation.technologies key the solar
                  export targets (default: 'solar').
            Optional fields (#656 slice 3 — Executive Workbook emission; OFF
            by default — leaving emit_executive_workbook false preserves
            behaviour and keeps committed-scenario output byte-identical):
                - emit_executive_workbook: If true, write a single-scenario
                  lender Executive Workbook (.xlsx) after a successful run via
                  analytics.executive_workbook.emit_executive_workbook_from_pipeline.
                  The five finance sheets come from the pipeline result; the
                  optional "ResourceTrend" sheet is added only when the supplied
                  frozen wind export carries a long_term_trend block. No live
                  ERA5 is run (the finance CLI stays cdsapi-free). Default false.
                - executive_workbook_path: Target .xlsx path. Default
                  '<export_dir>/executive_workbook.xlsx'. On emission the written
                  path is echoed back under result['executive_workbook_path'].

    Returns:
        None. Prints JSON result to stdout. Optionally writes artifacts.
        On wind- or solar-ingestion failure, prints a structured error JSON
        with ``status='error'`` and ``phase='wind_resource_ingestion'`` /
        ``phase='solar_resource_ingestion'`` (or
        ``error_type='WindAdapterDriftError'`` /
        ``error_type='SolarAdapterDriftError'`` for drift failures) and
        exits 1 before the finance pipeline runs.

    Raises:
        SystemExit: Exit code 1 on any failure (missing config, wind
            ingestion error, drift threshold breach, or pipeline error).
    """
    config = cfg.get("config")
    if not config:
        error_result: dict[str, Any] = {
            "status": "error",
            "error": "Missing 'config' parameter",
            "usage": (
                "python run_full_pipeline_v14.py "
                "config=scenarios/example_a.yaml "
                "[validation_mode=strict] "
                "[validation_modules=cashflow,debt] "
                "[export_dir=_out/release_run] "
                "[write_artifacts=true] "
                "[wind_assessment_json=_out/wind_assessment/dutchbay_P75.json] "
                "[wind_auto_orchestrate=false] "
                "[adapter_mode=fill_if_absent] "
                "[wind_tolerance_pct=0.5] "
                "[wind_export_scenario=P75] "
                "[solar_assessment_json=_out/solar_assessment/dutchbay_P50.json] "
                "[solar_adapter_mode=fill_if_absent] "
                "[solar_tolerance_pct=0.5] "
                "[solar_export_scenario=P50] "
                "[solar_technology=solar]"
            ),
        }
        print(json.dumps(error_result, indent=2))
        raise SystemExit(1)

    # ------------------------------------------------------------------
    # Sprint 19 W.6: optional wind-resource ingestion.
    #
    # OFF by default — if neither wind_assessment_json nor
    # wind_auto_orchestrate is set, control falls straight through to
    # run_v14_pipeline with the original config path. This preserves the
    # pre-Sprint-19 behaviour exactly for callers that don't opt in.
    # ------------------------------------------------------------------
    wind_assessment_json = cfg.get("wind_assessment_json", None)
    wind_auto_orchestrate = bool(cfg.get("wind_auto_orchestrate", False))
    adapter_mode = str(cfg.get("adapter_mode", "fill_if_absent"))
    wind_tolerance_pct = float(cfg.get("wind_tolerance_pct", 0.5))
    wind_export_scenario = str(cfg.get("wind_export_scenario", "P75"))

    # ------------------------------------------------------------------
    # W4 (#614): optional solar-resource ingestion (frozen export only).
    #
    # OFF by default — solar_assessment_json defaults to null, so when it
    # is unset the solar block is skipped entirely and CLI behaviour is
    # byte-identical (no committed scenario passes a solar export). There is
    # deliberately NO solar auto-orchestrate analogue: lender-grade runs
    # consume an audited frozen export, and the finance stack stays pvlib-free
    # (compute_solar_aep is never called here). When set, the solar export
    # flows through solar_resource.cashflow_adapter with the SAME semantics as
    # app/services/pipeline_service.run_integrated_case, patching the per-tech
    # generation block and re-blending the project headline. It chains AFTER
    # the wind patch (wind writes the project headline; solar re-blends it),
    # matching run_integrated_case's wind-then-solar ordering.
    # ------------------------------------------------------------------
    solar_assessment_json = cfg.get("solar_assessment_json", None)
    solar_adapter_mode = str(cfg.get("solar_adapter_mode", "fill_if_absent"))
    solar_tolerance_pct = float(cfg.get("solar_tolerance_pct", 0.5))
    solar_export_scenario = str(cfg.get("solar_export_scenario", "P50"))
    solar_technology = str(cfg.get("solar_technology", "solar"))

    # ------------------------------------------------------------------
    # #656 (slice 3): optional single-scenario Executive Workbook emission
    # (OFF by default). When true, after a successful finance run this CLI
    # writes a lender-facing .xlsx via
    # analytics.executive_workbook.emit_executive_workbook_from_pipeline —
    # the genuine live caller of build_executive_workbook. The five finance
    # sheets are assembled from the pipeline result; the optional
    # "ResourceTrend" sheet is added only when a supplied frozen wind export
    # carries a long_term_trend block. Emission derives no financial value and
    # never mutates KPIs, so committed-scenario runs (which leave this off) stay
    # byte-identical.
    # ------------------------------------------------------------------
    emit_executive_workbook = bool(cfg.get("emit_executive_workbook", False))
    executive_workbook_path = cfg.get("executive_workbook_path", None)

    effective_config: str = str(config)
    # Temp patched-scenario files (wind then solar) to clean up in ``finally``.
    patched_scenario_paths: list[Path] = []
    # Resolved frozen wind-export path (if any), captured for the optional
    # Executive Workbook step so it can read the long_term_trend block.
    resolved_wind_json_path: Path | None = None
    try:
        if wind_assessment_json or wind_auto_orchestrate:
            # Resolve the wind export path: either explicitly supplied or
            # produced via auto-orchestrate subprocess.
            if wind_assessment_json:
                wind_json_path = Path(str(wind_assessment_json))
                if not wind_json_path.exists():
                    raise FileNotFoundError(
                        f"wind_assessment_json={wind_json_path} does not exist"
                    )
            else:
                wind_json_path = _run_wind_producer(
                    scenario_yaml_path=config,
                    export_scenario=wind_export_scenario,
                    output_dir=Path(
                        str(cfg.get("export_dir", "_out/run_full_pipeline_v14"))
                    )
                    / "wind_export",
                )

            resolved_wind_json_path = wind_json_path

            patched_scenario_path = _apply_wind_to_scenario(
                scenario_path=config,
                wind_export_path=wind_json_path,
                adapter_mode=adapter_mode,
                tolerance_pct=wind_tolerance_pct,
                scenario_name=wind_export_scenario,
            )
            patched_scenario_paths.append(patched_scenario_path)
            effective_config = str(patched_scenario_path)
    except WindAdapterDriftError as e:
        # Surface as structured error — lender CI should fail loudly.
        error_result = {
            "status": "error",
            "error": str(e),
            "error_type": "WindAdapterDriftError",
            "field": e.field,
            "wind_value": e.wind_value,
            "scenario_value": e.scenario_value,
            "drift_pct": e.drift_pct,
            "tolerance_pct": e.tolerance_pct,
            "adapter_mode": e.mode,
        }
        print(json.dumps(error_result, indent=2))
        logger.error("Wind→scenario adapter raised drift error: %s", e)
        raise SystemExit(1) from e
    except (FileNotFoundError, RuntimeError, ValueError) as e:
        # Catches: missing wind_assessment_json, [wind]-extra-missing subprocess
        # probe failure, malformed wind export JSON, scenario YAML parse error.
        # Surface as structured JSON consistent with the WindAdapterDriftError
        # branch above so CI can parse the failure uniformly.
        error_result = {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__,
            "phase": "wind_resource_ingestion",
            "config": str(config),
        }
        print(json.dumps(error_result, indent=2))
        logger.error("Wind→scenario ingestion failed: %s", e)
        raise SystemExit(1) from e

    # ------------------------------------------------------------------
    # W4 (#614): optional solar-resource ingestion — chains on effective_config
    # (which already carries any wind patch), mirroring run_integrated_case's
    # wind-then-solar ordering. OFF unless solar_assessment_json is set.
    # ------------------------------------------------------------------
    try:
        if solar_assessment_json:
            solar_json_path = Path(str(solar_assessment_json))
            if not solar_json_path.exists():
                raise FileNotFoundError(
                    f"solar_assessment_json={solar_json_path} does not exist"
                )
            patched_scenario_path = _apply_solar_to_scenario(
                scenario_path=effective_config,
                solar_export_path=solar_json_path,
                adapter_mode=solar_adapter_mode,
                tolerance_pct=solar_tolerance_pct,
                scenario_name=solar_export_scenario,
                technology=solar_technology,
            )
            patched_scenario_paths.append(patched_scenario_path)
            effective_config = str(patched_scenario_path)
    except SolarAdapterDriftError as e:
        # Surface as structured error — lender CI should fail loudly. Mirrors the
        # WindAdapterDriftError branch; note the solar detail field is ``solar_value``.
        error_result = {
            "status": "error",
            "error": str(e),
            "error_type": "SolarAdapterDriftError",
            "field": e.field,
            "solar_value": e.solar_value,
            "scenario_value": e.scenario_value,
            "drift_pct": e.drift_pct,
            "tolerance_pct": e.tolerance_pct,
            "adapter_mode": e.mode,
        }
        print(json.dumps(error_result, indent=2))
        logger.error("Solar→scenario adapter raised drift error: %s", e)
        # A wind temp file may have been minted before solar failed — the pipeline
        # ``finally`` will not run because we exit here, so clean up now.
        _cleanup_patched_scenarios(patched_scenario_paths)
        raise SystemExit(1) from e
    except (FileNotFoundError, RuntimeError, ValueError) as e:
        # Catches: missing solar_assessment_json, malformed solar export JSON,
        # scenario YAML parse error, a bad adapter_mode/scenario_name. Surface as
        # structured JSON consistent with the wind ingestion path so CI can parse the
        # failure uniformly.
        error_result = {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__,
            "phase": "solar_resource_ingestion",
            "config": str(config),
        }
        print(json.dumps(error_result, indent=2))
        logger.error("Solar→scenario ingestion failed: %s", e)
        _cleanup_patched_scenarios(patched_scenario_paths)
        raise SystemExit(1) from e

    validation_mode = cfg.get("validation_mode", "strict")

    modules_raw = cfg.get("validation_modules", None)
    if isinstance(modules_raw, str):
        validation_modules = [m.strip() for m in modules_raw.split(",") if m.strip()]
    elif modules_raw is None:
        validation_modules = None
    else:
        validation_modules = list(modules_raw)

    try:
        result = run_v14_pipeline(
            config=effective_config,
            validation_mode=str(validation_mode),
            validation_modules=validation_modules,
        )

        # Stamp an auditable run manifest (resolved-config hash + engine version +
        # commit) so summary.json is reproducible and tamper-evident (ICAEW posture).
        # Stamp-if-absent (#577): the engine now stamps the manifest itself from the
        # RESOLVED config it evaluated, which is the binding stamp and wins here.
        _stamp_manifest_if_absent(result, effective_config, str(validation_mode))

        write_artifacts = bool(cfg.get("write_artifacts", False))
        export_dir_raw = cfg.get("export_dir", "_out/run_full_pipeline_v14")

        # #656 (slice 3): optional single-scenario Executive Workbook emission.
        # OFF unless emit_executive_workbook=true (committed scenarios leave it
        # off → byte-identical). Reads no live ERA5: the resource-trend sheet is
        # sourced only from a long_term_trend block riding in the frozen wind
        # export (when one was supplied). Fails loudly on error, since the caller
        # explicitly opted into the workbook (CESSPIT).
        if emit_executive_workbook and isinstance(result, dict):
            workbook_out = (
                Path(str(executive_workbook_path))
                if executive_workbook_path
                else Path(str(export_dir_raw)) / "executive_workbook.xlsx"
            )
            wind_export_payload = (
                _read_wind_export_payload(resolved_wind_json_path)
                if resolved_wind_json_path is not None
                else None
            )
            written = emit_executive_workbook_from_pipeline(
                result, workbook_out, wind_export=wind_export_payload
            )
            result["executive_workbook_path"] = str(written)
            logger.info("Wrote Executive Workbook to %s", written)

        if write_artifacts:
            export_dir = Path(str(export_dir_raw))
            _safe_mkdir(export_dir)

            _write_json(export_dir / "summary.json", result)
            logger.info("Wrote summary.json to %s", export_dir / "summary.json")

            if isinstance(result, dict):
                if "kpis" in result:
                    _write_json(export_dir / "kpis.json", result.get("kpis"))
                    logger.info("Wrote kpis.json to %s", export_dir / "kpis.json")

                if "debt_result" in result:
                    _write_json(
                        export_dir / "debt_result.json", result.get("debt_result")
                    )
                    logger.info(
                        "Wrote debt_result.json to %s", export_dir / "debt_result.json"
                    )

                if "equity_distribution" in result:
                    _write_json(
                        export_dir / "equity_distribution.json",
                        result.get("equity_distribution"),
                    )
                    logger.info(
                        "Wrote equity_distribution.json to %s",
                        export_dir / "equity_distribution.json",
                    )

                if "annual_rows" in result:
                    _write_annual_rows_csv(
                        export_dir / "annual_rows.csv", result.get("annual_rows")
                    )
                    logger.info(
                        "Wrote annual_rows.csv to %s", export_dir / "annual_rows.csv"
                    )

            logger.info("All artifacts written to: %s", str(export_dir.resolve()))

        print(json.dumps(result, indent=2, sort_keys=True))

    except Exception as e:
        error_result = {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__,
            "config": str(config),
        }
        print(json.dumps(error_result, indent=2))
        logger.exception("Pipeline execution failed")
        raise SystemExit(1) from e
    finally:
        # Sprint 19 W.6 (#614: extended to wind + solar): clean up every temp
        # patched-scenario file (wind then solar). Done in a finally so it runs
        # whether the pipeline succeeded or raised.
        _cleanup_patched_scenarios(patched_scenario_paths)


if __name__ == "__main__":
    cli()
