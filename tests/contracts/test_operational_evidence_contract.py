"""Hostile contract tests for the post-COD operational evidence envelope (#1331)."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError, replace
from typing import Any

import pytest

from analytics.operational.contracts import (
    OPERATIONAL_CALENDAR_MONTH_ALLOWED,
    OPERATIONAL_EVIDENCE_SCHEMA,
    OPERATIONAL_MAX_INTERVAL_SECONDS,
    OPERATIONAL_REQUIRED_ROLES,
    OperationalAssessmentInput,
    OperationalColumnBinding,
    OperationalDatasetEvidence,
    OperationalEvidenceError,
)

_START = "2025-01-01T00:00:00Z"
_END = "2025-12-31T23:50:00Z"
_SHA = "a" * 64


def _binding(role: str, source: str | None = None, unit: str | None = None):
    units = {
        "timestamp_utc": "iso8601_utc",
        "asset_id": "1",
        "status_code": "1",
        "energy_kwh": "kWh",
        "power_kw": "kW",
        "wind_speed_ms": "m/s",
        "wind_direction_deg": "degree",
        "air_density_kgm3": "kg/m^3",
        "air_temperature_c": "degC",
        "availability_loss_kwh": "kWh",
        "curtailment_loss_kwh": "kWh",
        "rated_power_kw": "kW",
        "latitude_deg": "degree_north",
        "longitude_deg": "degree_east",
    }
    return OperationalColumnBinding(
        role=role,
        source_column=source or role,
        unit=unit or units.get(role, "USD/MWh"),
    )


def _dataset(kind: str, roles: set[str] | frozenset[str], **overrides: Any):
    source_classes = {
        "scada": "observed_plant",
        "revenue_meter": "observed_plant",
        "met_tower": "observed_plant",
        "status": "observed_plant",
        "curtailment": "observed_plant",
        "reanalysis": "reference_reanalysis",
        "asset": "declared_asset",
    }
    observation_statuses = {
        "scada": "observed",
        "revenue_meter": "observed",
        "met_tower": "observed",
        "status": "observed",
        "curtailment": "derived_estimate",
        "reanalysis": "reference_reanalysis",
        "asset": "declared_metadata",
    }
    data = dict(
        logical_id=f"{kind}-primary",
        kind=kind,
        source_class=source_classes.get(kind, "observed_plant"),
        timezone_treatment="not_applicable" if kind == "asset" else "source_utc",
        source_timezone=None,
        ambiguous_time_policy="not_applicable",
        nonexistent_time_policy="not_applicable",
        observation_status=observation_statuses.get(kind, "observed"),
        lineage_source_sha256=(("b" * 64,) if kind == "curtailment" else ()),
        derivation_method_sha256=("c" * 64 if kind == "curtailment" else None),
        source_locator=f"evidence/{kind}.parquet",
        source_sha256=_SHA,
        coverage_start_utc=_START,
        coverage_end_utc=_END,
        interval_basis="not_applicable" if kind == "asset" else "fixed_seconds",
        interval_seconds=None if kind == "asset" else 600,
        row_count=15 if kind == "asset" else 52_560,
        columns=tuple(_binding(role) for role in sorted(roles)),
    )
    data.update(overrides)
    return OperationalDatasetEvidence(**data)


def _datasets_for(purpose: str) -> tuple[OperationalDatasetEvidence, ...]:
    return tuple(
        _dataset(kind, roles)
        for kind, roles in OPERATIONAL_REQUIRED_ROLES[purpose].items()
    )


def _envelope(purpose: str = "long_term_aep", **overrides: Any):
    datasets = (
        _datasets_for(purpose)
        if purpose in OPERATIONAL_REQUIRED_ROLES
        else _datasets_for("long_term_aep")
    )
    data = dict(
        schema=OPERATIONAL_EVIDENCE_SCHEMA,
        project_id="dutchbay",
        assessment_id=f"oa-{purpose}-2025",
        purpose=purpose,
        assessment_start_utc=_START,
        assessment_end_utc=_END,
        datasets=datasets,
    )
    data.update(overrides)
    return OperationalAssessmentInput(**data)


@pytest.mark.parametrize(
    "purpose",
    [
        "long_term_aep",
        "turbine_gross_energy",
        "electrical_losses",
        "wake_losses_scada",
        "wake_losses_tower",
    ],
)
def test_every_supported_purpose_accepts_its_exact_minimum(purpose: str) -> None:
    envelope = _envelope(purpose)
    assert envelope.purpose == purpose
    assert envelope.canonical_finance_eligible is False
    assert envelope.model_dump()["schema"] == OPERATIONAL_EVIDENCE_SCHEMA
    assert envelope.dict() == envelope.model_dump()


def test_contracts_are_frozen_and_nested_collections_are_tuples() -> None:
    envelope = _envelope()
    assert isinstance(envelope.datasets, tuple)
    assert isinstance(envelope.datasets[0].columns, tuple)
    with pytest.raises(FrozenInstanceError):
        envelope.bankable = True  # type: ignore[misc]


def test_model_dump_is_json_serializable_without_custom_encoders() -> None:
    encoded = json.dumps(_envelope().model_dump(), sort_keys=True)
    assert '"schema": "dutchbay.operational_evidence.v1"' in encoded
    assert '"canonical_finance_eligible": false' in encoded


@pytest.mark.parametrize("bad", ["A" * 64, "a" * 63, "not-a-digest", 7])
def test_source_digest_is_exact_lowercase_sha256(bad: object) -> None:
    with pytest.raises(OperationalEvidenceError, match="source_sha256"):
        _dataset("revenue_meter", {"timestamp_utc", "energy_kwh"}, source_sha256=bad)


@pytest.mark.parametrize(
    "field,bad",
    [
        ("coverage_start_utc", "2025-01-01T00:00:00"),
        ("coverage_start_utc", "2025-01-01T00:00:00+00:00"),
        ("coverage_start_utc", "2025-02-30T00:00:00Z"),
        ("coverage_end_utc", _START),
    ],
)
def test_dataset_time_basis_fails_loud(field: str, bad: str) -> None:
    with pytest.raises(OperationalEvidenceError):
        _dataset("revenue_meter", {"timestamp_utc", "energy_kwh"}, **{field: bad})


@pytest.mark.parametrize("bad", [0, -1, 1.5, True, None])
def test_timeseries_interval_is_a_positive_real_integer(bad: object) -> None:
    with pytest.raises(OperationalEvidenceError, match="interval_seconds"):
        _dataset(
            "revenue_meter",
            {"timestamp_utc", "energy_kwh"},
            interval_seconds=bad,
        )


def test_asset_metadata_refuses_a_fabricated_interval() -> None:
    with pytest.raises(OperationalEvidenceError, match="non-timeseries"):
        _dataset("asset", {"asset_id", "rated_power_kw"}, interval_seconds=600)


def test_asset_metadata_requires_explicit_not_applicable_time_treatment() -> None:
    with pytest.raises(OperationalEvidenceError, match="timezone_treatment"):
        _dataset(
            "asset",
            {"asset_id", "rated_power_kw"},
            timezone_treatment="source_utc",
        )
    with pytest.raises(OperationalEvidenceError, match="interval_basis"):
        _dataset(
            "asset",
            {"asset_id", "rated_power_kw"},
            interval_basis="fixed_seconds",
        )


@pytest.mark.parametrize("bad", [0, -1, 1.5, True])
def test_row_count_is_a_positive_real_integer(bad: object) -> None:
    with pytest.raises(OperationalEvidenceError, match="row_count"):
        _dataset("revenue_meter", {"timestamp_utc", "energy_kwh"}, row_count=bad)


def test_unknown_role_and_wrong_unit_are_rejected() -> None:
    with pytest.raises(OperationalEvidenceError, match="role"):
        _binding("price_usd_mwh")
    with pytest.raises(OperationalEvidenceError, match="requires"):
        _binding("power_kw", unit="MW")


def test_dataset_rejects_duplicate_roles_and_source_columns() -> None:
    common = dict(
        logical_id="meter",
        kind="revenue_meter",
        source_class="observed_plant",
        timezone_treatment="source_utc",
        source_timezone=None,
        ambiguous_time_policy="not_applicable",
        nonexistent_time_policy="not_applicable",
        observation_status="observed",
        lineage_source_sha256=(),
        derivation_method_sha256=None,
        source_locator="meter.parquet",
        source_sha256=_SHA,
        coverage_start_utc=_START,
        coverage_end_utc=_END,
        interval_basis="fixed_seconds",
        interval_seconds=600,
        row_count=2,
    )
    with pytest.raises(OperationalEvidenceError, match="duplicate semantic roles"):
        OperationalDatasetEvidence(
            **common,
            columns=(
                _binding("timestamp_utc", "a"),
                _binding("timestamp_utc", "b"),
            ),
        )
    with pytest.raises(OperationalEvidenceError, match="source column"):
        OperationalDatasetEvidence(
            **common,
            columns=(
                _binding("timestamp_utc", "same"),
                _binding("energy_kwh", "same"),
            ),
        )


def test_kind_requires_the_correct_evidence_class() -> None:
    with pytest.raises(OperationalEvidenceError, match="source_class"):
        _dataset(
            "reanalysis",
            {"timestamp_utc", "wind_speed_ms", "air_density_kgm3"},
            source_class="observed_plant",
        )


@pytest.mark.parametrize(
    "kind,bad_status",
    [
        ("scada", "reference_reanalysis"),
        ("reanalysis", "observed"),
        ("asset", "observed"),
    ],
)
def test_kind_requires_explicit_observation_status(kind: str, bad_status: str) -> None:
    roles = next(
        roles
        for requirements in OPERATIONAL_REQUIRED_ROLES.values()
        for candidate_kind, roles in requirements.items()
        if candidate_kind == kind
    )
    with pytest.raises(OperationalEvidenceError, match="observation_status"):
        _dataset(kind, roles, observation_status=bad_status)


def test_named_zone_treatment_binds_zone_and_dst_policies() -> None:
    dataset = _dataset(
        "revenue_meter",
        {"timestamp_utc", "energy_kwh"},
        timezone_treatment="named_zone_to_utc",
        source_timezone="America/New_York",
        ambiguous_time_policy="fold_1",
        nonexistent_time_policy="shift_forward",
    )
    assert dataset.source_timezone == "America/New_York"
    assert dataset.ambiguous_time_policy == "fold_1"


@pytest.mark.parametrize(
    "overrides,match",
    [
        (
            {
                "timezone_treatment": "named_zone_to_utc",
                "ambiguous_time_policy": "reject",
                "nonexistent_time_policy": "reject",
            },
            "source_timezone",
        ),
        (
            {
                "timezone_treatment": "named_zone_to_utc",
                "source_timezone": "Not/A_Real_Zone",
                "ambiguous_time_policy": "reject",
                "nonexistent_time_policy": "reject",
            },
            "IANA timezone",
        ),
        (
            {
                "timezone_treatment": "named_zone_to_utc",
                "source_timezone": "Asia/Colombo",
                "nonexistent_time_policy": "reject",
            },
            "ambiguous_time_policy",
        ),
        (
            {
                "timezone_treatment": "named_zone_to_utc",
                "source_timezone": "Asia/Colombo",
                "ambiguous_time_policy": "reject",
            },
            "nonexistent_time_policy",
        ),
        ({"source_timezone": "Asia/Colombo"}, "apply only"),
        ({"ambiguous_time_policy": "reject"}, "apply only"),
        ({"nonexistent_time_policy": "reject"}, "apply only"),
    ],
)
def test_timezone_policy_combinations_fail_loud(
    overrides: dict[str, object], match: str
) -> None:
    with pytest.raises(OperationalEvidenceError, match=match):
        _dataset("revenue_meter", {"timestamp_utc", "energy_kwh"}, **overrides)


def test_derived_curtailment_evidence_requires_bound_lineage() -> None:
    dataset = _dataset(
        "curtailment",
        {
            "timestamp_utc",
            "availability_loss_kwh",
            "curtailment_loss_kwh",
        },
    )
    assert dataset.observation_status == "derived_estimate"
    assert dataset.lineage_source_sha256 == ("b" * 64,)
    assert dataset.derivation_method_sha256 == "c" * 64

    with pytest.raises(OperationalEvidenceError, match="upstream"):
        replace(dataset, lineage_source_sha256=())
    with pytest.raises(OperationalEvidenceError, match="derivation_method_sha256"):
        replace(dataset, derivation_method_sha256=None)


def test_derived_status_is_bounded_and_mixed_status_is_prohibited() -> None:
    meter = _dataset("revenue_meter", {"timestamp_utc", "energy_kwh"})
    with pytest.raises(OperationalEvidenceError, match="admits observation_status"):
        replace(
            meter,
            observation_status="derived_estimate",
            lineage_source_sha256=("b" * 64,),
            derivation_method_sha256="c" * 64,
        )
    with pytest.raises(OperationalEvidenceError, match="observation_status"):
        replace(meter, observation_status="mixed")


def test_non_derived_evidence_rejects_derivation_lineage() -> None:
    meter = _dataset("revenue_meter", {"timestamp_utc", "energy_kwh"})
    with pytest.raises(OperationalEvidenceError, match="only to"):
        replace(meter, lineage_source_sha256=("b" * 64,))


def test_kind_refuses_semantically_wrong_but_globally_valid_roles() -> None:
    with pytest.raises(OperationalEvidenceError, match="does not admit"):
        _dataset(
            "revenue_meter",
            {"timestamp_utc", "availability_loss_kwh"},
        )


def test_missing_kind_and_missing_role_are_distinct_failures() -> None:
    datasets = _datasets_for("long_term_aep")
    with pytest.raises(OperationalEvidenceError, match="dataset kinds"):
        _envelope(datasets=tuple(d for d in datasets if d.kind != "curtailment"))

    bad_reanalysis = _dataset("reanalysis", {"timestamp_utc", "wind_speed_ms"})
    with pytest.raises(OperationalEvidenceError, match="air_density_kgm3"):
        _envelope(
            datasets=tuple(
                bad_reanalysis if d.kind == "reanalysis" else d for d in datasets
            )
        )


def test_roles_cannot_be_combined_across_unrelated_same_kind_artifacts() -> None:
    datasets = [d for d in _datasets_for("long_term_aep") if d.kind != "reanalysis"]
    datasets.extend(
        [
            _dataset(
                "reanalysis",
                {"timestamp_utc", "wind_speed_ms"},
                logical_id="era5-wind",
            ),
            _dataset(
                "reanalysis",
                {"air_density_kgm3"},
                logical_id="era5-density",
                source_sha256="b" * 64,
            ),
        ]
    )
    with pytest.raises(OperationalEvidenceError, match="individually complete"):
        _envelope(datasets=tuple(datasets))


@pytest.mark.parametrize(
    "purpose,kind,max_seconds",
    [
        (purpose, kind, max_seconds)
        for purpose, requirements in OPERATIONAL_MAX_INTERVAL_SECONDS.items()
        for kind, max_seconds in requirements.items()
        if max_seconds is not None
    ],
)
def test_purpose_kind_fixed_interval_boundary_is_inclusive_and_fail_loud(
    purpose: str, kind: str, max_seconds: int
) -> None:
    datasets = list(_datasets_for(purpose))
    index = next(i for i, dataset in enumerate(datasets) if dataset.kind == kind)
    datasets[index] = replace(datasets[index], interval_seconds=max_seconds)
    assert _envelope(purpose, datasets=tuple(datasets)).purpose == purpose

    datasets[index] = replace(datasets[index], interval_seconds=max_seconds + 1)
    with pytest.raises(OperationalEvidenceError, match="interval_seconds <="):
        _envelope(purpose, datasets=tuple(datasets))


@pytest.mark.parametrize(
    "purpose,kind",
    [
        (purpose, kind)
        for purpose, kinds in OPERATIONAL_CALENDAR_MONTH_ALLOWED.items()
        for kind in sorted(kinds)
    ],
)
def test_calendar_month_is_explicit_and_only_allowed_for_monthly_minima(
    purpose: str, kind: str
) -> None:
    datasets = list(_datasets_for(purpose))
    index = next(i for i, dataset in enumerate(datasets) if dataset.kind == kind)
    datasets[index] = replace(
        datasets[index], interval_basis="calendar_month", interval_seconds=None
    )
    assert _envelope(purpose, datasets=tuple(datasets)).purpose == purpose


@pytest.mark.parametrize(
    "purpose,kind",
    [
        ("turbine_gross_energy", "reanalysis"),
        ("wake_losses_scada", "reanalysis"),
    ],
)
def test_calendar_month_is_rejected_for_daily_and_hourly_purposes(
    purpose: str, kind: str
) -> None:
    datasets = list(_datasets_for(purpose))
    index = next(i for i, dataset in enumerate(datasets) if dataset.kind == kind)
    datasets[index] = replace(
        datasets[index], interval_basis="calendar_month", interval_seconds=None
    )
    with pytest.raises(OperationalEvidenceError, match="does not admit calendar-month"):
        _envelope(purpose, datasets=tuple(datasets))


def test_calendar_month_cannot_claim_a_fixed_seconds_duration() -> None:
    with pytest.raises(OperationalEvidenceError, match="variable duration"):
        _dataset(
            "revenue_meter",
            {"timestamp_utc", "energy_kwh"},
            interval_basis="calendar_month",
            interval_seconds=2_592_000,
        )


def test_duplicate_logical_id_is_rejected() -> None:
    datasets = list(_datasets_for("electrical_losses"))
    datasets[1] = replace(datasets[1], logical_id=datasets[0].logical_id)
    with pytest.raises(OperationalEvidenceError, match="logical_id values"):
        _envelope("electrical_losses", datasets=tuple(datasets))


def test_required_dataset_must_cover_declared_window() -> None:
    datasets = list(_datasets_for("electrical_losses"))
    datasets[0] = replace(datasets[0], coverage_start_utc="2025-02-01T00:00:00Z")
    with pytest.raises(OperationalEvidenceError, match="does not cover"):
        _envelope("electrical_losses", datasets=tuple(datasets))


@pytest.mark.parametrize(
    "field,bad",
    [
        ("raw_evidence_only", False),
        ("raw_evidence_only", 1),
        ("canonical_finance_eligible", True),
        ("canonical_finance_eligible", 0),
        ("bankable", True),
        ("lender_eligible", True),
        ("board_eligible", True),
    ],
)
def test_authority_fences_cannot_be_laundered(field: str, bad: object) -> None:
    with pytest.raises(OperationalEvidenceError, match=field):
        replace(_envelope(), **{field: bad})


def test_unknown_schema_purpose_and_kind_are_rejected_at_runtime() -> None:
    with pytest.raises(OperationalEvidenceError, match="schema"):
        _envelope(schema="dutchbay.operational_evidence.v2")
    with pytest.raises(OperationalEvidenceError, match="purpose"):
        _envelope(purpose="merchant_price")
    with pytest.raises(OperationalEvidenceError, match="kind"):
        _dataset("price", {"timestamp_utc", "energy_kwh"})


@pytest.mark.parametrize(
    "field,bad",
    [
        ("kind", []),
        ("source_class", []),
        ("timezone_treatment", {}),
        ("source_timezone", {}),
        ("ambiguous_time_policy", []),
        ("nonexistent_time_policy", {}),
        ("observation_status", []),
        ("interval_basis", {}),
    ],
)
def test_unhashable_dataset_vocabulary_inputs_use_contract_error(
    field: str, bad: object
) -> None:
    dataset = _dataset("revenue_meter", {"timestamp_utc", "energy_kwh"})
    with pytest.raises(OperationalEvidenceError, match=field):
        replace(dataset, **{field: bad})


@pytest.mark.parametrize("field,bad", [("role", []), ("unit", {})])
def test_unhashable_column_vocabulary_inputs_use_contract_error(
    field: str, bad: object
) -> None:
    with pytest.raises(OperationalEvidenceError):
        replace(_binding("power_kw"), **{field: bad})


def test_unhashable_purpose_uses_contract_error() -> None:
    with pytest.raises(OperationalEvidenceError, match="purpose"):
        replace(_envelope(), purpose=[])
