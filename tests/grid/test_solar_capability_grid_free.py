"""Grid-FREE coverage for the D4c solar grid-capability plug-in (#877).

These tests import NO grid library (``pandapower`` / ``andes`` are ABSENT in the default
venv) and are NOT marked ``grid`` — so they run in the default ``-m 'not grid'`` coverage
lane and carry the REAL coverage for :mod:`analytics.grid.capabilities.solar`. The whole
plug-in is grid-library-free (its capability math is pure Python), so this file covers
100% of its non-pragma lines. It exercises:

  * the tech classifier (``is_solar_capability_tech``) — solar True, wind/bess/tidal/junk
    False (keyed on the finance.tech_types single source of truth);
  * the DC:AC clipping helper (``ac_rating_from_dc``) incl. both ValueError branches, and
    the load-bearing rule that the inverter efficiency is NOT re-applied;
  * the current-limited fault-contribution model (``solar_fault_contribution``) — the
    ~1.1 pu ceiling, the negligible non-synchronous infeed, and its ValueError branches;
  * the pf_range parser (``_pf_range_from_gridcode``) incl. its ValueError branches;
  * ``screen_solar_capability`` end-to-end for a pf-matched plant (zero shortfall), a
    reactive-tight plant (grid-code demands a tighter pf than the inverter → positive
    Mvar shortfall), the explicit ``pf_capability`` override, and the missing-input
    (CESSPIT) failures.
"""

from __future__ import annotations

import math
from dataclasses import FrozenInstanceError

import pytest

from analytics.contracts_v14 import ReactiveCapabilityResult
from analytics.grid.capabilities import solar as sc
from analytics.grid.capabilities.solar import (
    DEFAULT_FAULT_CURRENT_PU,
    SOLAR_TECH,
    SolarFaultContribution,
    ac_rating_from_dc,
    is_solar_capability_tech,
    screen_solar_capability,
    solar_fault_contribution,
)

# A DutchBay-shaped solar grid block: 50 MWp DC / ILR 1.2 → 41.667 MVA AC export.
_SOLAR_BLOCK = {
    "dc_capacity_mw": 50.0,
    "dc_ac_ratio": 1.2,
    "gridcode": {"pf_range": [-0.95, 0.95]},
}


# --------------------------------------------------------------- tech classifier


def test_is_solar_capability_tech_true_for_solar() -> None:
    assert is_solar_capability_tech("solar") is True
    assert is_solar_capability_tech("SOLAR") is True
    assert is_solar_capability_tech(" Solar ") is True


def test_is_solar_capability_tech_false_for_other_techs() -> None:
    # wind is a modelled generation type but NOT solar (it has its own plug-in);
    # bess/tidal are not modelled-generation; junk/None are unknown.
    for other in ("wind", "bess", "tidal", "hydro", "geothermal", "", None, 3):
        assert is_solar_capability_tech(other) is False


# ------------------------------------------------------- DC:AC clipping helper


def test_ac_rating_from_dc_is_geometric_no_efficiency_derate() -> None:
    """AC rating = DC / ILR — a pure geometric cap; NO inverter efficiency is re-applied."""
    ac = ac_rating_from_dc(50.0, 1.2)
    assert ac == pytest.approx(50.0 / 1.2)
    # If an inverter efficiency (~0.96) had been (wrongly) re-applied, the rating would be
    # ~40.0 MVA, not 41.667. Assert it is the un-derated geometric value.
    assert ac == pytest.approx(41.6667, abs=1e-3)
    assert ac > 50.0 * 0.96 / 1.2  # strictly above the double-counted value


def test_ac_rating_from_dc_rejects_bad_dc() -> None:
    for bad in (0.0, -5.0, "x", None, True):
        with pytest.raises(ValueError, match="dc_capacity_mw"):
            ac_rating_from_dc(bad, 1.2)  # type: ignore[arg-type]


def test_ac_rating_from_dc_rejects_bad_ratio() -> None:
    for bad in (0.0, -1.0, "y", None, True):
        with pytest.raises(ValueError, match="dc_ac_ratio"):
            ac_rating_from_dc(50.0, bad)  # type: ignore[arg-type]


# ----------------------------------------------- current-limited fault model


def test_solar_fault_contribution_is_current_limited_not_synchronous() -> None:
    """~1.1 pu ceiling, small infeed, is_synchronous False (never a machine)."""
    ac = 41.667
    fc = solar_fault_contribution(ac)
    assert fc.fault_current_pu == DEFAULT_FAULT_CURRENT_PU == 1.1
    assert fc.ac_rating_mva == pytest.approx(ac)
    assert fc.fault_mva_contribution == pytest.approx(1.1 * ac)
    assert fc.is_synchronous is False
    # The infeed is SMALL — a synchronous machine would be ~5-6x rating, not ~1.1x.
    assert fc.fault_mva_contribution < 2.0 * ac
    assert "grid-following" in fc.note.lower()
    assert "voltage source" in fc.note.lower()  # the do-not-model-as caveat


def test_solar_fault_contribution_custom_pu() -> None:
    fc = solar_fault_contribution(40.0, fault_current_pu=1.2)
    assert fc.fault_current_pu == 1.2
    assert fc.fault_mva_contribution == pytest.approx(48.0)


def test_solar_fault_contribution_rejects_bad_inputs() -> None:
    with pytest.raises(ValueError, match="ac_rating_mva"):
        solar_fault_contribution(0.0)
    with pytest.raises(ValueError, match="ac_rating_mva"):
        solar_fault_contribution(-1.0)
    with pytest.raises(ValueError, match="fault_current_pu"):
        solar_fault_contribution(40.0, fault_current_pu=0.0)
    with pytest.raises(ValueError, match="fault_current_pu"):
        solar_fault_contribution(40.0, fault_current_pu=-0.5)


def test_solar_fault_contribution_is_frozen() -> None:
    fc = solar_fault_contribution(40.0)
    with pytest.raises(FrozenInstanceError):
        fc.is_synchronous = True  # type: ignore[misc]  # frozen dataclass


# --------------------------------------------------------- pf_range parser


def test_pf_range_parser_reads_gridcode() -> None:
    assert sc._pf_range_from_gridcode({"gridcode": {"pf_range": [-0.9, 0.95]}}) == (
        -0.9,
        0.95,
    )


def test_pf_range_parser_missing_raises() -> None:
    for block in ({}, {"gridcode": {}}, {"gridcode": {"pf_range": [0.95]}}):
        with pytest.raises(ValueError, match="pf_range"):
            sc._pf_range_from_gridcode(block)


def test_pf_range_parser_non_numeric_raises() -> None:
    with pytest.raises(ValueError, match="pf_range"):
        sc._pf_range_from_gridcode({"gridcode": {"pf_range": ["a", "b"]}})


def test_pf_range_parser_out_of_range_magnitude_raises() -> None:
    for bad in ([-1.5, 0.95], [0.0, 0.95], [-0.95, 0.0]):
        with pytest.raises(ValueError, match=r"magnitude in \(0, 1\]"):
            sc._pf_range_from_gridcode({"gridcode": {"pf_range": bad}})


# ---------------------------------------------- screen (end-to-end, no grid libs)


def test_screen_pf_matched_plant_zero_shortfall() -> None:
    """A plant whose inverter pf == the grid-code pf meets the demand → zero shortfall."""
    reactive, fault = screen_solar_capability(_SOLAR_BLOCK)
    assert isinstance(reactive, ReactiveCapabilityResult)
    assert isinstance(fault, SolarFaultContribution)

    ac = 50.0 / 1.2
    expected_q = ac * math.tan(math.acos(0.95))
    assert reactive.mvar_required == pytest.approx(expected_q)
    assert reactive.mvar_available == pytest.approx(expected_q)
    assert reactive.mvar_shortfall == pytest.approx(0.0)
    assert reactive.inside_pq_box is True
    assert reactive.method == "closed_form_solar"
    assert reactive.bankable is False
    assert reactive.pf_required_min == -0.95
    assert reactive.pf_required_max == 0.95
    assert reactive.governing_p_mw == pytest.approx(ac)
    # Fault contribution rides in from the same screen — current-limited, non-synchronous.
    assert fault.is_synchronous is False
    assert fault.fault_mva_contribution == pytest.approx(1.1 * ac)


def test_screen_reactive_tight_plant_has_shortfall() -> None:
    """Grid code demands a TIGHTER pf (0.90) than the inverter delivers (0.95) → shortfall.

    A tighter required pf demands MORE Mvar than the inverter's Q-envelope provides, so a
    positive shortfall (the STATCOM/MSC sizing gap) surfaces and inside_pq_box is False.
    """
    block = {
        "dc_capacity_mw": 50.0,
        "dc_ac_ratio": 1.2,
        "gridcode": {"pf_range": [-0.90, 0.90]},  # demand 0.90
        "pf_capability": 0.95,  # inverter only delivers 0.95
    }
    reactive, _fault = screen_solar_capability(block)
    ac = 50.0 / 1.2
    q_demand = ac * math.tan(math.acos(0.90))
    q_avail = ac * math.tan(math.acos(0.95))
    assert q_demand > q_avail
    assert reactive.mvar_required == pytest.approx(q_demand)
    assert reactive.mvar_available == pytest.approx(q_avail)
    assert reactive.mvar_shortfall == pytest.approx(q_demand - q_avail)
    assert reactive.inside_pq_box is False


def test_screen_pf_capability_override_used_when_valid() -> None:
    """An explicit valid ``pf_capability`` overrides the default (=grid-code pf)."""
    block = dict(_SOLAR_BLOCK, pf_capability=0.99)  # looser inverter envelope
    reactive, _ = screen_solar_capability(block)
    assert reactive.pf_at_poc == 0.99
    ac = 50.0 / 1.2
    assert reactive.mvar_available == pytest.approx(ac * math.tan(math.acos(0.99)))


def test_screen_pf_capability_ignored_when_out_of_range() -> None:
    """A junk/out-of-range ``pf_capability`` falls back to the grid-code pf (not a crash)."""
    for junk in (0.0, 1.5, -2.0, "x", None, True):
        block = dict(_SOLAR_BLOCK, pf_capability=junk)
        reactive, _ = screen_solar_capability(block)
        assert reactive.pf_at_poc == 0.95  # fell back to the required pf


def test_screen_missing_dc_raises() -> None:
    with pytest.raises(ValueError, match="dc_capacity_mw"):
        screen_solar_capability(
            {"dc_ac_ratio": 1.2, "gridcode": {"pf_range": [-0.95, 0.95]}}
        )


def test_screen_missing_ratio_raises() -> None:
    with pytest.raises(ValueError, match="dc_ac_ratio"):
        screen_solar_capability(
            {"dc_capacity_mw": 50.0, "gridcode": {"pf_range": [-0.95, 0.95]}}
        )


def test_screen_missing_gridcode_raises() -> None:
    with pytest.raises(ValueError, match="pf_range"):
        screen_solar_capability({"dc_capacity_mw": 50.0, "dc_ac_ratio": 1.2})


def test_screen_custom_fault_current_pu_flows_through() -> None:
    _reactive, fault = screen_solar_capability(_SOLAR_BLOCK, fault_current_pu=1.15)
    assert fault.fault_current_pu == 1.15


def test_module_constants_and_all() -> None:
    assert SOLAR_TECH == "solar"
    assert DEFAULT_FAULT_CURRENT_PU == 1.1
    assert "screen_solar_capability" in sc.__all__
    assert "solar_fault_contribution" in sc.__all__
