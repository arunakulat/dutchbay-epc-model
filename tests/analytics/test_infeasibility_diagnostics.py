#!/usr/bin/env python
"""Tests for infeasibility diagnostics + optimization audit log (#741).

When a debt-sizing / capital-structure optimizer search finds no feasible
candidate, the result carries a structured :class:`InfeasibilityDiagnostics`
(which covenant bound was violated, the required vs achieved value, how many
candidates it bound) and an :class:`OptimizationAuditLog` — instead of a bare
``feasible=False``. These are populated ONLY on the failure path.

KPI-NEUTRALITY (the load-bearing guarantee): a FEASIBLE solve leaves
``diagnostics`` and ``audit_log`` at ``None`` and the rest of the result
unchanged, so a successful solve is byte-identical to before #741. The
``*_feasible_solve_carries_no_diagnostics`` tests assert exactly that.

Context:
    Issue #741 (infeasibility diagnostics + optimization audit log); parent
    #622 §5a; follow-up to #740 (debt-mix / capex-contingency optimizers).
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional

import pytest

import analytics.capital_structure_optimizer_v14 as cs_mod
import analytics.optimization_v14 as opt_mod
from analytics.capital_structure_optimizer_v14 import (
    optimize_capex_contingency,
    optimize_debt_mix,
)
from analytics.contracts_v14 import CovenantConstraint
from analytics.infeasibility_diagnostics import (
    ConstraintViolation,
    InfeasibilityDiagnostics,
    OptimizationAuditLog,
    build_capital_structure_diagnostics,
    build_parameter_diagnostics,
)
from analytics.optimization_v14 import OptimizationPoint, optimize_parameter

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER_CONFIG = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")

_MIX_LKR_PATH = "Financing_Terms.mix.lkr_max"
_MIX_DFI_PATH = "Financing_Terms.mix.dfi_max"
_CAPEX_TOTAL_PATH = "capex.usd_total"
LENDER_BASE_CAPEX = 157_206_000.0


# ---------------------------------------------------------------------------
# Gateway fakes (mirror the #740 test harness)
# ---------------------------------------------------------------------------


def _make_mix_eval(
    objective_fn: Callable[[float, float], float],
    constraint_fns: Optional[Mapping[str, Callable[[float, float], float]]] = None,
) -> Callable[..., Dict[str, Any]]:
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


def _make_param_eval(
    objective_fn: Callable[[float], float],
    constraint_fn: Optional[Callable[[float], float]] = None,
    *,
    param_path: str = "Financing_Terms.debt_ratio",
) -> Callable[..., Dict[str, Any]]:
    def _fake(
        config_path: str,
        *,
        overrides: Optional[Mapping[str, Any]] = None,
        **_kwargs: Any,
    ) -> Dict[str, Any]:
        x = float((overrides or {})[param_path])
        kpis: Dict[str, Any] = {"equity_irr": objective_fn(x)}
        if constraint_fn is not None:
            kpis["min_dscr"] = constraint_fn(x)
        return kpis

    return _fake


# ---------------------------------------------------------------------------
# Builder unit tests (pure, no gateway)
# ---------------------------------------------------------------------------


def test_capital_builder_names_binding_floor_and_shortfall() -> None:
    """A floor that no candidate clears -> a min-side violation with a shortfall."""
    from analytics.contracts_v14 import CapitalStructurePoint

    # llcr read-back is always 0.5; the floor is 1.0 -> best achieved 0.5, short 0.5.
    curve = [
        CapitalStructurePoint(
            value=(float(i), 0.0),
            mix=None,
            objective=float(i),
            constraints={"llcr": 0.5},
            feasible=False,
            binding_constraints=("llcr",),
        )
        for i in range(3)
    ]
    diag = build_capital_structure_diagnostics(
        curve, [CovenantConstraint("llcr", minimum=1.0)]
    )
    assert isinstance(diag, InfeasibilityDiagnostics)
    assert diag.n_candidates == 3
    assert diag.n_feasible == 0
    assert len(diag.violations) == 1
    v = diag.violations[0]
    assert isinstance(v, ConstraintViolation)
    assert v.key == "llcr"
    assert v.bound_kind == "minimum"
    assert v.required == pytest.approx(1.0)
    assert v.achieved == pytest.approx(0.5)
    assert v.shortfall == pytest.approx(0.5)
    assert v.candidates_violating == 3
    assert v.candidates_total == 3
    assert v.never_satisfied is True
    assert "llcr" in diag.binding_summary
    assert diag.objective_range == (0.0, 2.0)


def test_capital_builder_orders_violations_worst_first() -> None:
    """Two binding covenants: the larger shortfall is reported first."""
    from analytics.contracts_v14 import CapitalStructurePoint

    curve = [
        CapitalStructurePoint(
            value=(0.0, 0.0),
            mix=None,
            objective=0.1,
            # llcr short by 0.5 (0.5 vs 1.0); dscr short by 0.3 (1.0 vs 1.3)
            constraints={"llcr": 0.5, "min_dscr_period": 1.0},
            feasible=False,
            binding_constraints=("llcr", "min_dscr_period"),
        )
    ]
    diag = build_capital_structure_diagnostics(
        curve,
        [
            CovenantConstraint("min_dscr_period", minimum=1.3),
            CovenantConstraint("llcr", minimum=1.0),
        ],
    )
    assert [v.key for v in diag.violations] == ["llcr", "min_dscr_period"]
    assert diag.violations[0].shortfall > diag.violations[1].shortfall


def test_capital_builder_maximum_bound_violation() -> None:
    """A ceiling (e.g. balloon_pct) that is always exceeded -> a max-side violation."""
    from analytics.contracts_v14 import CapitalStructurePoint

    curve = [
        CapitalStructurePoint(
            value=(0.0, 0.0),
            mix=None,
            objective=0.1,
            constraints={"balloon_pct": 0.20},
            feasible=False,
            binding_constraints=("balloon_pct",),
        )
    ]
    diag = build_capital_structure_diagnostics(
        curve, [CovenantConstraint("balloon_pct", maximum=0.10)]
    )
    assert len(diag.violations) == 1
    v = diag.violations[0]
    assert v.bound_kind == "maximum"
    assert v.required == pytest.approx(0.10)
    assert v.achieved == pytest.approx(0.20)
    assert v.shortfall == pytest.approx(0.10)


def test_param_builder_min_side() -> None:
    curve = [
        OptimizationPoint(
            value=float(i), objective=float(i), constraint=1.0, feasible=False
        )
        for i in range(4)
    ]
    diag = build_parameter_diagnostics(
        curve, constraint_key="min_dscr", constraint_min=1.3, constraint_max=None
    )
    assert diag.n_candidates == 4
    assert diag.n_feasible == 0
    assert len(diag.violations) == 1
    v = diag.violations[0]
    assert v.key == "min_dscr"
    assert v.bound_kind == "minimum"
    assert v.achieved == pytest.approx(1.0)
    assert v.shortfall == pytest.approx(0.3)


# ---------------------------------------------------------------------------
# Debt-mix optimizer — failure path carries diagnostics
# ---------------------------------------------------------------------------


def test_debt_mix_infeasible_carries_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _make_mix_eval(lambda lkr, dfi: dfi, {"llcr": lambda lkr, dfi: 0.5})
    monkeypatch.setattr(cs_mod, "evaluate_with_overrides", fake)
    res = optimize_debt_mix(
        LENDER_CONFIG,
        constraints=[CovenantConstraint("llcr", minimum=1.0)],
        lkr_bounds=(0.0, 0.4),
        dfi_bounds=(0.0, 0.4),
        n_steps=3,
    )
    assert res.feasible is False
    assert res.best is None
    # #740 minimal surface still present.
    assert res.infeasible_reason is not None and "llcr" in res.infeasible_reason
    # #741 structured surface populated.
    assert isinstance(res.diagnostics, InfeasibilityDiagnostics)
    assert res.diagnostics.n_feasible == 0
    assert res.diagnostics.n_candidates == len(res.curve)
    assert [v.key for v in res.diagnostics.violations] == ["llcr"]
    assert res.diagnostics.violations[0].bound_kind == "minimum"
    assert res.diagnostics.violations[0].required == pytest.approx(1.0)
    assert res.diagnostics.violations[0].achieved == pytest.approx(0.5)
    assert res.diagnostics.violations[0].never_satisfied is True
    # Audit log.
    assert isinstance(res.audit_log, OptimizationAuditLog)
    assert res.audit_log.method == "debt_mix"
    assert res.audit_log.final_status == "infeasible"
    assert res.audit_log.evaluations == len(res.curve)
    assert res.audit_log.binding_constraints == ("llcr",)
    assert res.audit_log.best_objective is None


def test_debt_mix_feasible_solve_carries_no_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """KPI-NEUTRAL: a feasible solve leaves diagnostics/audit_log at None."""
    fake = _make_mix_eval(lambda lkr, dfi: dfi - lkr)
    monkeypatch.setattr(cs_mod, "evaluate_with_overrides", fake)
    res = optimize_debt_mix(
        LENDER_CONFIG,
        lkr_bounds=(0.0, 0.5),
        dfi_bounds=(0.0, 0.5),
        n_steps=6,
    )
    assert res.feasible is True
    assert res.best is not None
    assert res.infeasible_reason is None
    assert res.diagnostics is None
    assert res.audit_log is None


# ---------------------------------------------------------------------------
# Capex-contingency optimizer — failure path carries diagnostics
# ---------------------------------------------------------------------------


def test_contingency_infeasible_carries_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _make_contingency_eval(lambda f: -f, {"llcr": lambda f: 0.5})
    monkeypatch.setattr(cs_mod, "evaluate_with_overrides", fake)
    res = optimize_capex_contingency(
        LENDER_CONFIG,
        base_capex_usd=LENDER_BASE_CAPEX,
        constraints=[CovenantConstraint("llcr", minimum=1.0)],
        contingency_bounds=(0.0, 0.20),
        n_steps=4,
    )
    assert res.feasible is False
    assert isinstance(res.diagnostics, InfeasibilityDiagnostics)
    assert [v.key for v in res.diagnostics.violations] == ["llcr"]
    assert isinstance(res.audit_log, OptimizationAuditLog)
    assert res.audit_log.method == "capex_contingency"


def test_contingency_feasible_solve_carries_no_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """KPI-NEUTRAL: the feasible contingency solve carries no diagnostics."""
    fake = _make_contingency_eval(lambda f: -f)
    monkeypatch.setattr(cs_mod, "evaluate_with_overrides", fake)
    res = optimize_capex_contingency(
        LENDER_CONFIG,
        base_capex_usd=LENDER_BASE_CAPEX,
        contingency_bounds=(0.0, 0.20),
        n_steps=5,
    )
    assert res.feasible is True
    assert res.best is not None
    assert res.diagnostics is None
    assert res.audit_log is None


# ---------------------------------------------------------------------------
# Single-parameter optimizer (grid + bounded) — failure path
# ---------------------------------------------------------------------------


def test_grid_infeasible_carries_diagnostics(monkeypatch: pytest.MonkeyPatch) -> None:
    # Constraint min_dscr is always 1.0; floor 1.3 is unreachable.
    fake = _make_param_eval(lambda x: x, lambda x: 1.0)
    monkeypatch.setattr(opt_mod, "evaluate_with_overrides", fake)
    res = optimize_parameter(
        LENDER_CONFIG,
        param_path="Financing_Terms.debt_ratio",
        objective_key="equity_irr",
        lower=0.45,
        upper=0.70,
        n_steps=5,
        constraint_key="min_dscr",
        constraint_min=1.3,
    )
    assert res.best is None
    assert isinstance(res.diagnostics, InfeasibilityDiagnostics)
    assert res.diagnostics.n_candidates == 5
    assert [v.key for v in res.diagnostics.violations] == ["min_dscr"]
    assert res.diagnostics.violations[0].achieved == pytest.approx(1.0)
    assert res.diagnostics.violations[0].shortfall == pytest.approx(0.3)
    assert isinstance(res.audit_log, OptimizationAuditLog)
    assert res.audit_log.method == "grid"
    assert res.audit_log.evaluations == 5
    assert res.audit_log.final_status == "infeasible"


def test_grid_feasible_solve_carries_no_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """KPI-NEUTRAL: a feasible grid solve leaves diagnostics/audit_log at None."""
    fake = _make_param_eval(lambda x: x, lambda x: 1.5)  # always clears 1.3
    monkeypatch.setattr(opt_mod, "evaluate_with_overrides", fake)
    res = optimize_parameter(
        LENDER_CONFIG,
        param_path="Financing_Terms.debt_ratio",
        objective_key="equity_irr",
        lower=0.45,
        upper=0.70,
        n_steps=5,
        constraint_key="min_dscr",
        constraint_min=1.3,
    )
    assert res.best is not None
    assert res.diagnostics is None
    assert res.audit_log is None


def test_bounded_infeasible_carries_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _make_param_eval(lambda x: x, lambda x: 1.0)  # floor 1.3 unreachable
    monkeypatch.setattr(opt_mod, "evaluate_with_overrides", fake)
    res = optimize_parameter(
        LENDER_CONFIG,
        param_path="Financing_Terms.debt_ratio",
        objective_key="equity_irr",
        lower=0.45,
        upper=0.70,
        method="bounded",
        constraint_key="min_dscr",
        constraint_min=1.3,
    )
    assert res.best is None
    assert isinstance(res.diagnostics, InfeasibilityDiagnostics)
    assert [v.key for v in res.diagnostics.violations] == ["min_dscr"]
    assert isinstance(res.audit_log, OptimizationAuditLog)
    assert res.audit_log.method == "bounded"
    assert res.audit_log.iterations >= 1


def test_bounded_feasible_solve_carries_no_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _make_param_eval(lambda x: -((x - 0.55) ** 2), lambda x: 1.5)
    monkeypatch.setattr(opt_mod, "evaluate_with_overrides", fake)
    res = optimize_parameter(
        LENDER_CONFIG,
        param_path="Financing_Terms.debt_ratio",
        objective_key="equity_irr",
        lower=0.45,
        upper=0.70,
        method="bounded",
        constraint_key="min_dscr",
        constraint_min=1.3,
    )
    assert res.best is not None
    assert res.diagnostics is None
    assert res.audit_log is None


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def test_infeasible_capital_result_json_serializable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The infeasible result + its diagnostics serialize (CLI asdict path)."""
    fake = _make_mix_eval(lambda lkr, dfi: dfi, {"llcr": lambda lkr, dfi: 0.5})
    monkeypatch.setattr(cs_mod, "evaluate_with_overrides", fake)
    res = optimize_debt_mix(
        LENDER_CONFIG,
        constraints=[CovenantConstraint("llcr", minimum=1.0)],
        lkr_bounds=(0.0, 0.4),
        dfi_bounds=(0.0, 0.4),
        n_steps=3,
    )
    payload = json.loads(json.dumps(asdict(res), default=list))
    assert payload["feasible"] is False
    assert payload["diagnostics"] is not None
    assert payload["diagnostics"]["violations"][0]["key"] == "llcr"
    assert payload["audit_log"]["final_status"] == "infeasible"
