"""Producer-side long-term-trend emission into the frozen wind export (#656, slice 4).

Closes the loop opened by slice 3 (the finance-CLI Executive Workbook consumer): a
wind producer now MINTS the ``long_term_trend`` block that the consumer decodes into
the workbook "ResourceTrend" sheet.

What is pinned:

* ``wind_resource.long_term_trend.build_resource_trend_export_block`` encodes the live
  ``analyze_long_term_resource`` output (exact match to
  ``analytics.executive_workbook.serialize_resource_trend``) and DEGRADES EXPLICITLY on
  a short record — never a spurious tau;
* the block round-trips into the slice-3 consumer
  (``resource_trend_df_from_wind_export``), proving producer↔consumer are wired end to
  end;
* ``WindPipeline.run_complete_assessment`` is a pure no-op unless ``analyze_trend=True``
  (default-off byte-identity), and when opted in it calls the builder with a
  timestamp-indexed hub series and an ``ERA5RequestConfig`` carrying the pipeline's
  identity;
* ``scripts/run_wind_analysis_v14.py`` surfaces the block at the export top level so a
  frozen export captured from its stdout carries it.

Framework: TEST-01 golden pin; CESSPIT fail-loud (explicit short-series degrade);
report/VALIDATE-only (no committed AEP/KPI touched).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd
import pytest
from omegaconf import OmegaConf

import scripts.run_wind_analysis_v14 as rwa
import wind_resource.wind_pipeline as wp
from analytics.executive_workbook import (
    resource_trend_df_from_wind_export,
    serialize_resource_trend,
)
from wind_resource.era5_retrieval import ERA5RequestConfig
from wind_resource.long_term_trend import (
    analyze_long_term_resource,
    build_resource_trend_export_block,
)

LOCATION = {"name": "TestSite", "lat": 8.33, "lon": 79.76}
HUB_HEIGHT = 150.0


def _cfg(start_year: int = 2005, end_year: int = 2024) -> ERA5RequestConfig:
    return ERA5RequestConfig(
        project_name="TestSite",
        latitude=8.33,
        longitude=79.76,
        start_year=start_year,
        end_year=end_year,
        hub_height_m=HUB_HEIGHT,
        turbine_model="iea_reference_10mw",
        num_turbines=15,
    )


def _series(start: str, end: str, seed: int = 7) -> pd.DataFrame:
    idx = pd.date_range(f"{start}-01-01", f"{end}-12-31 23:00", freq="h")
    ws = np.random.default_rng(seed).weibull(2.5, len(idx)) * 8.0
    return pd.DataFrame({"ws_150m": ws}, index=idx)


# ---------------------------------------------------------------------------
# build_resource_trend_export_block — encoder + explicit degrade
# ---------------------------------------------------------------------------


class TestBuildBlock:
    def test_analyzed_equals_live_serialize(self) -> None:
        cfg, series = _cfg(), _series("2005", "2024")
        block = build_resource_trend_export_block(cfg, series)
        assert block["analyzed"] is True
        assert block["summary_records"]
        # byte-for-byte the same as encoding the live analysis directly
        assert block == serialize_resource_trend(
            analyze_long_term_resource(cfg, series=series)
        )

    def test_round_trips_into_slice3_consumer(self) -> None:
        cfg, series = _cfg(), _series("2005", "2024")
        block = build_resource_trend_export_block(cfg, series)
        got = resource_trend_df_from_wind_export({"long_term_trend": block})
        assert got is not None
        pd.testing.assert_frame_equal(
            got.reset_index(drop=True),
            analyze_long_term_resource(cfg, series=series)["summary_df"].reset_index(
                drop=True
            ),
        )

    def test_short_series_degrades_explicitly(self) -> None:
        cfg = _cfg(2022, 2024)
        block = build_resource_trend_export_block(cfg, _series("2022", "2024", seed=1))
        assert block["analyzed"] is False
        assert "summary_records" not in block
        assert "3 calendar year" in block["reason"]
        assert "10-yr minimum" in block["reason"]

    def test_min_years_boundary(self) -> None:
        # Exactly MIN_TREND_YEARS distinct years analyzes; one fewer degrades.
        cfg = _cfg(2015, 2024)
        assert (
            build_resource_trend_export_block(cfg, _series("2015", "2024"))["analyzed"]
            is True
        )
        assert (
            build_resource_trend_export_block(
                _cfg(2016, 2024), _series("2016", "2024")
            )["analyzed"]
            is False
        )


# ---------------------------------------------------------------------------
# WindPipeline fakes (no CDS, no NetCDF, no network)
# ---------------------------------------------------------------------------


class _FakeFetcher:
    """Writes a synthetic multi-year CSV; adds the hub column on extrapolate."""

    def __init__(self, cache_dir: str, config_path: Any = None) -> None:
        self.cache_dir = Path(cache_dir)
        self._start = "2014-06-01"
        self._end = "2016-06-01"

    def download_wind_data(
        self,
        location: Dict[str, Any],
        start_date: str,
        end_date: str,
        force_download: bool = False,
    ) -> Path:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        ts = pd.date_range(self._start, self._end, freq="h")
        df = pd.DataFrame(
            {"timestamp": ts, "ws_10m": np.random.default_rng(3).weibull(2.5, len(ts))}
        )
        path = self.cache_dir / "synthetic_wind.csv"
        df.to_csv(path, index=False)
        return path

    def extrapolate_to_hub_height(
        self, df: pd.DataFrame, hub_height: float
    ) -> pd.DataFrame:
        out = df.copy()
        out[f"ws_{int(hub_height)}m"] = out["ws_10m"] * 6.0
        return out


class _FakeAnalyzer:
    def __init__(self, df: pd.DataFrame, ws_column: str) -> None:
        pass

    def analyze_all(self) -> Dict[str, Any]:
        return {
            "summary_stats": {"mean": 7.85},
            "weibull": {"shape_k": 2.66, "scale_c": 8.85},
            "variability": {"cov_annual_ws": 4.2},
        }


class _FakeCalculator:
    def __init__(self, df: pd.DataFrame, ws_column: str, **_kw: Any) -> None:
        self.rated_capacity = 10000.0

    def generate_complete_assessment(self) -> Dict[str, Any]:
        return {
            "gross_aep": {"capacity_factor_gross": 41.5},
            "net_aep": {
                "net_aep_p50_mwh": 500_000.0,
                "net_aep_p75_mwh": 470_000.0,
                "net_aep_p90_mwh": 440_000.0,
                "capacity_factor_net_p50": 39.0,
                "capacity_factor_net_p75": 36.5,
                "capacity_factor_net_p90": 34.0,
            },
            "revenue": {
                "annual_revenue_p75_usd": 37_000_000.0,
                "cumulative_revenue_p75_usd": 740_000_000.0,
                "ppa_years": 20,
                "tariff_lkr_per_kwh": 20.3,
                "exchange_rate_lkr_usd": 333.79,
            },
        }


@pytest.fixture()
def patched_stages(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(wp, "ERA5Fetcher", _FakeFetcher)
    monkeypatch.setattr(wp, "WindAnalyzer", _FakeAnalyzer)
    monkeypatch.setattr(wp, "EnergyCalculator", _FakeCalculator)


def _make_pipeline(tmp_path: Path) -> wp.WindPipeline:
    return wp.WindPipeline(
        location=dict(LOCATION),
        hub_height=HUB_HEIGHT,
        turbine_model="iea_reference_10mw",
        num_turbines=15,
        cache_dir=str(tmp_path / "cache"),
        output_dir=str(tmp_path / "out"),
    )


class TestWindPipelineWiring:
    def test_default_off_attaches_no_trend(self, patched_stages, tmp_path) -> None:
        results = _make_pipeline(tmp_path).run_complete_assessment()
        assert "long_term_trend" not in results

    def test_optin_calls_builder_with_series_and_config(
        self, patched_stages, tmp_path, monkeypatch
    ) -> None:
        captured: dict[str, Any] = {}

        def _spy(config: Any, series: pd.DataFrame, **_kw: Any) -> Dict[str, Any]:
            captured["config"] = config
            captured["series"] = series
            return {"analyzed": True, "summary_records": [{"Metric": "x", "Value": 1}]}

        monkeypatch.setattr(
            "wind_resource.long_term_trend.build_resource_trend_export_block", _spy
        )
        results = _make_pipeline(tmp_path).run_complete_assessment(analyze_trend=True)

        assert results["long_term_trend"] == {
            "analyzed": True,
            "summary_records": [{"Metric": "x", "Value": 1}],
        }
        # builder received a timestamp-indexed hub series + an identity-bearing config
        assert isinstance(captured["series"].index, pd.DatetimeIndex)
        assert f"ws_{int(HUB_HEIGHT)}m" in captured["series"].columns
        cfg = captured["config"]
        assert cfg.hub_height_m == HUB_HEIGHT
        assert cfg.turbine_model == "iea_reference_10mw"
        assert cfg.num_turbines == 15
        assert cfg.project_name == LOCATION["name"]

    def test_optin_short_series_degrades_end_to_end(
        self, patched_stages, tmp_path, monkeypatch
    ) -> None:
        # Shrink the fake series to a single-year span → real builder degrades.
        monkeypatch.setattr(_FakeFetcher, "_start", "2023-01-01", raising=False)
        monkeypatch.setattr(_FakeFetcher, "_end", "2023-01-03", raising=False)
        results = _make_pipeline(tmp_path).run_complete_assessment(analyze_trend=True)
        assert results["long_term_trend"]["analyzed"] is False
        assert "summary_records" not in results["long_term_trend"]


# ---------------------------------------------------------------------------
# run_wind_analysis_v14 CLI — surfaces the block at the export top level
# ---------------------------------------------------------------------------


def _full_assessment(trend_block: Dict[str, Any] | None) -> Dict[str, Any]:
    """A complete assessment dict carrying every key the CLI reads (+ optional trend)."""
    results: Dict[str, Any] = {
        "metadata": {"configuration": {"rated_capacity_kw": 10000.0}},
        "wind_data": {"mean_ws": 7.85},
        "statistical_analysis": {
            "weibull": {"shape_k": 2.66, "scale_c": 8.85, "r_squared": 0.99},
            "variability": {"cov_annual_ws": 4.2},
            "temporal": {"windiest_month": "June", "calmest_month": "April"},
        },
        "energy_production": {
            "gross_aep": {"capacity_factor_gross": 41.5, "windfarm_aep_mwh": 550_000.0},
            "net_aep": {
                "net_aep_p50_mwh": 500_000.0,
                "net_aep_p75_mwh": 470_000.0,
                "net_aep_p90_mwh": 440_000.0,
                "capacity_factor_net_p50": 39.0,
                "capacity_factor_net_p75": 36.5,
                "capacity_factor_net_p90": 34.0,
                "total_loss_factor": 0.12,
                "individual_losses": {"wake": 0.05},
            },
            "revenue": {
                "tariff_lkr_per_kwh": 20.3,
                "exchange_rate_lkr_usd": 333.79,
                "ppa_years": 20,
                "annual_revenue_p50_usd": 40_000_000.0,
                "annual_revenue_p75_usd": 37_000_000.0,
                "annual_revenue_p90_usd": 34_000_000.0,
                "cumulative_revenue_p50_usd": 800_000_000.0,
                "cumulative_revenue_p75_usd": 740_000_000.0,
                "cumulative_revenue_p90_usd": 680_000_000.0,
            },
        },
    }
    if trend_block is not None:
        results["long_term_trend"] = trend_block
    return results


class _FakeCliPipeline:
    last_analyze_trend: bool | None = None

    def __init__(self, **_kw: Any) -> None:
        pass

    def run_complete_assessment(
        self, *, start_date, end_date, force_download, analyze_trend
    ) -> Dict[str, Any]:
        _FakeCliPipeline.last_analyze_trend = analyze_trend
        block = {"analyzed": True, "summary_records": [{"Metric": "x", "Value": 1}]}
        return _full_assessment(block if analyze_trend else None)

    def export_for_cashflow_model(self, scenario: str = "P75") -> Dict[str, Any]:
        return {"scenario": scenario, "annual_generation_mwh": 470_000.0}


def _run_wind_cli(overrides: dict[str, Any]) -> dict[str, Any]:
    base = {
        "location": "dutchbay",
        "start_date": "2014-12-01",
        "end_date": "2025-12-31",
        "hub_height": 150.0,
        "turbine_model": "iea_reference_10mw",
        "num_turbines": 15,
        "force_download": False,
        "cache_dir": "inputs/wind_data",
        "output_dir": "outputs/wind_assessment",
        "export_scenario": "P75",
        "analyze_trend": False,
    }
    base.update(overrides)
    rwa.cli.__wrapped__(OmegaConf.create(base))


class TestWindCliSurface:
    def test_optin_surfaces_trend_block(self, monkeypatch, capsys) -> None:
        monkeypatch.setattr(rwa, "WindPipeline", _FakeCliPipeline)
        _run_wind_cli({"analyze_trend": True})
        out = capsys.readouterr().out
        payload = json.loads(out[out.index("{") :])
        assert _FakeCliPipeline.last_analyze_trend is True
        assert payload["long_term_trend"]["analyzed"] is True
        # slice-3 consumer can read it straight from the CLI's export payload
        assert resource_trend_df_from_wind_export(payload) is not None

    def test_default_off_omits_trend_block(self, monkeypatch, capsys) -> None:
        monkeypatch.setattr(rwa, "WindPipeline", _FakeCliPipeline)
        _run_wind_cli({})
        out = capsys.readouterr().out
        payload = json.loads(out[out.index("{") :])
        assert _FakeCliPipeline.last_analyze_trend is False
        assert "long_term_trend" not in payload
