"""Recomputed P90 downside beside the CFADS-ratio method (#1836).

Oracles do not come from the code under test (TEST-01):

* hand-worked fixed-debt coverage on a synthetic debt result (bridge fold and senior fee),
  and the hand algebra of the ratio method: (r x CFADS - fee) / service per row;
* the engine's own published figures: the base case's coverage equals the engine's
  ``dscr_by_year`` and ``llcr``, the P90 case bills r x the base year-1 energy, and the
  sizing downside is the factor the engine's ``dual_dscr`` detail publishes (the lender
  case's declared flat factor, not P90/P50, because it does not bind the downside);
* the tax re-basing: the recomputed case's CFADS is rebuilt here, independently, with
  the engine's cashflow builder and the committed loan's interest read straight off the
  base rows (interest_usd x fx_rate), and the P90 case's own-debt figure equals the
  engine's published covenant CFADS; a rebuild that disagrees with the engine is refused;
* identity: when P90 = P50 the recomputed and ratio cases equal the base case;
* the committed summary is regenerated in full and compared, with the SHA-256 of every
  scenario's bytes, so a stale summary fails here.

No sizing, input or KPI changes: ``evaluate_with_overrides`` on the lender case is
compared before and after the analysis runs, and the writer's scenario sweep is recorded
in the PR evidence.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import logging
import math
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, List

import pytest

from analytics.evaluation_v14 import evaluate_with_overrides
from analytics.finance import p90_recomputed_downside as p90
from analytics.mc.fixed_debt_coverage import fixed_debt_coverage_by_row
from analytics.scenario_loader import load_scenario_config

REPO = Path(__file__).resolve().parents[2]
LENDER = REPO / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"
KALPITIYA = REPO / "scenarios" / "kalpitiya_lendercase_160m_fitted.yaml"
HYBRID = REPO / "scenarios" / "dutchbay_hybrid_bess_2025Q4.yaml"
SUMMARY = REPO / "docs" / "finance" / "p90_recomputed_downside_summary.json"
SCRIPT = REPO / "scripts" / "run_p90_recomputed_downside_v14.py"


def _rows(cfads: List[float], first_period: int = 3) -> List[Dict[str, float]]:
    return [
        {
            "annual_row_index": i,
            "year": float(i + 1),
            "debt_period": first_period + i,
            "cfads_usd": v,
        }
        for i, v in enumerate(cfads)
    ]


# Two construction periods, a half-year bridge at period 2 (no row), operating rows at
# periods 3-5. Service 50 on the bridge and 100 a year; fee 10 a year.
_BASE = {
    "annual_row_debt_period_map": _rows([300.0, 300.0, 300.0]),
    "debt_service_total": [0.0, 0.0, 50.0, 100.0, 100.0, 100.0],
    "senior_fee_usd": [0.0, 0.0, 0.0, 10.0, 10.0, 10.0],
    "bridge_debt_period": 2,
}


def test_fixed_debt_coverage_by_row_is_hand_worked() -> None:
    trial = {"annual_row_debt_period_map": _rows([160.0, 400.0, 250.0])}
    rows = fixed_debt_coverage_by_row(_BASE, trial)
    # year 1 folds the bridge: (160 - 10) / 150; years 2-3: (c - 10) / 100.
    assert [r for r, _, _ in rows] == [0, 1, 2]
    assert [n for _, n, _ in rows] == pytest.approx([150.0, 390.0, 240.0])
    assert [d for _, _, d in rows] == pytest.approx([1.0, 3.9, 2.4])


def test_ratio_method_is_scaled_cfads_less_the_committed_fee() -> None:
    r = 0.8
    view = p90._cfads_map(_BASE, r)
    dscr = [d for _, _, d in fixed_debt_coverage_by_row(_BASE, view)]
    assert dscr == pytest.approx([(240 - 10) / 150, (240 - 10) / 100, (240 - 10) / 100])
    # Not r x the base DSCR: the fee does not scale with production.
    base = [d for _, _, d in fixed_debt_coverage_by_row(_BASE, _BASE)]
    assert dscr[1] != pytest.approx(r * base[1])


def test_llcr_scales_by_the_npv_of_net_cfads() -> None:
    view = p90._cfads_map(_BASE, 0.5)
    rate = 0.1
    npv = lambda xs: sum(x / 1.1 ** (i + 1) for i, x in enumerate(xs))  # noqa: E731
    expected = 2.0 * npv([140.0, 140.0]) / npv([290.0, 290.0])
    got = p90._llcr(view, _BASE, 2.0, tenor=2, rate=rate)
    assert got == pytest.approx(expected)


def test_energy_ratio_needs_a_declared_pair() -> None:
    assert p90.p90_energy_ratio({}) is None
    assert (
        p90.p90_energy_ratio({"expected_results": {"net_aep_p50_gwh": 100.0}}) is None
    )
    assert p90.p90_energy_ratio(
        {"expected_results": {"net_aep_p50_gwh": 100.0, "net_aep_p90_gwh": 85.0}}
    ) == (100.0, 85.0, 0.85)
    out = p90.recomputed_p90_downside({"expected_results": {}})
    assert out["status"] == "unavailable"


def test_p90_config_scales_every_billed_capacity_factor_and_no_storage() -> None:
    config = load_scenario_config(HYBRID)
    before = copy.deepcopy(config)
    out = p90.p90_production_config(config, 0.5)
    assert config == before  # the input is not mutated
    assert out["project"]["capacity_factor"] == pytest.approx(
        0.5 * before["project"]["capacity_factor"]
    )
    techs = before["generation"]["technologies"]
    scaled = 0
    for name, block in techs.items():
        new = out["generation"]["technologies"][name]
        if str(block.get("type", "")).lower() == "bess":
            assert new == block
        elif "capacity_factor" in block:
            assert new["capacity_factor"] == pytest.approx(
                0.5 * block["capacity_factor"]
            )
            scaled += 1
    assert scaled >= 2
    er = out["expected_results"]
    assert er["net_aep_p50_gwh"] == before["expected_results"]["net_aep_p90_gwh"]
    with pytest.raises(ValueError, match="capacity factor"):
        p90.p90_production_config({"project": {}}, 0.9)


def test_p90_case_bills_the_ratio_times_base_energy() -> None:
    config = load_scenario_config(LENDER)
    ratio = p90.p90_energy_ratio(config)
    assert ratio is not None
    base = evaluate_with_overrides(raw_config=config, return_full_result=True)
    down = evaluate_with_overrides(
        raw_config=p90.p90_production_config(config, ratio[2]),
        return_full_result=True,
    )
    for b, d in zip(base["annual_rows"], down["annual_rows"], strict=True):
        assert d["net_kwh"] == pytest.approx(ratio[2] * b["net_kwh"], rel=1e-9)
        # Fixed opex does not fall with production.
        assert d["opex_usd"] == pytest.approx(b["opex_usd"], rel=1e-9)


def test_base_case_matches_the_engines_covenant_figures() -> None:
    config = load_scenario_config(LENDER)
    kpis_before = evaluate_with_overrides(raw_config=copy.deepcopy(config))
    result = p90.recomputed_p90_downside(config)
    assert result["status"] == "ok"
    full = evaluate_with_overrides(raw_config=config, return_full_result=True)
    debt = full["debt_result"]
    covenant = [v for v in debt["dscr_by_year"].values() if v is not None]
    base = result["cases"]["base"]
    assert base["min_dscr"] == pytest.approx(min(covenant), abs=1e-12)
    assert base["avg_dscr"] == pytest.approx(sum(covenant) / len(covenant), abs=1e-12)
    assert base["llcr"] == pytest.approx(debt["llcr"], abs=1e-12)
    # The recomputed P90 case is no better than the base on the committed debt.
    assert result["cases"]["recomputed"]["min_dscr"] < base["min_dscr"]
    # KPIs are untouched by the analysis.
    assert evaluate_with_overrides(raw_config=copy.deepcopy(config)) == kpis_before


def test_sizing_downside_is_the_scenarios_own_factor() -> None:
    config = load_scenario_config(LENDER)
    fin = config["Financing_Terms"]
    assert not fin.get("bind_downside")
    result = p90.recomputed_p90_downside(config)
    sizing = result["cases"]["sizing_downside"]
    # Without bind_downside the engine uses the declared flat factor, not P90/P50.
    assert sizing["factor"] == pytest.approx(float(fin["dscr_p99_downside_factor"]))
    assert sizing["source"] == "flat_factor"
    assert sizing["binds_gearing"] is False
    assert sizing["factor"] != pytest.approx(result["p90_over_p50"], abs=1e-3)
    # Hand algebra on the engine's own rows: (factor x CFADS - fee) / service.
    debt = evaluate_with_overrides(raw_config=config, return_full_result=True)[
        "debt_result"
    ]
    view = p90._cfads_map(debt, sizing["factor"])
    expected = [d for _, _, d in fixed_debt_coverage_by_row(debt, view)]
    assert sizing["min_dscr"] == pytest.approx(min(expected), abs=1e-12)
    diff = result["recomputed_minus_sizing_downside"]
    assert diff["min_dscr"] == pytest.approx(
        result["cases"]["recomputed"]["min_dscr"] - sizing["min_dscr"], abs=1e-12
    )


def test_a_scenario_that_binds_the_downside_sizes_on_p90_over_p50() -> None:
    config = load_scenario_config(HYBRID)
    assert config["Financing_Terms"].get("bind_downside")
    result = p90.recomputed_p90_downside(config)
    sizing = result["cases"]["sizing_downside"]
    assert sizing["source"] == "p90_aep"
    assert sizing["binds_gearing"] is True
    assert sizing["factor"] == pytest.approx(result["p90_over_p50"], rel=1e-5)


def test_p90_equal_to_p50_reproduces_the_base_case() -> None:
    config = load_scenario_config(LENDER)
    er = config["expected_results"]
    er["net_aep_p90_gwh"] = er["net_aep_p50_gwh"]
    result = p90.recomputed_p90_downside(config)
    base = result["cases"]["base"]
    for case in ("ratio_method", "recomputed", "recomputed_own_debt_tax"):
        for key in ("min_dscr", "avg_dscr", "llcr"):
            assert result["cases"][case][key] == pytest.approx(base[key], abs=1e-9)
    for key in ("min_dscr", "avg_dscr", "llcr"):
        assert result["tax_rebase_effect"][key] == pytest.approx(0.0, abs=1e-9)


def test_recomputed_case_is_taxed_on_the_committed_loans_interest() -> None:
    from analytics.evaluation_v14 import evaluated_scenario_config
    from finance.cashflow_v14 import build_annual_rows

    config = load_scenario_config(KALPITIYA)
    assert (config.get("tax") or {}).get("balloon_interest_tax_basis") in (None, "paid")
    ratio = p90.p90_energy_ratio(config)
    assert ratio is not None
    result = p90.recomputed_p90_downside(config)
    base = evaluate_with_overrides(raw_config=config, return_full_result=True)
    p90_config = p90.p90_production_config(config, ratio[2])
    down = evaluate_with_overrides(raw_config=p90_config, return_full_result=True)
    debt = base["debt_result"]

    # Oracle: the committed loan's deductible interest, read off the base rows.
    interest = [
        (float(r["interest_usd"]) + float(r.get("balloon_interest_paid_usd") or 0.0))
        * float(r["fx_rate"])
        for r in base["annual_rows"]
    ]
    rows = build_annual_rows(
        evaluated_scenario_config(p90_config), interest_expense_series=interest
    )
    view = {
        "annual_row_debt_period_map": [
            {**m, "cfads_usd": float(rows[int(m["annual_row_index"])]["cfads_usd"])}
            for m in debt["annual_row_debt_period_map"]
        ]
    }
    expected = [d for _, _, d in fixed_debt_coverage_by_row(debt, view)]
    recomputed = result["cases"]["recomputed"]
    assert recomputed["min_dscr"] == pytest.approx(min(expected), abs=1e-12)
    assert recomputed["avg_dscr"] == pytest.approx(
        sum(expected) / len(expected), abs=1e-12
    )

    # The own-debt figure is the engine's published covenant CFADS of the P90 case.
    own = [d for _, _, d in fixed_debt_coverage_by_row(debt, down["debt_result"])]
    assert result["cases"]["recomputed_own_debt_tax"]["min_dscr"] == pytest.approx(
        min(own), abs=1e-12
    )
    # Non-vacuous: the P90 case carries less debt here, so taxing it on the committed
    # (larger) loan's interest raises its coverage.
    effect = result["tax_rebase_effect"]["min_dscr"]
    assert effect > 1e-3
    assert effect == pytest.approx(recomputed["min_dscr"] - min(own), abs=1e-12)


def test_a_rebuild_that_disagrees_with_the_engine_is_refused() -> None:
    debt = {"annual_row_debt_period_map": _rows([300.0, 300.0, 300.0])}
    p90._rebuild_matches_engine(debt, [300.0, 300.0, 300.0], "case")
    with pytest.raises(RuntimeError, match="row 1"):
        p90._rebuild_matches_engine(debt, [300.0, 300.01, 300.0], "case")
    with pytest.raises(RuntimeError, match="row 2"):
        p90._rebuild_matches_engine(debt, [300.0, 300.0], "case")
    with pytest.raises(RuntimeError, match="no covenant CFADS"):
        p90._rebuild_matches_engine({}, [300.0], "case")


def test_binds_gearing_follows_the_engines_binding_case() -> None:
    detail = {
        "downside_ratio": 0.87,
        "downside_source": "p90_aep",
        "solved_gearing_p90": 0.6,
        "binding_production_case": "P50",
    }
    sizing = p90._sizing_downside({"dual_dscr": detail})
    assert sizing is not None and sizing["binds_gearing"] is False
    sizing = p90._sizing_downside(
        {"dual_dscr": {**detail, "binding_production_case": "P90"}}
    )
    assert sizing is not None and sizing["binds_gearing"] is True


def _script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_p90_downside_1836", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _close(a: Any, b: Any) -> bool:
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_close(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_close(x, y) for x, y in zip(a, b, strict=True))
    if isinstance(a, float) or isinstance(b, float):
        return math.isclose(float(a), float(b), rel_tol=1e-9, abs_tol=1e-12)
    return bool(a == b)


def test_committed_summary_is_current() -> None:
    logging.disable(logging.WARNING)
    try:
        fresh = json.loads(json.dumps(_script().run("scenarios/**/*.yaml")))
    finally:
        logging.disable(logging.NOTSET)
    committed = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert committed["scenarios"], "the summary must cover at least one scenario"
    for rel, entry in committed["scenarios"].items():
        digest = hashlib.sha256((REPO / rel).read_bytes()).hexdigest()
        assert entry["scenario_sha256"] == digest, f"{rel} changed; regenerate"
    assert _close(
        fresh, committed
    ), "regenerate docs/finance/p90_recomputed_downside_summary.json"
