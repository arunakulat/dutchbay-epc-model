#!/usr/bin/env python
"""AEP pipeline integration for DutchBay v14 financial model.

Orchestrates the wind → AEP → revenue chain with:
- Config-driven resource loading (GWTF ARCH-01)
- Data Lake integration via aep_loader
- Monte Carlo uncertainty quantification (optional)
- Turbine specification validation
- Type-safe contracts

All parameters MUST come from YAML config. No hardcoded values.

Context:
    Sprint 17 - Phase 4: Pipeline Integration
    Connects wind analytics to finance modules
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from analytics.loader.aep_loader import load_aep_from_summary
from analytics.simulation.monte_carlo_aep import run_monte_carlo_aep
from analytics.wind.losses_model import DEFAULT_WIND_LOSSES

logger = logging.getLogger(__name__)


def validate_turbine_specs(config: Dict[str, Any], aep_data: Dict[str, Any]) -> None:
    """Validate turbine specifications consistency between config and AEP data.

    Ensures:
    - n_turbines matches between config and AEP summary
    - rated_power_mw matches
    - total_capacity_mw = n_turbines × rated_power_mw

    Args:
        config: Full project configuration dict (from YAML)
        aep_data: AEP summary dict from load_aep_from_summary()

    Raises:
        ValueError: If turbine specs are inconsistent

    Example:
        >>> config = {'resource': {'turbines': {'count': 15, 'rated_power_mw': 10.0}}}
        >>> aep_data = {'n_turbines': 15, 'rated_power_mw': 10.0}
        >>> validate_turbine_specs(config, aep_data)  # Pass
    """
    # Extract config turbine specs
    turbines_config = config.get("resource", {}).get("turbines", {})
    n_turbines_config = turbines_config.get("count")
    rated_power_mw_config = turbines_config.get("rated_power_mw")

    # Extract AEP turbine specs
    n_turbines_aep = aep_data.get("n_turbines")
    rated_power_mw_aep = aep_data.get("rated_power_mw")

    # Validate count
    if n_turbines_config and n_turbines_aep:
        if n_turbines_config != n_turbines_aep:
            raise ValueError(
                f"Turbine count mismatch: config says {n_turbines_config}, "
                f"AEP summary says {n_turbines_aep}. "
                f"Update scenarios/dutchbay_lendercase_2025Q4.yaml or "
                f"tests/mocks/aep_summary_dutchbay.json to match."
            )

    # Validate rated power
    if rated_power_mw_config and rated_power_mw_aep:
        if (
            abs(rated_power_mw_config - rated_power_mw_aep) > 0.1
        ):  # Allow 0.1 MW tolerance
            raise ValueError(
                f"Turbine rated power mismatch: config says {rated_power_mw_config} MW, "
                f"AEP summary says {rated_power_mw_aep} MW. "
                f"Update scenarios/dutchbay_lendercase_2025Q4.yaml or "
                f"tests/mocks/aep_summary_dutchbay.json to match."
            )

    # Validate total capacity
    if n_turbines_aep and rated_power_mw_aep:
        calculated_capacity_mw = n_turbines_aep * rated_power_mw_aep
        project_capacity_mw = config.get("project", {}).get("capacity_mw")

        if project_capacity_mw:
            if (
                abs(calculated_capacity_mw - project_capacity_mw) > 1.0
            ):  # 1 MW tolerance
                raise ValueError(
                    f"Total capacity mismatch: {n_turbines_aep} × {rated_power_mw_aep} MW = "
                    f"{calculated_capacity_mw} MW, but project.capacity_mw = {project_capacity_mw} MW. "
                    f"Update config to match: {n_turbines_aep} × {rated_power_mw_aep} = {calculated_capacity_mw} MW."
                )

    logger.info(
        f"Turbine specs validated: {n_turbines_aep} × {rated_power_mw_aep} MW = "
        f"{n_turbines_aep * rated_power_mw_aep if n_turbines_aep and rated_power_mw_aep else '?'} MW"
    )


def integrate_aep_pipeline(
    config: Dict[str, Any],
    validate_manifest: bool = True,
    run_monte_carlo: Optional[bool] = None,
) -> Dict[str, Any]:
    """Integrate AEP pipeline into v14 financial model configuration.

    CRITICAL: This function is config-driven (GWTF ARCH-01). All parameters
    come from the input config dict (loaded from YAML), not hardcoded.

    Workflow:
    1. Load AEP summary from Data Lake (via resource.aep_summary_path)
    2. Validate turbine specifications consistency
    3. Normalize AEP data and attach to config['resource']['aep_normalized']
    4. Optionally run Monte Carlo AEP simulation (if monte_carlo.enabled=true)
    5. Attach MC results to config['resource']['aep_mc_results']

    Args:
        config: Full project configuration dict (from YAML)
        validate_manifest: If True, verify source_id is in approved manifest
        run_monte_carlo: If True, force MC run; if None, use config.monte_carlo.enabled

    Returns:
        Updated config dict with:
            - config['resource']['aep_normalized']: Loaded AEP data
            - config['resource']['aep_mc_results']: Monte Carlo results (if enabled)

    Raises:
        ValueError: If turbine specs are inconsistent or AEP path missing
        FileNotFoundError: If AEP summary file not found

    Example:
        >>> import yaml
        >>> with open('scenarios/dutchbay_lendercase_2025Q4.yaml') as f:
        ...     config = yaml.safe_load(f)
        >>> config = integrate_aep_pipeline(config)
        >>> print(config['resource']['aep_normalized']['net_site_aep_gwh'])
        485.32
    """
    # Step 1: Load AEP summary from Data Lake
    aep_summary_path = config.get("resource", {}).get("aep_summary_path")

    if not aep_summary_path:
        raise ValueError(
            "Missing resource.aep_summary_path in config. "
            "Add to scenarios/dutchbay_lendercase_2025Q4.yaml: \n"
            "resource:\n"
            "  aep_summary_path: 'tests/mocks/aep_summary_dutchbay.json'"
        )

    logger.info(f"Loading AEP summary from: {aep_summary_path}")

    aep_data = load_aep_from_summary(
        path=aep_summary_path, validate_manifest=validate_manifest
    )

    # Step 2: Validate turbine specs consistency
    validate_turbine_specs(config, aep_data)

    # Step 3: Attach normalized AEP data to config
    if "resource" not in config:
        config["resource"] = {}

    config["resource"]["aep_normalized"] = aep_data

    logger.info(
        f"AEP data integrated: {aep_data['net_site_aep_gwh']:.2f} GWh/year, "
        f"CF={aep_data['capacity_factor']:.2%}"
    )

    # Step 4: Monte Carlo simulation (optional, config-driven)
    mc_config = config.get("monte_carlo", {})
    mc_enabled = (
        run_monte_carlo
        if run_monte_carlo is not None
        else mc_config.get("enabled", False)
    )

    if mc_enabled:
        logger.info("Running Monte Carlo AEP simulation (config-driven)...")

        n_scenarios = mc_config.get("n_scenarios", 100000)
        seed = mc_config.get("seed", None)
        output_path = mc_config.get("output_path", None)

        # Extract loss parameters from config; fall back to the centralised, documented
        # industry-typical defaults (overridable via resource.losses) rather than scattered
        # magic numbers (ARCH-01 / DRY — see losses_model.DEFAULT_WIND_LOSSES).
        losses_config = config.get("resource", {}).get("losses", {})
        wake_loss_pct = losses_config.get(
            "wake_loss_pct", DEFAULT_WIND_LOSSES["wake_loss_pct"]
        )
        availability_pct = losses_config.get(
            "availability_pct", DEFAULT_WIND_LOSSES["availability_pct"]
        )
        electrical_loss_pct = losses_config.get(
            "electrical_loss_pct", DEFAULT_WIND_LOSSES["electrical_loss_pct"]
        )

        # MC uncertainty parameters from config
        mc_params = mc_config.get("parameters", {})
        wake_loss_std = mc_params.get("wake_loss_std_pct", 2.0)
        avail_std = mc_params.get("availability_std_pct", 1.0)
        elec_loss_std = mc_params.get("electrical_loss_std_pct", 0.5)

        mc_results = run_monte_carlo_aep(
            aep_summary_path=aep_summary_path,
            n_scenarios=n_scenarios,
            wake_loss_mean_pct=wake_loss_pct,
            availability_mean_pct=availability_pct,
            electrical_loss_mean_pct=electrical_loss_pct,
            wake_loss_std_pct=wake_loss_std,
            availability_std_pct=avail_std,
            electrical_loss_std_pct=elec_loss_std,
            export_scenarios=(output_path is not None),
            output_path=output_path,
            seed=seed,
        )

        config["resource"]["aep_mc_results"] = mc_results

        logger.info(
            f"Monte Carlo complete: P50={mc_results['percentiles']['p50']:.2f} GWh, "
            f"P90={mc_results['percentiles']['p90']:.2f} GWh"
        )
    else:
        logger.info("Monte Carlo simulation disabled (monte_carlo.enabled=false)")

    return config


__all__ = [
    "validate_turbine_specs",
    "integrate_aep_pipeline",
]
