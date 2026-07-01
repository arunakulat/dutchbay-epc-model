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

import pytest
import yaml

from analytics.mc.engine import _trial_fixed_debt_min_dscr

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCENARIO = _REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"


def test_fixed_debt_min_dscr_helper_recovers_cfads() -> None:
    # base committed service: 2 construction zeros + 3 operating periods of 100
    base_ds = [0.0, 0.0, 100.0, 100.0, 100.0]
    # a trial that re-sized debt to 90/yr; its raw DSCR is cfads/90
    trial = {
        "raw_dscr_series": [0.0, 0.0, 1.3, 1.3, 1.0],
        "debt_service_total": [0.0, 0.0, 90.0, 90.0, 90.0],
    }
    # actual cfads = raw*ds = [117,117,90]; fixed dscr vs base 100 = [1.17,1.17,0.90] -> min 0.90
    assert _trial_fixed_debt_min_dscr(base_ds, trial) == pytest.approx(0.90)


def test_fixed_debt_min_dscr_helper_no_operating_periods() -> None:
    assert (
        _trial_fixed_debt_min_dscr(
            [0.0, 0.0], {"raw_dscr_series": [], "debt_service_total": []}
        )
        is None
    )


def _cfg(fixed_debt: bool):
    cfg = copy.deepcopy(yaml.safe_load(_SCENARIO.read_text()))
    if fixed_debt:
        cfg["monte_carlo"]["fixed_debt_stress"] = True
    return cfg


class TestEngineFixedDebt:
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
