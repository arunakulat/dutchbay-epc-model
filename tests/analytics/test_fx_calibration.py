"""Tests for the market-calibrated FX Monte-Carlo driver.

Covers the provenance-pinned historical loader (:mod:`analytics.fx.fx_history`),
the regime-split calibration + mixture sampler (:mod:`analytics.fx.fx_calibration`),
and the engine integration (``distribution: fx_calibrated``). All offline — they
read the committed BIS vintage, so CI never touches the network.
"""

from __future__ import annotations

import copy
import datetime as dt
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


# ── periodic refresh: trailing-window re-pin as-of TODAY (offline) ──────────


def _synthetic_daily_series(
    *, end: str = "2026-06-20", provider: str = "BIS"
) -> fx_history.FXHistorySeries:
    """A monotone monthly synthetic USD/LKR series 2000..end (offline fetcher stand-in)."""
    dates: list[str] = []
    rates: list[float] = []
    rate = 100.0
    for y in range(2000, 2027):
        for m in range(1, 13):
            d = f"{y:04d}-{m:02d}-15"
            if d > end:
                continue
            rate += 1.0
            dates.append(d)
            rates.append(rate)
    return fx_history.FXHistorySeries(
        provider=provider,
        frequency="daily",
        unit="LKR per 1 USD",
        dates=tuple(dates),
        rates=tuple(rates),
        fetched_as_of=end,
        source_endpoint=fx_history.BIS_DAILY_ENDPOINT,
        notes="synthetic test series",
    )


class TestFxRefresh:
    def test_window_start_20y_and_10y(self) -> None:
        as_of = dt.date(2026, 6, 20)
        assert fx_history._window_start(as_of, 20) == dt.date(2006, 6, 20)
        assert fx_history._window_start(as_of, 10) == dt.date(2016, 6, 20)

    def test_window_start_leap_day_clamps(self) -> None:
        # 2024-02-29 minus 20y -> 2004-02-29 (also leap) is fine; minus 1y -> 2023 not leap -> clamp 28
        assert fx_history._window_start(dt.date(2024, 2, 29), 1) == dt.date(2023, 2, 28)

    def test_window_start_rejects_nonpositive(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            fx_history._window_start(dt.date(2026, 6, 20), 0)

    def test_filter_series_to_window_inclusive(self) -> None:
        s = _synthetic_daily_series()
        w = fx_history.filter_series_to_window(
            s, dt.date(2016, 6, 20), dt.date(2026, 6, 20)
        )
        assert w.date_range[0] >= "2016-06-20"
        assert w.date_range[1] <= "2026-06-20"
        assert len(w.rates) < len(s.rates)
        # roughly a 10y monthly window
        assert 100 < len(w.rates) < 140

    def test_filter_empty_window_raises(self) -> None:
        s = _synthetic_daily_series()
        with pytest.raises(ValueError, match="empty vintage"):
            fx_history.filter_series_to_window(
                s, dt.date(2030, 1, 1), dt.date(2031, 1, 1)
            )

    def test_dry_run_writes_nothing(self, tmp_path: Path) -> None:
        csv_p = tmp_path / "v.csv"
        prov_p = tmp_path / "v.provenance.json"
        summary = fx_history.refresh_pinned_vintage(
            window_years=10,
            as_of=dt.date(2026, 6, 20),
            csv_path=csv_p,
            provenance_path=prov_p,
            fetcher=_synthetic_daily_series,
            dry_run=True,
        )
        assert summary["written"] is False
        assert summary["window_years"] == 10
        assert summary["window_start"] == "2016-06-20"
        assert summary["fetched_as_of"] == "2026-06-20"
        assert summary["date_range"][0] >= "2016-06-20"
        assert not csv_p.exists() and not prov_p.exists()

    def test_real_refresh_repins_and_roundtrips(self, tmp_path: Path) -> None:
        csv_p = tmp_path / "v.csv"
        prov_p = tmp_path / "v.provenance.json"
        summary = fx_history.refresh_pinned_vintage(
            window_years=20,
            as_of=dt.date(2026, 6, 20),
            csv_path=csv_p,
            provenance_path=prov_p,
            fetcher=_synthetic_daily_series,
        )
        assert summary["written"] is True
        assert summary["window_years"] == 20
        assert summary["fetched_as_of"] == "2026-06-20"
        assert csv_p.exists() and prov_p.exists()
        # provenance records the window + an approved provider + a matching sha
        prov = json.loads(prov_p.read_text())
        assert prov["window_years"] == 20
        assert prov["fetched_as_of"] == "2026-06-20"
        assert prov["provider"] in APPROVED_FX_SOURCES
        # the file we wrote must load + pass the sha + provenance guards
        reloaded = load_pinned_history(csv_p, prov_p)
        assert reloaded.provider == "BIS"
        assert reloaded.date_range[0] >= "2006-06-20"
        assert reloaded.date_range[1] <= "2026-06-20"
        assert reloaded.latest == pytest.approx(summary["latest_value"])

    def test_refresh_uses_today_when_as_of_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(fx_history, "_today", lambda: dt.date(2026, 6, 20))
        summary = fx_history.refresh_pinned_vintage(
            window_years=10,
            as_of=None,
            csv_path=tmp_path / "v.csv",
            provenance_path=tmp_path / "v.provenance.json",
            fetcher=_synthetic_daily_series,
        )
        assert summary["fetched_as_of"] == "2026-06-20"

    def test_refresh_rejects_unknown_provider(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="No default live fetcher"):
            fx_history.refresh_pinned_vintage(
                provider="RandomBlog",
                as_of=dt.date(2026, 6, 20),
                csv_path=tmp_path / "v.csv",
                provenance_path=tmp_path / "v.provenance.json",
            )

    def test_write_vintage_rejects_unapproved_provider(self, tmp_path: Path) -> None:
        bad = _synthetic_daily_series(provider="RandomBlog")
        with pytest.raises(ValueError, match="APPROVED_FX_SOURCES"):
            fx_history.write_vintage(
                bad,
                tmp_path / "v.csv",
                tmp_path / "v.provenance.json",
                window_years=20,
                as_of=dt.date(2026, 6, 20),
            )

    def test_refresh_does_not_touch_committed_default(self, tmp_path: Path) -> None:
        # A refresh aimed at tmp paths must leave the committed vintage byte-identical.
        before = fx_history._sha256(Path(fx_history.DEFAULT_VINTAGE_CSV))
        fx_history.refresh_pinned_vintage(
            window_years=10,
            as_of=dt.date(2026, 6, 20),
            csv_path=tmp_path / "v.csv",
            provenance_path=tmp_path / "v.provenance.json",
            fetcher=_synthetic_daily_series,
        )
        after = fx_history._sha256(Path(fx_history.DEFAULT_VINTAGE_CSV))
        assert before == after

    def test_generator_reproduces_committed_descriptors(self) -> None:
        # CCCDIR: _PROVIDER_METADATA is the single source for the sidecar's stable
        # DESCRIPTOR fields, so a refresh must reproduce the committed BIS sidecar's
        # descriptors exactly (guards against the generator drifting from the artifact).
        committed = json.loads(
            Path(fx_history.DEFAULT_VINTAGE_PROVENANCE).read_text()
        )
        s = _synthetic_daily_series(provider="BIS")
        gen = fx_history._build_refresh_provenance(
            s, window_years=20, as_of=dt.date(2026, 6, 28), sha256="deadbeef"
        )
        descriptor_keys = [
            "series",
            "provider",
            "dataset",
            "sdmx_key",
            "endpoint",
            "collection",
            "frequency",
            "unit",
            "authoritative_reference",
            "preferred_live_backbone",
        ]
        for k in descriptor_keys:
            assert gen[k] == committed[k], f"descriptor {k!r} drifted from committed sidecar"

    def test_write_vintage_fails_loud_on_silent_row_drop(self, tmp_path: Path) -> None:
        # A rate that rounds to "0" at 4dp would be dropped on reload; the write
        # round-trip must detect the row-count mismatch and refuse (CESSPIT fail-loud).
        s = fx_history.FXHistorySeries(
            provider="BIS",
            frequency="daily",
            unit="LKR per 1 USD",
            dates=("2020-01-01", "2020-01-02", "2020-01-03"),
            rates=(100.0, 0.00001, 150.0),  # middle rounds to "0" -> dropped on reload
            fetched_as_of="2020-01-03",
            source_endpoint=fx_history.BIS_DAILY_ENDPOINT,
        )
        with pytest.raises(ValueError, match="dropped rows"):
            fx_history.write_vintage(
                s,
                tmp_path / "v.csv",
                tmp_path / "v.provenance.json",
                window_years=20,
                as_of=dt.date(2020, 1, 3),
            )

    def test_provenance_latest_value_matches_on_disk(self, tmp_path: Path) -> None:
        # latest_value in the sidecar must equal the rounded value actually written
        # (not the raw >4dp float), so the sidecar describes its artifact exactly.
        s = fx_history.FXHistorySeries(
            provider="BIS",
            frequency="daily",
            unit="LKR per 1 USD",
            dates=("2026-06-22", "2026-06-23"),
            rates=(333.5, 333.916666),  # >4dp last value
            fetched_as_of="2026-06-23",
            source_endpoint=fx_history.BIS_DAILY_ENDPOINT,
        )
        csv_p = tmp_path / "v.csv"
        prov_p = tmp_path / "v.provenance.json"
        summary = fx_history.write_vintage(
            s, csv_p, prov_p, window_years=20, as_of=dt.date(2026, 6, 23)
        )
        prov = json.loads(prov_p.read_text())
        reloaded = load_pinned_history(csv_p, prov_p)
        assert prov["latest_value"] == reloaded.latest  # exact, not approx
        assert prov["latest_value"] == 333.9167
        assert summary["latest_value"] == 333.9167
        # the descriptor endpoint is the stable bare URL, not the ?format= request URL
        assert "?format=" not in prov["endpoint"]
