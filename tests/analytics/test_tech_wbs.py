"""Tests for analytics.portfolio.tech_wbs (ARCH-3 per-tech cost/return WBS, #475)."""

from __future__ import annotations

import pytest

from analytics.contracts_v14 import MultiTechWBS, TechnologyCostReturn
from analytics.portfolio.tech_wbs import build_multi_tech_wbs

# A wind+solar+BESS hybrid: financed totals exceed the per-tech allocations (the gap is
# the shared / balance-of-plant residual — grid connection, dev cost, the 220 kV line).
# WACC is build_up (as every committed multi-tech scenario is) — its blended value is
# computed in-pipeline from sized debt, so it is NOT config-derivable and must be passed in.
_HYBRID = {
    "capex": {"usd_total": 200_000_000.0},
    "opex": {"usd_per_year": 5_000_000.0},
    "wacc": {
        "mode": "build_up",
        "drives_discount_rate": True,
        "cost_of_equity": 0.12,
        "prudential_spread_bps": 100,
    },
    "generation": {
        "technologies": {
            "wind": {
                "type": "wind",
                "capacity_factor": 0.34,
                "capex_usd": 150_000_000.0,
                "opex_usd_per_year": 3_500_000.0,
            },
            "solar": {
                "type": "solar",
                "capacity_factor": 0.18,
                "capex_usd": 30_000_000.0,
                "opex_usd_per_year": 800_000.0,
                "wacc": {"cost_of_equity": 0.11},
            },
            "bess": {
                "type": "bess",
                "power_mw": 11,
                "energy_mwh": 22,
                "capex_usd": 12_000_000.0,
            },
        }
    },
}


# --------------------------------------------------------------------------- #
# Opportunistic attach
# --------------------------------------------------------------------------- #
def test_single_tech_without_technologies_block_returns_none() -> None:
    """Legacy single-tech scenarios (no generation.technologies) attach no WBS."""
    assert build_multi_tech_wbs({"capex": {"usd_total": 1.0}}) is None
    assert (
        build_multi_tech_wbs({"generation": {"technologies": "not-a-mapping"}}) is None
    )


def test_returns_multi_tech_wbs_with_a_row_per_technology() -> None:
    wbs = build_multi_tech_wbs(_HYBRID)
    assert isinstance(wbs, MultiTechWBS)
    assert set(wbs.technologies) == {"wind", "solar", "bess"}
    assert all(isinstance(r, TechnologyCostReturn) for r in wbs.technologies.values())


# --------------------------------------------------------------------------- #
# Per-tech resolution + shares (of the allocated total, so they sum to 100%)
# --------------------------------------------------------------------------- #
def test_per_tech_capex_opex_resolved() -> None:
    wbs = build_multi_tech_wbs(_HYBRID)
    assert wbs is not None
    assert wbs.technologies["wind"].capex_usd == pytest.approx(150_000_000.0)
    assert wbs.technologies["solar"].opex_usd_per_year == pytest.approx(800_000.0)
    # BESS carries capex but no opex in this scenario.
    assert wbs.technologies["bess"].capex_usd == pytest.approx(12_000_000.0)
    assert wbs.technologies["bess"].opex_usd_per_year is None


def test_capex_shares_are_of_allocated_total_and_sum_to_100() -> None:
    wbs = build_multi_tech_wbs(_HYBRID)
    assert wbs is not None
    shares = [r.share_of_capex_pct for r in wbs.technologies.values()]
    assert sum(shares) == pytest.approx(100.0)
    assert wbs.technologies["wind"].share_of_capex_pct == pytest.approx(78.125)


def test_classification_notes() -> None:
    wbs = build_multi_tech_wbs(_HYBRID)
    assert wbs is not None
    assert wbs.technologies["wind"].notes == "generation"
    assert wbs.technologies["bess"].notes == "storage"


# --------------------------------------------------------------------------- #
# Reconciliation against the financed totals
# --------------------------------------------------------------------------- #
def test_capex_residual_is_the_shared_unallocated_bucket() -> None:
    wbs = build_multi_tech_wbs(_HYBRID)
    assert wbs is not None
    assert wbs.financed_capex_usd == pytest.approx(200_000_000.0)
    assert wbs.allocated_capex_usd == pytest.approx(192_000_000.0)
    assert wbs.capex_residual_usd == pytest.approx(8_000_000.0)
    assert wbs.capex_reconciled is True


def test_opex_residual_and_reconciliation() -> None:
    wbs = build_multi_tech_wbs(_HYBRID)
    assert wbs is not None
    assert wbs.allocated_opex_usd_per_year == pytest.approx(4_300_000.0)
    assert wbs.opex_residual_usd_per_year == pytest.approx(700_000.0)
    assert wbs.opex_reconciled is True


def test_over_attribution_raises_for_capex() -> None:
    bad = {**_HYBRID, "capex": {"usd_total": 100_000_000.0}}
    with pytest.raises(ValueError, match="CAPEX over-attribution"):
        build_multi_tech_wbs(bad)


def test_over_attribution_raises_for_opex() -> None:
    bad = {**_HYBRID, "opex": {"usd_per_year": 1_000_000.0}}
    with pytest.raises(ValueError, match="OPEX over-attribution"):
        build_multi_tech_wbs(bad)


def test_within_tolerance_overshoot_reconciles() -> None:
    """An allocation within reconcile_tolerance_pct over the financed total is OK."""
    cfg = {
        "capex": {"usd_total": 100_000_000.0},
        "generation": {
            "technologies": {
                "wind": {
                    "type": "wind",
                    "capacity_factor": 0.34,
                    "capex_usd": 100_500_000.0,
                }
            }
        },
    }
    wbs = build_multi_tech_wbs(
        cfg, reconcile_tolerance_pct=1.0
    )  # 1% = 1,000,000 headroom
    assert wbs is not None
    assert wbs.capex_reconciled is True
    assert wbs.capex_residual_usd == pytest.approx(-500_000.0)


def test_no_financed_total_cannot_reconcile_but_does_not_crash() -> None:
    cfg = {
        "generation": {
            "technologies": {
                "wind": {
                    "type": "wind",
                    "capacity_factor": 0.34,
                    "capex_usd": 10_000_000.0,
                }
            }
        }
    }
    wbs = build_multi_tech_wbs(cfg)
    assert wbs is not None
    assert wbs.financed_capex_usd is None
    assert wbs.capex_residual_usd is None
    assert wbs.capex_reconciled is False
    assert wbs.allocated_capex_usd == pytest.approx(10_000_000.0)


# --------------------------------------------------------------------------- #
# Per-tech WACC is disclosure-only
# --------------------------------------------------------------------------- #
def test_per_tech_cost_of_equity_disclosure() -> None:
    """Per-tech cost_of_equity reads the tech block directly (independent of WACC mode)."""
    wbs = build_multi_tech_wbs(_HYBRID)
    assert wbs is not None
    # solar declares its own cost of equity -> tech-specific
    assert wbs.technologies["solar"].cost_of_equity == pytest.approx(0.11)
    assert wbs.technologies["solar"].wacc_basis == "tech-specific"
    # wind inherits the project (blended) WACC
    assert wbs.technologies["wind"].cost_of_equity is None
    assert wbs.technologies["wind"].wacc_basis == "blended"


def test_build_up_project_wacc_is_none_without_a_caller_supplied_value() -> None:
    """build_up WACC is computed in-pipeline; config alone cannot resolve it (the real
    failure mode the review caught — every committed multi-tech scenario is build_up).
    """
    wbs = build_multi_tech_wbs(_HYBRID)
    assert wbs is not None
    assert wbs.project_wacc_nominal is None


def test_caller_supplied_project_wacc_is_surfaced() -> None:
    """The resolved blended WACC (from the run) is surfaced when the caller passes it."""
    wbs = build_multi_tech_wbs(_HYBRID, project_wacc_nominal=0.0983)
    assert wbs is not None
    assert wbs.project_wacc_nominal == pytest.approx(0.0983)


def test_fixed_mode_project_wacc_falls_back_to_config() -> None:
    """For fixed/CAPM mode, the config fallback resolves the blended WACC."""
    cfg = {**_HYBRID, "wacc": {"mode": "fixed", "discount_rate": 9.83}}
    wbs = build_multi_tech_wbs(cfg)
    assert wbs is not None
    assert wbs.project_wacc_nominal == pytest.approx(0.0983)


def test_negative_financed_opex_does_not_spuriously_raise() -> None:
    """A non-positive financed total must not invert the over-attribution check."""
    bad = {**_HYBRID, "opex": {"usd_per_year": -1_000_000.0}}
    wbs = build_multi_tech_wbs(bad)  # must not raise
    assert wbs is not None
    assert wbs.opex_reconciled is False
    assert wbs.opex_residual_usd_per_year is None


def test_negative_per_tech_capex_is_excluded_not_silently_nulling_shares() -> None:
    """A negative per-tech capex is dropped (with a warning), so legitimate techs keep
    their shares instead of all-None degradation."""
    cfg = {
        "capex": {"usd_total": 100_000_000.0},
        "generation": {
            "technologies": {
                "wind": {
                    "type": "wind",
                    "capacity_factor": 0.34,
                    "capex_usd": 80_000_000.0,
                },
                "solar": {
                    "type": "solar",
                    "capacity_factor": 0.18,
                    "capex_usd": -5_000_000.0,  # data-entry error
                },
            }
        },
    }
    wbs = build_multi_tech_wbs(cfg)
    assert wbs is not None
    assert wbs.technologies["solar"].capex_usd is None
    assert wbs.allocated_capex_usd == pytest.approx(80_000_000.0)
    # wind keeps a real (100%) share rather than being nulled by a negative sum
    assert wbs.technologies["wind"].share_of_capex_pct == pytest.approx(100.0)


def test_reconciles_against_engine_derive_from_breakdown_total() -> None:
    """The financed total reuses the debt engine's resolver, so derive_from_breakdown
    (bottom-up) reconciles correctly — not just a flat capex.usd_total."""
    cfg = {
        "capex": {
            "derive_from_breakdown": True,
            "breakdown": {"turbines_usd": 120_000_000.0, "bop_usd": 60_000_000.0},
        },
        "generation": {
            "technologies": {
                "wind": {
                    "type": "wind",
                    "capacity_factor": 0.34,
                    "capex_usd": 150_000_000.0,
                }
            }
        },
    }
    wbs = build_multi_tech_wbs(cfg)
    assert wbs is not None
    assert wbs.financed_capex_usd == pytest.approx(180_000_000.0)  # 120M + 60M
    assert wbs.capex_residual_usd == pytest.approx(30_000_000.0)
    assert wbs.capex_reconciled is True


def test_serializable() -> None:
    wbs = build_multi_tech_wbs(_HYBRID)
    assert wbs is not None
    payload = wbs.to_dict()
    assert payload == wbs.model_dump()
    assert payload["technologies"]["wind"]["share_of_capex_pct"] == pytest.approx(
        78.125
    )
    assert payload["capex_residual_usd"] == pytest.approx(8_000_000.0)


def test_wbs_reaches_the_casper_json_payload() -> None:
    """The WBS is threaded into build_casper_payload -> _casper_to_dict, so it is not
    stranded on the typed CasperResult (the contract-drift anti-pattern)."""
    from analytics.casper.casper_payload import build_casper_payload

    wbs = build_multi_tech_wbs(_HYBRID, project_wacc_nominal=0.0983)
    payload = build_casper_payload(scenario="<wbs-test-stub>", multi_tech_wbs=wbs)
    assert "multi_tech_wbs" in payload
    assert payload["multi_tech_wbs"] is not None
    assert payload["multi_tech_wbs"]["capex_residual_usd"] == pytest.approx(8_000_000.0)
    # Absent WBS serializes to None (back-compat for single-tech runs).
    assert build_casper_payload(scenario="x")["multi_tech_wbs"] is None
