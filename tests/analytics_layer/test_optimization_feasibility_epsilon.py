"""Regression: optimizer feasibility must tolerate the DSCR-sculpt plateau.

`optimize_parameter` compared the achieved constraint to the bound with a naked
`<`/`>`. Because the dual-DSCR debt sculpt pins the achieved DSCR *exactly* at
the covenant target, the constraint lands at target +/- ~1e-15 rounding noise,
so feasibility flipped on that noise — on the canonical deleverage sweep, 6 of 9
covenant-compliant points were marked infeasible at random. A floating-point
tolerance makes a point feasible when it satisfies the bound within ~1e-9.
"""

from __future__ import annotations

from pathlib import Path

from analytics.optimization_v14 import _bound_slack, optimize_parameter

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")


def test_bound_slack_is_relative_and_nonzero() -> None:
    assert _bound_slack(1.30) >= 1e-9
    assert _bound_slack(45_000_000.0) >= 45_000_000.0 * 1e-9
    assert _bound_slack(0.0) == 1e-9


def test_deleverage_sweep_has_no_plateau_flipflop() -> None:
    """Every covenant-compliant point on the sweep must be marked feasible."""
    res = optimize_parameter(
        LENDER,
        param_path="Financing_Terms.debt_ratio",
        objective_key="equity_irr",
        direction="max",
        lower=0.30,
        upper=0.70,
        n_steps=9,
        constraint_key="min_dscr",
        constraint_min=1.30,
    )

    # Points at/above the covenant (within a generous 1e-6) must be feasible —
    # pre-fix, several plateau points at min_dscr≈1.30 were flipped to infeasible.
    flipped = [
        p
        for p in res.curve
        if p.constraint is not None and p.constraint >= 1.30 - 1e-6 and not p.feasible
    ]
    assert not flipped, (
        "covenant-compliant points marked infeasible (FP-plateau flip-flop): "
        + ", ".join(f"ratio={p.value:.3f} dscr={p.constraint:.12f}" for p in flipped)
    )

    # The optimum is well-defined and is the equity-IRR-maximizing feasible point.
    assert res.best is not None
    assert res.best.feasible
    assert res.best.objective == max(p.objective for p in res.curve if p.feasible)
