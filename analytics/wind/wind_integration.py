#!/usr/bin/env python
"""Wind-to-EPC integration bridge for DutchBay v14 pipeline.

Provides high-level functions to integrate wind resource analysis
(AEP from power curves, ERA5 reanalysis, Monte Carlo) into the
v14 financial modeling pipeline.

Usage:
    from analytics.wind.wind_integration import (
        load_aep_for_project,
        integrate_aep_into_config,
        run_aep_monte_carlo,
    )
    
    # Load AEP from Data Lake
    aep_data = load_aep_for_project(
        aep_summary_path='tests/mocks/aep_summary_dutchbay.json'
    )
    
    # Inject into finance config
    config_updated = integrate_aep_into_config(
        config=base_config,
        aep_data=aep_data
    )
    
    # Run Monte Carlo for risk quantification
    mc_results = run_aep_monte_carlo(
        aep_summary_path='tests/mocks/aep_summary_dutchbay.json',
        n_scenarios=100000
    )

Context:
    Sprint 17 - Issue #21 + #22: Wind-to-Finance Integration
    Bridge module between wind analytics and v14 finance engine
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Optional imports (graceful degradation if wind modules not available)
try:
    from analytics.loader.aep_loader import load_aep_from_summary
    from analytics.simulation.monte_carlo_aep import run_monte_carlo_aep
    WIND_MODULES_AVAILABLE = True
except ImportError:
    logger.warning(
        "Wind analytics modules not available; "
        "wind integration features will be disabled. "
        "Install wind modules or check import paths."
    )
    WIND_MODULES_AVAILABLE = False


# ═════════════════════════════════════════════════════════════════════════════
# AEP LOADING
# ═════════════════════════════════════════════════════════════════════════════


def load_aep_for_project(
    aep_summary_path: str,
    validate_manifest: bool = True,
) -> Dict[str, Any]:
    """Load AEP data from Data Lake with provenance validation.
    
    Wrapper around analytics.loader.aep_loader.load_aep_from_summary
    with project-specific conventions.
    
    Args:
        aep_summary_path: Path to AEP summary JSON file
        validate_manifest: If True, validates source_id against approved manifest
    
    Returns:
        AEP data dict with:
            - net_site_aep_gwh: Annual energy production (GWh)
            - capacity_factor: Net site capacity factor
            - n_turbines: Number of turbines
            - rated_power_kw: Rated power per turbine
            - source_id: Data source identifier
            - provenance: Audit trail metadata
    
    Raises:
        ImportError: If wind modules not available
        FileNotFoundError: If aep_summary_path not found
        KeyError: If source_id not in approved manifest
    
    Example:
        >>> aep_data = load_aep_for_project(
        ...     aep_summary_path='tests/mocks/aep_summary_dutchbay.json'
        ... )
        >>> aep_data['net_site_aep_gwh']
        485.32
        >>> aep_data['provenance']['iec_standard_version']
        '61400-12-1:2022'
    """
    if not WIND_MODULES_AVAILABLE:
        raise ImportError(
            "Wind analytics modules not available. "
            "Cannot load AEP from Data Lake. "
            "Ensure analytics.loader.aep_loader is installed."
        )
    
    logger.info("Loading AEP from Data Lake: %s", aep_summary_path)
    
    aep_data = load_aep_from_summary(
        path=aep_summary_path,
        validate_manifest=validate_manifest
    )
    
    logger.info(
        "AEP loaded: %.2f GWh, CF=%.2f%%, Source=%s",
        aep_data['net_site_aep_gwh'],
        aep_data['capacity_factor'] * 100,
        aep_data['source_id']
    )
    
    return aep_data


# ═════════════════════════════════════════════════════════════════════════════
# MONTE CARLO
# ═════════════════════════════════════════════════════════════════════════════


def run_aep_monte_carlo(
    aep_summary_path: str,
    n_scenarios: int = 100000,
    export_scenarios: bool = False,
    output_path: Optional[str] = None,
    seed: Optional[int] = None,
) -> Dict[str, Any]:
    """Run Monte Carlo simulation for AEP uncertainty quantification.
    
    Wrapper around analytics.simulation.monte_carlo_aep.run_monte_carlo_aep
    with project-specific defaults.
    
    Args:
        aep_summary_path: Path to AEP summary JSON
        n_scenarios: Number of MC scenarios (100k for production, 1k for testing)
        export_scenarios: If True, export scenarios to parquet
        output_path: Path to save scenarios (required if export_scenarios=True)
        seed: Random seed for reproducibility
    
    Returns:
        Dictionary with:
            - percentiles: {p50, p75, p90, p99} AEP values (GWh)
            - confidence_intervals: {ci95_lower, ci95_upper}
            - statistics: {mean, std, cv}
            - scenarios: DataFrame (if export_scenarios=True)
    
    Raises:
        ImportError: If wind modules not available
    
    Example:
        >>> mc_results = run_aep_monte_carlo(
        ...     aep_summary_path='tests/mocks/aep_summary_dutchbay.json',
        ...     n_scenarios=100000
        ... )
        >>> mc_results['percentiles']['p50']
        485.32
        >>> mc_results['percentiles']['p90']
        538.94
    """
    if not WIND_MODULES_AVAILABLE:
        raise ImportError(
            "Wind analytics modules not available. "
            "Cannot run Monte Carlo AEP simulation. "
            "Ensure analytics.simulation.monte_carlo_aep is installed."
        )
    
    logger.info(
        "Starting Monte Carlo AEP simulation: %d scenarios",
        n_scenarios
    )
    
    mc_results = run_monte_carlo_aep(
        aep_summary_path=aep_summary_path,
        n_scenarios=n_scenarios,
        export_scenarios=export_scenarios,
        output_path=output_path,
        seed=seed,
    )
    
    logger.info(
        "Monte Carlo complete: P50=%.2f GWh, P90=%.2f GWh, CV=%.2f%%",
        mc_results['percentiles']['p50'],
        mc_results['percentiles']['p90'],
        mc_results['statistics']['cv'] * 100
    )
    
    return mc_results


def compute_aep_p_values(
    mc_results: Dict[str, Any],
    p_values: Optional[list[int]] = None
) -> Dict[str, float]:
    """Extract AEP P-values from Monte Carlo results.
    
    Args:
        mc_results: Results from run_aep_monte_carlo()
        p_values: List of percentiles to extract (default: [50, 75, 90, 99])
    
    Returns:
        Dictionary mapping percentile names to AEP values (GWh)
    
    Example:
        >>> p_vals = compute_aep_p_values(mc_results)
        >>> p_vals['p50']
        485.32
        >>> p_vals['p90']
        538.94
    """
    if p_values is None:
        p_values = [50, 75, 90, 99]
    
    percentiles = mc_results['percentiles']
    
    result = {}
    for p in p_values:
        key = f'p{p}'
        if key in percentiles:
            result[key] = percentiles[key]
    
    return result


# ═════════════════════════════════════════════════════════════════════════════
# CONFIG INTEGRATION
# ═════════════════════════════════════════════════════════════════════════════


def derive_capacity_factor_from_aep(
    net_aep_gwh: float,
    capacity_mw: float,
    project_life_years: int = 25,
) -> float:
    """Reverse-engineer capacity factor from net AEP.
    
    Formula:
        CF = net_aep_gwh / (capacity_mw * 8760 * project_life_years / 1000)
    
    Note: This gives the AVERAGE capacity factor over project life,
    assuming constant AEP. For year-specific CF, use degradation curves.
    
    Args:
        net_aep_gwh: Net annual energy production (GWh/year)
        capacity_mw: Installed capacity (MW)
        project_life_years: Project lifetime (years)
    
    Returns:
        Capacity factor (0-1 decimal)
    
    Raises:
        ValueError: If inputs invalid or CF outside realistic range
    
    Example:
        >>> cf = derive_capacity_factor_from_aep(
        ...     net_aep_gwh=485.32,
        ...     capacity_mw=149.5,
        ...     project_life_years=25
        ... )
        >>> cf
        0.371
    """
    if capacity_mw <= 0:
        raise ValueError(f"capacity_mw must be positive, got {capacity_mw}")
    
    if net_aep_gwh < 0:
        raise ValueError(f"net_aep_gwh cannot be negative, got {net_aep_gwh}")
    
    # Annual energy at 100% CF (GWh/year)
    max_annual_energy_gwh = capacity_mw * 8.760  # 8760 hours = 8.76 MWh/MW
    
    # Capacity factor (average over project life)
    cf = net_aep_gwh / max_annual_energy_gwh
    
    # Validation: CF should be in [0, 1]
    if cf < 0 or cf > 1:
        raise ValueError(
            f"Derived capacity factor {cf:.3f} outside valid range [0, 1]. "
            f"Check inputs: net_aep_gwh={net_aep_gwh}, capacity_mw={capacity_mw}"
        )
    
    # Warn if CF outside typical wind range
    if cf < 0.15 or cf > 0.60:
        logger.warning(
            "Derived capacity factor %.2f%% outside typical wind range [15%%, 60%%]. "
            "Verify AEP data quality.",
            cf * 100
        )
    
    return cf


def integrate_aep_into_config(
    config: Dict[str, Any],
    aep_data: Optional[Dict[str, Any]] = None,
    aep_summary_path: Optional[str] = None,
    monte_carlo_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Integrate AEP data into finance config.
    
    This function injects AEP data into the config dict, allowing the
    cashflow engine to use net AEP instead of capacity factor for
    revenue calculations.
    
    Three modes supported:
    1. Direct AEP data injection (aep_data provided)
    2. Load from Data Lake (aep_summary_path provided)
    3. Monte Carlo mode (aep_summary_path + monte_carlo_config)
    
    Args:
        config: Finance config dict
        aep_data: Pre-loaded AEP data (from load_aep_for_project)
        aep_summary_path: Path to load AEP from Data Lake
        monte_carlo_config: Dict with MC settings:
            - n_scenarios: Number of scenarios (default 100k)
            - use_p_value: Percentile to use (default 50 = median)
            - export_scenarios: Export to parquet (default False)
            - output_path: Parquet output path
    
    Returns:
        Updated config with 'aep' block:
            - net_aep_gwh: Annual energy production
            - capacity_factor: Derived CF (for reference)
            - source_id: Data source identifier
            - provenance: Audit trail
            - monte_carlo_results: MC results (if MC mode)
    
    Example:
        >>> # Mode 1: Direct injection
        >>> config_updated = integrate_aep_into_config(
        ...     config=base_config,
        ...     aep_data={'net_site_aep_gwh': 485.32, ...}
        ... )
        
        >>> # Mode 2: Load from Data Lake
        >>> config_updated = integrate_aep_into_config(
        ...     config=base_config,
        ...     aep_summary_path='tests/mocks/aep_summary_dutchbay.json'
        ... )
        
        >>> # Mode 3: Monte Carlo P90
        >>> config_updated = integrate_aep_into_config(
        ...     config=base_config,
        ...     aep_summary_path='tests/mocks/aep_summary_dutchbay.json',
        ...     monte_carlo_config={'n_scenarios': 100000, 'use_p_value': 90}
        ... )
    """
    # Make a copy to avoid mutating input
    config = dict(config)
    
    # Determine mode
    if aep_data is None and aep_summary_path is not None:
        # Load from Data Lake
        aep_data = load_aep_for_project(aep_summary_path)
    
    if aep_data is None:
        logger.warning(
            "No AEP data provided; config will use capacity_factor as fallback"
        )
        return config
    
    # Extract capacity from config
    capacity_mw = None
    for path in [
        ('project', 'capacity_mw'),
        ('project', 'capacity'),
        ('parameters', 'capacity_mw'),
    ]:
        val = config
        for key in path:
            val = val.get(key)
            if val is None:
                break
        if val is not None:
            capacity_mw = float(val)
            break
    
    if capacity_mw is None:
        raise ValueError(
            "Cannot integrate AEP: capacity_mw not found in config. "
            "Provide project.capacity_mw or parameters.capacity_mw."
        )
    
    # Determine AEP value (P50 default, or MC percentile)
    net_aep_gwh = aep_data['net_site_aep_gwh']
    
    mc_results = None
    if monte_carlo_config is not None:
        # Run Monte Carlo
        n_scenarios = monte_carlo_config.get('n_scenarios', 100000)
        use_p_value = monte_carlo_config.get('use_p_value', 50)
        export = monte_carlo_config.get('export_scenarios', False)
        output_path = monte_carlo_config.get('output_path')
        
        logger.info(
            "Running Monte Carlo AEP: %d scenarios, P%d",
            n_scenarios,
            use_p_value
        )
        
        mc_results = run_aep_monte_carlo(
            aep_summary_path=aep_summary_path,
            n_scenarios=n_scenarios,
            export_scenarios=export,
            output_path=output_path,
        )
        
        # Use specified percentile
        p_key = f'p{use_p_value}'
        if p_key in mc_results['percentiles']:
            net_aep_gwh = mc_results['percentiles'][p_key]
            logger.info(
                "Using P%d AEP for revenue: %.2f GWh",
                use_p_value,
                net_aep_gwh
            )
        else:
            logger.warning(
                "P%d not found in MC results; using P50 (%.2f GWh)",
                use_p_value,
                mc_results['percentiles']['p50']
            )
            net_aep_gwh = mc_results['percentiles']['p50']
    
    # Derive capacity factor
    cf_derived = derive_capacity_factor_from_aep(
        net_aep_gwh=net_aep_gwh,
        capacity_mw=capacity_mw
    )
    
    # Build AEP block for config
    aep_block = {
        'net_aep_gwh': net_aep_gwh,
        'capacity_factor_derived': cf_derived,
        'source_id': aep_data.get('source_id'),
        'source_type': aep_data.get('source_type'),
        'provenance': aep_data.get('provenance'),
    }
    
    if mc_results is not None:
        aep_block['monte_carlo_results'] = {
            'percentiles': mc_results['percentiles'],
            'confidence_intervals': mc_results['confidence_intervals'],
            'statistics': mc_results['statistics'],
            'n_scenarios': mc_results['n_scenarios'],
        }
    
    config['aep'] = aep_block
    
    logger.info(
        "Integrated AEP into config: %.2f GWh (CF=%.2f%%)",
        net_aep_gwh,
        cf_derived * 100
    )
    
    return config


__all__ = [
    "WIND_MODULES_AVAILABLE",
    "load_aep_for_project",
    "run_aep_monte_carlo",
    "compute_aep_p_values",
    "derive_capacity_factor_from_aep",
    "integrate_aep_into_config",
]
