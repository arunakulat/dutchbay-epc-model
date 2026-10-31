"""Independent energy arithmetic and hostile constraint probes for #1402."""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from fractions import Fraction

import pytest

from analytics.contracts_v14 import ChronologicalDispatchInput
from analytics.grid.capabilities.bess_soc import bess_soc_state
from analytics.storage_dispatch import (
    evaluate_chronological_dispatch,
    simulate_dispatch,
)
from tests.contracts.test_storage_dispatch_contracts import raw_envelope


def test_fraction_oracle_traces_each_source_and_all_conversion_losses() -> None:
    result = simulate_dispatch(ChronologicalDispatchInput.from_mapping(raw_envelope()))
    first, second = result.steps
    # Independently hand-derived: 5 AC MWh charged at4/5 stores4; at1/2
    # discharge efficiency those4 stored MWh deliver2, losing1+2 MWh.
    stored = Fraction(5) * Fraction(4, 5)
    delivered = stored * Fraction(1, 2)
    assert first.wind_to_bess_mwh == 3
    assert first.solar_to_bess_mwh == 2
    assert first.wind_to_poc_mwh == 3
    assert first.solar_to_poc_mwh == 2
    assert first.soc_end_mwh == float(stored)
    assert first.charge_loss_mwh == pytest.approx(float(5 - stored))
    assert second.bess_to_poc_mwh == float(delivered)
    assert second.discharge_loss_mwh == float(stored - delivered)
    assert second.soc_end_mwh == 0
    assert (
        10
        == first.wind_to_poc_mwh
        + first.solar_to_poc_mwh
        + second.bess_to_poc_mwh
        + first.charge_loss_mwh
        + second.discharge_loss_mwh
    )
    assert result.feasible
    payload = result.model_dump()
    assert payload["bankable"] is False
    assert (
        payload["energy_balance_semantics"]
        == "accounting_identity_not_independent_validation"
    )
    assert not {"revenue", "irr", "dscr", "merchant_value"} & payload.keys()
    assert json.loads(json.dumps(payload))["input_sha256"] == result.inputs.sha256


def test_static_soh_and_soc_limits_match_the_preexisting_shared_model() -> None:
    raw = raw_envelope()
    raw.update(
        wind_generation_mwh=[100, 0],
        solar_generation_mwh=[0, 0],
        dispatch_instruction_mw=[-20, 50],
        minimum_soc_fraction=0.25,
        maximum_soc_fraction=0.5,
        initial_soc_fraction=0.25,
        final_soc_fraction=0.25,
    )
    result = simulate_dispatch(ChronologicalDispatchInput.from_mapping(raw))
    independent = bess_soc_state(
        {
            "type": "bess",
            "energy_mwh": 40,
            "soh_fraction": 0.5,
            "min_soc": 0.25,
            "max_soc": 0.5,
        },
        soc_fraction=0.25,
    )
    charge, discharge = result.steps
    assert charge.wind_to_bess_mwh == pytest.approx(independent.chargeable_mwh / 0.8)
    assert charge.soc_end_mwh == 10
    assert discharge.bess_to_poc_mwh == 2.5
    assert discharge.soc_end_mwh == 5
    assert charge.unmet_charge_mwh == 13.75
    assert discharge.unmet_discharge_mwh == 47.5
    assert not result.feasible


def test_power_rating_is_responsive_and_does_not_create_energy() -> None:
    raw = raw_envelope()
    raw["sizing"] = {"power_mw": 2, "duration_h": 4}
    result = simulate_dispatch(ChronologicalDispatchInput.from_mapping(raw))
    assert result.steps[0].wind_to_bess_mwh + result.steps[0].solar_to_bess_mwh == 2
    assert result.steps[1].bess_to_poc_mwh == pytest.approx(0.8)
    assert not result.feasible


def test_shared_poc_cannot_count_generation_and_battery_twice() -> None:
    raw = raw_envelope()
    raw.update(
        wind_generation_mwh=[8, 8],
        solar_generation_mwh=[2, 2],
        dispatch_instruction_mw=[0, 10],
        charge_source=["none", "none"],
        initial_soc_fraction=0.5,
        final_soc_fraction=0.5,
        poc_limit_mw=[5, 5],
    )
    result = simulate_dispatch(ChronologicalDispatchInput.from_mapping(raw))
    for row in result.steps:
        assert row.wind_to_poc_mwh + row.solar_to_poc_mwh == 5
        assert row.bess_to_poc_mwh == 0
        assert row.wind_curtailed_mwh + row.solar_curtailed_mwh == 5
    assert result.steps[1].unmet_discharge_mwh == 10
    assert not result.feasible


def test_grid_charge_import_and_generation_export_share_gross_cap() -> None:
    raw = raw_envelope()
    raw.update(
        dispatch_instruction_mw=[-2, 0],
        charge_source=["grid", "none"],
        wind_generation_mwh=[4, 0],
        solar_generation_mwh=[0, 0],
        poc_limit_mw=[3, 3],
        charge_efficiency=1,
        final_soc_fraction=0.1,
    )
    result = simulate_dispatch(ChronologicalDispatchInput.from_mapping(raw))
    row = result.steps[0]
    assert row.grid_to_bess_mwh == 2
    assert row.wind_to_bess_mwh == 0
    assert row.wind_to_poc_mwh == 1
    assert row.wind_curtailed_mwh == 3
    assert row.grid_to_bess_mwh + row.wind_to_poc_mwh == 3
    assert result.feasible


def test_poc_outage_still_allows_internal_renewable_charge_but_no_export() -> None:
    raw = raw_envelope()
    raw["poc_outage"] = [True, True]
    result = simulate_dispatch(ChronologicalDispatchInput.from_mapping(raw))
    assert result.steps[0].soc_end_mwh == 4
    assert result.steps[0].wind_to_poc_mwh == result.steps[1].bess_to_poc_mwh == 0
    assert result.steps[1].unmet_discharge_mwh == 2
    assert not result.feasible


@pytest.mark.parametrize("outage", ["wind_outage", "solar_outage", "bess_outage"])
def test_outages_are_named_energy_dispositions_and_cannot_be_ignored(
    outage: str,
) -> None:
    raw = raw_envelope()
    raw[outage] = [True, True]
    result = simulate_dispatch(ChronologicalDispatchInput.from_mapping(raw))
    if outage == "bess_outage":
        assert result.steps[0].soc_end_mwh == result.steps[1].bess_to_poc_mwh == 0
    else:
        assert getattr(result.steps[0], outage + "_mwh") > 0
    if outage == "solar_outage":
        # The remaining 6 wind MWh still covers the 5-MWh instruction.
        assert result.feasible
        assert result.steps[0].wind_to_poc_mwh == 1
    else:
        assert not result.feasible


def test_final_soc_target_is_reported_not_manufactured() -> None:
    raw = raw_envelope()
    raw["final_soc_fraction"] = 0.5
    result = simulate_dispatch(ChronologicalDispatchInput.from_mapping(raw))
    assert result.steps[-1].soc_end_mwh == 0
    assert result.model_dump()["final_soc_error_mwh"] == -10
    assert not result.feasible


def test_disabled_or_absent_block_is_inert_and_enabled_is_strict() -> None:
    assert evaluate_chronological_dispatch({}) is None
    assert (
        evaluate_chronological_dispatch({"chronological_dispatch": {"enabled": False}})
        is None
    )
    for block in (
        None,
        {},
        {"enabled": 1},
        {"enabled": True},
        {"enabled": False, "price": 100},
    ):
        with pytest.raises(ValueError, match="chronological_dispatch"):
            evaluate_chronological_dispatch({"chronological_dispatch": block})
    result = evaluate_chronological_dispatch(
        {"chronological_dispatch": {"enabled": True, "inputs": raw_envelope()}}
    )
    assert result is not None and result.feasible


@pytest.mark.parametrize("seed", range(12))
def test_seeded_hostile_chronologies_conserve_all_input_energy(seed: int) -> None:
    rng = random.Random(seed)
    raw = raw_envelope()
    count = 24
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    raw["timestamps_utc"] = [
        (start + timedelta(hours=i)).isoformat() for i in range(count)
    ]
    raw["wind_generation_mwh"] = [rng.uniform(0, 20) for _ in range(count)]
    raw["solar_generation_mwh"] = [rng.uniform(0, 15) for _ in range(count)]
    raw["dispatch_instruction_mw"] = [rng.uniform(-30, 30) for _ in range(count)]
    raw["poc_limit_mw"] = [rng.uniform(0, 20) for _ in range(count)]
    for field in ("wind_outage", "solar_outage", "bess_outage", "poc_outage"):
        raw[field] = [rng.random() < 0.2 for _ in range(count)]
    raw["charge_source"] = [
        rng.choice(["grid", "renewable"]) if value < 0 else "none"
        for value in raw["dispatch_instruction_mw"]
    ]
    raw.update(
        minimum_soc_fraction=0.1,
        maximum_soc_fraction=0.9,
        initial_soc_fraction=0.5,
        final_soc_fraction=0.5,
    )
    result = simulate_dispatch(ChronologicalDispatchInput.from_mapping(raw))
    # Independent whole-horizon balance, starting from authored external energy.
    incoming = sum(raw["wind_generation_mwh"]) + sum(raw["solar_generation_mwh"])
    imports = sum(row.grid_to_bess_mwh for row in result.steps)
    outgoing = sum(
        row.wind_to_poc_mwh
        + row.solar_to_poc_mwh
        + row.bess_to_poc_mwh
        + row.wind_curtailed_mwh
        + row.solar_curtailed_mwh
        + row.wind_outage_mwh
        + row.solar_outage_mwh
        + row.charge_loss_mwh
        + row.discharge_loss_mwh
        for row in result.steps
    )
    delta = result.steps[-1].soc_end_mwh - result.steps[0].soc_start_mwh
    assert incoming + imports == pytest.approx(outgoing + delta, abs=1e-9)
    for index, row in enumerate(result.steps):
        assert 2 - 1e-9 <= row.soc_end_mwh <= 18 + 1e-9
        assert row.bess_to_poc_mwh <= 10
        assert (
            row.grid_to_bess_mwh
            + row.wind_to_poc_mwh
            + row.solar_to_poc_mwh
            + row.bess_to_poc_mwh
            <= (0 if raw["poc_outage"][index] else raw["poc_limit_mw"][index]) + 1e-9
        )
