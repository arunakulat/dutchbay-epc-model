"""Independent dimensional and hostile-input controls for YAML BESS ratings."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from analytics.contracts_v14 import BessSizing


@pytest.mark.parametrize(("power", "duration"), [(10.0, 4.0), (17.5, 6.0), (2.0, 0.5)])
def test_energy_derives_from_authored_power_and_duration(
    power: float, duration: float
) -> None:
    config = {"power_mw": power, "duration_h": duration}
    sizing = BessSizing.from_mapping(config)
    assert sizing.energy_mwh == power * duration
    assert config == {"power_mw": power, "duration_h": duration}
    assert (
        replace(sizing, power_mw=power * 2, energy_mwh=sizing.energy_mwh * 2).energy_mwh
        == 2 * power * duration
    )


@pytest.mark.parametrize("field", ["power_mw", "duration_h", "energy_mwh"])
@pytest.mark.parametrize(
    "bad", [None, True, "4", 0, -1, float("inf"), float("nan"), 10**400]
)
def test_invalid_authored_ratings_fail_without_coercion(
    field: str, bad: object
) -> None:
    config = {"power_mw": 10.0, "duration_h": 4.0, "energy_mwh": 40.0, field: bad}
    with pytest.raises(ValueError, match=field):
        BessSizing.from_mapping(config)


def test_authored_energy_is_retained_and_the_existing_tolerance_is_not_widened() -> (
    None
):
    assert (
        BessSizing.from_mapping(
            {"power_mw": 10, "duration_h": 4, "energy_mwh": 40.2}
        ).energy_mwh
        == 40.2
    )
    with pytest.raises(ValueError, match="does not reconcile"):
        BessSizing.from_mapping({"power_mw": 10, "duration_h": 4, "energy_mwh": 40.5})


def test_sizing_is_immutable_and_dump_revalidates_hostile_changes() -> None:
    sizing = BessSizing(10.0, 4.0, 40.0)
    with pytest.raises(FrozenInstanceError):
        sizing.power_mw = 20.0  # type: ignore[misc]
    object.__setattr__(sizing, "duration_h", None)
    with pytest.raises(ValueError, match="duration_h"):
        sizing.model_dump()


def test_overflowing_derived_energy_is_not_a_valid_rating() -> None:
    with pytest.raises(ValueError, match="energy_mwh"):
        BessSizing.from_mapping({"power_mw": 1e300, "duration_h": 1e300})
