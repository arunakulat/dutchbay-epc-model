#!/usr/bin/env python
"""Tests for the capital_risk_layer_v14 facade (#33).

Covers the source-agnostic aggregator (VaR/CVaR, DSCR breach probability, AEP
exceedance) and the MC-source-agnostic trials→surface cores, all on synthetic
per-trial distributions (#780 retired the toy driver-MC runner; the canonical
MC path is exercised in test_canonical_mc_end_to_end_feeds_capital_risk_report).

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
    compute_capital_risk_layer,
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


def test_tail_report_from_trials_returns_full_report() -> None:
    from analytics.capital_risk_layer_v14 import _tail_report_from_trials
    from analytics.core.risk_metrics import TailRiskReport

    rep = _tail_report_from_trials(_synthetic_trials(40, seed=11), _risk_cfg())
    assert isinstance(rep, TailRiskReport)
    # every per-metric summary is populated + the covenant + hurdle rollups exist.
    for name in ("equity_irr", "project_irr", "equity_npv", "project_npv"):
        summary = getattr(rep, name)
        assert summary.metric_name == name
        assert summary.var_cvar is not None and summary.percentiles is not None
    assert 0.0 <= rep.covenant_breaches.dscr_breach_probability <= 1.0
    assert 0.0 <= rep.probability_below_hurdle <= 1.0


def test_tail_report_return_metrics_match_the_supplied_arrays() -> None:
    # the four return summaries are the supplied MC distributions themselves — not recomputed.
    from analytics.capital_risk_layer_v14 import _tail_report_from_trials

    trials = _synthetic_trials(40, seed=11)
    rep = _tail_report_from_trials(trials, _risk_cfg())
    assert rep.equity_irr.mean == pytest.approx(float(trials["equity_irr"].mean()))
    assert rep.project_npv.mean == pytest.approx(float(trials["project_npv"].mean()))
    assert rep.equity_npv.min == pytest.approx(float(trials["equity_npv"].min()))


def test_tail_report_covenant_reshape_is_faithful() -> None:
    # the (n_trials, 1) covenant reshape must be lossless: covenant_breach_probability's
    # per-scenario min(axis=1) of a single column returns the supplied per-trial scalars,
    # so the reported *_min_mean equals the mean of the supplied scalar arrays.
    from analytics.capital_risk_layer_v14 import _tail_report_from_trials

    trials = _synthetic_trials(40, seed=11)
    rep = _tail_report_from_trials(trials, _risk_cfg())
    cb = rep.covenant_breaches
    assert cb.dscr_min_mean == pytest.approx(float(trials["dscr_min"].mean()))
    assert cb.llcr_min_mean == pytest.approx(float(trials["llcr"].mean()))
    assert cb.plcr_min_mean == pytest.approx(float(trials["plcr"].mean()))


def test_tail_report_covenant_threshold_flows_through() -> None:
    # the covenant floor in the supplied RiskConfig reaches covenant_breach_probability:
    # an unreachably-low DSCR floor => 0 breach; a floor above every trial => 1.0 breach.
    from analytics.capital_risk_layer_v14 import _tail_report_from_trials
    from analytics.core.risk_metrics import RiskConfig

    trials = _synthetic_trials(30, seed=9)
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
    rep_loose = _tail_report_from_trials(trials, loose)
    rep_strict = _tail_report_from_trials(trials, strict)
    assert rep_loose.covenant_breaches.dscr_breach_probability == pytest.approx(0.0)
    assert rep_strict.covenant_breaches.dscr_breach_probability == pytest.approx(1.0)


def test_build_case_metadata_bucket_shape() -> None:
    trials = {k: list(v) for k, v in _synthetic_trials(20, seed=7).items()}
    trials["min_dscr"] = trials["dscr_min"]  # legacy convenience alias
    case = build_case_metadata_from_trials(trials, label="lender_p50")
    assert case["label"] == "lender_p50"
    packaged = case["metadata"]["trials"]
    # Exactly the canonical metrics, each a plain JSON-friendly list of floats.
    assert set(packaged) == set(DRIVER_MC_TRIAL_METRICS)
    assert "min_dscr" not in packaged  # convenience alias dropped, no double-count
    for _metric, arr in packaged.items():
        assert isinstance(arr, list) and len(arr) == 20
        assert all(isinstance(v, float) for v in arr)


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


def test_risk_config_from_scenario_is_config_first() -> None:
    from analytics.capital_risk_layer_v14 import _risk_config_from_scenario

    rc = _risk_config_from_scenario(LENDER_CONFIG)
    assert 0.0 <= rc.confidence_level <= 1.0
    assert rc.min_dscr > 0.0 and rc.min_llcr > 0.0 and rc.min_plcr > 0.0


# ---------------------------------------------------------------------------
# NPV-distribution PNG + unified capital-risk report from the CANONICAL MC
# (#657 wire c / #716) — MC-source-agnostic, fed from MonteCarloResult.trials
# ---------------------------------------------------------------------------

_RC = None


def _risk_cfg():
    from analytics.capital_risk_layer_v14 import _risk_config_from_scenario

    return _risk_config_from_scenario(LENDER_CONFIG)


def _synthetic_trials(n: int = 60, *, seed: int = 0) -> dict:
    # per-trial arrays with the seven canonical keys; LLCR/PLCR safely above the 1.0 floor
    # and DSCR ~ at the 1.30 sculpt floor (so the no-fabricated-breach path is exercised).
    rng = np.random.default_rng(seed)
    return {
        "equity_irr": rng.normal(-0.048, 0.01, n),
        "project_irr": rng.normal(0.027, 0.01, n),
        "equity_npv": rng.normal(-65e6, 5e6, n),
        "project_npv": rng.normal(-48e6, 5e6, n),
        "dscr_min": np.full(n, 1.30),
        "llcr": rng.normal(1.30, 0.002, n),
        "plcr": rng.normal(1.35, 0.002, n),
    }


def test_emit_npv_distribution_from_trials_writes_png(tmp_path) -> None:
    pytest.importorskip("matplotlib")
    from analytics.capital_risk_layer_v14 import emit_npv_distribution_from_trials

    out = tmp_path / "npv.png"
    p = emit_npv_distribution_from_trials(
        _synthetic_trials(), out, npv_metric="equity_npv"
    )
    assert p == out and p.exists() and p.stat().st_size > 0


def test_emit_npv_distribution_degrades_without_matplotlib(
    tmp_path, monkeypatch
) -> None:
    from analytics import export_helpers
    from analytics.capital_risk_layer_v14 import emit_npv_distribution_from_trials

    monkeypatch.setattr(export_helpers.ChartGenerator, "_get_plt", lambda self: None)
    out = tmp_path / "npv.png"
    p = emit_npv_distribution_from_trials(_synthetic_trials(), out)
    assert p == out and not p.exists()  # degraded gracefully — no file written


def test_emit_npv_distribution_rejects_unknown_metric(tmp_path) -> None:
    from analytics.capital_risk_layer_v14 import emit_npv_distribution_from_trials

    with pytest.raises(ValueError, match="equity_npv.*project_npv"):
        emit_npv_distribution_from_trials(
            _synthetic_trials(), tmp_path / "x.png", npv_metric="made_up"
        )


def test_build_from_trials_assembles_all_three_surfaces(tmp_path) -> None:
    pytest.importorskip("matplotlib")
    from analytics.capital_risk_layer_v14 import (
        DRIVER_MC_TRIAL_METRICS,
        CapitalRiskReport,
        build_capital_risk_report_from_trials,
    )
    from analytics.core.risk_metrics import TailRiskReport

    rep = build_capital_risk_report_from_trials(
        _synthetic_trials(60), tmp_path, risk_config=_risk_cfg(), scenario="lender"
    )
    assert isinstance(rep, CapitalRiskReport)
    assert {r["metric"] for r in rep.snapshot["rows"]} == set(DRIVER_MC_TRIAL_METRICS)
    assert isinstance(rep.tail_report, TailRiskReport)
    assert (
        rep.npv_distribution_png.exists()
        and rep.npv_distribution_png.stat().st_size > 0
    )
    assert rep.scenario == "lender" and rep.model_version and rep.n_trials == 60


def test_build_from_trials_fails_loud_on_missing_key(tmp_path) -> None:
    from analytics.capital_risk_layer_v14 import build_capital_risk_report_from_trials

    trials = _synthetic_trials()
    del trials["llcr"]
    with pytest.raises(KeyError, match="llcr"):
        build_capital_risk_report_from_trials(
            trials, tmp_path, risk_config=_risk_cfg(), scenario="x"
        )


def test_build_from_trials_no_fabricated_breach(tmp_path) -> None:
    # dscr pinned at the 1.30 floor -> 0.0 breach (the #725/#657 invariant), and the
    # config-first LLCR/PLCR non-binding 1.0 floor (the #715 fix) -> 0.0 (llcr ~1.30 > 1.0).
    from analytics.capital_risk_layer_v14 import build_capital_risk_report_from_trials

    rep = build_capital_risk_report_from_trials(
        _synthetic_trials(60), tmp_path, risk_config=_risk_cfg(), scenario="x"
    )
    cb = rep.tail_report.covenant_breaches
    assert cb.dscr_breach_probability == pytest.approx(0.0)
    assert cb.llcr_breach_probability == pytest.approx(0.0)
    assert cb.plcr_breach_probability == pytest.approx(0.0)
    # The pinned-at-floor sculpt degeneracy is disclosed on the snapshot, not silently
    # swallowed: the informative lender tail lives in LLCR/PLCR and the balloon.
    dscr_row = {r["metric"]: r for r in rep.snapshot["rows"]}["dscr_min"]
    assert dscr_row["degeneracy"] == "dscr_min_pinned_at_floor"
    assert "LLCR/PLCR" in dscr_row["degeneracy_note"]


def test_build_from_trials_degrades_png_without_matplotlib(
    tmp_path, monkeypatch
) -> None:
    from analytics import export_helpers
    from analytics.capital_risk_layer_v14 import build_capital_risk_report_from_trials

    monkeypatch.setattr(export_helpers.ChartGenerator, "_get_plt", lambda self: None)
    rep = build_capital_risk_report_from_trials(
        _synthetic_trials(), tmp_path, risk_config=_risk_cfg(), scenario="x"
    )
    assert rep.snapshot["rows"] and rep.tail_report is not None
    assert not rep.npv_distribution_png.exists()  # PNG degraded, report still built


def test_from_mc_result_needs_risk_config_or_config_path(tmp_path) -> None:
    from analytics.capital_risk_layer_v14 import (
        build_capital_risk_report_from_mc_result,
    )
    from analytics.contracts_v14 import MonteCarloResult

    result = MonteCarloResult(
        trials={k: list(v) for k, v in _synthetic_trials().items()}
    )
    with pytest.raises(ValueError, match="risk_config or a config_path"):
        build_capital_risk_report_from_mc_result(result, tmp_path)


def test_from_mc_result_from_synthetic_result(tmp_path) -> None:
    pytest.importorskip("matplotlib")
    from analytics.capital_risk_layer_v14 import (
        build_capital_risk_report_from_mc_result,
    )
    from analytics.contracts_v14 import MonteCarloResult

    result = MonteCarloResult(
        trials={k: list(v) for k, v in _synthetic_trials(50).items()}
    )
    rep = build_capital_risk_report_from_mc_result(
        result, tmp_path, risk_config=_risk_cfg()
    )
    assert rep.n_trials == 50 and rep.npv_distribution_png.exists()
    assert rep.tail_report.covenant_breaches.dscr_breach_probability == pytest.approx(
        0.0
    )


@pytest.mark.slow
def test_canonical_mc_end_to_end_feeds_capital_risk_report(tmp_path) -> None:
    # The production path: the CANONICAL MonteCarloEngine (LHS + Iman-Conover correlation,
    # reading the scenario's monte_carlo.parameters) -> MonteCarloResult.trials -> the unified
    # capital-risk report. Proves the driver spec is fed from config, not a toy Gaussian MC.
    pytest.importorskip("matplotlib")
    from omegaconf import OmegaConf

    from analytics.capital_risk_layer_v14 import (
        DRIVER_MC_TRIAL_METRICS,
        build_capital_risk_report_from_mc_result,
    )
    from analytics.contracts_v14 import MonteCarloResult
    from analytics.mc.engine import MonteCarloEngine

    cfg = OmegaConf.load(LENDER_CONFIG)
    result = MonteCarloEngine(cfg, seed=42).run(n_trials=30)
    assert isinstance(result, MonteCarloResult)
    assert set(DRIVER_MC_TRIAL_METRICS).issubset(result.trials)
    # the healthy lender path uses no toy fallbacks — lock that so a fully-toy regression
    # (fabricated KPIs with the same 7 keys) can't pass this test silently (#716 F1/F6).
    assert result.metadata.get("toy_fallback_count", 0) == 0

    rep = build_capital_risk_report_from_mc_result(
        result, tmp_path, config_path=LENDER_CONFIG
    )
    assert rep.n_trials == 30 and rep.npv_distribution_png.exists()
    # F5-01 removes the former one-year fold gap in the deterministic case. The
    # seeded MC still records genuine driver-stressed DSCR breaches: 24 of the 30
    # canonical trials fall below the authored 1.30 covenant. LLCR remains clear.
    cb = rep.tail_report.covenant_breaches
    assert cb.dscr_breach_probability == pytest.approx(0.8)
    assert cb.llcr_breach_probability == pytest.approx(0.0)


def test_build_from_trials_requires_min_trials(tmp_path) -> None:
    # F2/F3: an n=1 (or n=0) MC must fail loud, not crash inside VaR/CVaR with IndexError.
    from analytics.capital_risk_layer_v14 import build_capital_risk_report_from_trials

    for n in (0, 1, 5):
        trials = {k: list(v)[:n] for k, v in _synthetic_trials(60).items()}
        with pytest.raises(ValueError, match="stable VaR/CVaR tail"):
            build_capital_risk_report_from_trials(
                trials, tmp_path, risk_config=_risk_cfg(), scenario="x"
            )


def test_from_mc_result_refuses_toy_fallback_contamination(tmp_path) -> None:
    # F1: a MonteCarloResult carrying toy-fallback trials (fabricated KPIs) must be refused,
    # not silently fed into the lender covenant-breach / VaR-CVaR / NPV numbers.
    from analytics.capital_risk_layer_v14 import (
        build_capital_risk_report_from_mc_result,
    )
    from analytics.contracts_v14 import MonteCarloResult

    result = MonteCarloResult(
        trials={k: list(v) for k, v in _synthetic_trials(50).items()},
        metadata={"toy_fallback_count": 3},
    )
    with pytest.raises(ValueError, match="toy-fallback"):
        build_capital_risk_report_from_mc_result(
            result, tmp_path, risk_config=_risk_cfg()
        )


def test_snapshot_dscr_floor_matches_config_first_covenant(tmp_path) -> None:
    # F7: the snapshot (slice 1) DSCR floor must be the config-first covenant, not a hardcoded
    # 1.30 default — one report never shows two different DSCR floors.
    from analytics.capital_risk_layer_v14 import build_capital_risk_report_from_trials
    from analytics.core.risk_metrics import RiskConfig

    rc = RiskConfig(
        confidence_level=0.95,
        target_return=0.0,
        min_dscr=1.20,
        min_llcr=1.0,
        min_plcr=1.0,
    )
    rep = build_capital_risk_report_from_trials(
        _synthetic_trials(60), tmp_path, risk_config=rc, scenario="x"
    )
    dscr_row = {r["metric"]: r for r in rep.snapshot["rows"]}["dscr_min"]
    assert dscr_row["dscr_floor"] == pytest.approx(1.20)
