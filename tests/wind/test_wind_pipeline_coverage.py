"""Coverage tests for wind_resource.wind_pipeline (WindPipeline orchestrator).

The pipeline glues three heavy/network stages together:

    ERA5Fetcher.download_wind_data  ->  WindAnalyzer.analyze_all
                                    ->  EnergyCalculator.generate_complete_assessment

These tests NEVER touch the network or the CDS/ERA5 client. The fetcher and the
two analysis stages are replaced (at the ``wind_resource.wind_pipeline`` module
namespace) with lightweight fakes via ``monkeypatch``, and the pipeline is driven
with a tiny synthetic hub-height wind DataFrame written to a CSV the fake fetcher
returns. The tests assert on real wiring behaviour: config loading, the compiled
results dict, the executive summary, JSON persistence, and the cashflow export
selector plus its error/skip branches.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pandas as pd
import pytest

from wind_resource import wind_pipeline as wp
from wind_resource.wind_pipeline import WindPipeline

LOCATION: Dict[str, Any] = {"name": "TestSite", "lat": 8.33, "lon": 79.76}
HUB_HEIGHT = 150.0
WS_COLUMN = "ws_150m"


# ---------------------------------------------------------------------------
# Fakes for the three heavy collaborators (installed at the pipeline namespace)
# ---------------------------------------------------------------------------


class _FakeFetcher:
    """Stand-in for ERA5Fetcher: no CDS client, no NetCDF, no network.

    ``download_wind_data`` writes a deterministic 48-row synthetic CSV (the
    pipeline reads it back with pandas) and ``extrapolate_to_hub_height`` simply
    adds the expected ``ws_<hub>m`` column.
    """

    instances: list["_FakeFetcher"] = []

    def __init__(self, cache_dir: str, config_path: Any = None) -> None:
        self.cache_dir = Path(cache_dir)
        self.config_path = config_path
        self.download_calls: list[dict] = []
        _FakeFetcher.instances.append(self)

    def download_wind_data(
        self,
        location: Dict[str, Any],
        start_date: str,
        end_date: str,
        force_download: bool = False,
    ) -> Path:
        self.download_calls.append(
            {
                "location": location,
                "start_date": start_date,
                "end_date": end_date,
                "force_download": force_download,
            }
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        ts = pd.date_range("2023-01-01", periods=48, freq="h")
        # ws_10m present so extrapolate has something to base the hub column on.
        df = pd.DataFrame(
            {"timestamp": ts, "ws_10m": [6.0 + (i % 5) for i in range(48)]}
        )
        path = self.cache_dir / "synthetic_wind.csv"
        df.to_csv(path, index=False)
        return path

    def extrapolate_to_hub_height(
        self, df: pd.DataFrame, hub_height: float
    ) -> pd.DataFrame:
        out = df.copy()
        out[f"ws_{int(hub_height)}m"] = out["ws_10m"] * 1.25
        return out


class _FakeAnalyzer:
    """Stand-in for WindAnalyzer returning a fixed statistical block."""

    def __init__(self, df: pd.DataFrame, ws_column: str) -> None:
        self.df = df
        self.ws_column = ws_column

    def analyze_all(self) -> Dict[str, Any]:
        return {
            "summary_stats": {"mean": 7.85},
            "weibull": {"shape_k": 2.66, "scale_c": 8.85},
            "variability": {"cov_annual_ws": 4.2},
        }


class _FakeCalculator:
    """Stand-in for EnergyCalculator returning a fixed energy assessment."""

    def __init__(
        self,
        df: pd.DataFrame,
        ws_column: str,
        turbine_model: str,
        num_turbines: int,
    ) -> None:
        self.df = df
        self.ws_column = ws_column
        self.turbine_model = turbine_model
        self.num_turbines = num_turbines
        self.rated_capacity = 10000.0  # kW per turbine

    def generate_complete_assessment(self) -> Dict[str, Any]:
        return _energy_assessment(self.num_turbines, self.rated_capacity)


def _energy_assessment(num_turbines: int, rated_kw: float) -> Dict[str, Any]:
    """A complete energy_production block matching every key the pipeline reads."""
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
            "annual_revenue_p50_usd": 40_000_000.0,
            "annual_revenue_p75_usd": 37_000_000.0,
            "annual_revenue_p90_usd": 34_000_000.0,
            "cumulative_revenue_p50_usd": 800_000_000.0,
            "cumulative_revenue_p75_usd": 740_000_000.0,
            "cumulative_revenue_p90_usd": 680_000_000.0,
            "ppa_years": 20,
            "tariff_lkr_per_kwh": 20.3,
            "exchange_rate_lkr_usd": 333.79,
        },
        "config": {
            "total_capacity_mw": (rated_kw * num_turbines) / 1000,
            "num_turbines": num_turbines,
            "rated_capacity_kw": rated_kw,
        },
    }


@pytest.fixture()
def patched_stages(monkeypatch: pytest.MonkeyPatch) -> None:
    """Swap all three heavy collaborators for the local fakes."""
    _FakeFetcher.instances.clear()
    monkeypatch.setattr(wp, "ERA5Fetcher", _FakeFetcher)
    monkeypatch.setattr(wp, "WindAnalyzer", _FakeAnalyzer)
    monkeypatch.setattr(wp, "EnergyCalculator", _FakeCalculator)


def _make_pipeline(tmp_path: Path, num_turbines: int = 15) -> WindPipeline:
    return WindPipeline(
        location=dict(LOCATION),
        hub_height=HUB_HEIGHT,
        turbine_model="iea_reference_10mw",
        num_turbines=num_turbines,
        cache_dir=str(tmp_path / "cache"),
        output_dir=str(tmp_path / "out"),
    )


# ---------------------------------------------------------------------------
# __init__ / config handling
# ---------------------------------------------------------------------------


def test_init_creates_dirs_and_loads_config(
    patched_stages: None, tmp_path: Path
) -> None:
    pipe = _make_pipeline(tmp_path)
    # Directories created.
    assert (tmp_path / "cache").is_dir()
    assert (tmp_path / "out").is_dir()
    # Identity stored verbatim.
    assert pipe.hub_height == HUB_HEIGHT
    assert pipe.turbine_model == "iea_reference_10mw"
    assert pipe.num_turbines == 15
    # Config loaded from the packaged default era5_config.yaml.
    assert isinstance(pipe.config, dict) and pipe.config
    # Fake fetcher was constructed with the cache_dir.
    assert _FakeFetcher.instances[-1].cache_dir == Path(str(tmp_path / "cache"))


def test_init_rejects_location_missing_keys(
    patched_stages: None, tmp_path: Path
) -> None:
    with pytest.raises(ValueError, match="location must contain keys"):
        WindPipeline(
            location={"name": "NoCoords"},  # missing lat/lon
            hub_height=HUB_HEIGHT,
            turbine_model="iea_reference_10mw",
            num_turbines=15,
            cache_dir=str(tmp_path / "cache"),
            output_dir=str(tmp_path / "out"),
        )


def test_init_explicit_config_path(patched_stages: None, tmp_path: Path) -> None:
    cfg = tmp_path / "custom_era5.yaml"
    cfg.write_text("dataset: reanalysis-era5\nvariables: [u100, v100]\n")
    pipe = WindPipeline(
        location=dict(LOCATION),
        hub_height=HUB_HEIGHT,
        turbine_model="iea_reference_10mw",
        num_turbines=15,
        cache_dir=str(tmp_path / "cache"),
        output_dir=str(tmp_path / "out"),
        config_path=str(cfg),
    )
    assert pipe.config["dataset"] == "reanalysis-era5"
    assert pipe.config["variables"] == ["u100", "v100"]


def test_load_config_missing_file_raises(patched_stages: None, tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist.yaml"
    with pytest.raises(FileNotFoundError, match="Config file not found"):
        WindPipeline(
            location=dict(LOCATION),
            hub_height=HUB_HEIGHT,
            turbine_model="iea_reference_10mw",
            num_turbines=15,
            cache_dir=str(tmp_path / "cache"),
            output_dir=str(tmp_path / "out"),
            config_path=str(missing),
        )


# ---------------------------------------------------------------------------
# run_complete_assessment (full stage wiring)
# ---------------------------------------------------------------------------


def test_run_complete_assessment_wires_all_stages(
    patched_stages: None, tmp_path: Path
) -> None:
    pipe = _make_pipeline(tmp_path)
    results = pipe.run_complete_assessment(
        start_date="2023-01-01", end_date="2023-12-31"
    )

    # Top-level structure.
    assert set(results) >= {
        "metadata",
        "wind_data",
        "statistical_analysis",
        "energy_production",
        "summary",
    }

    # Fetcher was driven with the pipeline's own location and the given dates.
    call = _FakeFetcher.instances[-1].download_calls[-1]
    assert call["location"] == LOCATION
    assert call["start_date"] == "2023-01-01"
    assert call["end_date"] == "2023-12-31"
    assert call["force_download"] is False

    # Metadata reflects the synthetic 48-row dataset and config.
    meta = results["metadata"]
    assert meta["data_period"]["data_points"] == 48
    cfg = meta["configuration"]
    assert cfg["hub_height_m"] == HUB_HEIGHT
    assert cfg["num_turbines"] == 15
    assert cfg["rated_capacity_kw"] == 10000.0
    assert cfg["total_capacity_mw"] == pytest.approx(150.0)

    # wind_data stats are computed from the extrapolated ws_150m column.
    wd = results["wind_data"]
    assert wd["mean_ws"] > 0
    assert wd["max_ws"] >= wd["min_ws"]
    assert "p90_ws" in wd

    # statistical_analysis / energy_production passed straight through.
    assert results["statistical_analysis"]["weibull"]["shape_k"] == 2.66
    assert results["energy_production"]["net_aep"]["net_aep_p75_mwh"] == 470_000.0

    # JSON output file written under output_dir, named from the lowercased site.
    out_files = list((tmp_path / "out").glob("testsite_assessment_*.json"))
    assert len(out_files) == 1
    persisted = json.loads(out_files[0].read_text())
    assert persisted["metadata"]["data_period"]["data_points"] == 48


def test_run_complete_assessment_summary_metrics(
    patched_stages: None, tmp_path: Path
) -> None:
    pipe = _make_pipeline(tmp_path)
    results = pipe.run_complete_assessment()
    summary = results["summary"]

    # _generate_summary maps the fixed analyzer/calculator outputs.
    wr = summary["wind_resource"]
    assert wr["mean_wind_speed_ms"] == 7.85
    assert wr["weibull_shape_k"] == 2.66
    assert wr["weibull_scale_c_ms"] == 8.85
    assert wr["interannual_cov_percent"] == 4.2

    ep = summary["energy_production"]
    assert ep["gross_capacity_factor_percent"] == 41.5
    assert ep["net_aep_p50_gwh"] == pytest.approx(500.0)  # 500_000 mwh / 1000
    assert ep["net_aep_p75_gwh"] == pytest.approx(470.0)
    assert ep["net_aep_p90_gwh"] == pytest.approx(440.0)
    assert ep["net_capacity_factor_p75_percent"] == 36.5

    rev = summary["revenue"]
    assert rev["annual_revenue_p75_usd"] == 37_000_000.0
    assert rev["ppa_years"] == 20
    assert rev["cumulative_revenue_p75_usd"] == 740_000_000.0


def test_run_complete_assessment_force_download_propagates(
    patched_stages: None, tmp_path: Path
) -> None:
    pipe = _make_pipeline(tmp_path)
    pipe.run_complete_assessment(force_download=True)
    assert _FakeFetcher.instances[-1].download_calls[-1]["force_download"] is True


# ---------------------------------------------------------------------------
# export_for_cashflow_model (selector + error/skip branches)
# ---------------------------------------------------------------------------


def test_export_rejects_invalid_scenario(patched_stages: None, tmp_path: Path) -> None:
    pipe = _make_pipeline(tmp_path)
    with pytest.raises(ValueError, match="scenario must be"):
        pipe.export_for_cashflow_model(scenario="P42")


def test_export_without_assessment_raises_runtime(
    patched_stages: None, tmp_path: Path
) -> None:
    pipe = _make_pipeline(tmp_path)
    # No run_complete_assessment() has been executed: no *_assessment_*.json.
    with pytest.raises(RuntimeError, match="No assessment results found"):
        pipe.export_for_cashflow_model(scenario="P75")


@pytest.mark.parametrize(
    ("scenario", "expected_mwh", "expected_cf", "expected_rev"),
    [
        ("P50", 500_000.0, 39.0, 40_000_000.0),
        ("P75", 470_000.0, 36.5, 37_000_000.0),
        ("P90", 440_000.0, 34.0, 34_000_000.0),
    ],
)
def test_export_for_cashflow_model_per_scenario(
    patched_stages: None,
    tmp_path: Path,
    scenario: str,
    expected_mwh: float,
    expected_cf: float,
    expected_rev: float,
) -> None:
    pipe = _make_pipeline(tmp_path)
    pipe.run_complete_assessment()

    export = pipe.export_for_cashflow_model(scenario=scenario)

    assert export["scenario"] == scenario
    assert export["annual_generation_mwh"] == expected_mwh
    assert export["capacity_factor_percent"] == expected_cf
    assert export["revenue_annual_usd"] == expected_rev
    assert export["project_capacity_mw"] == pytest.approx(150.0)
    assert export["num_turbines"] == 15
    assert export["rated_capacity_per_turbine_kw"] == 10000.0
    assert export["ppa_years"] == 20
    assert export["tariff_lkr_per_kwh"] == 20.3
    assert export["exchange_rate_lkr_usd"] == 333.79

    # Export persisted to its own JSON file.
    export_file = tmp_path / "out" / f"testsite_cashflow_export_{scenario}.json"
    assert export_file.is_file()
    assert json.loads(export_file.read_text()) == export


def test_export_uses_most_recent_assessment(
    patched_stages: None, tmp_path: Path
) -> None:
    pipe = _make_pipeline(tmp_path)
    pipe.run_complete_assessment()

    # Drop in a lexically-later assessment file with a distinct generation value;
    # the export must pick the sorted()[-1] file, i.e. this one.
    later = tmp_path / "out" / "testsite_assessment_2099-01-01_to_2099-12-31.json"
    payload = {
        "energy_production": _energy_assessment(num_turbines=20, rated_kw=10000.0)
    }
    payload["energy_production"]["net_aep"]["net_aep_p75_mwh"] = 999_999.0
    later.write_text(json.dumps(payload))

    export = pipe.export_for_cashflow_model(scenario="P75")
    assert export["annual_generation_mwh"] == 999_999.0
    assert export["num_turbines"] == 20
