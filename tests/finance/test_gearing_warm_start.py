"""The warm-started gearing solve returns exactly what the cold scan returns.

#1451 sizes debt as a fixed point over levered-tax CFADS, so a pipeline run solves the
gearing several times on CFADS that barely moves between passes. Since #1514's follow-up,
each pass after the first starts ``_solve_gearing_for_dscr``'s scan at the previous
pass's answer instead of at ``max_ratio`` and walks to the boundary. That is exact only
where min DSCR is non-increasing in gearing, so these tests re-run every warm-started
solve cold and require the same float, on the committed lender case under the debt
options that change the solve, and pin the walk's branches on a small synthetic case.
"""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path
from typing import Any, Callable

import pytest

import finance.debt
from analytics.evaluation_v14 import evaluate_with_overrides
from finance import debt_v14

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER_CONFIG = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")


def _wrap_everywhere(
    monkeypatch: pytest.MonkeyPatch,
    real: Callable[..., Any],
    wrapper: Callable[..., Any],
) -> list[str]:
    """Replace ``real`` in every ``finance.debt`` module that binds it by name.

    The engine's functions read their collaborators from their own module's globals,
    so a patch on the ``finance.debt_v14`` façade would be dead
    (``tests/lint/test_debt_package_boundary.py`` rule 2).
    """
    patched = []
    for info in pkgutil.iter_modules(finance.debt.__path__):
        module = importlib.import_module(f"finance.debt.{info.name}")
        if getattr(module, real.__name__, None) is real:
            monkeypatch.setattr(module, real.__name__, wrapper)
            patched.append(module.__name__)
    return patched


@pytest.fixture
def solves(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Re-run every warm-started solve cold, and count the engine calls."""
    record: dict[str, Any] = {"hinted": [], "cold": 0, "layer_calls": 0}
    real_solve = debt_v14._solve_gearing_for_dscr
    real_layer = debt_v14.apply_debt_layer

    def counting_layer(**kwargs: Any) -> Any:
        record["layer_calls"] += 1
        return real_layer(**kwargs)

    def checking_solve(config, annual_rows, target_dscr, max_ratio, **kw):  # type: ignore[no-untyped-def]
        solved = real_solve(config, annual_rows, target_dscr, max_ratio, **kw)
        if kw.get("start_hint") is None:
            record["cold"] += 1
            return solved
        cold_kw = {k: v for k, v in kw.items() if k != "start_hint"}
        calls_before = record["layer_calls"]
        cold = real_solve(config, annual_rows, target_dscr, max_ratio, **cold_kw)
        record["layer_calls"] = calls_before  # the oracle's calls are not the run's
        record["hinted"].append((kw["start_hint"], solved, cold))
        return solved

    for real, wrapper in ((real_layer, counting_layer), (real_solve, checking_solve)):
        # A seam no module binds would leave the counters silently empty.
        assert _wrap_everywhere(monkeypatch, real, wrapper), real.__name__
    return record


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({}, id="lender-case"),
        pytest.param({"Financing_Terms.bind_downside": True}, id="p90-bind"),
        pytest.param({"Financing_Terms.balloon_treatment": "amortize"}, id="amortize"),
    ],
)
def test_every_warm_started_solve_equals_the_cold_scan(
    solves: dict[str, Any], overrides: dict[str, Any]
) -> None:
    evaluate_with_overrides(LENDER_CONFIG, overrides=overrides, return_full_result=True)

    # The first pass of each case is cold; every later pass is warm-started.
    assert solves["cold"] >= 1
    assert len(solves["hinted"]) >= 5, "the fixed point no longer reaches a warm start"
    mismatches = [h for h in solves["hinted"] if h[1] != h[2]]
    assert mismatches == [], f"(hint, warm, cold) differ: {mismatches}"


def test_the_warm_start_is_where_the_time_goes(solves: dict[str, Any]) -> None:
    """The lender case's 7 passes cost about 920 engine calls cold; warm, about 170."""
    evaluate_with_overrides(LENDER_CONFIG, return_full_result=True)
    # The lower bound proves the counter sits on the engine's real seam: a dead patch
    # would count nothing and pass the upper bound.
    assert 50 < solves["layer_calls"] < 300, solves["layer_calls"]


# --------------------------------------------------------------------------- #
# The walk itself, on a synthetic schedule whose cold answer is interior.
# --------------------------------------------------------------------------- #
def _config() -> dict[str, Any]:
    return {
        "capex": {"usd_total": 100.0},
        "debt_ratio": 0.7,
        "tenor_years": 8,
        "construction_periods": 1,
        "amortization_style": "sculpted",
        "target_dscr": 1.30,
        "mix": {"usd_commercial_min": 1.0},
        "rates": {"usd_nominal": 0.08},
    }


def _rows() -> list[dict[str, Any]]:
    return [{"year": i + 1, "cfads_usd": 8.0} for i in range(8)]


def _cold() -> float:
    return debt_v14._solve_gearing_for_dscr(
        _config(), _rows(), target_dscr=1.30, max_ratio=0.7
    )


def test_the_synthetic_answer_is_interior() -> None:
    cold = _cold()
    assert 0.1 < cold < 0.6, cold


@pytest.mark.parametrize(
    "offset_steps",
    [
        pytest.param(0, id="at"),
        pytest.param(-8, id="above"),
        pytest.param(8, id="below"),
    ],
)
def test_the_walk_lands_on_the_cold_answer_from_either_side(offset_steps: int) -> None:
    """A hint above the answer walks down; one below walks up; one on it stays."""
    cold = _cold()
    # A grid point offset_steps away from the answer, built the way the scan builds it.
    grid: list[float] = []
    ratio = 0.7
    while ratio > 0.0:
        grid.append(ratio)
        ratio -= 0.0025
    at = next(i for i, r in enumerate(grid) if round(r, 6) == cold)
    hint = round(grid[at + offset_steps], 6)
    warm = debt_v14._solve_gearing_for_dscr(
        _config(), _rows(), target_dscr=1.30, max_ratio=0.7, start_hint=hint
    )
    assert warm == cold


def test_a_hint_off_the_grid_falls_back_to_the_cold_scan() -> None:
    warm = debt_v14._solve_gearing_for_dscr(
        _config(), _rows(), target_dscr=1.30, max_ratio=0.7, start_hint=0.123456789
    )
    assert warm == _cold()


def test_an_unmet_target_still_falls_back_to_the_floor_when_warm() -> None:
    rows = [{"year": i + 1, "cfads_usd": 0.001} for i in range(8)]
    kwargs: dict[str, Any] = {"target_dscr": 5.0, "max_ratio": 0.05, "step": 0.0025}
    cold = debt_v14._solve_gearing_for_dscr(_config(), rows, **kwargs)
    warm = debt_v14._solve_gearing_for_dscr(_config(), rows, start_hint=0.025, **kwargs)
    assert cold == warm == pytest.approx(0.0025)


def test_a_hint_is_used_only_on_the_same_terms() -> None:
    hints = {"P50": (0.7, 1.30, 0.4)}
    assert debt_v14._gearing_hint(hints, "P50", 0.7, 1.30) == 0.4
    assert debt_v14._gearing_hint(hints, "P50", 0.75, 1.30) is None
    assert debt_v14._gearing_hint(hints, "P50", 0.7, 1.25) is None
    assert debt_v14._gearing_hint(hints, "P90", 0.7, 1.30) is None
    assert debt_v14._gearing_hint(None, "P50", 0.7, 1.30) is None
