"""Wind artifact hygiene (#618): version strings, ``resource.uncertainty.*``
plumbing, and the IEC 61400-12-1 air-density correction on the timeseries path.

Three regression families:

1. Version strings — ``wind_resource`` derives every stamped/logged version from
   ``analytics.run_manifest.engine_version()`` (the repo ``VERSION`` file); the
   stale hardcoded ``1.0.0``/``1.1.0`` literals cannot creep back (source scan).
2. Uncertainty plumbing — ``EnergyCalculator`` builds its exceedance budget from a
   ``resource.uncertainty.*`` mapping via the SHARED ``budget_from_mapping`` parser;
   the no-config default is byte-identical to the previous hardcoded
   ``UncertaintyBudget()`` call, and a declared ``p50_haircut_pct`` is NOT applied
   (kernel 0.0 pinned pending the user-gated #653 policy decision). The parser
   fails loud on unknown/typo'd sigma keys (#683) — the caller-consumed
   ``p50_haircut_pct``/``correlation``/``life_years`` knobs are allowlisted.
3. Air density — ``calculate_gross_aep`` applies the bankable path's IEC 61400-12-1
   velocity correction when a site density is supplied, and is exactly identity
   when it is not.

No network, no CDS: the fetcher test drives ``_save_metadata`` directly with a
tmp_path config (same pattern as tests/wind/test_era5_fetcher_coverage.py).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import wind_resource
from analytics.run_manifest import engine_version
from wind_resource import EnergyCalculator
from wind_resource.bankable_aep import (
    UncertaintyBudget,
    budget_from_mapping,
    density_velocity_factor,
    exceedance_levels,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

# Monotone manual curve: linear ramp 3 -> 12 m/s to a 1000 kW plateau (same shape
# as tests/wind/test_energy_calculator_coverage.py), so a downward velocity shift
# strictly reduces power in the ramp region.
_MANUAL_CURVE = {
    "ws": [0.0, 3.0, 12.0, 25.0, 25.1],
    "power": [0.0, 0.0, 1000.0, 1000.0, 0.0],
}


def _df(speed: float = 10.0, n: int = 8760) -> pd.DataFrame:
    idx = pd.date_range("2020-01-01", periods=n, freq="h")
    return pd.DataFrame({"ws_150m": np.full(n, speed)}, index=idx)


def _calc(**kwargs: object) -> EnergyCalculator:
    return EnergyCalculator(
        df=_df(),
        ws_column="ws_150m",
        power_curve=_MANUAL_CURVE,
        num_turbines=10,
        **kwargs,  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# 1. Version strings derive from the repo VERSION file
# ---------------------------------------------------------------------------


def test_package_version_tracks_engine_version() -> None:
    assert wind_resource.__version__ == engine_version()
    assert wind_resource.__version__ != "1.0.0"
    # Sanity: engine_version really is the VERSION file, not a fallback.
    assert engine_version() == (REPO_ROOT / "VERSION").read_text().strip()


def test_no_stale_version_literals_in_wind_resource() -> None:
    """Greppable fence: the stale hardcoded module versions must stay removed.

    rglob, not glob (#683): the fence must keep covering wind_resource/ if it
    ever grows subpackages — a non-recursive scan silently stops fencing them.
    """
    stale = re.compile(
        r"""1\.[01]\.0\s*\(CCCDIR|__version__\s*=\s*"1\.|v1\.[01]\.0\s"""
    )
    offenders = [
        str(p.relative_to(REPO_ROOT / "wind_resource"))
        for p in sorted((REPO_ROOT / "wind_resource").rglob("*.py"))
        if "__pycache__" not in p.parts and stale.search(p.read_text())
    ]
    assert offenders == [], f"stale version literals in: {offenders}"


def test_era5_fetcher_metadata_version_is_engine_version(tmp_path: Path) -> None:
    from wind_resource.era5_fetcher import ERA5Fetcher

    cfg = tmp_path / "era5_config.yaml"
    cfg.write_text(
        "api:\n"
        "  area_buffer_degrees: 0.5\n"
        "variables:\n"
        "  - 100m_u_component_of_wind\n"
        "  - 100m_v_component_of_wind\n"
        "wind_shear:\n"
        "  reference_heights: [10, 100]\n"
        "  alpha_min: 0.05\n"
        "  alpha_max: 0.40\n"
        "  alpha_default: 0.143\n"
    )
    fetcher = ERA5Fetcher(cache_dir=str(tmp_path / "cache"), config_path=str(cfg))
    cache_file = fetcher.cache_dir / "era5_site_2020-01-01_to_2020-12-31.csv"
    fetcher._save_metadata(
        location={"name": "Site", "lat": 8.33, "lon": 79.76},
        start_date="2020-01-01",
        end_date="2020-12-31",
        cache_file=cache_file,
    )
    meta = json.loads(
        (fetcher.metadata_dir / f"{cache_file.stem}_metadata.json").read_text()
    )
    assert meta["version"] == engine_version()
    assert "1.1.0" not in meta["version"]


# ---------------------------------------------------------------------------
# 2. resource.uncertainty.* plumbing (haircut pinned 0.0 — #653)
# ---------------------------------------------------------------------------


def test_budget_from_mapping_empty_is_default_budget() -> None:
    assert budget_from_mapping({}) == UncertaintyBudget()


def test_budget_from_mapping_overrides_only_supplied_sigmas() -> None:
    b = budget_from_mapping({"wind_measurement_pct": 6.0, "wake_model_pct": 1.0})
    d = UncertaintyBudget()
    assert b.wind_measurement_pct == 6.0
    assert b.wake_model_pct == 1.0
    assert b.long_term_pct == d.long_term_pct
    assert b.interannual_variability_pct == d.interannual_variability_pct


def test_budget_from_mapping_rejects_typod_sigma_key_with_suggestion() -> None:
    """#683 (CESSPIT): a typo'd sigma previously yielded the ALL-defaults budget
    silently — the worst failure mode for a lender-facing P90. The error must name
    the offending key, suggest the nearest valid key, and spell out the allowlist."""
    with pytest.raises(ValueError) as exc:
        budget_from_mapping({"wind_measurment_pct": 6.0})
    msg = str(exc.value)
    assert "'wind_measurment_pct'" in msg
    assert "did you mean 'wind_measurement_pct'?" in msg
    # The full allowlist is spelled out: all seven IEC sigmas + the policy knobs.
    for key in (
        "wind_measurement_pct",
        "long_term_pct",
        "vertical_extrapolation_pct",
        "horizontal_flow_pct",
        "power_curve_pct",
        "wake_model_pct",
        "interannual_variability_pct",
        "p50_haircut_pct",
        "correlation",
        "life_years",
    ):
        assert key in msg


def test_budget_from_mapping_names_every_unknown_key() -> None:
    with pytest.raises(ValueError) as exc:
        budget_from_mapping({"wake_pct": 1.0, "not_a_knob": 2.0, "long_term_pct": 4.0})
    msg = str(exc.value)
    assert "'wake_pct'" in msg
    assert "'not_a_knob'" in msg


def test_budget_from_mapping_tolerates_caller_policy_knobs() -> None:
    """The knobs consumed by the CALLERS (the #653/#618 split) must not trip the
    fence — they legitimately share the ``resource.uncertainty`` mapping."""
    b = budget_from_mapping(
        {"p50_haircut_pct": 2.0, "correlation": 0.5, "life_years": 25}
    )
    assert b == UncertaintyBudget()  # knobs are not sigmas: defaults untouched


def test_budget_from_mapping_full_seven_key_mapping_parses() -> None:
    vals = {
        "wind_measurement_pct": 1.0,
        "long_term_pct": 2.0,
        "vertical_extrapolation_pct": 3.5,
        "horizontal_flow_pct": 4.0,
        "power_curve_pct": 5.5,
        "wake_model_pct": 6.0,
        "interannual_variability_pct": 7.0,
    }
    b = budget_from_mapping(vals)
    for key, expected in vals.items():
        assert getattr(b, key) == expected


def test_no_uncertainty_config_is_byte_identical_to_defaults() -> None:
    """Absent / empty mapping must reproduce the previous hardcoded budget EXACTLY."""
    base = _calc().calculate_net_aep()
    empty = _calc(uncertainty={}).calculate_net_aep()
    for key in (
        "net_aep_p50_mwh",
        "net_aep_p75_mwh",
        "net_aep_p90_mwh",
        "uncertainty_sigma_1yr_pct",
    ):
        assert base[key] == empty[key]  # exact, not approx: identity is the contract
    assert base["exceedance_correlation"] == 0.0
    assert base["exceedance_life_years"] == 20  # ppa_years from era5_config.yaml
    assert base["p50_haircut_pct"] == 0.0


def test_nondefault_sigmas_move_p75_p90_not_p50() -> None:
    unc = {"wind_measurement_pct": 12.0, "power_curve_pct": 10.0}
    base = _calc().calculate_net_aep()
    wide = _calc(uncertainty=unc).calculate_net_aep()

    assert wide["net_aep_p50_mwh"] == base["net_aep_p50_mwh"]  # P50 untouched
    assert wide["net_aep_p75_mwh"] < base["net_aep_p75_mwh"]
    assert wide["net_aep_p90_mwh"] < base["net_aep_p90_mwh"]
    assert wide["uncertainty_sigma_1yr_pct"] > base["uncertainty_sigma_1yr_pct"]

    # Delegation check: identical to the canonical kernel with the same budget.
    exc = exceedance_levels(
        wide["net_aep_p50_mwh"] / 1000.0, budget_from_mapping(unc), life_years=20
    )
    assert wide["net_aep_p75_mwh"] == pytest.approx(exc.p75_gwh * 1000.0)
    assert wide["net_aep_p90_mwh"] == pytest.approx(exc.p90_1yr_gwh * 1000.0)


def test_correlation_knob_widens_sigma() -> None:
    base = _calc(uncertainty={"correlation": 0.0}).calculate_net_aep()
    corr = _calc(uncertainty={"correlation": 1.0}).calculate_net_aep()
    assert corr["uncertainty_sigma_1yr_pct"] > base["uncertainty_sigma_1yr_pct"]
    assert corr["net_aep_p90_mwh"] < base["net_aep_p90_mwh"]
    assert corr["exceedance_correlation"] == 1.0


def test_declared_p50_haircut_is_not_applied_on_timeseries_path() -> None:
    """#653 trap: even an EXPLICIT p50_haircut_pct must not move this path (pinned 0.0)."""
    base = _calc().calculate_net_aep()
    haircut = _calc(uncertainty={"p50_haircut_pct": 5.0}).calculate_net_aep()
    for key in ("net_aep_p50_mwh", "net_aep_p75_mwh", "net_aep_p90_mwh"):
        assert haircut[key] == base[key]
    assert haircut["p50_haircut_pct"] == 0.0


# ---------------------------------------------------------------------------
# 3. IEC 61400-12-1 air density on the timeseries gross AEP
# ---------------------------------------------------------------------------


def test_no_density_config_is_identity() -> None:
    base = _calc().calculate_gross_aep()
    assert base["density_velocity_factor"] == 1.0
    # And a site density equal to the reference is also exactly factor 1.0.
    same = _calc(air_density_site_kgm3=1.225).calculate_gross_aep()
    assert same["density_velocity_factor"] == 1.0
    assert same["windfarm_aep_mwh"] == base["windfarm_aep_mwh"]


def test_site_density_scales_gross_aep() -> None:
    rho_site = 1.10
    base = _calc().calculate_gross_aep()
    corrected = _calc(air_density_site_kgm3=rho_site).calculate_gross_aep()

    factor = density_velocity_factor(rho_site, 1.225)
    assert corrected["density_velocity_factor"] == pytest.approx(factor)
    assert factor < 1.0
    # 10 m/s sits in the 3->12 linear ramp, so the leftward velocity shift
    # strictly reduces power: same direction/magnitude as the bankable engine.
    expected_power = 1000.0 * (10.0 * factor - 3.0) / (12.0 - 3.0)
    assert corrected["average_power_kw"] == pytest.approx(expected_power)
    assert corrected["windfarm_aep_mwh"] < base["windfarm_aep_mwh"]


def test_monthly_profile_uses_same_density_correction() -> None:
    """Monthly energy must stay consistent with the corrected annual gross."""
    calc = _calc(air_density_site_kgm3=1.10)
    gross = calc.calculate_gross_aep()
    monthly = calc.calculate_monthly_energy()
    # Constant wind speed -> monthly avg power == annual avg power (both corrected):
    # energy = avg_power * 730 h * n_turbines / 1000.
    assert monthly["energy_mwh"].iloc[0] == pytest.approx(
        gross["average_power_kw"] * 730 * 10 / 1000
    )
