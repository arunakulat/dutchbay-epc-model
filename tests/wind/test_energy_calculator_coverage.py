"""Coverage tests for ``wind_resource.energy_calculator``.

Targets the branches the IEC p-values regression test does not exercise:
the gross/net build-up, the manual power-curve path, monthly energy,
revenue projections, the full assessment, and the documented ``__init__`` /
config-loader raises. No network and no live CDS/ERA5 access — config-failure
paths are driven with ``tmp_path`` YAML files, never real Copernicus calls.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from wind_resource import EnergyCalculator

# A simple, monotone power curve: zero below cut-in, linear ramp to a 1000 kW
# rated plateau, then zero past cut-out. ``max(power)`` => rated_capacity 1000.
_MANUAL_CURVE = {
    "ws": [0.0, 3.0, 12.0, 25.0, 25.1],
    "power": [0.0, 0.0, 1000.0, 1000.0, 0.0],
}


def _df(speed: float = 10.0, n: int = 8760) -> pd.DataFrame:
    """Hourly wind series with a real DatetimeIndex (needed for monthly grouping)."""
    idx = pd.date_range("2020-01-01", periods=n, freq="h")
    return pd.DataFrame({"ws_150m": np.full(n, speed)}, index=idx)


def _calc(speed: float = 10.0, num_turbines: int = 10) -> EnergyCalculator:
    return EnergyCalculator(
        df=_df(speed),
        ws_column="ws_150m",
        power_curve=_MANUAL_CURVE,
        num_turbines=num_turbines,
    )


# ---------------------------------------------------------------------------
# __init__ validation raises
# ---------------------------------------------------------------------------


def test_init_requires_turbine_or_curve() -> None:
    with pytest.raises(ValueError, match="turbine_model.*or.*power_curve"):
        EnergyCalculator(df=_df(), num_turbines=10)


def test_init_requires_num_turbines() -> None:
    with pytest.raises(ValueError, match="num_turbines is required"):
        EnergyCalculator(df=_df(), power_curve=_MANUAL_CURVE)


def test_init_rejects_missing_ws_column() -> None:
    df = _df().rename(columns={"ws_150m": "other"})
    with pytest.raises(ValueError, match="ws_150m.*not found"):
        EnergyCalculator(df=df, power_curve=_MANUAL_CURVE, num_turbines=10)


# ---------------------------------------------------------------------------
# Manual power-curve loader (_load_power_curve_manual)
# ---------------------------------------------------------------------------


def test_manual_curve_sets_rated_capacity_to_peak() -> None:
    calc = _calc()
    # rated_capacity is the max of the manual power array.
    assert calc.rated_capacity == pytest.approx(1000.0)
    # The interpolant is wired and evaluates the plateau and the out-of-range tails.
    assert float(calc.power_curve_func(12.0)) == pytest.approx(1000.0)
    assert float(calc.power_curve_func(100.0)) == pytest.approx(0.0)
    assert float(calc.power_curve_func(-5.0)) == pytest.approx(0.0)


def test_manual_curve_requires_ws_and_power_keys() -> None:
    with pytest.raises(ValueError, match="must have 'ws' and 'power'"):
        EnergyCalculator(
            df=_df(), power_curve={"ws": [1.0, 2.0]}, num_turbines=10
        )


def test_manual_curve_length_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="same length"):
        EnergyCalculator(
            df=_df(),
            power_curve={"ws": [1.0, 2.0, 3.0], "power": [0.0, 1.0]},
            num_turbines=10,
        )


# ---------------------------------------------------------------------------
# Config loader raises (_load_config / _load_power_curve_from_config)
# ---------------------------------------------------------------------------


def test_missing_config_file_raises(tmp_path: Path) -> None:
    missing = tmp_path / "nope.yaml"
    with pytest.raises(FileNotFoundError, match="Config file not found"):
        EnergyCalculator(
            df=_df(),
            power_curve=_MANUAL_CURVE,
            num_turbines=10,
            config_path=str(missing),
        )


def test_config_missing_required_key_raises(tmp_path: Path) -> None:
    # Valid YAML but missing the 'p_levels' / 'revenue' structure => KeyError.
    bad = tmp_path / "era5_config.yaml"
    bad.write_text(yaml.safe_dump({"losses": {"availability": 0.97}}))
    with pytest.raises(KeyError, match="Missing required config key"):
        EnergyCalculator(
            df=_df(),
            power_curve=_MANUAL_CURVE,
            num_turbines=10,
            config_path=str(bad),
        )


def _good_config(path: Path) -> Path:
    cfg = {
        "losses": {"availability": 0.97, "wake": 0.95},
        "p_levels": {"p50": 1.00},
        "revenue": {
            "default_tariff_lkr_kwh": 20.30,
            "default_exchange_rate_lkr_usd": 333.79,
            "ppa_years": 20,
        },
    }
    path.write_text(yaml.safe_dump(cfg))
    return path


def test_missing_power_curves_file_raises(tmp_path: Path) -> None:
    cfg = _good_config(tmp_path / "era5_config.yaml")
    missing_curves = tmp_path / "no_curves.yaml"
    with pytest.raises(FileNotFoundError, match="Power curves file not found"):
        EnergyCalculator(
            df=_df(),
            turbine_model="iea_reference_10mw",
            num_turbines=10,
            config_path=str(cfg),
            power_curves_path=str(missing_curves),
        )


def test_unknown_turbine_model_raises(tmp_path: Path) -> None:
    cfg = _good_config(tmp_path / "era5_config.yaml")
    curves = tmp_path / "power_curves.yaml"
    curves.write_text(
        yaml.safe_dump(
            {
                "real_model": {
                    "rated_capacity_kw": 5000,
                    "cut_in": 3.0,
                    "rated": 12.0,
                    "cut_out": 25.0,
                    "power_curve": {"ws": [3.0, 12.0], "power": [0.0, 5000.0]},
                }
            }
        )
    )
    with pytest.raises(KeyError, match="not found in power_curves.yaml"):
        EnergyCalculator(
            df=_df(),
            turbine_model="does_not_exist",
            num_turbines=10,
            config_path=str(cfg),
            power_curves_path=str(curves),
        )


def test_turbine_model_loaded_from_config_files(tmp_path: Path) -> None:
    cfg = _good_config(tmp_path / "era5_config.yaml")
    curves = tmp_path / "power_curves.yaml"
    curves.write_text(
        yaml.safe_dump(
            {
                "tmodel": {
                    "rated_capacity_kw": 4000,
                    "cut_in": 3.0,
                    "rated": 12.0,
                    "cut_out": 25.0,
                    "power_curve": {
                        "ws": [0.0, 3.0, 12.0, 25.0, 25.1],
                        "power": [0.0, 0.0, 4000.0, 4000.0, 0.0],
                    },
                }
            }
        )
    )
    calc = EnergyCalculator(
        df=_df(),
        turbine_model="tmodel",
        num_turbines=10,
        config_path=str(cfg),
        power_curves_path=str(curves),
    )
    assert calc.rated_capacity == 4000
    assert float(calc.power_curve_func(12.0)) == pytest.approx(4000.0)


# ---------------------------------------------------------------------------
# Loss factor + gross AEP
# ---------------------------------------------------------------------------


def test_total_loss_factor_is_product_of_losses() -> None:
    calc = _calc()
    expected = 1.0
    for v in calc.losses.values():
        expected *= v
    assert calc._calculate_total_loss() == pytest.approx(expected)
    assert 0.0 < calc._calculate_total_loss() < 1.0


def test_gross_aep_at_rated_wind() -> None:
    # At 12 m/s the curve sits on the 1000 kW plateau, so CF is ~100% and AEP
    # is rated_capacity * 8760h * num_turbines / 1000.
    calc = _calc(speed=12.0, num_turbines=10)
    gross = calc.calculate_gross_aep()
    assert gross["average_power_kw"] == pytest.approx(1000.0)
    assert gross["capacity_factor_gross"] == pytest.approx(100.0)
    assert gross["single_turbine_aep_mwh"] == pytest.approx(1000.0 * 8760 / 1000)
    assert gross["windfarm_aep_mwh"] == pytest.approx(
        gross["single_turbine_aep_mwh"] * 10
    )


# ---------------------------------------------------------------------------
# Net AEP (gross/net build-up branch + the gross_aep_mwh=None path)
# ---------------------------------------------------------------------------


def test_net_aep_computes_gross_when_none() -> None:
    calc = _calc(speed=12.0)
    net = calc.calculate_net_aep()  # gross_aep_mwh is None => calc.calculate_gross_aep()
    total_loss = calc._calculate_total_loss()
    expected_p50 = net["gross_aep_mwh"] * total_loss * calc.p_levels["p50"]
    assert net["net_aep_p50_mwh"] == pytest.approx(expected_p50)
    assert net["total_loss_factor"] == pytest.approx(total_loss)
    assert net["individual_losses"] is calc.losses
    # Exceedance ordering and CF derivation.
    assert 0 < net["net_aep_p90_mwh"] < net["net_aep_p75_mwh"] < net["net_aep_p50_mwh"]
    total_cap_mw = (calc.rated_capacity * calc.num_turbines) / 1000
    assert net["capacity_factor_net_p50"] == pytest.approx(
        net["net_aep_p50_mwh"] / (total_cap_mw * 8760) * 100
    )


def test_net_aep_honours_supplied_gross() -> None:
    calc = _calc(speed=12.0)
    net = calc.calculate_net_aep(gross_aep_mwh=100_000.0)
    assert net["gross_aep_mwh"] == pytest.approx(100_000.0)
    expected_p50 = 100_000.0 * calc._calculate_total_loss() * calc.p_levels["p50"]
    assert net["net_aep_p50_mwh"] == pytest.approx(expected_p50)


# ---------------------------------------------------------------------------
# Monthly energy profile (calculate_monthly_energy)
# ---------------------------------------------------------------------------


def test_monthly_energy_profile_shape_and_values() -> None:
    calc = _calc(speed=12.0, num_turbines=10)
    monthly = calc.calculate_monthly_energy()
    assert list(monthly.columns) == ["month", "energy_mwh", "cf_percent"]
    # 8760 hourly rows starting Jan 1 cover all 12 calendar months.
    assert sorted(monthly["month"].tolist()) == list(range(1, 13))
    # At a constant 12 m/s (rated plateau) every month is ~100% CF.
    assert monthly["cf_percent"].min() == pytest.approx(100.0, abs=1e-6)
    # energy = avg_power(1000kW) * 730h * 10 turbines / 1000 = 7300 MWh.
    assert monthly["energy_mwh"].iloc[0] == pytest.approx(1000.0 * 730 * 10 / 1000)


# ---------------------------------------------------------------------------
# Revenue (calculate_revenue) — config defaults and explicit overrides
# ---------------------------------------------------------------------------


def test_revenue_uses_config_defaults() -> None:
    calc = _calc(speed=12.0)
    net = calc.calculate_net_aep()
    rev = calc.calculate_revenue(net)
    assert rev["tariff_lkr_per_kwh"] == pytest.approx(calc.tariff)
    assert rev["exchange_rate_lkr_usd"] == pytest.approx(calc.exchange_rate)
    assert rev["ppa_years"] == calc.ppa_years
    expected_annual_p50 = (
        net["net_aep_p50_mwh"] * 1000 * calc.tariff / calc.exchange_rate
    )
    assert rev["annual_revenue_p50_usd"] == pytest.approx(expected_annual_p50)
    assert rev["cumulative_revenue_p50_usd"] == pytest.approx(
        expected_annual_p50 * calc.ppa_years
    )
    # Exceedance ordering carries through to revenue.
    assert (
        rev["annual_revenue_p90_usd"]
        < rev["annual_revenue_p75_usd"]
        < rev["annual_revenue_p50_usd"]
    )


def test_revenue_respects_explicit_overrides() -> None:
    calc = _calc(speed=12.0)
    net = calc.calculate_net_aep()
    rev = calc.calculate_revenue(
        net, tariff_lkr_per_kwh=30.0, exchange_rate_lkr_usd=300.0
    )
    assert rev["tariff_lkr_per_kwh"] == pytest.approx(30.0)
    assert rev["exchange_rate_lkr_usd"] == pytest.approx(300.0)
    expected = net["net_aep_p75_mwh"] * 1000 * 30.0 / 300.0
    assert rev["annual_revenue_p75_usd"] == pytest.approx(expected)


# ---------------------------------------------------------------------------
# Full assessment (generate_complete_assessment)
# ---------------------------------------------------------------------------


def test_generate_complete_assessment_is_consistent() -> None:
    calc = _calc(speed=12.0, num_turbines=10)
    out = calc.generate_complete_assessment()
    assert set(out) == {"gross_aep", "net_aep", "monthly_profile", "revenue", "config"}
    # net_aep inside the bundle is built off the bundle's gross windfarm AEP.
    assert out["net_aep"]["gross_aep_mwh"] == pytest.approx(
        out["gross_aep"]["windfarm_aep_mwh"]
    )
    # monthly_profile is the records form of the monthly DataFrame.
    assert isinstance(out["monthly_profile"], list)
    assert len(out["monthly_profile"]) == 12
    assert set(out["monthly_profile"][0]) == {"month", "energy_mwh", "cf_percent"}
    # config echoes the wiring.
    assert out["config"]["num_turbines"] == 10
    assert out["config"]["rated_capacity_kw"] == pytest.approx(1000.0)
    assert out["config"]["total_capacity_mw"] == pytest.approx(1000.0 * 10 / 1000)
