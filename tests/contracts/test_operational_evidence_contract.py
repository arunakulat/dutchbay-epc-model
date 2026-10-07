"""Hostile contract tests for the post-COD operational evidence envelope (#1331)."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError, replace
from typing import Any

import pytest

from analytics.operational.contracts import (
    OPERATIONAL_EVIDENCE_SCHEMA,
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
    data = dict(
        logical_id=f"{kind}-primary",
        kind=kind,
        source_class=source_classes.get(kind, "observed_plant"),
        source_locator=f"evidence/{kind}.parquet",
        source_sha256=_SHA,
        coverage_start_utc=_START,
        coverage_end_utc=_END,
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


@pytest.mark.parametrize("bad", [0, -1, 1.5, True])
def test_row_count_is_a_positive_real_integer(bad: object) -> None:
    with pytest.raises(OperationalEvidenceError, match="row_count"):
        _dataset("revenue_meter", {"timestamp_utc", "energy_kwh"}, row_count=bad)


def test_unknown_role_and_wrong_unit_are_rejected() -> None:
    with pytest.raises(OperationalEvidenceError, match="Unsupported"):
        _binding("price_usd_mwh")
    with pytest.raises(OperationalEvidenceError, match="requires"):
        _binding("power_kw", unit="MW")


def test_dataset_rejects_duplicate_roles_and_source_columns() -> None:
    common = dict(
        logical_id="meter",
        kind="revenue_meter",
        source_class="observed_plant",
        source_locator="meter.parquet",
        source_sha256=_SHA,
        coverage_start_utc=_START,
        coverage_end_utc=_END,
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


def test_roles_may_be_satisfied_across_multiple_same_kind_artifacts() -> None:
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
    assert _envelope(datasets=tuple(datasets)).purpose == "long_term_aep"


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
