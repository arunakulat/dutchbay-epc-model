"""#733b — run-mode -> debt-engine toy-fallback ceiling wiring.

Slice 1 (#733a, ``analytics.run_modes``) declared the policy contract but nothing
consumed it beyond preflight validation. This slice wires it: the pipeline resolves
the declared mode and asks the debt engine to hard-forbid the toy CAPEX / cost-free-debt
fallbacks for a lender/IC run (``POLICIES[mode].allow_toy_capex is False``), even where
the config opted in. The permission is a CEILING, not a default: screening/developer
(and an undeclared mode) leave the engine's opt-in semantics untouched.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import pytest

from analytics.run_modes import POLICIES, RunMode
from finance.debt_v14 import _FORBID_TOY_FALLBACK_KEY, plan_debt

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")


def _toy_rows(n: int = 10) -> List[Dict[str, Any]]:
    return [
        {"year": i + 1, "cfads_usd": 1.0e6, "revenue_lkr": 1.0e8, "opex_lkr": 2.0e7}
        for i in range(n)
    ]


def _toy_config_no_capex() -> Dict[str, Any]:
    """A config that opts into the toy fallback and declares NO capex key."""
    return {
        "allow_toy_fallback": True,
        "fx": {"start_lkr_per_usd": 300.0, "annual_depr": 0.05},
        "Financing_Terms": {
            "debt_ratio": 0.6,
            "tenor_years": 10,
            "rates": {"usd_nominal": 0.06},
        },
    }


def _cost_free_debt_config() -> Dict[str, Any]:
    """Debt sized on real capex but every tranche rate 0.0, with toy opt-in set."""
    return {
        "allow_toy_fallback": True,
        "fx": {"start_lkr_per_usd": 300.0, "annual_depr": 0.05},
        "capex": {"usd_total": 1.0e8},
        "Financing_Terms": {
            "debt_ratio": 0.6,
            "tenor_years": 10,
            "rates": {"usd_nominal": 0.0},
        },
    }


# --------------------------------------------------------------------------- #
# Policy mapping — the ceiling direction the wiring must translate
# --------------------------------------------------------------------------- #
def test_policy_allow_toy_capex_direction() -> None:
    """screening/developer permit (ceiling loose); lender/IC forbid (hard gate)."""
    assert POLICIES[RunMode.SCREENING].allow_toy_capex is True
    assert POLICIES[RunMode.DEVELOPER].allow_toy_capex is True
    assert POLICIES[RunMode.LENDER].allow_toy_capex is False
    assert POLICIES[RunMode.IC].allow_toy_capex is False


# --------------------------------------------------------------------------- #
# The ceiling hazard: forbid=True (lender/IC) hard-gates; forbid=False is a no-op
# --------------------------------------------------------------------------- #
def test_lender_ceiling_hard_forbids_toy_capex_even_when_opted_in() -> None:
    """forbid_toy_fallback=True refuses the toy CAPEX=100 fallback the config opted into."""
    with pytest.raises(ValueError, match="CAPEX extractor"):
        plan_debt(
            annual_rows=_toy_rows(),
            config=_toy_config_no_capex(),
            forbid_toy_fallback=True,
        )


def test_screening_ceiling_is_a_noop_toy_capex_stays_opt_in() -> None:
    """forbid_toy_fallback=False (screening/developer/undeclared) leaves the opt-in
    intact — the toy CAPEX=100 fallback still fires (0.6 x 100 = 60 debt)."""
    result = plan_debt(
        annual_rows=_toy_rows(),
        config=_toy_config_no_capex(),
        forbid_toy_fallback=False,
    )
    assert result["debt_total"] == pytest.approx(60.0)


def test_lender_ceiling_hard_forbids_cost_free_debt_even_when_opted_in() -> None:
    """forbid_toy_fallback=True refuses cost-free (zero-rate) debt the config opted into."""
    with pytest.raises(ValueError, match="cost-free debt"):
        plan_debt(
            annual_rows=_toy_rows(),
            config=_cost_free_debt_config(),
            forbid_toy_fallback=True,
        )


def test_cost_free_debt_permitted_when_not_forbidden() -> None:
    """forbid_toy_fallback=False keeps the opt-in: cost-free debt is modelled."""
    result = plan_debt(
        annual_rows=_toy_rows(),
        config=_cost_free_debt_config(),
        forbid_toy_fallback=False,
    )
    assert result["debt_total"] > 0


# --------------------------------------------------------------------------- #
# Byte-identity: the wiring never perturbs a real run or leaks the reserved key
# --------------------------------------------------------------------------- #
def _lendercase_kpis(run_block: Any = "__absent__") -> Dict[str, Any]:
    from analytics.pipeline_v14_enhanced import run_v14_pipeline
    from analytics.scenario_loader import load_scenario_config

    cfg = load_scenario_config(LENDER)
    if run_block != "__absent__":
        cfg = {**cfg, "run": run_block}
    return run_v14_pipeline(config=cfg, validation_mode="strict")


def test_lender_mode_is_byte_identical_on_a_real_config() -> None:
    """The committed lendercase has real capex + rates, so declaring lender mode
    changes NOTHING — the ceiling only bites a config that opted into a fabrication."""
    base = _lendercase_kpis()  # no run block
    lender = _lendercase_kpis({"mode": "lender"})
    for key in (
        "project_irr",
        "equity_irr",
        "project_npv",
        "min_dscr",
        "total_cfads_usd",
    ):
        assert lender["kpis"][key] == pytest.approx(base["kpis"][key], abs=0.0, rel=0.0)


def test_reserved_forbid_flag_does_not_leak_into_debt_result() -> None:
    """The lender-mode ceiling stamps a reserved key on the debt engine's OWN config
    copy; it must never surface in the returned debt_result."""
    lender = _lendercase_kpis({"mode": "lender"})
    assert _FORBID_TOY_FALLBACK_KEY not in lender["debt_result"]
