"""Compatibility re-export of :mod:`wind_resource.aep_summary` (#1615).

The AEP summary builder (curve-selection validation, the config-driven AEP summary and
the wind-rose, wake and uncertainty resolvers) moved into the main wind engine under
the owner ruling of 2026-11-16 on #1615. Its live callers (``wind_resource/crossval.py``,
``wind_resource/arco_assessment.py`` and ``app/reports/report_model.py``) now import it
from ``wind_resource.aep_summary``. This module keeps the old import path working for
the analytics cluster's own tests and off-path scripts; it holds no implementation, so
the two paths cannot drift. It goes when Phase 1 of the cluster deprecation (#1551,
``docs/AEP_ANALYTICS_CLUSTER_DEPRECATION_DECISION.md``) removes the cluster; it emits no
warning, so lender runs log nothing new.
"""

from __future__ import annotations

from wind_resource.aep_summary import (  # noqa: F401  (re-exported)
    _resolve_density_factor,
    _resolve_live_wind_rose_freq,
    _resolve_wake_loss,
    _resolve_wake_ti,
    _resolve_wind_rose,
    _uncertainty_from_config,
    _validated_life_years,
    _validated_number,
    build_aep_summary_from_config,
    validate_curve_selection,
    write_aep_summary,
)

__all__ = [
    "validate_curve_selection",
    "build_aep_summary_from_config",
    "write_aep_summary",
]
