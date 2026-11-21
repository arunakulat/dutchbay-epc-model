"""Monte Carlo trial-path guards: the pre-sampling dry run (#1629) and the opt-in
breakdown reconciliation (#1762).

The engine merges the base config with each parameter's low and high bound and runs the
trial path's own config checks (strict pre-flight and CAPEX resolution) before sampling.
A sweep those checks refuse is refused up front, with the parameter and bound named,
instead of failing trial by trial. A ``capex.usd_total`` sweep on a scenario that derives
CAPEX from its breakdown can opt in to ``reconcile_breakdown: pro_rata``, which scales
every breakdown line with the sampled total so the trial path's cross-check holds. The
committed 5 US-cent variant declares it on its CAPEX sweep (#1762). Offline: committed
scenarios only. No figure is asserted.
"""

from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Any, Dict, Iterator, List, cast

import pytest
import yaml

import analytics.mc.engine as mc_engine
from analytics.mc.engine import (
    MonteCarloConfigError,
    MonteCarloEngine,
    run_monte_carlo_analysis,
)

_SCENARIOS = Path(__file__).resolve().parents[2] / "scenarios"
_FIVE_US_CENT = _SCENARIOS / "dutchbay_lendercase_5usc_fixed_lkr.yaml"
_LENDER = _SCENARIOS / "dutchbay_lendercase_2025Q4.yaml"


@pytest.fixture(autouse=True)
def _quiet() -> Iterator[None]:
    logging.disable(logging.WARNING)
    yield
    logging.disable(logging.NOTSET)


def _load(path: Path) -> Dict[str, Any]:
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(cfg, dict)
    return cast(Dict[str, Any], copy.deepcopy(cfg))


def _capex_param(cfg: Dict[str, Any]) -> Dict[str, Any]:
    (param,) = [
        p for p in cfg["monte_carlo"]["parameters"] if p["name"] == "capex.usd_total"
    ]
    return cast(Dict[str, Any], param)


def _reconciled() -> Dict[str, Any]:
    """The 5 US-cent variant with ``reconcile_breakdown: pro_rata`` set on a copy."""
    cfg = _load(_FIVE_US_CENT)
    _capex_param(cfg)["reconcile_breakdown"] = "pro_rata"
    return cfg


# ── #1762: the 5 US-cent variant ────────────────────────────────────────────────


def test_five_us_cent_capex_sweep_declares_the_breakdown_reconciliation() -> None:
    cfg = _load(_FIVE_US_CENT)
    assert cfg["capex"]["derive_from_breakdown"] is True
    assert _capex_param(cfg)["reconcile_breakdown"] == "pro_rata"


def test_five_us_cent_tariff_band_is_centred_on_its_own_tariff() -> None:
    """The variant's tariff sweep spans its own base, not the canonical case's.

    It once carried the canonical lender case's band, centred about 22% above this
    variant's tariff, so its trials sampled almost only upside.
    """
    cfg = _load(_FIVE_US_CENT)
    (param,) = [
        p for p in cfg["monte_carlo"]["parameters"] if p["name"] == "tariff.lkr_per_kwh"
    ]
    base = float(cfg["tariff"]["lkr_per_kwh"])
    low, high = float(param["low"]), float(param["high"])
    assert (low + high) / 2 == pytest.approx(base, rel=1e-9)
    assert low < base < high


def test_without_the_reconciliation_the_sweep_is_refused_before_sampling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Negative control: without the declaration the engine refuses the sweep before any
    trial runs, and says how to fix it."""
    cfg = _load(_FIVE_US_CENT)
    del _capex_param(cfg)["reconcile_breakdown"]

    def _no_trial(*_a: Any, **_k: Any) -> Any:
        raise AssertionError("a trial ran before the refusal")

    monkeypatch.setattr(mc_engine, "evaluate_with_overrides", _no_trial)
    with pytest.raises(MonteCarloConfigError) as err:
        MonteCarloEngine(cfg)
    message = str(err.value)
    assert "'capex.usd_total'" in message
    assert "#1629" in message
    assert "low" in message and "high" in message
    assert "reconcile_breakdown: pro_rata" in message


def test_each_trial_scales_the_breakdown_to_the_sampled_total(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = _reconciled()
    base_lines = cfg["capex"]["breakdown"]
    seen: List[Dict[str, Any]] = []
    real = mc_engine.evaluate_with_overrides

    def _spy(*args: Any, **kwargs: Any) -> Any:
        if kwargs.get("overrides"):
            seen.append(copy.deepcopy(kwargs["overrides"]))
        return real(*args, **kwargs)

    monkeypatch.setattr(mc_engine, "evaluate_with_overrides", _spy)
    cfg["monte_carlo"]["fixed_debt_stress"] = False
    result = run_monte_carlo_analysis(base_config=cfg, n_trials=3, seed=11)

    assert result.failed_iterations == 0
    assert result.metadata["toy_fallback_count"] == 0
    assert len(seen) == 3
    for overrides in seen:
        capex = overrides["capex"]
        lines = capex["breakdown"]
        assert set(lines) == set(base_lines)
        assert sum(lines.values()) == pytest.approx(capex["usd_total"], rel=1e-12)
        ratios = {k: lines[k] / base_lines[k] for k in base_lines}
        assert max(ratios.values()) == pytest.approx(min(ratios.values()), rel=1e-12)


def test_the_reconciled_capex_lever_moves_the_outputs() -> None:
    """Not a dead lever: sweeping only CAPEX spreads the project NPV."""
    cfg = _reconciled()
    cfg["monte_carlo"]["parameters"] = [_capex_param(cfg)]
    cfg["monte_carlo"]["fixed_debt_stress"] = False
    result = run_monte_carlo_analysis(base_config=cfg, n_trials=4, seed=3)
    assert result.failed_iterations == 0
    assert result.metadata["degenerate_sweep"] is False
    assert result.metadata["dead_param_names"] == []
    npv = [v for v in result.trials["project_npv"] if v is not None]
    assert max(npv) > min(npv)


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (
            lambda c: _capex_param(c).__setitem__("reconcile_breakdown", "scale"),
            "must be 'pro_rata'",
        ),
        (
            lambda c: c["monte_carlo"]["parameters"][0].__setitem__(
                "reconcile_breakdown", "pro_rata"
            ),
            "capex.usd_total only",
        ),
        (
            lambda c: c["capex"].__setitem__("derive_from_breakdown", False),
            "needs capex.derive_from_breakdown",
        ),
        (
            lambda c: c["capex"].__setitem__("contingency", {"method": "qra"}),
            "QRA contingency",
        ),
        (
            lambda c: c["capex"].__setitem__(
                "breakdown", {k: 0.0 for k in c["capex"]["breakdown"]}
            ),
            "positive total",
        ),
    ],
    ids=["unknown-mode", "wrong-parameter", "no-derive", "qra", "empty-breakdown"],
)
def test_reconcile_breakdown_is_refused_where_it_would_not_mean_pro_rata(
    mutate: Any, match: str
) -> None:
    cfg = _reconciled()
    mutate(cfg)
    with pytest.raises(MonteCarloConfigError, match=match):
        MonteCarloEngine(cfg)


# ── #1629: the dry run ──────────────────────────────────────────────────────────


def test_bare_capex_sweep_on_a_usd_scenario_is_refused_before_sampling() -> None:
    """#1629 item 2: a bare ``capex`` override replaces the whole capex mapping, so the
    strict pre-flight refuses every trial. The dry run refuses it up front."""
    cfg = _load(_LENDER)
    cfg["monte_carlo"]["parameters"] = [{"name": "capex", "low": 1.0, "high": 2.0}]
    cfg["monte_carlo"].pop("correlation", None)
    with pytest.raises(MonteCarloConfigError, match=r"'capex'.*#1629"):
        MonteCarloEngine(cfg)


def test_a_bound_that_fails_alone_is_named() -> None:
    """A sweep refused at one bound only is still refused: the trials near it fail."""
    cfg = _load(_FIVE_US_CENT)
    param = _capex_param(cfg)
    param.pop("reconcile_breakdown", None)  # independent of the scenario's declaration
    base_total = float(cfg["capex"]["usd_total"])
    param["low"], param["high"] = base_total, base_total * 1.5
    cfg["monte_carlo"]["parameters"] = [param]
    with pytest.raises(MonteCarloConfigError) as err:
        MonteCarloEngine(cfg)
    failures = str(err.value).split("(#1629). ", 1)[1]
    assert failures.startswith("high ")
    assert "; low " not in failures


def test_a_config_whose_base_does_not_resolve_is_left_to_the_trials() -> None:
    """A minimal smoke config has no CAPEX the trial path recognises; the dry run stands
    aside, so the toy-fallback smoke path behaves exactly as before."""
    cfg = {
        "monte_carlo": {
            "parameters": [{"name": "capex.usd_total", "low": 90.0, "high": 110.0}],
            # Off by default since #962: this smoke config opts in to the toy path.
            "allow_toy_fallback": True,
        }
    }
    engine = MonteCarloEngine(cfg)
    result = engine.run(n_trials=2)
    assert result.metadata["toy_fallback_count"] == 2


def test_census_the_dry_run_refuses_no_committed_scenario() -> None:
    """Census: the dry run refuses no committed Monte Carlo scenario, now that the 5
    US-cent variant declares its reconciliation. Mapping-form ``monte_carlo.parameters``
    blocks are refused by the existing schema check, as on main, and are out of scope.
    """
    checked = 0
    refused = []
    for path in sorted(_SCENARIOS.rglob("*.yaml")):
        try:
            cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue
        mc = cfg.get("monte_carlo") if isinstance(cfg, dict) else None
        if not isinstance(mc, dict) or not isinstance(mc.get("parameters"), list):
            continue
        try:
            MonteCarloEngine(cfg)
        except MonteCarloConfigError as exc:
            assert "#1629" in str(exc)
            refused.append(path.name)
        checked += 1
    assert checked >= 17
    assert refused == []
