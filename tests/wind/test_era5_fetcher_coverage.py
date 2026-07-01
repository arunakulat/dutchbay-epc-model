"""Coverage tests for :mod:`wind_resource.era5_fetcher`.

These exercise the ERA5Fetcher orchestration without touching the network or
the live Copernicus CDS: ``cdsapi.Client`` and the xarray/NetCDF I/O are
mocked, and all file output is routed through ``tmp_path``. The focus is on
request building, the ``download_wind_data`` orchestration, the
skip-if-cached branch, wind-metric maths, hub-height extrapolation, the CDS
error/hint handling, and metadata persistence.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict
from unittest import mock

import numpy as np
import pandas as pd
import pytest
import scipy.stats  # noqa: F401  (warm doc-gen before any numpy reload)

from wind_resource import era5_fetcher
from wind_resource.era5_fetcher import ERA5Fetcher

CONFIG_YAML = """\
api:
  area_buffer_degrees: 0.5
variables:
  - 10m_u_component_of_wind
  - 10m_v_component_of_wind
  - 100m_u_component_of_wind
  - 100m_v_component_of_wind
wind_shear:
  reference_heights: [10, 100]
  alpha_min: 0.05
  alpha_max: 0.40
  alpha_default: 0.143
"""


def _write_config(tmp_path: Path, text: str = CONFIG_YAML) -> Path:
    cfg = tmp_path / "era5_config.yaml"
    cfg.write_text(text)
    return cfg


def _make_fetcher(tmp_path: Path) -> ERA5Fetcher:
    cfg = _write_config(tmp_path)
    return ERA5Fetcher(cache_dir=str(tmp_path / "cache"), config_path=str(cfg))


def _location() -> Dict[str, Any]:
    return {"name": "DutchBay", "lat": 8.33, "lon": 79.76}


def test_init_creates_dirs_and_loads_config(tmp_path: Path) -> None:
    fetcher = _make_fetcher(tmp_path)

    assert fetcher.cache_dir.is_dir()
    assert fetcher.metadata_dir.is_dir()
    assert fetcher.metadata_dir == fetcher.cache_dir / "metadata"
    # Config values extracted from the YAML.
    assert fetcher.area_buffer == 0.5
    assert fetcher.variables[0] == "10m_u_component_of_wind"
    assert fetcher.alpha_min == 0.05
    assert fetcher.alpha_max == 0.40
    assert fetcher.alpha_default == 0.143
    # reference_height is reference_heights[1] == 100m.
    assert fetcher.reference_height == 100
    assert fetcher._config_path == tmp_path / "era5_config.yaml"


def test_init_raises_when_cds_unavailable(tmp_path: Path) -> None:
    with mock.patch.object(era5_fetcher, "CDS_AVAILABLE", False):
        with pytest.raises(ImportError, match="requires 'cdsapi' and 'xarray'"):
            ERA5Fetcher(cache_dir=str(tmp_path / "cache"))


def test_load_config_default_path(tmp_path: Path) -> None:
    # config_path=None falls back to wind_resource/config/era5_config.yaml,
    # which exists in the repo.
    fetcher = ERA5Fetcher(cache_dir=str(tmp_path / "cache"), config_path=None)
    expected = Path(era5_fetcher.__file__).parent / "config" / "era5_config.yaml"
    assert fetcher._config_path == expected
    assert fetcher.variables  # loaded from real config


def test_load_config_missing_file_raises(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist.yaml"
    with pytest.raises(FileNotFoundError, match="Config file not found"):
        ERA5Fetcher(cache_dir=str(tmp_path / "cache"), config_path=str(missing))


def test_load_config_missing_key_raises(tmp_path: Path) -> None:
    # Drop the wind_shear section to trigger the KeyError -> KeyError re-raise.
    bad_yaml = "api:\n  area_buffer_degrees: 0.5\nvariables:\n  - x\n"
    cfg = _write_config(tmp_path, bad_yaml)
    with pytest.raises(KeyError, match="Missing required config key"):
        ERA5Fetcher(cache_dir=str(tmp_path / "cache"), config_path=str(cfg))


def test_get_years_single_and_range() -> None:
    assert ERA5Fetcher._get_years("2020-01-01", "2020-12-31") == ["2020"]
    assert ERA5Fetcher._get_years("2014-12-01", "2016-03-15") == [
        "2014",
        "2015",
        "2016",
    ]


def test_download_wind_data_missing_location_keys(tmp_path: Path) -> None:
    fetcher = _make_fetcher(tmp_path)
    with pytest.raises(ValueError, match="location must contain keys"):
        fetcher.download_wind_data(
            location={"name": "x", "lat": 1.0},  # missing 'lon'
            start_date="2020-01-01",
            end_date="2020-12-31",
        )


def test_download_wind_data_uses_cache(tmp_path: Path) -> None:
    fetcher = _make_fetcher(tmp_path)
    cache_file = fetcher.cache_dir / "era5_dutchbay_2020-01-01_to_2020-12-31.csv"
    cache_file.write_text("timestamp,ws_100m\n2020-01-01,7.0\n")

    with mock.patch.object(fetcher, "_download_from_cds") as dl:
        result = fetcher.download_wind_data(
            location=_location(),
            start_date="2020-01-01",
            end_date="2020-12-31",
        )

    assert result == cache_file
    dl.assert_not_called()  # cache hit short-circuits the download


def _fake_uv_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2020-01-01", periods=4, freq="h"),
            "u10": [3.0, 4.0, 0.0, 5.0],
            "v10": [4.0, 3.0, 0.0, 0.0],
            "u100": [6.0, 8.0, 0.0, 10.0],
            "v100": [8.0, 6.0, 0.0, 0.0],
        }
    )


def test_download_wind_data_full_orchestration(tmp_path: Path) -> None:
    fetcher = _make_fetcher(tmp_path)
    nc_path = fetcher.cache_dir / "era5_dutchbay_raw.nc"

    with (
        mock.patch.object(fetcher, "_download_from_cds", return_value=nc_path) as dl,
        mock.patch.object(
            fetcher, "_convert_netcdf_to_dataframe", return_value=_fake_uv_frame()
        ) as conv,
    ):
        result = fetcher.download_wind_data(
            location=_location(),
            start_date="2020-01-01",
            end_date="2020-12-31",
            force_download=True,
        )

    dl.assert_called_once()
    conv.assert_called_once_with(nc_path)
    assert result.exists()
    assert result.name == "era5_dutchbay_2020-01-01_to_2020-12-31.csv"

    out = pd.read_csv(result)
    # Wind metrics were computed and written to CSV.
    for col in ("ws_10m", "ws_100m", "wd_10m", "wd_100m", "alpha"):
        assert col in out.columns

    # Metadata sidecar JSON was produced.
    meta = fetcher.metadata_dir / f"{result.stem}_metadata.json"
    assert meta.exists()


def test_download_wind_data_force_redownload_ignores_cache(tmp_path: Path) -> None:
    fetcher = _make_fetcher(tmp_path)
    cache_file = fetcher.cache_dir / "era5_dutchbay_2020-01-01_to_2020-12-31.csv"
    cache_file.write_text("stale\n")
    nc_path = fetcher.cache_dir / "era5_dutchbay_raw.nc"

    with (
        mock.patch.object(fetcher, "_download_from_cds", return_value=nc_path) as dl,
        mock.patch.object(
            fetcher, "_convert_netcdf_to_dataframe", return_value=_fake_uv_frame()
        ),
    ):
        fetcher.download_wind_data(
            location=_location(),
            start_date="2020-01-01",
            end_date="2020-12-31",
            force_download=True,
        )

    dl.assert_called_once()  # force_download bypasses the existing cache file


def test_download_from_cds_builds_request_and_area(tmp_path: Path) -> None:
    fetcher = _make_fetcher(tmp_path)
    fake_client = mock.MagicMock()

    with mock.patch.object(
        era5_fetcher.cdsapi, "Client", return_value=fake_client
    ) as client_ctor:
        nc_file = fetcher._download_from_cds(
            location=_location(),
            start_date="2020-01-01",
            end_date="2021-12-31",
        )

    client_ctor.assert_called_once_with()
    fake_client.retrieve.assert_called_once()
    args, _ = fake_client.retrieve.call_args
    dataset, request, target = args

    assert dataset == "reanalysis-era5-single-levels"
    assert request["product_type"] == "reanalysis"
    assert request["variable"] == fetcher.variables
    assert request["year"] == ["2020", "2021"]
    assert request["format"] == "netcdf"
    assert request["month"] == [f"{m:02d}" for m in range(1, 13)]
    assert request["day"] == [f"{d:02d}" for d in range(1, 32)]
    assert request["time"] == [f"{h:02d}:00" for h in range(24)]

    # Area = [N, W, S, E] with config buffer applied.
    lat, lon, buf = 8.33, 79.76, fetcher.area_buffer
    assert request["area"] == pytest.approx(
        [lat + buf, lon - buf, lat - buf, lon + buf]
    )

    assert nc_file == fetcher.cache_dir / "era5_dutchbay_raw.nc"
    assert target == str(nc_file)


def test_download_from_cds_generic_error(tmp_path: Path) -> None:
    fetcher = _make_fetcher(tmp_path)
    fake_client = mock.MagicMock()
    fake_client.retrieve.side_effect = RuntimeError("connection reset")

    with mock.patch.object(era5_fetcher.cdsapi, "Client", return_value=fake_client):
        with pytest.raises(RuntimeError, match="CDS API download failed") as exc:
            fetcher._download_from_cds(
                location=_location(),
                start_date="2020-01-01",
                end_date="2020-12-31",
            )

    # Generic failures do NOT append the ARCO timeseries hint.
    assert "ARCO timeseries" not in str(exc.value)


def test_download_from_cds_too_large_error_adds_hint(tmp_path: Path) -> None:
    fetcher = _make_fetcher(tmp_path)
    fake_client = mock.MagicMock()
    fake_client.retrieve.side_effect = Exception("Request too large for CDS")

    with mock.patch.object(era5_fetcher.cdsapi, "Client", return_value=fake_client):
        with pytest.raises(RuntimeError, match="CDS API download failed") as exc:
            fetcher._download_from_cds(
                location=_location(),
                start_date="2014-01-01",
                end_date="2025-12-31",
            )

    msg = str(exc.value)
    assert "ARCO timeseries" in msg
    assert "wind_resource.era5_retrieval" in msg


def test_download_from_cds_cost_error_adds_hint(tmp_path: Path) -> None:
    fetcher = _make_fetcher(tmp_path)
    fake_client = mock.MagicMock()
    fake_client.retrieve.side_effect = Exception("403 cost limit exceeded")

    with mock.patch.object(era5_fetcher.cdsapi, "Client", return_value=fake_client):
        with pytest.raises(RuntimeError) as exc:
            fetcher._download_from_cds(
                location=_location(),
                start_date="2014-01-01",
                end_date="2025-12-31",
            )

    assert "ARCO timeseries" in str(exc.value)


def test_convert_netcdf_to_dataframe(tmp_path: Path) -> None:
    fetcher = _make_fetcher(tmp_path)

    raw = pd.DataFrame(
        {
            "time": pd.date_range("2020-01-01", periods=3, freq="h"),
            "u10": [1.0, 2.0, 3.0],
            "v10": [1.0, 2.0, 3.0],
            "u100": [2.0, 4.0, 6.0],
            "v100": [2.0, 4.0, 6.0],
            "extra": [9, 9, 9],  # dropped by the column filter
        }
    )

    fake_ds = mock.MagicMock()
    fake_ds.to_dataframe.return_value.reset_index.return_value = raw

    nc_file = fetcher.cache_dir / "era5_dutchbay_raw.nc"
    with mock.patch.object(
        era5_fetcher.xr, "open_dataset", return_value=fake_ds
    ) as opener:
        df = fetcher._convert_netcdf_to_dataframe(nc_file)

    opener.assert_called_once_with(nc_file)
    assert list(df.columns) == ["timestamp", "u10", "v10", "u100", "v100"]
    assert "extra" not in df.columns
    assert len(df) == 3


def test_calculate_wind_metrics_values(tmp_path: Path) -> None:
    fetcher = _make_fetcher(tmp_path)
    df = fetcher._calculate_wind_metrics(_fake_uv_frame())

    # Row 0: u=3,v=4 -> speed 5; u=6,v=8 -> speed 10.
    assert df["ws_10m"].iloc[0] == pytest.approx(5.0)
    assert df["ws_100m"].iloc[0] == pytest.approx(10.0)

    # alpha = ln(ws100/ws10)/ln(10); for row0 = ln(2)/ln(10) ~= 0.30103.
    assert df["alpha"].iloc[0] == pytest.approx(np.log(2.0) / np.log(10.0))

    # Direction is in [0, 360).
    assert (df["wd_10m"] >= 0).all()
    assert (df["wd_10m"] < 360).all()

    # Row 2 is all-zero -> ws are 0, alpha is NaN before fill -> filled with
    # alpha_default. Row 3 (ws100>ws10) clips at alpha_max.
    assert df["alpha"].iloc[2] == pytest.approx(fetcher.alpha_default)
    assert (df["alpha"] >= fetcher.alpha_min).all()
    assert (df["alpha"] <= fetcher.alpha_max).all()


def test_extrapolate_to_hub_height(tmp_path: Path) -> None:
    fetcher = _make_fetcher(tmp_path)
    df = pd.DataFrame({"ws_100m": [10.0, 8.0], "alpha": [0.0, 0.2]})

    out = fetcher.extrapolate_to_hub_height(df, hub_height=150.0)

    assert "ws_150m" in out.columns
    # alpha=0 -> no change at any height.
    assert out["ws_150m"].iloc[0] == pytest.approx(10.0)
    # alpha=0.2: 8 * (150/100)^0.2.
    assert out["ws_150m"].iloc[1] == pytest.approx(8.0 * (150.0 / 100.0) ** 0.2)


def test_extrapolate_rejects_low_hub_height(tmp_path: Path) -> None:
    fetcher = _make_fetcher(tmp_path)
    df = pd.DataFrame({"ws_100m": [10.0], "alpha": [0.1]})
    # reference_height is 100m; 100 is not > 100 -> rejected.
    with pytest.raises(ValueError, match="hub_height must be >"):
        fetcher.extrapolate_to_hub_height(df, hub_height=100.0)


def test_extrapolate_requires_columns(tmp_path: Path) -> None:
    fetcher = _make_fetcher(tmp_path)
    df = pd.DataFrame({"ws_100m": [10.0]})  # missing 'alpha'
    with pytest.raises(ValueError, match="must contain columns"):
        fetcher.extrapolate_to_hub_height(df, hub_height=150.0)


def test_save_metadata_writes_json(tmp_path: Path) -> None:
    fetcher = _make_fetcher(tmp_path)
    cache_file = fetcher.cache_dir / "era5_dutchbay_2020-01-01_to_2020-12-31.csv"

    fetcher._save_metadata(
        location=_location(),
        start_date="2020-01-01",
        end_date="2020-12-31",
        cache_file=cache_file,
    )

    meta_file = fetcher.metadata_dir / f"{cache_file.stem}_metadata.json"
    assert meta_file.exists()

    meta = json.loads(meta_file.read_text())
    assert meta["location"] == _location()
    assert meta["start_date"] == "2020-01-01"
    assert meta["end_date"] == "2020-12-31"
    assert meta["cache_file"] == str(cache_file)
    assert meta["config_values"]["area_buffer_degrees"] == fetcher.area_buffer
    assert meta["config_values"]["alpha_default"] == fetcher.alpha_default
    assert meta["config_values"]["reference_height"] == fetcher.reference_height
    assert "download_timestamp" in meta
