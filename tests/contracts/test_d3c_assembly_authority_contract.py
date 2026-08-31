"""Executable D3C-0 assembly-authority acceptance and hostile controls."""

from __future__ import annotations

import ast
import copy
import inspect
import json
import os
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any

import jsonschema  # type: ignore[import-untyped]
import pytest
from pydantic import ValidationError

import analytics.feasibility_report_contract as public_contract
import analytics.feasibility_report_contract.assembly_authority as authority
from analytics.feasibility_report_contract.assembly_authority import (
    ASSEMBLY_AUTHORITY_CONTRACT_VERSION,
    ASSEMBLY_AUTHORITY_SCHEMA_ID,
    NON_RELIANCE_STATEMENT,
    AcceptedAssemblyAuthority,
    AssemblyAuthorityBlockCode,
    AssemblyAuthorityOutcome,
    BlockedAssemblyAuthority,
    GovernedByteArtifactRole,
    resolve_assembly_authority,
)
from analytics.feasibility_report_contract.vocabulary import (
    FEASIBILITY_REPORT_CONTRACT_VERSION,
)

_MODULE = Path(authority.__file__).resolve()
_UTC = timezone.utc
_ALLOCATED = datetime(2026, 8, 31, 1, tzinfo=_UTC)
_REPORT_CREATED = datetime(2026, 8, 31, 2, tzinfo=_UTC)
_ENGINE_CREATED = datetime(2026, 8, 31, 3, tzinfo=_UTC)
_ARTIFACT_CREATED = datetime(2026, 8, 31, 4, tzinfo=_UTC)
_RUNTIME_CAPTURED = datetime(2026, 8, 31, 5, tzinfo=_UTC)
_AUTHORITY_CREATED = datetime(2026, 8, 31, 6, tzinfo=_UTC)


def _digest(character: str) -> dict[str, str]:
    return {"algorithm": "sha256", "value": character * 64}


def _pack(*, pack_id: str, kind: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "pack_id": pack_id,
        "kind": kind,
        "status": "unsupported",
        "version": "1.0.0",
        "owner_actor_id": "actor:d3c-orchestrator",
        "effective_date": date(2026, 8, 31),
        "review_date": date(2026, 9, 30),
        "compatible_contract_versions": (FEASIBILITY_REPORT_CONTRACT_VERSION,),
        "project_stages": ("screening",),
        "section_ids": ("appendices_provenance_audit_trail",),
        "capability_ids": (f"capability:{kind}",),
        "evidence_minima": (),
        "cross_field_rules": ("Exact pack axis and version must remain visible.",),
        "permitted_degradations": (),
        "prohibited_substitutions": (
            "Unsupported pack facts cannot be promoted or defaulted.",
        ),
    }
    if kind == "jurisdiction":
        payload["jurisdiction_codes"] = ("FIC",)
    else:
        payload["technology_ids"] = ("wind",)
    return payload


def _artifact(role: str, character: str) -> dict[str, Any]:
    return {
        "artifact_id": f"artifact:{role}",
        "report_id": "report:d3c-fixture",
        "run_id": "run:d3c-fixture",
        "format": "json",
        "mime_type": "application/json",
        "producer": "D3B governed result capture",
        "producer_version": "15.4.0",
        "created_at": _ARTIFACT_CREATED,
        "content_digest": _digest(character),
        "completeness_profile": f"Exact {role} bytes only; not a report package.",
        "is_full_package": False,
        "source_ids": ("source:runtime",),
        "disclosure_exceptions": (
            "Held internal plumbing artifact; no reliance is permitted.",
        ),
        "confidentiality": "internal",
    }


def _byte_binding(role: str, character: str) -> dict[str, Any]:
    return {
        "artifact_id": f"artifact:{role}",
        "role": role,
        "byte_length": 128,
        "locator": f"governed://d3b-result/{role}.json",
        "format": "json",
        "mime_type": "application/json",
        "producer": "D3B governed result capture",
        "producer_version": "15.4.0",
        "created_at": _ARTIFACT_CREATED,
        "source_ids": ("source:runtime",),
        "confidentiality": "internal",
        "content_digest": _digest(character),
    }


def _accepted_payload() -> dict[str, Any]:
    artifact_roles = (
        (GovernedByteArtifactRole.ANNUAL_ROWS.value, "a"),
        (GovernedByteArtifactRole.DEBT_RESULT.value, "b"),
        (GovernedByteArtifactRole.FX_CURVE.value, "c"),
    )
    artifact_ids = tuple(f"artifact:{role}" for role, _ in artifact_roles)
    return {
        "outcome": AssemblyAuthorityOutcome.ACCEPTED.value,
        "schema_id": ASSEMBLY_AUTHORITY_SCHEMA_ID,
        "contract_version": ASSEMBLY_AUTHORITY_CONTRACT_VERSION,
        "authority_id": "authority:d3c-fixture",
        "authority_created_at": _AUTHORITY_CREATED,
        "report_identity": {
            "report_id": "report:d3c-fixture",
            "project_id": "project:fictionland-wind",
            "case_id": "case:screening-base",
            "run_id": "run:d3c-fixture",
            "issue": 1,
            "revision": 0,
            "created_at": _REPORT_CREATED,
        },
        "evaluation_request_identity": {
            "request_id": "request:d3b-fixture",
            "project_id": "project:fictionland-wind",
            "case_id": "case:screening-base",
            "project_case_revision": 1,
            "d3b_scenario_authority_id": "authority:d3b-fixture",
            "config_id": "config:fictionland-wind",
            "evidence_cutoff": date(2026, 8, 30),
            "valuation_date": date(2026, 8, 31),
        },
        "upstream_digests": {
            "project_case": _digest("d"),
            "evaluation_request": _digest("e"),
            "d3b_execution_success": _digest("f"),
            "d3b_embedded_project_case": _digest("d"),
            "d3b_embedded_evaluation_request": _digest("e"),
        },
        "allocation_authority": {
            "allocation_id": "allocation:d3c-fixture",
            "source_id": "source:runtime",
            "actor_id": "actor:d3c-orchestrator",
            "allocated_at": _ALLOCATED,
        },
        "orchestration_actor_id": "actor:d3c-orchestrator",
        "runtime_receipt": {
            "runtime_receipt_id": "runtime:d3b-fixture",
            "source_id": "source:runtime",
            "source_digest": _digest("9"),
            "engine_version": "15.4.0",
            "code_commit": "1d3b004d8c1cc6ecfa9515d0a4b51ec876e986f8",
            "dirty_worktree": False,
            "dirty_diff_digest": None,
            "environment": ("python=3.12.13", "platform=macos"),
            "dependency_versions": ("pydantic=2.12.5", "numpy=2.4.6"),
            "engine_run_created_at": _ENGINE_CREATED,
            "captured_at": _RUNTIME_CAPTURED,
        },
        "actor_records": (
            {
                "actor_id": "actor:d3c-orchestrator",
                "kind": "software",
                "name": "D3C orchestration fixture",
                "organization": "DutchBay",
                "version": "1.0.0",
                "operation": "Bind governed assembly facts without assembly.",
                "identity_verified": False,
                "authority_basis": "Fixture provenance only; no human role or release.",
            },
        ),
        "source_records": (
            {
                "source_id": "source:runtime",
                "title": "Governed D3B runtime and artifact receipt fixture",
                "issuer_or_author": "DutchBay test fixture",
                "document_or_dataset_id": "d3b-runtime-fixture-v1",
                "revision": "1",
                "observation_date": date(2026, 8, 31),
                "retrieval_date": date(2026, 8, 31),
                "locator": {
                    "evidence_path": "tests/fixtures/d3b-runtime-fixture.json",
                    "pinpoint": "whole controlled fixture",
                },
                "source_class": "derived",
                "authenticity_status": "verified",
                "authority": "Controlled contract fixture only.",
                "jurisdictions": ("FIC",),
                "technology_ids": ("wind",),
                "project_boundary": "Fictionland wind contract fixture",
                "section_ids": ("appendices_provenance_audit_trail",),
                "period": "2026-08-31 controlled fixture",
                "licence_or_publication_rights": "Internal test use only.",
                "publication_permitted": False,
                "access_restrictions": "Internal verification only.",
                "confidentiality": "internal",
                "extraction_method": "Deterministic fixture construction.",
                "extracting_actor_id": "actor:d3c-orchestrator",
                "quality_checks": ("Exact digest and graph reciprocity checked.",),
                "content_digest": _digest("9"),
            },
        ),
        "pack_bindings": (
            _pack(pack_id="pack:fic", kind="jurisdiction"),
            _pack(pack_id="pack:wind", kind="technology"),
        ),
        "jurisdiction_pack_ids": ("pack:fic",),
        "technology_pack_ids": ("pack:wind",),
        "authorized_registry_ids": {
            "capability_ids": (
                "capability:jurisdiction",
                "capability:technology",
            )
        },
        "artifact_records": tuple(
            _artifact(role, character) for role, character in artifact_roles
        ),
        "byte_artifact_bindings": tuple(
            _byte_binding(role, character) for role, character in artifact_roles
        ),
        "distribution": {
            "release_status": "hold",
            "non_reliance": True,
            "permitted_reliance_statement": NON_RELIANCE_STATEMENT,
            "scope_intended_audiences": ("Internal engineering reviewers",),
            "scope_intended_uses": ("D3C plumbing verification",),
            "control": {
                "distribution_id": "distribution:d3c-fixture",
                "artifact_ids": artifact_ids,
                "intended_audiences": ("Internal engineering reviewers",),
                "permitted_uses": ("D3C plumbing verification",),
                "permitted_reliance": NON_RELIANCE_STATEMENT,
                "distribution_class": "internal",
                "confidentiality": "Internal controlled fixture.",
                "publication_rights": "No publication is authorized.",
                "reliance_exclusions": (
                    "No achieved grade, professional conclusion, lender acceptance, "
                    "Board authority or package release is conferred.",
                ),
                "expiry_or_review_date": date(2027, 8, 31),
                "redaction_policy": "No external distribution; fail closed.",
            },
        },
    }


def _accepted() -> AcceptedAssemblyAuthority:
    return _validate(_accepted_payload())


def _validate(payload: dict[str, Any]) -> AcceptedAssemblyAuthority:
    return AcceptedAssemblyAuthority.model_validate_json(
        json.dumps(
            payload,
            default=lambda value: (
                value.isoformat() if isinstance(value, (date, datetime)) else value
            ),
        )
    )


def _set(payload: dict[str, Any], path: tuple[str | int, ...], value: Any) -> None:
    cursor: Any = payload
    for component in path[:-1]:
        cursor = cursor[component]
    cursor[path[-1]] = value


def test_constructive_authority_is_exact_frozen_and_round_trips() -> None:
    accepted = _accepted()

    assert accepted.outcome is AssemblyAuthorityOutcome.ACCEPTED
    assert accepted.distribution.release_status == "hold"
    assert accepted.distribution.non_reliance is True
    assert accepted.distribution.control.permitted_reliance == NON_RELIANCE_STATEMENT
    assert {pack.status.value for pack in accepted.pack_bindings} == {"unsupported"}
    assert {binding.role for binding in accepted.byte_artifact_bindings} == set(
        GovernedByteArtifactRole
    )
    assert (
        AcceptedAssemblyAuthority.model_validate_json(accepted.model_dump_json())
        == accepted
    )
    with pytest.raises(ValidationError, match="frozen"):
        accepted.authority_id = "authority:mutated"  # type: ignore[misc]


@pytest.mark.parametrize(
    "model",
    (AcceptedAssemblyAuthority, BlockedAssemblyAuthority),
)
def test_draft_2020_12_validation_and_serialization_schemas(model: type[Any]) -> None:
    instance: Any
    if model is AcceptedAssemblyAuthority:
        instance = _accepted()
    else:
        instance = resolve_assembly_authority("authority:not-present")
    dumped = instance.model_dump(mode="json")
    for mode in ("validation", "serialization"):
        schema = model.model_json_schema(mode=mode)
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(schema).validate(dumped)


def test_public_resolver_accepts_only_a_stable_id_and_production_is_closed() -> None:
    assert tuple(inspect.signature(resolve_assembly_authority).parameters) == (
        "authority_id",
    )
    assert isinstance(authority._PRODUCTION_ASSEMBLY_AUTHORITIES, MappingProxyType)
    assert not authority._PRODUCTION_ASSEMBLY_AUTHORITIES

    invalid = resolve_assembly_authority(" authority:invalid ")
    missing = resolve_assembly_authority("authority:not-present")
    assert isinstance(invalid, BlockedAssemblyAuthority)
    assert isinstance(missing, BlockedAssemblyAuthority)
    assert invalid.code is AssemblyAuthorityBlockCode.INVALID_AUTHORITY_ID
    assert missing.code is AssemblyAuthorityBlockCode.AUTHORITY_NOT_FOUND
    with pytest.raises(TypeError):
        authority._PRODUCTION_ASSEMBLY_AUTHORITIES["authority:x"] = _accepted()  # type: ignore[index]


def test_private_catalogue_seam_preserves_exact_receipt_and_refuses_key_drift() -> None:
    accepted = _accepted()
    assert (
        authority._resolve_from_catalogue(
            accepted.authority_id, MappingProxyType({accepted.authority_id: accepted})
        )
        is accepted
    )
    drift = authority._resolve_from_catalogue(
        "authority:catalogue-key",
        MappingProxyType({"authority:catalogue-key": accepted}),
    )
    assert isinstance(drift, BlockedAssemblyAuthority)
    assert drift.code is AssemblyAuthorityBlockCode.IDENTITY_FACT_UNAVAILABLE


def test_schema_version_and_unknown_fields_are_mandatory_and_closed() -> None:
    for field_name in ("schema_id", "contract_version"):
        payload = _accepted_payload()
        del payload[field_name]
        with pytest.raises(ValidationError):
            _validate(payload)

    payload = _accepted_payload()
    payload["achieved_grade"] = "lender_grade"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        _validate(payload)


@pytest.mark.parametrize(
    ("path", "value", "message"),
    (
        (("authority_id",), " authority:d3c-fixture", "stable identifier"),
        (("authority_id",), "authority:d3c-☃", "stable identifier"),
        (
            ("evaluation_request_identity", "request_id"),
            "report:d3c-fixture",
            "cannot be aliased",
        ),
        (("report_identity", "run_id"), "report:d3c-fixture", "must be distinct"),
        (
            ("evaluation_request_identity", "case_id"),
            "case:foreign",
            "does not match",
        ),
        (
            ("allocation_authority", "allocated_at"),
            _AUTHORITY_CREATED,
            "cannot predate its allocation",
        ),
        (
            ("runtime_receipt", "engine_run_created_at"),
            _ALLOCATED,
            "engine run cannot predate",
        ),
        (
            ("runtime_receipt", "captured_at"),
            datetime(2026, 9, 1, tzinfo=_UTC),
            "cannot predate its runtime receipt",
        ),
        (
            ("upstream_digests", "d3b_embedded_project_case"),
            _digest("0"),
            "differs from the exact ProjectCase",
        ),
        (
            ("upstream_digests", "d3b_embedded_evaluation_request"),
            _digest("0"),
            "differs from the exact request",
        ),
        (
            ("runtime_receipt", "captured_at"),
            _ALLOCATED,
            "runtime capture cannot predate",
        ),
        (
            ("runtime_receipt", "source_digest"),
            _digest("0"),
            "differs from its source record",
        ),
        (
            ("actor_records", 0, "kind"),
            "human",
            "must be software or AI",
        ),
        (
            ("jurisdiction_pack_ids",),
            ("pack:wind",),
            "do not equal selected jurisdiction packs",
        ),
        (
            ("technology_pack_ids",),
            ("pack:fic",),
            "do not equal selected technology packs",
        ),
        (
            ("authorized_registry_ids", "capability_ids"),
            ("capability:jurisdiction",),
            "do not equal the exact pack references",
        ),
        (
            ("byte_artifact_bindings", 0, "content_digest"),
            _digest("0"),
            "differs from artifact digest",
        ),
        (
            ("byte_artifact_bindings", 0, "mime_type"),
            "text/plain",
            "differs from artifact mime_type",
        ),
        (
            ("distribution", "control", "artifact_ids"),
            ("artifact:annual_rows", "artifact:debt_result"),
            "cover every and only",
        ),
        (
            ("distribution", "control", "permitted_reliance"),
            "Reliance is permitted.",
            "contradicts the non-reliance hold",
        ),
        (
            ("distribution", "control", "distribution_class"),
            "public",
            "cannot authorize public distribution",
        ),
        (
            ("distribution", "control", "expiry_or_review_date"),
            date(2026, 8, 30),
            "expired at authority creation",
        ),
        (
            ("distribution", "scope_intended_audiences"),
            ("Internal engineering reviewers", "Internal engineering reviewers"),
            "scope intended audiences contain duplicates",
        ),
        (
            ("distribution", "scope_intended_uses"),
            ("D3C plumbing verification", "D3C plumbing verification"),
            "scope intended uses contain duplicates",
        ),
        (
            ("distribution", "scope_intended_audiences"),
            ("Board circulation",),
            "audiences do not equal the held scope",
        ),
        (
            ("distribution", "scope_intended_uses"),
            ("Lender reliance",),
            "uses do not equal the held scope",
        ),
        (
            ("distribution", "control", "artifact_ids"),
            (
                "artifact:annual_rows",
                "artifact:debt_result",
                "artifact:fx_curve",
                "artifact:fx_curve",
            ),
            "artifact_ids contains duplicate identities",
        ),
    ),
)
def test_reciprocal_identity_runtime_pack_artifact_and_hold_guards_fire(
    path: tuple[str | int, ...], value: Any, message: str
) -> None:
    payload = _accepted_payload()
    _set(payload, path, value)
    with pytest.raises(ValidationError, match=message):
        _validate(payload)


@pytest.mark.parametrize(
    ("field_name", "identity_field", "message"),
    (
        ("actor_records", "actor_id", "duplicate actor identity"),
        ("source_records", "source_id", "duplicate source identity"),
        ("pack_bindings", "pack_id", "duplicate pack identity"),
        ("artifact_records", "artifact_id", "duplicate artifact identity"),
    ),
)
def test_duplicate_graph_identities_are_refused(
    field_name: str, identity_field: str, message: str
) -> None:
    payload = _accepted_payload()
    records = list(payload[field_name])
    duplicate = copy.deepcopy(records[0])
    if field_name in {"source_records", "actor_records", "pack_bindings"}:
        records.append(duplicate)
    else:
        records[1][identity_field] = records[0][identity_field]
    payload[field_name] = tuple(records)
    with pytest.raises(ValidationError, match=message):
        _validate(payload)


def test_duplicate_byte_roles_and_artifact_reuse_are_refused() -> None:
    payload = _accepted_payload()
    payload["byte_artifact_bindings"][1]["role"] = "annual_rows"
    with pytest.raises(ValidationError, match="duplicate byte artifact role"):
        _validate(payload)

    payload = _accepted_payload()
    payload["byte_artifact_bindings"][1]["artifact_id"] = "artifact:annual_rows"
    with pytest.raises(ValidationError, match="multiple byte artifact roles"):
        _validate(payload)


@pytest.mark.parametrize(
    ("path", "value", "message"),
    (
        (("allocation_authority", "actor_id"), "actor:missing", "allocation actor"),
        (("allocation_authority", "source_id"), "source:missing", "allocation source"),
        (("orchestration_actor_id",), "actor:missing", "orchestration actor"),
        (("runtime_receipt", "source_id"), "source:missing", "runtime receipt source"),
        (
            ("source_records", 0, "extracting_actor_id"),
            "actor:missing",
            "dangling extracting actor",
        ),
        (
            ("source_records", 0, "supersedes_source_id"),
            "source:missing",
            "dangling supersession",
        ),
        (("pack_bindings", 0, "owner_actor_id"), "actor:missing", "pack .* owner"),
        (("pack_bindings", 0, "source_ids"), ("source:missing",), "dangling source"),
        (
            ("pack_bindings", 0, "compatible_pack_ids"),
            ("pack:missing",),
            "dangling compatible_pack_ids",
        ),
        (
            ("artifact_records", 0, "run_id"),
            "run:foreign",
            "foreign report/run identity",
        ),
        (("artifact_records", 0, "source_ids"), (), "requires source_ids"),
        (
            ("artifact_records", 0, "source_ids"),
            ("source:missing",),
            "dangling source",
        ),
        (
            ("artifact_records", 0, "created_at"),
            _ALLOCATED,
            "outside engine/authority chronology",
        ),
        (
            ("byte_artifact_bindings", 0, "artifact_id"),
            "artifact:missing",
            "dangling artifact",
        ),
    ),
)
def test_dangling_graph_references_are_refused(
    path: tuple[str | int, ...], value: Any, message: str
) -> None:
    payload = _accepted_payload()
    _set(payload, path, value)
    with pytest.raises(ValidationError, match=message):
        _validate(payload)


def test_dirty_runtime_state_requires_exact_diff_digest_and_unique_facts() -> None:
    payload = _accepted_payload()
    payload["runtime_receipt"]["dirty_worktree"] = True
    with pytest.raises(ValidationError, match="describe the same state"):
        _validate(payload)

    payload["runtime_receipt"]["dirty_diff_digest"] = _digest("8")
    accepted = _validate(payload)
    assert accepted.runtime_receipt.dirty_diff_digest is not None

    for field_name in ("environment", "dependency_versions"):
        payload = _accepted_payload()
        payload["runtime_receipt"][field_name] = ("duplicate", "duplicate")
        with pytest.raises(ValidationError, match="must be unique"):
            _validate(payload)


def test_exact_identifiers_text_and_bounded_registry_refusals() -> None:
    payload = _accepted_payload()
    payload["authority_id"] = 7
    with pytest.raises(ValidationError, match="must be an exact string"):
        _validate(payload)

    blocked = {
        "outcome": "blocked",
        "schema_id": ASSEMBLY_AUTHORITY_SCHEMA_ID,
        "contract_version": ASSEMBLY_AUTHORITY_CONTRACT_VERSION,
        "authority_id": "authority:blocked-fixture",
        "code": "identity_fact_unavailable",
        "message": "One exact identity fact is unavailable.",
    }
    for bad_message in (7, "", " padded", "bad\u0000text"):
        candidate = {**blocked, "message": bad_message}
        with pytest.raises(ValidationError, match="bounded text"):
            BlockedAssemblyAuthority.model_validate_json(json.dumps(candidate))

    duplicate_fact = {**blocked, "blocking_fact_ids": ("fact:x", "fact:x")}
    with pytest.raises(ValidationError, match="duplicate"):
        BlockedAssemblyAuthority.model_validate_json(json.dumps(duplicate_fact))

    too_many_facts = {
        **blocked,
        "blocking_fact_ids": tuple(f"fact:{index}" for index in range(257)),
    }
    with pytest.raises(ValidationError, match="bounded record count"):
        BlockedAssemblyAuthority.model_validate_json(json.dumps(too_many_facts))

    payload = _accepted_payload()
    payload["authorized_registry_ids"]["input_ids"] = tuple(
        f"input:{index}" for index in range(257)
    )
    with pytest.raises(ValidationError, match="bounded record count"):
        _validate(payload)

    payload = _accepted_payload()
    payload["authorized_registry_ids"]["capability_ids"] = (
        "capability:jurisdiction",
        "capability:jurisdiction",
    )
    with pytest.raises(ValidationError, match="duplicate identities"):
        _validate(payload)

    payload = _accepted_payload()
    payload["authorized_registry_ids"]["input_ids"] = ("input:x", "input:x")
    with pytest.raises(ValidationError, match="duplicate identities"):
        _validate(payload)


def test_disclosure_bindings_are_reciprocal() -> None:
    disclosure = {
        "artifact_id": "artifact:annual_rows",
        "source_id": "source:runtime",
        "action": "include",
        "reason": "Exact governed source remains attached.",
    }
    payload = _accepted_payload()
    payload["distribution"]["control"]["disclosure_bindings"] = (disclosure,)
    assert _validate(payload).distribution.control.disclosure_bindings

    for field_name, bad_value, message in (
        ("artifact_id", "artifact:missing", "dangling artifact"),
        ("source_id", "source:missing", "dangling source"),
        ("validation_id", "validation:missing", "dangling validation"),
    ):
        payload = _accepted_payload()
        bad_disclosure = {**disclosure, field_name: bad_value}
        payload["distribution"]["control"]["disclosure_bindings"] = (bad_disclosure,)
        with pytest.raises(ValidationError, match=message):
            _validate(payload)


@pytest.mark.parametrize(
    ("record_kind", "field_name", "identity", "message"),
    (
        ("actor", "input_ids", "input:unauthorized", "unauthorized input_ids"),
        ("actor", "review_ids", "review:unauthorized", "unauthorized review_ids"),
        (
            "source",
            "limitation_ids",
            "limitation:unauthorized",
            "unauthorized limitation_ids",
        ),
        (
            "source",
            "review_ids",
            "review:unauthorized",
            "unauthorized review_ids",
        ),
    ),
)
def test_actor_and_source_registry_links_require_pack_authority(
    record_kind: str, field_name: str, identity: str, message: str
) -> None:
    payload = _accepted_payload()
    record_field = "actor_records" if record_kind == "actor" else "source_records"
    payload[record_field][0][field_name] = (identity,)
    with pytest.raises(ValidationError, match=message):
        _validate(payload)


def test_valid_source_supersession_is_retained_in_the_exact_graph() -> None:
    payload = _accepted_payload()
    predecessor = copy.deepcopy(payload["source_records"][0])
    predecessor["source_id"] = "source:runtime-predecessor"
    predecessor["supersedes_source_id"] = None
    payload["source_records"][0]["supersedes_source_id"] = predecessor["source_id"]
    payload["source_records"] += (predecessor,)

    accepted = _validate(payload)
    assert accepted.source_records[0].supersedes_source_id == predecessor["source_id"]


@pytest.mark.parametrize(
    ("path", "value", "message"),
    (
        (
            ("report_identity", "report_id"),
            " report:d3c-fixture ",
            "not an exact stable identifier",
        ),
        (
            ("actor_records", 0, "actor_id"),
            " actor:d3c-orchestrator ",
            "not an exact stable identifier",
        ),
        (
            ("source_records", 0, "source_id"),
            " source:runtime ",
            "not an exact stable identifier",
        ),
        (
            ("pack_bindings", 0, "pack_id"),
            " pack:fic ",
            "not an exact stable identifier",
        ),
        (
            ("artifact_records", 0, "artifact_id"),
            " artifact:annual_rows ",
            "not an exact stable identifier",
        ),
        (
            ("distribution", "control", "distribution_id"),
            " distribution:d3c-fixture ",
            "not an exact stable identifier",
        ),
        (
            ("distribution", "control", "intended_audiences"),
            (" Internal engineering reviewers ",),
            "not exact bounded text",
        ),
    ),
)
def test_nested_d2_wire_aliases_are_refused_before_normalization(
    path: tuple[str | int, ...], value: Any, message: str
) -> None:
    payload = _accepted_payload()
    _set(payload, path, value)
    with pytest.raises(ValidationError, match=message):
        _validate(payload)


def test_duplicate_pack_references_are_refused_before_set_reconciliation() -> None:
    payload = _accepted_payload()
    payload["pack_bindings"][0]["capability_ids"] = (
        "capability:jurisdiction",
        "capability:jurisdiction",
    )
    with pytest.raises(ValidationError, match="contains duplicate identities"):
        _validate(payload)


def test_result_artifacts_cannot_predate_the_engine_run() -> None:
    payload = _accepted_payload()
    early = datetime(2026, 8, 31, 2, 30, tzinfo=_UTC)
    payload["artifact_records"][0]["created_at"] = early
    payload["byte_artifact_bindings"][0]["created_at"] = early
    with pytest.raises(ValidationError, match="outside engine/authority chronology"):
        _validate(payload)


def test_each_technology_axis_has_exactly_one_pack_but_hybrids_remain_valid() -> None:
    payload = _accepted_payload()
    duplicate = _pack(pack_id="pack:wind-duplicate", kind="technology")
    duplicate["capability_ids"] = ("capability:technology-duplicate",)
    payload["pack_bindings"] += (duplicate,)
    payload["technology_pack_ids"] += ("pack:wind-duplicate",)
    payload["authorized_registry_ids"]["capability_ids"] += (
        "capability:technology-duplicate",
    )
    with pytest.raises(ValidationError, match="exactly one D2 pack"):
        _validate(payload)

    payload = _accepted_payload()
    solar = _pack(pack_id="pack:solar", kind="technology")
    solar["technology_ids"] = ("solar_pv",)
    solar["capability_ids"] = ("capability:technology-solar",)
    payload["pack_bindings"] += (solar,)
    payload["technology_pack_ids"] += ("pack:solar",)
    payload["authorized_registry_ids"]["capability_ids"] += (
        "capability:technology-solar",
    )
    accepted = _validate(payload)
    assert {
        pack.technology_ids for pack in accepted.pack_bindings if pack.technology_ids
    } == {
        ("wind",),
        ("solar_pv",),
    }


def test_taxonomy_supersession_and_surplus_circulation_fail_closed() -> None:
    payload = _accepted_payload()
    payload["artifact_records"][0]["supersedes_artifact_id"] = "artifact:historical"
    with pytest.raises(ValidationError, match="supersession is unsupported"):
        _validate(payload)

    payload = _accepted_payload()
    payload["pack_bindings"][0]["section_ids"] = ("unknown_section",)
    with pytest.raises(ValidationError, match="pack .* unknown taxonomy section"):
        _validate(payload)

    payload = _accepted_payload()
    payload["source_records"][0]["section_ids"] = ("unknown_section",)
    with pytest.raises(ValidationError, match="source .* unknown taxonomy section"):
        _validate(payload)

    payload = _accepted_payload()
    payload["distribution"]["control"]["intended_audiences"] += (
        "Board members",
        "Lenders",
    )
    payload["distribution"]["control"]["permitted_uses"] += (
        "Board circulation",
        "Lender circulation",
    )
    with pytest.raises(ValidationError, match="do not equal the held scope"):
        _validate(payload)


def test_raw_d2_guard_bounds_shapes_and_python_mode() -> None:
    accepted = _accepted()
    assert AcceptedAssemblyAuthority.model_validate(accepted.model_dump()) == accepted
    authority._validate_raw_nested_d2_records(
        {"actor_records": (accepted.actor_records[0],)}
    )

    with pytest.raises(ValueError, match="actor_records must be an exact list"):
        authority._validate_raw_nested_d2_records({"actor_records": "not-a-list"})
    with pytest.raises(ValueError, match="nested D2 records"):
        authority._validate_raw_nested_d2_records({"actor_records": (7,)})

    payload = _accepted_payload()
    payload["actor_records"][0]["input_ids"] = "input:not-a-tuple"
    with pytest.raises(ValidationError, match="exact identifier list or tuple"):
        _validate(payload)

    payload = _accepted_payload()
    payload["actor_records"][0]["input_ids"] = tuple(
        f"input:{index}" for index in range(257)
    )
    with pytest.raises(ValidationError, match="bounded record count"):
        _validate(payload)

    payload = _accepted_payload()
    payload["source_records"][0]["quality_checks"] = "not-a-tuple"
    with pytest.raises(ValidationError, match="exact text list or tuple"):
        _validate(payload)

    payload = _accepted_payload()
    payload["source_records"][0]["quality_checks"] = tuple(
        f"quality check {index}" for index in range(257)
    )
    with pytest.raises(ValidationError, match="bounded record count"):
        _validate(payload)

    payload = _accepted_payload()
    payload["source_records"][0]["quality_checks"] = (
        "Duplicate check.",
        "Duplicate check.",
    )
    with pytest.raises(ValidationError, match="duplicate entries"):
        _validate(payload)


def test_raw_d2_guard_nested_pack_and_disclosure_shapes() -> None:
    authority._validate_raw_nested_d2_records(
        {"source_records": ({"source_id": "source:minimal"},)}
    )

    pack = {
        "pack_id": "pack:minimal",
        "input_defaults": (
            {
                "input_id": "input:minimal",
                "source_ids": ("source:minimal",),
                "applicability_predicate": "Exact fixture predicate.",
            },
        ),
        "evidence_minima": (
            {
                "section_id": "appendices_provenance_audit_trail",
                "requirement": "Exact fixture minimum.",
            },
        ),
    }
    authority._validate_raw_nested_d2_records({"pack_bindings": (pack,)})

    invalid_pack = {**pack, "input_defaults": "not-a-sequence"}
    with pytest.raises(ValueError, match="input_defaults must be an exact list"):
        authority._validate_raw_nested_d2_records({"pack_bindings": (invalid_pack,)})

    duplicate_minimum = copy.deepcopy(pack["evidence_minima"][0])
    duplicate_pack = {
        **pack,
        "evidence_minima": (pack["evidence_minima"][0], duplicate_minimum),
    }
    with pytest.raises(ValueError, match="duplicate section_ids"):
        authority._validate_raw_nested_d2_records({"pack_bindings": (duplicate_pack,)})

    authority._validate_raw_nested_d2_records({"distribution": {}})
    disclosure = {
        "artifact_id": "artifact:x",
        "source_id": "source:x",
        "reason": "Exact fixture disclosure.",
    }
    with pytest.raises(ValueError, match="duplicate bindings"):
        authority._validate_raw_nested_d2_records(
            {
                "distribution": {
                    "control": {"disclosure_bindings": (disclosure, disclosure)}
                }
            }
        )


def test_actor_source_sets_are_exact_not_supersets() -> None:
    payload = _accepted_payload()
    extra_actor = copy.deepcopy(payload["actor_records"][0])
    extra_actor["actor_id"] = "actor:unused"
    payload["actor_records"] += (extra_actor,)
    with pytest.raises(ValidationError, match="exactly the referenced actors"):
        _validate(payload)

    payload = _accepted_payload()
    extra_source = copy.deepcopy(payload["source_records"][0])
    extra_source["source_id"] = "source:unused"
    payload["source_records"] += (extra_source,)
    with pytest.raises(ValidationError, match="exactly the referenced sources"):
        _validate(payload)


def test_module_has_no_evaluator_finance_surface_or_package_assembly_import() -> None:
    tree = ast.parse(_MODULE.read_text(encoding="utf-8"))
    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    }
    forbidden_roots = ("analytics.evaluation", "finance", "app", "api")
    assert not any(module.startswith(forbidden_roots) for module in imported_modules)
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    attributes = {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    assert "FeasibilityReportPackage" not in names
    assert "evaluate_with_overrides" not in names | attributes


def test_public_namespace_exports_the_complete_d3c0_surface() -> None:
    for exported_name in authority.__all__:
        assert exported_name in public_contract.__all__
        assert getattr(public_contract, exported_name) is getattr(
            authority, exported_name
        )


def test_blocked_resolution_is_stable_across_hash_seeds() -> None:
    source = (
        "from analytics.feasibility_report_contract.assembly_authority import "
        "resolve_assembly_authority;"
        "print(resolve_assembly_authority('authority:not-present').model_dump_json())"
    )
    outputs = []
    for seed in ("1", "7", "101"):
        completed = subprocess.run(
            [sys.executable, "-c", source],
            check=True,
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "PYTHONHASHSEED": seed,
                "PYTHONPATH": str(_MODULE.parents[2]),
            },
        )
        outputs.append(json.loads(completed.stdout))
    assert outputs[0] == outputs[1] == outputs[2]
