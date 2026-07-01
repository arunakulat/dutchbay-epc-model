"""Coverage-completion tests for :mod:`wind_resource.era5_retrieval`.

The sibling ``test_era5_retrieval.py`` exercises the config/processing/coverage-guard
happy paths. This file targets the remaining uncovered branches WITHOUT any network or
live CDS access: the ``cdsapi`` client and NetCDF I/O are fully mocked.

Specifically covered here:
- ``_resolve_reference`` ``mode: fixed`` branch (via ``from_yaml``).
- ``retrieve_era5_timeseries``: the full download/unzip/extract path (mocked
  ``cdsapi.Client``), plus the empty-archive ``RuntimeError``.
- ``build_hub_height_series``: the ``comp()`` ``KeyError`` when a required wind
  component is absent (mocked ``xarray.open_dataset``).
- ``run``: end-to-end orchestration + frozen vintage (sub-functions mocked).
- ``main``: the config-driven entry point honouring ``ERA5_REQUEST_CONFIG``.
"""

from __future__ import annotations

import json
import sys
import types
import zipfile
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd
import pytest

from wind_resource import era5_retrieval
from wind_resource.era5_retrieval import (
    ERA5_TIMESERIES_DATASET,
    ERA5RequestConfig,
    build_hub_height_series,
    main,
    retrieve_era5_timeseries,
    run,
)


def _cfg(**overrides: Any) -> ERA5RequestConfig:
    base: Dict[str, Any] = dict(
        project_name="Cover Site",
        latitude=8.27,
        longitude=79.75,
        start_year=2023,
        end_year=2023,
        hub_height_m=150.0,
        turbine_model="iea_reference_10mw",
        num_turbines=15,
    )
    base.update(overrides)
    return ERA5RequestConfig(**base)


class _FakeDataset:
    """Minimal stand-in for an ``xarray.Dataset`` used by ``build_hub_height_series``.

    Supports ``in`` membership, ``ds[name]`` lookup (returning an object with a
    ``.values`` attribute), a ``coords`` mapping and a ``data_vars`` list -- just enough
    for the function under test.
    """

    def __init__(self, data: Dict[str, np.ndarray], coords: Dict[str, Any]) -> None:
        self._data = data
        self.coords = coords

    def __contains__(self, name: str) -> bool:
        return name in self._data or name in self.coords

    def __getitem__(self, name: str) -> Any:
        value = self._data[name] if name in self._data else self.coords[name]
        return types.SimpleNamespace(values=value)

    @property
    def data_vars(self) -> Dict[str, np.ndarray]:
        return self._data


def test_resolve_reference_fixed_mode_via_yaml(tmp_path: Path) -> None:
    """``reference: {mode: fixed}`` resolves the explicit span (era5_retrieval.py:92)."""
    yml = tmp_path / "fixed.yaml"
    yml.write_text(
        "project:\n  name: F\n  latitude: 8.27\n  longitude: 79.75\n"
        "download:\n  reference:\n    mode: fixed\n    start: 2008\n    end: 2017\n"
        "turbine:\n  model: iea_reference_10mw\n  num_turbines: 15\n  hub_height_m: 150\n"
    )
    cfg = ERA5RequestConfig.from_yaml(str(yml))
    assert cfg.reference_mode == "fixed"
    assert (cfg.start_year, cfg.end_year) == (2008, 2017)
    assert cfg.date_range == "2008-01-01/2017-12-31"


def _install_fake_cdsapi(
    monkeypatch: pytest.MonkeyPatch, nc_names: list[str]
) -> Dict[str, Any]:
    """Install a fake ``cdsapi`` module whose ``Client().retrieve`` writes a zip.

    The written zip contains one entry per name in ``nc_names`` (each a tiny byte
    payload). Returns a dict capturing the recorded ``retrieve`` call arguments.
    """
    recorded: Dict[str, Any] = {}

    class _FakeClient:
        def retrieve(self, dataset: str, request: Dict[str, Any], target: str) -> None:
            recorded["dataset"] = dataset
            recorded["request"] = request
            recorded["target"] = target
            with zipfile.ZipFile(target, "w") as zf:
                for name in nc_names:
                    zf.writestr(name, b"\x89netcdf-stub")

    fake_module = types.ModuleType("cdsapi")
    fake_module.Client = _FakeClient  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "cdsapi", fake_module)
    return recorded


def test_retrieve_era5_timeseries_downloads_and_extracts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The full retrieve/unzip/extract path returns the extracted .nc (lines 202-242)."""
    recorded = _install_fake_cdsapi(monkeypatch, ["era5_point.nc"])
    # Neutralise credential check -- no real ~/.cdsapirc in this env.
    monkeypatch.setattr(era5_retrieval, "ensure_cdsapirc", lambda: Path("/dev/null"))

    cfg = _cfg(project_name="My Cover Site", output_dir=str(tmp_path / "cache"))
    nc_path = retrieve_era5_timeseries(cfg)

    assert nc_path.suffix == ".nc"
    assert nc_path.exists()
    # Request payload is wired from the config.
    assert recorded["dataset"] == ERA5_TIMESERIES_DATASET
    assert recorded["request"]["location"] == {"longitude": 79.75, "latitude": 8.27}
    assert recorded["request"]["date"] == ["2023-01-01/2023-12-31"]
    assert recorded["request"]["data_format"] == "netcdf"
    # Project name is slugified into the zip path.
    assert "my_cover_site" in Path(recorded["target"]).name


def test_retrieve_era5_timeseries_empty_archive_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An archive with no .nc triggers the RuntimeError guard (lines 239-240)."""
    _install_fake_cdsapi(monkeypatch, ["readme.txt"])
    monkeypatch.setattr(era5_retrieval, "ensure_cdsapirc", lambda: Path("/dev/null"))

    cfg = _cfg(output_dir=str(tmp_path / "cache"))
    with pytest.raises(RuntimeError, match="No NetCDF found"):
        retrieve_era5_timeseries(cfg)


def test_build_hub_height_series_missing_component_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A dataset missing a wind component hits the comp() KeyError (line 262)."""
    times = pd.date_range("2023-01-01", periods=4, freq="h")
    # u10 present but v10 absent -> comp("v10") exhausts its names and raises.
    fake = _FakeDataset(
        data={"u10": np.ones(4)},
        coords={"valid_time": times},
    )
    fake_xr = types.ModuleType("xarray")
    fake_xr.open_dataset = lambda _path: fake  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "xarray", fake_xr)

    with pytest.raises(KeyError, match="v10"):
        build_hub_height_series(Path("ignored.nc"), _cfg())


def test_build_hub_height_series_falls_back_to_time_coord(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When ``valid_time`` is absent the ``time`` coord is used (line 255 false branch)."""
    times = pd.date_range("2023-01-01", periods=6, freq="h")
    n = len(times)
    fake = _FakeDataset(
        data={
            "u10": np.full(n, 4.0),
            "v10": np.full(n, 3.0),
            "u100": np.full(n, 8.0),
            "v100": np.full(n, 6.0),
        },
        coords={"time": times},  # note: NOT valid_time
    )
    fake_xr = types.ModuleType("xarray")
    fake_xr.open_dataset = lambda _path: fake  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "xarray", fake_xr)

    df = build_hub_height_series(Path("ignored.nc"), _cfg())
    assert len(df) == n
    assert "ws_150m" in df.columns
    # ws10 = hypot(4,3)=5, ws100 = hypot(8,6)=10 -> alpha = log(2)/log(10) ~ 0.301.
    assert df["wind_shear_alpha"].between(0.05, 0.40).all()
    assert np.isclose(df["wind_shear_alpha"].iloc[0], np.log(2.0) / np.log(10.0))


def test_build_hub_height_series_fills_nan_alpha_with_default_not_floor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A NaN shear alpha is filled with alpha_default (0.143), not the clip floor.

    Audit D13 (#580): this path filled an uncomputable alpha (0/0 winds -> NaN) with
    alpha_min (0.05, a clip floor), diverging from ERA5Fetcher, which uses alpha_default.
    Both now use the coastal/neutral 0.143 default.
    """
    times = pd.date_range("2023-01-01", periods=3, freq="h")
    zero = np.zeros(len(times))  # ws10 = ws100 = 0 -> 0/0 -> NaN alpha
    fake = _FakeDataset(
        data={"u10": zero, "v10": zero, "u100": zero, "v100": zero},
        coords={"valid_time": times},
    )
    fake_xr = types.ModuleType("xarray")
    fake_xr.open_dataset = lambda _path: fake  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "xarray", fake_xr)

    cfg = _cfg()
    assert cfg.alpha_default == pytest.approx(0.143)
    df = build_hub_height_series(Path("ignored.nc"), cfg)
    alphas = df["wind_shear_alpha"].to_numpy()
    assert np.allclose(alphas, cfg.alpha_default)
    assert not np.allclose(alphas, cfg.alpha_min)  # NOT the old clip-floor fill


def test_request_config_reads_alpha_default_from_yaml(tmp_path: Path) -> None:
    """``download.alpha_default`` overrides the 0.143 default (audit D13, #580)."""
    yml = tmp_path / "cfg.yaml"
    yml.write_text(
        "project:\n  name: A\n  latitude: 8.27\n  longitude: 79.75\n"
        "download:\n  alpha_default: 0.12\n"
        "  reference:\n    mode: fixed\n    start: 2020\n    end: 2023\n"
        "turbine:\n  model: iea_reference_10mw\n  num_turbines: 15\n  hub_height_m: 150\n"
    )
    cfg = ERA5RequestConfig.from_yaml(str(yml))
    assert cfg.alpha_default == pytest.approx(0.12)


def test_run_orchestrates_and_freezes_vintage(monkeypatch: pytest.MonkeyPatch) -> None:
    """``run`` wires retrieve -> build -> coverage -> AEP and freezes vintage (345-373)."""
    cfg = _cfg(reference_mode="latest")
    sentinel_nc = Path("/tmp/sentinel.nc")
    sentinel_series = pd.DataFrame({"ws_150m": [7.0, 7.5]})
    coverage = {
        "actual_hours": 8760,
        "expected_hours": 8760,
        "coverage_complete": True,
        "missing_hours": 0,
    }
    aep = {
        "project": cfg.project_name,
        "net_aep_p50_gwh": 480.5,
        "capacity_factor_p50": 0.34,
    }

    calls: Dict[str, Any] = {}

    def _fake_retrieve(c: ERA5RequestConfig) -> Path:
        calls["retrieve"] = c
        return sentinel_nc

    def _fake_build(nc: Path, c: ERA5RequestConfig) -> pd.DataFrame:
        calls["build"] = (nc, c)
        return sentinel_series

    def _fake_validate(s: pd.DataFrame, c: ERA5RequestConfig) -> Dict[str, Any]:
        calls["validate"] = s
        return coverage

    def _fake_compute(s: pd.DataFrame, c: ERA5RequestConfig) -> Dict[str, Any]:
        calls["compute"] = s
        return dict(aep)

    monkeypatch.setattr(era5_retrieval, "retrieve_era5_timeseries", _fake_retrieve)
    monkeypatch.setattr(era5_retrieval, "build_hub_height_series", _fake_build)
    monkeypatch.setattr(era5_retrieval, "validate_coverage", _fake_validate)
    monkeypatch.setattr(era5_retrieval, "compute_site_aep", _fake_compute)

    result = run(cfg)

    # Pipeline threaded the right objects through in order.
    assert calls["retrieve"] is cfg
    assert calls["build"][0] is sentinel_nc
    assert calls["validate"] is sentinel_series
    assert calls["compute"] is sentinel_series
    # Coverage + frozen vintage attached.
    assert result["coverage"] is coverage
    vintage = result["vintage"]
    assert vintage["reference_mode"] == "latest"
    assert vintage["start_year"] == 2023
    assert vintage["end_year"] == 2023
    assert vintage["dataset"] == ERA5_TIMESERIES_DATASET
    assert vintage["expected_hours"] == cfg.expected_hours
    assert vintage["actual_hours"] == 8760
    assert vintage["coverage_complete"] is True


def test_run_logs_incomplete_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    """``run`` also handles the INCOMPLETE coverage log branch (line 371 ternary)."""
    cfg = _cfg(strict_coverage=False)
    coverage = {
        "actual_hours": 8640,
        "expected_hours": 8760,
        "coverage_complete": False,
        "missing_hours": 120,
    }
    monkeypatch.setattr(
        era5_retrieval, "retrieve_era5_timeseries", lambda c: Path("x.nc")
    )
    monkeypatch.setattr(
        era5_retrieval, "build_hub_height_series", lambda nc, c: pd.DataFrame()
    )
    monkeypatch.setattr(era5_retrieval, "validate_coverage", lambda s, c: coverage)
    monkeypatch.setattr(
        era5_retrieval,
        "compute_site_aep",
        lambda s, c: {"net_aep_p50_gwh": 470.0, "capacity_factor_p50": 0.33},
    )

    result = run(cfg)
    assert result["vintage"]["coverage_complete"] is False
    assert result["coverage"]["missing_hours"] == 120


def test_main_prints_run_result_for_env_config(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """``main`` loads ERA5_REQUEST_CONFIG, runs, and prints JSON (lines 378-382)."""
    cfg = _cfg(project_name="Env Site")
    captured_path: Dict[str, str] = {}

    def _fake_from_yaml(path: str) -> ERA5RequestConfig:
        captured_path["path"] = path
        return cfg

    monkeypatch.setattr(
        ERA5RequestConfig,
        "from_yaml",
        classmethod(lambda _cls, path: _fake_from_yaml(path)),
    )
    monkeypatch.setattr(
        era5_retrieval, "run", lambda c: {"project": c.project_name, "ok": True}
    )
    monkeypatch.setenv("ERA5_REQUEST_CONFIG", "config/custom_request.yaml")

    main()

    assert captured_path["path"] == "config/custom_request.yaml"
    out = json.loads(capsys.readouterr().out)
    assert out == {"project": "Env Site", "ok": True}


def test_main_uses_default_config_path_when_env_unset(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """With no env var, ``main`` falls back to the Kalpitiya default path (line 378-379)."""
    captured_path: Dict[str, str] = {}

    monkeypatch.setattr(
        ERA5RequestConfig,
        "from_yaml",
        classmethod(
            lambda _cls, path: captured_path.setdefault("path", path) and None or _cfg()
        ),
    )
    monkeypatch.setattr(era5_retrieval, "run", lambda c: {"ok": True})
    monkeypatch.delenv("ERA5_REQUEST_CONFIG", raising=False)

    main()

    assert captured_path["path"] == ("wind_resource/config/era5_request_kalpitiya.yaml")
    assert json.loads(capsys.readouterr().out) == {"ok": True}
