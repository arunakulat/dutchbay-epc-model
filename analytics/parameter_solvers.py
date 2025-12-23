"""DEPRECATED: Use analytics.core.parameter_solvers instead.

This module will be removed in a future release.
Please update imports to: from analytics.core.parameter_solvers import ...
"""

import warnings

# Issue deprecation warning
warnings.warn(
    "analytics.parameter_solvers is deprecated. "
    "Use 'from analytics.core.parameter_solvers import ...' instead. "
    "This shim will be removed in Sprint 17.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export everything from the new location
from analytics.core.parameter_solvers import (  # noqa: F401, E402
    SOLVER_REGISTRY,
    get_solver,
    solve_for_max_debt_given_dscr,
    solve_for_max_debt_multi_covenant,
    solve_for_min_capex_given_irr_floor,
    solve_for_tariff_given_irr,
    solve_for_tariff_given_npv,
)

__all__ = [
    "SOLVER_REGISTRY",
    "get_solver",
    "solve_for_max_debt_given_dscr",
    "solve_for_max_debt_multi_covenant",
    "solve_for_min_capex_given_irr_floor",
    "solve_for_tariff_given_irr",
    "solve_for_tariff_given_npv",
]
