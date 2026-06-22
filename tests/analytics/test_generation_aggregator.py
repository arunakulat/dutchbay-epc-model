"""Tests for analytics.portfolio.generation_aggregator (multi-tech producer)."""

from __future__ import annotations

import pytest

from analytics.contracts_v14 import GenerationProfile, MultiTechGenerationResult
from analytics.portfolio.generation_aggregator import (
    aggregate_generation,
    build_multi_tech_from_run,
    build_wind_generation_profile,
    resolve_wind_aep_kwh,
    technology_breakdown,
)

_CONFIG = {
    "resource": {"wind": {"aep_gwh": 473.8, "availability_pct": 97.0}},
    "aep_summary": {"net_aep_p50_gwh": 473.8},
}
_KPIS = {"mean_operational_cfads_usd": 14_646_357.7, "final_cfads_usd": 8_476_286.0}


# --------------------------------------------------------------------------- #
# AEP resolution
# --------------------------------------------------------------------------- #
def test_resolve_aep_from_resource_block() -> None:
    assert resolve_wind_aep_kwh(_CONFIG) == pytest.approx(473.8e6)


def test_resolve_aep_falls_back_to_aep_summary() -> None:
    cfg = {"aep_summary": {"net_aep_p50_gwh": 400.0}}
    assert resolve_wind_aep_kwh(cfg) == pytest.approx(400.0e6)


def test_resolve_aep_none_when_absent() -> None:
    assert resolve_wind_aep_kwh({"resource": {"wind": {}}}) is None
    assert resolve_wind_aep_kwh({"resource": "not-a-mapping"}) is None


# --------------------------------------------------------------------------- #
# Wind profile
# --------------------------------------------------------------------------- #
def test_build_wind_profile_full() -> None:
    p = build_wind_generation_profile(_KPIS, _CONFIG)
    assert p is not None
    assert p.technology == "wind"
    assert p.annual_aep_kwh == pytest.approx(473.8e6)
    assert p.annual_cfads_usd == pytest.approx(14_646_357.7)
    assert p.availability_pct == pytest.approx(97.0)


def test_build_wind_profile_cfads_fallback() -> None:
    p = build_wind_generation_profile({"final_cfads_usd": 5.0}, _CONFIG)
    assert p is not None and p.annual_cfads_usd == pytest.approx(5.0)


def test_build_wind_profile_none_without_aep() -> None:
    assert build_wind_generation_profile(_KPIS, {"resource": {"wind": {}}}) is None


# --------------------------------------------------------------------------- #
# Aggregation + breakdown (genuinely multi-tech)
# --------------------------------------------------------------------------- #
def _profile(tech: str, aep: float, cfads: float) -> GenerationProfile:
    return GenerationProfile(technology=tech, annual_aep_kwh=aep, annual_cfads_usd=cfads)


def test_aggregate_sums_and_indexes() -> None:
    res = aggregate_generation([_profile("wind", 400e6, 40e6), _profile("solar", 100e6, 8e6)])
    assert isinstance(res, MultiTechGenerationResult)
    assert res.total_aep_kwh == pytest.approx(500e6)
    assert res.total_cfads_usd == pytest.approx(48e6)
    assert set(res.technologies) == {"wind", "solar"}


def test_aggregate_empty_raises() -> None:
    with pytest.raises(ValueError):
        aggregate_generation([])


def test_breakdown_shares_split_across_techs() -> None:
    res = aggregate_generation([_profile("wind", 400e6, 40e6), _profile("solar", 100e6, 8e6)])
    rows = {r.technology: r for r in technology_breakdown(res)}
    assert rows["wind"].share_of_aep_pct == pytest.approx(80.0)
    assert rows["solar"].share_of_aep_pct == pytest.approx(20.0)
    assert rows["wind"].share_of_cfads_pct == pytest.approx(40e6 / 48e6 * 100)


def test_breakdown_capex_shares_when_provided() -> None:
    res = aggregate_generation([_profile("wind", 400e6, 40e6), _profile("solar", 100e6, 8e6)])
    rows = {r.technology: r for r in technology_breakdown(res, capex_by_tech={"wind": 150e6, "solar": 50e6})}
    assert rows["wind"].share_of_capex_pct == pytest.approx(75.0)
    assert rows["solar"].share_of_capex_pct == pytest.approx(25.0)


def test_breakdown_capex_none_without_input() -> None:
    res = aggregate_generation([_profile("wind", 400e6, 40e6)])
    assert technology_breakdown(res)[0].share_of_capex_pct is None


# --------------------------------------------------------------------------- #
# End-to-end convenience
# --------------------------------------------------------------------------- #
def test_build_multi_tech_from_run_wind_only() -> None:
    result, breakdown = build_multi_tech_from_run(_KPIS, _CONFIG)
    assert result is not None and breakdown is not None
    assert result.technologies["wind"].annual_aep_kwh == pytest.approx(473.8e6)
    assert breakdown[0].share_of_aep_pct == pytest.approx(100.0)
    # Round-trips through the contract's JSON helper (what casper_payload calls).
    assert result.to_dict()["technologies"]["wind"]["annual_aep_kwh"] == pytest.approx(473.8e6)


def test_build_multi_tech_from_run_none_without_aep() -> None:
    result, breakdown = build_multi_tech_from_run(_KPIS, {})
    assert result is None and breakdown is None


# --------------------------------------------------------------------------- #
# M2: solar resolution + the generation.technologies block + hybrid split
# --------------------------------------------------------------------------- #
from analytics.portfolio.generation_aggregator import resolve_tech_aep_kwh  # noqa: E402

_HYBRID_CONFIG = {
    "generation": {
        "technologies": {
            "wind": {"aep_gwh": 473.8, "availability_pct": 97.0, "capex_usd": 195_000_000},
            "solar": {"aep_gwh": 87.6, "availability_pct": 99.0, "capex_usd": 35_000_000},
        }
    }
}


def test_resolve_tech_aep_prefers_generation_block() -> None:
    cfg = {
        "generation": {"technologies": {"wind": {"aep_gwh": 500.0}}},
        "resource": {"wind": {"aep_gwh": 473.8}},  # legacy; should be overridden
    }
    assert resolve_tech_aep_kwh(cfg, "wind") == pytest.approx(500.0e6)


def test_resolve_solar_aep_from_generation_and_resource() -> None:
    assert resolve_tech_aep_kwh(_HYBRID_CONFIG, "solar") == pytest.approx(87.6e6)
    assert resolve_tech_aep_kwh({"resource": {"solar": {"aep_gwh": 60.0}}}, "solar") == pytest.approx(60.0e6)
    assert resolve_tech_aep_kwh({}, "solar") is None


def test_hybrid_run_splits_cfads_by_aep_share() -> None:
    kpis = {"mean_operational_cfads_usd": 50_000_000.0}
    result, breakdown = build_multi_tech_from_run(kpis, _HYBRID_CONFIG)
    assert result is not None and breakdown is not None
    # Both technologies present.
    assert set(result.technologies) == {"wind", "solar"}
    total_aep = 473.8 + 87.6
    # CFADS split in proportion to AEP; the allocation conserves the run total.
    assert result.total_cfads_usd == pytest.approx(50_000_000.0)
    assert result.technologies["wind"].annual_cfads_usd == pytest.approx(
        50_000_000.0 * 473.8 / total_aep
    )
    assert result.technologies["solar"].annual_cfads_usd == pytest.approx(
        50_000_000.0 * 87.6 / total_aep
    )
    rows = {r.technology: r for r in breakdown}
    assert rows["wind"].share_of_aep_pct == pytest.approx(100.0 * 473.8 / total_aep)
    assert rows["solar"].share_of_aep_pct == pytest.approx(100.0 * 87.6 / total_aep)
    # CAPEX shares come from the generation block.
    assert rows["wind"].share_of_capex_pct == pytest.approx(100.0 * 195 / 230)
    assert rows["solar"].share_of_capex_pct == pytest.approx(100.0 * 35 / 230)
    # Per-tech availability flows through.
    assert result.technologies["solar"].availability_pct == pytest.approx(99.0)


def test_tech_without_availability_is_none() -> None:
    cfg = {"generation": {"technologies": {"wind": {"aep_gwh": 400.0}}}}
    result, _ = build_multi_tech_from_run({"final_cfads_usd": 1.0}, cfg)
    assert result is not None
    assert result.technologies["wind"].availability_pct is None
