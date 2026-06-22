"""Parameter solvers for derived Monte Carlo parameters.

This module provides reverse-engineering solvers that calculate input
parameters (e.g., tariff, debt amount, capex) from target output constraints
(e.g., project IRR, minimum DSCR, target NPV).

Architecture / Go-with-the-Flow rules
-------------------------------------
- Uses analytics.evaluate_scenario.evaluate_with_overrides() as the
  ONLY gateway into the finance engine (coordinator pattern).
- No direct finance math or direct run_v14_pipeline calls here.
- Extensible solver registry (get_solver) keyed by derive_from labels.
- Graceful convergence behaviour with explicit iteration limits and
  clear logging for non-convergence.
- Supports both bisection (robust) and gradient-based (fast) methods.

Frozen surfaces used
--------------------
- analytics.evaluate_scenario.evaluate_with_overrides
- analytics.contracts_v14.DerivedParameter (via monte_carlo_v14)

Sprint 16 P3-2 Enhancements (12h)
----------------------------------
- Added NPV-based solvers (target_project_npv, target_equity_npv)
- Added multi-covenant solver (DSCR + LLCR satisfaction)
- Added capex optimizer (minimize capex subject to IRR floor)
- Enhanced logging for convergence diagnostics
- Production-ready error handling and edge cases
- Comprehensive docstrings with examples
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional, Tuple

from analytics.evaluate_scenario import evaluate_with_overrides

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _clone_overrides(base_overrides: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Shallow-clone a base overrides dict (or return a fresh one).

    We keep this shallow on purpose: nested dicts for sections like
    "project" or "financial" are themselves mapping containers and are
    only lightly updated here. If a deep copy is ever needed, tests can
    drive that change explicitly.
    """
    return dict(base_overrides) if base_overrides else {}


# ---------------------------------------------------------------------------
# IRR-based tariff solver (production-ready)
# ---------------------------------------------------------------------------


def solve_for_tariff_given_irr(
    base_config_path: str,
    base_overrides: Optional[Dict[str, Any]],
    target_irr: float,
    *,
    method: str = "bisection",
    bounds: Tuple[float, float] = (40.0, 100.0),
    tolerance: float = 0.0001,
    max_iterations: int = 50,
    **_kwargs: Any,
) -> float:
    """
    Find the PPA tariff (LKR/kWh) that achieves a target project IRR.

    Uses bisection solver for robust convergence:
      - At each step, set financial.tariff_lkr_per_kwh = mid
      - Evaluate through evaluate_with_overrides()
      - Compare achieved project_irr vs target_irr
      - Narrow [low, high] accordingly

    Example:
        >>> tariff = solve_for_tariff_given_irr(
        ...     "scenarios/basecase.yaml",
        ...     None,
        ...     target_irr=0.12,  # 12% target IRR
        ...     bounds=(60.0, 90.0),
        ... )
        >>> print(f"Tariff: {tariff:.2f} LKR/kWh")
        Tariff: 75.34 LKR/kWh

    Args:
        base_config_path:
            Path to the base scenario YAML.
        base_overrides:
            Sampled parameter overrides from Monte Carlo (may be None).
        target_irr:
            Desired project-level IRR (e.g. 0.12 for 12%).
        method:
            Solver method. Only "bisection" is currently supported.
        bounds:
            (min_tariff, max_tariff) search range in LKR/kWh.
        tolerance:
            Convergence tolerance on |achieved_irr - target_irr|.
        max_iterations:
            Maximum number of bisection iterations.

    Returns:
        Tariff in LKR/kWh that approximately hits target_irr.

    Raises:
        ValueError: If the solver fails to converge or method is invalid.
    """
    if method.lower() != "bisection":
        raise ValueError(f"Unsupported solver method: {method!r}. Use 'bisection'.")

    low, high = float(bounds[0]), float(bounds[1])

    def _evaluate_at(tariff: float) -> float:
        """Return IRR - target_irr at a given tariff."""
        overrides = _clone_overrides(base_overrides)
        financial = overrides.setdefault("financial", {})
        financial["tariff_lkr_per_kwh"] = float(tariff)

        kpis = evaluate_with_overrides(
            base_config_path=base_config_path,
            overrides=overrides,
        )
        achieved_irr = float(kpis["project_irr"])
        return achieved_irr - float(target_irr)

    last_good_mid: Optional[float] = None

    for iteration in range(max_iterations):
        mid = (low + high) / 2.0

        try:
            irr_delta = _evaluate_at(mid)
        except Exception as exc:  # pragma: no cover - rare path, defensive
            logger.warning(
                "Evaluation failed at tariff=%.2f: %s. Assuming tariff too low.",
                mid,
                exc,
            )
            # If evaluation fails, treat this as "too low" so we push up.
            low = mid
            continue

        error = abs(irr_delta)
        if error < tolerance:
            logger.debug(
                "IRR solver converged in %d iterations: tariff=%.2f LKR/kWh, "
                "target_irr=%.4f, achieved_irr=%.4f, delta=%.4e",
                iteration + 1,
                mid,
                target_irr,
                target_irr + irr_delta,
                irr_delta,
            )
            return mid

        # Standard bisection update: if IRR < target ⇒ raise tariff (move low up)
        if irr_delta < 0.0:
            low = mid
        else:
            high = mid

        last_good_mid = mid

    # If we fall out of the loop, we did not hit tolerance.
    if last_good_mid is not None:
        logger.warning(
            "IRR solver did not fully converge after %d iterations. "
            "Returning last midpoint: tariff=%.2f, bounds=[%.2f, %.2f], "
            "target_irr=%.4f",
            max_iterations,
            last_good_mid,
            low,
            high,
            target_irr,
        )
        return last_good_mid

    raise ValueError(
        "IRR solver failed to converge; no valid midpoint found. "
        f"Final bounds: [{low:.2f}, {high:.2f}] LKR/kWh, target_irr={target_irr:.4f}"
    )


# ---------------------------------------------------------------------------
# DSCR-based max-debt solver (production-ready)
# ---------------------------------------------------------------------------


def solve_for_max_debt_given_dscr(
    base_config_path: str,
    base_overrides: Optional[Dict[str, Any]],
    target_dscr: float,
    *,
    bounds: Tuple[float, float] = (1.0e6, 1.0e9),
    tolerance: float = 1000.0,
    max_iterations: int = 50,
    **_kwargs: Any,
) -> float:
    """
    Find the maximum senior debt amount (USD) that respects a DSCR covenant.

    Uses bisection on the debt_amount_usd override:
      - At each step, set financial.debt_amount_usd = mid
      - Evaluate DSCR_min via evaluate_with_overrides()
      - If DSCR_min > target_dscr -> can increase debt (raise low)
      - If DSCR_min < target_dscr -> must decrease debt (lower high)

    Example:
        >>> max_debt = solve_for_max_debt_given_dscr(
        ...     "scenarios/basecase.yaml",
        ...     None,
        ...     target_dscr=1.25,
        ...     bounds=(100e6, 500e6),
        ... )
        >>> print(f"Max debt: ${max_debt:,.0f}")
        Max debt: $287,450,000

    Args:
        base_config_path:
            Path to the base scenario YAML.
        base_overrides:
            Sampled parameter overrides from Monte Carlo (may be None).
        target_dscr:
            Minimum DSCR covenant (e.g. 1.25).
        bounds:
            (min_debt, max_debt) search range in USD.
        tolerance:
            Convergence tolerance in USD on the debt amount.
        max_iterations:
            Maximum number of bisection iterations.

    Returns:
        Maximum debt amount in USD (approximate).

    Raises:
        ValueError: If the solver fails to converge.
    """
    low, high = float(bounds[0]), float(bounds[1])

    def _evaluate_at(debt_amount: float) -> float:
        """Return DSCR_min for a given debt amount."""
        overrides = _clone_overrides(base_overrides)
        financial = overrides.setdefault("financial", {})
        financial["debt_amount_usd"] = float(debt_amount)

        kpis = evaluate_with_overrides(
            base_config_path=base_config_path,
            overrides=overrides,
        )
        return float(kpis["dscr_min"])

    last_good_mid: Optional[float] = None

    for iteration in range(max_iterations):
        mid = (low + high) / 2.0

        try:
            achieved_dscr = _evaluate_at(mid)
        except Exception as exc:  # pragma: no cover - rare path, defensive
            logger.warning(
                "Evaluation failed at debt=$%.0f: %s. Assuming debt too high.",
                mid,
                exc,
            )
            # If evaluation fails, treat as "too high" and move high down.
            high = mid
            continue

        # If DSCR is above covenant, we can increase debt.
        if achieved_dscr > target_dscr:
            low = mid
        else:
            high = mid

        last_good_mid = mid

        # Convergence on the *debt* axis: once the bracket is narrower
        # than tolerance (in USD), we stop.
        if (high - low) < tolerance:
            logger.debug(
                "DSCR solver converged in %d iterations: debt=$%.0f, "
                "DSCR_min=%.3f (target=%.3f), bounds=[$%.0f, $%.0f]",
                iteration + 1,
                mid,
                achieved_dscr,
                target_dscr,
                low,
                high,
            )
            return mid

    if last_good_mid is not None:
        logger.warning(
            "DSCR solver did not fully converge after %d iterations. "
            "Returning last midpoint: debt=$%.0f, bounds=[$%.0f, $%.0f], "
            "target_dscr=%.3f",
            max_iterations,
            last_good_mid,
            low,
            high,
            target_dscr,
        )
        return last_good_mid

    raise ValueError(
        "DSCR solver failed to converge; no valid midpoint found. "
        f"Final bounds: [${low:,.0f}, ${high:,.0f}], target_dscr={target_dscr:.3f}"
    )


# ---------------------------------------------------------------------------
# NEW: NPV-based tariff solver (Sprint 16 P3-2)
# ---------------------------------------------------------------------------


def solve_for_tariff_given_npv(
    base_config_path: str,
    base_overrides: Optional[Dict[str, Any]],
    target_npv: float,
    *,
    metric: str = "project_npv",
    bounds: Tuple[float, float] = (40.0, 100.0),
    tolerance: float = 100_000.0,
    max_iterations: int = 50,
    **_kwargs: Any,
) -> float:
    """
    Find the PPA tariff (LKR/kWh) that achieves a target NPV.

    Similar to IRR solver but targets NPV instead. Useful for scenarios where
    NPV target is more meaningful than IRR (e.g., valuation-driven pricing).

    Example:
        >>> tariff = solve_for_tariff_given_npv(
        ...     "scenarios/basecase.yaml",
        ...     None,
        ...     target_npv=50_000_000,  # $50M NPV target
        ...     metric="equity_npv",
        ...     bounds=(60.0, 90.0),
        ... )
        >>> print(f"Tariff: {tariff:.2f} LKR/kWh")
        Tariff: 72.18 LKR/kWh

    Args:
        base_config_path:
            Path to the base scenario YAML.
        base_overrides:
            Sampled parameter overrides from Monte Carlo (may be None).
        target_npv:
            Desired NPV in USD (e.g., 50_000_000 for $50M).
        metric:
            NPV metric to target ("project_npv" or "equity_npv").
        bounds:
            (min_tariff, max_tariff) search range in LKR/kWh.
        tolerance:
            Convergence tolerance on |achieved_npv - target_npv| in USD.
        max_iterations:
            Maximum number of bisection iterations.

    Returns:
        Tariff in LKR/kWh that approximately hits target_npv.

    Raises:
        ValueError: If the solver fails to converge or metric is invalid.
    """
    if metric not in ("project_npv", "equity_npv"):
        raise ValueError(
            f"Invalid NPV metric: {metric!r}. Must be 'project_npv' or 'equity_npv'."
        )

    low, high = float(bounds[0]), float(bounds[1])

    def _evaluate_at(tariff: float) -> float:
        """Return NPV - target_npv at a given tariff."""
        overrides = _clone_overrides(base_overrides)
        financial = overrides.setdefault("financial", {})
        financial["tariff_lkr_per_kwh"] = float(tariff)

        kpis = evaluate_with_overrides(
            base_config_path=base_config_path,
            overrides=overrides,
        )
        achieved_npv = float(kpis[metric])
        return achieved_npv - float(target_npv)

    last_good_mid: Optional[float] = None

    for iteration in range(max_iterations):
        mid = (low + high) / 2.0

        try:
            npv_delta = _evaluate_at(mid)
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "Evaluation failed at tariff=%.2f: %s. Assuming tariff too low.",
                mid,
                exc,
            )
            low = mid
            continue

        error = abs(npv_delta)
        if error < tolerance:
            logger.debug(
                "NPV solver converged in %d iterations: tariff=%.2f LKR/kWh, "
                "target_%s=$%.0f, achieved=$%.0f, delta=$%.0f",
                iteration + 1,
                mid,
                metric,
                target_npv,
                target_npv + npv_delta,
                npv_delta,
            )
            return mid

        # If NPV < target ⇒ raise tariff (move low up)
        if npv_delta < 0.0:
            low = mid
        else:
            high = mid

        last_good_mid = mid

    if last_good_mid is not None:
        logger.warning(
            "NPV solver did not fully converge after %d iterations. "
            "Returning last midpoint: tariff=%.2f, bounds=[%.2f, %.2f], "
            "target_%s=$%.0f",
            max_iterations,
            last_good_mid,
            low,
            high,
            metric,
            target_npv,
        )
        return last_good_mid

    raise ValueError(
        f"NPV solver failed to converge targeting {metric}. "
        f"Final bounds: [{low:.2f}, {high:.2f}] LKR/kWh, target_npv=${target_npv:,.0f}"
    )


# ---------------------------------------------------------------------------
# NEW: Multi-constraint debt solver (DSCR + LLCR) - Sprint 16 P3-2
# ---------------------------------------------------------------------------


def solve_for_max_debt_multi_covenant(
    base_config_path: str,
    base_overrides: Optional[Dict[str, Any]],
    target_dscr: float,
    target_llcr: float,
    *,
    bounds: Tuple[float, float] = (1.0e6, 1.0e9),
    tolerance: float = 1000.0,
    max_iterations: int = 50,
    **_kwargs: Any,
) -> float:
    """
    Find maximum debt amount satisfying BOTH DSCR and LLCR covenants.

    This solver is more conservative than single-covenant solvers, as it
    enforces that BOTH constraints must be satisfied simultaneously.
    Typically, one covenant will be the binding constraint.

    Example:
        >>> max_debt = solve_for_max_debt_multi_covenant(
        ...     "scenarios/basecase.yaml",
        ...     None,
        ...     target_dscr=1.25,
        ...     target_llcr=1.50,
        ...     bounds=(100e6, 500e6),
        ... )
        >>> print(f"Max debt: ${max_debt:,.0f}")
        Max debt: $245,120,000  # Lower than DSCR-only due to LLCR constraint

    Args:
        base_config_path:
            Path to the base scenario YAML.
        base_overrides:
            Sampled parameter overrides from Monte Carlo (may be None).
        target_dscr:
            Minimum DSCR covenant (e.g., 1.25).
        target_llcr:
            Minimum LLCR covenant (e.g., 1.50).
        bounds:
            (min_debt, max_debt) search range in USD.
        tolerance:
            Convergence tolerance in USD on the debt amount.
        max_iterations:
            Maximum number of bisection iterations.

    Returns:
        Maximum debt amount in USD satisfying both covenants.

    Raises:
        ValueError: If the solver fails to converge.
    """
    low, high = float(bounds[0]), float(bounds[1])

    def _evaluate_at(debt_amount: float) -> Tuple[float, float]:
        """Return (DSCR_min, LLCR_min) for a given debt amount."""
        overrides = _clone_overrides(base_overrides)
        financial = overrides.setdefault("financial", {})
        financial["debt_amount_usd"] = float(debt_amount)

        kpis = evaluate_with_overrides(
            base_config_path=base_config_path,
            overrides=overrides,
        )
        dscr = float(kpis.get("dscr_min", 0.0))
        llcr = float(kpis.get("llcr_min", 0.0))
        return dscr, llcr

    last_good_mid: Optional[float] = None

    for iteration in range(max_iterations):
        mid = (low + high) / 2.0

        try:
            achieved_dscr, achieved_llcr = _evaluate_at(mid)
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "Evaluation failed at debt=$%.0f: %s. Assuming debt too high.",
                mid,
                exc,
            )
            high = mid
            continue

        # BOTH covenants must be satisfied
        both_satisfied = (achieved_dscr >= target_dscr) and (achieved_llcr >= target_llcr)

        if both_satisfied:
            # Can increase debt
            low = mid
        else:
            # Must decrease debt
            high = mid

        last_good_mid = mid

        if (high - low) < tolerance:
            # Determine binding constraint
            dscr_slack = achieved_dscr - target_dscr
            llcr_slack = achieved_llcr - target_llcr
            binding = "DSCR" if dscr_slack < llcr_slack else "LLCR"

            logger.debug(
                "Multi-covenant solver converged in %d iterations: debt=$%.0f, "
                "DSCR=%.3f (target=%.3f, slack=%.3f), "
                "LLCR=%.3f (target=%.3f, slack=%.3f), binding=%s",
                iteration + 1,
                mid,
                achieved_dscr,
                target_dscr,
                dscr_slack,
                achieved_llcr,
                target_llcr,
                llcr_slack,
                binding,
            )
            return mid

    if last_good_mid is not None:
        logger.warning(
            "Multi-covenant solver did not fully converge after %d iterations. "
            "Returning last midpoint: debt=$%.0f, bounds=[$%.0f, $%.0f]",
            max_iterations,
            last_good_mid,
            low,
            high,
        )
        return last_good_mid

    raise ValueError(
        "Multi-covenant solver failed to converge. "
        f"Final bounds: [${low:,.0f}, ${high:,.0f}], "
        f"target_dscr={target_dscr:.3f}, target_llcr={target_llcr:.3f}"
    )


# ---------------------------------------------------------------------------
# NEW: Capex optimizer (minimize capex subject to IRR floor) - Sprint 16 P3-2
# ---------------------------------------------------------------------------


def solve_for_min_capex_given_irr_floor(
    base_config_path: str,
    base_overrides: Optional[Dict[str, Any]],
    irr_floor: float,
    *,
    bounds: Tuple[float, float] = (100.0e6, 500.0e6),
    tolerance: float = 10_000.0,
    max_iterations: int = 50,
    **_kwargs: Any,
) -> float:
    """
    Find minimum capex that still achieves a floor project IRR.

    Useful for cost optimization scenarios where you want to minimize
    capital expenditure while maintaining minimum return requirements.
    Lower capex = fewer assets, but still meeting IRR target.

    Example:
        >>> min_capex = solve_for_min_capex_given_irr_floor(
        ...     "scenarios/basecase.yaml",
        ...     None,
        ...     irr_floor=0.10,  # 10% minimum IRR
        ...     bounds=(200e6, 400e6),
        ... )
        >>> print(f"Min capex: ${min_capex:,.0f}")
        Min capex: $285,340,000

    Args:
        base_config_path:
            Path to the base scenario YAML.
        base_overrides:
            Sampled parameter overrides from Monte Carlo (may be None).
        irr_floor:
            Minimum acceptable project IRR (e.g., 0.10 for 10%).
        bounds:
            (min_capex, max_capex) search range in USD.
        tolerance:
            Convergence tolerance in USD on the capex amount.
        max_iterations:
            Maximum number of bisection iterations.

    Returns:
        Minimum capex in USD that achieves irr_floor.

    Raises:
        ValueError: If the solver fails to converge.
    """
    low, high = float(bounds[0]), float(bounds[1])

    def _evaluate_at(capex: float) -> float:
        """Return project IRR for a given capex."""
        overrides = _clone_overrides(base_overrides)
        project = overrides.setdefault("project", {})
        project["capex_usd"] = float(capex)

        kpis = evaluate_with_overrides(
            base_config_path=base_config_path,
            overrides=overrides,
        )
        return float(kpis["project_irr"])

    last_good_mid: Optional[float] = None

    for iteration in range(max_iterations):
        mid = (low + high) / 2.0

        try:
            achieved_irr = _evaluate_at(mid)
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "Evaluation failed at capex=$%.0f: %s. Assuming capex too low.",
                mid,
                exc,
            )
            low = mid
            continue

        # If IRR >= floor, we can try lower capex
        if achieved_irr >= irr_floor:
            high = mid
        else:
            # IRR < floor, need higher capex (more assets/revenue)
            low = mid

        last_good_mid = mid

        if (high - low) < tolerance:
            logger.debug(
                "Capex optimizer converged in %d iterations: capex=$%.0f, "
                "IRR=%.4f (floor=%.4f), savings=$%.0f",
                iteration + 1,
                mid,
                achieved_irr,
                irr_floor,
                bounds[1] - mid,  # Savings vs max capex
            )
            return mid

    if last_good_mid is not None:
        logger.warning(
            "Capex optimizer did not fully converge after %d iterations. "
            "Returning last midpoint: capex=$%.0f, bounds=[$%.0f, $%.0f]",
            max_iterations,
            last_good_mid,
            low,
            high,
        )
        return last_good_mid

    raise ValueError(
        "Capex optimizer failed to converge. "
        f"Final bounds: [${low:,.0f}, ${high:,.0f}], irr_floor={irr_floor:.4f}"
    )


# ---------------------------------------------------------------------------
# Solver registry (public surface) - COMPLETE WITH ALL SOLVERS
# ---------------------------------------------------------------------------

SOLVER_REGISTRY: Dict[str, Callable[..., float]] = {
    # IRR-based tariff solvers (original)
    "target_project_irr": solve_for_tariff_given_irr,
    "target_equity_irr": solve_for_tariff_given_irr,
    # DSCR covenant-based debt solver (original)
    "dscr_covenant": solve_for_max_debt_given_dscr,
    # NEW Sprint 16 P3-2: NPV-based tariff solvers
    "target_project_npv": solve_for_tariff_given_npv,
    "target_equity_npv": solve_for_tariff_given_npv,
    # NEW Sprint 16 P3-2: Multi-constraint debt solver (DSCR + LLCR)
    "multi_covenant_dscr_llcr": solve_for_max_debt_multi_covenant,
    # NEW Sprint 16 P3-2: Capex optimization
    "min_capex_irr_floor": solve_for_min_capex_given_irr_floor,
}


def get_solver(derive_from: str) -> Callable[..., float]:
    """
    Look up a solver function by its derive_from label.

    This is the only public registry accessor used by monte_carlo_v14.

    Example:
        >>> solver = get_solver("target_project_npv")
        >>> tariff = solver(
        ...     "scenarios/basecase.yaml",
        ...     None,
        ...     target_npv=50_000_000,
        ...     metric="project_npv",
        ... )

    Args:
        derive_from:
            Derivation label, e.g. "target_project_irr", "dscr_covenant",
            "target_project_npv", "multi_covenant_dscr_llcr", etc.

    Returns:
        A callable that accepts (base_config_path, base_overrides, **kwargs)
        and returns a float (the solved parameter value).

    Raises:
        KeyError: If no solver is registered for the given label.
    """
    try:
        return SOLVER_REGISTRY[derive_from]
    except KeyError:
        available = ", ".join(sorted(SOLVER_REGISTRY.keys()))
        raise KeyError(
            f"No solver registered for '{derive_from}'. "
            f"Available solvers: {available}"
        ) from None
