from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

import hydra
from omegaconf import DictConfig, OmegaConf

from analytics.scenario_analytics import BatchResultSummary, ScenarioAnalytics

logger = logging.getLogger(__name__)

#!/usr/bin/env python3
"""
v14 Scenario Analytics – Hydra CLI entrypoint (batch scenario COMPARISON).

This is the thin, blessed CLI wrapper around analytics.scenario_analytics.ScenarioAnalytics.

PIPELINE ROLE (PIPE-1, #472) — this is the deliberately LIGHTER batch path, NOT the
canonical engine. It discovers many scenarios and runs each through
``ScenarioAnalytics._run_single`` (``build_annual_rows`` + ``apply_debt_layer`` +
``calculate_scenario_kpis`` with ``wacc_is_real=False``) for fast, comparable snapshots.
It intentionally does NOT do the canonical lender-grade work that
``run_full_pipeline_v14.py`` (→ ``analytics.pipeline_v14_enhanced.run_v14_pipeline``)
does: build-up WACC driving the discount rate, the two-pass interest tax shield, the
equity-distribution waterfall, FX integration, and the full
``contracts_v14.ScenarioResult`` surface. The discount rate here is the scenario's
configured/global default (informational WACC only) — so for a single scenario's
authoritative economics use ``run_full_pipeline_v14.py``; use this CLI to rank/compare a
directory of scenarios. See docs/ARCHITECTURE.md ("Canonical execution map").

Usage (Hydra-style overrides)
-----------------------------
Run against the default scenarios directory:

    python run_scenario_analytics_v14.py \
        scenarios_dir=scenarios \
        output=exports/v14_analytics.xlsx \
        strict=true \
        charts=true

Key behaviours
--------------
- Discovers scenario configs under `scenarios_dir`
- Runs v14 engine via ScenarioAnalytics (strict schema guard inside)
- Writes summary + timeseries to `output` (Excel)
- Optionally writes charts alongside the workbook
- Prints a small JSON summary to stdout for CI / smoke tests:

    {
      "basis": "comparison_snapshot",
      "n_success": <int>,
      "n_failed": <int>,
      "output_path": "...",
      "summary_json": null | "path"
    }

  ``basis`` is the machine-readable provenance marker (#611): batch economics are
  comparison snapshots, not the canonical ``run_full_pipeline_v14.py`` numbers.

Hydra config
------------
Defaults live in: conf/run_scenario_analytics_v14.yaml

You can override any top-level key using Hydra’s `key=value` syntax, e.g.:

    python run_scenario_analytics_v14.py output=exports/custom.xlsx charts=false
"""


def _build_stdout_payload(
    batch_metadata: BatchResultSummary,
    output_path: Path,
    summary_json_path: Optional[Path],
) -> dict[str, Any]:
    """
    Build the compact JSON payload printed to stdout for CI / smoke tests.

    Additive contract (#611): carries the batch provenance marker ``basis``
    (sourced from :class:`analytics.scenario_analytics.BatchResultSummary`, always
    ``"comparison_snapshot"``) alongside the pre-existing keys, so downstream
    consumers cannot mistake batch DSCR/IRR for canonical pipeline economics.
    No existing key is renamed or removed.
    """
    return {
        "basis": batch_metadata.basis,
        "n_success": batch_metadata.n_success,
        "n_failed": batch_metadata.n_failed,
        "output_path": str(output_path),
        "summary_json": str(summary_json_path) if summary_json_path else None,
    }


def _build_scenario_filter(expr: Optional[str]) -> Optional[Callable[[str], bool]]:
    """
    Turn a simple filter expression into a scenario-name predicate.

    Current behaviour (deliberately simple and predictable):
    - None / empty string -> no filter (include all scenarios)
    - "foo" -> include only scenarios whose name contains "foo" as a substring
    """
    if expr is None:
        return None

    pattern = str(expr).strip()
    if not pattern:
        return None

    def _predicate(name: str, pat: str = pattern) -> bool:
        return pat in name

    return _predicate


def _resolve_default_discount_rate(cfg_dict: Mapping[Any, Any]) -> float:
    """
    Resolve the batch-wide default discount rate from the Hydra config.

    Single source of truth (#586, CESSPIT — Config Explicit): for batch runs the
    authoritative value is the ``default_discount_rate`` key in
    ``conf/run_scenario_analytics_v14.yaml`` (0.12 as committed). There is
    deliberately NO silent numeric fallback here — a config that omits the key
    (e.g. via a ``~default_discount_rate`` Hydra delete-override) fails loudly
    instead of quietly diverging from the packaged value. Direct-API callers of
    :class:`analytics.scenario_analytics.ScenarioAnalytics` are instead backed by
    ``analytics.scenario_analytics.DEFAULT_GLOBAL_DISCOUNT_RATE``.
    """
    if "default_discount_rate" not in cfg_dict:
        raise ValueError(
            "Missing 'default_discount_rate' in the batch config. "
            "conf/run_scenario_analytics_v14.yaml carries the authoritative "
            "value; restore the key or pass default_discount_rate=<rate> as a "
            "Hydra override (there is no silent code fallback)."
        )
    raw = cfg_dict["default_discount_rate"]
    try:
        return float(raw)
    except (TypeError, ValueError):
        raise ValueError(
            f"Invalid default_discount_rate: {raw!r} – expected a float-like value."
        )


@hydra.main(
    config_path="conf",
    config_name="run_scenario_analytics_v14",
    # Explicit version_base to avoid Hydra warnings and lock semantics.
    version_base="1.3",
)
def main(cfg: DictConfig) -> None:
    """
    Hydra entrypoint.

    Reads config from conf/run_scenario_analytics_v14.yaml plus CLI overrides,
    runs the v14 ScenarioAnalytics batch, and prints a small JSON summary.
    """
    # Normalise to a plain dict for safety.
    cfg_dict = OmegaConf.to_container(cfg, resolve=True) or {}
    if not isinstance(cfg_dict, dict):
        raise TypeError(
            f"Expected DictConfig to convert to dict, got {type(cfg_dict).__name__}"
        )

    # Core parameters with sane defaults.
    scenarios_dir = Path(str(cfg_dict.get("scenarios_dir", "scenarios")))
    output_path = Path(str(cfg_dict.get("output", "exports/v14_analytics.xlsx")))
    strict = bool(cfg_dict.get("strict", True))
    parallel = bool(cfg_dict.get("parallel", False))
    charts = bool(cfg_dict.get("charts", False))

    # Optional extras.
    filter_expr = cfg_dict.get("filter", None)
    summary_json_cfg = cfg_dict.get("summary_json", None)

    # Ensure output directory exists (scenarios_dir should already exist).
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Wire scenario filter (fixes the previous "unused variable" lint warning).
    scenario_filter = _build_scenario_filter(filter_expr)

    # Resolve the batch-wide default discount rate — fail-loud if the config
    # omits the key; the packaged YAML is the single source of truth (#586).
    global_default_discount_rate = _resolve_default_discount_rate(cfg_dict)

    # Optional JSON summary file path.
    summary_json_path: Optional[Path]
    if summary_json_cfg:
        summary_json_path = Path(str(summary_json_cfg))
        summary_json_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        summary_json_path = None

    logger.info(
        "ScenarioAnalytics v14 – starting batch run: scenarios_dir=%s, "
        "output=%s, strict=%s, parallel=%s, charts=%s, filter=%r",
        scenarios_dir,
        output_path,
        strict,
        parallel,
        charts,
        filter_expr,
    )

    # Instantiate the v14 analytics engine.
    engine = ScenarioAnalytics(
        scenarios_dir=scenarios_dir,
        output_path=output_path,
        scenario_filter=scenario_filter,
        strict=strict,
        parallel=parallel,
        global_default_discount_rate=global_default_discount_rate,
    )

    # Run batch; engine handles Excel + charts export internally.
    _summary_df, _timeseries_df, batch_metadata = engine.run(
        export_excel=True,
        export_charts=charts,
        output_summary_json=summary_json_path,
    )

    # Compact JSON payload for CI / smoke tests (incl. the #611 basis marker).
    result: dict[str, Any] = _build_stdout_payload(
        batch_metadata, output_path, summary_json_path
    )

    # IMPORTANT: stdout must be valid JSON for the CLI smoke test.
    # Logs will go via the logging framework (typically to stderr).
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
