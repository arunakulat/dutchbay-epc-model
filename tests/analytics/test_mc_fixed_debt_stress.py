"""Fixed-debt covenant-stress MC mode (capability/provenance audit HIGH #4).

The per-trial pipeline re-sizes debt by DSCR sculpting, so every trial's min_dscr is pinned
at the covenant target and the modelled breach probability is structurally ZERO. The opt-in
`monte_carlo.fixed_debt_stress` mode sizes debt once on the base (financial-close) schedule
and tests each trial's CFADS against that committed service, yielding a real breach
distribution. Offline (uses the committed scenario), so CI never touches the network.
"""

from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Any, cast

import numpy as np
import pytest
import yaml

import analytics.mc.engine as mc_engine
from analytics.mc.engine import _trial_fixed_debt_min_dscr

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCENARIO = _REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"
_PIN_UNIT = np.array([1.2999999999999996, 1.2999999999999998, 1.3, 1.3000000000000003])


def _rows(cfads: list[float], first_period: int = 3) -> list[dict[str, float]]:
    return [
        {
            "annual_row_index": i,
            "year": float(i + 1),
            "debt_period": first_period + i,
            "cfads_usd": v,
        }
        for i, v in enumerate(cfads)
    ]


# Synthetic base: 2 construction periods, a half-year bridge at period 2 (maps to no row),
# then operating rows at periods 3, 4, 5. Service 50 on the bridge and 100 a year; fee 10.
_BASE = {
    "annual_row_debt_period_map": _rows([300.0, 300.0, 300.0]),
    "debt_service_total": [0.0, 0.0, 50.0, 100.0, 100.0, 100.0],
    "senior_fee_usd": [0.0, 0.0, 0.0, 10.0, 10.0, 10.0],
    "bridge_debt_period": 2,
}


def test_helper_tests_trial_cfads_on_the_covenant_fold_basis() -> None:
    """#1728: year 1 carries the bridge service, as ``dscr_by_year`` does."""
    trial = {"annual_row_debt_period_map": _rows([160.0, 400.0, 400.0])}
    # year 1: (160 - 10) / (100 + 50) = 1.0; years 2-3: (400 - 10) / 100 = 3.9
    assert _trial_fixed_debt_min_dscr(_BASE, trial) == pytest.approx(1.0)
    # Without the fold, year 1 would read (160 - 10) / 100 = 1.5 and never bind.
    orphaned = {**_BASE, "bridge_debt_period": None}
    assert _trial_fixed_debt_min_dscr(orphaned, trial) is None
    unfolded = {**orphaned, "debt_service_total": [0.0, 0.0, 0.0, 100.0, 100.0, 100.0]}
    assert _trial_fixed_debt_min_dscr(unfolded, trial) == pytest.approx(1.5)


def test_helper_charges_the_committed_fee_and_ignores_the_trial_debt() -> None:
    """#1728 L-1: the fee is the base (committed-debt) fee. Nothing the trial derived
    from its own re-sized debt moves the result, including the deprecated alias."""
    trial = {"annual_row_debt_period_map": _rows([300.0, 300.0, 120.0])}
    expected = (120.0 - 10.0) / 100.0
    assert _trial_fixed_debt_min_dscr(_BASE, trial) == pytest.approx(expected)
    noisy = {
        **trial,
        "senior_fee_usd": [0.0, 0.0, 0.0, 99.0, 99.0, 99.0],
        "debt_service_total": [0.0, 0.0, 1.0, 1.0, 1.0, 1.0],
        "raw_dscr_series": [None, None, 9.0, 9.0, 9.0, 9.0],
        "dscr_series": [None, None, 9.0, 9.0, 9.0, 9.0],
    }
    assert _trial_fixed_debt_min_dscr(_BASE, noisy) == pytest.approx(expected)


def test_helper_skips_rows_with_no_committed_service() -> None:
    """A row whose base period carries no service is not a covenant observation."""
    base = {**_BASE, "debt_service_total": [0.0, 0.0, 50.0, 100.0, 100.0, 0.0]}
    trial = {"annual_row_debt_period_map": _rows([300.0, 300.0, -50.0])}
    assert _trial_fixed_debt_min_dscr(base, trial) == pytest.approx(
        (300.0 - 10.0) / 150.0
    )


@pytest.mark.parametrize(
    ("base", "trial"),
    [
        ({**_BASE, "debt_service_total": [0.0] * 6}, _BASE),
        ({}, _BASE),
        (_BASE, {}),
        (_BASE, {"annual_row_debt_period_map": [{"annual_row_index": 0}]}),
    ],
    ids=["no-base-service", "no-base", "no-trial-rows", "trial-rows-without-cfads"],
)
def test_helper_returns_none_without_an_observation(
    base: dict[str, object], trial: dict[str, object]
) -> None:
    assert _trial_fixed_debt_min_dscr(base, trial) is None


def test_trial_equal_to_base_reproduces_the_covenant_minimum() -> None:
    """Acceptance (#1728): with trial = base the stress reads the base ``dscr_by_year``
    minimum exactly, on the lender case."""
    from analytics.evaluation_v14 import evaluate_with_overrides

    logging.disable(logging.WARNING)
    try:
        full = evaluate_with_overrides(
            raw_config=_cfg(fixed_debt=True), overrides={}, return_full_result=True
        )
    finally:
        logging.disable(logging.NOTSET)
    assert isinstance(full, dict)
    debt = cast(dict[str, Any], full["debt_result"])
    covenant_min = min(v for v in debt["dscr_by_year"].values() if v is not None)
    assert _trial_fixed_debt_min_dscr(debt, debt) == covenant_min


def _cfg(fixed_debt: bool) -> dict[str, Any]:
    cfg = copy.deepcopy(yaml.safe_load(_SCENARIO.read_text()))
    # The lender case turns the stress on (#962 item 4); "off" is set explicitly here.
    cfg["monte_carlo"]["fixed_debt_stress"] = fixed_debt
    if fixed_debt:
        cfg["monte_carlo"]["allow_toy_fallback"] = False
    return cast(dict[str, Any], cfg)


class TestEngineFixedDebt:
    @pytest.mark.parametrize(
        ("controlled_dscr", "expected_probability"),
        [
            (np.tile(_PIN_UNIT, 2), 0.0),
            (np.concatenate([np.tile(_PIN_UNIT, 2), [1.10]]), 1.0 / 9.0),
        ],
        ids=["floor-pin-noise", "genuine-breach"],
    )
    def test_breach_probability_uses_shared_noise_tolerant_primitive(
        self,
        monkeypatch: pytest.MonkeyPatch,
        controlled_dscr: np.ndarray,
        expected_probability: float,
    ) -> None:
        # The first call checks the base itself (trial = base); then one per trial.
        values = iter([1.5, *controlled_dscr.tolist()])
        monkeypatch.setattr(
            mc_engine,
            "_trial_fixed_debt_min_dscr",
            lambda *_args, **_kwargs: next(values),
        )

        logging.disable(logging.WARNING)
        try:
            result = mc_engine.MonteCarloEngine(_cfg(fixed_debt=True), seed=725).run(
                n_trials=controlled_dscr.size
            )
        finally:
            logging.disable(logging.NOTSET)

        fixed = result.metadata["fixed_debt_stress"]
        assert fixed["status"] == "ok"
        assert fixed["basis"] == "dscr_by_year"
        assert fixed["n"] == controlled_dscr.size
        assert fixed["breach_probability"] == pytest.approx(expected_probability)

    def test_off_by_default_is_byte_identical_shape(self) -> None:
        logging.disable(logging.WARNING)
        try:
            from analytics.mc.engine import MonteCarloEngine

            res = MonteCarloEngine(_cfg(fixed_debt=False), seed=123).run(n_trials=24)
            assert "fixed_debt_stress" not in res.metadata  # opt-in: no key when off
        finally:
            logging.disable(logging.NOTSET)

    def test_on_surfaces_real_breach_distribution(self) -> None:
        logging.disable(logging.WARNING)
        try:
            from analytics.mc.engine import MonteCarloEngine

            res = MonteCarloEngine(_cfg(fixed_debt=True), seed=123).run(n_trials=48)
            fds = res.metadata.get("fixed_debt_stress")
            assert fds is not None
            assert fds["n"] > 0
            assert 0.0 <= fds["breach_probability"] <= 1.0
            assert fds["min_dscr_p10"] <= fds["min_dscr_p50"] <= fds["min_dscr_p90"]
            # the WHOLE POINT: fixed-debt DSCR is NOT a point mass (re-sized min_dscr is ~1.30
            # every trial; fixed-debt spreads as CFADS is shocked) -> a real distribution.
            assert fds["min_dscr_max"] - fds["min_dscr_min"] > 0.01
            assert fds["covenant"] > 0.0
        finally:
            logging.disable(logging.NOTSET)

    def test_reproducible(self) -> None:
        logging.disable(logging.WARNING)
        try:
            from analytics.mc.engine import MonteCarloEngine

            a = MonteCarloEngine(_cfg(fixed_debt=True), seed=7).run(n_trials=24)
            b = MonteCarloEngine(_cfg(fixed_debt=True), seed=7).run(n_trials=24)
            assert a.metadata["fixed_debt_stress"][
                "breach_probability"
            ] == pytest.approx(b.metadata["fixed_debt_stress"]["breach_probability"])
        finally:
            logging.disable(logging.NOTSET)


class TestFailLoud:
    """#1728: the stress is ruled on for lender runs, so a missing result there raises."""

    def test_lender_posture_raises_when_the_base_has_no_covenant(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(mc_engine, "_trial_fixed_debt_min_dscr", lambda *_a: None)
        logging.disable(logging.WARNING)
        try:
            with pytest.raises(
                RuntimeError, match="fixed_debt_stress is on.*base case"
            ):
                mc_engine.MonteCarloEngine(_cfg(fixed_debt=True), seed=1).run(
                    n_trials=2
                )
        finally:
            logging.disable(logging.NOTSET)

    def test_lender_posture_raises_when_a_trial_has_no_observation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        values = iter([1.5, 1.4, None])
        monkeypatch.setattr(
            mc_engine, "_trial_fixed_debt_min_dscr", lambda *_a: next(values)
        )
        logging.disable(logging.WARNING)
        try:
            with pytest.raises(
                RuntimeError, match="MC trial 1 published no CFADS"
            ) as err:
                mc_engine.MonteCarloEngine(_cfg(fixed_debt=True), seed=1).run(
                    n_trials=2
                )
        finally:
            logging.disable(logging.NOTSET)
        # Raised by the stress check itself, not re-wrapped as a failed trial evaluation.
        assert "toy-metric fallback" not in str(err.value)

    def test_the_stress_check_sits_outside_the_trial_fail_soft_handler(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An error in the stress check propagates even on a permissive run: it is never
        caught by the trial's handler and turned into a toy trial."""
        calls = iter([1.5])

        def _helper(*_a: object) -> float:
            try:
                return next(calls)  # the base check
            except StopIteration:
                raise ValueError("stress check failed") from None

        monkeypatch.setattr(mc_engine, "_trial_fixed_debt_min_dscr", _helper)
        cfg = _cfg(fixed_debt=True)
        cfg["monte_carlo"]["allow_toy_fallback"] = True
        logging.disable(logging.WARNING)
        try:
            with pytest.raises(ValueError, match="stress check failed"):
                mc_engine.MonteCarloEngine(cfg, seed=1).run(n_trials=2)
        finally:
            logging.disable(logging.NOTSET)

    def test_permissive_run_with_one_failed_trial_withholds_the_stress(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A missing stress observation makes the full stress result unavailable."""
        real = mc_engine.evaluate_with_overrides
        trial_calls = {"n": 0}

        def _evaluate(*args: Any, **kwargs: Any) -> Any:
            if kwargs.get("overrides"):
                trial_calls["n"] += 1
                if trial_calls["n"] == 2:
                    raise RuntimeError("simulated trial failure")
            return real(*args, **kwargs)

        monkeypatch.setattr(mc_engine, "evaluate_with_overrides", _evaluate)
        cfg = _cfg(fixed_debt=True)
        cfg["monte_carlo"]["allow_toy_fallback"] = True
        logging.disable(logging.WARNING)
        try:
            result = mc_engine.MonteCarloEngine(cfg, seed=1).run(n_trials=3)
        finally:
            logging.disable(logging.NOTSET)
        assert result.metadata["toy_fallback_count"] == 1
        fixed = result.metadata["fixed_debt_stress"]
        assert fixed["status"] == "unavailable"
        assert fixed["n"] == 2
        assert fixed["n_requested"] == 3
        assert "breach_probability" not in fixed

    def test_permissive_run_records_why_the_stress_is_missing(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.setattr(mc_engine, "_trial_fixed_debt_min_dscr", lambda *_a: None)
        cfg = _cfg(fixed_debt=True)
        cfg["monte_carlo"]["allow_toy_fallback"] = True
        with caplog.at_level(logging.WARNING, logger="analytics.mc.engine"):
            result = mc_engine.MonteCarloEngine(cfg, seed=1).run(n_trials=2)
        fixed = result.metadata["fixed_debt_stress"]
        assert fixed["status"] == "unavailable"
        assert "base case" in fixed["reason"]
        assert any("fixed_debt_stress is on" in r.getMessage() for r in caplog.records)


def test_strict_engine_rejects_incomplete_covenant_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = copy.deepcopy(_BASE)
    incomplete = copy.deepcopy(_BASE)
    del cast(list[Any], incomplete["annual_row_debt_period_map"])[1]
    calls = iter([{"debt_result": base}, {"kpis": {}, "debt_result": incomplete}])
    monkeypatch.setattr(
        mc_engine, "evaluate_with_overrides", lambda *a, **k: next(calls)
    )
    with pytest.raises(RuntimeError, match="MC trial 0 published no CFADS"):
        mc_engine.MonteCarloEngine(_cfg(fixed_debt=True), seed=1).run(n_trials=2)
