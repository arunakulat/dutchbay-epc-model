"""Unit tests for the frozen ResourceAssessment contract (#996 D4).

Covers construction + serialisation, the ``from_assessment`` projection of a
``WindPipeline.run_complete_assessment`` result, and every fail-loud validation
path (AEP identity, P90<=P75<=P50 monotonicity, range/sign guards, bad P-level).
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Any, Callable

import pytest

from analytics.resource_contracts import (
    ResourceAssessment,
    ResourceAssessmentError,
)

# A self-consistent DutchBay-shaped assessment: 150 MW / 15 turbines, with each
# net AEP equal to capacity_mw * 8760 * CF / 1000 (to a few sig figs).
_KW = dict(
    capacity_mw=150.0,
    n_turbines=15,
    net_aep_p50_gwh=464.3,
    net_aep_p75_gwh=430.0,
    net_aep_p90_gwh=404.4,
    capacity_factor_p50=0.3533,
    capacity_factor_p75=0.3272,
    capacity_factor_p90=0.3078,
    selected_p_level="P75",
    report_grade="screening",
)


def _assessment(**overrides: object) -> ResourceAssessment:
    return ResourceAssessment(**{**_KW, **overrides})  # type: ignore[arg-type]


def _full_results() -> dict[str, Any]:
    # Shape matches WindPipeline.run_complete_assessment: net AEP in MWh and
    # capacity_factor_net_pXX as a PERCENT (wind_resource.energy_calculator).
    return {
        "energy_production": {
            "net_aep": {
                "net_aep_p50_mwh": 464300.0,
                "net_aep_p75_mwh": 430000.0,
                "net_aep_p90_mwh": 404400.0,
                "capacity_factor_net_p50": 35.33,
                "capacity_factor_net_p75": 32.72,
                "capacity_factor_net_p90": 30.78,
            }
        },
        "metadata": {
            "configuration": {
                "num_turbines": 15,
                "total_capacity_mw": 150.0,
                "turbine_model": "IEA_10MW_198m",
            }
        },
    }


# ---------------------------------------------------------------------------
# Construction + serialisation
# ---------------------------------------------------------------------------
def test_valid_construction_and_model_dump() -> None:
    a = _assessment()
    dumped = a.model_dump()
    assert dumped["net_aep_p50_gwh"] == 464.3
    assert dumped["selected_p_level"] == "P75"
    assert a.dict() == dumped  # ContractMixin-parity alias


@pytest.mark.parametrize("level", ["P50", "P75", "P90"])
def test_every_p_level_is_selectable(level: str) -> None:
    a = _assessment(selected_p_level=level)
    assert a.selected_p_level == level
    assert a.selected_net_aep_gwh == a.net_aep_gwh(level)
    assert a.selected_capacity_factor == a.capacity_factor(level)


def test_accessors_and_ratio() -> None:
    a = _assessment()
    assert a.net_aep_gwh("p90") == 404.4  # case-insensitive
    assert a.capacity_factor("P50") == 0.3533
    assert a.p90_p50_ratio == pytest.approx(404.4 / 464.3)


def test_is_frozen() -> None:
    a = _assessment()
    with pytest.raises(FrozenInstanceError):
        a.capacity_mw = 200.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# from_assessment projection
# ---------------------------------------------------------------------------
def test_from_assessment_projects_and_validates() -> None:
    a = ResourceAssessment.from_assessment(
        _full_results(), "P75", report_grade="screening"
    )
    assert a.capacity_mw == 150.0
    assert a.n_turbines == 15
    assert a.net_aep_p50_gwh == pytest.approx(464.3)  # MWh -> GWh
    assert a.net_aep_p90_gwh == pytest.approx(404.4)
    # capacity_factor_net_pXX is a PERCENT in the pipeline result -> decimal here.
    assert a.capacity_factor_p50 == pytest.approx(0.3533)  # from 35.33
    assert a.capacity_factor_p75 == pytest.approx(0.3272)  # from 32.72
    assert a.selected_p_level == "P75"
    assert a.source_id == "IEA_10MW_198m"  # turbine_model -> source_id
    assert a.report_grade == "screening"


def test_from_assessment_carries_run_manifest() -> None:
    manifest = {
        "config_sha256": "abc",
        "engine_version": "15.3.0",
        "git_sha": "deadbee",
    }
    a = ResourceAssessment.from_assessment(
        _full_results(), "P50", report_grade="screening", run_manifest=manifest
    )
    assert a.run_manifest == manifest
    assert a.model_dump()["run_manifest"]["git_sha"] == "deadbee"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda fr: fr.pop("energy_production"),
        lambda fr: fr.pop("metadata"),
        lambda fr: fr["energy_production"].pop("net_aep"),
    ],
)
def test_from_assessment_malformed_raises(
    mutate: Callable[[dict[str, Any]], object],
) -> None:
    fr = _full_results()
    mutate(fr)
    with pytest.raises(ResourceAssessmentError):
        ResourceAssessment.from_assessment(fr, "P75", report_grade="screening")


# ---------------------------------------------------------------------------
# Fail-loud validation
# ---------------------------------------------------------------------------
def test_bad_aep_identity_raises() -> None:
    # P50 AEP wildly inconsistent with capacity * 8760 * CF (double it).
    with pytest.raises(ResourceAssessmentError, match="AEP identity"):
        _assessment(net_aep_p50_gwh=928.6)


def test_non_monotonic_aep_raises() -> None:
    # P75 AEP above P50 (inverted) — also keep CF consistent so we isolate AEP.
    with pytest.raises(ResourceAssessmentError, match="monotone"):
        _assessment(
            net_aep_p75_gwh=500.0,
            capacity_factor_p75=0.3806,  # keeps identity for the inverted P75
        )


def test_non_monotonic_cf_raises() -> None:
    # CF is proportional to AEP, so an inverted CF can only be isolated from the
    # AEP-monotonicity + identity checks by relaxing identity_rtol: keep AEP
    # monotonic, push P90 CF above P75 CF, and let the CF-order guard fire.
    with pytest.raises(
        ResourceAssessmentError, match="capacity factor must be monotone"
    ):
        _assessment(capacity_factor_p90=0.33, identity_rtol=1.0)


def test_bad_selected_p_level_raises() -> None:
    with pytest.raises(ResourceAssessmentError, match="p_level"):
        _assessment(selected_p_level="P80")


@pytest.mark.parametrize("bad", [0.0, -10.0])
def test_non_positive_capacity_raises(bad: float) -> None:
    with pytest.raises(ResourceAssessmentError, match="capacity_mw"):
        _assessment(capacity_mw=bad)


def test_non_positive_turbines_raises() -> None:
    with pytest.raises(ResourceAssessmentError, match="n_turbines"):
        _assessment(n_turbines=0)


def test_capacity_factor_out_of_range_raises() -> None:
    with pytest.raises(ResourceAssessmentError, match="capacity_factor_p50"):
        # >1 CF, with matching AEP so the identity passes and the range check fires.
        _assessment(capacity_factor_p50=1.2, net_aep_p50_gwh=1576.8)


def test_negative_aep_raises() -> None:
    with pytest.raises(ResourceAssessmentError):
        _assessment(net_aep_p90_gwh=-1.0, capacity_factor_p90=0.0)


def test_zero_aep_with_positive_cf_raises() -> None:
    # A level that reports zero energy but a non-zero capacity factor is
    # contradictory and must fail the identity, not be skipped.
    with pytest.raises(ResourceAssessmentError, match="AEP identity"):
        _assessment(net_aep_p90_gwh=0.0, capacity_factor_p90=0.30)


# ---------------------------------------------------------------------------
# Re-export surface
# ---------------------------------------------------------------------------
def test_reexported_from_contracts_v14() -> None:
    from analytics.contracts_v14 import ResourceAssessment as ReExported

    assert ReExported is ResourceAssessment
