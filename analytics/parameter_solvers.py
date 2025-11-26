"""Parameter solvers for derived Monte Carlo parameters.

This module provides reverse-engineering solvers that calculate input
parameters (e.g., tariff) from target output constraints (e.g., IRR).

Architecture:
- Uses evaluate_with_overrides() gateway (coordinator pattern)
- No direct finance math duplication
- Extensible solver registry for custom derivations
- Graceful convergence handling with iteration limits

Frozen Surfaces Used:
- analytics.evaluate_scenario (evaluate_with_overrides gateway)
- analytics.contracts_v14 (DerivedParameter contract)
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from analytics.evaluate_scenario import evaluate_with_overrides

logger = logging.getLogger(__name__)


def solve_for_tariff_given_irr(
    base_config_path: str,
    base_overrides: dict[str, Any],
    target_irr: float,
    method: str = "bisection",
    bounds: tuple[float, float] = (40.0, 100.0),
    tolerance: float = 0.0001,
    max_iterations: int = 50,
) -> float:
    """
    Find tariff (LKR/kWh) that achieves target project IRR.

    Uses binary search (bisection method) to efficiently find the
    tariff value that produces the desired IRR given all other
    sampled parameters (capex, opex, capacity factor, etc.).

    Args:
        base_config_path: Path to base scenario YAML
        base_overrides: Dict of sampled parameter values
        target_irr: Desired project-level IRR (e.g., 0.12 for 12%)
        method: Solver method ("bisection" only for now)
        bounds: (min_tariff, max_tariff) search range in LKR/kWh
        tolerance: IRR convergence tolerance
        max_iterations: Maximum solver iterations

    Returns:
        Required tariff in LKR/kWh

    Raises:
        ValueError: If solver fails to converge

    Example:
        >>> tariff = solve_for_tariff_given_irr(
        ...     "scenarios/dutchbay_master_config_v14.yaml",
        ...     {"project": {"capex_usd_per_kw": 900.0}},
        ...     target_irr=0.12
        ... )
        >>> print(f"Required tariff: LKR {tariff:.2f}/kWh")
    """
    if method != "bisection":
        raise ValueError(f"Unsupported solver method: {method}")

    low, high = bounds

    for iteration in range(max_iterations):
        mid = (low + high) / 2.0

        # Evaluate scenario with this tariff
        overrides = {**base_overrides}
        overrides.setdefault("financial", {})["tariff_lkr_per_kwh"] = mid

        try:
            kpis = evaluate_with_overrides(base_config_path, overrides)
            achieved_irr = kpis["project_irr"]
        except Exception as e:
            logger.warning(f"Evaluation failed at tariff={mid:.2f}: {e}")
            # If evaluation fails, assume tariff too low
            low = mid
            continue

        # Check convergence
        error = abs(achieved_irr - target_irr)
        if error < tolerance:
            logger.debug(
                f"Converged in {iteration+1} iterations: "
                f"tariff={mid:.2f}, IRR={achieved_irr:.4f} (target={target_irr:.4f})"
            )
            return mid

        # Binary search update
        if achieved_irr < target_irr:
            # Need higher tariff
            low = mid
        else:
            # Need lower tariff
            high = mid

    # Failed to converge
    raise ValueError(
        f"Solver failed to converge after {max_iterations} iterations. "
        f"Final range: [{low:.2f}, {high:.2f}] LKR/kWh"
    )


def solve_for_max_debt_given_dscr(
    base_config_path: str,
    base_overrides: dict[str, Any],
    target_dscr: float,
    bounds: tuple[float, float] = (1.0e6, 1.0e9),
    tolerance: float = 1000.0,
    max_iterations: int = 50,
) -> float:
    """
    Find maximum debt amount that maintains minimum DSCR covenant.

    Uses bisection to find the debt level where min(DSCR) equals
    the target covenant threshold.

    Args:
        base_config_path: Path to base scenario YAML
        base_overrides: Dict of sampled parameter values
        target_dscr: Minimum DSCR covenant (e.g., 1.25)
        bounds: (min_debt, max_debt) search range in USD
        tolerance: Convergence tolerance in USD
        max_iterations: Maximum solver iterations

    Returns:
        Maximum debt amount in USD

    Raises:
        ValueError: If solver fails to converge

    Example:
        >>> max_debt = solve_for_max_debt_given_dscr(
        ...     "scenarios/dutchbay_master_config_v14.yaml",
        ...     {"project": {"capex_usd_per_kw": 850.0}},
        ...     target_dscr=1.30
        ... )
        >>> print(f"Max debt at DSCR 1.30: ${max_debt:,.0f}")
    """
    low, high = bounds

    for iteration in range(max_iterations):
        mid = (low + high) / 2.0

        # Evaluate scenario with this debt level
        overrides = {**base_overrides}
        overrides.setdefault("financial", {})["debt_amount_usd"] = mid

        try:
            kpis = evaluate_with_overrides(base_config_path, overrides)
            achieved_dscr = kpis["dscr_min"]
        except Exception as e:
            logger.warning(f"Evaluation failed at debt=${mid:,.0f}: {e}")
            # If evaluation fails, assume debt too high
            high = mid
            continue

        # Check convergence
        error = abs(mid - (low + high) / 2.0)
        if error < tolerance:
            logger.debug(
                f"Converged in {iteration+1} iterations: "
                f"debt=${mid:,.0f}, DSCR={achieved_dscr:.2f} (target={target_dscr:.2f})"
            )
            return mid

        # Binary search update
        if achieved_dscr > target_dscr:
            # Can increase debt
            low = mid
        else:
            # Must decrease debt
            high = mid

    # Failed to converge
    raise ValueError(
        f"Solver failed to converge after {max_iterations} iterations. "
        f"Final range: [${low:,.0f}, ${high:,.0f}]"
    )


# Solver registry for extensibility
# Users can add custom solvers by adding to this dict
SOLVER_REGISTRY: dict[str, Callable[..., float]] = {
    "target_project_irr": solve_for_tariff_given_irr,
    "target_equity_irr": solve_for_tariff_given_irr,  # Same solver, different target
    "dscr_covenant": solve_for_max_debt_given_dscr,
}


def get_solver(derive_from: str) -> Callable[..., float]:
    """
    Get solver function from registry.

    Args:
        derive_from: Derivation type (e.g., "target_project_irr")

    Returns:
        Solver function

    Raises:
        KeyError: If solver not found in registry
    """
    if derive_from not in SOLVER_REGISTRY:
        raise KeyError(
            f"No solver registered for '{derive_from}'. "
            f"Available solvers: {list(SOLVER_REGISTRY.keys())}"
        )

    return SOLVER_REGISTRY[derive_from]
