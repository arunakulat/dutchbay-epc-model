"""Tests for the bankable AEP engine (density / wake / IEC uncertainty)."""

from __future__ import annotations

import numpy as np
import pytest

from analytics.power_curves.oem_parser import parse_power_curve
from wind_resource.bankable_aep import (
    DEFAULT_TURBULENCE_INTENSITY,
    UncertaintyBudget,
    density_velocity_factor,
    exceedance_levels,
    gaussian_k_star,
    gross_aep_weibull,
    interannual_variability_drift,
    model_wake_loss,
    non_wake_retention,
    wake_loss_ti_sensitivity,
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
        wind_speed_ms=ws,
        power_kw=pw,
        weibull_a=A,
        weibull_k=K,
        rated_power_kw=rated,
        n_turbines=N_TURBINES,
    )
    dens = gross_aep_weibull(
        wind_speed_ms=ws,
        power_kw=pw,
        weibull_a=A,
        weibull_k=K,
        rated_power_kw=rated,
        n_turbines=N_TURBINES,
        rho_site_kgm3=RHO_SITE,
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
        "wake_loss_pct": 7.9,
        "availability_pct": 97.0,
        "electrical_loss_pct": 2.0,
        "curtailment_pct": 2.0,
        "other_pct": 1.0,
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
        wind_speed_ms=ws,
        power_kw=pw,
        thrust_coefficient=ct,
        rotor_diameter_m=ROTOR_M,
        hub_height_m=HUB_M,
        layout_x_m=x,
        layout_y_m=y,
        weibull_a=A,
        weibull_k=K,
        wind_rose_freq=rose,
        deficit_model="bastankhah",
    )
    assert res.n_turbines == N_TURBINES
    assert 3.0 < res.wake_loss_pct < 15.0  # modeled, not the flat 5% placeholder
    assert res.aep_wake_gwh < res.aep_gross_gwh


# ── WIND-6 (#484): computed-vs-assumed interannual-variability validation ──────
def test_interannual_variability_drift_within_tolerance() -> None:
    # computed 3.6% vs assumed default 4.0% -> 0.4 pp drift, within 1.5 pp, and assumed is
    # conservative (>= computed).
    chk = interannual_variability_drift(3.6)
    assert chk["assumed_iav_pct"] == 4.0
    assert chk["drift_pp"] == pytest.approx(-0.4, abs=1e-9)
    assert chk["within_tolerance"] is True
    assert chk["assumed_is_conservative"] is True


def test_interannual_variability_drift_flags_optimistic_assumption() -> None:
    # computed 6.0% vs assumed 4.0% -> the bankable P90 UNDERSTATES interannual risk.
    chk = interannual_variability_drift(6.0)
    assert chk["drift_pp"] == pytest.approx(2.0, abs=1e-9)
    assert chk["within_tolerance"] is False  # 2.0 pp > 1.5 pp tolerance
    assert chk["assumed_is_conservative"] is False


def test_interannual_variability_drift_is_validate_only() -> None:
    # The check must not mutate the budget default; calling it leaves 4.0% intact.
    before = UncertaintyBudget().interannual_variability_pct
    interannual_variability_drift(9.9, assumed_pct=before)
    assert UncertaintyBudget().interannual_variability_pct == before == 4.0


# ── #832: coastal-TI wake parametrization + sensitivity ─────────────────────────
def test_gaussian_k_star_closure() -> None:
    # Niayifar & Porte-Agel (2016): k* = 0.38*TI + 0.004; single source of truth.
    assert gaussian_k_star(0.10) == pytest.approx(0.042, abs=1e-12)
    assert gaussian_k_star(0.06) == pytest.approx(0.0268, abs=1e-12)
    # Default kernel TI reproduces today's exact k* -> the DEFAULT-OFF guarantee.
    assert DEFAULT_TURBULENCE_INTENSITY == 0.10
    assert gaussian_k_star(DEFAULT_TURBULENCE_INTENSITY) == pytest.approx(
        0.042, abs=1e-12
    )


def test_model_wake_loss_uses_shared_k_star_closure() -> None:
    # The engine's k* must equal the shared helper for any TI (no drift).
    pytest.importorskip("py_wake")
    ws, pw, ct = _iea_curve()
    x = np.zeros(N_TURBINES)
    y = np.arange(N_TURBINES) * 650.0
    rose = np.array([3, 3, 3, 4, 6, 9, 14, 20, 16, 9, 6, 4], dtype=float)
    res = model_wake_loss(
        wind_speed_ms=ws,
        power_kw=pw,
        thrust_coefficient=ct,
        rotor_diameter_m=ROTOR_M,
        hub_height_m=HUB_M,
        layout_x_m=x,
        layout_y_m=y,
        weibull_a=A,
        weibull_k=K,
        wind_rose_freq=rose,
        turbulence_intensity=0.08,
        deficit_model="bastankhah",
    )
    # deficit_model string carries the k* the model actually used.
    assert f"k*={gaussian_k_star(0.08):.4f}" in res.deficit_model


def _sens():
    ws, pw, ct = _iea_curve()
    x = np.zeros(N_TURBINES)
    y = np.arange(N_TURBINES) * 650.0
    rose = np.array([3, 3, 3, 4, 6, 9, 14, 20, 16, 9, 6, 4], dtype=float)
    return wake_loss_ti_sensitivity(
        wind_speed_ms=ws,
        power_kw=pw,
        thrust_coefficient=ct,
        rotor_diameter_m=ROTOR_M,
        hub_height_m=HUB_M,
        layout_x_m=x,
        layout_y_m=y,
        weibull_a=A,
        weibull_k=K,
        wind_rose_freq=rose,
        ti_grid=(0.06, 0.08, 0.12, 0.14),
        baseline_ti=0.10,
    )


def test_wake_ti_sensitivity_recomputes_and_discloses_slope() -> None:
    pytest.importorskip("py_wake")
    sens = _sens()
    # baseline TI is added to the grid even though it was not in ti_grid.
    tis = [p.turbulence_intensity for p in sens.points]
    assert tis == sorted(tis)  # ascending
    assert 0.10 in tis
    assert sens.baseline_ti == 0.10
    # The baseline point has exactly zero delta and matches the disclosed baseline loss.
    base = [p for p in sens.points if p.turbulence_intensity == 0.10][0]
    assert base.delta_wake_loss_pct == pytest.approx(0.0, abs=1e-12)
    assert base.wake_loss_pct == pytest.approx(sens.baseline_wake_loss_pct, abs=1e-12)
    # Each point's k* is the shared closure (no fabricated table).
    for p in sens.points:
        assert p.k_star == pytest.approx(
            gaussian_k_star(p.turbulence_intensity), abs=1e-12
        )
    # Honest, layout-specific direction: for this dense single row, LOWER TI -> HIGHER
    # wake loss (positive delta at TI < baseline), so the slope per +0.01 TI is negative.
    low = [p for p in sens.points if p.turbulence_intensity == 0.06][0]
    assert low.delta_wake_loss_pct > 0.0
    slope = sens.per_0p01_ti_pct()
    assert slope is not None and slope < 0.0


def test_wake_ti_sensitivity_slope_none_for_degenerate_grid() -> None:
    from wind_resource.bankable_aep import WakeTISensitivity, WakeTISensitivityPoint

    one = WakeTISensitivity(
        baseline_ti=0.10,
        baseline_wake_loss_pct=8.0,
        points=[WakeTISensitivityPoint(0.10, gaussian_k_star(0.10), 8.0, 0.0)],
    )
    assert one.per_0p01_ti_pct() is None
