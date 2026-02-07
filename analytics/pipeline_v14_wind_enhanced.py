"""Enhanced pipeline_v14 with wind analytics integration.

This is a BACKWARD-COMPATIBLE enhancement to pipeline_v14.py that adds
optional wind analytics integration. The original pipeline_v14.py is
untouched; this module can be used as a drop-in replacement.

Changes from pipeline_v14:
- Step 0.5: Optional AEP loading from Data Lake
- Step 0.6: Optional Monte Carlo AEP simulation
- AEP provenance tracking in ScenarioResult
- Enhanced logging for wind resource integration

Usage:
    # Use exactly like pipeline_v14:
    from analytics.pipeline_v14_wind_enhanced import run_v14_pipeline

    result = run_v14_pipeline(config='scenario_with_aep.yaml')

Context:
    Sprint 17 - Issue #21: Pipeline Integration for Wind Analytics
"""

from __future__ import annotations

import logging
from analytics.pipeline_v14 import run_v14_pipeline as _run_v14_pipeline_original
from analytics.wind_integration import (
    WIND_MODULES_AVAILABLE,
    integrate_aep_into_config,
)

logger = logging.getLogger(__name__)


def run_v14_pipeline(
    config,
    validation_mode: str = "strict",
    validation_modules: list[str] | None = None,
    allow_fx_degradation: bool = False,
):
    """Enhanced v14 pipeline with optional wind analytics integration.

    This is a DROP-IN REPLACEMENT for analytics.pipeline_v14.run_v14_pipeline
    with added wind analytics support. All parameters and return types
    are identical to the original.

    Wind Integration (Optional):
    If config contains an 'aep' block, the pipeline will:
    1. Load AEP from Data Lake (if aep.data_lake_path provided)
    2. Run Monte Carlo AEP (if aep.monte_carlo.enabled = true)
    3. Inject AEP data into config for cashflow engine
    4. Track AEP provenance in ScenarioResult

    Config Examples:

    # Example 1: Direct AEP specification
    aep:
      net_aep_gwh: 485.32
      source_id: "ECMWF_ERA5_2020_2024_DUTCHBAY"

    # Example 2: Load from Data Lake
    aep:
      data_lake_path: "tests/mocks/aep_summary_dutchbay.json"
      validate_manifest: true

    # Example 3: Monte Carlo mode (P90 for conservative revenue)
    aep:
      data_lake_path: "tests/mocks/aep_summary_dutchbay.json"
      monte_carlo:
        enabled: true
        n_scenarios: 100000
        use_p_value: 90
        export_scenarios: true
        output_path: "outputs/mc_aep_scenarios.parquet"

    Backward Compatibility:
    - If no 'aep' block present, behaves exactly like original pipeline
    - All existing scenarios work without modification
    - Wind modules are optional (graceful degradation)

    Parameters
    ----------
    Same as analytics.pipeline_v14.run_v14_pipeline

    Returns
    -------
    Same as analytics.pipeline_v14.run_v14_pipeline, with optional
    'aep_data' key in result dict if AEP integration enabled.
    """
    # Handle config loading
    from pathlib import Path
    from analytics.scenario_loader import load_scenario_config

    if isinstance(config, (str, Path)):
        config_path_label = str(config)
        cfg = load_scenario_config(str(config))
    elif isinstance(config, dict):
        config_path_label = "<inline_config>"
        cfg = dict(config)
    else:
        # Let original pipeline handle type error
        return _run_v14_pipeline_original(
            config=config,
            validation_mode=validation_mode,
            validation_modules=validation_modules,
            allow_fx_degradation=allow_fx_degradation,
        )

    # Check for AEP block
    aep_block = cfg.get("aep") or cfg.get("AEP")

    if aep_block is None:
        # No AEP integration requested; use original pipeline
        logger.debug("No AEP block found; using standard pipeline")
        return _run_v14_pipeline_original(
            config=cfg,
            validation_mode=validation_mode,
            validation_modules=validation_modules,
            allow_fx_degradation=allow_fx_degradation,
        )

    # AEP integration requested
    if not WIND_MODULES_AVAILABLE:
        logger.warning(
            "AEP block found but wind modules not available; "
            "falling back to standard pipeline (will use capacity_factor)"
        )
        return _run_v14_pipeline_original(
            config=cfg,
            validation_mode=validation_mode,
            validation_modules=validation_modules,
            allow_fx_degradation=allow_fx_degradation,
        )

    logger.info(
        "Wind analytics integration enabled for scenario: %s", config_path_label
    )

    # Parse AEP block
    data_lake_path = aep_block.get("data_lake_path")
    net_aep_gwh_direct = aep_block.get("net_aep_gwh")
    monte_carlo_config = aep_block.get("monte_carlo")

    # Integrate AEP into config
    try:
        if net_aep_gwh_direct is not None:
            # Direct AEP specification
            logger.info("Using direct AEP specification: %.2f GWh", net_aep_gwh_direct)
            # Already in config; no need to integrate
            pass
        elif data_lake_path is not None:
            # Load from Data Lake
            logger.info("Step 0.5/5: Loading AEP from Data Lake...")

            mc_dict = None
            if monte_carlo_config and monte_carlo_config.get("enabled"):
                logger.info("Step 0.6/5: Running Monte Carlo AEP simulation...")
                mc_dict = monte_carlo_config

            cfg = integrate_aep_into_config(
                config=cfg,
                aep_summary_path=data_lake_path,
                monte_carlo_config=mc_dict,
            )

            logger.info(
                "AEP integration complete: %.2f GWh (CF=%.2f%%)",
                cfg["aep"]["net_aep_gwh"],
                cfg["aep"]["capacity_factor_derived"] * 100,
            )
        else:
            logger.warning(
                "AEP block found but no data_lake_path or net_aep_gwh; "
                "falling back to capacity_factor"
            )
    except Exception as e:
        logger.error(
            "AEP integration failed: %s; falling back to standard pipeline",
            e,
            exc_info=True,
        )
        # Continue with original config (will use capacity_factor)

    # Run original pipeline with enhanced config
    result = _run_v14_pipeline_original(
        config=cfg,
        validation_mode=validation_mode,
        validation_modules=validation_modules,
        allow_fx_degradation=allow_fx_degradation,
    )

    # Add AEP data to result if present
    if "aep" in cfg:
        result["aep_data"] = cfg["aep"]
        logger.info(
            "AEP provenance included in result: Source=%s, IEC=%s",
            cfg["aep"].get("source_id", "unknown"),
            cfg["aep"].get("provenance", {}).get("iec_standard_version", "unknown"),
        )

    return result


__all__ = ["run_v14_pipeline"]
