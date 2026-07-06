"""Grid-FREE coverage for the D5b static hybrid-POC aggregation (#880).

These tests import NO grid library (pandapower / andes are ABSENT in the default venv) and
are NOT marked ``grid`` — so they run in the default ``-m 'not grid'`` coverage lane and
carry the real coverage for :mod:`analytics.grid.hybrid.poc_aggregation`. They exercise:

  * the per-resource dispatch (:func:`resource_contribution`) into the D4b/c/d plug-ins —
    wind (Type-3 DFIG partial-load narrowing vs Type-4 rectangular box), solar (current-
    limited, ≈0 fault contribution), BESS (SoH-degraded ±Q + a real PCS fault contribution);
  * the COMPOSITE / weighted SCR fold: source + Σ PCS fault contributions over Σ IBR MVA,
    and the LOAD-BEARING hybrid rule that adding IBR behind the POC LOWERS the SCR;
  * the AGGREGATE ±Q(P) vector sum MINUS the collector/transformer reactive path (absolute,
    fractional, and the lossless-default forms), the PQ-box verdict + shortfall; and
  * every CESSPIT strict-input raise (absent grid / resources, unrecognised tech, missing
    POC voltage / source fault level / grid-code pf_range, bad collector-loss keys).

The aggregation reuses the per-tech plug-ins, whose only optional-dependency paths live
inside the D1 SCR screen (grid-marked companions cover those); this static aggregation has
NO pandapower/andes-only lines of its own.
"""

from __future__ import annotations

import math

import pytest

from analytics.contracts_v14 import (
    PocCapabilityEnvelope,
    ResourceReactiveContribution,
)
from analytics.grid.hybrid import poc_aggregation
from analytics.grid.hybrid.poc_aggregation import (
    aggregate_poc_capability,
    resource_contribution,
)
from analytics.grid.reactive_screen import pf_to_qp_ratio

# A DutchBay-shaped hybrid POC: 100 MVA Type-4 wind + 60 MWp / 1.2 ILR solar (50 MVA AC) +
# a 10.64 MVA / ±3 Mvar Envision BESS site, all behind one 33 kV POC on an 800 MVA source,
# grid-code ±0.95 pf, with a 5% collector/transformer reactive loss.
_WIND_RES = {
    "name": "wind",
    "tech": "wind",
    "converter_type": "type4_full_converter",
    "rated_mva": 100.0,
    "pf_range": [-0.95, 0.95],
}
_SOLAR_RES = {
    "name": "solar",
    "tech": "solar",
    "dc_capacity_mw": 60.0,
    "dc_ac_ratio": 1.2,
    "gridcode": {"pf_range": [-0.95, 0.95]},
}
_BESS_RES = {
    "name": "bess",
    "tech": "bess",
    "rated_mva": 10.64,
    "q_rated_mvar": 3.0,
    "sc_contribution_pu": 1.1,
    "pf_range": [-0.95, 0.95],
    "soh_curve": {1: 1.0, 15: 0.765},
}
_HYBRID_GRID = {
    "grid": {
        "poc_voltage_kv": 33.0,
        "source_fault_level_mva": 800.0,
        "gridcode": {"pf_range": [-0.95, 0.95]},
        "collector_transformer_q_loss_fraction": 0.05,
        "resources": [_WIND_RES, _SOLAR_RES, _BESS_RES],
    }
}

_QP95 = pf_to_qp_ratio(0.95)


# ----------------------------------------------------- per-resource dispatch (wind/solar/bess)


def test_wind_contribution_type4_rectangular_box() -> None:
    c = resource_contribution(_WIND_RES, p_fraction=1.0)
    assert isinstance(c, ResourceReactiveContribution)
    assert c.tech == "wind"
    assert c.rated_mva == pytest.approx(100.0)
    # Type-4 full converter: full ±Q at rated P = rated_mva · tan(acos(0.95)).
    assert c.q_available_mvar == pytest.approx(100.0 * _QP95)
    # Grid-following: contributes ≈0 to the POC fault level, non-synchronous.
    assert c.fault_mva_contribution == pytest.approx(0.0)
    assert c.is_synchronous is False


def test_wind_contribution_type3_narrows_at_partial_load() -> None:
    dfig = {**_WIND_RES, "converter_type": "type3_dfig"}
    full = resource_contribution(dfig, p_fraction=1.0)
    half = resource_contribution(dfig, p_fraction=0.5)
    # A Type-3 DFIG's ±Q NARROWS at partial load — the crux of D4b, preserved by aggregation.
    assert half.q_available_mvar < full.q_available_mvar


def test_solar_contribution_current_limited_zero_fault() -> None:
    c = resource_contribution(_SOLAR_RES, p_fraction=1.0)
    assert c.tech == "solar"
    # AC export rating = DC 60 / ILR 1.2 = 50 MVA (inverter efficiency NOT re-applied, D4c).
    assert c.rated_mva == pytest.approx(50.0)
    assert c.q_available_mvar == pytest.approx(50.0 * _QP95)
    # Solar is current-limited grid-following: ≈0 fault contribution, non-synchronous.
    assert c.fault_mva_contribution == pytest.approx(0.0)
    assert c.is_synchronous is False


def test_solar_contribution_explicit_pf_capability_overrides() -> None:
    res = {**_SOLAR_RES, "pf_capability": 0.90}
    c = resource_contribution(res, p_fraction=1.0)
    # The tighter inverter pf capability governs the ±Q, not the grid-code 0.95.
    assert c.q_available_mvar == pytest.approx(50.0 * pf_to_qp_ratio(0.90))


def test_solar_contribution_out_of_range_pf_capability_falls_back() -> None:
    # An out-of-(0,1] pf_capability is ignored → falls back to the grid-code binding pf.
    res = {**_SOLAR_RES, "pf_capability": 1.5}
    c = resource_contribution(res, p_fraction=1.0)
    assert c.q_available_mvar == pytest.approx(50.0 * _QP95)


def test_bess_contribution_soh_degraded_q_and_real_fault() -> None:
    c = resource_contribution(_BESS_RES, reference_year=None)
    assert c.tech == "bess"
    assert c.rated_mva == pytest.approx(10.64)
    # SoH-degraded (year-15) reactive headroom = 3.0 · 0.765, NOT the BoL 3.0.
    assert c.q_available_mvar == pytest.approx(3.0 * 0.765)
    # The PCS presents a REAL current-limited fault contribution = sc_pu · rated_mva_bol.
    assert c.fault_mva_contribution == pytest.approx(1.1 * 10.64)
    assert c.is_synchronous is False


def test_bess_contribution_reference_year_bol() -> None:
    c = resource_contribution(_BESS_RES, reference_year=1)
    assert c.q_available_mvar == pytest.approx(3.0)  # full BoL headroom


def test_dispatch_unrecognised_tech_raises() -> None:
    with pytest.raises(ValueError, match="recognised tech/type"):
        resource_contribution({"tech": "tidal", "rated_mva": 5.0})


def test_dispatch_missing_tech_raises() -> None:
    with pytest.raises(ValueError, match="recognised tech/type"):
        resource_contribution({"rated_mva": 5.0})


def test_dispatch_p_fraction_clamped() -> None:
    # p_fraction is clamped to [0, 1]; > 1 behaves like full export.
    over = resource_contribution(_WIND_RES, p_fraction=5.0)
    full = resource_contribution(_WIND_RES, p_fraction=1.0)
    assert over.q_available_mvar == pytest.approx(full.q_available_mvar)


# --------------------------------------------------------------------- aggregate (end-to-end)


def test_aggregate_composite_scr_and_fault_fold() -> None:
    env = aggregate_poc_capability(_HYBRID_GRID)
    assert isinstance(env, PocCapabilityEnvelope)
    assert env.n_resources == 3
    # Total IBR MVA = wind 100 + solar 50 + bess 10.64.
    assert env.total_ibr_mva == pytest.approx(160.64)
    # Only the BESS PCS folds into the fault level (wind/solar add ≈0).
    assert env.aggregate_fault_level_mva == pytest.approx(800.0 + 1.1 * 10.64)
    assert env.composite_scr == pytest.approx((800.0 + 1.1 * 10.64) / 160.64)
    assert env.scr_band in {"weak", "marginal", "strong"}
    assert env.bankable is False
    assert env.method == "static_poc_aggregation"


def test_aggregate_adding_ibr_lowers_scr() -> None:
    """The LOAD-BEARING hybrid rule: stacking IBR behind the POC LOWERS the effective SCR."""
    wind_only = {
        "grid": {
            "poc_voltage_kv": 33.0,
            "source_fault_level_mva": 800.0,
            "gridcode": {"pf_range": [-0.95, 0.95]},
            "resources": [_WIND_RES],
        }
    }
    env_wind = aggregate_poc_capability(wind_only)
    env_hybrid = aggregate_poc_capability(_HYBRID_GRID)
    # Adding solar + BESS raises total IBR MVA far more than the small PCS fault uplift, so
    # the composite SCR every inverter sees DROPS vs the wind-only POC.
    assert env_hybrid.total_ibr_mva > env_wind.total_ibr_mva
    assert env_hybrid.composite_scr < env_wind.composite_scr


def test_aggregate_reactive_vector_sum_minus_collector_loss() -> None:
    env = aggregate_poc_capability(_HYBRID_GRID)
    gross = 100.0 * _QP95 + 50.0 * _QP95 + 3.0 * 0.765
    assert env.gross_q_available_mvar == pytest.approx(gross)
    # 5% fractional collector/transformer reactive loss.
    assert env.collector_transformer_q_loss_mvar == pytest.approx(0.05 * gross)
    assert env.aggregate_q_available_mvar == pytest.approx(gross - 0.05 * gross)
    # Demand at the combined POC reference P (Σ rating · fraction=1.0) and the 0.95 pf.
    assert env.reference_p_mw == pytest.approx(160.64)
    assert env.aggregate_q_required_mvar == pytest.approx(160.64 * _QP95)
    assert env.aggregate_q_shortfall_mvar == pytest.approx(
        max(0.0, env.aggregate_q_required_mvar - env.aggregate_q_available_mvar)
    )
    assert env.inside_pq_box is (env.aggregate_q_shortfall_mvar <= 0.0)
    assert (env.pf_required_min, env.pf_required_max) == (-0.95, 0.95)


def test_aggregate_collector_loss_absolute_form() -> None:
    grid = {
        "grid": {
            **_HYBRID_GRID["grid"],
            "collector_transformer_q_loss_mvar": 4.0,
        }
    }
    # Remove the fraction key so the absolute form governs.
    grid["grid"].pop("collector_transformer_q_loss_fraction", None)
    env = aggregate_poc_capability(grid)
    assert env.collector_transformer_q_loss_mvar == pytest.approx(4.0)
    assert env.aggregate_q_available_mvar == pytest.approx(
        env.gross_q_available_mvar - 4.0
    )


def test_aggregate_lossless_collector_default() -> None:
    grid = {"grid": {k: v for k, v in _HYBRID_GRID["grid"].items()}}
    grid["grid"].pop("collector_transformer_q_loss_fraction", None)
    env = aggregate_poc_capability(grid)
    # No loss key → lossless collector (0 Mvar), gross == at-POC available.
    assert env.collector_transformer_q_loss_mvar == pytest.approx(0.0)
    assert env.aggregate_q_available_mvar == pytest.approx(env.gross_q_available_mvar)


def test_aggregate_inside_pq_box_when_ample_reactive() -> None:
    # A wind plant sized to over-deliver reactive clears the PQ box (zero shortfall).
    grid = {
        "grid": {
            "poc_voltage_kv": 33.0,
            "source_fault_level_mva": 800.0,
            "gridcode": {"pf_range": [-0.95, 0.95]},
            "resources": [
                {
                    "name": "wind",
                    "tech": "wind",
                    "converter_type": "type4_full_converter",
                    "rated_mva": 100.0,
                    "reactive_capability": {"max_q_mvar": 60.0},
                }
            ],
        }
    }
    env = aggregate_poc_capability(grid)
    # ±Q 60 Mvar available vs 100·tan(acos(0.95)) ≈ 32.9 demanded → inside the box.
    assert env.aggregate_q_shortfall_mvar == pytest.approx(0.0)
    assert env.inside_pq_box is True


def test_aggregate_partial_load_reference() -> None:
    env = aggregate_poc_capability(_HYBRID_GRID, p_fraction=0.5)
    # The POC reference P scales with the operating fraction.
    assert env.reference_p_mw == pytest.approx(160.64 * 0.5)
    assert env.aggregate_q_required_mvar == pytest.approx(160.64 * 0.5 * _QP95)


def test_aggregate_accepts_bare_grid_block() -> None:
    # Passing the grid block directly (with a resources list) also works.
    env = aggregate_poc_capability(_HYBRID_GRID["grid"])
    assert env.n_resources == 3


def test_aggregate_provenance_override() -> None:
    env = aggregate_poc_capability(_HYBRID_GRID, provenance="custom prov")
    assert env.provenance == "custom prov"


def test_aggregate_default_provenance_is_static_screen() -> None:
    env = aggregate_poc_capability(_HYBRID_GRID)
    assert "STATIC hybrid-POC aggregation" in env.provenance
    assert "NOT the utility-accepted bankable" in env.provenance


def test_aggregate_gfl_gfm_recommendation_tracks_band() -> None:
    env = aggregate_poc_capability(_HYBRID_GRID)
    # The recommendation string is the D1 mapping for the composite band.
    from analytics.contracts_v14 import grid_gfl_gfm_recommendation

    assert env.gfl_gfm_recommendation == grid_gfl_gfm_recommendation(env.scr_band)


def test_aggregate_notes_summarise_tech_counts() -> None:
    env = aggregate_poc_capability(_HYBRID_GRID)
    assert "bess×1" in env.notes and "solar×1" in env.notes and "wind×1" in env.notes


# ----------------------------------------------------------------------- strict-input raises


def test_aggregate_missing_grid_block_raises() -> None:
    with pytest.raises(ValueError, match="requires a 'grid' block"):
        aggregate_poc_capability({"scenario": "x"})


def test_aggregate_non_mapping_config_raises() -> None:
    with pytest.raises(ValueError, match="requires a 'grid' block"):
        aggregate_poc_capability("not-a-mapping")  # type: ignore[arg-type]


def test_aggregate_missing_resources_raises() -> None:
    grid = {"grid": {k: v for k, v in _HYBRID_GRID["grid"].items() if k != "resources"}}
    with pytest.raises(ValueError, match="requires grid.resources"):
        aggregate_poc_capability(grid)


def test_aggregate_empty_resources_raises() -> None:
    grid = {"grid": {**_HYBRID_GRID["grid"], "resources": []}}
    with pytest.raises(ValueError, match="at least one resource"):
        aggregate_poc_capability(grid)


def test_aggregate_resources_all_non_mapping_raises() -> None:
    grid = {"grid": {**_HYBRID_GRID["grid"], "resources": [1, "x", None]}}
    with pytest.raises(ValueError, match="at least one resource"):
        aggregate_poc_capability(grid)


def test_aggregate_missing_poc_kv_raises() -> None:
    grid = {
        "grid": {k: v for k, v in _HYBRID_GRID["grid"].items() if k != "poc_voltage_kv"}
    }
    with pytest.raises(ValueError, match="poc_voltage_kv"):
        aggregate_poc_capability(grid)


def test_aggregate_missing_source_fault_raises() -> None:
    grid = {
        "grid": {
            k: v
            for k, v in _HYBRID_GRID["grid"].items()
            if k != "source_fault_level_mva"
        }
    }
    with pytest.raises(ValueError, match="source_fault_level_mva"):
        aggregate_poc_capability(grid)


def test_aggregate_missing_grid_code_pf_range_raises() -> None:
    grid = {"grid": {k: v for k, v in _HYBRID_GRID["grid"].items() if k != "gridcode"}}
    with pytest.raises(ValueError, match="grid-code pf_range"):
        aggregate_poc_capability(grid)


def test_aggregate_grid_code_pf_range_out_of_range_raises() -> None:
    grid = {"grid": {**_HYBRID_GRID["grid"], "gridcode": {"pf_range": [0.0, 0.95]}}}
    with pytest.raises(ValueError, match=r"magnitude in \(0, 1\]"):
        aggregate_poc_capability(grid)


def test_aggregate_top_level_pf_range_fallback() -> None:
    # No gridcode block → the top-level pf_range is the grid-code demand source.
    grid = {"grid": {k: v for k, v in _HYBRID_GRID["grid"].items() if k != "gridcode"}}
    grid["grid"]["pf_range"] = [-0.95, 0.95]
    env = aggregate_poc_capability(grid)
    assert (env.pf_required_min, env.pf_required_max) == (-0.95, 0.95)


@pytest.mark.parametrize("bad", [-1.0, "0.05", True])
def test_aggregate_bad_absolute_loss_raises(bad: object) -> None:
    grid = {
        "grid": {
            **{
                k: v
                for k, v in _HYBRID_GRID["grid"].items()
                if k != "collector_transformer_q_loss_fraction"
            },
            "collector_transformer_q_loss_mvar": bad,
        }
    }
    with pytest.raises(ValueError, match="collector_transformer_q_loss_mvar"):
        aggregate_poc_capability(grid)


@pytest.mark.parametrize("bad", [-0.1, 1.0, 1.5, "0.05"])
def test_aggregate_bad_fraction_loss_raises(bad: object) -> None:
    grid = {
        "grid": {
            **_HYBRID_GRID["grid"],
            "collector_transformer_q_loss_fraction": bad,
        }
    }
    with pytest.raises(ValueError, match="collector_transformer_q_loss_fraction"):
        aggregate_poc_capability(grid)


def test_aggregate_zero_total_ibr_mva_would_raise() -> None:
    # A wind resource whose rating is zero is rejected upstream by the wind plug-in
    # (rated_mva > 0), so the aggregate never reaches a zero denominator with real config.
    grid = {
        "grid": {
            **{k: v for k, v in _HYBRID_GRID["grid"].items() if k != "resources"},
            "resources": [{**_WIND_RES, "rated_mva": 0.0}],
        }
    }
    with pytest.raises(ValueError, match="rated_mva"):
        aggregate_poc_capability(grid)


def test_bess_only_hybrid_gives_zero_denominator_guard(monkeypatch) -> None:
    """Directly exercise the total-IBR-MVA > 0 guard via a degenerate contribution.

    Real per-tech plug-ins reject a zero rating, so the guard is defensive. We patch the
    dispatch to yield a zero-rated contribution and assert the guard fires — proving the
    composite-SCR denominator can never be zero (NO SPURIOUS PASS / no ZeroDivision).
    """

    def _zero_contrib(resource, *, p_fraction=1.0, reference_year=None):
        return ResourceReactiveContribution(
            name="z",
            tech="wind",
            rated_mva=0.0,
            q_available_mvar=0.0,
            fault_mva_contribution=0.0,
        )

    monkeypatch.setattr(poc_aggregation, "resource_contribution", _zero_contrib)
    with pytest.raises(ValueError, match="total IBR MVA must be > 0"):
        aggregate_poc_capability(_HYBRID_GRID)


def test_contract_model_dump_roundtrips() -> None:
    env = aggregate_poc_capability(_HYBRID_GRID)
    dumped = env.model_dump()
    assert dumped["composite_scr"] == pytest.approx(env.composite_scr)
    assert dumped["n_resources"] == 3
    # The per-resource contributions are carried through (as a tuple — the ContractMixin
    # ``_dump`` recurses dict/list but leaves the tuple as-is, matching the other frozen
    # grid contracts). The audit trail is present with all three resources.
    assert len(dumped["contributions"]) == 3
    assert env.contributions[0].tech == "wind"


def test_reference_math_matches_hand_calc() -> None:
    env = aggregate_poc_capability(_HYBRID_GRID)
    gross = (100.0 + 50.0) * math.tan(math.acos(0.95)) + 3.0 * 0.765
    assert env.gross_q_available_mvar == pytest.approx(gross)
