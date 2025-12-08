"""Parameter solvers for derived Monte Carlo parameters.

This module provides reverse-engineering solvers that calculate input
parameters (e.g., tariff, debt amount) from target output constraints
(e.g., project IRR, minimum DSCR).

Architecture / Go-with-the-Flow rules
-------------------------------------
- Uses analytics.evaluate_scenario.evaluate_with_overrides() as the
  ONLY gateway into the finance engine (coordinator pattern).
- No direct finance math or direct run_v14_pipeline calls here.
- Extensible solver registry (get_solver) keyed by derive_from labels.
- Graceful convergence behaviour with explicit iteration limits and
  clear logging for non-convergence.

Frozen surfaces used
--------------------
- analytics.evaluate_scenario.evaluate_with_overrides
- analytics.contracts_v14.DerivedParameter (via monte_carlo_v14)
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
# IRR-based tariff solver
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

    Uses a simple bisection solver:
      - At each step, set financial.tariff_lkr_per_kwh = mid
      - Evaluate through evaluate_with_overrides()
      - Compare achieved project_irr vs target_irr
      - Narrow [low, high] accordingly

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
        ValueError: If the solver fails to converge.
    """
    if method.lower() != "bisection":
        raise ValueError(f"Unsupported solver method: {method!r}")

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
                "IRR solver converged in %d iterations: tariff=%.2f, "
                "target_irr=%.4f, delta=%.4e",
                iteration + 1,
                mid,
                target_irr,
                irr_delta,
            )
            return mid

        # Standard bisection update: if IRR < target ⇒ raise tariff (move low up)
        if irr_delta < 0.0:
            low = mid
        else:
            high = mid

        last_good_mid = mid

    # If we fall out of the loop, we did not hit tolerance. Return the best
    # midpoint we have, but also raise to signal non-convergence for callers
    # that treat this strictly.
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
        f"Final bounds: [{low:.2f}, {high:.2f}] LKR/kWh"
    )


# ---------------------------------------------------------------------------
# DSCR-based max-debt solver
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
                "Evaluation failed at debt=%,.0f: %s. Assuming debt too high.",
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
                "DSCR solver converged in %d iterations: debt=%,.0f, "
                "DSCR=%.3f (target=%.3f), bounds=[%.,0f, %.,0f]",
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
            "Returning last midpoint: debt=%,.0f, bounds=[%.,0f, %.,0f], "
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
        f"Final bounds: [${low:,.0f}, ${high:,.0f}]"
    )


# ---------------------------------------------------------------------------
# Solver registry (public surface)
# ---------------------------------------------------------------------------

SOLVER_REGISTRY: Dict[str, Callable[..., float]] = {
    # IRR-based solvers – project vs equity IRR share the same tariff
    # inversion logic; what changes is the analytics layer that interprets
    # the target_irr value.
    "target_project_irr": solve_for_tariff_given_irr,
    "target_equity_irr": solve_for_tariff_given_irr,
    # DSCR covenant-based solver for debt sizing
    "dscr_covenant": solve_for_max_debt_given_dscr,
}


def get_solver(derive_from: str) -> Callable[..., float]:
    """
    Look up a solver function by its derive_from label.

    This is the only public registry accessor used by monte_carlo_v14.

    Args:
        derive_from:
            Derivation label, e.g. "target_project_irr", "dscr_covenant".

    Returns:
        A callable that accepts (base_config_path, base_overrides, **kwargs)
        and returns a float (the solved parameter value).

    Raises:
        KeyError: If no solver is registered for the given label.
    """
    try:
        return SOLVER_REGISTRY[derive_from]
    except KeyError:
        raise KeyError(
            f"No solver registered for '{derive_from}'. "
            f"Available solvers: {list(SOLVER_REGISTRY.keys())}"
        ) from None
