"""Tests for the ARCO single-point ERA5 wiring (Weibull fit + VALIDATE-mode drift).

Covers the new resource.era5 schema, the scenario->ERA5RequestConfig adapter (with the
hub-height cross-assertion and no masking defaults), the Weibull fitter + drift, and the
end-to-end assessment that fits a Weibull on a synthetic ERA5 series and validates it
against the declared lender baseline WITHOUT mutating it. No live CDS calls.
"""

from __future__ import annotations

import copy
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from analytics.config_schema import get_required_fields
from analytics.scenario_loader import load_scenario_config
from analytics.schema_guard import (ConfigValidationError,
                                    validate_config_for_v14)
# Top-level import registers the era5 specs at collection time (mirrors
# tests/analytics/test_wind_interface_schema.py). Required because the import-smoke
# lint test wipes ``analytics.*`` from ``sys.modules`` mid-run; without this the
# schema would only register into a re-imported config_schema instance the schema-guard
# binding here can't see, and the negative tests would silently not raise.
from analytics.wind.era5_interface_schema import ERA5_INTERFACE_MODULE
from wind_resource.arco_assessment import (build_arco_assessment,
                                           era5_config_from_scenario)
from wind_resource.weibull_fit import (fit_weibull_on_series, weibull_drift,
                                       weibull_std)

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER_CONFIG = REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"


@pytest.fixture(scope="module")
def scenario() -> dict:
    return load_scenario_config(str(LENDER_CONFIG))


def _weibull_series(a: float, k: float, n: int = 60_000, seed: int = 7) -> pd.DataFrame:
    """A synthetic hub-height series drawn from Weibull(scale=a, shape=k)."""
    rng = np.random.default_rng(seed)
    ws = rng.weibull(k, n) * a
    return pd.DataFrame({"ws_150m": ws})


# ── schema ────────────────────────────────────────────────────────────────────


def test_era5_specs_registered() -> None:
    names = {spec.name for spec in get_required_fields(ERA5_INTERFACE_MODULE)}
    assert names == {"latitude", "longitude", "reference_mode", "hub_height_m", "strict_coverage"}


def test_lender_era5_block_passes_schema(scenario: dict) -> None:
    validate_config_for_v14(scenario, str(LENDER_CONFIG), ["era5"])  # must not raise


def test_invalid_reference_mode_rejected(scenario: dict) -> None:
    bad = copy.deepcopy(scenario)
    bad["resource"]["era5"]["reference"]["mode"] = "rolling"
    with pytest.raises(ConfigValidationError):
        validate_config_for_v14(bad, str(LENDER_CONFIG), ["era5"])


def test_missing_latitude_rejected(scenario: dict) -> None:
    bad = copy.deepcopy(scenario)
    del bad["resource"]["era5"]["latitude"]
    with pytest.raises(ConfigValidationError):
        validate_config_for_v14(bad, str(LENDER_CONFIG), ["era5"])


# ── adapter (config-driven, no masking defaults) ────────────────────────────────


def test_adapter_maps_scenario_to_request(scenario: dict) -> None:
    cfg = era5_config_from_scenario(scenario)
    assert (cfg.latitude, cfg.longitude) == (8.27, 79.75)
    assert (cfg.start_year, cfg.end_year, cfg.reference_mode) == (2005, 2024, "fixed")
    # turbine identity comes from config, NOT the EN-171/23 defaults.
    assert cfg.turbine_model == "iea_reference_10mw"
    assert cfg.num_turbines == 15
    assert cfg.hub_height_m == 150.0
    assert cfg.strict_coverage is True


def test_adapter_rejects_hub_height_mismatch(scenario: dict) -> None:
    bad = copy.deepcopy(scenario)
    bad["resource"]["era5"]["hub_height_m"] = 120
    with pytest.raises(ValueError, match="hub_height_m"):
        era5_config_from_scenario(bad)


def test_adapter_requires_curve_key_no_default(scenario: dict) -> None:
    bad = copy.deepcopy(scenario)
    del bad["resource"]["power_curve"]["curve_key"]
    with pytest.raises(KeyError, match="curve_key"):
        era5_config_from_scenario(bad)


def test_adapter_fixed_mode_requires_explicit_years(scenario: dict) -> None:
    bad = copy.deepcopy(scenario)
    del bad["resource"]["era5"]["reference"]["start_year"]
    with pytest.raises(KeyError, match="start_year"):
        era5_config_from_scenario(bad)


# ── Weibull fit + drift ─────────────────────────────────────────────────────────


def test_fit_recovers_known_weibull() -> None:
    fit = fit_weibull_on_series(_weibull_series(8.32, 2.1), "ws_150m")
    assert fit.weibull_a == pytest.approx(8.32, abs=0.15)
    assert fit.weibull_k == pytest.approx(2.1, abs=0.06)
    # the reported std is the Weibull-implied std (consistent with A,k), not raw sample.
    assert fit.std_ws_ms == pytest.approx(weibull_std(fit.weibull_a, fit.weibull_k), abs=1e-9)
    assert fit.r_squared > 0.99


def test_fit_requires_enough_points() -> None:
    with pytest.raises(ValueError, match=">=2"):
        fit_weibull_on_series(pd.DataFrame({"ws_150m": [0.0, -1.0]}), "ws_150m")


def test_drift_within_and_outside_tolerance() -> None:
    near = weibull_drift(8.30, 2.10, 8.32, 2.10, tolerance_pct=5.0)
    assert near.within_tolerance is True
    far = weibull_drift(9.20, 2.50, 8.32, 2.10, tolerance_pct=5.0)
    assert far.within_tolerance is False
    assert far.a_drift_pct > 5.0


# ── end-to-end assessment (VALIDATE mode) ───────────────────────────────────────


def test_assessment_validates_without_mutating(scenario: dict) -> None:
    before = copy.deepcopy(scenario)
    res = build_arco_assessment(_weibull_series(8.30, 2.10), scenario, ws_column="ws_150m")
    # VALIDATE mode: declared baseline untouched.
    assert res["mode"] == "validate"
    assert scenario == before  # no mutation of the caller's scenario
    assert res["drift"]["within_tolerance"] is True
    # implied AEP comes from the analytic engine on the fitted Weibull, near 483.6.
    assert res["implied_aep"]["net_aep_gwh"] == pytest.approx(483.6, abs=8.0)


def test_assessment_implied_block_satisfies_wind_contract(scenario: dict) -> None:
    res = build_arco_assessment(_weibull_series(8.32, 2.10), scenario, ws_column="ws_150m")
    probe = copy.deepcopy(scenario)
    probe["resource"]["wind"] = res["implied_wind_block"]
    # the ARCO-produced wind block is a valid resource.wind handoff contract.
    validate_config_for_v14(probe, str(LENDER_CONFIG), ["wind"])


def test_large_drift_flags_out_of_tolerance(scenario: dict) -> None:
    res = build_arco_assessment(
        _weibull_series(6.0, 1.6), scenario, ws_column="ws_150m", drift_tolerance_pct=5.0
    )
    assert res["drift"]["within_tolerance"] is False  # a much weaker resource is caught


# ── end-to-end through a synthetic ERA5 NetCDF (xarray path) ─────────────────────


def test_end_to_end_from_synthetic_netcdf(scenario: dict, tmp_path) -> None:
    pytest.importorskip("xarray")
    import xarray as xr

    hours = 8760
    t = pd.date_range("2024-01-01", periods=hours, freq="h")
    rng = np.random.default_rng(11)
    ws100 = rng.weibull(2.2, hours) * 8.6
    ws10 = ws100 / (100.0 / 10.0) ** 0.14
    ds = xr.Dataset(
        {
            "u10": ("valid_time", ws10 * 0.8),
            "v10": ("valid_time", ws10 * 0.6),
            "u100": ("valid_time", ws100 * 0.8),
            "v100": ("valid_time", ws100 * 0.6),
            "sp": ("valid_time", np.full(hours, 101000.0)),
        },
        coords={"valid_time": t, "latitude": 8.27, "longitude": 79.75},
    )
    nc = tmp_path / "era5_ts.nc"
    ds.to_netcdf(nc)

    from wind_resource.era5_retrieval import build_hub_height_series

    cfg = era5_config_from_scenario(scenario)
    series = build_hub_height_series(nc, cfg)
    res = build_arco_assessment(series, scenario, ws_column="ws_150m")
    assert res["weibull_fit"]["weibull_k"] > 1.0
    assert res["weibull_fit"]["n_samples"] == hours
    assert "within_tolerance" in res["drift"]
