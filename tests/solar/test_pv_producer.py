#!/usr/bin/env python
"""Tests for the pvlib solar-resource producer (solar_resource.pv_producer).

Gated behind ``pytest.importorskip('pvlib')`` (CASPER) — like the [wind] PyWake tests and
the [report] WeasyPrint tests, this whole module skips when the optional [solar] extra is
absent (e.g. the default CI install), so the base finance stack never depends on pvlib.

Context:
    Item 3 — optional pvlib solar producer for the multi-tech hybrid.
"""

from __future__ import annotations

import sys

import pytest

pytest.importorskip("pvlib")  # the [solar] extra; skip the whole module if absent

from solar_resource.pv_producer import (  # noqa: E402
    SolarResourceConfig,
    _require_pvlib,
    compute_solar_aep,
    validate_declared_solar_cf,
)

# Kalpitiya / Puttalam reference PV site (matches the hybrid scenario's solar block).
KALPITIYA = dict(
    latitude=8.27,
    longitude=79.75,
    timezone="Asia/Colombo",
    altitude_m=5.0,
    annual_ghi_kwh_m2=2000.0,  # measured Puttalam annual GHI (~5.5 kWh/m²/day)
    dc_capacity_mw=50.0,
    tilt_deg=8.0,
    azimuth_deg=180.0,
)


def _cfg(**overrides: object) -> SolarResourceConfig:
    return SolarResourceConfig(**{**KALPITIYA, **overrides})  # type: ignore[arg-type]


# ── The CASPER optional-dep guard ─────────────────────────────────────────────


def test_require_pvlib_returns_module() -> None:
    assert _require_pvlib().__name__ == "pvlib"


def test_require_pvlib_raises_actionable_error(monkeypatch: pytest.MonkeyPatch) -> None:
    # Force `import pvlib` to fail even though it is installed (sys.modules[...] = None).
    monkeypatch.setitem(sys.modules, "pvlib", None)
    with pytest.raises(RuntimeError, match=r"\[solar\] extra"):
        _require_pvlib()


# ── The producer ──────────────────────────────────────────────────────────────


def test_kalpitiya_cf_and_yield_are_realistic() -> None:
    r = compute_solar_aep(_cfg())
    # Puttalam utility-scale fixed-tilt PV: CF ~0.17-0.21, specific yield ~1450-1750 kWh/kWp.
    assert 0.15 < r.capacity_factor < 0.22, r.capacity_factor
    assert 1400 < r.specific_yield_kwh_per_kwp < 1800, r.specific_yield_kwh_per_kwp
    # AEP = CF x nameplate x 8760: 50 MWp x ~0.18 x 8.760 ≈ ~78 GWh.
    assert 70 < r.annual_energy_gwh < 90, r.annual_energy_gwh
    assert 0.7 < r.clearsky_scale < 0.95  # clear-sky index for a sunny tropical site


def test_is_deterministic() -> None:
    assert compute_solar_aep(_cfg()).capacity_factor == compute_solar_aep(_cfg()).capacity_factor


def test_cf_monotonic_in_ghi() -> None:
    low = compute_solar_aep(_cfg(annual_ghi_kwh_m2=1800.0)).capacity_factor
    high = compute_solar_aep(_cfg(annual_ghi_kwh_m2=2200.0)).capacity_factor
    assert high > low


def test_cf_invariant_aep_scales_with_capacity() -> None:
    small = compute_solar_aep(_cfg(dc_capacity_mw=10.0))
    big = compute_solar_aep(_cfg(dc_capacity_mw=100.0))
    # CF / yield are per-kWp -> capacity-invariant; AEP scales linearly with nameplate.
    assert small.capacity_factor == pytest.approx(big.capacity_factor, rel=1e-9)
    assert big.annual_energy_gwh == pytest.approx(10.0 * small.annual_energy_gwh, rel=1e-9)


# ── Config-first parsing + validation ─────────────────────────────────────────


def test_from_scenario_resource_solar_block() -> None:
    scenario = {"resource": {"solar": dict(KALPITIYA)}}
    cfg = SolarResourceConfig.from_scenario(scenario)
    assert cfg.dc_capacity_mw == 50.0
    assert 0.15 < compute_solar_aep(cfg).capacity_factor < 0.22


def test_from_scenario_missing_block_raises() -> None:
    with pytest.raises(KeyError, match="no resource.solar"):
        SolarResourceConfig.from_scenario({"resource": {}})


def test_from_scenario_missing_required_field_raises() -> None:
    block = {k: v for k, v in KALPITIYA.items() if k != "annual_ghi_kwh_m2"}
    with pytest.raises(KeyError, match="annual_ghi_kwh_m2"):
        SolarResourceConfig.from_scenario({"resource": {"solar": block}})


@pytest.mark.parametrize(
    "bad",
    [
        {"dc_capacity_mw": 0.0},
        {"dc_capacity_mw": -5.0},
        {"annual_ghi_kwh_m2": 0.0},
        {"latitude": 120.0},
        {"longitude": -200.0},
        {"dc_ac_ratio": 0.0},
        {"system_loss_pct": 100.0},
        {"inverter_eff_nom": 0.0},  # would be a raw ZeroDivisionError without the guard
        {"inverter_eff_nom": 1.5},
        {"azimuth_deg": 400.0},
        {"tilt_deg": 120.0},
    ],
)
def test_config_rejects_invalid_inputs(bad: dict) -> None:
    with pytest.raises(ValueError):
        _cfg(**bad)


def test_from_scenario_rejects_unknown_key() -> None:
    # CESSPIT: a typo'd field must fail loud, not silently revert to a default.
    block = {**KALPITIYA, "system_los_pct": 14.0}  # typo of system_loss_pct
    with pytest.raises(KeyError, match="unknown field"):
        SolarResourceConfig.from_scenario({"resource": {"solar": block}})


# ── VALIDATE a declared P50 CF against the producer (no overwrite) ─────────────


def test_validate_declared_cf_within_tolerance() -> None:
    v = validate_declared_solar_cf(_cfg(), declared_cf=0.20, tolerance_pct=15.0)
    assert v.within_tolerance
    assert v.modelled_cf == pytest.approx(v.result.capacity_factor)


def test_validate_declared_cf_flags_drift() -> None:
    # A wildly optimistic declared CF (0.35) is flagged, not silently accepted.
    v = validate_declared_solar_cf(_cfg(), declared_cf=0.35, tolerance_pct=10.0)
    assert not v.within_tolerance
    assert v.relative_diff > 0.10


def test_validate_declared_cf_rejects_nonpositive() -> None:
    with pytest.raises(ValueError, match="declared_cf must be"):
        validate_declared_solar_cf(_cfg(), declared_cf=0.0)


# ── End-to-end against the committed hybrid scenario ──────────────────────────


def test_hybrid_scenario_solar_block_validates_declared_p50() -> None:
    """The committed hybrid scenario's resource.solar block reproduces (~within tol) the
    declared generation.technologies.solar.capacity_factor P50 via the pvlib producer."""
    import pathlib

    import yaml

    repo_root = pathlib.Path(__file__).resolve().parents[2]
    scenario = yaml.safe_load(
        (repo_root / "scenarios" / "dutchbay_hybrid_windsolar_2025Q4.yaml").read_text()
    )
    declared = scenario["generation"]["technologies"]["solar"]["capacity_factor"]
    cfg = SolarResourceConfig.from_scenario(scenario)
    v = validate_declared_solar_cf(cfg, declared_cf=declared, tolerance_pct=15.0)
    assert v.within_tolerance, (
        f"declared {declared} vs producer {v.modelled_cf:.3f} drifted {v.relative_diff:.1%}"
    )
