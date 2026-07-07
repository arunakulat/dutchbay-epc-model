"""Grid-FREE coverage for the D5c hybrid combined frequency-droop study (#881).

These tests import NO grid library (``pandapower`` / ``andes`` are ABSENT in the default
venv) and are NOT marked ``grid`` — so they run in the default ``-m 'not grid'`` coverage
lane and carry the real coverage for :mod:`analytics.grid.hybrid.frequency_response`. The
per-group droop split, the SOC integration (via the shared D5a model), the settling-frequency
estimate, the band-compliance / adequacy verdicts and EVERY CESSPIT raise + NOT-RUN branch
are all pure Python and are exercised here. The only ANDES-touching line
(:func:`_attempt_dynamic_nadir`) reaches ``andes`` through the shared D4a machinery at
call-time and is covered by the ``grid``-marked companion.

They exercise:
  * ``compute_group_droop_split`` — the ENPPC per-group droop math ``ΔP=(|Δf|/f_n)/R·P``
    reproducing a KNOWN event split, the priority-order residual dispatch, headroom capping
    (wind spinning/de-load for up- vs down-regulation), and the BESS SOC-energy limit via
    the shared D5a ``bess_soc_state`` / ``split_reserves`` (no double-count), plus every
    strict raise (bad groups list, >6 groups, bad droop/rating, bad priority order, bad Δf);
  * ``run_hybrid_frequency_response`` — the full study emit: band compliance vs the grid-code
    band, response adequacy, the zero-command NOT-RUN branches, the grid/ppc/event strict
    raises, and the dynamic-gate-OFF path (no ANDES import).
"""

from __future__ import annotations

import sys
from typing import Any

import pytest

from analytics.contracts_v14 import FreqResponseResult, GroupDroopContribution
from analytics.grid.hybrid import frequency_response
from analytics.grid.hybrid.frequency_response import (
    compute_group_droop_split,
    run_hybrid_frequency_response,
)

# A DutchBay-shaped hybrid ENPPC: two wind groups (100 MW + 50 MW, both 4 % droop) and one
# 40 MW BESS group (4 % droop, a 40 MWh pack at 50 % SoC), all dispatched wind-first.
_WG1 = {"name": "wg1", "tech": "wind", "rated_mw": 100.0, "freq_droop_pct": 4.0}
_WG2 = {"name": "wg2", "tech": "wind", "rated_mw": 50.0, "freq_droop_pct": 4.0}
_BESS_GROUP = {
    "name": "bess",
    "tech": "bess",
    "rated_mw": 40.0,
    "freq_droop_pct": 4.0,
    "output_mw": 0.0,
    "energy_mwh": 40.0,
    "soh_fraction": 1.0,
    "min_soc": 0.10,
    "max_soc": 0.95,
    "soc_fraction": 0.50,
}
_GRIDCODE = {"freq_ride_through": {"continuous_hz": [47.5, 51.5]}}


def _ppc(*groups: dict[str, Any], order: list[str] | None = None) -> dict[str, Any]:
    names = [g["name"] for g in groups]
    return {"groups": list(groups), "p_priority_order": order or names}


# ─────────────────────────────────────────────── compute_group_droop_split (math)


def test_known_event_reproduces_per_group_droop_shares_and_plant_obligation() -> None:
    # Under-frequency -0.4 Hz on 4 % droop: each group's OWN droop share is ΔP_g =
    # (0.4/50)/0.04 * P = 0.2 * P → wg1 20 MW, wg2 10 MW. The PLANT OBLIGATION the PPC fills
    # is their SUM = 30 MW. Both groups have ample headroom (de-loaded), so the fleet meets
    # the full obligation.
    wg1 = dict(_WG1, output_mw=60.0)  # 40 MW up-headroom
    wg2 = dict(_WG2, output_mw=20.0)  # 30 MW up-headroom
    contribs, cmd, deliv = compute_group_droop_split(_ppc(wg1, wg2), deviation_hz=-0.4)
    assert [c.name for c in contribs] == ["wg1", "wg2"]  # returned in priority order
    # The per-group droop SHARES reproduce the known split.
    assert contribs[0].commanded_mw == pytest.approx(20.0)
    assert contribs[1].commanded_mw == pytest.approx(10.0)
    # The plant obligation (Σ shares) is met by the fleet.
    assert cmd == pytest.approx(30.0)
    assert deliv == pytest.approx(30.0)
    # wg1 (first, 40 MW headroom) fills the 30 MW obligation entirely; wg2 gets the residual.
    assert contribs[0].delivered_mw == pytest.approx(30.0)
    assert contribs[1].delivered_mw == pytest.approx(0.0)
    assert all(isinstance(c, GroupDroopContribution) for c in contribs)


def test_droop_split_scales_with_droop_setting() -> None:
    # A stiffer 2 % droop group is commanded DOUBLE the ΔP of a 4 % droop group at the same
    # rating (1/R gain): (0.2/50)/0.02*100 = 20 vs (0.2/50)/0.04*100 = 10.
    stiff = {
        "name": "stiff",
        "tech": "wind",
        "rated_mw": 100.0,
        "freq_droop_pct": 2.0,
        "output_mw": 0.0,
    }
    soft = {
        "name": "soft",
        "tech": "wind",
        "rated_mw": 100.0,
        "freq_droop_pct": 4.0,
        "output_mw": 0.0,
    }
    contribs, _, _ = compute_group_droop_split(_ppc(stiff, soft), deviation_hz=-0.2)
    by = {c.name: c for c in contribs}
    assert by["stiff"].commanded_mw == pytest.approx(20.0)
    assert by["soft"].commanded_mw == pytest.approx(10.0)


def test_over_frequency_down_regulation_headroom_is_output() -> None:
    # Over-frequency +0.4 Hz → DOWN-regulation: a group can shed only its current output.
    wg = dict(_WG1, output_mw=15.0)  # commanded 20 MW but can only shed 15 MW
    contribs, cmd, deliv = compute_group_droop_split(_ppc(wg), deviation_hz=+0.4)
    assert contribs[0].commanded_mw == pytest.approx(20.0)
    assert contribs[0].headroom_mw == pytest.approx(15.0)  # capped at output
    assert contribs[0].delivered_mw == pytest.approx(15.0)
    assert cmd == pytest.approx(20.0)
    assert deliv == pytest.approx(15.0)  # under-delivered → inadequate downstream


def test_priority_order_is_load_bearing_changes_the_split() -> None:
    # PPC aggregate-fill: the plant obligation is dispatched in priority order up to each
    # group's HEADROOM, so REORDERING p_priority_order CHANGES the delivered split. Two
    # groups, each 100 MW headroom (de-loaded), plant obligation 30 MW: whichever group is
    # FIRST takes the whole 30 MW, the other gets the residual 0. This is the PPC covering
    # the obligation with the highest-priority group's headroom — impossible under a purely
    # decentralized per-group droop (where each would deliver only its own 20/10 share).
    wg1 = dict(_WG1, output_mw=0.0)  # 100 MW headroom
    wg2 = dict(_WG2, output_mw=0.0)  # 50 MW headroom (still > 30 MW obligation)

    a = {
        c.name: c
        for c in compute_group_droop_split(
            _ppc(wg1, wg2, order=["wg1", "wg2"]), deviation_hz=-0.4
        )[0]
    }
    assert a["wg1"].delivered_mw == pytest.approx(30.0)
    assert a["wg2"].delivered_mw == pytest.approx(0.0)

    b = {
        c.name: c
        for c in compute_group_droop_split(
            _ppc(wg1, wg2, order=["wg2", "wg1"]), deviation_hz=-0.4
        )[0]
    }
    assert b["wg2"].delivered_mw == pytest.approx(30.0)
    assert b["wg1"].delivered_mw == pytest.approx(0.0)

    # The split genuinely differs by order (the LOAD-BEARING proof).
    assert a["wg1"].delivered_mw != b["wg1"].delivered_mw


def test_priority_order_changes_which_bess_is_soc_limited_out() -> None:
    # The stronger PPC proof: with a headroom-limited fleet, the priority order changes WHICH
    # BESS group is dispatched to its SOC-bound cap (SOC-limited-out). A big wind group
    # (60 MW headroom) + a tiny-energy BESS (SOC-bound at 4.8 MW). Plant obligation = wind
    # 0.2*100=20 + bess 0.2*40=8 = 28 MW.
    wind = {
        "name": "wind",
        "tech": "wind",
        "rated_mw": 100.0,
        "freq_droop_pct": 4.0,
        "output_mw": 40.0,
    }  # 60 MW headroom
    bess = dict(_BESS_GROUP, name="bess", energy_mwh=0.05)  # SOC-bound ~4.8 MW at 15 s

    # Wind FIRST: wind covers the whole 28 MW obligation from its 60 MW headroom; the BESS
    # is never dispatched → NOT SOC-limited-out (physical evidence, not a hypothetical).
    wind_first = {
        c.name: c
        for c in compute_group_droop_split(
            _ppc(wind, bess, order=["wind", "bess"]), deviation_hz=-0.4, sustain_s=15.0
        )[0]
    }
    assert wind_first["wind"].delivered_mw == pytest.approx(28.0)
    assert wind_first["bess"].delivered_mw == pytest.approx(0.0)
    assert wind_first["bess"].soc_limited is False

    # BESS FIRST: the PPC pushes the BESS to its SOC-bound headroom (4.8 MW) → SOC-limited-out;
    # wind picks up the residual 28 - 4.8 = 23.2 MW.
    bess_first = {
        c.name: c
        for c in compute_group_droop_split(
            _ppc(wind, bess, order=["bess", "wind"]), deviation_hz=-0.4, sustain_s=15.0
        )[0]
    }
    assert bess_first["bess"].delivered_mw == pytest.approx(4.8)
    assert bess_first["bess"].soc_limited is True
    assert bess_first["wind"].delivered_mw == pytest.approx(23.2)
    # Same fleet, same event — only the priority changed the SOC-limited-out verdict.
    assert wind_first["bess"].soc_limited != bess_first["bess"].soc_limited


def test_full_output_group_has_no_up_headroom() -> None:
    # A group at full output (default when no output_mw / dispatch_fraction) has ZERO
    # up-regulation spinning headroom, so it delivers nothing on under-frequency.
    contribs, cmd, deliv = compute_group_droop_split(_ppc(_WG1), deviation_hz=-0.4)
    assert contribs[0].commanded_mw == pytest.approx(20.0)
    assert contribs[0].headroom_mw == pytest.approx(0.0)
    assert contribs[0].delivered_mw == pytest.approx(0.0)
    assert deliv == pytest.approx(0.0)


def test_dispatch_fraction_sets_up_headroom() -> None:
    # dispatch_fraction=0.4 on a 100 MW group → output 40 MW, up-headroom 60 MW.
    wg = {
        "name": "wg",
        "tech": "wind",
        "rated_mw": 100.0,
        "freq_droop_pct": 4.0,
        "dispatch_fraction": 0.4,
    }
    contribs, _, _ = compute_group_droop_split(_ppc(wg), deviation_hz=-0.4)
    assert contribs[0].headroom_mw == pytest.approx(60.0)


# ─────────────────────────────────────────────── BESS SOC integration (shared D5a)


def test_bess_group_soc_energy_limited() -> None:
    # A 40 MW BESS, alone, must cover the whole 8 MW plant obligation (0.2*40). Its ample
    # 40 MWh pack (dischargeable (0.5-0.1)*40 = 16 MWh) sustains the full 40 MW power headroom
    # over 15 s, so it is NOT SOC-bound and delivers the 8 MW obligation without being pushed
    # to its cap → soc_limited False.
    contribs, cmd, deliv = compute_group_droop_split(
        _ppc(_BESS_GROUP), deviation_hz=-0.4, sustain_s=15.0
    )
    assert contribs[0].commanded_mw == pytest.approx(8.0)
    assert contribs[0].delivered_mw == pytest.approx(8.0)
    assert contribs[0].soc_limited is False


def test_bess_group_soc_binds_when_energy_tiny() -> None:
    # A tiny 0.05 MWh pack, alone, faces an 8 MW obligation but its SOC-bound headroom is only
    # dischargeable (0.5-0.1)*0.05 = 0.02 MWh → over 15 s supports 0.02*3600/15 = 4.8 MW. The
    # PPC dispatches it to that SOC-bound cap → delivered 4.8 MW, SOC-limited-out.
    small = dict(_BESS_GROUP, energy_mwh=0.05)
    contribs, cmd, deliv = compute_group_droop_split(
        _ppc(small), deviation_hz=-0.4, sustain_s=15.0
    )
    assert contribs[0].commanded_mw == pytest.approx(8.0)
    assert contribs[0].headroom_mw == pytest.approx(4.8)
    assert contribs[0].delivered_mw == pytest.approx(4.8)
    assert contribs[0].soc_limited is True


def test_bess_no_double_count_with_firming_reserve() -> None:
    # A firming reserve committed to the SAME dischargeable headroom cannot be re-claimed by
    # frequency (D5a no-double-count). Small pack: dischargeable (0.5-0.1)*0.05 = 0.02 MWh.
    # The SOC energy is sized against the group's POWER headroom (40 MW — the max the PPC
    # could dispatch it to): frequency needs 40 MW * 15/3600 = 0.16667 MWh; firming asks
    # 0.015 MWh; the discharge direction is over-subscribed (0.18167 > 0.02), so D5a clamps
    # PROPORTIONALLY — the frequency reserve gets 0.02 * (0.16667/0.18167) MWh, LESS than its
    # firming-free share (the same MWh is never double-counted). That energy over 15 s sets
    # the SOC-bound headroom, and the group is dispatched to it.
    small = dict(_BESS_GROUP, energy_mwh=0.05, firming_reserve_mwh=0.015)
    freq_needed_mwh = 40.0 * 15.0 / 3600.0
    firming_mwh = 0.015
    dischargeable_mwh = (0.50 - 0.10) * 0.05
    freq_alloc_mwh = dischargeable_mwh * (
        freq_needed_mwh / (freq_needed_mwh + firming_mwh)
    )
    expected_mw = freq_alloc_mwh * 3600.0 / 15.0
    contribs, _, deliv = compute_group_droop_split(
        _ppc(small), deviation_hz=-0.4, sustain_s=15.0
    )
    assert contribs[0].delivered_mw == pytest.approx(expected_mw)
    assert contribs[0].delivered_mw < 4.8  # strictly less than the firming-free 4.8 MW
    assert contribs[0].soc_limited is True


def test_bess_power_headroom_binds_over_soc() -> None:
    # A BESS already discharging near its rating has little converter power headroom even
    # with ample energy — the power cap binds, not the SOC energy (soc_limited stays False).
    b = dict(_BESS_GROUP, output_mw=38.0)  # only 2 MW power headroom; command 8 MW
    contribs, _, _ = compute_group_droop_split(_ppc(b), deviation_hz=-0.4)
    assert contribs[0].delivered_mw == pytest.approx(2.0)
    assert contribs[0].soc_limited is False  # power-limited, not SOC-limited


# ─────────────────────────────────────────────── CESSPIT strict raises (split)


def test_split_missing_groups_raises() -> None:
    with pytest.raises(ValueError, match="ppc.groups"):
        compute_group_droop_split({"p_priority_order": []}, deviation_hz=-0.4)


def test_split_empty_groups_raises() -> None:
    with pytest.raises(ValueError, match="at least one mapping"):
        compute_group_droop_split(
            {"groups": [], "p_priority_order": []}, deviation_hz=-0.4
        )


def test_split_more_than_six_groups_raises() -> None:
    groups = [
        {"name": f"g{i}", "tech": "wind", "rated_mw": 10.0, "freq_droop_pct": 4.0}
        for i in range(7)
    ]
    with pytest.raises(ValueError, match="up to 6 dispatch groups"):
        compute_group_droop_split(
            {"groups": groups, "p_priority_order": [g["name"] for g in groups]},
            deviation_hz=-0.4,
        )


def test_split_missing_tech_raises() -> None:
    with pytest.raises(ValueError, match="tech/type token"):
        compute_group_droop_split(
            _ppc({"name": "g", "rated_mw": 10.0, "freq_droop_pct": 4.0}),
            deviation_hz=-0.4,
        )


@pytest.mark.parametrize("bad_droop", [0.0, -4.0, float("nan"), "x", True])
def test_split_bad_droop_raises(bad_droop: object) -> None:
    g = {"name": "g", "tech": "wind", "rated_mw": 10.0, "freq_droop_pct": bad_droop}
    with pytest.raises(ValueError, match="freq_droop_pct"):
        compute_group_droop_split(_ppc(g), deviation_hz=-0.4)


@pytest.mark.parametrize("bad_rating", [0.0, -10.0, float("inf"), None])
def test_split_bad_rating_raises(bad_rating: object) -> None:
    g = {"name": "g", "tech": "wind", "rated_mw": bad_rating, "freq_droop_pct": 4.0}
    with pytest.raises(ValueError, match="rated_mw"):
        compute_group_droop_split(_ppc(g), deviation_hz=-0.4)


def test_split_missing_priority_order_raises() -> None:
    with pytest.raises(ValueError, match="p_priority_order"):
        compute_group_droop_split({"groups": [_WG1]}, deviation_hz=-0.4)


def test_split_priority_order_wrong_names_raises() -> None:
    with pytest.raises(ValueError, match="EXACTLY the"):
        compute_group_droop_split(
            {"groups": [_WG1, _WG2], "p_priority_order": ["wg1", "wg1"]},
            deviation_hz=-0.4,
        )


def test_split_priority_order_missing_group_raises() -> None:
    with pytest.raises(ValueError, match="EXACTLY the"):
        compute_group_droop_split(
            {"groups": [_WG1, _WG2], "p_priority_order": ["wg1"]}, deviation_hz=-0.4
        )


@pytest.mark.parametrize("bad_dev", [float("nan"), float("inf"), "x", None, True])
def test_split_bad_deviation_raises(bad_dev: object) -> None:
    with pytest.raises(ValueError, match="deviation_hz"):
        compute_group_droop_split(_ppc(_WG1), deviation_hz=bad_dev)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad_nom", [0.0, -50.0])
def test_split_bad_nominal_raises(bad_nom: float) -> None:
    with pytest.raises(ValueError, match="nominal_hz must be > 0"):
        compute_group_droop_split(_ppc(_WG1), deviation_hz=-0.4, nominal_hz=bad_nom)


@pytest.mark.parametrize("bad_sustain", [0.0, -15.0])
def test_split_bad_sustain_raises(bad_sustain: float) -> None:
    with pytest.raises(ValueError, match="sustain_s must be > 0"):
        compute_group_droop_split(_ppc(_WG1), deviation_hz=-0.4, sustain_s=bad_sustain)


def test_bess_bad_output_raises() -> None:
    # Output above rating is rejected (active power cannot exceed the rating).
    b = dict(_BESS_GROUP, output_mw=99.0)  # > 40 MW rating
    with pytest.raises(ValueError, match="outside"):
        compute_group_droop_split(_ppc(b), deviation_hz=-0.4)


def test_bess_bad_soc_fraction_raises() -> None:
    b = dict(_BESS_GROUP, soc_fraction=1.5)  # outside [0, 1]
    with pytest.raises(ValueError, match="soc_fraction"):
        compute_group_droop_split(_ppc(b), deviation_hz=-0.4)


def test_bess_bad_firming_reserve_raises() -> None:
    b = dict(_BESS_GROUP, energy_mwh=0.05, firming_reserve_mwh=-1.0)
    with pytest.raises(ValueError, match="firming_reserve_mwh"):
        compute_group_droop_split(_ppc(b), deviation_hz=-0.4)


# ─────────────────────────────────────────────── run_hybrid_frequency_response


def test_run_full_delivery_band_compliant_and_adequate() -> None:
    wg1 = dict(_WG1, output_mw=0.0)
    wg2 = dict(_WG2, output_mw=0.0)
    cfg = {
        "grid": {
            "ppc": _ppc(wg1, wg2),
            "freq_event_hz": 49.6,  # Δf = -0.4 Hz
            "gridcode": _GRIDCODE,
        }
    }
    res = run_hybrid_frequency_response(cfg)
    assert isinstance(res, FreqResponseResult)
    assert res.bankable is False
    assert res.method == "enppc_group_droop"
    assert res.deviation_hz == pytest.approx(-0.4)
    assert res.total_commanded_mw == pytest.approx(30.0)
    assert res.total_delivered_mw == pytest.approx(30.0)
    # Full delivery restores frequency to nominal → inside the band, adequate.
    assert res.settling_frequency_hz == pytest.approx(50.0)
    assert res.band_compliant is True
    assert res.response_adequate is True
    assert res.dynamic_ran is False
    assert res.dynamic_nadir_hz is None
    assert res.n_groups == 2
    assert res.n_soc_limited == 0


def test_run_partial_delivery_inadequate_and_band_screened() -> None:
    # Both groups at full output → zero up-headroom → nothing delivered on under-frequency.
    cfg = {
        "grid": {
            "ppc": _ppc(_WG1, _WG2),
            "freq_event_hz": 49.6,
            "gridcode": _GRIDCODE,
        }
    }
    res = run_hybrid_frequency_response(cfg)
    assert res.total_delivered_mw == pytest.approx(0.0)
    # Zero delivery leaves the full deviation → settling stays at the event frequency.
    assert res.settling_frequency_hz == pytest.approx(49.6)
    assert res.band_compliant is True  # 49.6 still inside [47.5, 51.5]
    assert res.response_adequate is False  # commanded 30, delivered 0


def test_run_band_non_compliant_when_settling_outside_band() -> None:
    # A deep under-frequency event with no headroom leaves the settling frequency BELOW the
    # band's lower edge → band_compliant False (a real breach from physical evidence).
    cfg = {
        "grid": {
            "ppc": _ppc(_WG1),
            "freq_event_hz": 47.0,  # Δf = -3.0 Hz, below the 47.5 band edge
            "gridcode": _GRIDCODE,
        }
    }
    res = run_hybrid_frequency_response(cfg)
    assert res.total_delivered_mw == pytest.approx(0.0)
    assert res.settling_frequency_hz == pytest.approx(47.0)
    assert res.band_compliant is False
    assert res.response_adequate is False


def test_run_soc_limited_group_counted() -> None:
    small = dict(_BESS_GROUP, energy_mwh=0.05)
    cfg = {"grid": {"ppc": _ppc(small), "freq_event_hz": 49.6, "gridcode": _GRIDCODE}}
    res = run_hybrid_frequency_response(cfg)
    assert res.n_soc_limited == 1
    assert res.response_adequate is False  # SOC could not sustain the full command


def test_run_zero_command_event_is_not_run() -> None:
    # A nominal event (Δf = 0) has no command → both verdicts NOT-RUN (None), no fabricated
    # pass, and no settling point.
    cfg = {"grid": {"ppc": _ppc(_WG1), "freq_event_hz": 50.0, "gridcode": _GRIDCODE}}
    res = run_hybrid_frequency_response(cfg)
    assert res.deviation_hz == pytest.approx(0.0)
    assert res.total_commanded_mw == pytest.approx(0.0)
    assert res.settling_frequency_hz is None
    assert res.band_compliant is None
    assert res.response_adequate is None


def test_run_explicit_deviation_overrides_event() -> None:
    cfg = {"grid": {"ppc": _ppc(dict(_WG1, output_mw=0.0)), "gridcode": _GRIDCODE}}
    res = run_hybrid_frequency_response(cfg, deviation_hz=-0.2)
    assert res.deviation_hz == pytest.approx(-0.2)
    assert res.total_commanded_mw == pytest.approx(10.0)


def test_run_over_frequency_direction_note() -> None:
    cfg = {
        "grid": {
            "ppc": _ppc(dict(_WG1, output_mw=50.0)),
            "freq_event_hz": 50.4,  # over-frequency
            "gridcode": _GRIDCODE,
        }
    }
    res = run_hybrid_frequency_response(cfg)
    assert "over-frequency" in res.notes
    assert res.deviation_hz == pytest.approx(0.4)


def test_run_accepts_bare_grid_block() -> None:
    # A grid-shaped mapping carrying ppc directly (not under a 'grid' key) is accepted.
    grid = {
        "ppc": _ppc(dict(_WG1, output_mw=0.0)),
        "freq_event_hz": 49.8,
        "gridcode": _GRIDCODE,
    }
    res = run_hybrid_frequency_response(grid)
    assert res.deviation_hz == pytest.approx(-0.2)


def test_run_custom_sustain_from_config() -> None:
    # A mandated sustain window read from config; a longer window needs more energy, so a
    # small pack becomes MORE SOC-limited.
    small = dict(_BESS_GROUP, energy_mwh=0.05)
    cfg = {
        "grid": {
            "ppc": _ppc(small),
            "freq_event_hz": 49.6,
            "gridcode": _GRIDCODE,
            "freq_response_sustain_s": 30.0,
        }
    }
    res = run_hybrid_frequency_response(cfg)
    assert res.sustain_s == pytest.approx(30.0)
    # dischargeable 0.02 MWh over 30 s → 0.02*3600/30 = 2.4 MW (< the 8 MW command).
    assert res.total_delivered_mw == pytest.approx(2.4)


def test_run_custom_provenance() -> None:
    cfg = {"grid": {"ppc": _ppc(dict(_WG1, output_mw=0.0)), "freq_event_hz": 49.8}}
    res = run_hybrid_frequency_response(cfg, provenance="CUSTOM PROV")
    assert res.provenance == "CUSTOM PROV"


def test_run_dynamics_gate_on_reports_not_run_nadir_grid_free(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """run_dynamics=True is grid-free-SAFE for the frequency case and MUST NOT fabricate.

    As of D4b (#892) the frequency case DOES apply a real excursion, so
    ``run_ride_through_case("frequency", run_dynamics=True)`` reaches the CASPER
    ``_require_andes`` guard — which, without andes importable, raises ImportError.
    ``_attempt_dynamic_nadir`` catches that and DEGRADES to the honest NOT-RUN
    (``dynamic_ran=False``, ``dynamic_nadir_hz=None``), never derived from the closed-form
    settling estimate (NO SPURIOUS PASS). This exercises the dynamic-gate branch +
    ``_attempt_dynamic_nadir`` CASPER fallback without touching ANDES. Absence is
    SIMULATED (poisoned ``sys.modules`` entry) so the test is environment-independent —
    it passes with or without the [grid] extra installed.
    """
    monkeypatch.setitem(sys.modules, "andes", None)
    cfg = {"grid": {"ppc": _ppc(dict(_WG1, output_mw=0.0)), "freq_event_hz": 49.6}}
    res = run_hybrid_frequency_response(cfg, run_dynamics=True)
    # The closed-form deliverable is still physically produced.
    assert res.total_delivered_mw == pytest.approx(20.0)
    # Grid-free (no andes): the dynamic nadir degrades to an honest NOT-RUN — no fabrication.
    assert res.dynamic_nadir_hz is None
    assert res.dynamic_ran is False


# ─────────────────────────────────────────────── run raises (CESSPIT)


def test_run_missing_grid_block_raises() -> None:
    with pytest.raises(ValueError, match="'grid' block"):
        run_hybrid_frequency_response({"foo": 1})


def test_run_non_mapping_config_raises() -> None:
    with pytest.raises(ValueError, match="config mapping"):
        run_hybrid_frequency_response(None)  # type: ignore[arg-type]


def test_run_missing_ppc_raises() -> None:
    with pytest.raises(ValueError, match="grid.ppc"):
        run_hybrid_frequency_response({"grid": {"gridcode": _GRIDCODE}})


def test_run_missing_event_raises() -> None:
    # No explicit deviation AND no grid.freq_event_hz → strict raise (no silent nominal).
    with pytest.raises(ValueError, match="event frequency"):
        run_hybrid_frequency_response({"grid": {"ppc": _ppc(_WG1)}})


@pytest.mark.parametrize("bad_event", [0.0, -1.0, "x", None])
def test_run_bad_event_frequency_raises(bad_event: object) -> None:
    with pytest.raises(ValueError, match="event frequency"):
        run_hybrid_frequency_response(
            {"grid": {"ppc": _ppc(_WG1), "freq_event_hz": bad_event}}
        )


@pytest.mark.parametrize("bad_dev", [float("nan"), "x"])
def test_run_bad_explicit_deviation_raises(bad_dev: object) -> None:
    with pytest.raises(ValueError, match="deviation_hz"):
        run_hybrid_frequency_response(
            {"grid": {"ppc": _ppc(_WG1)}}, deviation_hz=bad_dev  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("bad_sustain", [0.0, -5.0, "x"])
def test_run_bad_sustain_raises(bad_sustain: object) -> None:
    cfg = {
        "grid": {
            "ppc": _ppc(_WG1),
            "freq_event_hz": 49.6,
            "freq_response_sustain_s": bad_sustain,
        }
    }
    with pytest.raises(ValueError, match="freq_response_sustain_s"):
        run_hybrid_frequency_response(cfg)


def test_module_all_surface() -> None:
    assert set(frequency_response.__all__) == {
        "GroupDroopContribution",
        "compute_group_droop_split",
        "run_hybrid_frequency_response",
    }


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
