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
import dataclasses
import json
import logging
import os
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Callable, cast

import hydra
import yaml
from omegaconf import DictConfig, OmegaConf

# Canonical lender-grade pipeline (analytics.pipeline_v14_enhanced).
from analytics.emit_selection import (
    STATUS_FAILED,
    STATUS_NOT_RUN,
    STATUS_OFF,
    emit_all_requested,
    plan_emitters,
    plan_report,
)
from analytics.executive_workbook import emit_executive_workbook_from_pipeline
from analytics.output_paths import DEFAULT_PIPELINE_OUTPUT_ROOT, resolve_output_dir
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


def _read_solar_export_payload(export_path: str | Path) -> dict[str, Any]:
    """Load the FULL frozen solar-export JSON (top-level, not just cashflow_export).

    The solar analogue of :func:`_read_wind_export_payload` (#727): the Executive
    Workbook step needs the top-level payload so it can read the optional
    ``long_term_trend`` block a solar producer freezes alongside its cashflow export
    (see ``analytics.executive_workbook.resource_trend_df_from_solar_export``). Pure
    read — no validation beyond "is a dict".
    """
    p = Path(export_path)
    with p.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(
            f"Solar export {export_path!r} did not parse to a dict "
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
    location = scenario_dict.get("wind_resource", {}).get(
        "location"
    ) or scenario_dict.get("project", {}).get("location")
    if not location:
        # #1759: no site default. A scenario that names no location used to run as one
        # particular site; the model is universal, so the scenario must say where it is.
        raise ValueError(
            "wind_auto_orchestrate needs the scenario to name its location "
            "(wind_resource.location or project.location); "
            f"{scenario_yaml_path} names none"
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


def _deep_merge_into(
    base: dict[str, Any], overlay: Mapping[str, Any]
) -> dict[str, Any]:
    """Recursively merge ``overlay`` into ``base`` (overlay wins); returns ``base``.

    Nested mappings merge key-by-key; every non-mapping value (scalars, lists)
    replaces the base value. Used to overlay CLI resource overrides onto a scenario's
    ``resource`` block without discarding sibling keys.
    """
    for key, value in overlay.items():
        existing = base.get(key)
        if isinstance(existing, dict) and isinstance(value, Mapping):
            _deep_merge_into(existing, value)
        else:
            base[key] = value
    return base


def _apply_resource_overrides_to_scenario(
    scenario_path: str | Path,
    resource_overrides: Mapping[str, Any],
) -> Path:
    """Overlay CLI ``resource_overrides`` onto the scenario's ``resource`` block (#683a).

    Deep-merges the override mapping into ``scenario['resource']`` (creating it if
    absent) so wind-resource knobs already drivable in the scenario YAML —
    ``uncertainty.*`` (IEC 61400-15-2 budget / P50 haircut) and the air-density
    corrections under ``wind`` — can also be set from the Hydra CLI without editing
    the committed scenario. Returns the path of a NEW temp file; the original scenario
    on disk is never touched. Cleaned up by the ``finally`` block in :func:`cli`.
    """
    scenario_dict = _load_yaml_scenario(scenario_path)
    resource = scenario_dict.get("resource")
    if not isinstance(resource, dict):
        resource = {}
    _deep_merge_into(resource, resource_overrides)
    scenario_dict["resource"] = resource

    src_dir = Path(scenario_path).resolve().parent
    tmp = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".patched.yaml",
        dir=str(src_dir),
        delete=False,
    )
    try:
        yaml.safe_dump(scenario_dict, tmp, sort_keys=False)
    finally:
        tmp.close()
    logger.info(
        "Resource overrides applied to scenario (keys=%s)",
        sorted(resource_overrides.keys()),
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


def _run_epc_only_scenario(cfg: DictConfig, config: str) -> bool:
    """Run an EPC-only scenario through the construction-margin model (#1780).

    The run follows the main path's rules (#1760): the emit switches are checked first, so
    a bad one exits 1 as it does for any scenario; each emitter is listed under
    ``result['emitters']`` with the reason it does not run; an earlier ``summary.json`` is
    removed before anything is computed, so a failed run leaves none behind; and the
    written summary carries a run manifest and lands in the resolved export directory.

    Args:
        cfg: The Hydra config.
        config: The scenario path.

    Returns:
        ``False`` when the scenario is not EPC-only (or cannot be read here), so the
        caller runs the full pipeline. ``True`` after printing the EPC-only result.

    Raises:
        SystemExit: Exit code 1 when the ``epc`` block does not compute.
        ValueError: An emit switch is not true, false or null.
    """
    from finance.epc_margin import epc_only_result, is_epc_only_scenario

    try:
        raw = _load_yaml_scenario(config)
    except (OSError, ValueError, yaml.YAMLError):
        return False
    if not is_epc_only_scenario(raw):
        return False

    write_artifacts = bool(cfg.get("write_artifacts", False))
    emit_all = emit_all_requested(cfg)
    plan = plan_emitters(cfg, {} if emit_all else None, write_artifacts=write_artifacts)
    export_dir = resolve_output_dir(
        cfg.get("export_dir", DEFAULT_PIPELINE_OUTPUT_ROOT),
        run_scoped=bool(cfg.get("run_scoped", False)),
        run_id=cfg.get("run_id", None),
    )
    if write_artifacts:
        stale = export_dir / "summary.json"
        if stale.is_file():
            stale.unlink()
            logger.info("Removed the earlier run's summary.json from %s", export_dir)

    result = epc_only_result(raw, config)
    result["run_manifest"] = build_run_manifest(
        raw, validation_mode=str(cfg.get("validation_mode", "strict"))
    ).as_dict()
    if emit_all or any(d.run for d in plan.values()):
        emitters: dict[str, dict[str, Any]] = {}
        for flag, decision in plan.items():
            keep = decision.status == STATUS_OFF or (
                decision.source == "emit_all" and not write_artifacts
            )
            emitters[flag] = (
                decision.as_dict()
                if keep
                else {
                    "status": STATUS_NOT_RUN,
                    "source": decision.source,
                    "reason": EPC_ONLY_EMITTER_REASON,
                }
            )
        result["emitters"] = emitters
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["status"] != "success":
        raise SystemExit(1)
    if write_artifacts:
        _safe_mkdir(export_dir)
        _write_json(export_dir / "summary.json", result)
    return True


#: Why no report or workbook emitter runs on an EPC-only scenario.
EPC_ONLY_EMITTER_REASON = (
    "an EPC-only scenario has no operating cashflow, which every report and workbook "
    "emitter reads"
)


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
                - write_artifacts: Write JSON/CSV files. The committed
                  conf sets it true, so a plain CLI run writes its figures and,
                  under emit_all (on by default), the workbook and every
                  applicable report. Only a config without the key falls back
                  to false (bool(cfg.get("write_artifacts", False))).
                - run_scoped: If true (#735 slice-2), group EVERY artifact of
                  this run — the JSON/CSV dump and the four optional
                  report/workbook emitters — under a per-run subdirectory of
                  export_dir so successive runs do not overwrite each other.
                  Default false → the export_dir root is used unchanged, so
                  committed-scenario output stays byte-identical.
                - run_id: Explicit run-scope subdirectory name; defaults to
                  analytics.output_paths.default_run_id() (v<engine>_<sha12>)
                  when run_scoped is set and this is omitted. Ignored when
                  run_scoped is false.
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
            Optional field (#1756 — one switch for all emitters; ON by default,
            owner ruling 2026-11-16; set emit_all=false to run none of them):
                - emit_all: If true (the default, also when unset), every emit_*
                  switch below that is left null turns on. An explicit switch wins. An emitter whose inputs the
                  run lacks is not run and is listed with its reason under
                  result['emitters']. The figures are written first; an emitter
                  that emit_all turns on and that fails is listed as failed and the
                  run completes, while one switched on explicitly still stops the
                  run when it fails. See analytics.emit_selection.
            Optional fields (#656 slice 3 — Executive Workbook emission; follows
            emit_all, so ON by default since #1756; KPIs are byte-identical either way):
                - emit_executive_workbook: If true, write a single-scenario
                  lender Executive Workbook (.xlsx) after a successful run via
                  analytics.executive_workbook.emit_executive_workbook_from_pipeline.
                  The five finance sheets come from the pipeline result; the
                  optional "ResourceTrend" sheet is added only when the supplied
                  frozen wind OR solar export carries a long_term_trend block
                  (#656 wind / #727 solar GHI; ONE sheet, wind-first on a hybrid).
                  No live ERA5/pvlib is run (the finance CLI stays cdsapi-/pvlib-
                  free). Default null (follows emit_all).
                - executive_workbook_path: Target .xlsx path. Default
                  '<export_dir>/executive_workbook.xlsx'. On emission the written
                  path is echoed back under result['executive_workbook_path'].
            Optional fields (#779 — capital-risk Monte-Carlo report emission; follows
            emit_all, so ON by default since #1756 for a scenario with
            monte_carlo.parameters; KPIs are byte-identical either way):
                - emit_capital_risk_report: If true, after a successful run run the
                  CANONICAL MC (analytics.mc.engine — LHS + Iman-Conover, with
                  monte_carlo.allow_toy_fallback forced false so a failed trial
                  raises rather than fabricating a toy metric) over a bounded trial
                  count and render a lender HTML report carrying the capital-risk
                  section, via app.reports.capital_risk_emit. Heavy (each trial is a
                  full evaluation), so batch-path only. Default null (follows emit_all).
                - capital_risk_report.n_trials: Bounded MC trial count for the
                  report tail (NOT the scenario's monte_carlo.n_scenarios). Default
                  2000 (app.reports.capital_risk_emit.DEFAULT_CAPITAL_RISK_N_TRIALS).
                  A lender-grade floor (LENDER_GRADE_MIN_TRIALS = 1000) is enforced:
                  a smaller n_trials fails loud rather than emitting a VaR/CVaR
                  number off a statistically inadequate tail.
                - capital_risk_report.seed: MC seed; defaults to the scenario's
                  monte_carlo.seed.
                - capital_risk_report.npv_metric: 'equity_npv' | 'project_npv' for
                  the NPV-distribution chart. Default 'equity_npv'.
                - capital_risk_report.path: Target .html path. Default
                  '<export_dir>/capital_risk_report.html'. On emission the written
                  path is echoed back under result['capital_risk_report_path'].
            Optional fields (#1752 — the combined lender report, HTML and a DBPL-01
            PDF; follows emit_all, so ON by default for every run with figures; KPIs
            are byte-identical either way):
                - emit_lender_report: If true, after a successful run render the same
                  combined lender report POST /v1/cases/report.pdf builds, through
                  app.reports.report_orchestration (production sensitivity profile:
                  tornado, Morris, PAWN) plus the capital-risk section, via
                  app.reports.lender_report_emit. The Monte Carlo is the capital-risk
                  emitter's own when it ran in this run, otherwise run here under the
                  same lender guards and capital_risk_report settings. Every section
                  left out is listed on the report with its reason. The PDF goes
                  through the DBPL print core; under emit_all a missing [report]
                  extra leaves the HTML and records why there is no PDF, and switched
                  on by name it fails loud. Default null (follows emit_all).
                - lender_report.path: Target .html path. Default
                  '<export_dir>/lender_report.html'. The PDF is written beside it
                  with a .pdf suffix. On emission the record is echoed back under
                  result['lender_report'].
            Optional fields (#739 slice-2 — two-factor interaction-grid report
            emission; follows emit_all, so ON by default since #1756 for a scenario
            with an interaction_grid block; KPIs are byte-identical either way):
                - emit_interaction_grid: If true, after a successful run build the
                  two-factor sensitivity interaction grid (N×M full-pipeline
                  evaluations — heavy, batch-path only, never the synchronous HTTP
                  report route; the #645 latency ledger) and render a lender HTML
                  report carrying the interaction-grid section, via
                  app.reports.interaction_grid_emit. The two drivers and the metric
                  are config-required (the scenario's 'interaction_grid' block); no
                  default pair is imposed, and a missing/malformed block fails loud.
                  Default null (follows emit_all).
                - interaction_grid_report.path: Target .html path. Default
                  '<export_dir>/interaction_grid_report.html'. On emission the written
                  path is echoed back under result['interaction_grid_report_path'].

            Optional fields (#745 slice-1 — cross-technology headline-KPI comparison
            report emission; follows emit_all, so ON by default since #1756 when
            tech_comparison.scenarios is listed; KPIs are byte-identical either way):
                - emit_tech_comparison: If true, after a successful run render a lender
                  HTML report carrying a side-by-side headline-KPI comparison of the
                  compared configs, via app.reports.tech_comparison_emit. Each compared
                  config is run through the CANONICAL pipeline (strict), so every column
                  reconciles to that config's own committed headline KPIs (the multiple
                  full-pipeline runs are heavy — batch-path only, never the synchronous
                  HTTP report route; the #645 latency ledger). The compared scenarios are
                  config-required (tech_comparison.scenarios); no default pair is imposed,
                  and an absent/empty/malformed list or a missing scenario path fails loud.
                  Default null (follows emit_all).
                - tech_comparison.scenarios: A non-empty list of {label, config} entries
                  naming the configs to compare (config-required; this slice compares the
                  wind lender case + the hybrid case that exist — solar-only and
                  hybrid-plus-BESS are a deferred follow-up).
                - tech_comparison.path: Target .html path. Default
                  '<export_dir>/tech_comparison_report.html'. On emission the written path
                  is echoed back under result['tech_comparison_report_path'].

            Optional fields (#884 D8 — advisory GRID-SCREENING report emission; follows
            emit_all, so ON by default since #1756 for a scenario whose grid block has
            study_enabled: true; KPIs are BYTE-IDENTICAL either way; the grid study is advisory
            (bankable=false) and NEVER feeds finance, so no committed KPI moves):
                - emit_grid_screen: If true, after a successful run compose the in-house
                  design-stage grid screens (SCR@POC / GFL-vs-GFM, reactive/PQ-box Mvar
                  shortfall, SCR-coupled harmonics/flicker, RMS ride-through, hybrid-POC
                  composite-SCR, combined frequency-droop, QSTS curtailment split) and
                  render a STANDALONE advisory HTML report, via
                  app.reports.grid_screening_emit. Requires the scenario's grid block with
                  study_enabled: true (fails loud otherwise — CESSPIT). The heavy screens
                  (pandapower / ANDES / OpenDSS) live on this batch path only, never the
                  synchronous HTTP report route (the #645 latency ledger); a missing [grid]
                  engine degrades that screen to an honest 'not run' state (CASPER), it does
                  not crash. Every grid surface carries the un-suppressible SCREENING-not-
                  bankable + EMT-gap caveat + dependency/verification provenance. Default null (follows emit_all).
                - grid_screen_report.path: Target .html path. Default
                  '<export_dir>/grid_screening_report.html'. On emission the written path is
                  echoed back under result['grid_screening_report_path'].

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

    # #1780: an EPC-only scenario (an epc block and no operating project) is a
    # construction-margin deal with no operating cashflow, so it runs the margin model
    # alone and prints its result; it exits 1 when the block does not compute. A file
    # that cannot be read here falls through, so the pipeline reports it as before.
    if _run_epc_only_scenario(cfg, str(config)):
        return

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
    # (follows emit_all, #1756). When on, after a successful finance run this CLI
    # writes a lender-facing .xlsx via
    # analytics.executive_workbook.emit_executive_workbook_from_pipeline —
    # the genuine live caller of build_executive_workbook. The five finance
    # sheets are assembled from the pipeline result; the optional
    # "ResourceTrend" sheet is added only when a supplied frozen wind export
    # carries a long_term_trend block. Emission derives no financial value and
    # never mutates KPIs, so the KPIs and the JSON/CSV dump are byte-identical
    # with it on or off.
    # ------------------------------------------------------------------
    # #1756: every emit_* switch is read through analytics.emit_selection, which adds
    # emit_all (one switch for all emitters). An explicit switch wins over emit_all; an unset
    # one follows it. emit_all is on by default (owner ruling 2026-11-16); with it off each
    # switch behaves exactly as it did before #1756.
    # This early plan validates the switches before the finance run; under emit_all the plan
    # is made again against the effective scenario just before the emitters run.
    # With write_artifacts=false, emit_all switches nothing on (#1760 assurance L-1): a run that
    # writes no figures writes no report either, as on main; a switch set by name still runs.
    emit_all = emit_all_requested(cfg)
    emit_plan = plan_emitters(
        cfg,
        {} if emit_all else None,
        write_artifacts=bool(cfg.get("write_artifacts", False)),
    )
    emit_executive_workbook = emit_plan["emit_executive_workbook"].run
    executive_workbook_path = cfg.get("executive_workbook_path", None)

    # ------------------------------------------------------------------
    # #779: optional capital-risk (Monte-Carlo) report emission (follows emit_all, #1756).
    # When true, after a successful finance run this CLI runs the CANONICAL MC
    # (analytics.mc.engine, allow_toy_fallback forced false — no fabricated
    # trials) over a BOUNDED trial count and renders a lender HTML report that
    # carries the capital-risk section, via app.reports.capital_risk_emit. It is
    # heavy (each trial is a full v14 evaluation), so it belongs in this batch
    # path, never the synchronous HTTP report route. Emission derives no committed
    # KPI, so the KPIs are byte-identical with it on or off.
    # ------------------------------------------------------------------
    emit_capital_risk_report = emit_plan["emit_capital_risk_report"].run
    capital_risk_report_cfg = cfg.get("capital_risk_report", None) or {}

    # #1752: the combined lender report (follows emit_all). It reuses the capital-risk Monte
    # Carlo of this run when that emitter ran, and lists every section it left out.
    emit_lender_report = emit_plan["emit_lender_report"].run
    lender_report_cfg = cfg.get("lender_report", None) or {}

    # #739 slice-2: optional two-factor interaction-grid report emission (follows emit_all); the
    # drivers/metric are config-required (interaction_grid block), no default pair is imposed.
    emit_interaction_grid = emit_plan["emit_interaction_grid"].run
    interaction_grid_cfg = cfg.get("interaction_grid_report", None) or {}

    # #683 (a): optional CLI-overridable wind-resource knobs. A ``resource_overrides``
    # mapping (uncertainty budget / P50 haircut, air-density corrections, ...) is
    # deep-merged onto the scenario's ``resource`` block, so knobs already drivable in
    # the scenario YAML can also be set from the CLI. OFF by default (null) — when unset
    # the original scenario path flows straight through, byte-identical.
    resource_overrides = cfg.get("resource_overrides", None)

    # #745 slice-1: optional cross-technology headline-KPI comparison report emission (follows
    # emit_all); the compared scenarios are config-required (tech_comparison.scenarios list of
    # {label, config} entries), no default scenario pair is imposed. Each compared config is run
    # through the CANONICAL pipeline (strict), so every column reconciles to that config's own
    # committed headline KPIs (the lender-integrity basis, per #745).
    emit_tech_comparison = emit_plan["emit_tech_comparison"].run
    tech_comparison_cfg = cfg.get("tech_comparison", None) or {}

    # #884 D8: optional advisory grid-screening report emission (follows emit_all); the study is
    # advisory (bankable=false) and NEVER feeds finance, so the KPIs are byte-identical with it
    # on or off. Requires the scenario's grid block with study_enabled: true (under emit_all a
    # scenario without it is listed as not run; switched on explicitly, it fails loud). The heavy screens are on this
    # batch path only; a missing [grid] engine degrades gracefully (CASPER).
    emit_grid_screen = emit_plan["emit_grid_screen"].run
    grid_screen_cfg = cfg.get("grid_screen_report", None) or {}

    effective_config: str = str(config)
    # Temp patched-scenario files (resource-overrides then wind then solar) to clean up
    # in ``finally``.
    patched_scenario_paths: list[Path] = []
    # Resolved frozen wind-/solar-export path (if any), captured for the optional
    # Executive Workbook step so it can read the long_term_trend block from either
    # (#656 wind / #727 solar). The workbook fills ONE ResourceTrend sheet, wind-first.
    resolved_wind_json_path: Path | None = None
    resolved_solar_json_path: Path | None = None
    try:
        # #683 (a): apply CLI resource overrides FIRST so any subsequent wind/solar
        # patch builds on the overridden resource block. Empty/absent -> no-op ->
        # the original scenario path flows through unchanged (byte-identical).
        if resource_overrides:
            overrides_dict = OmegaConf.to_container(resource_overrides, resolve=True)
            if not isinstance(overrides_dict, Mapping):
                raise ValueError(
                    "resource_overrides must be a mapping (e.g. "
                    "'resource_overrides={uncertainty:{p50_haircut_pct:0.05}}'); "
                    f"got {type(overrides_dict).__name__}"
                )
            resource_patched_path = _apply_resource_overrides_to_scenario(
                scenario_path=config,
                resource_overrides=cast(Mapping[str, Any], overrides_dict),
            )
            patched_scenario_paths.append(resource_patched_path)
            config = str(resource_patched_path)
            effective_config = str(resource_patched_path)
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
                        str(cfg.get("export_dir", DEFAULT_PIPELINE_OUTPUT_ROOT))
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
            resolved_solar_json_path = solar_json_path
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
        export_dir_raw = cfg.get("export_dir", DEFAULT_PIPELINE_OUTPUT_ROOT)

        # #735 slice-2: resolve the artifact directory ONCE, up front, so every
        # pipeline artifact — the four report/workbook emitters below AND the
        # JSON/CSV dump block — co-scopes under the same directory. At the
        # default (run_scoped=False) the resolver returns export_dir_raw
        # unchanged, so committed runs write to exactly the same paths
        # (byte-identical); opt-in run-scoping (run_scoped/run_id cfg knobs,
        # default off) groups the whole run under one reproducible subdirectory
        # instead of scattering the JSON block into a scoped dir while the
        # reports land un-scoped. Only the DEFAULT report paths are derived from
        # this; an explicit user-supplied path still wins unchanged (below).
        export_dir_scoped = resolve_output_dir(
            export_dir_raw,
            run_scoped=bool(cfg.get("run_scoped", False)),
            run_id=cfg.get("run_id", None),
        )

        # #1756: the figures are written BEFORE the emitter plan and before any emitter runs, so
        # nothing an analysis does (planning included) can stop them being written (owner ruling
        # 2026-11-16 07:15Z). summary.json, which records the emitters' outcome, is written after.
        if write_artifacts:
            # #735: route through the single-source resolver. Default (run_scoped=False) returns
            # the configured root unchanged, so committed runs write to the same paths
            # (byte-identical). Slice-2: reuse the one export_dir_scoped resolved up front so the
            # JSON/CSV block co-scopes with the four report emitters under the same directory.
            export_dir = export_dir_scoped
            _safe_mkdir(export_dir)
            # #1760 assurance M-1: summary.json records this run's outcome and is written last,
            # so one left by an earlier run is removed now. A run that stops before the end
            # (an emitter switched on by name that fails) then leaves no summary that
            # describes another run beside this run's figures.
            stale_summary = export_dir / "summary.json"
            if stale_summary.is_file():
                stale_summary.unlink()
                logger.info(
                    "Removed the earlier run's summary.json from %s", export_dir
                )

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

        # #1756: under emit_all, decide which emitters apply to this run from the effective
        # scenario. One whose inputs are absent is recorded as not run with its reason; one that
        # applies runs and, if it fails, is recorded as failed (below). The plan is recorded under
        # result['emitters'] whenever emit_all is on, which is the default; a run with
        # emit_all=false records no plan and is byte-identical to the behaviour before #1756.
        if emit_all and isinstance(result, dict):
            # The engine read this scenario file earlier in the run; if it cannot be read
            # again, every emitter emit_all would switch on is listed as not run with the
            # reason, and the run goes on (#1760 assurance M-2 audit at cf357629).
            replan_error: str | None = None
            try:
                replan_scenario = dict(load_scenario_config(str(effective_config)))
            except (
                Exception
            ) as exc:  # noqa: BLE001 - listed with its reason, never silent
                replan_scenario = {}
                replan_error = (
                    "the effective scenario cannot be read again to plan the emitters: "
                    f"{type(exc).__name__}: {exc}"
                )
            emit_plan = plan_emitters(
                cfg, replan_scenario, write_artifacts=write_artifacts
            )
            if replan_error is not None:
                emit_plan = {
                    flag: (
                        dataclasses.replace(
                            decision,
                            run=False,
                            status=STATUS_NOT_RUN,
                            reason=replan_error,
                        )
                        if decision.source == "emit_all"
                        else decision
                    )
                    for flag, decision in emit_plan.items()
                }
            emit_executive_workbook = emit_plan["emit_executive_workbook"].run
            emit_capital_risk_report = emit_plan["emit_capital_risk_report"].run
            emit_lender_report = emit_plan["emit_lender_report"].run
            emit_interaction_grid = emit_plan["emit_interaction_grid"].run
            emit_tech_comparison = emit_plan["emit_tech_comparison"].run
            emit_grid_screen = emit_plan["emit_grid_screen"].run
            result["emitters"] = plan_report(emit_plan)
            for decision in emit_plan.values():
                if decision.status == STATUS_NOT_RUN:
                    logger.info(
                        "emit_all: %s not run (%s)", decision.flag, decision.reason
                    )

        # #1756 / #1760 (domain D-2, assurance M-1): which default-path files this run owns.
        # The default export directory is shared between runs. One rule decides what a run
        # does with an emitter's default-path outputs (the workbook, each report and its
        # companion files under export_dir):
        #
        # * Under emit_all, when the run writes its figures, every default path is this run's.
        #   All are cleared up front, before any emitter runs, so whatever is left there after
        #   the run was written by this run, even if an emitter switched on by name then stops
        #   it. Each emitter that ends without writing to its default path (not run, failed,
        #   switched off by name, or writing to a configured path) lists what was cleared under
        #   ``removed_stale_outputs``; one that failed is cleared again, of anything it wrote
        #   before failing.
        # * Otherwise (emit_all=false, or write_artifacts=false), an emitter that is attempted
        #   at its default path clears its own default-path outputs first, so a failure cannot
        #   leave an earlier run's file there; nothing else is touched.
        # * A configured path is the caller's and is never cleared. A default-path file beside
        #   it is cleared like any other (#1760 domain D-1 at 7c595118); if the emitter then
        #   writes a companion file there (the capital-risk PNG), it is this run's and is not
        #   listed as removed.
        from analytics.contracts_v14 import QSTS_SYNTHETIC_OUTPUT_CLASS

        unreadable: set[str] = set()

        def _read_optional(block: Any, key: str, default: Any, where: str) -> Any:
            # Every config read between the figures and summary.json that is not inside an
            # emitter goes through here (#1760 assurance M-2 at cf357629). These reads only
            # say which default-path files to keep or clear, so a value that cannot be read
            # (a malformed block, or an interpolation such as ${oc.env:...} that does not
            # resolve) falls back to the default and is logged; it never stops the run. An
            # emitter that runs reads the same key itself, inside _run_emitter, and fails
            # there as before (#1760 domain D-1 for malformed blocks).
            if not isinstance(block, Mapping):
                return default
            try:
                return block.get(key, default)
            except Exception as exc:  # noqa: BLE001 - logged, never silent
                unreadable.add(where)
                logger.warning(
                    "%s.%s cannot be read (%s: %s); using %r to decide which default"
                    " outputs to clear",
                    where,
                    key,
                    type(exc).__name__,
                    exc,
                    default,
                )
                return default

        configured_paths: dict[str, Any] = {
            "emit_executive_workbook": executive_workbook_path,
            "emit_capital_risk_report": _read_optional(
                capital_risk_report_cfg, "path", None, "capital_risk_report"
            ),
            "emit_lender_report": _read_optional(
                lender_report_cfg, "path", None, "lender_report"
            ),
            "emit_interaction_grid": _read_optional(
                interaction_grid_cfg, "path", None, "interaction_grid_report"
            ),
            "emit_tech_comparison": _read_optional(
                tech_comparison_cfg, "path", None, "tech_comparison"
            ),
            "emit_grid_screen": _read_optional(
                grid_screen_cfg, "path", None, "grid_screen_report"
            ),
        }
        config_block_of = {
            "emit_capital_risk_report": "capital_risk_report",
            "emit_lender_report": "lender_report",
            "emit_interaction_grid": "interaction_grid_report",
            "emit_tech_comparison": "tech_comparison",
            "emit_grid_screen": "grid_screen_report",
        }
        npv_metric = _read_optional(
            capital_risk_report_cfg, "npv_metric", "equity_npv", "capital_risk_report"
        )
        default_outputs: dict[str, list[Path]] = {
            "emit_executive_workbook": [export_dir_scoped / "executive_workbook.xlsx"],
            "emit_capital_risk_report": [
                export_dir_scoped / "capital_risk_report.html",
                export_dir_scoped / "npv_distribution_{}.png".format(npv_metric),
            ],
            "emit_lender_report": [
                export_dir_scoped / "lender_report.html",
                export_dir_scoped / "lender_report.pdf",
                export_dir_scoped
                / "lender_report_files"
                / "npv_distribution_{}.png".format(npv_metric),
            ],
            "emit_interaction_grid": [
                export_dir_scoped / "interaction_grid_report.html"
            ],
            "emit_tech_comparison": [export_dir_scoped / "tech_comparison_report.html"],
            "emit_grid_screen": [
                export_dir_scoped / "grid_screening_report.html",
                export_dir_scoped
                / QSTS_SYNTHETIC_OUTPUT_CLASS
                / "grid_screening_report.html",
            ],
        }

        def _clear_default_outputs(flag: str) -> list[Path]:
            configured = configured_paths.get(flag)
            kept = Path(str(configured)).resolve() if configured else None
            removed: list[Path] = []
            for stale in default_outputs.get(flag, []):
                # Only the configured file itself is the caller's (#1760 domain D-1 at
                # 7c595118): a default-path file beside it is still cleared.
                if kept is not None and stale.resolve() == kept:
                    continue
                if stale.is_file():
                    stale.unlink()
                    removed.append(stale)
            return removed

        def _shown(stale: Path) -> str:
            # Listed relative to the export directory, so the grid screen's two reports of
            # the same name stay apart (#1760 assurance L-1 at 7c595118).
            return stale.relative_to(export_dir_scoped).as_posix()

        owns_default_paths = (
            emit_all
            and write_artifacts
            and isinstance(result, dict)
            and isinstance(result.get("emitters"), dict)
        )
        cleared_up_front: dict[str, list[Path]] = {}
        if owns_default_paths:
            for flag in default_outputs:
                cleared_up_front[flag] = _clear_default_outputs(flag)

        # #1756: an emitter switched on by emit_all (the default) that raises is recorded as
        # failed, with its error, under result['emitters'] and logged as an error; the run
        # carries on, and its figures are already written. An emitter switched on explicitly
        # still stops the run on failure (FRAMEWORK-02), as before #1756.
        def _run_emitter(flag: str, emit: Callable[[], None]) -> None:
            # Outside emit_all's ownership, a default path is cleared only for an emitter that
            # is attempted there: not when a path is configured, nor when the configured path
            # could not be read (the emitter then fails reading it, as before #1756).
            if (
                not owns_default_paths
                and not configured_paths.get(flag)
                and config_block_of.get(flag) not in unreadable
            ):
                for stale in _clear_default_outputs(flag):
                    logger.info(
                        "%s: removed earlier output %s before running",
                        flag,
                        _shown(stale),
                    )
            if emit_plan[flag].source != "emit_all" or not isinstance(result, dict):
                emit()
                return
            try:
                emit()
            except Exception as exc:  # noqa: BLE001 - recorded and logged, never silent
                reason = f"{type(exc).__name__}: {exc}"
                logger.error("emit_all: %s failed (%s)", flag, reason)
                result["emitters"][flag] = {
                    "status": STATUS_FAILED,
                    "source": "emit_all",
                    "reason": reason,
                }

        # #656 (slice 3): optional single-scenario Executive Workbook emission.
        # OFF unless emit_executive_workbook=true (committed scenarios leave it
        # off → byte-identical). Reads no live ERA5: the resource-trend sheet is
        # sourced only from a long_term_trend block riding in the frozen wind
        # export (when one was supplied). Fails loudly on error, since the caller
        # explicitly opted into the workbook (CESSPIT).
        if emit_executive_workbook and isinstance(result, dict):

            def _emit_executive_workbook() -> None:
                workbook_out = (
                    Path(str(executive_workbook_path))
                    if executive_workbook_path
                    else export_dir_scoped / "executive_workbook.xlsx"
                )
                wind_export_payload = (
                    _read_wind_export_payload(resolved_wind_json_path)
                    if resolved_wind_json_path is not None
                    else None
                )
                # #727: a frozen solar export can ALSO carry a long_term_trend block (GHI
                # dimming/brightening). The workbook fills ONE ResourceTrend sheet; wind
                # takes precedence when both are present (see the HYBRID note in
                # emit_executive_workbook_from_pipeline). Solar-only runs fill it from solar.
                solar_export_payload = (
                    _read_solar_export_payload(resolved_solar_json_path)
                    if resolved_solar_json_path is not None
                    else None
                )
                written = emit_executive_workbook_from_pipeline(
                    result,
                    workbook_out,
                    wind_export=wind_export_payload,
                    solar_export=solar_export_payload,
                )
                result["executive_workbook_path"] = str(written)
                logger.info("Wrote Executive Workbook to %s", written)

            _run_emitter("emit_executive_workbook", _emit_executive_workbook)

        # #779: optional capital-risk (Monte-Carlo) report emission. OFF unless
        # emit_capital_risk_report=true (committed scenarios leave it off →
        # byte-identical). Runs the canonical MC (allow_toy_fallback forced false)
        # over a bounded n and renders a lender report with the capital-risk
        # section. Fails loud on error, since the caller explicitly opted in
        # (CESSPIT). Imported lazily so the report stack (jinja/matplotlib) is not
        # pulled onto the finance CLI's import path unless this step runs.
        # #1752: the capital-risk emitter hands its report here, so the lender report below
        # reuses this run's Monte Carlo rather than running a second one.
        shared_capital_risk: list[Any] = []
        if emit_capital_risk_report and isinstance(result, dict):

            def _emit_capital_risk_report() -> None:
                from app.reports.capital_risk_emit import (
                    DEFAULT_CAPITAL_RISK_N_TRIALS,
                    emit_capital_risk_report_from_pipeline,
                )

                cr_path_raw = capital_risk_report_cfg.get("path", None)
                cr_out = (
                    Path(str(cr_path_raw))
                    if cr_path_raw
                    else export_dir_scoped / "capital_risk_report.html"
                )
                cr_seed_raw = capital_risk_report_cfg.get("seed", None)
                cr_written = emit_capital_risk_report_from_pipeline(
                    result,
                    effective_config,
                    cr_out,
                    n_trials=int(
                        capital_risk_report_cfg.get(
                            "n_trials", DEFAULT_CAPITAL_RISK_N_TRIALS
                        )
                    ),
                    seed=int(cr_seed_raw) if cr_seed_raw is not None else None,
                    npv_metric=str(
                        capital_risk_report_cfg.get("npv_metric", "equity_npv")
                    ),
                    on_report=shared_capital_risk.append,
                )
                result["capital_risk_report_path"] = str(cr_written)
                logger.info("Wrote capital-risk report to %s", cr_written)

            _run_emitter("emit_capital_risk_report", _emit_capital_risk_report)

        # #1752: the combined lender report, HTML and a DBPL-01 PDF. The same sections as
        # POST /v1/cases/report.pdf, through app.reports.report_orchestration, plus the
        # capital-risk section. The Monte Carlo is the one the capital-risk emitter ran above
        # when it ran; if that emitter failed, the section is listed as not run rather than
        # run a second time. Imported lazily so the report stack stays off the finance CLI's
        # import path unless this step runs.
        if emit_lender_report and isinstance(result, dict):

            def _emit_lender_report() -> None:
                from app.reports.lender_report_emit import (
                    LENDER_REPORT_HTML_NAME,
                    capital_structure_settings_from_config,
                    emit_lender_report_from_pipeline,
                    lender_sensitivity_settings_from_config,
                )

                lr_path_raw = lender_report_cfg.get("path", None)
                lr_out = (
                    Path(str(lr_path_raw))
                    if lr_path_raw
                    else export_dir_scoped / LENDER_REPORT_HTML_NAME
                )
                cr_entry = (result.get("emitters") or {}).get(
                    "emit_capital_risk_report"
                )
                cr_not_run = None
                if not shared_capital_risk and isinstance(cr_entry, dict):
                    # Never re-attempt a Monte Carlo this run already declined or failed:
                    # list the capital-risk emitter's own reason instead.
                    if cr_entry.get("status") == STATUS_FAILED:
                        cr_not_run = (
                            "not run: the capital-risk Monte Carlo failed in this run ("
                            f"{cr_entry.get('reason')})"
                        )
                    elif cr_entry.get("status") == STATUS_NOT_RUN:
                        cr_not_run = f"not run: {cr_entry.get('reason')}"
                cr_seed_raw = capital_risk_report_cfg.get("seed", None)
                cr_trials_raw = capital_risk_report_cfg.get("n_trials", None)
                written = emit_lender_report_from_pipeline(
                    result,
                    effective_config,
                    lr_out,
                    capital_risk=(
                        shared_capital_risk[0] if shared_capital_risk else None
                    ),
                    capital_risk_not_run=cr_not_run,
                    n_trials=int(cr_trials_raw) if cr_trials_raw is not None else None,
                    seed=int(cr_seed_raw) if cr_seed_raw is not None else None,
                    npv_metric=str(
                        capital_risk_report_cfg.get("npv_metric", "equity_npv")
                    ),
                    require_pdf=emit_plan["emit_lender_report"].source != "emit_all",
                    capital_structure=capital_structure_settings_from_config(
                        lender_report_cfg.get("capital_structure", None)
                    ),
                    sensitivities=lender_sensitivity_settings_from_config(
                        lender_report_cfg.get("sensitivities", None)
                    ),
                )
                result["lender_report"] = written.as_dict()
                logger.info("Wrote lender report to %s", written.html_path)
                if written.pdf_path is not None:
                    logger.info("Wrote lender report PDF to %s", written.pdf_path)
                else:
                    logger.warning(
                        "Lender report PDF not written: %s", written.pdf_not_written
                    )
                    lr_entry = (result.get("emitters") or {}).get("emit_lender_report")
                    if isinstance(lr_entry, dict):
                        lr_entry["pdf_not_written"] = written.pdf_not_written

            _run_emitter("emit_lender_report", _emit_lender_report)

        # #739 slice-2: optional two-factor interaction-grid report emission. OFF unless
        # emit_interaction_grid=true (committed scenarios leave it off → byte-identical). Builds
        # the grid (N×M full-pipeline evaluations — heavy, batch-path only, never the synchronous
        # HTTP report route; the #645 latency ledger) from the config-required interaction_grid
        # block and renders a lender report with that section. Fails loud on a missing/malformed
        # block, since the caller explicitly opted in (CESSPIT). Imported lazily so the report
        # stack is not pulled onto the finance CLI's import path unless this step runs.
        if emit_interaction_grid and isinstance(result, dict):

            def _emit_interaction_grid() -> None:
                from app.reports.interaction_grid_emit import (
                    emit_interaction_grid_report_from_pipeline,
                )

                ig_path_raw = interaction_grid_cfg.get("path", None)
                ig_out = (
                    Path(str(ig_path_raw))
                    if ig_path_raw
                    else export_dir_scoped / "interaction_grid_report.html"
                )
                ig_written = emit_interaction_grid_report_from_pipeline(
                    result,
                    effective_config,
                    ig_out,
                )
                result["interaction_grid_report_path"] = str(ig_written)
                logger.info("Wrote interaction-grid report to %s", ig_written)

            _run_emitter("emit_interaction_grid", _emit_interaction_grid)

        # #745 slice-1: optional cross-technology headline-KPI comparison report emission. OFF
        # unless emit_tech_comparison=true (committed scenarios leave it off → byte-identical).
        # Runs the CANONICAL pipeline per compared config (heavy multi-run — batch-path only, never
        # the synchronous HTTP report route; the #645 latency ledger) so every column reconciles to
        # that config's own committed headline KPIs, and renders a lender report with that section.
        # Fails loud on an absent/empty/malformed scenarios list or a missing scenario path, since
        # the caller explicitly opted in (CESSPIT). Imported lazily so the report stack is not
        # pulled onto the finance CLI's import path unless this step runs.
        if emit_tech_comparison and isinstance(result, dict):

            def _emit_tech_comparison() -> None:
                from app.reports.tech_comparison_emit import (
                    emit_tech_comparison_report_from_pipeline,
                )

                tc_path_raw = tech_comparison_cfg.get("path", None)
                tc_out = (
                    Path(str(tc_path_raw))
                    if tc_path_raw
                    else export_dir_scoped / "tech_comparison_report.html"
                )
                tc_written = emit_tech_comparison_report_from_pipeline(
                    result,
                    effective_config,
                    tc_out,
                    scenarios=tech_comparison_cfg.get("scenarios", None),
                )
                result["tech_comparison_report_path"] = str(tc_written)
                logger.info("Wrote tech-comparison report to %s", tc_written)

            _run_emitter("emit_tech_comparison", _emit_tech_comparison)

        # #884 D8: optional advisory grid-screening report emission. OFF unless
        # emit_grid_screen=true (committed scenarios leave it off → byte-identical). The grid
        # study is ADVISORY (bankable=false) and NEVER feeds finance (CFADS/IRR/DSCR unchanged),
        # so emission derives no committed KPI. Composes the in-house grid screens and writes a
        # STANDALONE advisory HTML report carrying the un-suppressible SCREENING-not-bankable +
        # EMT-gap caveat + dependency/verification provenance. Fails loud on a missing/disabled
        # grid block, since the caller explicitly opted in (CESSPIT). Heavy screens (pandapower/
        # ANDES/OpenDSS) run here on the batch path only, never the synchronous HTTP report route
        # (the #645 latency ledger); a missing [grid] engine degrades that screen (CASPER), not
        # crashes. Imported lazily so the report stack is not pulled onto the finance CLI's import
        # path unless this step runs.
        if emit_grid_screen and isinstance(result, dict):

            def _emit_grid_screen() -> None:
                from app.reports.grid_screening_emit import (
                    emit_grid_screening_report_from_pipeline,
                )

                gs_path_raw = grid_screen_cfg.get("path", None)
                gs_out = (
                    Path(str(gs_path_raw))
                    if gs_path_raw
                    else export_dir_scoped / "grid_screening_report.html"
                )
                gs_written = emit_grid_screening_report_from_pipeline(
                    result,
                    effective_config,
                    gs_out,
                )
                result["grid_screening_report_path"] = str(gs_written)
                logger.info("Wrote grid-screening report to %s", gs_written)

            _run_emitter("emit_grid_screen", _emit_grid_screen)

        # #1756 / #1760: record, on each emitter that did not write to its default path, the
        # earlier outputs this run cleared there (the rule above).
        if owns_default_paths and isinstance(result, dict):
            for flag, entry in result["emitters"].items():
                if not isinstance(entry, dict):
                    continue
                source, status = entry.get("source"), entry.get("status")
                failed = source == "emit_all" and status == STATUS_FAILED
                if not (
                    (source == "emit_all" and status in (STATUS_NOT_RUN, STATUS_FAILED))
                    or (source == "explicit" and status == STATUS_OFF)
                    or configured_paths.get(flag)
                ):
                    continue
                # A cleared file that the emitter wrote again (a companion file beside a
                # configured path, such as the capital-risk PNG) is this run's, not stale.
                removed = [
                    _shown(stale)
                    for stale in cleared_up_front.get(flag, [])
                    if not stale.exists()
                ]
                if failed:
                    removed += [
                        _shown(stale)
                        for stale in _clear_default_outputs(flag)
                        if _shown(stale) not in removed
                    ]
                if removed:
                    entry["removed_stale_outputs"] = removed
                    logger.info(
                        "emit_all: %s %s; removed earlier output %s",
                        flag,
                        entry.get("status"),
                        ", ".join(removed),
                    )

        if write_artifacts:
            _write_json(export_dir_scoped / "summary.json", result)
            logger.info("Wrote summary.json to %s", export_dir_scoped / "summary.json")
            logger.info(
                "All artifacts written to: %s", str(export_dir_scoped.resolve())
            )

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
