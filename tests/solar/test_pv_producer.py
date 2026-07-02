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


def test_solar10_cross_validation_against_independent_references() -> None:
    """SOLAR-10 (#485): cross-validate the pvlib producer against INDEPENDENT references.

    Beyond the generic plausibility band above, pin the modelled specific yield against named
    third-party estimates for this exact site so a silent model regression is caught:
      - SolarGIS PVOUT for Puttalam/Kalpitiya fixed-tilt c-Si ≈ 1524 kWh/kWp (the value the
        standalone solar-assessment report cites as its reference).
      - SAM / PVsyst tropical fixed-tilt c-Si typically land ~1450-1700 kWh/kWp at this GHI.
    The producer must agree with the SolarGIS reference within ±10% (a wide bankability band,
    not a tight pin — the references themselves differ by a few %). KPI-neutral: this reads the
    computed yield; it does not mutate the scenario, the frozen export, or any committed AEP.
    """
    SOLARGIS_PVOUT_KWH_PER_KWP = 1524.0  # SolarGIS reference for the site
    r = compute_solar_aep(_cfg())
    rel = (
        abs(r.specific_yield_kwh_per_kwp - SOLARGIS_PVOUT_KWH_PER_KWP)
        / SOLARGIS_PVOUT_KWH_PER_KWP
    )
    assert rel < 0.10, (
        f"modelled yield {r.specific_yield_kwh_per_kwp:.0f} kWh/kWp drifted {rel:.1%} from the "
        f"SolarGIS PVOUT reference {SOLARGIS_PVOUT_KWH_PER_KWP:.0f} — investigate before trusting."
    )
    # ...and inside the SAM/PVsyst tropical fixed-tilt c-Si envelope.
    assert 1450 < r.specific_yield_kwh_per_kwp < 1700, r.specific_yield_kwh_per_kwp


def test_is_deterministic() -> None:
    assert (
        compute_solar_aep(_cfg()).capacity_factor
        == compute_solar_aep(_cfg()).capacity_factor
    )


def test_cf_monotonic_in_ghi() -> None:
    low = compute_solar_aep(_cfg(annual_ghi_kwh_m2=1800.0)).capacity_factor
    high = compute_solar_aep(_cfg(annual_ghi_kwh_m2=2200.0)).capacity_factor
    assert high > low


def test_cf_invariant_aep_scales_with_capacity() -> None:
    small = compute_solar_aep(_cfg(dc_capacity_mw=10.0))
    big = compute_solar_aep(_cfg(dc_capacity_mw=100.0))
    # CF / yield are per-kWp -> capacity-invariant; AEP scales linearly with nameplate.
    assert small.capacity_factor == pytest.approx(big.capacity_factor, rel=1e-9)
    assert big.annual_energy_gwh == pytest.approx(
        10.0 * small.annual_energy_gwh, rel=1e-9
    )


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


# ── #604: scenario-YAML wiring for resource.solar.uncertainty ─────────────────

# A representative scenario block: two exceedance knobs + one budget-sigma override.
UNCERTAINTY_BLOCK = {
    "p50_haircut_pct": 2.0,
    "correlation": 0.2,
    "life_years": 25,
    "ghi_dataset_pct": 5.0,
}


def test_from_scenario_accepts_uncertainty_block() -> None:
    cfg = SolarResourceConfig.from_scenario(
        {"resource": {"solar": {**KALPITIYA, "uncertainty": dict(UNCERTAINTY_BLOCK)}}}
    )
    assert cfg.uncertainty == UNCERTAINTY_BLOCK


def test_scenario_uncertainty_block_reaches_exceedance_end_to_end() -> None:
    """A scenario-declared block drives the exceedance build-up (#604 wiring)."""
    from solar_resource.exceedance import (
        SolarUncertaintyBudget,
        exceedance_levels_solar,
    )

    scenario = {
        "resource": {"solar": {**KALPITIYA, "uncertainty": dict(UNCERTAINTY_BLOCK)}}
    }
    cfg = SolarResourceConfig.from_scenario(scenario)
    r = compute_solar_aep(cfg, emit_exceedance=True)
    assert r.exceedance is not None
    expected = exceedance_levels_solar(
        r.annual_energy_gwh,
        SolarUncertaintyBudget(ghi_dataset_pct=5.0),
        life_years=25,
        p50_haircut_pct=2.0,
        correlation=0.2,
    )
    assert r.exceedance == expected
    # The 2% haircut applied inside the build-up; the deterministic P50 is untouched.
    assert r.exceedance.p50_gwh == pytest.approx(0.98 * r.annual_energy_gwh)
    assert r.exceedance.life_years == 25


def test_explicit_kwarg_overrides_scenario_uncertainty_block() -> None:
    # Precedence: explicit keyword argument > config block > module default.
    cfg = SolarResourceConfig.from_scenario(
        {"resource": {"solar": {**KALPITIYA, "uncertainty": {"p50_haircut_pct": 2.0}}}}
    )
    r = compute_solar_aep(cfg, emit_exceedance=True, p50_haircut_pct=5.0)
    assert r.exceedance is not None
    assert r.exceedance.p50_gwh == pytest.approx(0.95 * r.annual_energy_gwh)


def test_no_uncertainty_block_is_default_identity() -> None:
    """A config WITHOUT the block behaves byte-identically to the pre-wiring defaults."""
    r = compute_solar_aep(_cfg(), emit_exceedance=True)
    assert r == compute_solar_aep(_cfg(uncertainty=None), emit_exceedance=True)
    assert r.exceedance is not None
    # No haircut is introduced silently (the wind #587 no-EYA default does NOT port),
    # and the life window stays at the 20-year default.
    assert r.exceedance.p50_gwh == pytest.approx(r.annual_energy_gwh)
    assert r.exceedance.life_years == 20


def test_deterministic_p50_unchanged_by_uncertainty_block() -> None:
    # The block only parameterises the OPT-IN exceedance build-up; the deterministic
    # P50 contract (and the default emit_exceedance=False) is unchanged by it.
    base = compute_solar_aep(_cfg())
    with_block = compute_solar_aep(_cfg(uncertainty={"p50_haircut_pct": 5.0}))
    assert with_block.annual_energy_gwh == base.annual_energy_gwh
    assert with_block.capacity_factor == base.capacity_factor
    assert with_block.exceedance is None  # emit_exceedance remains opt-in


def test_uncertainty_typo_key_rejected_at_construction() -> None:
    # CESSPIT pre-flight: the typo fails loud when the config is BUILT, not at the
    # first (opt-in) emit_exceedance consumption.
    with pytest.raises(KeyError, match="unknown field"):
        _cfg(uncertainty={"soling_pct": 2.0})  # typo of soiling_pct


def test_uncertainty_typo_key_rejected_from_scenario() -> None:
    block = {**KALPITIYA, "uncertainty": {"soling_pct": 2.0}}
    with pytest.raises(KeyError, match="unknown field"):
        SolarResourceConfig.from_scenario({"resource": {"solar": block}})


def test_uncertainty_non_mapping_rejected() -> None:
    with pytest.raises(TypeError, match="uncertainty must be a mapping"):
        _cfg(uncertainty=3.0)


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
    declared generation.technologies.solar.capacity_factor P50 via the pvlib producer.
    """
    import pathlib

    import yaml

    repo_root = pathlib.Path(__file__).resolve().parents[2]
    scenario = yaml.safe_load(
        (repo_root / "scenarios" / "dutchbay_hybrid_windsolar_2025Q4.yaml").read_text()
    )
    declared = scenario["generation"]["technologies"]["solar"]["capacity_factor"]
    cfg = SolarResourceConfig.from_scenario(scenario)
    v = validate_declared_solar_cf(cfg, declared_cf=declared, tolerance_pct=15.0)
    assert (
        v.within_tolerance
    ), f"declared {declared} vs producer {v.modelled_cf:.3f} drifted {v.relative_diff:.1%}"


# ── SOLAR-6/12 (#529): TMY ingest + hourly thermal ────────────────────────────
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from solar_resource.pv_producer import _load_tmy  # noqa: E402

_FROZEN_TMY = "inputs/solar_tmy/kalpitiya_pvgis_tmy_8.27N_79.75E.csv"


def _write_tmy(path: str, *, temp_c: float = 27.0, wind: float = 4.5) -> str:
    """Write a synthetic 8760-row hourly TMY CSV (a simple diurnal GHI shape)."""
    idx = pd.date_range("1990-01-01", periods=8760, freq="1h", tz="UTC")
    hour = idx.hour.to_numpy()
    ghi = np.clip(900.0 * np.sin((hour - 6) / 12.0 * np.pi), 0.0, None)  # daytime bell
    df = pd.DataFrame(
        {
            "ghi": ghi,
            "dni": ghi * 0.7,
            "dhi": ghi * 0.3,
            "temp_air": np.full(8760, temp_c),
            "wind_speed": np.full(8760, wind),
        },
        index=idx,
    )
    df.index.name = "time"
    df.to_csv(path)
    return path


def test_frozen_kalpitiya_tmy_repins_solar_cf() -> None:
    """Regression pin: the committed frozen PVGIS TMY yields the re-baselined P50 (#529)."""
    r = compute_solar_aep(_cfg(tmy_path=_FROZEN_TMY))
    assert r.capacity_factor == pytest.approx(0.1685, abs=0.001)
    assert r.annual_energy_gwh == pytest.approx(73.8, abs=0.3)


def test_tmy_path_changes_result_vs_clearsky() -> None:
    """The TMY path produces a different (here lower) CF than the clear-sky default."""
    clearsky = compute_solar_aep(_cfg()).capacity_factor
    tmy = compute_solar_aep(_cfg(tmy_path=_FROZEN_TMY)).capacity_factor
    assert tmy < clearsky  # real GHI 1871 < declared 2000, + hot-hour thermal


def test_solar12_hourly_thermal_hotter_tmy_lowers_cf(tmp_path) -> None:
    """SOLAR-12: a hotter hourly ambient series yields a lower CF (cell-temp losses)."""
    cool = _write_tmy(str(tmp_path / "cool.csv"), temp_c=20.0)
    hot = _write_tmy(str(tmp_path / "hot.csv"), temp_c=40.0)
    cf_cool = compute_solar_aep(_cfg(tmy_path=cool)).capacity_factor
    cf_hot = compute_solar_aep(_cfg(tmy_path=hot)).capacity_factor
    assert cf_hot < cf_cool


def test_clearsky_path_byte_identical_without_tmy() -> None:
    """No tmy_path -> the clear-sky path is unchanged (the default is byte-identical)."""
    a = compute_solar_aep(_cfg(tmy_path=None)).capacity_factor
    b = compute_solar_aep(_cfg()).capacity_factor
    assert a == b


def test_load_tmy_missing_file_raises() -> None:
    with pytest.raises(FileNotFoundError, match="TMY file not found"):
        _load_tmy("inputs/solar_tmy/does_not_exist.csv")


def test_load_tmy_missing_column_raises(tmp_path) -> None:
    idx = pd.date_range("1990-01-01", periods=8760, freq="1h", tz="UTC")
    df = pd.DataFrame({"ghi": 1.0, "dni": 1.0, "dhi": 1.0, "temp_air": 25.0}, index=idx)
    p = str(tmp_path / "nowind.csv")
    df.to_csv(p)
    with pytest.raises(ValueError, match="missing required column"):
        _load_tmy(p)


def test_load_tmy_wrong_row_count_raises(tmp_path) -> None:
    idx = pd.date_range("1990-01-01", periods=100, freq="1h", tz="UTC")
    df = pd.DataFrame(
        {"ghi": 1.0, "dni": 1.0, "dhi": 1.0, "temp_air": 25.0, "wind_speed": 2.0},
        index=idx,
    )
    p = str(tmp_path / "short.csv")
    df.to_csv(p)
    with pytest.raises(ValueError, match="expected 8760"):
        _load_tmy(p)


def test_load_tmy_non_finite_raises(tmp_path) -> None:
    p = _write_tmy(str(tmp_path / "nan.csv"))
    df = pd.read_csv(p, index_col=0, parse_dates=True)
    df.iloc[5, df.columns.get_loc("temp_air")] = np.nan
    df.to_csv(p)
    with pytest.raises(ValueError, match="non-finite"):
        _load_tmy(p)


def test_from_scenario_passes_tmy_path() -> None:
    cfg = SolarResourceConfig.from_scenario(
        {"resource": {"solar": {**KALPITIYA, "tmy_path": _FROZEN_TMY}}}
    )
    assert cfg.tmy_path == _FROZEN_TMY


def test_load_tmy_negative_irradiance_raises(tmp_path) -> None:
    p = _write_tmy(str(tmp_path / "neg.csv"))
    df = pd.read_csv(p, index_col=0, parse_dates=True)
    df.iloc[12, df.columns.get_loc("ghi")] = -5.0
    df.to_csv(p)
    with pytest.raises(ValueError, match="negative irradiance"):
        _load_tmy(p)


def test_load_tmy_non_monotonic_index_raises(tmp_path) -> None:
    p = _write_tmy(str(tmp_path / "dup.csv"))
    df = pd.read_csv(p, index_col=0, parse_dates=True)
    idx = df.index.to_list()
    idx[1] = idx[0]  # duplicate timestamp -> non-unique / non-monotonic
    df.index = pd.DatetimeIndex(idx)
    df.to_csv(p)
    with pytest.raises(ValueError, match="unique and monotonically increasing"):
        _load_tmy(p)
