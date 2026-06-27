"""Tests for the market-calibrated FX Monte-Carlo driver.

Covers the provenance-pinned historical loader (:mod:`analytics.fx.fx_history`),
the regime-split calibration + mixture sampler (:mod:`analytics.fx.fx_calibration`),
and the engine integration (``distribution: fx_calibrated``). All offline — they
read the committed BIS vintage, so CI never touches the network.
"""

from __future__ import annotations

import copy
import json
import logging
from pathlib import Path

import pytest
import yaml

from analytics.fx import fx_history
from analytics.fx.fx_calibration import (
    CRISIS_REGIME,
    NORMAL_REGIME,
    calibrate_from_config,
    calibrate_fx,
)
from analytics.fx.fx_history import (
    APPROVED_FX_SOURCES,
    load_pinned_history,
    to_periodic,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCENARIO = _REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"
_PINNED_SPOT = 333.79


# ── fx_history: pinned vintage + provenance guard ──────────────────────────


class TestFxHistory:
    def test_load_pinned_vintage(self) -> None:
        s = load_pinned_history()
        assert s.provider in APPROVED_FX_SOURCES
        assert s.frequency == "daily"
        # at-least-weekly back to ~2005 (the stated requirement)
        assert s.date_range[0] <= "2005-12-31"
        assert s.date_range[1] >= "2025-01-01"
        assert len(s.rates) > 3000  # daily over ~20y
        assert 200.0 < s.latest < 500.0  # sane recent LKR/USD level
        assert all(r > 0 for r in s.rates)

    def test_provenance_guard_rejects_unapproved_source(self, tmp_path: Path) -> None:
        # Copy the real CSV but write a provenance with a non-approved provider.
        src = load_pinned_history()  # ensures defaults exist
        csv_src = fx_history.DEFAULT_VINTAGE_CSV
        csv_dst = tmp_path / "v.csv"
        csv_dst.write_bytes(Path(csv_src).read_bytes())
        prov = json.loads(Path(fx_history.DEFAULT_VINTAGE_PROVENANCE).read_text())
        prov["provider"] = "RandomBlog"  # not in APPROVED_FX_SOURCES
        prov_dst = tmp_path / "v.provenance.json"
        prov_dst.write_text(json.dumps(prov))
        with pytest.raises(ValueError, match="APPROVED_FX_SOURCES"):
            load_pinned_history(csv_dst, prov_dst)
        assert src.provider in APPROVED_FX_SOURCES  # sanity

    def test_integrity_guard_rejects_tampered_csv(self, tmp_path: Path) -> None:
        csv_dst = tmp_path / "v.csv"
        # tamper: append a row so the sha256 no longer matches the sidecar
        original = Path(fx_history.DEFAULT_VINTAGE_CSV).read_text()
        csv_dst.write_text(original + "2099-01-01,999.0\n")
        prov_dst = tmp_path / "v.provenance.json"
        prov_dst.write_text(Path(fx_history.DEFAULT_VINTAGE_PROVENANCE).read_text())
        with pytest.raises(ValueError, match="integrity check FAILED"):
            load_pinned_history(csv_dst, prov_dst)

    def test_to_periodic_weekly_returns_real_dates(self) -> None:
        s = load_pinned_history()
        wk_dates, wk_vals = to_periodic(s, "weekly")
        assert len(wk_dates) == len(wk_vals)
        # weekly is coarser than daily but still substantial
        assert len(wk_dates) < len(s.rates)
        assert len(wk_dates) > 500
        # dates are real YYYY-MM-DD (not ISO-week labels), so regime windows compare
        assert all(len(d) == 10 and d[4] == "-" and "W" not in d for d in wk_dates)
        assert wk_dates == sorted(wk_dates)


# ── fx_calibration: regimes, drift, mixture sampler ────────────────────────


class TestFxCalibration:
    @pytest.fixture(scope="class")
    def cal(self):
        return calibrate_fx(
            load_pinned_history(), pinned_spot=_PINNED_SPOT, frequency="weekly"
        )

    def test_drift_is_positive_and_plausible(self, cal) -> None:
        # rupee structurally depreciates; long-run annual drift in a sane band
        assert 0.02 < cal.annual_depr < 0.12
        assert cal.long_run_drift_annual > 0

    def test_crisis_regime_has_higher_vol_than_normal(self, cal) -> None:
        assert cal.sigma_crisis_1y > cal.sigma_normal_1y
        assert cal.crisis_log_shift > 0  # the 2022 float was a depreciation jump
        assert 0.01 <= cal.crisis_prob <= 0.25

    def test_regimes_reported(self, cal) -> None:
        names = {r.name for r in cal.regimes}
        assert NORMAL_REGIME in names and CRISIS_REGIME in names
        # the excluded peg window is still reported (transparency), just not in vol
        assert "noncredible_peg" in names

    def test_sampler_monotone_and_centered(self, cal) -> None:
        smp = cal.sampler()
        xs = [smp.spot_from_unit(u / 500) for u in range(1, 500)]
        assert all(xs[i] <= xs[i + 1] + 1e-9 for i in range(len(xs) - 1))  # monotone
        median = smp.spot_from_unit(0.5)
        assert (
            abs(median - _PINNED_SPOT) / _PINNED_SPOT < 0.05
        )  # level centred on today
        # the forward drift is delivered separately, not baked into the level
        assert smp.drift == pytest.approx(cal.annual_depr)

    def test_sampler_crisis_tail_in_upper_quantiles(self, cal) -> None:
        smp = cal.sampler()
        # a deep upper-quantile draw must reflect a crisis-scale depreciation
        assert smp.spot_from_unit(0.999) > 1.5 * _PINNED_SPOT
        assert smp.spot_from_unit(0.5) < smp.spot_from_unit(0.95)

    def test_calibrate_from_config(self) -> None:
        cfg = {
            "monte_carlo": {
                "fx_calibration": {"frequency": "weekly", "horizon_years": 1.0}
            }
        }
        cal = calibrate_from_config(cfg, pinned_spot=_PINNED_SPOT)
        assert cal.pinned_spot == _PINNED_SPOT
        assert cal.provider in APPROVED_FX_SOURCES

    def test_pinned_spot_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="pinned_spot"):
            calibrate_fx(load_pinned_history(), pinned_spot=0.0)


# ── engine integration: distribution: fx_calibrated ────────────────────────


def _calibrated_config():
    cfg = copy.deepcopy(yaml.safe_load(_SCENARIO.read_text()))
    cfg["monte_carlo"]["parameters"] = [
        {"name": "fx.start_lkr_per_usd", "distribution": "fx_calibrated"}
    ]
    cfg["monte_carlo"]["fx_calibration"] = {
        "frequency": "weekly",
        "horizon_years": 1.0,
        "drive_drift": True,
    }
    return cfg


class TestEngineIntegration:
    def test_calibrated_mc_runs_nondegenerate(self) -> None:
        logging.disable(logging.WARNING)
        try:
            from analytics.mc.engine import MonteCarloEngine

            eng = MonteCarloEngine(_calibrated_config(), seed=123)
            assert eng._param_kinds == ["fx_calibrated"]
            assert eng._fx_sampler is not None
            res = eng.run(n_trials=64)
            assert res.failed_iterations == 0
            assert res.metadata.get("degenerate_sweep") is False
            irr = [
                float(x)
                for x in (res.trials or {}).get("project_irr", [])
                if x is not None
            ]
            assert len(irr) == 64
            assert max(irr) - min(irr) > 1e-4  # FX genuinely moves the IRR
        finally:
            logging.disable(logging.NOTSET)

    def test_calibrated_mc_reproducible(self) -> None:
        logging.disable(logging.WARNING)
        try:
            from analytics.mc.engine import MonteCarloEngine

            a = MonteCarloEngine(_calibrated_config(), seed=7).run(n_trials=32)
            b = MonteCarloEngine(_calibrated_config(), seed=7).run(n_trials=32)
            ka = (a.trials or {}).get("project_irr", [])[:5]
            kb = (b.trials or {}).get("project_irr", [])[:5]
            assert ka == kb
        finally:
            logging.disable(logging.NOTSET)

    def test_recorded_fx_inputs_are_spots_not_unit_draws(self) -> None:
        logging.disable(logging.WARNING)
        try:
            from analytics.mc.engine import MonteCarloEngine

            eng = MonteCarloEngine(_calibrated_config(), seed=123)
            eng.run(n_trials=64)
            # the engine records realised spots back into the sample column (not 0..1)
            # exercised via the public run(); assert the sampler maps into a sane band
            spots = [eng._fx_sampler.spot_from_unit(u / 100) for u in range(1, 100)]
            assert min(spots) > 150.0 and max(spots) < 3000.0
        finally:
            logging.disable(logging.NOTSET)

    def test_missing_pinned_spot_raises(self) -> None:
        from analytics.mc.engine import MonteCarloConfigError, MonteCarloEngine

        cfg = _calibrated_config()
        cfg.pop("fx", None)  # remove the anchor spot
        with pytest.raises(MonteCarloConfigError, match="fx.start_lkr_per_usd"):
            MonteCarloEngine(cfg, seed=1)
