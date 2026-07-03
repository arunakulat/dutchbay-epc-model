#!/usr/bin/env python
"""Tests for the capital_risk_layer_v14 facade (#33).

Covers the source-agnostic aggregator (VaR/CVaR, DSCR breach probability, AEP
exceedance) with synthetic distributions, and a small driver-MC smoke test that
wires evaluate_with_overrides → aggregation.

Context:
    Sprint 11 - Issue #33 (capital_risk_layer_v14 facade).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from analytics.capital_risk_layer_v14 import (
    DRIVER_MC_TRIAL_METRICS,
    CapitalRiskLayer,
    build_case_metadata_from_trials,
    build_driver_mc_tail_snapshot,
    compute_capital_risk_layer,
    run_capital_risk_layer,
    run_driver_mc,
)
from analytics.sensitivity.tail_risk import TailRiskConfig

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER_CONFIG = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")


@pytest.fixture
def synthetic() -> dict:
    rng = np.random.default_rng(0)
    return {
        "irr": rng.normal(0.08, 0.02, 2000),
        "npv": rng.normal(-3e6, 5e6, 2000),
        "dscr": rng.normal(1.30, 0.08, 2000),
        "aep": rng.normal(402.0, 30.0, 2000),
    }


def test_aggregator_returns_layer(synthetic: dict) -> None:
    layer = compute_capital_risk_layer(
        equity_irr_samples=synthetic["irr"],
        min_dscr_samples=synthetic["dscr"],
        equity_npv_samples=synthetic["npv"],
        aep_gwh_samples=synthetic["aep"],
        dscr_covenant=1.20,
    )
    assert isinstance(layer, CapitalRiskLayer)
    assert layer.n_samples == 2000
    assert layer.confidence == 0.95


def test_cvar_not_better_than_var(synthetic: dict) -> None:
    """CVaR (mean of the worst tail) must be <= VaR for returns."""
    layer = compute_capital_risk_layer(
        equity_irr_samples=synthetic["irr"], min_dscr_samples=synthetic["dscr"]
    )
    vc = layer.equity_irr_var_cvar
    assert vc.cvar <= vc.var


def test_dscr_breach_probability(synthetic: dict) -> None:
    layer = compute_capital_risk_layer(
        equity_irr_samples=synthetic["irr"],
        min_dscr_samples=synthetic["dscr"],
        dscr_covenant=1.20,
    )
    # N(1.30, 0.08): P(DSCR < 1.20) ~ 0.106.
    assert 0.0 <= layer.dscr["prob_breach"] <= 1.0
    assert layer.dscr["prob_breach"] == pytest.approx(0.106, abs=0.04)
    assert layer.dscr["min"] < layer.dscr["p50"]


def test_aep_exceedance_ordering(synthetic: dict) -> None:
    layer = compute_capital_risk_layer(
        equity_irr_samples=synthetic["irr"],
        min_dscr_samples=synthetic["dscr"],
        aep_gwh_samples=synthetic["aep"],
    )
    assert layer.aep is not None
    assert layer.aep["p99"] < layer.aep["p90"] < layer.aep["p50"]


def test_npv_optional(synthetic: dict) -> None:
    layer = compute_capital_risk_layer(
        equity_irr_samples=synthetic["irr"], min_dscr_samples=synthetic["dscr"]
    )
    assert layer.equity_npv_var_cvar is None
    assert layer.aep is None


def test_too_few_samples_raises() -> None:
    with pytest.raises(ValueError, match="Need >="):
        compute_capital_risk_layer(
            equity_irr_samples=[0.08] * 5, min_dscr_samples=[1.3] * 5
        )


def test_driver_mc_shapes() -> None:
    mc = run_driver_mc(
        LENDER_CONFIG,
        drivers={"Financing_Terms.debt_ratio": {"mean": 0.625, "std": 0.02}},
        n_samples=25,
        seed=1,
    )
    assert set(mc) == {"equity_irr", "equity_npv", "min_dscr"}
    assert all(arr.shape == (25,) for arr in mc.values())


def test_run_capital_risk_layer_smoke() -> None:
    layer = run_capital_risk_layer(
        LENDER_CONFIG,
        drivers={"Financing_Terms.debt_ratio": {"mean": 0.625, "std": 0.02}},
        n_samples=25,
        seed=1,
    )
    assert layer.n_samples == 25
    assert 0.0 <= layer.dscr["prob_breach"] <= 1.0
    assert layer.equity_irr_var_cvar.var_label == "VaR(95%)"


# ---------------------------------------------------------------------------
# Distributional tail-risk plumbing + wire (#657)
# ---------------------------------------------------------------------------

_DRIVERS = {"Financing_Terms.debt_ratio": {"mean": 0.625, "std": 0.02}}


def test_driver_mc_default_return_unchanged() -> None:
    # Opt-in feature must not alter the historical three-key return surface.
    mc = run_driver_mc(LENDER_CONFIG, drivers=_DRIVERS, n_samples=20, seed=3)
    assert set(mc) == {"equity_irr", "equity_npv", "min_dscr"}


def test_driver_mc_collect_trials_adds_all_metric_buckets() -> None:
    mc = run_driver_mc(
        LENDER_CONFIG, drivers=_DRIVERS, n_samples=20, seed=3, collect_trials=True
    )
    # Legacy keys stay, plus every canonical trial metric, all shape (n,).
    assert {"equity_irr", "equity_npv", "min_dscr"}.issubset(mc)
    for m in DRIVER_MC_TRIAL_METRICS:
        assert mc[m].shape == (20,), (m, mc[m].shape)


def test_driver_mc_mode_parity_same_seed() -> None:
    # collect_trials must not perturb the RNG draw sequence: the three legacy
    # arrays are identical whether or not trials are collected.
    base = run_driver_mc(LENDER_CONFIG, drivers=_DRIVERS, n_samples=20, seed=5)
    full = run_driver_mc(
        LENDER_CONFIG, drivers=_DRIVERS, n_samples=20, seed=5, collect_trials=True
    )
    for k in ("equity_irr", "equity_npv", "min_dscr"):
        assert np.array_equal(base[k], full[k])
    # dscr_min aliases min_dscr; the collected equity_irr matches the legacy array.
    assert np.array_equal(full["dscr_min"], full["min_dscr"])
    assert np.array_equal(base["equity_irr"], full["equity_irr"])


def test_build_case_metadata_bucket_shape() -> None:
    mc = run_driver_mc(
        LENDER_CONFIG, drivers=_DRIVERS, n_samples=20, seed=7, collect_trials=True
    )
    case = build_case_metadata_from_trials(mc, label="lender_p50")
    assert case["label"] == "lender_p50"
    trials = case["metadata"]["trials"]
    # Exactly the canonical metrics, each a plain JSON-friendly list of floats.
    assert set(trials) == set(DRIVER_MC_TRIAL_METRICS)
    assert "min_dscr" not in trials  # convenience alias dropped, no double-count
    for m, arr in trials.items():
        assert isinstance(arr, list) and len(arr) == 20
        assert all(isinstance(v, float) for v in arr)


def test_build_driver_mc_tail_snapshot_var_cvar_and_breach() -> None:
    snap = build_driver_mc_tail_snapshot(
        LENDER_CONFIG, drivers=_DRIVERS, n_samples=40, seed=11
    )
    rows = {r["metric"]: r for r in snap["rows"]}
    assert set(rows) == set(DRIVER_MC_TRIAL_METRICS)

    irr_row = rows["project_irr"]
    # Quantile ordering holds and CVaR sits at or below the downside VaR.
    assert irr_row["p5"] <= irr_row["p10"] <= irr_row["p95"]
    assert irr_row["cvar"] <= irr_row["p5"]
    assert "prob_breach" not in irr_row  # non-DSCR metric: no breach key

    dscr_row = rows["dscr_min"]
    assert 0.0 <= dscr_row["prob_breach"] <= 1.0
    assert dscr_row["dscr_floor"] == pytest.approx(TailRiskConfig().dscr_floor)


def test_build_driver_mc_tail_snapshot_respects_metric_keys() -> None:
    snap = build_driver_mc_tail_snapshot(
        LENDER_CONFIG,
        drivers=_DRIVERS,
        n_samples=30,
        seed=13,
        metric_keys=["dscr_min"],
    )
    assert [r["metric"] for r in snap["rows"]] == ["dscr_min"]


@pytest.mark.parametrize("seed", [11, 42, 7])
def test_lender_case_dscr_breach_is_zero_not_fabricated(seed: int) -> None:
    # #657 Fable blocker (SERIOUS: false lender risk number). The dual-DSCR sculpt
    # pins per-trial dscr_min at the covenant floor (1.30) by construction — every
    # trial within ~1e-16 of the floor. Before the fix, the strict `arr < floor`
    # comparison counted that representation noise as breaches and reported an 85-93%
    # DSCR covenant-breach probability on the flagship lender case whose TRUE value is
    # 0.0. A lender must never see a fabricated breach probability.
    snap = build_driver_mc_tail_snapshot(
        LENDER_CONFIG, drivers=_DRIVERS, n_samples=40, seed=seed
    )
    dscr_row = {r["metric"]: r for r in snap["rows"]}["dscr_min"]
    assert dscr_row["prob_breach"] == pytest.approx(0.0)
    # The sculpt degeneracy is disclosed, not silently swallowed: the informative
    # lender tail lives in LLCR/PLCR and the balloon, not min-DSCR.
    assert dscr_row["degeneracy"] == "dscr_min_pinned_at_floor"
    assert "LLCR/PLCR" in dscr_row["degeneracy_note"]


def test_tail_snapshot_require_trials_fail_loud_when_absent() -> None:
    # CESSPIT: a metric with no trial array yields an explicit no_trials note,
    # never a silently fabricated distributional statistic.
    from analytics.sensitivity.tail_risk import _build_case_tail_snapshot

    empty_case = build_case_metadata_from_trials({}, label="no_mc")
    out = _build_case_tail_snapshot(
        case=empty_case,
        metric_keys=["project_irr"],
        run_cfg=TailRiskConfig(require_trials=True),
    )
    assert out["rows"][0] == {
        "case": "no_mc",
        "metric": "project_irr",
        "note": "no_trials",
    }


# ---------------------------------------------------------------------------
# tail_risk_report wire (#657 wire b / #715)
# ---------------------------------------------------------------------------


def test_build_driver_mc_tail_report_returns_full_report() -> None:
    from analytics.capital_risk_layer_v14 import build_driver_mc_tail_report
    from analytics.core.risk_metrics import TailRiskReport

    rep = build_driver_mc_tail_report(
        LENDER_CONFIG, drivers=_DRIVERS, n_samples=40, seed=11
    )
    assert isinstance(rep, TailRiskReport)
    # every per-metric summary is populated + the covenant + hurdle rollups exist.
    for name in ("equity_irr", "project_irr", "equity_npv", "project_npv"):
        summary = getattr(rep, name)
        assert summary.metric_name == name
        assert summary.var_cvar is not None and summary.percentiles is not None
    assert 0.0 <= rep.covenant_breaches.dscr_breach_probability <= 1.0
    assert 0.0 <= rep.probability_below_hurdle <= 1.0


def test_tail_report_return_metrics_match_the_collected_mc_arrays() -> None:
    # the four return summaries are the MC distributions themselves — not recomputed.
    from analytics.capital_risk_layer_v14 import (
        build_driver_mc_tail_report,
        run_driver_mc,
    )

    trials = run_driver_mc(
        LENDER_CONFIG, drivers=_DRIVERS, n_samples=40, seed=11, collect_trials=True
    )
    rep = build_driver_mc_tail_report(
        LENDER_CONFIG, drivers=_DRIVERS, n_samples=40, seed=11
    )
    assert rep.equity_irr.mean == pytest.approx(float(trials["equity_irr"].mean()))
    assert rep.project_npv.mean == pytest.approx(float(trials["project_npv"].mean()))
    assert rep.equity_npv.min == pytest.approx(float(trials["equity_npv"].min()))


def test_tail_report_covenant_reshape_is_faithful() -> None:
    # the (n_trials, 1) covenant reshape must be lossless: covenant_breach_probability's
    # per-scenario min(axis=1) of a single column returns the collected per-trial scalars,
    # so the reported *_min_mean equals the mean of the collected scalar arrays.
    from analytics.capital_risk_layer_v14 import (
        build_driver_mc_tail_report,
        run_driver_mc,
    )

    trials = run_driver_mc(
        LENDER_CONFIG, drivers=_DRIVERS, n_samples=40, seed=11, collect_trials=True
    )
    rep = build_driver_mc_tail_report(
        LENDER_CONFIG, drivers=_DRIVERS, n_samples=40, seed=11
    )
    cb = rep.covenant_breaches
    assert cb.dscr_min_mean == pytest.approx(float(trials["dscr_min"].mean()))
    assert cb.llcr_min_mean == pytest.approx(float(trials["llcr"].mean()))
    assert cb.plcr_min_mean == pytest.approx(float(trials["plcr"].mean()))


@pytest.mark.parametrize("seed", [11, 42, 7])
def test_tail_report_lender_dscr_breach_is_zero_not_fabricated(seed: int) -> None:
    # Same #657 blocker as the snapshot path, now via the full report: the dual-DSCR
    # sculpt pins per-trial dscr_min at the covenant floor (1.30), and the noise-tolerant
    # prob_breach must report 0.0, never a fabricated lender breach probability.
    from analytics.capital_risk_layer_v14 import build_driver_mc_tail_report

    rep = build_driver_mc_tail_report(
        LENDER_CONFIG, drivers=_DRIVERS, n_samples=40, seed=seed
    )
    assert rep.covenant_breaches.dscr_breach_probability == pytest.approx(0.0)


@pytest.mark.parametrize("seed", [11, 42, 3])
def test_tail_report_undeclared_llcr_plcr_covenant_not_fabricated(seed: int) -> None:
    # The #715 Fable BLOCK: the lender scenario declares no top-level LLCR/PLCR covenant.
    # Borrowing the DSCR floor (1.30) fabricated a 95-100% LLCR breach (LLCR ~1.296 < 1.30);
    # an undeclared covenant must default to the non-binding 1.0 coverage floor, so a real
    # LLCR/PLCR ~1.30/1.34 reports 0.0 breach — never a fabricated lender covenant breach.
    from analytics.capital_risk_layer_v14 import build_driver_mc_tail_report

    rep = build_driver_mc_tail_report(
        LENDER_CONFIG, drivers=_DRIVERS, n_samples=40, seed=seed
    )
    cb = rep.covenant_breaches
    assert cb.llcr_breach_probability == pytest.approx(0.0)
    assert cb.plcr_breach_probability == pytest.approx(0.0)
    # sanity: the coverage ratios really are well above the non-binding 1.0 floor.
    assert cb.llcr_min_mean > 1.0 and cb.plcr_min_mean > 1.0


def test_risk_config_llcr_plcr_default_is_non_binding_not_dscr() -> None:
    # _risk_config_from_scenario must NOT borrow the DSCR covenant for an undeclared
    # LLCR/PLCR floor (that is the fabricated-breach root); the default is 1.0.
    from analytics.capital_risk_layer_v14 import _risk_config_from_scenario

    rc = _risk_config_from_scenario(LENDER_CONFIG)
    assert rc.min_dscr == pytest.approx(1.30)  # the declared DSCR covenant is read
    assert rc.min_llcr == pytest.approx(1.0)  # undeclared -> non-binding, NOT 1.30
    assert rc.min_plcr == pytest.approx(1.0)


def test_declared_llcr_covenant_in_constraints_is_read(tmp_path) -> None:
    # when a scenario DOES declare an LLCR covenant in constraints, it is honored (so the
    # non-binding default is only a fallback, not a ceiling on real covenant evaluation).
    import yaml

    from analytics.capital_risk_layer_v14 import _risk_config_from_scenario
    from analytics.scenario_loader import load_scenario_config

    cfg = load_scenario_config(LENDER_CONFIG)
    cfg.setdefault("constraints", {})["min_llcr_covenant"] = 1.40
    p = tmp_path / "with_llcr_covenant.yaml"
    p.write_text(yaml.safe_dump(cfg))
    rc = _risk_config_from_scenario(str(p))
    assert rc.min_llcr == pytest.approx(1.40)


def test_tail_report_is_deterministic_for_a_seed() -> None:
    from analytics.capital_risk_layer_v14 import build_driver_mc_tail_report

    a = build_driver_mc_tail_report(
        LENDER_CONFIG, drivers=_DRIVERS, n_samples=30, seed=5
    )
    b = build_driver_mc_tail_report(
        LENDER_CONFIG, drivers=_DRIVERS, n_samples=30, seed=5
    )
    assert a.equity_irr.mean == b.equity_irr.mean
    assert a.covenant_breaches.dscr_breach_probability == (
        b.covenant_breaches.dscr_breach_probability
    )


def test_tail_report_covenant_threshold_flows_through() -> None:
    # the covenant floor in the supplied RiskConfig reaches covenant_breach_probability:
    # an unreachably-low DSCR floor => 0 breach; a floor above every trial => 1.0 breach.
    from analytics.capital_risk_layer_v14 import build_driver_mc_tail_report
    from analytics.core.risk_metrics import RiskConfig

    loose = RiskConfig(
        confidence_level=0.95,
        target_return=0.0,
        min_dscr=0.01,
        min_llcr=0.01,
        min_plcr=0.01,
    )
    strict = RiskConfig(
        confidence_level=0.95,
        target_return=0.0,
        min_dscr=99.0,
        min_llcr=99.0,
        min_plcr=99.0,
    )
    rep_loose = build_driver_mc_tail_report(
        LENDER_CONFIG, drivers=_DRIVERS, n_samples=30, seed=9, risk_config=loose
    )
    rep_strict = build_driver_mc_tail_report(
        LENDER_CONFIG, drivers=_DRIVERS, n_samples=30, seed=9, risk_config=strict
    )
    assert rep_loose.covenant_breaches.dscr_breach_probability == pytest.approx(0.0)
    assert rep_strict.covenant_breaches.dscr_breach_probability == pytest.approx(1.0)


def test_risk_config_from_scenario_is_config_first() -> None:
    from analytics.capital_risk_layer_v14 import _risk_config_from_scenario

    rc = _risk_config_from_scenario(LENDER_CONFIG)
    assert 0.0 <= rc.confidence_level <= 1.0
    assert rc.min_dscr > 0.0 and rc.min_llcr > 0.0 and rc.min_plcr > 0.0
