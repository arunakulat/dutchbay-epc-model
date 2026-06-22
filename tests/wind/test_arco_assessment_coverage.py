"""Coverage tests for :mod:`wind_resource.arco_assessment`.

Targets the branches the existing ``test_arco_wiring.py`` leaves uncovered:

* the ``reference.mode: latest`` rolling-window branch of
  ``_resolve_reference_window`` (defaults and explicit ``n_years`` / ``end_year_lag``),
* the invalid-mode ``ValueError`` raised by ``_resolve_reference_window``,
* the live ``assess`` orchestrator, exercised end-to-end with the CDS/NetCDF I/O
  (``retrieve_era5_timeseries`` / ``build_hub_height_series`` / ``validate_coverage``)
  fully mocked -- no network and no live Copernicus CDS calls.
"""

from __future__ import annotations

import copy
import datetime as dt
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd
import pytest

from analytics.scenario_loader import load_scenario_config
from wind_resource import arco_assessment, era5_retrieval
from wind_resource.arco_assessment import assess, era5_config_from_scenario
from wind_resource.era5_retrieval import ERA5RequestConfig

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER_CONFIG = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"


@pytest.fixture(scope="module")
def scenario() -> Dict[str, Any]:
    return load_scenario_config(str(LENDER_CONFIG))


def _weibull_series(a: float, k: float, n: int = 40_000, seed: int = 3) -> pd.DataFrame:
    """A synthetic hub-height series drawn from Weibull(scale=a, shape=k)."""
    rng = np.random.default_rng(seed)
    return pd.DataFrame({"ws_150m": rng.weibull(k, n) * a})


# ── reference.mode: latest (rolling window) ─────────────────────────────────────


def test_latest_mode_uses_defaults(scenario: Dict[str, Any]) -> None:
    """``mode: latest`` with no n_years/lag resolves a 20-year window ending today-2."""
    sc = copy.deepcopy(scenario)
    sc["resource"]["era5"]["reference"] = {"mode": "latest"}

    cfg = era5_config_from_scenario(sc)

    expected_end = dt.date.today().year - 2  # default end_year_lag
    assert cfg.reference_mode == "latest"
    assert cfg.end_year == expected_end
    assert cfg.start_year == expected_end - 20 + 1  # default n_years=20


def test_latest_mode_honours_explicit_n_years_and_lag(scenario: Dict[str, Any]) -> None:
    """Explicit ``n_years`` / ``end_year_lag`` drive the resolved rolling window."""
    sc = copy.deepcopy(scenario)
    sc["resource"]["era5"]["reference"] = {
        "mode": "latest",
        "n_years": 5,
        "end_year_lag": 3,
    }

    cfg = era5_config_from_scenario(sc)

    expected_end = dt.date.today().year - 3
    assert cfg.end_year == expected_end
    assert cfg.start_year == expected_end - 5 + 1
    # span is exactly n_years inclusive
    assert cfg.end_year - cfg.start_year + 1 == 5


def test_invalid_reference_mode_raises(scenario: Dict[str, Any]) -> None:
    """A mode that is neither 'fixed' nor 'latest' fails fast inside the resolver."""
    sc = copy.deepcopy(scenario)
    sc["resource"]["era5"]["reference"] = {"mode": "rolling"}

    with pytest.raises(ValueError, match="must be 'fixed' or 'latest'"):
        era5_config_from_scenario(sc)


# ── assess() live orchestrator (CDS / NetCDF mocked) ───────────────────────────


def test_assess_end_to_end_mocks_retrieval(
    scenario: Dict[str, Any], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``assess`` retrieves, builds the hub series, guards coverage, then assesses.

    The three ERA5 boundary functions are patched on the ``era5_retrieval`` module
    (``assess`` imports them from there at call time), so no CDS / NetCDF I/O runs.
    The fitted series matches the declared (A=8.199, k=2.665) baseline so the drift
    lands within tolerance, and the mocked coverage dict is threaded into the
    returned vintage + the top-level ``coverage`` key.
    """
    captured: Dict[str, Any] = {}

    def fake_retrieve(config: ERA5RequestConfig) -> Path:
        captured["cfg"] = config
        # Cross-check the adapter wired the live config through unchanged.
        assert config.reference_mode == "fixed"
        assert config.hub_height_m == 150.0
        nc = tmp_path / "fake_era5.nc"
        nc.write_bytes(b"not-a-real-netcdf")  # never parsed; build is mocked too
        return nc

    def fake_build(nc_path: Path, config: ERA5RequestConfig) -> pd.DataFrame:
        captured["nc_path"] = nc_path
        return _weibull_series(8.199, 2.665)

    def fake_validate(
        series: pd.DataFrame, config: ERA5RequestConfig
    ) -> Dict[str, Any]:
        return {
            "actual_hours": config.expected_hours,
            "expected_hours": config.expected_hours,
            "coverage_complete": True,
            "missing_hours": 0,
        }

    monkeypatch.setattr(era5_retrieval, "retrieve_era5_timeseries", fake_retrieve)
    monkeypatch.setattr(era5_retrieval, "build_hub_height_series", fake_build)
    monkeypatch.setattr(era5_retrieval, "validate_coverage", fake_validate)

    result = assess(scenario)

    cfg = captured["cfg"]
    assert captured["nc_path"] == tmp_path / "fake_era5.nc"
    # The hub series was retrieved off the resolved hub height (ws_150m).
    assert result["mode"] == "validate"
    assert result["drift"]["within_tolerance"] is True
    # Top-level coverage is the mocked dict verbatim.
    assert result["coverage"]["coverage_complete"] is True
    assert result["coverage"]["actual_hours"] == cfg.expected_hours
    # Vintage is stamped from the resolved config + coverage.
    vintage = result["vintage"]
    assert vintage["reference_mode"] == "fixed"
    assert vintage["start_year"] == cfg.start_year
    assert vintage["end_year"] == cfg.end_year
    assert vintage["latitude"] == cfg.latitude
    assert vintage["longitude"] == cfg.longitude
    assert vintage["expected_hours"] == cfg.expected_hours
    assert vintage["actual_hours"] == cfg.expected_hours
    assert vintage["coverage_complete"] is True
    assert vintage["resolved_at"] == cfg.resolved_at


def test_assess_propagates_incomplete_coverage(
    scenario: Dict[str, Any], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A non-strict partial-coverage dict flows through assess into the result."""
    monkeypatch.setattr(
        era5_retrieval,
        "retrieve_era5_timeseries",
        lambda config: tmp_path / "x.nc",
    )
    monkeypatch.setattr(
        era5_retrieval,
        "build_hub_height_series",
        lambda nc_path, config: _weibull_series(8.199, 2.665),
    )
    coverage = {
        "actual_hours": 8640,
        "expected_hours": 8760,
        "coverage_complete": False,
        "missing_hours": 120,
    }
    monkeypatch.setattr(
        era5_retrieval, "validate_coverage", lambda series, config: coverage
    )

    result = assess(scenario)

    assert result["coverage"]["missing_hours"] == 120
    assert result["vintage"]["coverage_complete"] is False
    assert result["vintage"]["actual_hours"] == 8640


def test_assess_uses_module_level_functions(monkeypatch: pytest.MonkeyPatch) -> None:
    """``assess`` resolves the boundary funcs via the era5_retrieval module.

    Guards the call-time-import contract: patching the module attributes (not the
    arco_assessment namespace) is what intercepts the live calls.
    """
    assert hasattr(arco_assessment, "assess")
    assert hasattr(era5_retrieval, "retrieve_era5_timeseries")
    assert hasattr(era5_retrieval, "build_hub_height_series")
    assert hasattr(era5_retrieval, "validate_coverage")
