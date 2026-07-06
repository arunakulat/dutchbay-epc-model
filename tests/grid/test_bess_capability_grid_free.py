"""Grid-FREE coverage for the D4d BESS capability plug-in (#878).

These tests import NO grid library (pandapower / andes are ABSENT in the default venv) and
are NOT marked ``grid`` — so they run in the default ``-m 'not grid'`` coverage lane and
carry the real coverage for :mod:`analytics.grid.capabilities.bess`. They exercise:

  * the STRICT ``sc_contribution_pu`` parser (present / 0.0 accepted / missing / negative /
    non-numeric) — the manual PCS short-circuit input with NO silent default;
  * the ``soh_curve`` resolver (last-year default, explicit reference_year, and every
    ValueError branch: empty, non-int key, non-numeric SoH, out-of-range SoH, missing
    reference year);
  * the BoL reactive-rating resolver (explicit q_rated_mvar / pf_range derivation / raises);
  * ``degrade_bess_rating`` (SoH scaling of S and Q, the rated_mw fallback); and
  * ``screen_bess_capability`` end-to-end in the closed-form (pandapower-absent) path —
    the PCS SC contribution folded into the SCR fault level, the SoH-degraded reactive
    verdict, and the storage-type gate.

The only pandapower-dependent code this plug-in touches lives INSIDE the D1 SCR screen
(``analytics.grid.short_circuit``), which transparently falls back to its closed-form
Thevenin path when the extra is absent — so this module has NO pandapower-only lines of its
own. A ``grid``-marked companion (``test_bess_capability_grid.py``) re-runs the end-to-end
screen with ``pip install -e '.[grid]'`` so the SCR path exercises IEC 60909.
"""

from __future__ import annotations

import math

import pytest

from analytics.contracts_v14 import GridStrengthResult, ReactiveCapabilityResult
from analytics.grid.capabilities import bess
from analytics.grid.capabilities.bess import (
    BessDegradedRating,
    bess_sc_contribution_pu,
    degrade_bess_rating,
    screen_bess_capability,
)
from analytics.grid.reactive_screen import pf_to_qp_ratio

# A DutchBay-shaped per-site BESS grid block: 10.64 MW / ±3 Mvar Envision site at a 33 kV
# POC, grid-code ±0.95 pf, with the Envision SoH curve (BoL 100% → yr15 76.5%) and a
# manual PCS short-circuit contribution of 1.1 pu (a current-limited converter ~1.1x In).
_BESS_GRID = {
    "type": "bess",
    "poc_voltage_kv": 33.0,
    "source_fault_level_mva": 800.0,
    "source_rx": 0.083,
    "connection_r_ohm": 0.05,
    "connection_x_ohm": 1.2,
    "rated_mva": 10.64,
    "q_rated_mvar": 3.0,
    "sc_contribution_pu": 1.1,
    "pf_range": [-0.95, 0.95],
    "soh_curve": {1: 1.0, 15: 0.765},
}


# --------------------------------------------------------------- sc_contribution_pu (strict)


def test_sc_contribution_pu_present() -> None:
    assert bess_sc_contribution_pu({"sc_contribution_pu": 1.1}) == pytest.approx(1.1)


def test_sc_contribution_pu_zero_is_accepted() -> None:
    # 0.0 is an EXPLICIT "PCS contributes no sustained fault current" — accepted, not a
    # silent default (only missing/negative/non-numeric raise).
    assert bess_sc_contribution_pu({"sc_contribution_pu": 0.0}) == pytest.approx(0.0)


@pytest.mark.parametrize(
    "grid",
    [
        {},  # missing → NO silent default
        {"sc_contribution_pu": -0.5},  # negative
        {"sc_contribution_pu": "1.1"},  # string, not numeric
        {"sc_contribution_pu": None},  # explicit null
        {"sc_contribution_pu": True},  # bool is not a number
    ],
)
def test_sc_contribution_pu_missing_or_bad_raises(grid: dict) -> None:
    with pytest.raises(ValueError, match="sc_contribution_pu"):
        bess_sc_contribution_pu(grid)


# ------------------------------------------------------------------------ soh_curve resolver


def test_soh_last_year_is_governing_by_default() -> None:
    soh, year = bess._soh_at_reference_year(
        {1: 1.0, 5: 0.9, 15: 0.765}, reference_year=None
    )
    assert year == 15
    assert soh == pytest.approx(0.765)


def test_soh_explicit_reference_year() -> None:
    soh, year = bess._soh_at_reference_year(
        {1: 1.0, 5: 0.9, 15: 0.765}, reference_year=5
    )
    assert year == 5
    assert soh == pytest.approx(0.9)


def test_soh_string_year_keys_are_coerced() -> None:
    # YAML often loads integer-like keys as strings; they must coerce, not raise.
    soh, year = bess._soh_at_reference_year(
        {"1": 1.0, "15": 0.765}, reference_year=None
    )
    assert year == 15
    assert soh == pytest.approx(0.765)


@pytest.mark.parametrize("curve", [None, {}, "not-a-mapping", []])
def test_soh_absent_or_empty_raises(curve: object) -> None:
    with pytest.raises(ValueError, match="soh_curve"):
        bess._soh_at_reference_year(curve, reference_year=None)  # type: ignore[arg-type]


def test_soh_non_integer_year_key_raises() -> None:
    with pytest.raises(ValueError, match="non-integer year"):
        bess._soh_at_reference_year({"yr15": 0.765}, reference_year=None)


def test_soh_non_numeric_value_raises() -> None:
    with pytest.raises(ValueError, match="must be a number"):
        bess._soh_at_reference_year({15: "0.765"}, reference_year=None)


@pytest.mark.parametrize("bad_soh", [0.0, -0.1, 1.01, 2.0])
def test_soh_out_of_range_raises(bad_soh: float) -> None:
    with pytest.raises(ValueError, match=r"SoH fraction must be in"):
        bess._soh_at_reference_year({15: bad_soh}, reference_year=None)


def test_soh_missing_reference_year_raises() -> None:
    with pytest.raises(ValueError, match="no entry for reference_year=7"):
        bess._soh_at_reference_year({1: 1.0, 15: 0.765}, reference_year=7)


# --------------------------------------------------------------- reactive-rating resolver


def test_q_rated_from_explicit_mvar() -> None:
    assert bess._resolve_q_rated_mvar_bol(
        {"q_rated_mvar": 3.0}, 10.64
    ) == pytest.approx(3.0)
    # A signed value uses its magnitude.
    assert bess._resolve_q_rated_mvar_bol(
        {"q_rated_mvar": -3.0}, 10.64
    ) == pytest.approx(3.0)


def test_q_rated_explicit_zero_raises() -> None:
    with pytest.raises(ValueError, match="non-zero reactive rating"):
        bess._resolve_q_rated_mvar_bol({"q_rated_mvar": 0.0}, 10.64)


def test_q_rated_from_pf_range() -> None:
    q = bess._resolve_q_rated_mvar_bol({"pf_range": [-0.95, 0.95]}, 10.64)
    assert q == pytest.approx(10.64 * pf_to_qp_ratio(0.95))


@pytest.mark.parametrize(
    "grid",
    [
        {},  # neither form
        {"pf_range": [-0.95]},  # wrong length
        {"pf_range": "x"},  # not a sequence
        {"pf_range": [0.0, 0.95]},  # binding endpoint out of range
    ],
)
def test_q_rated_undetermined_or_bad_raises(grid: dict) -> None:
    with pytest.raises(ValueError):
        bess._resolve_q_rated_mvar_bol(grid, 10.64)


# ------------------------------------------------------------------------ degrade_bess_rating


def test_degrade_scales_s_and_q_by_soh() -> None:
    d = degrade_bess_rating(_BESS_GRID)
    assert isinstance(d, BessDegradedRating)
    assert d.governing_year == 15
    assert d.soh_fraction == pytest.approx(0.765)
    assert d.rated_mva_bol == pytest.approx(10.64)
    assert d.rated_mva_soh == pytest.approx(10.64 * 0.765)
    assert d.q_rated_mvar_bol == pytest.approx(3.0)
    # The reactive headroom SHRINKS with SoH — the crux of the D4d degradation model.
    assert d.q_rated_mvar_soh == pytest.approx(3.0 * 0.765)
    assert d.q_rated_mvar_soh < d.q_rated_mvar_bol


def test_degrade_reference_year_selects_bol() -> None:
    d = degrade_bess_rating(_BESS_GRID, reference_year=1)
    assert d.governing_year == 1
    assert d.soh_fraction == pytest.approx(1.0)
    assert d.q_rated_mvar_soh == pytest.approx(3.0)


def test_degrade_rated_mw_fallback() -> None:
    grid = {k: v for k, v in _BESS_GRID.items() if k != "rated_mva"}
    grid["rated_mw"] = 10.64
    d = degrade_bess_rating(grid)
    assert d.rated_mva_bol == pytest.approx(10.64)


def test_degrade_missing_rating_raises() -> None:
    grid = {k: v for k, v in _BESS_GRID.items() if k != "rated_mva"}
    with pytest.raises(ValueError, match="rated_mva"):
        degrade_bess_rating(grid)


def test_degrade_q_from_pf_range_when_no_explicit_q() -> None:
    grid = {k: v for k, v in _BESS_GRID.items() if k != "q_rated_mvar"}
    d = degrade_bess_rating(grid)
    q_bol = 10.64 * pf_to_qp_ratio(0.95)
    assert d.q_rated_mvar_bol == pytest.approx(q_bol)
    assert d.q_rated_mvar_soh == pytest.approx(q_bol * 0.765)


# ---------------------------------------------------------------- screen (closed-form path)


def test_screen_folds_pcs_contribution_into_scr() -> None:
    """The manual PCS SC contribution RAISES the POC fault level vs a zero-contribution BESS."""
    strength, reactive = screen_bess_capability(_BESS_GRID, use_pandapower=False)
    assert isinstance(strength, GridStrengthResult)
    assert isinstance(reactive, ReactiveCapabilityResult)
    assert strength.bankable is False
    assert strength.method == "closed_form"

    # A BESS with zero PCS contribution yields a LOWER fault level (weaker grid) — proving
    # the contribution is genuinely folded into the SCR screen, not ignored.
    grid_zero = {**_BESS_GRID, "sc_contribution_pu": 0.0}
    strength_zero, _ = screen_bess_capability(grid_zero, use_pandapower=False)
    assert strength.fault_level_poc_mva > strength_zero.fault_level_poc_mva
    # Higher fault level → higher SCR (same plant rating denominator).
    assert strength.scr > strength_zero.scr


def test_screen_reactive_uses_soh_degraded_headroom() -> None:
    """The reactive verdict is graded at the SoH-degraded (year-15) headroom, not BoL."""
    strength, reactive = screen_bess_capability(_BESS_GRID, use_pandapower=False)
    # Available reactive == degraded headroom (3.0 * 0.765), NOT the 3.0 BoL figure.
    assert reactive.mvar_available == pytest.approx(3.0 * 0.765)
    # Demand at the degraded MVA rating and the binding 0.95 pf.
    p_ref = 10.64 * 0.765
    assert reactive.mvar_required == pytest.approx(p_ref * math.tan(math.acos(0.95)))
    assert reactive.mvar_shortfall == pytest.approx(
        max(0.0, reactive.mvar_required - reactive.mvar_available)
    )
    assert reactive.method == "closed_form"
    assert reactive.governing_p_mw == pytest.approx(p_ref)
    assert reactive.governing_grid_v_pu is None


def test_screen_reactive_ample_headroom_inside_box() -> None:
    """A BESS with generous Mvar clears the PQ box at end-of-life (zero shortfall)."""
    grid = {**_BESS_GRID, "q_rated_mvar": 20.0}
    _strength, reactive = screen_bess_capability(grid, use_pandapower=False)
    assert reactive.mvar_shortfall == pytest.approx(0.0)
    assert reactive.inside_pq_box is True


def test_screen_reference_year_bol_uses_full_headroom() -> None:
    _strength, reactive = screen_bess_capability(
        _BESS_GRID, use_pandapower=False, reference_year=1
    )
    assert reactive.mvar_available == pytest.approx(3.0)


def test_screen_uses_gridcode_pf_range_when_present() -> None:
    """gridcode.pf_range (D2 structured location) takes precedence over top-level pf_range."""
    grid = {**_BESS_GRID, "gridcode": {"pf_range": [-0.90, 0.90]}}
    _strength, reactive = screen_bess_capability(grid, use_pandapower=False)
    assert (reactive.pf_required_min, reactive.pf_required_max) == (-0.90, 0.90)


def test_screen_rejects_non_storage_type() -> None:
    grid = {**_BESS_GRID, "type": "wind"}
    with pytest.raises(ValueError, match="STORAGE plug-in"):
        screen_bess_capability(grid, use_pandapower=False)


def test_screen_requires_poc_kv() -> None:
    grid = {k: v for k, v in _BESS_GRID.items() if k != "poc_voltage_kv"}
    with pytest.raises(ValueError, match="poc_voltage_kv"):
        screen_bess_capability(grid, use_pandapower=False)


def test_screen_requires_sc_contribution() -> None:
    grid = {k: v for k, v in _BESS_GRID.items() if k != "sc_contribution_pu"}
    with pytest.raises(ValueError, match="sc_contribution_pu"):
        screen_bess_capability(grid, use_pandapower=False)


def test_screen_requires_grid_code_pf_range() -> None:
    grid = {k: v for k, v in _BESS_GRID.items() if k != "pf_range"}
    # q_rated_mvar is explicit so the rating resolves; the grid-code demand is what's absent.
    with pytest.raises(ValueError, match="grid-code pf_range"):
        screen_bess_capability(grid, use_pandapower=False)


def test_screen_grid_code_pf_range_out_of_range_raises() -> None:
    # A grid-code pf_range whose binding endpoint is out of (0, 1] is rejected — an explicit
    # q_rated_mvar keeps the rating resolvable so the grid-code demand is the failing input.
    grid = {**_BESS_GRID, "gridcode": {"pf_range": [0.0, 0.95]}}
    with pytest.raises(ValueError, match=r"magnitude in \(0, 1\]"):
        screen_bess_capability(grid, use_pandapower=False)


def test_screen_requires_source_fault_level() -> None:
    grid = {k: v for k, v in _BESS_GRID.items() if k != "source_fault_level_mva"}
    with pytest.raises(ValueError, match="source_fault_level_mva"):
        screen_bess_capability(grid, use_pandapower=False)


def test_screen_default_type_is_bess() -> None:
    """A block with no explicit 'type' defaults to bess (storage) and screens cleanly."""
    grid = {k: v for k, v in _BESS_GRID.items() if k != "type"}
    strength, reactive = screen_bess_capability(grid, use_pandapower=False)
    assert strength.bankable is False
    assert reactive.bankable is False
