"""Tests for the bankable AEP engine (density / wake / IEC uncertainty)."""

from __future__ import annotations

import numpy as np
import pytest

from analytics.power_curves.oem_parser import parse_power_curve
from wind_resource.bankable_aep import (
    UncertaintyBudget,
    density_velocity_factor,
    exceedance_levels,
    gross_aep_weibull,
    model_wake_loss,
    non_wake_retention,
)

# DutchBay site (Kalpitiya): ERA5-fitted Weibull + densities (was declared 8.32/2.1).
A, K = 8.199, 2.665
RHO_SITE, RHO_REF = 1.15, 1.225
N_TURBINES = 15
ROTOR_M, HUB_M = 198.0, 150.0


def _iea_curve():
    c = parse_power_curve("iea_reference_10mw", air_density_kgm3=RHO_REF)
    return (
        c["wind_speed_ms"].to_numpy(),
        c["power_kw"].to_numpy(),
        c["thrust_coefficient"].to_numpy(),
    )


def test_density_velocity_factor_iec() -> None:
    f = density_velocity_factor(RHO_SITE, RHO_REF)
    assert abs(f - (RHO_SITE / RHO_REF) ** (1 / 3)) < 1e-12
    assert 0.978 < f < 0.980  # ~0.979 leftward shift


def test_gross_aep_iea_10mw_density_corrected() -> None:
    ws, pw, _ = _iea_curve()
    rated = pw.max()
    ref = gross_aep_weibull(
        wind_speed_ms=ws, power_kw=pw, weibull_a=A, weibull_k=K,
        rated_power_kw=rated, n_turbines=N_TURBINES,
    )
    dens = gross_aep_weibull(
        wind_speed_ms=ws, power_kw=pw, weibull_a=A, weibull_k=K,
        rated_power_kw=rated, n_turbines=N_TURBINES, rho_site_kgm3=RHO_SITE,
    )
    # IEA 10MW on the ERA5-fitted site Weibull: ~0.414 ref, ~0.396 density-corrected.
    assert 0.40 < ref.capacity_factor < 0.42
    assert 0.39 < dens.capacity_factor < 0.41
    assert dens.capacity_factor < ref.capacity_factor  # density haircut
    assert dens.aep_gwh_farm > 540.0  # gross farm AEP (15 turbines)


def test_iec_uncertainty_build_up() -> None:
    budget = UncertaintyBudget()
    res = exceedance_levels(480.0, budget, life_years=20)
    assert res.p50_gwh == 480.0
    # ordering + plausible IEC spreads (P90/P50 ~0.87, not the old 0.80 haircut)
    assert res.p90_1yr_gwh < res.p75_gwh < res.p50_gwh
    assert res.p90_life_gwh > res.p90_1yr_gwh  # multi-year P90 is higher (IAV averaged)
    assert 0.85 < res.p90_1yr_gwh / res.p50_gwh < 0.89
    assert 9.0 < res.sigma_1yr_pct < 11.0


def test_non_wake_retention_excludes_wake() -> None:
    losses = {
        "wake_loss_pct": 7.9, "availability_pct": 97.0,
        "electrical_loss_pct": 2.0, "curtailment_pct": 2.0, "other_pct": 1.0,
    }
    f = non_wake_retention(losses)
    # 0.97 * 0.98 * 0.98 * 0.99 = 0.9224 (no wake term)
    assert abs(f - 0.97 * 0.98 * 0.98 * 0.99) < 1e-9


def test_pywake_granular_wake_15_turbines() -> None:
    pytest.importorskip("py_wake")
    ws, pw, ct = _iea_curve()
    x = np.zeros(N_TURBINES)
    y = np.arange(N_TURBINES) * 650.0  # single N-S row, 650 m spacing
    rose = np.array([3, 3, 3, 4, 6, 9, 14, 20, 16, 9, 6, 4], dtype=float)  # SW-dominant
    res = model_wake_loss(
        wind_speed_ms=ws, power_kw=pw, thrust_coefficient=ct,
        rotor_diameter_m=ROTOR_M, hub_height_m=HUB_M,
        layout_x_m=x, layout_y_m=y, weibull_a=A, weibull_k=K,
        wind_rose_freq=rose, deficit_model="bastankhah",
    )
    assert res.n_turbines == N_TURBINES
    assert 3.0 < res.wake_loss_pct < 15.0  # modeled, not the flat 5% placeholder
    assert res.aep_wake_gwh < res.aep_gross_gwh
