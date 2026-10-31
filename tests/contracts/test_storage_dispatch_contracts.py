"""Strict hostile-input and immutable-receipt controls for the hourly ledger."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from typing import Any

import pytest

from analytics.contracts_v14 import ChronologicalDispatchInput, DispatchLedger
from analytics.storage_dispatch import simulate_dispatch


def raw_envelope() -> dict[str, Any]:
    """Return a synthetic two-hour 10-MWh input, with every assumption authored."""
    return {
        "sizing": {"power_mw": 10.0, "duration_h": 4.0},
        "timestamps_utc": ["2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z"],
        "step_h": 1.0,
        "wind_generation_mwh": [6.0, 0.0],
        "solar_generation_mwh": [4.0, 0.0],
        "dispatch_instruction_mw": [-5.0, 2.0],
        "poc_limit_mw": [100.0, 100.0],
        "wind_outage": [False, False],
        "solar_outage": [False, False],
        "bess_outage": [False, False],
        "poc_outage": [False, False],
        "charge_source": ["renewable", "none"],
        "charge_efficiency": 0.8,
        "discharge_efficiency": 0.5,
        "soh_fraction": 0.5,
        "minimum_soc_fraction": 0.0,
        "maximum_soc_fraction": 1.0,
        "initial_soc_fraction": 0.0,
        "final_soc_fraction": 0.0,
        "poc_flow_basis": "gross_sum",
        "allocation_policy": "charge_then_generation_then_discharge",
        "tariff_terms": "Synthetic test only; no tariff valuation or entitlement.",
        "ld_terms": "Synthetic test only; no LD valuation.",
        "provenance": "Independent synthetic physical example; not Dutch Bay evidence.",
    }


@pytest.mark.parametrize("field", sorted(raw_envelope()))
def test_every_envelope_field_is_required(field: str) -> None:
    raw = raw_envelope()
    del raw[field]
    with pytest.raises(ValueError, match=field):
        ChronologicalDispatchInput.from_mapping(raw)


@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("step_h", 0.5),
        ("step_h", True),
        ("charge_efficiency", 0.0),
        ("charge_efficiency", 1.01),
        ("discharge_efficiency", "0.9"),
        ("discharge_efficiency", float("nan")),
        ("soh_fraction", 0),
        ("soh_fraction", None),
        ("minimum_soc_fraction", -0.01),
        ("maximum_soc_fraction", 1.01),
        ("initial_soc_fraction", 1.1),
        ("final_soc_fraction", None),
        ("poc_flow_basis", "net"),
        ("allocation_policy", "merchant_optimum"),
        ("tariff_terms", ""),
        ("ld_terms", None),
        ("provenance", "  "),
        ("wind_generation_mwh", [True, 0]),
        ("solar_generation_mwh", [-1, 0]),
        ("dispatch_instruction_mw", ["-5", 2]),
        ("poc_limit_mw", [float("inf"), 100]),
        ("wind_outage", [0, False]),
        ("solar_outage", [None, False]),
        ("bess_outage", ["false", False]),
        ("poc_outage", [False]),
        ("charge_source", ["none", "none"]),
        ("charge_source", ["renewable", "grid"]),
        ("charge_source", ["invented", "none"]),
        ("wind_generation_mwh", [10**400, 0]),
    ],
)
def test_bad_envelope_values_name_the_field(field: str, bad: object) -> None:
    raw = raw_envelope()
    raw[field] = bad
    with pytest.raises(ValueError, match=field):
        ChronologicalDispatchInput.from_mapping(raw)


@pytest.mark.parametrize(
    "times",
    [
        [],
        ["2026-01-01T00:00:00Z"] * 2,
        ["2026-01-01T00:00:00Z", "2026-01-01T02:00:00Z"],
        ["2026-01-01T00:00:00", "2026-01-01T01:00:00"],
        ["2026-01-01T00:00:00+05:30", "2026-01-01T01:00:00+05:30"],
        ["bad", "2026-01-01T01:00:00Z"],
    ],
)
def test_timeline_cannot_hide_gaps_duplicates_or_timezone_inference(
    times: object,
) -> None:
    raw = raw_envelope()
    raw["timestamps_utc"] = times
    with pytest.raises(ValueError, match="timestamps_utc"):
        ChronologicalDispatchInput.from_mapping(raw)


def test_unknown_keys_and_bad_sizing_do_not_silently_disappear() -> None:
    raw = raw_envelope()
    raw["price_signal"] = [100, 200]
    with pytest.raises(ValueError, match="price_signal"):
        ChronologicalDispatchInput.from_mapping(raw)
    del raw["price_signal"]
    raw["sizing"]["rating_units"] = "kW"
    with pytest.raises(ValueError, match="sizing"):
        ChronologicalDispatchInput.from_mapping(raw)
    del raw["sizing"]["rating_units"]
    raw["sizing"]["energy_mwh"] = 400
    with pytest.raises(ValueError, match="reconcile"):
        ChronologicalDispatchInput.from_mapping(raw)


def test_sizing_underflow_and_generation_overflow_refuse_before_simulation() -> None:
    raw = raw_envelope()
    raw["sizing"] = {"power_mw": 5e-324, "duration_h": 1}
    raw["soh_fraction"] = 0.1
    with pytest.raises(ValueError, match="soh_fraction"):
        ChronologicalDispatchInput.from_mapping(raw)
    raw = raw_envelope()
    raw["wind_generation_mwh"] = raw["solar_generation_mwh"] = [1e308, 0]
    with pytest.raises(ValueError, match="remain finite"):
        ChronologicalDispatchInput.from_mapping(raw)


def test_soc_targets_must_be_inside_the_authored_window() -> None:
    raw = raw_envelope()
    raw.update(minimum_soc_fraction=0.4, maximum_soc_fraction=0.4)
    with pytest.raises(ValueError, match="minimum_soc_fraction"):
        ChronologicalDispatchInput.from_mapping(raw)
    raw.update(maximum_soc_fraction=0.9)
    with pytest.raises(ValueError, match="initial_soc_fraction"):
        ChronologicalDispatchInput.from_mapping(raw)


def test_input_is_deeply_immutable_and_json_copy_cannot_rewrite_it() -> None:
    raw = raw_envelope()
    before = deepcopy(raw)
    cfg = ChronologicalDispatchInput.from_mapping(raw)
    digest = cfg.sha256
    assert raw == before
    raw["wind_generation_mwh"][0] = 999
    assert cfg.wind_generation_mwh == (6.0, 0.0)
    with pytest.raises(FrozenInstanceError):
        cfg.step_h = 2  # type: ignore[misc]
    with pytest.raises(ValueError, match="immutable tuple"):
        replace(cfg, wind_generation_mwh=[6, 0])  # type: ignore[arg-type]
    dumped = cfg.model_dump()
    dumped["wind_generation_mwh"][0] = 777
    assert cfg.sha256 == digest
    assert ChronologicalDispatchInput.from_mapping(cfg.model_dump()) == cfg


def test_receipt_serialization_revalidates_hostile_flow_edits() -> None:
    cfg = ChronologicalDispatchInput.from_mapping(raw_envelope())
    result = simulate_dispatch(cfg)
    row = result.steps[0]
    with pytest.raises(FrozenInstanceError):
        row.wind_to_poc_mwh = 100  # type: ignore[misc]
    with pytest.raises(ValueError, match="wind custody"):
        DispatchLedger(
            inputs=cfg, steps=(replace(row, wind_to_poc_mwh=100), result.steps[1])
        )
    object.__setattr__(row, "charge_loss_mwh", 0)
    with pytest.raises(ValueError, match="charge loss"):
        result.model_dump()


def test_hostile_envelope_mutation_is_rechecked_by_simulation() -> None:
    cfg = ChronologicalDispatchInput.from_mapping(raw_envelope())
    object.__setattr__(cfg, "charge_efficiency", None)
    with pytest.raises(ValueError, match="charge_efficiency"):
        simulate_dispatch(cfg)


@pytest.mark.parametrize(
    ("change", "error"),
    [
        ({"poc_limit_mw": (4, 100)}, "POC limit"),
        ({"poc_outage": (True, False)}, "POC limit"),
        ({"maximum_soc_fraction": 0.1}, "SOC window"),
        ({"bess_outage": (True, False)}, "battery in outage"),
        ({"charge_source": ("grid", "none")}, "charge source"),
    ],
)
def test_receipts_cannot_be_relabelled_with_a_tighter_envelope(
    change: dict[str, Any], error: str
) -> None:
    cfg = ChronologicalDispatchInput.from_mapping(raw_envelope())
    result = simulate_dispatch(cfg)
    with pytest.raises(ValueError, match=error):
        DispatchLedger(inputs=replace(cfg, **change), steps=result.steps)


def test_receipt_power_limit_and_soc_continuity_are_independently_checked() -> None:
    from analytics.contracts_v14 import BessSizing

    cfg = ChronologicalDispatchInput.from_mapping(raw_envelope())
    result = simulate_dispatch(cfg)
    # Same energy capacity, tighter power rating: do not merely pin the nameplate.
    with pytest.raises(ValueError, match="battery power"):
        DispatchLedger(
            inputs=replace(cfg, sizing=BessSizing(2, 20, 40)), steps=result.steps
        )
    with pytest.raises(ValueError, match="SOC continuity"):
        DispatchLedger(
            inputs=cfg,
            steps=(result.steps[0], replace(result.steps[1], soc_start_mwh=1)),
        )


def test_direct_constructor_refuses_mutable_or_unparsed_timeline() -> None:
    cfg = ChronologicalDispatchInput.from_mapping(raw_envelope())
    with pytest.raises(ValueError, match="timestamps_utc"):
        replace(cfg, timestamps_utc=tuple(raw_envelope()["timestamps_utc"]))


def test_malformed_shapes_fail_at_their_public_boundary() -> None:
    with pytest.raises(ValueError, match="mapping"):
        ChronologicalDispatchInput.from_mapping(None)  # type: ignore[arg-type]
    for field in ("sizing", "wind_generation_mwh"):
        raw = raw_envelope()
        raw[field] = None
        with pytest.raises(ValueError, match=field):
            ChronologicalDispatchInput.from_mapping(raw)
    cfg = ChronologicalDispatchInput.from_mapping(raw_envelope())
    with pytest.raises(ValueError, match="BessSizing"):
        replace(cfg, sizing={})  # type: ignore[arg-type]
    result = simulate_dispatch(cfg)
    with pytest.raises(ValueError, match="ChronologicalDispatchInput"):
        DispatchLedger(inputs={}, steps=result.steps)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="aligned hourly"):
        DispatchLedger(inputs=cfg, steps=result.steps[:1])
    with pytest.raises(ValueError, match="DispatchStep"):
        DispatchLedger(inputs=cfg, steps=(None, None))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="timestamp"):
        DispatchLedger(
            inputs=cfg,
            steps=(
                replace(result.steps[0], timestamp_utc=cfg.timestamps_utc[1]),
                result.steps[1],
            ),
        )
    with pytest.raises(ValueError, match="unmet_charge_mwh"):
        replace(result.steps[0], unmet_charge_mwh=-1)
