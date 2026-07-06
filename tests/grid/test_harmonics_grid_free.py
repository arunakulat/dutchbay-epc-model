"""Grid-FREE coverage for the D7 SCR-coupled harmonics / flicker screen (#883).

These tests import NO grid library (pandapower is ABSENT in the default venv) and are NOT
marked ``grid`` — so they run in the default ``-m 'not grid'`` coverage lane and carry the
real coverage for :mod:`analytics.grid.harmonics`. They exercise:

  * every pure helper (IEEE 519 limit tables, ``poc_ssc_mva`` / ``isc_il_ratio``, the
    closed-form Zbus shape, ``harmonic_voltages_pct`` incl. the fundamental exclusion,
    ``total_harmonic_distortion_pct``, ``flicker_pst``) incl. their ValueError branches;
  * the EXPLICIT SCR-COUPLING property (harmonic voltage + flicker WORSEN as SCR drops);
  * the closed-form ``screen_harmonics`` (``use_pandapower=False``) — the verdict logic,
    the NOT-RUN paths (absent spectrum / disabled flicker), and the frequency-response
    headroom wiring — end-to-end into :class:`HarmonicComplianceResult`.

The genuinely pandapower-only code (``_pandapower_zbus_pu_by_order`` and the scan branch
inside ``screen_harmonics``) is ``# pragma: no cover - requires [grid] extra`` and is
exercised by the ``grid``-marked ``test_harmonics_d7.py`` under ``pip install -e '.[grid]'``.
"""

from __future__ import annotations

import math

import pytest

from analytics.contracts_v14 import HarmonicComplianceResult
from analytics.grid import harmonics as hm
from analytics.grid.harmonics import (
    DEFAULT_FLICKER_COEFFICIENT,
    DEFAULT_FLICKER_PST_LIMIT,
    closed_form_zbus_shape,
    flicker_pst,
    harmonic_voltages_pct,
    ieee519_current_tdd_limit,
    ieee519_voltage_limits,
    isc_il_ratio,
    poc_ssc_mva,
    screen_harmonics,
    total_harmonic_distortion_pct,
)

# A DutchBay-shaped grid block with an OEM current-emission spectrum (% of IL), flicker
# coefficient, and a frequency band — the full D7 input surface.
_SPECTRUM = [[1, 100.0], [5, 2.4], [7, 1.5], [11, 0.9], [13, 0.7]]
_GRID = {
    "poc": {"nominal_kv": 33.0, "plant_rated_mva": 159.6},
    "harmonic_spectrum": _SPECTRUM,
    "flicker_coefficient": 3.4,
    "gridcode": {"freq_ride_through": {"continuous_hz": [47.5, 51.5], "droop": 0.04}},
}


# --------------------------------------------------------------------------- IEEE 519


@pytest.mark.parametrize(
    "kv, individual, thd",
    [(0.4, 5.0, 8.0), (33.0, 3.0, 5.0), (132.0, 1.5, 2.5), (220.0, 1.0, 1.5)],
)
def test_ieee519_voltage_limits_bands(kv: float, individual: float, thd: float) -> None:
    assert ieee519_voltage_limits(kv) == (individual, thd)


def test_ieee519_voltage_limits_bad_kv_raises() -> None:
    with pytest.raises(ValueError, match="poc_voltage_kv must be > 0"):
        ieee519_voltage_limits(0.0)


@pytest.mark.parametrize(
    "ratio, tdd",
    [(10.0, 5.0), (30.0, 8.0), (75.0, 12.0), (500.0, 15.0), (2000.0, 20.0)],
)
def test_ieee519_current_tdd_indexed_by_isc_il(ratio: float, tdd: float) -> None:
    # A weaker grid (lower Isc/IL) allows LESS current distortion — the SCR coupling.
    assert ieee519_current_tdd_limit(ratio) == tdd


def test_ieee519_current_tdd_monotonic_in_ratio() -> None:
    # The allowed TDD is non-decreasing as the grid stiffens.
    limits = [ieee519_current_tdd_limit(r) for r in (5, 25, 75, 500, 5000)]
    assert limits == sorted(limits)


def test_ieee519_current_tdd_bad_ratio_raises() -> None:
    with pytest.raises(ValueError, match="isc_il_ratio must be > 0"):
        ieee519_current_tdd_limit(0.0)


# --------------------------------------------------------------------------- Ssc / ratio


def test_poc_ssc_mva() -> None:
    assert poc_ssc_mva(4.0, 159.6) == pytest.approx(638.4)


@pytest.mark.parametrize("scr, mva", [(0.0, 100.0), (2.0, 0.0), (-1.0, 100.0)])
def test_poc_ssc_mva_bad_inputs_raise(scr: float, mva: float) -> None:
    with pytest.raises(ValueError, match="requires scr > 0"):
        poc_ssc_mva(scr, mva)


def test_isc_il_ratio_equals_scr() -> None:
    assert isc_il_ratio(3.5) == 3.5


def test_isc_il_ratio_bad_raises() -> None:
    with pytest.raises(ValueError, match="requires scr > 0"):
        isc_il_ratio(0.0)


# --------------------------------------------------------------------------- zbus shape


def test_closed_form_zbus_shape_is_order() -> None:
    assert closed_form_zbus_shape(5) == 5.0
    assert closed_form_zbus_shape(1) == 1.0


def test_closed_form_zbus_shape_bad_order_raises() -> None:
    with pytest.raises(ValueError, match="order must be >= 1"):
        closed_form_zbus_shape(0)


# --------------------------------------------------------------------------- V_h


def test_harmonic_voltages_excludes_fundamental() -> None:
    # Order 1 (the fundamental) is NOT a distortion component and must be dropped.
    v = harmonic_voltages_pct(
        [(1, 100.0), (5, 2.4)],
        z1_pu_plant_base=1.0 / 4.0,
        zbus_shape_by_order={1: 1.0, 5: 5.0},
    )
    assert [o for (o, _p) in v] == [5]
    # V_5 = (1/4) * 5 * 2.4 = 3.0 %.
    assert v[0][1] == pytest.approx(3.0)


def test_harmonic_voltages_scales_inverse_with_scr() -> None:
    # SCR-COUPLING: halving the SCR (doubling 1/SCR) doubles the harmonic voltage.
    weak = harmonic_voltages_pct(
        [(5, 2.4)], z1_pu_plant_base=1.0 / 2.0, zbus_shape_by_order={5: 5.0}
    )
    stiff = harmonic_voltages_pct(
        [(5, 2.4)], z1_pu_plant_base=1.0 / 8.0, zbus_shape_by_order={5: 5.0}
    )
    assert weak[0][1] == pytest.approx(4.0 * stiff[0][1])


def test_harmonic_voltages_skips_orders_without_shape() -> None:
    v = harmonic_voltages_pct(
        [(5, 2.4), (7, 1.5)], z1_pu_plant_base=0.25, zbus_shape_by_order={5: 5.0}
    )
    assert [o for (o, _p) in v] == [5]


def test_harmonic_voltages_bad_z1_raises() -> None:
    with pytest.raises(ValueError, match="z1_pu_plant_base"):
        harmonic_voltages_pct(
            [(5, 2.4)], z1_pu_plant_base=0.0, zbus_shape_by_order={5: 5.0}
        )


def test_total_harmonic_distortion_rss() -> None:
    assert total_harmonic_distortion_pct([(5, 3.0), (7, 4.0)]) == pytest.approx(5.0)
    assert total_harmonic_distortion_pct([]) == 0.0


# --------------------------------------------------------------------------- flicker


def test_flicker_pst_inverse_ssc() -> None:
    # Pst = c * S / Ssc. Weaker grid (lower Ssc) → higher Pst.
    weak = flicker_pst(
        flicker_coefficient=3.4, plant_rating_mva=159.6, poc_ssc_mva_value=319.2
    )
    stiff = flicker_pst(
        flicker_coefficient=3.4, plant_rating_mva=159.6, poc_ssc_mva_value=1276.8
    )
    assert weak == pytest.approx(4.0 * stiff)
    assert weak == pytest.approx(3.4 * 159.6 / 319.2)


def test_flicker_pst_bad_ssc_raises() -> None:
    with pytest.raises(ValueError, match="poc_ssc_mva_value > 0"):
        flicker_pst(
            flicker_coefficient=3.4, plant_rating_mva=100.0, poc_ssc_mva_value=0.0
        )


def test_flicker_pst_negative_inputs_raise() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        flicker_pst(
            flicker_coefficient=-1.0, plant_rating_mva=100.0, poc_ssc_mva_value=500.0
        )


# --------------------------------------------------------------------------- screen (closed-form)


def test_screen_stiff_grid_passes_harmonics() -> None:
    r = screen_harmonics(_GRID, scr=8.0, capacity_factor=0.354, use_pandapower=False)
    assert isinstance(r, HarmonicComplianceResult)
    assert r.method == "closed_form"
    assert r.bankable is False
    assert r.worst_harmonic_order == 5  # fundamental excluded
    # SCR=8 → 1/8 * 5 * 2.4 = 1.5 % worst V_h ≤ 3 % individual limit; THD ≤ 5 %.
    assert r.worst_harmonic_voltage_pct == pytest.approx(1.5)
    assert r.harmonic_within_limits is True
    assert "SCR" in r.disclaimer and "screening" in r.disclaimer.lower()
    assert "DEGRADES as SCR falls" in r.notes


def test_screen_weak_grid_fails_harmonics() -> None:
    r = screen_harmonics(_GRID, scr=2.0, capacity_factor=0.354, use_pandapower=False)
    # SCR=2 → 1/2 * 5 * 2.4 = 6 % worst V_h > 3 % individual limit → FAIL.
    assert r.worst_harmonic_voltage_pct == pytest.approx(6.0)
    assert r.harmonic_within_limits is False


def test_screen_scr_coupling_worsens_as_scr_drops() -> None:
    stiff = screen_harmonics(_GRID, scr=8.0, capacity_factor=0.3, use_pandapower=False)
    weak = screen_harmonics(_GRID, scr=2.0, capacity_factor=0.3, use_pandapower=False)
    assert weak.worst_harmonic_voltage_pct > stiff.worst_harmonic_voltage_pct
    assert weak.thd_voltage_pct > stiff.thd_voltage_pct
    assert weak.flicker_pst > stiff.flicker_pst
    assert weak.poc_ssc_mva < stiff.poc_ssc_mva
    # The current-TDD LIMIT is indexed by Isc/IL (= SCR): weaker grid → tighter limit.
    assert weak.current_tdd_limit_pct <= stiff.current_tdd_limit_pct


def test_screen_current_tdd_excludes_fundamental() -> None:
    r = screen_harmonics(_GRID, scr=5.0, capacity_factor=0.3, use_pandapower=False)
    # TDD_i = RSS of the h>=2 emission percentages (fundamental 100 % excluded).
    expected = math.sqrt(2.4**2 + 1.5**2 + 0.9**2 + 0.7**2)
    assert r.current_tdd_pct == pytest.approx(expected)


def test_screen_flicker_scr_coupled_and_limit() -> None:
    r = screen_harmonics(_GRID, scr=2.0, capacity_factor=0.3, use_pandapower=False)
    assert r.flicker_pst_limit == DEFAULT_FLICKER_PST_LIMIT
    # Pst = 3.4 * 159.6 / (2*159.6) = 1.7 >> 0.35 → flicker fails.
    assert r.flicker_pst == pytest.approx(1.7)
    assert r.flicker_within_limits is False


def test_screen_no_spectrum_reports_harmonic_not_run() -> None:
    grid = {k: v for k, v in _GRID.items() if k != "harmonic_spectrum"}
    r = screen_harmonics(grid, scr=5.0, capacity_factor=0.3, use_pandapower=False)
    # No emission spectrum → the harmonic domain is an honest NOT-RUN, never a spurious pass.
    assert r.harmonic_within_limits is None
    assert r.worst_harmonic_order is None
    assert r.worst_harmonic_voltage_pct is None
    assert r.thd_voltage_pct is None
    assert r.current_tdd_pct is None
    # Flicker still screens (a coefficient is present).
    assert r.flicker_within_limits is not None


def test_screen_disabled_flicker_reports_not_run() -> None:
    grid = dict(_GRID)
    grid["flicker_coefficient"] = -1.0  # explicit invalid → disables the flicker screen
    r = screen_harmonics(grid, scr=5.0, capacity_factor=0.3, use_pandapower=False)
    assert r.flicker_pst is None
    assert r.flicker_within_limits is None


def test_screen_default_flicker_coefficient_when_absent() -> None:
    grid = {k: v for k, v in _GRID.items() if k != "flicker_coefficient"}
    grid["gridcode"] = {"freq_ride_through": {"continuous_hz": [47.5, 51.5]}}
    r = screen_harmonics(grid, scr=5.0, capacity_factor=0.3, use_pandapower=False)
    # Flicker is always screened for a converter plant via the default coefficient.
    expected = DEFAULT_FLICKER_COEFFICIENT * 159.6 / (5.0 * 159.6)
    assert r.flicker_pst == pytest.approx(expected)


def test_screen_flicker_limit_override() -> None:
    grid = dict(_GRID)
    grid["flicker_pst_limit"] = 1.0
    r = screen_harmonics(grid, scr=5.0, capacity_factor=0.3, use_pandapower=False)
    assert r.flicker_pst_limit == 1.0


def test_screen_frequency_headroom_wired() -> None:
    r = screen_harmonics(_GRID, scr=5.0, capacity_factor=0.354, use_pandapower=False)
    # 10 % reserve on 159.6 MVA-as-MW; energy = headroom * cf * 8760.
    assert r.freq_response_headroom_mw == pytest.approx(15.96)
    assert r.energy_foregone_mwh_yr == pytest.approx(15.96 * 0.354 * 8760.0)


def test_screen_config_droop_and_mandated_reserve() -> None:
    # Explicit grid.droop + grid.mandated_reserve_fraction drive the headroom sizing.
    grid = dict(_GRID)
    grid["droop"] = 0.05
    grid["mandated_reserve_fraction"] = 0.15
    r = screen_harmonics(grid, scr=5.0, capacity_factor=0.3, use_pandapower=False)
    # Mandated 15 % dominates the droop-implied (0.2/50/0.05 = 8 %) figure → 15 % of 159.6.
    assert r.freq_response_headroom_mw == pytest.approx(0.15 * 159.6)


def test_screen_gridcode_droop_and_reserve() -> None:
    # Droop / mandated-reserve can also live under gridcode.
    grid = {
        "poc": {"nominal_kv": 33.0, "plant_rated_mva": 100.0},
        "harmonic_spectrum": [[1, 100.0], [5, 2.4]],
        "gridcode": {
            "freq_ride_through": {"continuous_hz": [47.5, 51.5]},
            "droop": 0.04,
            "mandated_reserve_fraction": 0.12,
        },
    }
    r = screen_harmonics(grid, scr=5.0, capacity_factor=0.3, use_pandapower=False)
    assert r.freq_response_headroom_mw == pytest.approx(0.12 * 100.0)


def test_screen_reads_flat_core_poc() -> None:
    # Falls back to the D1 flat-core poc_voltage_kv / plant_rating_mva when no poc block.
    grid = {
        "poc_voltage_kv": 220.0,
        "plant_rating_mva": 159.6,
        "harmonic_spectrum": [[1, 100.0], [5, 2.4]],
    }
    r = screen_harmonics(grid, scr=6.0, capacity_factor=0.3, use_pandapower=False)
    # 220 kV → tightest IEEE 519 band (1.0 % individual / 1.5 % THD).
    assert r.harmonic_voltage_limit_pct == 1.0
    assert r.thd_voltage_limit_pct == 1.5


def test_screen_spectrum_as_mapping() -> None:
    grid = {
        "poc": {"nominal_kv": 33.0, "plant_rated_mva": 159.6},
        "harmonic_spectrum": {5: 2.4, 7: 1.5},
        "gridcode": {"harmonic_spectrum": None},
    }
    r = screen_harmonics(grid, scr=5.0, capacity_factor=0.3, use_pandapower=False)
    # V_5 = (1/5)*5*2.4 = 2.4 ; V_7 = (1/5)*7*1.5 = 2.1 → the worst is order 5.
    assert r.worst_harmonic_order == 5
    assert r.worst_harmonic_voltage_pct == pytest.approx(2.4)


def test_screen_spectrum_from_gridcode_fallback() -> None:
    grid = {
        "poc": {"nominal_kv": 33.0, "plant_rated_mva": 159.6},
        "gridcode": {"harmonic_spectrum": [[5, 2.4]]},
    }
    r = screen_harmonics(grid, scr=5.0, capacity_factor=0.3, use_pandapower=False)
    assert r.worst_harmonic_order == 5


@pytest.mark.parametrize("bad_scr", [0.0, -1.0])
def test_screen_bad_scr_raises(bad_scr: float) -> None:
    with pytest.raises(ValueError, match="requires scr > 0"):
        screen_harmonics(_GRID, scr=bad_scr, capacity_factor=0.3, use_pandapower=False)


def test_screen_missing_kv_raises() -> None:
    with pytest.raises(ValueError, match="nominal_kv"):
        screen_harmonics(
            {"plant_rating_mva": 100.0, "harmonic_spectrum": [[5, 2.4]]},
            scr=5.0,
            use_pandapower=False,
        )


def test_screen_missing_mva_raises() -> None:
    with pytest.raises(ValueError, match="plant_rated_mva"):
        screen_harmonics(
            {"poc_voltage_kv": 33.0, "harmonic_spectrum": [[5, 2.4]]},
            scr=5.0,
            use_pandapower=False,
        )


def test_screen_capacity_factor_clamped() -> None:
    # Out-of-range cf is clamped (not raised) at the screen level so a report never crashes.
    r = screen_harmonics(_GRID, scr=5.0, capacity_factor=2.0, use_pandapower=False)
    assert r.energy_foregone_mwh_yr == pytest.approx(
        r.freq_response_headroom_mw * 1.0 * 8760.0
    )


def test_screen_use_pandapower_true_falls_back_when_absent() -> None:
    # With pandapower ABSENT (default venv) but use_pandapower=True, the screen must fall
    # back to the closed-form path (not raise) — the CASPER graceful-degradation contract.
    r = screen_harmonics(_GRID, scr=5.0, capacity_factor=0.3, use_pandapower=True)
    assert r.method == "closed_form"
    assert r.harmonic_within_limits is not None


def test_require_pandapower_raises_actionable() -> None:
    # pandapower is absent in the default venv → the CASPER guard raises an actionable error.
    with pytest.raises(ImportError, match=r"\[grid\] extra"):
        hm._require_pandapower()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
