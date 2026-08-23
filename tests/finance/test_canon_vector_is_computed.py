"""Guard that the canonical lender KPI vector is *computed*, not *returned*.

``tests/finance/test_multitech_generation.py::test_canonical_lendercase_economics_unchanged``
pins the eight canonical lender KPIs to full-precision literals held in
:mod:`tests._canon`. A pinned-constant oracle answers "did the number change?" but not
"is the number still being derived?" — an engine short-circuited to emit the pinned
values would satisfy it exactly.

In practice the lender scenario is driven through ``evaluate_with_overrides`` by many
other tests, so a short-circuited path would break several of them. That defence is
real but *emergent*: it exists because those tests happen to use the lender case for
other purposes, nothing names it, and a coverage-driven consolidation could remove the
property without anyone noticing it was load-bearing.

This module states the property directly. Perturb genuine economic drivers through the
canonical gateway and require every value KPI to move materially. It is the standing
guard against the failure mode where a metric is satisfied by special-casing its inputs
rather than by doing the work — see ``docs/AGENTIC_DELIVERY_PRACTICE.md`` §5.2.

Scope: this guard asserts *responsiveness*, never a magnitude or a direction. It is
KPI-neutral by construction and must never be re-baselined when the canon moves.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Mapping

import pytest
import yaml

from analytics.evaluation_v14 import evaluate_with_overrides
from tests._canon import (
    LENDER_EQUITY_IRR,
    LENDER_MIN_DSCR,
    LENDER_PROJECT_IRR,
    LENDER_PROJECT_NPV,
    LENDER_TOTAL_CFADS_USD,
)

LENDERCASE = Path("scenarios/dutchbay_lendercase_2025Q4.yaml")

#: KPIs that must respond to an economic driver. ``min_dscr`` and ``min_dscr_period``
#: are deliberately absent — see :func:`test_min_dscr_is_held_at_the_sculpt_target`.
RESPONSIVE_KPIS: tuple[str, ...] = (
    "project_irr",
    "equity_irr",
    "project_npv",
    "total_cfads_usd",
    "project_npv_prudential",
    "prudential_rate_used",
)

#: Minimum relative movement that counts as "computed". The observed responses are two
#: to four orders of magnitude larger than this, so the threshold separates real
#: computation from floating-point noise without pinning any magnitude.
MIN_RELATIVE_MOVE = 1e-4

#: Driver perturbations, each unambiguously economic and none of which touches the AEP
#: chain (so no reconciliation guard is disturbed). Values are ~+10%/+25% of scenario.
DRIVERS: tuple[tuple[str, dict[str, float]], ...] = (
    ("tariff +10%", {"tariff.lkr_per_kwh": 22.33}),
    ("opex +25%", {"opex.usd_per_year": 3_750_000.0}),
    ("capex +10%", {"capex.usd_total": 175_560_000.0}),
)


@pytest.fixture(scope="module")
def lendercase() -> dict[str, Any]:
    """Return the canonical lender scenario as an in-memory config dict.

    The in-memory ``raw_config`` route is used deliberately: the path-based branch
    applies the AEP reconciliation guard, which is not what this module is testing.
    """
    if not LENDERCASE.is_file():
        pytest.skip(f"canonical scenario missing: {LENDERCASE}")
    loaded: dict[str, Any] = yaml.safe_load(LENDERCASE.read_text())
    return loaded


def _kpis(cfg: Mapping[str, Any], overrides: Mapping[str, float]) -> dict[str, Any]:
    """Evaluate the scenario through the canonical gateway and return its KPIs."""
    out: Any = evaluate_with_overrides(
        config_path=None, raw_config=copy.deepcopy(dict(cfg)), overrides=dict(overrides)
    )
    kpis: Any = out.get("kpis", out) if isinstance(out, Mapping) else out
    return dict(kpis)


@pytest.fixture(scope="module")
def base_kpis(lendercase: dict[str, Any]) -> dict[str, Any]:
    """Return the unperturbed KPI vector from the gateway."""
    return _kpis(lendercase, {})


def test_gateway_base_reconciles_with_the_pinned_canon(
    base_kpis: dict[str, Any],
) -> None:
    """The gateway's unperturbed vector must still be the pinned canon.

    Without this, a drifted gateway would silently make every movement assertion below
    compare against the wrong baseline.
    """
    assert base_kpis["project_irr"] == pytest.approx(LENDER_PROJECT_IRR, abs=1e-9)
    assert base_kpis["equity_irr"] == pytest.approx(LENDER_EQUITY_IRR, abs=1e-9)
    assert base_kpis["project_npv"] == pytest.approx(LENDER_PROJECT_NPV, rel=1e-9)
    assert base_kpis["total_cfads_usd"] == pytest.approx(
        LENDER_TOTAL_CFADS_USD, rel=1e-9
    )


@pytest.mark.parametrize("label,overrides", DRIVERS, ids=[d[0] for d in DRIVERS])
def test_canon_kpis_respond_to_economic_drivers(
    lendercase: dict[str, Any],
    base_kpis: dict[str, Any],
    label: str,
    overrides: dict[str, float],
) -> None:
    """Every responsive KPI must move materially when a real driver is perturbed.

    A pipeline that emitted the pinned canon regardless of input — the ``if/else``
    returning expected values without computing them — fails here while still passing
    the value oracle.
    """
    shocked = _kpis(lendercase, overrides)
    unmoved: list[str] = []
    for key in RESPONSIVE_KPIS:
        base, new = float(base_kpis[key]), float(shocked[key])
        relative = abs(new - base) / max(abs(base), 1e-6)
        if relative <= MIN_RELATIVE_MOVE:
            unmoved.append(f"{key}: {base!r} -> {new!r} (rel {relative:.3e})")
    assert not unmoved, (
        f"{label} left canon KPIs unresponsive — the vector may be returned rather "
        f"than computed: " + "; ".join(unmoved)
    )


@pytest.mark.parametrize(
    "label,overrides",
    [d for d in DRIVERS if not d[0].startswith("capex")],
    ids=[d[0] for d in DRIVERS if not d[0].startswith("capex")],
)
def test_min_dscr_is_held_at_the_sculpt_target(
    lendercase: dict[str, Any], label: str, overrides: dict[str, float]
) -> None:
    """``min_dscr`` is a solved target, so it must NOT move with revenue or opex.

    Debt is sculpted to the 1.30 covenant target, so the two DSCR entries in the canon
    vector are *inputs the sizer solves to*, not outputs that vary — which is why they
    are excluded from :data:`RESPONSIVE_KPIS`. Recorded explicitly so a later reader
    does not "fix" this guard by making them responsive.

    The target does give way when the case cannot support it: a +10% capex shock drives
    ``min_dscr`` below 1.30, which is why that driver is excluded here.
    """
    shocked = _kpis(lendercase, overrides)
    assert shocked["min_dscr"] == pytest.approx(LENDER_MIN_DSCR, abs=1e-9)
    assert shocked["min_dscr_period"] == pytest.approx(LENDER_MIN_DSCR, abs=1e-9)
