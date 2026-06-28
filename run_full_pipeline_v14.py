"""Hydra CLI for Complete Wind-to-Finance Pipeline.

Entrypoint for running the complete DutchBay wind farm assessment and
financial analysis. Integrates:

- Wind-resource frozen-export ingestion (consumes JSON produced by
  ``scripts/run_wind_analysis_v14.py``; never calls Copernicus directly)
- Optional auto-orchestration: when ``wind_auto_orchestrate=true`` and the
  ``[wind]`` extra is installed, this CLI subprocesses the wind producer
  to mint a fresh frozen export before the finance run
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

# CRITICAL FIX: Import lender-grade pipeline (was: analytics.pipeline_v14)
from analytics.pipeline_v14_enhanced import run_v14_pipeline
from analytics.run_manifest import build_run_manifest
from analytics.scenario_loader import load_scenario_config

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
        location, export_scenario,
    )
    proc = subprocess.run(
        [
            sys.executable, str(producer),
            f"location={location}",
            f"export_scenario={export_scenario}",
        ],
        capture_output=True, text=True, env=env, check=False,
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
        adapter_mode, tolerance_pct, scenario_name,
    )
    return Path(tmp.name)


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

    Returns:
        None. Prints JSON result to stdout. Optionally writes artifacts.
        On wind-ingestion failure, prints a structured error JSON with
        ``status='error'`` and ``phase='wind_resource_ingestion'`` (or
        ``error_type='WindAdapterDriftError'`` for drift failures) and
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
                "[wind_export_scenario=P75]"
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

    effective_config: str = str(config)
    patched_scenario_path: Path | None = None
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
                    output_dir=Path(str(cfg.get("export_dir", "_out/run_full_pipeline_v14"))) / "wind_export",
                )

            patched_scenario_path = _apply_wind_to_scenario(
                scenario_path=config,
                wind_export_path=wind_json_path,
                adapter_mode=adapter_mode,
                tolerance_pct=wind_tolerance_pct,
                scenario_name=wind_export_scenario,
            )
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
        if isinstance(result, dict):
            try:
                _manifest_cfg = dict(load_scenario_config(effective_config))
            except Exception:
                _manifest_cfg = {"config_path": str(effective_config)}
            result["run_manifest"] = build_run_manifest(
                _manifest_cfg, validation_mode=str(validation_mode)
            ).as_dict()

        write_artifacts = bool(cfg.get("write_artifacts", False))
        export_dir_raw = cfg.get("export_dir", "_out/run_full_pipeline_v14")

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
                    _write_json(export_dir / "debt_result.json", result.get("debt_result"))
                    logger.info("Wrote debt_result.json to %s", export_dir / "debt_result.json")

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
                    logger.info("Wrote annual_rows.csv to %s", export_dir / "annual_rows.csv")

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
        # Sprint 19 W.6: clean up the temp patched-scenario file. Done in
        # a finally so it runs whether the pipeline succeeded or raised.
        if patched_scenario_path is not None:
            try:
                patched_scenario_path.unlink(missing_ok=True)
            except OSError as cleanup_exc:  # pragma: no cover (best-effort)
                logger.warning(
                    "Could not remove temp patched scenario %s: %s",
                    patched_scenario_path, cleanup_exc,
                )


if __name__ == "__main__":
    cli()
