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

Override paths drive the LIVE engine inputs
-------------------------------------------
Each solver perturbs the real nested config keys the v14 engine reads
(``tariff.lkr_per_kwh``, ``capex.usd_total``) — NOT the flat ``financial.*`` /
``project.capex_usd`` keys, which are not in the schema and never reached the engine
(Wave-2 fix). Every solver runs :func:`_assert_override_is_live` first: if the override
does not actually move the targeted KPI it raises rather than bisecting to a meaningless
bound. The max-debt solvers therefore fail loud on the default ``dual_dscr`` sizing —
the engine sizes debt to the covenant itself, so "max debt given DSCR" is its solved
gearing, not a sweepable absolute debt amount.

Frozen surfaces used
--------------------
- analytics.evaluate_scenario.evaluate_with_overrides

Status: standalone, on-demand analyst solver utility. These are read-only analysis tools with
NO committed-scenario caller — they perturb tariff/capex overrides purely to answer "what
input hits target X" and never touch a committed KPI. The module is still NOT wired into a
Hydra CLI (the historical "via monte_carlo_v14" claim was false — that module never imported
these solvers); a ``conf/cli_solvers.yaml`` + a wrapper alongside
``analytics/cli/cli_sensitivity_hydra.py`` is the deferred follow-up (issue #615). Any future
CLI exposure must be Hydra-only (argparse is banned repo-wide, GWTF R3/CLI-01).

W4 (issue #615) tariff-solver deltas
------------------------------------
- ``solve_for_tariff_given_irr`` generalized with a ``metric`` parameter
  (``project_irr`` | ``equity_irr``); project-IRR behaviour is the default and unchanged.
- ``solve_for_tariff_given_equity_irr`` added; ``SOLVER_REGISTRY['target_equity_irr']`` now
  resolves to it (it previously mislabelled the project-IRR solver, silently solving the
  wrong KPI). Fails loud when the scenario computes no equity distribution.
- ``solve_tariff_breakeven`` added — a first-class breakeven surface (NPV=0 or IRR-hurdle
  over tariff) returning the centralized ``contracts_v14.BreakevenResult`` with a ``status``
  and searched ``bracket`` instead of a bare float.

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
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

from analytics.contracts_v14 import BreakevenResult
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


def _require_kpi_present(kpis: Mapping[str, Any], kpi_key: str, *, lever: str) -> float:
    """Return ``kpis[kpi_key]`` as a float, failing loud (CESSPIT) if it is absent or None.

    Some KPIs are only emitted when a companion computation ran. In particular the engine
    merges ``equity_irr`` into the KPI surface only when an equity distribution was computed
    (``pipeline_v14_enhanced._update_kpis_with_equity_distribution``); a scenario with no
    equity distribution exposes no ``equity_irr``. Rather than let a bare ``KeyError`` (or a
    silent ``0.0`` default) leak out and make the solver answer the wrong question, raise a
    clear error naming the missing KPI and the lever so the analyst knows the scenario cannot
    support this solve.

    The "not exposed" hint is parameterized on ``kpi_key``: ``equity_irr``/``equity_npv`` are
    absent when the scenario computes no equity distribution; the project KPIs are absent only
    on a genuinely degenerate KPI surface (they always ride the base pipeline result).
    """
    if kpi_key not in kpis or kpis[kpi_key] is None:
        if kpi_key.startswith("equity_"):
            hint = f"{kpi_key} is only present when an equity distribution is computed"
        else:
            hint = f"the scenario's KPI surface does not include {kpi_key}"
        raise ValueError(
            f"Solver lever {lever!r} targets KPI {kpi_key!r}, but this scenario does not "
            f"expose it ({hint}). Refusing to solve on a missing KPI — choose a scenario "
            f"that computes it, or target a KPI the scenario emits."
        )
    return float(kpis[kpi_key])


def _assert_override_is_live(
    base_config_path: str,
    base_overrides: Optional[Dict[str, Any]],
    apply: Callable[[Dict[str, Any], float], None],
    probes: Tuple[float, float],
    kpi_key: str,
    *,
    lever: str,
) -> None:
    """Fail loud if the solver's override does not actually move the targeted KPI.

    A solver that bisects on an override the engine never reads silently converges to a
    bound and reports a meaningless answer (the Wave-2 finding: tariff/capex/debt solvers
    wrote dead paths). Before solving, evaluate the base config at two probe values; if
    ``kpi_key`` is unchanged the override is a DEAD lever for this scenario — a wrong key,
    or one the engine auto-overrides (e.g. debt amount/ratio under dual_dscr sizing). Raise
    rather than return a fake bound.

    The probe evaluations also gate KPI presence via :func:`_require_kpi_present`, so a
    scenario missing the targeted KPI (e.g. ``equity_irr`` with no equity distribution) fails
    loud here with a clear message before any bisection begins.
    """
    lo_over = _clone_overrides(base_overrides)
    apply(lo_over, float(probes[0]))
    hi_over = _clone_overrides(base_overrides)
    apply(hi_over, float(probes[1]))
    lo = _require_kpi_present(
        evaluate_with_overrides(base_config_path=base_config_path, overrides=lo_over),
        kpi_key,
        lever=lever,
    )
    hi = _require_kpi_present(
        evaluate_with_overrides(base_config_path=base_config_path, overrides=hi_over),
        kpi_key,
        lever=lever,
    )
    if abs(hi - lo) < 1e-9:
        raise ValueError(
            f"Solver lever {lever!r} does not move {kpi_key} for this scenario "
            f"({kpi_key}={lo:.6g} at both probe values {probes}). The override is not a "
            f"live engine input here (wrong key, or auto-sized by the engine — e.g. debt "
            f"under dual_dscr) — refusing to return a meaningless solver bound."
        )


def _assert_target_bracketed(
    delta_low: float,
    delta_high: float,
    *,
    label: str,
    low: float,
    high: float,
    target: float,
    tolerance: float,
) -> None:
    """Fail loud when a bisection target is not bracketed by ``[f(low), f(high)]``.

    Each delta-root solver's ``_evaluate_at`` returns ``achieved - target``. A root lies in
    ``[low, high]`` only if the two endpoint deltas straddle zero. If both share a sign (and
    neither is within tolerance), the target is unreachable in the bounds and bisection
    would silently converge to a bound and return a meaningless answer — raise instead,
    naming the achievable range.
    """
    if abs(delta_low) <= tolerance or abs(delta_high) <= tolerance:
        return  # a bound already (nearly) hits the target
    if (delta_low > 0.0) == (delta_high > 0.0):  # same sign -> no root bracketed
        raise ValueError(
            f"{label}: target {target:.6g} is not achievable within bounds "
            f"[{low:.6g}, {high:.6g}]; achievable range is "
            f"[{target + min(delta_low, delta_high):.6g}, "
            f"{target + max(delta_low, delta_high):.6g}]. Widen the bounds."
        )


def _bracket_deltas(
    evaluate_at: Callable[[float], float], low: float, high: float
) -> Tuple[Optional[float], Optional[float]]:
    """Return (f(low), f(high)) for the bracketing precheck, or (None, None) if a bound
    evaluation raises (let the solver's own loop handle that degenerate case)."""
    try:
        return evaluate_at(low), evaluate_at(high)
    except Exception:  # pragma: no cover - defensive; main loop handles eval failures
        return None, None


# ---------------------------------------------------------------------------
# IRR-based tariff solver (production-ready)
# ---------------------------------------------------------------------------


IRR_METRICS = ("project_irr", "equity_irr")


def solve_for_tariff_given_irr(
    base_config_path: str,
    base_overrides: Optional[Dict[str, Any]],
    target_irr: float,
    *,
    metric: str = "project_irr",
    method: str = "bisection",
    bounds: Tuple[float, float] = (40.0, 100.0),
    tolerance: float = 0.0001,
    max_iterations: int = 50,
    **_kwargs: Any,
) -> float:
    """
    Find the PPA tariff (LKR/kWh) that achieves a target IRR.

    Targets either the project IRR (default) or the equity IRR, selected by ``metric``.
    Uses bisection solver for robust convergence:
      - At each step, set tariff.lkr_per_kwh = mid (the LIVE engine input)
      - Evaluate through evaluate_with_overrides()
      - Compare achieved ``metric`` vs target_irr
      - Narrow [low, high] accordingly

    The equity-IRR path fails loud (CESSPIT) if the scenario computes no equity distribution
    (``equity_irr`` absent from the KPI surface) rather than silently solving a different KPI —
    the ``_assert_override_is_live`` precheck routes both probes through
    :func:`_require_kpi_present`.

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
            Desired IRR (e.g. 0.12 for 12%), interpreted against ``metric``.
        metric:
            IRR metric to target ("project_irr" or "equity_irr").
        method:
            Solver method. Only "bisection" is currently supported.
        bounds:
            (min_tariff, max_tariff) search range in LKR/kWh.
        tolerance:
            Convergence tolerance on |achieved_irr - target_irr|.
        max_iterations:
            Maximum number of bisection iterations.

    Returns:
        Tariff in LKR/kWh that approximately hits target_irr. NOTE: on iteration exhaustion
        WITHOUT meeting ``tolerance`` this returns the last evaluated midpoint (a best-effort
        bound) and only logs a warning — it does NOT raise. A ``ValueError`` is raised only
        when NO midpoint could be evaluated at all (every bound evaluation failed). Callers
        that need a guaranteed-within-tolerance answer must re-verify the returned tariff
        (see :func:`solve_tariff_breakeven`, which does exactly that before reporting
        ``status="converged"``).

    Raises:
        ValueError: If ``method`` is invalid, ``metric`` is invalid, the target is not
            bracketed by the bounds, the override is a dead lever, (for ``equity_irr``) the
            scenario exposes no equity distribution, or no valid midpoint could be evaluated.
            Iteration exhaustion short of ``tolerance`` does NOT raise (see Returns).
    """
    if method.lower() != "bisection":
        raise ValueError(f"Unsupported solver method: {method!r}. Use 'bisection'.")
    if metric not in IRR_METRICS:
        raise ValueError(
            f"Invalid IRR metric: {metric!r}. Must be one of {IRR_METRICS}."
        )

    low, high = float(bounds[0]), float(bounds[1])

    def _apply_tariff(overrides: Dict[str, Any], tariff: float) -> None:
        # LIVE engine path is tariff.lkr_per_kwh (NOT the dead financial.tariff_lkr_per_kwh).
        overrides.setdefault("tariff", {})["lkr_per_kwh"] = float(tariff)

    _assert_override_is_live(
        base_config_path,
        base_overrides,
        _apply_tariff,
        (low, high),
        metric,
        lever="tariff.lkr_per_kwh",
    )

    def _evaluate_at(tariff: float) -> float:
        """Return achieved IRR - target_irr at a given tariff."""
        overrides = _clone_overrides(base_overrides)
        _apply_tariff(overrides, tariff)

        kpis = evaluate_with_overrides(
            base_config_path=base_config_path,
            overrides=overrides,
        )
        achieved_irr = _require_kpi_present(kpis, metric, lever="tariff.lkr_per_kwh")
        return achieved_irr - float(target_irr)

    # Bracketing precheck: fail loud if target_irr is outside the achievable IRR range over
    # [low, high] tariff, rather than silently bisecting to a bound (round-2 finding).
    _d_low, _d_high = _bracket_deltas(_evaluate_at, low, high)
    if _d_low is not None and _d_high is not None:
        _assert_target_bracketed(
            _d_low,
            _d_high,
            label="solve_for_tariff_given_irr",
            low=low,
            high=high,
            target=float(target_irr),
            tolerance=tolerance,
        )

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


def solve_for_tariff_given_equity_irr(
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
    """Find the PPA tariff (LKR/kWh) that achieves a target EQUITY IRR.

    Thin, registry-friendly wrapper around :func:`solve_for_tariff_given_irr` pinned to the
    ``equity_irr`` KPI. This is the solver behind ``SOLVER_REGISTRY['target_equity_irr']``;
    the registry key previously (mis)pointed at the project-IRR solver, silently answering
    the wrong question. Fails loud (CESSPIT) if the scenario computes no equity distribution
    (``equity_irr`` absent) rather than falling back to project IRR.

    Args mirror :func:`solve_for_tariff_given_irr` (``metric`` is fixed to ``equity_irr``).
    """
    return solve_for_tariff_given_irr(
        base_config_path,
        base_overrides,
        target_irr,
        metric="equity_irr",
        method=method,
        bounds=bounds,
        tolerance=tolerance,
        max_iterations=max_iterations,
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

    def _apply_debt(overrides: Dict[str, Any], debt_amount: float) -> None:
        overrides.setdefault("financial", {})["debt_amount_usd"] = float(debt_amount)

    # The v14 engine SIZES debt itself (Financing_Terms.debt_sizing: dual_dscr auto-solves
    # gearing to target DSCR); there is no absolute debt-amount input. So sweeping
    # debt_amount_usd does not move dscr_min and the self-check fails loud — "max debt given
    # DSCR" IS the engine's solved gearing, not a solver sweep. (Kept fail-loud rather than
    # returning a silent bound; see the Wave-2 audit finding.)
    _assert_override_is_live(
        base_config_path,
        base_overrides,
        _apply_debt,
        (low, high),
        "dscr_min",
        lever="financial.debt_amount_usd",
    )

    def _evaluate_at(debt_amount: float) -> float:
        """Return DSCR_min for a given debt amount."""
        overrides = _clone_overrides(base_overrides)
        _apply_debt(overrides, debt_amount)

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
        Tariff in LKR/kWh that approximately hits target_npv. NOTE: on iteration exhaustion
        WITHOUT meeting ``tolerance`` this returns the last evaluated midpoint (a best-effort
        bound) and only logs a warning — it does NOT raise. A ``ValueError`` is raised only
        when NO midpoint could be evaluated at all. Callers needing a guaranteed-within-
        tolerance answer must re-verify the returned tariff (see
        :func:`solve_tariff_breakeven`).

    Raises:
        ValueError: If ``metric`` is invalid, the target is not bracketed by the bounds, the
            override is a dead lever, or no valid midpoint could be evaluated. Iteration
            exhaustion short of ``tolerance`` does NOT raise (see Returns).
    """
    if metric not in ("project_npv", "equity_npv"):
        raise ValueError(
            f"Invalid NPV metric: {metric!r}. Must be 'project_npv' or 'equity_npv'."
        )

    low, high = float(bounds[0]), float(bounds[1])

    def _apply_tariff(overrides: Dict[str, Any], tariff: float) -> None:
        # LIVE engine path is tariff.lkr_per_kwh (NOT the dead financial.tariff_lkr_per_kwh).
        overrides.setdefault("tariff", {})["lkr_per_kwh"] = float(tariff)

    _assert_override_is_live(
        base_config_path,
        base_overrides,
        _apply_tariff,
        (low, high),
        metric,
        lever="tariff.lkr_per_kwh",
    )

    def _evaluate_at(tariff: float) -> float:
        """Return NPV - target_npv at a given tariff."""
        overrides = _clone_overrides(base_overrides)
        _apply_tariff(overrides, tariff)

        kpis = evaluate_with_overrides(
            base_config_path=base_config_path,
            overrides=overrides,
        )
        achieved_npv = float(kpis[metric])
        return achieved_npv - float(target_npv)

    # Bracketing precheck: fail loud if target_npv is unreachable over [low, high] tariff
    # rather than bisecting to a meaningless bound (round-2 finding).
    _d_low, _d_high = _bracket_deltas(_evaluate_at, low, high)
    if _d_low is not None and _d_high is not None:
        _assert_target_bracketed(
            _d_low,
            _d_high,
            label="solve_for_tariff_given_npv",
            low=low,
            high=high,
            target=float(target_npv),
            tolerance=tolerance,
        )

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

    def _apply_debt(overrides: Dict[str, Any], debt_amount: float) -> None:
        overrides.setdefault("financial", {})["debt_amount_usd"] = float(debt_amount)

    # As with solve_for_max_debt_given_dscr: debt is engine-sized (dual_dscr), so an absolute
    # debt-amount sweep does not move the covenants — fail loud instead of returning a bound.
    _assert_override_is_live(
        base_config_path,
        base_overrides,
        _apply_debt,
        (low, high),
        "dscr_min",
        lever="financial.debt_amount_usd",
    )

    def _evaluate_at(debt_amount: float) -> Tuple[float, float]:
        """Return (DSCR_min, LLCR_min) for a given debt amount."""
        overrides = _clone_overrides(base_overrides)
        _apply_debt(overrides, debt_amount)

        kpis = evaluate_with_overrides(
            base_config_path=base_config_path,
            overrides=overrides,
        )
        dscr = float(kpis.get("dscr_min", 0.0))
        # The engine emits the loan-life coverage ratio under "llcr"; the old
        # "llcr_min" key never existed, so LLCR read 0.0 and the covenant could
        # never be satisfied -> debt always collapsed to the floor.
        llcr = float(kpis.get("llcr", 0.0))
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
        both_satisfied = (achieved_dscr >= target_dscr) and (
            achieved_llcr >= target_llcr
        )

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
    Find the MAXIMUM capex at which the project IRR still meets a floor (the
    affordable-capex ceiling / breakeven).

    In this engine ``capex.usd_total`` is pure cost — revenue is driven by
    ``capacity_factor x capacity_mw``, independent of it — so project IRR DECREASES
    as capex rises. The feasible set is therefore ``capex <= breakeven`` and the
    useful answer is the largest capex budget that still clears ``irr_floor`` (used
    for "how much can we spend and still hit X% IRR"). The historical "minimize
    capex" framing assumed capex scaled revenue, which it does not here.

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

    def _apply_capex(overrides: Dict[str, Any], capex: float) -> None:
        # LIVE engine path is capex.usd_total (NOT the dead project.capex_usd).
        # #738: this is the PRE-LEVY base — under a taxes_indirect config the
        # pipeline re-applies the import levies on top of each candidate, so the
        # solved value is the pre-levy base that clears the floor levy-inclusive.
        overrides.setdefault("capex", {})["usd_total"] = float(capex)

    _assert_override_is_live(
        base_config_path,
        base_overrides,
        _apply_capex,
        (low, high),
        "project_irr",
        lever="capex.usd_total",
    )

    def _evaluate_at(capex: float) -> float:
        """Return project IRR for a given capex."""
        overrides = _clone_overrides(base_overrides)
        _apply_capex(overrides, capex)

        kpis = evaluate_with_overrides(
            base_config_path=base_config_path,
            overrides=overrides,
        )
        return float(kpis["project_irr"])

    # Bracketing precheck (round-2 finding, extended here in round 3): fail loud if irr_floor
    # is unreachable over [low, high] capex rather than silently bisecting to a bound. IRR
    # DECREASES as capex rises, so the achievable IRR range is [irr(high), irr(low)]; the
    # delta = irr(capex) - irr_floor and the same-sign test detects an unbracketed floor
    # regardless of monotonicity direction. (IRR tolerance, not the USD capex tolerance.)
    _d_low, _d_high = _bracket_deltas(lambda c: _evaluate_at(c) - irr_floor, low, high)
    if _d_low is not None and _d_high is not None:
        _assert_target_bracketed(
            _d_low,
            _d_high,
            label="solve_for_min_capex_given_irr_floor",
            low=low,
            high=high,
            target=float(irr_floor),
            tolerance=1e-4,
        )

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

        # project IRR DECREASES as capex rises (capex.usd_total is pure cost; revenue is
        # driven by capacity_factor x capacity_mw, independent of it). So the feasible region
        # is capex <= the breakeven where IRR == floor, and the useful answer is the MAXIMUM
        # capex still meeting the floor (the affordable-capex ceiling). Bisect toward it:
        if achieved_irr >= irr_floor:
            # clears the floor -> capex can rise toward the breakeven
            low = mid
        else:
            # IRR below floor -> capex is too high, reduce it
            high = mid

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
# NEW: First-class tariff-breakeven surface (returns contracts_v14.BreakevenResult)
# ---------------------------------------------------------------------------

_BREAKEVEN_METRICS = ("project_npv", "equity_npv", "project_irr", "equity_irr")


def solve_tariff_breakeven(
    base_config_path: str,
    base_overrides: Optional[Dict[str, Any]] = None,
    *,
    metric: str = "project_npv",
    target_value: float = 0.0,
    bounds: Tuple[float, float] = (40.0, 100.0),
    tolerance: Optional[float] = None,
    max_iterations: int = 50,
) -> BreakevenResult:
    """Solve the breakeven PPA tariff (LKR/kWh) for a target KPI, as a structured result.

    First-class convenience over the tariff root-finders that returns the centralized
    :class:`analytics.contracts_v14.BreakevenResult` (CCCDIR: no new contract types outside
    ``contracts_v14``) instead of a bare float, so a caller always gets the variable, the
    target, and — critically — the ``status`` and achievable ``bracket`` even when the target
    is not reachable or the solve does not converge.

    Two breakeven flavours, both driven ONLY through the ``evaluate_with_overrides`` gateway
    (ARCH-02: no direct IRR/NPV math here — that lives in ``finance/irr.py``):

    - NPV breakeven (``metric`` = ``project_npv`` | ``equity_npv``): the tariff at which NPV
      equals ``target_value`` (default 0.0, i.e. the classic NPV=0 breakeven), via
      :func:`solve_for_tariff_given_npv`.
    - IRR-hurdle breakeven (``metric`` = ``project_irr`` | ``equity_irr``): the tariff at which
      that IRR equals ``target_value`` (the hurdle rate), via
      :func:`solve_for_tariff_given_irr`. The ``equity_irr`` flavour fails loud if the scenario
      computes no equity distribution.

    Fail-loud at the numeric core for structural problems: the underlying solvers raise on a
    missing lever, an unbracketed target, or a missing KPI. This wrapper translates those raises
    into a ``BreakevenResult`` with ``status="unbracketed"`` (or ``"error"``) and the searched
    ``bracket`` populated, rather than propagating a bare exception — so breakeven is safe to
    call in a batch analytics sweep.

    HONEST convergence status (Fable blocker on #615): the underlying root-finders do NOT raise
    on iteration exhaustion — they return the last evaluated midpoint (a best-effort bound) with
    only a ``logger.warning`` — so a bare ``except`` would never see non-convergence and would
    stamp ``status="converged"`` on a bound that misses the target by orders of magnitude. This
    wrapper therefore RE-VERIFIES the returned tariff through one extra ``evaluate_with_overrides``
    gateway evaluation: ``status="converged"`` is emitted ONLY when the achieved metric is within
    ``tolerance`` of ``target_value``. When it is not, the result reports
    ``status="max_iterations"`` with the residual (``achieved``, ``target``, ``abs_residual``,
    ``tolerance``) captured in ``metadata`` so the analyst sees the true miss instead of a false
    "converged".

    Args:
        base_config_path: Path to the base scenario YAML.
        base_overrides: Optional nested overrides applied before solving (may be None).
        metric: Target KPI — one of ``project_npv``, ``equity_npv``, ``project_irr``,
            ``equity_irr``.
        target_value: The breakeven target value for ``metric`` (0.0 gives NPV=0; a hurdle
            rate, e.g. 0.12, for the IRR flavours).
        bounds: (min_tariff, max_tariff) search range in LKR/kWh.
        tolerance: Convergence tolerance in ``metric`` units; defaults to a metric-appropriate
            value (1e5 USD for NPV, 1e-4 for IRR) when None.
        max_iterations: Maximum bisection iterations.

    Returns:
        A :class:`BreakevenResult` with ``variable="tariff.lkr_per_kwh"``, the requested
        ``target_metric`` / ``target_value``, and ``status`` in
        {``converged``, ``max_iterations``, ``unbracketed``, ``error``}. ``breakeven_value``
        is the solved tariff only when ``status="converged"`` (genuinely within ``tolerance``);
        on ``max_iterations`` it is None and the residual is in ``metadata``. ``bracket`` records
        the searched tariff range.

    Raises:
        ValueError: Only for a programming error — an unknown ``metric``. Scenario/target
            infeasibility and non-convergence are reported via ``status``, not raised.
    """
    if metric not in _BREAKEVEN_METRICS:
        raise ValueError(
            f"Invalid breakeven metric: {metric!r}. Must be one of {_BREAKEVEN_METRICS}."
        )

    is_irr_metric = metric in IRR_METRICS
    eff_tolerance = (
        tolerance if tolerance is not None else (1e-4 if is_irr_metric else 1e5)
    )
    bracket = (float(bounds[0]), float(bounds[1]))

    try:
        if is_irr_metric:
            solved = solve_for_tariff_given_irr(
                base_config_path,
                base_overrides,
                float(target_value),
                metric=metric,
                bounds=bounds,
                tolerance=eff_tolerance,
                max_iterations=max_iterations,
            )
        else:
            solved = solve_for_tariff_given_npv(
                base_config_path,
                base_overrides,
                float(target_value),
                metric=metric,
                bounds=bounds,
                tolerance=eff_tolerance,
                max_iterations=max_iterations,
            )
    except ValueError as exc:
        # Unbracketed / missing-lever / missing-KPI: report as a structured result rather than a
        # bare float or a raw exception. The achievable-range guard raises "not achievable within
        # bounds"; classify that as an explicit "unbracketed" status.
        status = (
            "unbracketed" if "not achievable within bounds" in str(exc) else "error"
        )
        return BreakevenResult(
            variable="tariff.lkr_per_kwh",
            target_metric=metric,
            target_value=float(target_value),
            breakeven_value=None,
            status=status,
            bracket=bracket,
            metadata={"error": str(exc)},
        )

    # HONEST convergence check (Fable blocker on #615). The root-finders return the last
    # midpoint on iteration exhaustion (they raise ONLY when NO midpoint could be evaluated),
    # so a returned float is NOT proof of convergence. Re-verify by evaluating the achieved
    # metric at the solved tariff through the same gateway; emit status="converged" ONLY when
    # |achieved - target| <= tolerance, else status="max_iterations" with the residual.
    try:
        verify_kpis = evaluate_with_overrides(
            base_config_path=base_config_path,
            overrides={
                **_clone_overrides(base_overrides),
                "tariff": {"lkr_per_kwh": float(solved)},
            },
        )
        achieved = _require_kpi_present(verify_kpis, metric, lever="tariff.lkr_per_kwh")
    except (
        ValueError
    ) as exc:  # pragma: no cover - defensive: solve succeeded, re-eval failed
        return BreakevenResult(
            variable="tariff.lkr_per_kwh",
            target_metric=metric,
            target_value=float(target_value),
            breakeven_value=None,
            status="error",
            bracket=bracket,
            metadata={"error": str(exc)},
        )

    abs_residual = abs(achieved - float(target_value))
    if abs_residual <= eff_tolerance:
        return BreakevenResult(
            variable="tariff.lkr_per_kwh",
            target_metric=metric,
            target_value=float(target_value),
            breakeven_value=float(solved),
            status="converged",
            bracket=bracket,
            metadata={
                "tolerance": eff_tolerance,
                "max_iterations": max_iterations,
                "achieved": achieved,
                "abs_residual": abs_residual,
            },
        )

    # Solver exhausted its iterations without meeting tolerance: the returned float is a
    # best-effort bound, NOT a converged breakeven. Report it honestly with the residual so the
    # analyst sees the true miss rather than a false "converged".
    logger.warning(
        "Tariff-breakeven did NOT converge for metric=%s: solved tariff=%.4f achieves "
        "%s=%.6g vs target=%.6g (|residual|=%.6g > tolerance=%.6g). Reporting "
        "status='max_iterations'.",
        metric,
        float(solved),
        metric,
        achieved,
        float(target_value),
        abs_residual,
        eff_tolerance,
    )
    return BreakevenResult(
        variable="tariff.lkr_per_kwh",
        target_metric=metric,
        target_value=float(target_value),
        breakeven_value=None,
        status="max_iterations",
        bracket=bracket,
        metadata={
            "tolerance": eff_tolerance,
            "max_iterations": max_iterations,
            "achieved": achieved,
            "abs_residual": abs_residual,
            "last_bound_tariff": float(solved),
        },
    )


# ---------------------------------------------------------------------------
# Solver registry (public surface) - COMPLETE WITH ALL SOLVERS
# ---------------------------------------------------------------------------

SOLVER_REGISTRY: Dict[str, Callable[..., float]] = {
    # IRR-based tariff solvers (original)
    "target_project_irr": solve_for_tariff_given_irr,
    # target_equity_irr previously (mis)pointed at the project-IRR solver, silently solving
    # the wrong KPI; it now resolves to the equity-IRR-pinned solver (fails loud if the
    # scenario computes no equity distribution).
    "target_equity_irr": solve_for_tariff_given_equity_irr,
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

    This is the public registry accessor for the on-demand solver surface. (It is not wired
    into a live pipeline caller — the historical "used by monte_carlo_v14" note was false.)

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
