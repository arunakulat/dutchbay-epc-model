"""AEP-enhanced cashflow parameters extraction.

This module extends cashflow_v14_params to support AEP-driven revenue
calculation, where net_aep_gwh takes precedence over capacity_factor.

Integration:
- Injected into cashflow_v14_params._extract_parameters() logic
- Fully backward-compatible with capacity_factor mode
- Used by cashflow_v14.build_annual_rows()

Usage:
    # This module is imported by cashflow_v14_params
    # No direct usage required

Context:
    Sprint 17 - Issue #22: Finance Integration for Wind Analytics
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def extract_aep_driven_capacity_factor(
    config: Dict[str, Any],
    capacity_mw: float,
) -> Optional[float]:
    """Extract or derive capacity_factor from AEP data in config.
    
    This function checks for 'aep.net_aep_gwh' in config and reverse-engineers
    the capacity factor if present. Otherwise returns None, signaling that
    the standard capacity_factor extraction should be used.
    
    Args:
        config: Finance config dict
        capacity_mw: Installed capacity (MW)
    
    Returns:
        Capacity factor (0-1 decimal) if AEP present, else None
    
    Example:
        >>> config = {'aep': {'net_aep_gwh': 485.32}, 'project': {'capacity_mw': 149.5}}
        >>> cf = extract_aep_driven_capacity_factor(config, 149.5)
        >>> cf
        0.371
    """
    aep_block = config.get('aep') or config.get('AEP')
    
    if aep_block is None:
        return None
    
    net_aep_gwh = aep_block.get('net_aep_gwh')
    
    if net_aep_gwh is None:
        return None
    
    try:
        net_aep_gwh = float(net_aep_gwh)
    except (TypeError, ValueError):
        logger.warning(
            "Invalid net_aep_gwh in config: %s; falling back to capacity_factor",
            net_aep_gwh
        )
        return None
    
    if capacity_mw <= 0:
        logger.error(
            "Cannot derive CF from AEP: capacity_mw=%.2f invalid",
            capacity_mw
        )
        return None
    
    # Derive CF: net_aep_gwh / (capacity_mw * 8760 hours / 1000)
    max_annual_energy_gwh = capacity_mw * 8.760
    cf = net_aep_gwh / max_annual_energy_gwh
    
    # Validation
    if cf < 0 or cf > 1:
        raise ValueError(
            f"AEP-derived capacity_factor {cf:.3f} outside valid range [0, 1]. "
            f"Check net_aep_gwh={net_aep_gwh} and capacity_mw={capacity_mw}"
        )
    
    # Warn if outside typical wind range
    if cf < 0.15 or cf > 0.60:
        logger.warning(
            "AEP-derived capacity_factor %.2f%% outside typical wind range [15%%, 60%%]",
            cf * 100
        )
    
    logger.info(
        "Using AEP-driven capacity_factor: %.2f%% (from net_aep_gwh=%.2f GWh)",
        cf * 100,
        net_aep_gwh
    )
    
    return cf


__all__ = ['extract_aep_driven_capacity_factor']
