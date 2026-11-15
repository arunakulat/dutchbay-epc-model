"""The solar assessment report's narrative is filled from the run (#1578, BW-10).

The narrative used to quote figures from a superseded baseline (a +1.1% project IRR,
breakevens of LKR 50-60/kWh, 35% gearing, 3% FX drift). The figures it quotes are now
``{placeholders}`` that ``render_pdf`` fills from ``narrative_values(R)``. These tests
run without the report's optional extras: they read the narrative JSON and call the
script's pure helpers on a small hand-built results dict. The gated integration test
(tests/integration/test_assessment_report.py) checks the same placeholders, and the
narrative's qualitative claims, against a real run.

``TEST-01`` oracles that did not originate in this change: the narrative JSON's own
placeholders (parsed with ``string.Formatter``) and the stale figures read from the
narrative as it stood on main before this change.
"""

from __future__ import annotations

import importlib.util
import json
import string
from pathlib import Path
from typing import Any, Dict, Iterator

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / "scripts" / "generate_solar_assessment_report.py"
_NARRATIVE = _ROOT / "scripts" / "assets" / "solar_assessment_narrative.json"


def _load_module() -> Any:
    spec = importlib.util.spec_from_file_location("gen_solar_report_narr", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _paragraphs() -> Iterator[str]:
    def walk(node: Any) -> Iterator[str]:
        if isinstance(node, dict):
            for value in node.values():
                yield from walk(value)
        elif isinstance(node, list):
            for value in node:
                yield from walk(value)
        elif isinstance(node, str):
            yield node

    yield from walk(json.loads(_NARRATIVE.read_text(encoding="utf-8")))


def _placeholders() -> set[str]:
    names: set[str] = set()
    for para in _paragraphs():
        for _, field, spec, conv in string.Formatter().parse(para):
            if field is not None:
                assert not spec and conv is None, (field, spec, conv)
                names.add(field)
    return names


def _results(*, dscr_breakeven: float | None = 73.04) -> Dict[str, Any]:
    """A results dict shaped like ``run_routines``'s, with round figures."""
    site = {
        "fx": 333.79,
        "fit_tariff_lkr": 14.46,
        "competitive_tariff_lkr": 26.7,
        "competitive_usc": 8.0,
    }
    inputs = {
        "fx_annual_depr": 0.0589,
        "lkr_rate": 0.1339,
        "dfi_rate": 0.065,
        "usd_rate": 0.08,
        "lkr_max": 0.45,
        "dfi_max": 0.10,
        "usd_min": 0.45,
        "tenor_years": 15,
        "interest_only_years": 2,
        "construction_years": 1,
        "debt_ratio": 0.70,
        "cfads_haircut": 0.10,
        "tax_rate": 0.30,
        "loss_carryforward_years": 6,
        "project_discount_rate": 0.10,
        "equity_discount_rate": 0.15,
        "wacc_drives_discount": False,
        "wacc_built": 0.116,
        "cost_of_equity_built": 0.20,
        "wacc_cost_of_debt": 0.08,
        "wacc_target_gearing": 0.70,
        "equity_npv_discount_rate": 0.10,
    }
    case = {
        "discount_rate_used": 0.10,
        "project_irr": -0.026,
        "project_npv": -8.06e6,
        "min_dscr": 0.32,
        "equity_irr": -0.463,
        "equity_sponsor_cure_usd": 7.0e6,
        "equity_inflows_usd": 1_200.0,
    }

    def gear(
        x: float, dscr: float, npv: float, irr: float, cure: float, sc: int
    ) -> Dict[str, Any]:
        return {
            "x": x,
            "constraint": dscr,
            "obj": npv,
            "eqNPV": npv,
            "eqIRR": irr,
            "cure": cure,
            "sign_changes": sc,
        }

    def sweep(
        t: float, g: float, irr: float, npv: float, locked: int
    ) -> Dict[str, Any]:
        return {
            "target_dscr": t,
            "gearing": g,
            "eqIRR": irr,
            "projIRR": -0.026,
            "npv": -8.06e6,
            "eqNPV": npv,
            "locked_years": locked,
            "lockup_threshold": 1.30,
            "sign_changes": 1,
        }

    trials = [-0.037, -0.027, -0.019]
    return {
        "site": site,
        "inputs": inputs,
        "case_fit": {
            **case,
            "project_irr": -0.099,
            "project_npv": -10.22e6,
            "min_dscr": 0.12,
            "equity_irr": None,
        },
        "case_competitive": case,
        "mc": {
            "n": 3,
            "failed": 0,
            "_irr_trials": trials,
            "proj_irr": {"p10": -0.037, "p50": -0.027, "p90": -0.019},
            "proj_mean": -0.027,
            "p_below_0": 1.0,
            "eq_p50": -0.437,
            "eq_p_below_0": 1.0,
            "coverage": {"equity_irr": {"defined_trials": 2, "unavailable_trials": 1}},
        },
        "breakeven": {
            "dscr_target": 1.30,
            "dscr_tariff_lkr": dscr_breakeven,
            "irr_target": 0.10,
            "irr_tariff_lkr": 85.7,
        },
        "sensitivity": [
            {"param": p, "impact": i}
            for p, i in (
                ("Capacity Factor", 0.021),
                ("Tariff", 0.021),
                ("CAPEX", 0.016),
                ("OPEX", 0.007),
                ("Corporate Tax Rate", 0.004),
                ("Debt Tenor", 0.0),
            )
        ],
        "optimization": {
            "curve": [
                gear(0.75, 0.30, -6.45e6, -0.468, 8.06e6, 1),
                gear(0.35, 0.69, -7.63e6, -0.257, 0.12e6, 3),
                gear(0.30, 0.98, -7.91e6, -0.151, 0.0, 1),
            ],
            "best": None,
        },
        "dscr": {
            "sweep": [
                sweep(1.60, 0.19, -0.069, -8.49e6, 0),
                sweep(1.30, 0.235, -0.078, -8.44e6, 0),
                sweep(1.20, 0.255, -0.074, -8.62e6, 14),
                sweep(1.05, 0.29, -0.088, -8.36e6, 14),
            ],
            "opt_curve": [
                {"x": 1.60, "obj": -8.49e6, "feasible": True},
                {"x": 1.3000000000000003, "obj": -8.44e6, "feasible": True},
                {"x": 1.25, "obj": -8.70e6, "feasible": True},
                {"x": 1.05, "obj": -8.36e6, "feasible": True},
            ],
            "opt_best": {"target": 1.05, "equity_npv": -8.36e6},
        },
    }


def test_every_placeholder_in_the_narrative_is_a_run_value() -> None:
    values = _load_module().narrative_values(_results())
    missing = _placeholders() - set(values)
    assert not missing, sorted(missing)


def test_every_paragraph_renders_without_leftover_braces() -> None:
    values = _load_module().narrative_values(_results())
    for para in _paragraphs():
        text = para.format_map(values)
        assert "{" not in text and "}" not in text, text[:120]


def test_the_values_are_formatted_from_the_results() -> None:
    v = _load_module().narrative_values(_results())
    assert (v["fit_irr"], v["comp_irr"]) == ("-9.9%", "-2.6%")
    assert (v["fit_npv"], v["comp_npv"]) == ("-USD 10.22M", "-USD 8.06M")
    assert v["comp_eq_irr"] == "-46.3%"
    assert (v["disc"], v["wacc_built"], v["fx_depr"]) == ("10%", "11.6%", "5.89%")
    assert (v["gap_pp"], v["irr_lift_pp"]) == ("12.6", "7.3")
    assert (v["be_dscr_lkr"], v["be_dscr_usc"]) == ("73.0", "21.9")
    assert (v["be_irr_lkr"], v["be_irr_x_comp"]) == ("85.7", "3.2")
    assert (v["mc_reach"], v["mc_best"]) == ("0", "-1.9%")
    # Curves are read in order of x, whatever order the routine returned them in.
    assert (v["opt_lo"], v["opt_dscr_lo"], v["opt_npv_hi"]) == (
        "30%",
        "0.98",
        "-USD 6.45M",
    )
    assert (v["dscr_lo"], v["dscr_gear_lo"], v["dscr_eqnpv_hi"]) == (
        "1.05",
        "29.0%",
        "-USD 8.49M",
    )
    assert (v["dscr_best"], v["dscr_best_eqnpv"]) == ("1.05", "-USD 8.36M")


def test_the_covenant_step_and_the_leverage_mechanism_come_from_the_run() -> None:
    # BW-10 domain lane R-1 and R-2: the DSCR curve steps at the lock-up threshold,
    # and the equity NPV gain with gearing comes with sponsor-funded debt service.
    v = _load_module().narrative_values(_results())
    assert (v["dscr_cov"], v["dscr_lock_years"]) == ("1.30", "14")
    assert (v["dscr_below"], v["dscr_eq_below"], v["dscr_eqnpv_below"]) == (
        "1.20",
        "-7.4%",
        "-USD 8.62M",
    )
    assert (v["dscr_eq_cov"], v["dscr_eqnpv_cov"]) == ("-7.8%", "-USD 8.44M")
    assert (v["dscr_dip"], v["dscr_eqnpv_dip"]) == ("1.25", "-USD 8.70M")
    assert v["dscr_best_margin"] == "USD 0.08M"
    assert v["dscr_npv_span"] == "USD 0.34M"
    assert (v["opt_eq_lo"], v["opt_eq_hi"]) == ("-15.1%", "-46.8%")
    assert (v["opt_cure_lo"], v["opt_cure_hi"]) == ("USD 0.00M", "USD 8.06M")
    assert v["opt_npv_gain"] == "USD 1.46M"
    assert (v["comp_cure"], v["comp_eq_dist"]) == ("USD 7.00M", "USD 1k")
    assert (v["eq_npv_disc"], v["wacc_kd"], v["wacc_gear"]) == ("10%", "8.0%", "70%")


def test_the_sign_sentence_names_the_multi_root_gearing_points() -> None:
    mod = _load_module()
    v = mod.narrative_values(_results())
    assert v["eq_sign_sentence"].startswith(
        "Here the equity cash flows change sign three times at 35% gearing,"
    )
    R = _results()
    for point in R["optimization"]["curve"]:
        point["sign_changes"] = 1
    assert "at most once in every case" in mod.narrative_values(R)["eq_sign_sentence"]


def test_an_unreached_breakeven_reads_as_more_than_the_ceiling() -> None:
    v = _load_module().narrative_values(_results(dscr_breakeven=None))
    assert v["be_dscr_lkr"] == "400+"
    assert v["be_dscr_x_fit"] == "28+"


def test_an_undefined_equity_irr_reads_as_undefined() -> None:
    R = _results()
    R["case_competitive"] = {**R["case_competitive"], "equity_irr": None}
    assert _load_module().narrative_values(R)["comp_eq_irr"] == "undefined"


@pytest.mark.parametrize(
    "stale",
    [
        "+1.1%",
        "-3.8%",
        "LKR 50/kWh",
        "LKR 60/kWh",
        "LKR 50-60/kWh",
        "35% gearing",
        "3% per year",
    ],
)
def test_the_superseded_figures_are_gone(stale: str) -> None:
    assert not any(stale in para for para in _paragraphs())


def test_breakeven_bisects_a_rising_metric() -> None:
    be = _load_module()._breakeven_tariff(lambda t: t / 100.0, 0.5, lo=10.0)
    assert be == pytest.approx(50.0, abs=0.01)


def test_breakeven_is_the_lower_bound_when_already_met() -> None:
    assert _load_module()._breakeven_tariff(lambda t: 2.0, 1.3, lo=14.46) == 14.46


def test_breakeven_is_none_when_not_reached_by_the_ceiling() -> None:
    assert _load_module()._breakeven_tariff(lambda t: t / 1e4, 1.3, lo=10.0) is None


def test_an_undefined_metric_counts_as_not_met() -> None:
    be = _load_module()._breakeven_tariff(
        lambda t: None if t < 80.0 else 0.2, 0.1, lo=10.0
    )
    assert be == pytest.approx(80.0, abs=0.01)


def test_breakeven_allows_rounding_slack_on_a_capped_dscr() -> None:
    # Sculpted debt pins the minimum DSCR at the covenant, give or take rounding:
    # 1.2999999999999998 must count as meeting 1.30, or the solver runs to the ceiling.
    capped = 1.2999999999999998
    be = _load_module()._breakeven_tariff(
        lambda t: min(t / 50.0, capped), 1.30, lo=10.0
    )
    assert be == pytest.approx(65.0, abs=0.01)


def test_render_pdf_fills_every_section_and_hard_codes_no_tariff() -> None:
    # Assurance lane A-2: the run-to-prose wiring is in render_pdf, which the unit
    # tests above do not reach. The narrative sections are filled from the values,
    # and the executive summary quotes no literal rupee figure.
    import re

    source = _SCRIPT.read_text(encoding="utf-8")
    assert "P(para.format_map(V))" in source
    start = source.index("Headline finding")
    summary = source[start : source.index("story.append(PageBreak())", start)]
    assert not re.search(r"LKR(&nbsp;|\s)\d", summary), "literal LKR figure in summary"
    assert "{V['be_dscr_lkr']}" in summary and "{V['be_irr_lkr']}" in summary
