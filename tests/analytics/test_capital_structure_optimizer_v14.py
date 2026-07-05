#!/usr/bin/env python
"""Tests for the capital-structure optimizers (#740).

Two OPT-IN analysis optimizers — the debt-tranche-mix optimizer and the
capex-contingency optimizer — score candidate capital structures through the
``analytics.evaluation_v14`` gateway and return the return-optimal one that
clears the declared covenants.

The fast tests monkeypatch the gateway with analytic KPI surfaces so the optima
are known exactly: they cover objective selection, covenant enforcement (with the
shared floating-point tolerance), the fail-loud infeasible path with a binding
reason, and input validation. Two ``slow`` tests exercise the real committed
lender scenario (the levers actually move KPIs) and PROVE the opt-in byte-identity
guarantee (nothing added is read by ``run_v14_pipeline``).

Context:
    Issue #740 (debt-mix & capex-contingency optimizers). Follow-up #741
    (rich infeasibility diagnostics + optimization audit log).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional

import pytest

import analytics.capital_structure_optimizer_v14 as opt_mod
from analytics.capital_structure_optimizer_v14 import (
    optimize_capex_contingency,
    optimize_debt_mix,
)
from analytics.contracts_v14 import (
    CapitalStructureOptimizationResult,
    CapitalStructurePoint,
    CovenantConstraint,
    DebtTrancheMix,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER_CONFIG = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")

# The committed lender case project IRR — the byte-identity anchor.
LENDER_PROJECT_IRR = 0.014551597740253388

# The lender case base capex (usd_total minus its fixed contingency line):
# 159_600_000 - 2_394_000.
LENDER_BASE_CAPEX = 157_206_000.0

_MIX_LKR_PATH = "Financing_Terms.mix.lkr_max"
_MIX_DFI_PATH = "Financing_Terms.mix.dfi_max"
_CAPEX_TOTAL_PATH = "capex.usd_total"


# ---------------------------------------------------------------------------
# Analytic gateway fakes (fast, deterministic)
# ---------------------------------------------------------------------------


def _make_mix_eval(
    objective_fn: Callable[[float, float], float],
    constraint_fns: Optional[Mapping[str, Callable[[float, float], float]]] = None,
) -> Callable[..., Dict[str, Any]]:
    """Fake gateway mapping the (lkr, dfi) mix override to analytic KPIs."""

    def _fake(
        config_path: str,
        *,
        overrides: Optional[Mapping[str, Any]] = None,
        **_kwargs: Any,
    ) -> Dict[str, Any]:
        ov = overrides or {}
        lkr = float(ov[_MIX_LKR_PATH])
        dfi = float(ov[_MIX_DFI_PATH])
        kpis: Dict[str, Any] = {"equity_irr": objective_fn(lkr, dfi)}
        for key, fn in (constraint_fns or {}).items():
            kpis[key] = fn(lkr, dfi)
        return kpis

    return _fake


def _make_contingency_eval(
    objective_fn: Callable[[float], float],
    constraint_fns: Optional[Mapping[str, Callable[[float], float]]] = None,
    *,
    base_capex: float = LENDER_BASE_CAPEX,
) -> Callable[..., Dict[str, Any]]:
    """Fake gateway mapping the capex override back to the contingency fraction."""

    def _fake(
        config_path: str,
        *,
        overrides: Optional[Mapping[str, Any]] = None,
        **_kwargs: Any,
    ) -> Dict[str, Any]:
        total = float((overrides or {})[_CAPEX_TOTAL_PATH])
        frac = total / base_capex - 1.0
        kpis: Dict[str, Any] = {"equity_irr": objective_fn(frac)}
        for key, fn in (constraint_fns or {}).items():
            kpis[key] = fn(frac)
        return kpis

    return _fake


# ---------------------------------------------------------------------------
# Debt-mix optimizer — objective selection
# ---------------------------------------------------------------------------


def test_debt_mix_selects_analytic_max(monkeypatch: pytest.MonkeyPatch) -> None:
    """Objective peaks at all-DFI: the search must pick the max feasible point."""
    # Increasing in dfi, decreasing in lkr -> peak on the (lkr=0, dfi=high) corner.
    fake = _make_mix_eval(lambda lkr, dfi: dfi - lkr)
    monkeypatch.setattr(opt_mod, "evaluate_with_overrides", fake)

    res = optimize_debt_mix(
        LENDER_CONFIG,
        objective_key="equity_irr",
        direction="max",
        lkr_bounds=(0.0, 0.5),
        dfi_bounds=(0.0, 0.5),
        n_steps=6,
    )
    assert isinstance(res, CapitalStructureOptimizationResult)
    assert res.kind == "debt_mix"
    assert res.feasible
    assert res.best is not None
    assert res.best.mix is not None
    assert res.best.mix.lkr_share == pytest.approx(0.0)
    assert res.best.mix.dfi_share == pytest.approx(0.5)
    # It is genuinely the max over the whole evaluated curve.
    assert res.best.objective == max(p.objective for p in res.curve)


def test_debt_mix_min_direction(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _make_mix_eval(lambda lkr, dfi: dfi - lkr)
    monkeypatch.setattr(opt_mod, "evaluate_with_overrides", fake)

    res = optimize_debt_mix(
        LENDER_CONFIG,
        direction="min",
        lkr_bounds=(0.0, 0.5),
        dfi_bounds=(0.0, 0.5),
        n_steps=6,
    )
    assert res.best is not None
    assert res.best.objective == min(p.objective for p in res.curve)


def test_debt_mix_residual_and_shares_sum_to_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """USD absorbs the residual; the three shares sum to 1 for every candidate."""
    fake = _make_mix_eval(lambda lkr, dfi: dfi - lkr)
    monkeypatch.setattr(opt_mod, "evaluate_with_overrides", fake)

    res = optimize_debt_mix(
        LENDER_CONFIG, lkr_bounds=(0.0, 0.6), dfi_bounds=(0.0, 0.4), n_steps=5
    )
    for point in res.curve:
        assert isinstance(point.mix, DebtTrancheMix)
        total = point.mix.lkr_share + point.mix.dfi_share + point.mix.usd_share
        assert total == pytest.approx(1.0, abs=1e-9)
        assert point.mix.usd_share >= 0.0


def test_debt_mix_skips_over_allocated_geometry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Candidates with lkr + dfi > 1 (negative USD residual) are never scored."""
    calls: list[tuple[float, float]] = []

    def _fake(
        config_path: str,
        *,
        overrides: Optional[Mapping[str, Any]] = None,
        **_kwargs: Any,
    ) -> Dict[str, Any]:
        ov = overrides or {}
        calls.append((float(ov[_MIX_LKR_PATH]), float(ov[_MIX_DFI_PATH])))
        return {"equity_irr": 0.1}

    monkeypatch.setattr(opt_mod, "evaluate_with_overrides", _fake)
    res = optimize_debt_mix(
        LENDER_CONFIG, lkr_bounds=(0.0, 1.0), dfi_bounds=(0.0, 1.0), n_steps=3
    )
    # 3x3 lattice on [0,1]: only (lkr + dfi) <= 1 survive -> 6 of 9 corners.
    assert len(calls) == 6
    assert all(lkr + dfi <= 1.0 + 1e-9 for lkr, dfi in calls)
    assert len(res.curve) == 6


# ---------------------------------------------------------------------------
# Covenant enforcement
# ---------------------------------------------------------------------------


def test_debt_mix_covenant_restricts_best(monkeypatch: pytest.MonkeyPatch) -> None:
    """The unconstrained optimum is barred by a covenant; the search obeys it.

    Objective increases with dfi (peak at dfi=0.5), but the covenant makes only
    dfi <= 0.2 feasible. The best FEASIBLE point sits at the covenant wall.
    """
    fake = _make_mix_eval(
        lambda lkr, dfi: dfi,
        {"llcr": lambda lkr, dfi: 2.0 if dfi <= 0.2 else 0.5},
    )
    monkeypatch.setattr(opt_mod, "evaluate_with_overrides", fake)

    res = optimize_debt_mix(
        LENDER_CONFIG,
        direction="max",
        constraints=[CovenantConstraint("llcr", minimum=1.0)],
        lkr_bounds=(0.0, 0.0),
        dfi_bounds=(0.0, 0.5),
        n_steps=6,
    )
    assert res.feasible
    assert res.best is not None
    assert res.best.mix is not None
    assert res.best.mix.dfi_share <= 0.2 + 1e-9
    assert res.best.feasible
    # The infeasible corners were evaluated and flagged.
    assert any(not p.feasible for p in res.curve)
    assert all(("llcr" in p.binding_constraints) == (not p.feasible) for p in res.curve)


def test_debt_mix_records_all_constraint_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _make_mix_eval(
        lambda lkr, dfi: dfi,
        {"llcr": lambda lkr, dfi: 1.5, "min_dscr_period": lambda lkr, dfi: 1.3},
    )
    monkeypatch.setattr(opt_mod, "evaluate_with_overrides", fake)
    res = optimize_debt_mix(
        LENDER_CONFIG,
        constraints=[
            CovenantConstraint("llcr", minimum=1.0),
            CovenantConstraint("min_dscr_period", minimum=1.3),
        ],
        lkr_bounds=(0.0, 0.4),
        dfi_bounds=(0.0, 0.4),
        n_steps=3,
    )
    for point in res.curve:
        assert set(point.constraints) == {"llcr", "min_dscr_period"}


def test_debt_mix_max_ceiling_covenant(monkeypatch: pytest.MonkeyPatch) -> None:
    """A ``maximum`` covenant (e.g. balloon ceiling) bounds feasibility above."""
    fake = _make_mix_eval(
        lambda lkr, dfi: dfi,
        {"balloon_pct": lambda lkr, dfi: 0.05 if dfi <= 0.3 else 0.20},
    )
    monkeypatch.setattr(opt_mod, "evaluate_with_overrides", fake)
    res = optimize_debt_mix(
        LENDER_CONFIG,
        constraints=[CovenantConstraint("balloon_pct", maximum=0.10)],
        lkr_bounds=(0.0, 0.0),
        dfi_bounds=(0.0, 0.5),
        n_steps=6,
    )
    assert res.best is not None
    assert res.best.mix is not None
    assert res.best.mix.dfi_share <= 0.3 + 1e-9


def test_covenant_bound_slack_keeps_grazing_point_feasible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A DSCR pinned an epsilon below the covenant stays feasible (shared tol)."""
    fake = _make_mix_eval(
        lambda lkr, dfi: dfi,
        {"min_dscr_period": lambda lkr, dfi: 1.30 - 1e-12},
    )
    monkeypatch.setattr(opt_mod, "evaluate_with_overrides", fake)
    res = optimize_debt_mix(
        LENDER_CONFIG,
        constraints=[CovenantConstraint("min_dscr_period", minimum=1.30)],
        lkr_bounds=(0.0, 0.0),
        dfi_bounds=(0.0, 0.4),
        n_steps=4,
    )
    assert res.feasible
    assert all(p.feasible for p in res.curve)


# ---------------------------------------------------------------------------
# Fail-loud infeasibility
# ---------------------------------------------------------------------------


def test_debt_mix_infeasible_is_structured_not_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No candidate meets the covenant -> feasible=False + a binding reason."""
    fake = _make_mix_eval(
        lambda lkr, dfi: dfi,
        {"llcr": lambda lkr, dfi: 0.5},  # always below any sane floor
    )
    monkeypatch.setattr(opt_mod, "evaluate_with_overrides", fake)
    res = optimize_debt_mix(
        LENDER_CONFIG,
        constraints=[CovenantConstraint("llcr", minimum=1.0)],
        lkr_bounds=(0.0, 0.4),
        dfi_bounds=(0.0, 0.4),
        n_steps=3,
    )
    assert res.feasible is False
    assert res.best is None
    assert res.curve  # the search still ran and recorded every candidate
    assert res.infeasible_reason is not None
    assert "llcr" in res.infeasible_reason
    assert all(not p.feasible for p in res.curve)


def test_missing_objective_key_fails_loud(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _make_mix_eval(lambda lkr, dfi: dfi)  # no 'project_irr' key
    monkeypatch.setattr(opt_mod, "evaluate_with_overrides", fake)
    with pytest.raises(KeyError, match="objective_key"):
        optimize_debt_mix(
            LENDER_CONFIG,
            objective_key="project_irr",
            lkr_bounds=(0.0, 0.4),
            dfi_bounds=(0.0, 0.4),
            n_steps=2,
        )


def test_missing_constraint_key_fails_loud(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _make_mix_eval(lambda lkr, dfi: dfi)  # no 'llcr' key
    monkeypatch.setattr(opt_mod, "evaluate_with_overrides", fake)
    with pytest.raises(KeyError, match="not found in evaluated KPIs"):
        optimize_debt_mix(
            LENDER_CONFIG,
            constraints=[CovenantConstraint("llcr", minimum=1.0)],
            lkr_bounds=(0.0, 0.4),
            dfi_bounds=(0.0, 0.4),
            n_steps=2,
        )


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def test_debt_mix_invalid_direction_raises() -> None:
    with pytest.raises(ValueError, match="direction must be"):
        optimize_debt_mix(LENDER_CONFIG, direction="sideways")


def test_debt_mix_too_few_steps_raises() -> None:
    with pytest.raises(ValueError, match="n_steps must be"):
        optimize_debt_mix(LENDER_CONFIG, n_steps=1)


def test_debt_mix_bad_bounds_raise() -> None:
    with pytest.raises(ValueError, match="lkr_bounds"):
        optimize_debt_mix(LENDER_CONFIG, lkr_bounds=(0.6, 0.4))
    with pytest.raises(ValueError, match="dfi_bounds"):
        optimize_debt_mix(LENDER_CONFIG, dfi_bounds=(-0.1, 0.5))


def test_constraint_without_bound_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _make_mix_eval(lambda lkr, dfi: dfi, {"llcr": lambda lkr, dfi: 1.5})
    monkeypatch.setattr(opt_mod, "evaluate_with_overrides", fake)
    with pytest.raises(ValueError, match="neither minimum nor maximum"):
        optimize_debt_mix(
            LENDER_CONFIG,
            constraints=[CovenantConstraint("llcr")],
            lkr_bounds=(0.0, 0.4),
            dfi_bounds=(0.0, 0.4),
            n_steps=2,
        )


def test_constraint_inverted_interval_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _make_mix_eval(lambda lkr, dfi: dfi, {"llcr": lambda lkr, dfi: 1.5})
    monkeypatch.setattr(opt_mod, "evaluate_with_overrides", fake)
    with pytest.raises(ValueError, match="> maximum"):
        optimize_debt_mix(
            LENDER_CONFIG,
            constraints=[CovenantConstraint("llcr", minimum=2.0, maximum=1.0)],
            lkr_bounds=(0.0, 0.4),
            dfi_bounds=(0.0, 0.4),
            n_steps=2,
        )


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_debt_mix_is_deterministic(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _make_mix_eval(lambda lkr, dfi: dfi - 0.5 * lkr)
    monkeypatch.setattr(opt_mod, "evaluate_with_overrides", fake)
    a = optimize_debt_mix(LENDER_CONFIG, lkr_bounds=(0.0, 0.5), dfi_bounds=(0.0, 0.5))
    b = optimize_debt_mix(LENDER_CONFIG, lkr_bounds=(0.0, 0.5), dfi_bounds=(0.0, 0.5))
    assert a.curve == b.curve
    assert a.best == b.best


# ---------------------------------------------------------------------------
# Capex-contingency optimizer
# ---------------------------------------------------------------------------


def test_contingency_max_picks_lowest_safe_fraction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Return decreases with contingency; max return -> the smallest fraction."""
    fake = _make_contingency_eval(lambda f: -f)  # strictly decreasing in f
    monkeypatch.setattr(opt_mod, "evaluate_with_overrides", fake)
    res = optimize_capex_contingency(
        LENDER_CONFIG,
        base_capex_usd=LENDER_BASE_CAPEX,
        direction="max",
        contingency_bounds=(0.0, 0.20),
        n_steps=5,
    )
    assert res.kind == "capex_contingency"
    assert res.best is not None
    assert res.best.value[0] == pytest.approx(0.0, abs=1e-9)
    assert res.best.mix is None


def test_contingency_covenant_forces_higher_fraction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A safety covenant met only at higher contingency drives the pick up.

    Return decreases with f (favours f=0), but the covenant is satisfied only for
    f >= 0.10, so the best FEASIBLE fraction is exactly 0.10 (the wall).
    """
    fake = _make_contingency_eval(
        lambda f: -f,
        {"llcr": lambda f: 2.0 if f >= 0.10 - 1e-12 else 0.5},
    )
    monkeypatch.setattr(opt_mod, "evaluate_with_overrides", fake)
    res = optimize_capex_contingency(
        LENDER_CONFIG,
        base_capex_usd=LENDER_BASE_CAPEX,
        direction="max",
        constraints=[CovenantConstraint("llcr", minimum=1.0)],
        contingency_bounds=(0.0, 0.20),
        n_steps=11,
    )
    assert res.feasible
    assert res.best is not None
    assert res.best.value[0] == pytest.approx(0.10, abs=1e-9)


def test_contingency_infeasible_fails_loud(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _make_contingency_eval(lambda f: -f, {"llcr": lambda f: 0.5})
    monkeypatch.setattr(opt_mod, "evaluate_with_overrides", fake)
    res = optimize_capex_contingency(
        LENDER_CONFIG,
        base_capex_usd=LENDER_BASE_CAPEX,
        constraints=[CovenantConstraint("llcr", minimum=1.0)],
        contingency_bounds=(0.0, 0.20),
        n_steps=4,
    )
    assert res.feasible is False
    assert res.best is None
    assert res.infeasible_reason is not None
    assert "llcr" in res.infeasible_reason


def test_contingency_bad_base_capex_raises() -> None:
    with pytest.raises(ValueError, match="base_capex_usd must be"):
        optimize_capex_contingency(LENDER_CONFIG, base_capex_usd=0.0)
    with pytest.raises(ValueError, match="base_capex_usd must be"):
        optimize_capex_contingency(LENDER_CONFIG, base_capex_usd=float("inf"))


def test_contingency_bad_bounds_raise() -> None:
    with pytest.raises(ValueError, match="contingency_bounds"):
        optimize_capex_contingency(
            LENDER_CONFIG, base_capex_usd=1.0, contingency_bounds=(0.2, 0.1)
        )
    with pytest.raises(ValueError, match="contingency_bounds"):
        optimize_capex_contingency(
            LENDER_CONFIG, base_capex_usd=1.0, contingency_bounds=(-0.1, 0.2)
        )


# ---------------------------------------------------------------------------
# Contract shapes
# ---------------------------------------------------------------------------


def test_result_is_json_serializable(monkeypatch: pytest.MonkeyPatch) -> None:
    """The result + its points serialize cleanly (CLI-03 / dataclasses.asdict)."""
    import json
    from dataclasses import asdict

    fake = _make_mix_eval(lambda lkr, dfi: dfi, {"llcr": lambda lkr, dfi: 1.5})
    monkeypatch.setattr(opt_mod, "evaluate_with_overrides", fake)
    res = optimize_debt_mix(
        LENDER_CONFIG,
        constraints=[CovenantConstraint("llcr", minimum=1.0)],
        lkr_bounds=(0.0, 0.4),
        dfi_bounds=(0.0, 0.4),
        n_steps=3,
    )
    payload = json.loads(json.dumps(asdict(res), default=list))
    assert payload["kind"] == "debt_mix"
    assert payload["best"] is not None
    assert isinstance(res.curve[0], CapitalStructurePoint)


# ---------------------------------------------------------------------------
# Real-scenario integration + opt-in byte-identity (slow)
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_real_debt_mix_favours_cheap_dfi() -> None:
    """On the committed lender case, max equity IRR shifts weight to cheap DFI.

    DFI debt is the cheapest tranche (6.5% vs LKR 13.39%), so — absent a binding
    covenant — the equity-IRR-maximizing mix loads DFI and drops LKR. This proves
    the real levers move the pipeline the intended way (no monkeypatch).
    """
    res = optimize_debt_mix(
        LENDER_CONFIG,
        objective_key="equity_irr",
        direction="max",
        lkr_bounds=(0.0, 0.6),
        dfi_bounds=(0.0, 0.4),
        n_steps=4,
    )
    assert res.feasible
    assert res.best is not None
    assert res.best.mix is not None
    # Cheap DFI wins; LKR is minimized.
    assert res.best.mix.dfi_share == pytest.approx(0.4, abs=1e-9)
    assert res.best.mix.lkr_share == pytest.approx(0.0, abs=1e-9)
    # The full curve was evaluated (4x4 lattice, all lkr+dfi <= 1).
    assert len(res.curve) == 16


@pytest.mark.slow
def test_real_contingency_monotonic_and_opt_in_byte_identical() -> None:
    """Contingency lowers equity IRR monotonically AND the pipeline is untouched.

    (1) Running the optimizer does not change the committed scenario: a plain
        pipeline eval before and after returns the exact committed project IRR
        (0.014551597740253388) — nothing the optimizers add is read by
        run_v14_pipeline on a committed scenario (opt-in / byte-identical).
    (2) The f=0 candidate reproduces the committed capex economics; higher
        contingency strictly lowers equity IRR (safer-but-costlier).
    """
    from analytics.evaluation_v14 import evaluate_with_overrides

    before = evaluate_with_overrides(config_path=LENDER_CONFIG, overrides={})
    assert before["project_irr"] == LENDER_PROJECT_IRR

    res = optimize_capex_contingency(
        LENDER_CONFIG,
        base_capex_usd=LENDER_BASE_CAPEX,
        objective_key="equity_irr",
        direction="max",
        contingency_bounds=(0.0, 0.15),
        n_steps=4,
    )
    assert res.feasible
    assert res.best is not None
    # Return maximized at the lowest contingency.
    assert res.best.value[0] == pytest.approx(0.0, abs=1e-9)
    # Strictly decreasing equity IRR across the (ascending) contingency grid.
    eqs = [p.objective for p in res.curve]
    assert eqs == sorted(eqs, reverse=True)
    assert eqs[0] > eqs[-1]

    # The committed pipeline is byte-identical after the optimizer ran.
    after = evaluate_with_overrides(config_path=LENDER_CONFIG, overrides={})
    assert after["project_irr"] == LENDER_PROJECT_IRR
