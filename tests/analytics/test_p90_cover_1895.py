"""The opt-in P90 cover term (#1895).

Owner ruling on #1895 (2026-11-22, option A): keep the P50 sizing, disclose the recomputed
P90 cover, and add an opt-in ``Financing_Terms.p90_cover_min_dscr`` with no default.

- Absent, nothing changes: no committed scenario declares it, and the pipeline's debt
  result has no ``p90_cover`` key.
- Declared and already met, the figures are those of the scenario without it.
- Declared and not met, the P50 sizing target is raised to the smallest value at which the
  recomputed P90 case meets the cover. This is checked independently by re-running the
  recomputed case on the priced configuration.
- A bad value, a scenario with no P50/P90 pair and one that does not size on DSCR are
  refused, by pre-flight and by the pipeline, naming the path.
"""

from __future__ import annotations

import copy
import glob
import math
from pathlib import Path
from typing import Any, Dict, Mapping

import pytest
import yaml

from analytics.finance.p90_cover import (
    MAX_TARGET_DSCR,
    P90_COVER_KEY,
    TARGET_TOLERANCE,
    resolve_p90_cover,
    solve_p90_cover,
    without_p90_cover,
)
from analytics.finance.p90_recomputed_downside import recomputed_p90_downside
from analytics.pipeline_v14_enhanced import run_v14_pipeline
from analytics.scenario_loader import load_scenario_config
from analytics.schema_guard import ConfigValidationError, validate_config_for_v14

ROOT = Path(__file__).resolve().parents[2]
LENDER = str(ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")


@pytest.fixture(scope="module")
def lender() -> Dict[str, Any]:
    return dict(load_scenario_config(LENDER))


@pytest.fixture(scope="module")
def unbound(lender: Dict[str, Any]) -> Dict[str, Any]:
    return run_v14_pipeline(config=copy.deepcopy(lender))


def _with_cover(config: Mapping[str, Any], cover: Any) -> Dict[str, Any]:
    out = copy.deepcopy(dict(config))
    out["Financing_Terms"][P90_COVER_KEY] = cover
    return out


def _preflight(config: Mapping[str, Any]) -> None:
    validate_config_for_v14(dict(config), "case", ["cashflow", "debt"])


def _recomputed_min(config: Mapping[str, Any]) -> float:
    check = recomputed_p90_downside(copy.deepcopy(dict(config)))
    assert check["status"] == "ok"
    return float(check["cases"]["recomputed"]["min_dscr"])


# --- Absent: nothing changes ---------------------------------------------------------


def test_no_committed_scenario_declares_the_term() -> None:
    for path in sorted(
        glob.glob(str(ROOT / "scenarios" / "**" / "*.yaml"), recursive=True)
    ):
        try:
            raw = yaml.safe_load(Path(path).read_text())
        except yaml.YAMLError:
            continue
        if not isinstance(raw, dict):
            continue
        fin = raw.get("Financing_Terms")
        assert not (isinstance(fin, dict) and P90_COVER_KEY in fin), path


def test_absent_or_null_is_no_term(lender: Dict[str, Any]) -> None:
    assert resolve_p90_cover(lender) is None
    assert resolve_p90_cover(_with_cover(lender, None)) is None
    assert resolve_p90_cover({}) is None
    _preflight(lender)


def test_an_absent_term_leaves_no_trace_in_the_result(
    unbound: Dict[str, Any],
) -> None:
    assert "p90_cover" not in unbound["debt_result"]
    assert "p90_cover" not in unbound


def test_without_the_term_copies_and_drops_only_the_term(
    lender: Dict[str, Any],
) -> None:
    declared = _with_cover(lender, 1.1)
    stripped = without_p90_cover(declared)
    assert P90_COVER_KEY not in stripped["Financing_Terms"]
    assert declared["Financing_Terms"][P90_COVER_KEY] == 1.1
    assert stripped == lender


# --- Declared --------------------------------------------------------------------------


def test_a_cover_already_met_moves_nothing(
    lender: Dict[str, Any], unbound: Dict[str, Any]
) -> None:
    result = run_v14_pipeline(config=_with_cover(lender, 1.0))
    block = result["debt_result"]["p90_cover"]
    assert block["binding"] is False
    assert block["solver_steps"] == 0
    assert block["target_dscr"] == block["declared_target_dscr"]
    assert block["recomputed_min_dscr"] >= 1.0
    assert result["kpis"] == unbound["kpis"]
    assert result["debt_result"]["debt_total"] == unbound["debt_result"]["debt_total"]


def test_a_binding_cover_raises_the_target_until_the_p90_case_meets_it(
    lender: Dict[str, Any], unbound: Dict[str, Any]
) -> None:
    cover = 1.10
    unbound_p90 = _recomputed_min(lender)
    assert unbound_p90 < cover  # the control: on its own sizing the cover is not met

    result = run_v14_pipeline(config=_with_cover(lender, cover))
    block = result["debt_result"]["p90_cover"]
    assert block["binding"] is True
    assert block["source"] == "Financing_Terms.p90_cover_min_dscr"
    assert block["declared_min_dscr"] == cover
    assert block["recomputed_min_dscr_unbound"] == pytest.approx(unbound_p90)
    assert block["target_dscr"] > block["declared_target_dscr"]

    # Independent oracle: the recomputed P90 case on the priced target meets the cover,
    # and a target one tolerance lower does not.
    priced = copy.deepcopy(lender)
    priced["Financing_Terms"]["target_dscr"] = block["target_dscr"]
    assert _recomputed_min(priced) >= cover
    assert _recomputed_min(priced) == pytest.approx(block["recomputed_min_dscr"])
    below = copy.deepcopy(lender)
    below["Financing_Terms"]["target_dscr"] = (
        block["target_dscr"] - 2 * TARGET_TOLERANCE
    )
    assert _recomputed_min(below) < cover

    # Less debt, and the P50 test is still met.
    assert result["debt_result"]["debt_total"] < unbound["debt_result"]["debt_total"]
    assert result["kpis"]["min_dscr"] >= unbound["kpis"]["min_dscr"]


# --- Refusals ----------------------------------------------------------------------------


@pytest.mark.parametrize("bad", ["high", True, math.nan, math.inf, [1.2]], ids=str)
def test_a_value_that_is_not_a_finite_number_is_refused(
    lender: Dict[str, Any], bad: Any
) -> None:
    config = _with_cover(lender, bad)
    with pytest.raises(
        ValueError, match=r"Financing_Terms\.p90_cover_min_dscr must be a finite"
    ):
        resolve_p90_cover(config)
    with pytest.raises(ConfigValidationError, match=r"p90_cover_min_dscr"):
        _preflight(config)


@pytest.mark.parametrize("low", [0, 0.5, 0.999])
def test_a_cover_below_one_is_refused(lender: Dict[str, Any], low: float) -> None:
    config = _with_cover(lender, low)
    with pytest.raises(ValueError, match=r"p90_cover_min_dscr must be at least 1"):
        resolve_p90_cover(config)
    with pytest.raises(
        ConfigValidationError, match=r"p90_cover_min_dscr must be at least 1"
    ):
        _preflight(config)


def test_a_scenario_with_no_p50_p90_pair_is_refused(lender: Dict[str, Any]) -> None:
    config = _with_cover(lender, 1.1)
    del config["expected_results"]["net_aep_p90_gwh"]
    with pytest.raises(
        ValueError, match=r"no expected_results net_aep_p50_gwh / net_aep_p90_gwh"
    ):
        resolve_p90_cover(config)
    with pytest.raises(ConfigValidationError, match=r"no expected_results"):
        _preflight(config)


def test_the_pipeline_refuses_what_preflight_refuses(lender: Dict[str, Any]) -> None:
    with pytest.raises(Exception, match=r"p90_cover_min_dscr must be at least 1"):
        run_v14_pipeline(config=_with_cover(lender, 0.9))


def test_a_scenario_that_does_not_size_on_dscr_is_refused(
    lender: Dict[str, Any],
) -> None:
    config = _with_cover(lender, 1.1)
    config["Financing_Terms"]["debt_sizing"] = "gearing"
    with pytest.raises(
        ValueError, match=r"Financing_Terms\.debt_sizing must be one of"
    ):
        solve_p90_cover(config, 1.1, recompute=lambda _c: {"status": "ok"})


# --- The solve, on a stand-in recomputed case ------------------------------------------


def _fake_recompute():
    """A recomputed P90 minimum that rises with the sizing target: 0.8 x target."""

    def recompute(config: Mapping[str, Any]) -> Dict[str, Any]:
        target = float(config["Financing_Terms"]["target_dscr"])
        assert P90_COVER_KEY not in config["Financing_Terms"]
        return {"status": "ok", "cases": {"recomputed": {"min_dscr": 0.8 * target}}}

    return recompute


def _fake_config(target: float = 1.3) -> Dict[str, Any]:
    return {
        "Financing_Terms": {
            "debt_sizing": "dual_dscr",
            "target_dscr": target,
            P90_COVER_KEY: 1.2,
        }
    }


def test_the_solve_finds_the_smallest_target_that_meets_the_cover() -> None:
    priced, block = solve_p90_cover(_fake_config(), 1.2, recompute=_fake_recompute())
    # 0.8 x target >= 1.2 first holds at target 1.5.
    assert block["binding"] is True
    assert 1.5 <= block["target_dscr"] <= 1.5 + TARGET_TOLERANCE
    assert priced["Financing_Terms"]["target_dscr"] == block["target_dscr"]
    assert P90_COVER_KEY not in priced["Financing_Terms"]
    assert block["recomputed_min_dscr"] >= 1.2


def test_the_solve_leaves_a_met_cover_alone() -> None:
    priced, block = solve_p90_cover(_fake_config(2.0), 1.2, recompute=_fake_recompute())
    assert block["binding"] is False
    assert priced["Financing_Terms"]["target_dscr"] == 2.0


def test_an_unreachable_cover_is_refused() -> None:
    def never(config: Mapping[str, Any]) -> Dict[str, Any]:
        return {"status": "ok", "cases": {"recomputed": {"min_dscr": 0.5}}}

    with pytest.raises(
        ValueError, match=rf"no P50 sizing target up to {MAX_TARGET_DSCR:g}"
    ):
        solve_p90_cover(_fake_config(), 1.2, recompute=never)


def test_an_unavailable_p90_case_is_refused() -> None:
    def unavailable(config: Mapping[str, Any]) -> Dict[str, Any]:
        return {"status": "unavailable", "reason": "no debt service"}

    with pytest.raises(ValueError, match=r"recomputed P90 case is unavailable"):
        solve_p90_cover(_fake_config(), 1.2, recompute=unavailable)
