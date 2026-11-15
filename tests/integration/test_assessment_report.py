#!/usr/bin/env python
"""Gated smoke test for the solar PV assessment-report generator.

scripts/generate_solar_assessment_report.py is the end-of-pipeline reporting stage. It
depends on optional extras (reportlab/pvlib/rasterio), so this test is skipped unless
they are installed — exactly like the [wind]/[report]/[solar] suites. It exercises the
analytical chain (a short Monte Carlo) without rendering the full PDF or fetching the map.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

pytest.importorskip("reportlab")
pytest.importorskip("pvlib")
pytest.importorskip("rasterio")

_SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "generate_solar_assessment_report.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("gen_solar_report", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_site_config_is_sane() -> None:
    m = _load_module()
    assert m.SITE["location_name"] == "Sri Jayewardenepura Kotte"
    # USc 8.0 fixed at signing FX 333.79 -> LKR 26.70 (the 5usc-style convention)
    assert m.SITE["competitive_tariff_lkr"] == round(8.0 / 100.0 * 333.79, 2)


def test_routines_run_and_produce_sane_results(tmp_path: Path) -> None:
    m = _load_module()
    m._OUT_PATH = tmp_path  # scenario YAMLs for the path-based routines land here
    R = m.run_routines(trials=20)

    assert {
        "resource",
        "case_fit",
        "case_competitive",
        "mc",
        "sensitivity",
        "optimization",
        "dscr",
    } <= set(R)

    # Wet-zone site at the competitive tariff: a marginal unlevered return, now slightly
    # negative after the 5.9% FX-drift re-baseline (~-1.5%; was low-but-positive at 3%);
    # the FiT case is deeper underwater still.
    assert -0.03 < R["case_competitive"]["project_irr"] < 0.02
    assert R["case_fit"]["project_irr"] < 0.0

    # The Monte Carlo actually ran (no toy fallbacks).
    assert R["mc"]["n"] == 20 and R["mc"]["failed"] == 0

    # Sensitivity surfaced the standard driver set (resource/tariff dominate).
    labels = {d["param"] for d in R["sensitivity"]}
    assert {"Capacity Factor", "Tariff", "CAPEX"} <= labels

    # Both optimisations rank on equity NPV (#1456, #1522 assurance A-3).
    assert R["optimization"]["objective_key"] == "equity_npv"
    assert R["dscr"]["objective_key"] == "equity_npv"
    best = R["dscr"]["opt_best"]
    assert best is not None and set(best) == {"target", "equity_npv"}

    # The key DSCR finding: the unlevered project IRR is INVARIANT to the DSCR target.
    proj_irrs = {round(d["projIRR"], 5) for d in R["dscr"]["sweep"]}
    assert len(proj_irrs) == 1, f"project IRR should be DSCR-invariant, got {proj_irrs}"

    # The narrative is filled from this run (#1578, BW-10), and the claims its prose
    # makes in words still hold on the run's figures.
    import json
    import string

    values = m.narrative_values(R)
    narrative = json.loads(
        (_SCRIPT.parent / "assets" / "solar_assessment_narrative.json").read_text(
            encoding="utf-8"
        )
    )

    def paragraphs(node):
        if isinstance(node, dict):
            for v in node.values():
                yield from paragraphs(v)
        elif isinstance(node, list):
            for v in node:
                yield from paragraphs(v)
        elif isinstance(node, str):
            yield node

    for para in paragraphs(narrative):
        fields = {f for _, f, _, _ in string.Formatter().parse(para) if f}
        assert fields <= set(values), sorted(fields - set(values))
        text = para.format_map(values)
        assert "{" not in text and "}" not in text

    _assert_narrative_claims(R)
    _assert_values_are_wired_to_the_run(R, tmp_path / "solar_scenario_competitive.yaml")


def _assert_narrative_claims(R) -> None:
    """The claims the narrative states in words, checked on a run."""
    fit, cc = R["case_fit"], R["case_competitive"]
    disc = cc["discount_rate_used"]
    inp = R["inputs"]
    # "a negative unlevered return ... under both regimes", NPV strongly negative.
    assert fit["project_irr"] < cc["project_irr"] < 0.0 < disc
    assert fit["project_npv"] < cc["project_npv"] < 0.0
    # The competitive case lifts the DSCR, still far below the 1.30x covenant.
    assert fit["min_dscr"] < cc["min_dscr"] < 1.30
    # "undefined under the feed-in tariff".
    assert fit["equity_irr"] is None
    # At standard gearing the sponsor funds debt service and the equity receives
    # "only" a token amount (results 7.1).
    assert cc["equity_sponsor_cure_usd"] > 0.0
    assert cc["equity_inflows_usd"] < 0.01 * R["site"]["capex_usd"]

    # Breakevens: the IRR test needs a higher tariff than the DSCR test, and both
    # sit above the competitive tariff.
    be = R["breakeven"]
    assert be["dscr_tariff_lkr"] is not None and be["irr_tariff_lkr"] is not None
    comp = R["site"]["competitive_tariff_lkr"]
    assert comp < be["dscr_tariff_lkr"] < be["irr_tariff_lkr"]

    # "no trial reaches the discount rate".
    assert max(R["mc"]["_irr_trials"]) < disc

    # Tornado: CF and tariff equal and on top, capex third, opex and tax second
    # order, tenor zero.
    t = {d["param"]: d["impact"] for d in R["sensitivity"]}
    assert abs(t["Capacity Factor"] - t["Tariff"]) < 1e-3
    assert min(t["Capacity Factor"], t["Tariff"]) > t["CAPEX"]
    assert t["CAPEX"] > max(t["OPEX"], t["Corporate Tax Rate"])
    assert abs(t["Debt Tenor"]) < 1e-9

    # Discounting (6.2): the equity rate is flat and below the declared hurdle; the
    # built WACC is above the declared project rate, so it would deepen every
    # project NPV; the CAPM block does not drive discounting.
    assert inp["equity_npv_discount_rate"] < inp["equity_discount_rate"]
    assert inp["wacc_built"] > disc
    assert not inp["wacc_drives_discount"]

    # The financing-rate spread (8.3): DFI and USD debt cost less than the equity
    # rate, and the LKR rate is the USD rate plus the expected depreciation.
    assert max(inp["dfi_rate"], inp["usd_rate"]) < inp["equity_npv_discount_rate"]
    assert abs(inp["lkr_rate"] - (inp["usd_rate"] + inp["fx_annual_depr"])) < 1e-9

    # Gearing (8.3): no feasible point; the DSCR falls, equity IRR falls, equity NPV
    # rises and sponsor cures rise with leverage. The re-run matches the optimiser.
    opt = R["optimization"]
    assert opt["best"] is None
    gear = sorted(opt["curve"], key=lambda p: p["x"])
    assert gear[0]["constraint"] < 1.30
    assert gear[-1]["constraint"] < gear[0]["constraint"]
    assert gear[-1]["obj"] > gear[0]["obj"]
    assert gear[-1]["eqIRR"] < gear[0]["eqIRR"]
    assert gear[-1]["cure"] > gear[0]["cure"]
    for p in gear:
        assert abs(p["eqNPV"] - p["obj"]) < 1.0
    # The sign sentence: elsewhere the equity cash flows change sign at most once.
    assert all(int(d["sign_changes"]) <= 1 for d in R["dscr"]["sweep"])

    # DSCR sweep (9): between the ends, a lower target gears up, lowers equity IRR
    # and edges equity NPV up; project returns are invariant.
    sweep = sorted(R["dscr"]["sweep"], key=lambda d: d["target_dscr"])
    lo, hi = sweep[0], sweep[-1]
    assert lo["gearing"] > hi["gearing"]
    assert lo["eqIRR"] < hi["eqIRR"]
    assert lo["eqNPV"] > hi["eqNPV"]
    assert len({round(d["npv"], 0) for d in sweep}) == 1
    # The lock-up step: distributions are locked below the threshold and not at or
    # above it; stepping just below it raises equity IRR and lowers equity NPV.
    cov = sweep[0]["lockup_threshold"]
    assert all(d["locked_years"] > 0 for d in sweep if d["target_dscr"] < cov - 1e-9)
    assert all(d["locked_years"] == 0 for d in sweep if d["target_dscr"] >= cov - 1e-9)
    below = [d for d in sweep if d["target_dscr"] < cov - 1e-9][-1]
    at_cov = min(sweep, key=lambda d: abs(d["target_dscr"] - cov))
    assert below["eqIRR"] > at_cov["eqIRR"]
    assert below["eqNPV"] < at_cov["eqNPV"]
    # The NPV-ranked optimum is the lowest target, worth "only" a little over the
    # covenant; the curve is not monotonic and dips below the covenant.
    curve = sorted(R["dscr"]["opt_curve"], key=lambda p: p["x"])
    best = R["dscr"]["opt_best"]
    assert best["target"] == curve[0]["x"]
    cov_obj = min(curve, key=lambda p: abs(p["x"] - cov))["obj"]
    assert 0.0 < best["equity_npv"] - cov_obj < 0.25e6
    steps = [b["obj"] - a["obj"] for a, b in zip(curve, curve[1:], strict=False)]
    assert any(d > 0 for d in steps) and any(d < 0 for d in steps)
    dip = min(curve, key=lambda p: p["obj"])
    assert dip["x"] < cov
    for d in sweep:
        point = min(curve, key=lambda p: abs(p["x"] - d["target_dscr"]))
        if abs(point["x"] - d["target_dscr"]) < 1e-9:
            assert abs(point["obj"] - d["eqNPV"]) < 1.0

    # The first half of the narrative keeps its resource figures literal.
    res = R["resource"]
    assert round(res["cf_mono"], 3) == 0.171
    assert round(res["cf_bifacial"], 3) in (0.182, 0.183)
    assert round(res["yield_mono"]) == 1496
    assert round(res["poa"]) == 1913
    assert round(res["aep_gwh"], 1) == 16.0


def _assert_values_are_wired_to_the_run(R, scenario: Path) -> None:
    """The figures the narrative quotes are the run's own (assurance lane A-2)."""
    import yaml

    from analytics.pipeline_v14_enhanced import run_v14_pipeline

    cfg = yaml.safe_load(scenario.read_text(encoding="utf-8"))
    inp, ft = R["inputs"], cfg["Financing_Terms"]
    assert inp["fx_annual_depr"] == cfg["fx"]["annual_depr"]
    assert inp["lkr_rate"] == ft["rates"]["lkr_nominal"]
    assert inp["dfi_rate"] == ft["rates"]["dfi_nominal"]
    assert inp["usd_rate"] == ft["rates"]["usd_nominal"]
    assert inp["debt_ratio"] == ft["debt_ratio"]
    assert inp["tenor_years"] == ft["tenor_years"]
    assert inp["tax_rate"] == cfg["tax"]["corporate_tax_rate"]
    assert inp["project_discount_rate"] == cfg["returns"]["project_discount_rate"]
    assert inp["wacc_drives_discount"] == bool(
        (cfg.get("wacc") or {}).get("drives_discount_rate")
    )

    def kpi(tariff: float, key: str):
        c = yaml.safe_load(scenario.read_text(encoding="utf-8"))
        c["tariff"]["lkr_per_kwh"] = tariff
        return run_v14_pipeline(config=c)["kpis"][key]

    # Each solved breakeven meets its target, and 0.1 LKR below it does not.
    be = R["breakeven"]
    for key, target, tariff in (
        ("min_dscr", be["dscr_target"], be["dscr_tariff_lkr"]),
        ("project_irr", be["irr_target"], be["irr_tariff_lkr"]),
    ):
        assert kpi(tariff, key) >= target - 1e-9
        assert kpi(tariff - 0.1, key) < target - 1e-9
