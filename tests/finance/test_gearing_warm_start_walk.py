"""The warm-started gearing walk's one-step, floor and cap boundaries.

``tests/finance/test_gearing_warm_start.py`` starts the walk 0 and 8 grid steps from the
answer. A walk-down that skips the next grid point, or a walk-up that stops one step
short of ``max_ratio``, passes those starts (#1527 assurance A-1, domain D-1). These
tests start the walk one step either side of the answer, at the step floor, and below a
``max_ratio`` that itself holds the target, on the same small synthetic schedule.
"""

from __future__ import annotations

from typing import Any

import pytest

from finance import debt_v14

MAX_RATIO = 0.7
STEP = 0.0025


def _config() -> dict[str, Any]:
    return {
        "capex": {"usd_total": 100.0},
        "debt_ratio": MAX_RATIO,
        "tenor_years": 8,
        "construction_periods": 1,
        "amortization_style": "sculpted",
        "target_dscr": 1.30,
        "mix": {"usd_commercial_min": 1.0},
        "rates": {"usd_nominal": 0.08},
    }


def _rows() -> list[dict[str, Any]]:
    return [{"year": i + 1, "cfads_usd": 8.0} for i in range(8)]


def _solve(target_dscr: float, start_hint: float | None = None) -> float:
    kwargs: dict[str, Any] = {} if start_hint is None else {"start_hint": start_hint}
    return debt_v14._solve_gearing_for_dscr(
        _config(), _rows(), target_dscr=target_dscr, max_ratio=MAX_RATIO, **kwargs
    )


def _grid() -> list[float]:
    """The scan's grid, built the way the scan builds it (highest gearing first)."""
    grid: list[float] = []
    ratio = MAX_RATIO
    while ratio > 0.0:
        grid.append(ratio)
        ratio -= STEP
    return grid


@pytest.mark.parametrize(
    "offset_steps",
    [
        pytest.param(-1, id="one-above"),
        pytest.param(1, id="one-below"),
        pytest.param(None, id="from-the-floor"),
    ],
)
def test_the_walk_lands_on_the_cold_answer_from_one_step_away(
    offset_steps: int | None,
) -> None:
    """One step either side is the likeliest movement between fixed-point passes.

    It is also the start that catches a walk skipping or repeating a grid point. The
    step floor is itself a grid point, so a hint there walks up too.
    """
    cold = _solve(1.30)
    assert 0.1 < cold < 0.6, cold  # interior, so both one-step starts exist
    grid = _grid()
    at = next(i for i, r in enumerate(grid) if round(r, 6) == cold)
    index = len(grid) - 1 if offset_steps is None else at + offset_steps
    assert _solve(1.30, start_hint=round(grid[index], 6)) == cold


@pytest.mark.parametrize("offset_steps", [0, 1, 8], ids=["at", "one-below", "below"])
def test_the_walk_up_stops_at_the_cap(offset_steps: int) -> None:
    """When max_ratio itself holds the target, the walk up ends on max_ratio exactly."""
    cold = _solve(0.5)
    assert cold == MAX_RATIO
    assert _solve(0.5, start_hint=round(_grid()[offset_steps], 6)) == cold
