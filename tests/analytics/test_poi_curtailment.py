"""Tests for analytics.portfolio.poi_curtailment (ARCH-5 shared-POI curtailment, #476)."""

from __future__ import annotations

import pytest

from analytics.contracts_v14 import SharedPoiCurtailmentResult
from analytics.portfolio.poi_curtailment import (
    estimate_poi_curtailment,
    resolve_shared_poi_curtailment,
)


def test_no_curtailment_when_combined_below_limit() -> None:
    profiles = {"wind": [40.0, 30.0, 20.0], "solar": [10.0, 20.0, 0.0]}
    res = estimate_poi_curtailment(profiles, poi_limit_mw=100.0)
    assert isinstance(res, SharedPoiCurtailmentResult)
    assert res.curtailed_energy_mwh == 0.0
    assert res.curtailment_pct == 0.0
    assert res.hours_curtailed == 0
    assert res.gross_energy_mwh == pytest.approx(120.0)


def test_curtailment_when_combined_exceeds_limit() -> None:
    # Hour 0: combined 120 -> 20 curtailed; hour 1: 50 -> 0; hour 2: 110 -> 10 curtailed.
    profiles = {"wind": [80.0, 30.0, 70.0], "solar": [40.0, 20.0, 40.0]}
    res = estimate_poi_curtailment(profiles, poi_limit_mw=100.0)
    assert res.curtailed_energy_mwh == pytest.approx(30.0)  # 20 + 0 + 10
    assert res.gross_energy_mwh == pytest.approx(280.0)
    assert res.curtailment_pct == pytest.approx(30.0 / 280.0 * 100.0)
    assert res.hours_curtailed == 2
    assert res.hours_total == 3


def test_estimate_rejects_bad_inputs() -> None:
    with pytest.raises(ValueError, match="poi_limit_mw must be positive"):
        estimate_poi_curtailment({"wind": [1.0]}, poi_limit_mw=0.0)
    with pytest.raises(ValueError, match="at least one profile"):
        estimate_poi_curtailment({}, poi_limit_mw=100.0)
    with pytest.raises(ValueError, match="share one length"):
        estimate_poi_curtailment(
            {"wind": [1.0, 2.0], "solar": [1.0]}, poi_limit_mw=100.0
        )


def test_resolve_none_without_poi_limit() -> None:
    cfg = {
        "generation": {
            "technologies": {
                "wind": {"hourly_profile_mw": [80.0, 70.0]},
                "solar": {"hourly_profile_mw": [40.0, 40.0]},
            }
        }
    }
    assert resolve_shared_poi_curtailment(cfg) is None


def test_resolve_none_with_fewer_than_two_profiles() -> None:
    cfg = {
        "generation": {
            "shared_poi": {"limit_mw": 100.0},
            "technologies": {"wind": {"hourly_profile_mw": [120.0]}},
        }
    }
    assert resolve_shared_poi_curtailment(cfg) is None


def test_resolve_computes_curtailment_when_configured() -> None:
    cfg = {
        "generation": {
            "shared_poi": {"limit_mw": 100.0},
            "technologies": {
                "wind": {"hourly_profile_mw": [80.0, 30.0, 70.0]},
                "solar": {"hourly_profile_mw": [40.0, 20.0, 40.0]},
            },
        }
    }
    res = resolve_shared_poi_curtailment(cfg)
    assert res is not None
    assert res.poi_limit_mw == 100.0
    assert res.curtailed_energy_mwh == pytest.approx(30.0)


def test_serializable() -> None:
    res = estimate_poi_curtailment(
        {"wind": [120.0], "solar": [0.0]}, poi_limit_mw=100.0
    )
    payload = res.model_dump()
    assert payload["curtailed_energy_mwh"] == pytest.approx(20.0)
    assert payload["hours_curtailed"] == 1


def test_negative_injection_is_rejected() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        estimate_poi_curtailment(
            {"wind": [80.0, -5.0], "solar": [40.0, 40.0]}, poi_limit_mw=100.0
        )


def test_step_hours_scales_energy() -> None:
    # 15-minute steps (0.25h): combined [120] over 1 step -> 20 MW excess -> 5 MWh curtailed.
    res = estimate_poi_curtailment(
        {"wind": [80.0], "solar": [40.0]}, poi_limit_mw=100.0, step_hours=0.25
    )
    assert res.gross_energy_mwh == pytest.approx(30.0)  # 120 MW * 0.25 h
    assert res.curtailed_energy_mwh == pytest.approx(5.0)  # 20 MW * 0.25 h
    assert res.curtailment_pct == pytest.approx(20.0 / 120.0 * 100.0)  # ratio unchanged


def test_step_hours_must_be_positive() -> None:
    with pytest.raises(ValueError, match="step_hours must be positive"):
        estimate_poi_curtailment({"wind": [1.0]}, poi_limit_mw=10.0, step_hours=0.0)
