"""Constructive and hostile controls for the held D3C-1b context binding."""

from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import json
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal, cast

import jsonschema  # type: ignore[import-untyped]
import pytest
from pydantic import ValidationError

import analytics.evaluation_v14 as evaluation_v14
import analytics.feasibility_execution as execution
import analytics.feasibility_report_contract.context_binding as context_binding
from analytics.contracts_v14 import (
    AuthoredScenarioPathAuthority,
    D3BExecutionSuccess,
)
from analytics.feasibility_report_contract import (
    AssumptionReference,
    EvaluationRequest,
    ProjectCase,
    resolved_config_sha256,
)
from analytics.feasibility_report_contract.assembly_authority import (
    AcceptedAssemblyAuthority,
    GovernedByteArtifactRole,
)
from analytics.feasibility_report_contract.context_binding import (
    BlockedD3CContextBinding,
    D3CContextBindingCandidate,
    D3CContextBindingError,
    GovernedArtifactPayload,
    _bind_d3c_context_from_catalogue_for_test,
    bind_d3c_context,
    d3b_execution_success_content_digest,
)
from analytics.feasibility_report_contract.result_facade import (
    D3C_SECTION_IDS,
    ResultObservationState,
)
from analytics.feasibility_result_projection import project_d3b_result
from tests.contracts.test_d3b_execution_contract import (
    _AUTHORITY_ID,
    _bundle,
    _gateway_result,
    _install_gateway,
)
from tests.contracts.test_d3c_assembly_authority_contract import _accepted_payload
from tests.contracts.test_project_case_contract import _case_payload

_MODULE = Path(
    cast(
        str,
        __import__(
            "analytics.feasibility_report_contract.context_binding",
            fromlist=["context_binding"],
        ).__file__,
    )
).resolve()
_UTC = timezone.utc
_KNOWN_D3B_SUCCESS_DIGEST = (
    "d6dfe823cec253092ffc88ee588f559cb0f39bce65823e1886969fc56117a048"
)
_FX_RATE_INPUT_ID = (
    "input:project_case.currency_conversion.fx:lkr-to-usd:2026-08-29.rate"
)


@dataclass(frozen=True)
class _ContextFixture:
    project_case: Any
    request: EvaluationRequest
    success: D3BExecutionSuccess
    authority: AcceptedAssemblyAuthority
    payloads: tuple[GovernedArtifactPayload, ...]


def _json_default(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(type(value).__name__)


def _digest(value: str) -> dict[str, str]:
    return {"algorithm": "sha256", "value": value}


def _adapt_request_and_authority(
    bundle: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[EvaluationRequest, AuthoredScenarioPathAuthority]:
    request_payload = json.loads(bundle.request.model_dump_json())
    scope_payload = request_payload["scope"]
    scope_payload["project_boundary"] = "Fictional single-site assessment boundary"
    request_payload["scope"]["intended_audiences"] = [
        {
            "audience_id": "audience:internal-engineering",
            "statement": "Internal engineering reviewers",
        }
    ]
    request_payload["scope"]["intended_uses"] = [
        {
            "use_id": "use:d3c-plumbing-verification",
            "statement": "D3C plumbing verification",
        }
    ]
    request = EvaluationRequest.model_validate_json(json.dumps(request_payload))
    binding = replace(
        bundle.authority.bindings[0],
        evaluation_request_sha256=resolved_config_sha256(
            request.model_dump(mode="json")
        ),
    )
    scenario_authority = replace(bundle.authority, bindings=(binding,))
    monkeypatch.setattr(
        execution,
        "_AUTHORED_SCENARIO_AUTHORITIES",
        MappingProxyType({_AUTHORITY_ID: scenario_authority}),
    )
    return request, scenario_authority


def _d3b_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    gateway: Any | None = None,
) -> tuple[Any, EvaluationRequest, D3BExecutionSuccess]:
    bundle = _bundle(tmp_path, monkeypatch)
    request, _ = _adapt_request_and_authority(bundle, monkeypatch)
    _install_gateway(
        monkeypatch,
        gateway
        or (
            lambda **kwargs: _gateway_result(kwargs["raw_config"], kwargs["overrides"])
        ),
    )
    result = execution.execute_evaluation_request(
        project_case=bundle.project_case,
        request=request,
        scenario_authority_id=_AUTHORITY_ID,
    )
    assert type(result) is D3BExecutionSuccess
    return bundle.project_case, request, result


def _aligned_authority_payload(
    project_case: Any,
    request: EvaluationRequest,
    success: D3BExecutionSuccess,
    payload_bytes: dict[GovernedByteArtifactRole, bytes],
) -> dict[str, Any]:
    payload = _accepted_payload()
    manifest = success.run_manifest
    engine_created = datetime.fromisoformat(
        str(manifest["generated_at"]).replace("Z", "+00:00")
    )
    report_created = engine_created - timedelta(hours=1)
    allocated = report_created - timedelta(hours=1)
    artifact_created = engine_created + timedelta(minutes=15)
    captured = engine_created + timedelta(minutes=30)
    authority_created = engine_created + timedelta(hours=1)

    payload["authority_created_at"] = authority_created
    payload["report_identity"].update(
        {
            "project_id": project_case.identity.project_id,
            "case_id": project_case.identity.case_id,
            "created_at": report_created,
        }
    )
    scope = request.scope
    payload["evaluation_request_identity"] = {
        "request_id": request.request_id,
        "project_id": request.project_case.project_id,
        "case_id": request.project_case.case_id,
        "project_case_revision": request.project_case.revision,
        "d3b_scenario_authority_id": success.authority_id,
        "config_id": request.base_scenario.config_id,
        "scope_id": scope.scope_id,
        "project_boundary": scope.project_boundary,
        "jurisdiction_codes": tuple(
            dict.fromkeys(item.jurisdiction_code for item in scope.jurisdiction_scope)
        ),
        "technology_ids": tuple(
            dict.fromkeys(item.technology_id for item in scope.technology_scope)
        ),
        "project_stage": scope.project_stage,
        "intended_audiences": tuple(
            item.model_dump(mode="json") for item in scope.intended_audiences
        ),
        "intended_uses": tuple(
            item.model_dump(mode="json") for item in scope.intended_uses
        ),
        "evidence_cutoff": scope.evidence_cutoff,
        "valuation_date": scope.valuation_date,
    }
    project_digest = resolved_config_sha256(project_case.model_dump(mode="json"))
    request_digest = resolved_config_sha256(request.model_dump(mode="json"))
    success_digest = d3b_execution_success_content_digest(success).value
    payload["upstream_digests"] = {
        "project_case": _digest(project_digest),
        "evaluation_request": _digest(request_digest),
        "d3b_execution_success": _digest(success_digest),
        "d3b_embedded_project_case": _digest(project_digest),
        "d3b_embedded_evaluation_request": _digest(request_digest),
    }
    payload["allocation_authority"]["allocated_at"] = allocated
    payload["runtime_receipt"].update(
        {
            "engine_version": manifest["engine_version"],
            "code_commit": manifest["git_sha"],
            "engine_run_created_at": engine_created,
            "captured_at": captured,
        }
    )

    boundary = scope.project_boundary
    technology_ids = tuple(
        dict.fromkeys(item.technology_id for item in scope.technology_scope)
    )
    jurisdiction_codes = tuple(
        dict.fromkeys(item.jurisdiction_code for item in scope.jurisdiction_scope)
    )
    runtime_source = payload["source_records"][0]
    runtime_source.update(
        {
            "project_boundary": boundary,
            "jurisdictions": jurisdiction_codes,
            "technology_ids": technology_ids,
            "observation_date": scope.evidence_cutoff,
            "retrieval_date": scope.evidence_cutoff,
        }
    )
    project_source = {
        "source_id": "source:project-basis",
        "title": "Controlled ProjectCase basis fixture",
        "issuer_or_author": "DutchBay contract tests",
        "document_or_dataset_id": "project-case-basis-v1",
        "revision": "1",
        "observation_date": scope.evidence_cutoff,
        "retrieval_date": scope.evidence_cutoff,
        "locator": {
            "evidence_path": "tests/fixtures/project-case-basis.json",
            "pinpoint": "whole controlled fixture",
        },
        "source_class": "authenticated_project",
        "authenticity_status": "verified",
        "authority": "Controlled ProjectCase fixture only.",
        "jurisdictions": jurisdiction_codes,
        "technology_ids": technology_ids,
        "project_boundary": boundary,
        "section_ids": (
            "project_description_and_structure",
            "technology_selection_design_basis",
            "capex_opex_contingency_procurement",
            "tax_fx_inflation_accounting",
        ),
        "period": "2026 controlled fixture",
        "licence_or_publication_rights": "Internal test use only.",
        "publication_permitted": False,
        "access_restrictions": "Internal verification only.",
        "confidentiality": "internal",
        "extraction_method": "Deterministic fixture construction.",
        "extracting_actor_id": "actor:d3c-orchestrator",
        "quality_checks": ("Exact ProjectCase source identity checked.",),
    }
    payload["source_records"] = (runtime_source, project_source)
    for pack in payload["pack_bindings"]:
        pack["project_stages"] = (scope.project_stage,)
        pack["effective_date"] = scope.evidence_cutoff
        pack["review_date"] = scope.evidence_cutoff
        if pack["kind"] == "technology":
            pack["source_ids"] = ("source:project-basis",)

    role_order = tuple(GovernedByteArtifactRole)
    artifact_by_role = {
        artifact["artifact_id"].removeprefix("artifact:"): artifact
        for artifact in payload["artifact_records"]
    }
    binding_by_role = {
        binding["role"]: binding for binding in payload["byte_artifact_bindings"]
    }
    for role in role_order:
        content = payload_bytes[role]
        digest = hashlib.sha256(content).hexdigest()
        artifact = artifact_by_role[role.value]
        binding = binding_by_role[role.value]
        artifact.update(
            {
                "created_at": artifact_created,
                "content_digest": _digest(digest),
            }
        )
        binding.update(
            {
                "byte_length": len(content),
                "created_at": artifact_created,
                "content_digest": _digest(digest),
            }
        )
    return payload


def _validate_authority(payload: dict[str, Any]) -> AcceptedAssemblyAuthority:
    return AcceptedAssemblyAuthority.model_validate_json(
        json.dumps(payload, default=_json_default)
    )


def _fixture_for_success(
    project_case: Any,
    request: EvaluationRequest,
    success: D3BExecutionSuccess,
    *,
    payload_bytes: dict[GovernedByteArtifactRole, bytes] | None = None,
) -> _ContextFixture:
    selected_bytes = payload_bytes or {
        GovernedByteArtifactRole.ANNUAL_ROWS: b'[{"year":1}]',
        GovernedByteArtifactRole.DEBT_RESULT: b'{"debt_total":100}',
        GovernedByteArtifactRole.FX_CURVE: b'[{"fx_rate":300}]',
    }
    authority = _validate_authority(
        _aligned_authority_payload(project_case, request, success, selected_bytes)
    )
    payloads = tuple(
        GovernedArtifactPayload(role=role, content=selected_bytes[role])
        for role in GovernedByteArtifactRole
    )
    return _ContextFixture(project_case, request, success, authority, payloads)


def _directed_fx_project_case() -> ProjectCase:
    payload = _case_payload()
    costs = payload["costs"]
    costs["reporting_currency"] = "LKR"
    basis = costs["price_bases"][0]
    basis["reporting_currency"] = "LKR"
    basis["price_level"] = "Controlled LKR valuation basis"
    conversion = costs["currency_conversions"][0]
    conversion.update(
        {
            "conversion_id": "fx:usd-to-lkr:2026-08-29",
            "from_currency": "USD",
            "to_currency": "LKR",
            "rate": {
                "state": "resolved",
                "value": "300",
                "unit": "LKR/USD",
                "bindings": [
                    {"kind": "source", "reference_id": "source:project-basis"}
                ],
            },
            "quote_precision": 2,
        }
    )
    capex_amount = costs["lines"][0]["amount"]
    capex_amount.update(
        {
            "reporting_amount": {
                "state": "resolved",
                "value": "3000000000",
                "unit": "LKR",
                "bindings": [
                    {"kind": "source", "reference_id": "source:project-basis"}
                ],
            },
            "reporting_currency": "LKR",
            "conversion_id": "fx:usd-to-lkr:2026-08-29",
        }
    )
    opex_amount = costs["lines"][1]["amount"]
    opex_amount.update(
        {
            "reporting_amount": copy.deepcopy(opex_amount["native_amount"]),
            "reporting_currency": "LKR",
            "reporting_minor_unit_places": opex_amount["native_minor_unit_places"],
            "conversion_id": None,
        }
    )
    return ProjectCase.model_validate_json(json.dumps(payload))


@pytest.fixture
def context_fixture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> _ContextFixture:
    project_case, request, success = _d3b_success(tmp_path, monkeypatch)
    return _fixture_for_success(project_case, request, success)


def _bind(
    fixture: _ContextFixture,
    *,
    success: D3BExecutionSuccess | None = None,
    authority: AcceptedAssemblyAuthority | None = None,
    payloads: tuple[GovernedArtifactPayload, ...] | None = None,
    projection: Any = None,
) -> Any:
    selected_authority = authority or fixture.authority
    return _bind_d3c_context_from_catalogue_for_test(
        project_case=fixture.project_case,
        request=fixture.request,
        success=success or fixture.success,
        projection=projection,
        authority_id=selected_authority.authority_id,
        artifact_payloads=payloads or fixture.payloads,
        authority_catalogue=MappingProxyType(
            {selected_authority.authority_id: selected_authority}
        ),
    )


def _thaw(value: Any, memo: dict[int, Any] | None = None) -> Any:
    copies = memo if memo is not None else {}
    if isinstance(value, MappingProxyType):
        marker = id(value)
        if marker in copies:
            return copies[marker]
        result: dict[Any, Any] = {}
        copies[marker] = result
        result.update({key: _thaw(item, copies) for key, item in value.items()})
        return result
    if type(value) is tuple:
        marker = id(value)
        if marker in copies:
            return copies[marker]
        placeholder: list[Any] = []
        copies[marker] = placeholder
        placeholder.extend(_thaw(item, copies) for item in value)
        result_tuple = tuple(placeholder)
        copies[marker] = result_tuple
        return result_tuple
    return value


def _freeze(value: Any, memo: dict[int, Any] | None = None) -> Any:
    copies = memo if memo is not None else {}
    if type(value) is dict:
        marker = id(value)
        if marker in copies:
            return copies[marker]
        backing: dict[Any, Any] = {}
        proxy = MappingProxyType(backing)
        copies[marker] = proxy
        backing.update({key: _freeze(item, copies) for key, item in value.items()})
        return proxy
    if type(value) in {list, tuple}:
        marker = id(value)
        if marker in copies:
            return copies[marker]
        result = tuple(_freeze(item, copies) for item in value)
        copies[marker] = result
        return result
    return value


def _mutated_success(
    success: D3BExecutionSuccess,
    mutation: Any,
) -> D3BExecutionSuccess:
    root = _thaw(success.full_result)
    mutation(root)
    scenario = root["scenario_result"]
    scenario["annual_rows"] = root["annual_rows"]
    scenario["debt_result"] = root["debt_result"]
    scenario["kpis"] = root["kpis"]
    frozen = _freeze(root)
    return replace(success, full_result=frozen, run_manifest=frozen["run_manifest"])


def test_constructive_binding_is_candidate_only_and_round_trips(
    context_fixture: _ContextFixture,
) -> None:
    candidate = _bind(context_fixture)

    assert type(candidate) is D3CContextBindingCandidate
    assert candidate.outcome == "candidate"
    assert candidate.authority_status == "candidate_non_authoritative"
    assert candidate.completeness_status == "unresolved"
    assert candidate.evidence_status == "unresolved"
    assert candidate.review_status == "not_performed"
    assert candidate.professional_act_status == "not_performed"
    assert candidate.achieved_grade == "ungraded"
    assert candidate.release_status == "hold"
    assert candidate.reliance_status == "not_permitted"
    assert candidate.publication_status == "not_authorized"
    assert (
        tuple(section.section_id for section in candidate.sections) == D3C_SECTION_IDS
    )
    assert all(
        section.completeness_status == "unresolved" for section in candidate.sections
    )
    assert all(section.release_status == "hold" for section in candidate.sections)
    assert {receipt.role for receipt in candidate.verified_artifact_payloads} == set(
        GovernedByteArtifactRole
    )
    assert candidate.d3b_execution_success_content_digest.value == (
        _KNOWN_D3B_SUCCESS_DIGEST
    )
    assert not any(
        output.output_id.startswith("output:debt_result.fx_")
        for output in candidate.output_references
    )
    round_trip = D3CContextBindingCandidate.model_validate_json(
        candidate.model_dump_json()
    )
    assert round_trip == candidate
    assert round_trip.canonical_json_bytes() == candidate.canonical_json_bytes()


@pytest.mark.parametrize(
    "mode",
    ("validation", "serialization"),
)
def test_candidate_schema_is_valid_draft_2020_12(
    context_fixture: _ContextFixture,
    mode: Literal["validation", "serialization"],
) -> None:
    candidate = _bind(context_fixture)
    schema = D3CContextBindingCandidate.model_json_schema(mode=mode)
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema).validate(candidate.model_dump(mode="json"))


def test_public_selection_is_closed_and_has_no_receipt_injection(
    context_fixture: _ContextFixture,
) -> None:
    assert tuple(inspect.signature(bind_d3c_context).parameters) == (
        "project_case",
        "request",
        "success",
        "projection",
        "authority_id",
        "artifact_payloads",
    )
    result = bind_d3c_context(
        project_case=context_fixture.project_case,
        request=context_fixture.request,
        success=context_fixture.success,
        projection=None,
        authority_id=context_fixture.authority.authority_id,
        artifact_payloads=context_fixture.payloads,
    )
    assert type(result) is BlockedD3CContextBinding
    assert result.code.value == "authority_not_found"
    assert result.candidate_emitted is False
    assert (
        BlockedD3CContextBinding.model_validate_json(result.model_dump_json()) == result
    )
    for mode in ("validation", "serialization"):
        schema = BlockedD3CContextBinding.model_json_schema(mode=mode)
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(schema).validate(result.model_dump(mode="json"))

    blocked = _bind_d3c_context_from_catalogue_for_test(
        project_case=context_fixture.project_case,
        request=context_fixture.request,
        success=context_fixture.success,
        projection=None,
        authority_id="authority:not-present",
        artifact_payloads=context_fixture.payloads,
        authority_catalogue=MappingProxyType({}),
    )
    assert type(blocked) is BlockedD3CContextBinding
    with pytest.raises(D3CContextBindingError) as caught:
        _bind_d3c_context_from_catalogue_for_test(
            project_case=context_fixture.project_case,
            request=context_fixture.request,
            success=context_fixture.success,
            projection=None,
            authority_id="authority:not-present",
            artifact_payloads=context_fixture.payloads,
            authority_catalogue=cast(Any, {}),
        )
    assert caught.value.code == "test_catalogue_not_immutable"


def test_binding_input_types_and_fresh_projection_failure_are_bounded(
    context_fixture: _ContextFixture,
) -> None:
    common = {
        "project_case": context_fixture.project_case,
        "request": context_fixture.request,
        "success": context_fixture.success,
        "projection": None,
        "authority": context_fixture.authority,
        "artifact_payloads": context_fixture.payloads,
    }
    for field_name, error_code in (
        ("project_case", "invalid_project_case_type"),
        ("request", "invalid_evaluation_request_type"),
        ("success", "invalid_success_type"),
        ("authority", "invalid_selected_authority_type"),
    ):
        inputs = dict(common)
        inputs[field_name] = object()
        with pytest.raises(D3CContextBindingError) as caught:
            context_binding._bind_selected_authority(**inputs)
        assert caught.value.code == error_code

    with pytest.raises(D3CContextBindingError) as caught:
        context_binding._bind_selected_authority(
            **{**common, "projection": cast(Any, "not-a-projection")}
        )
    assert caught.value.code == "invalid_projection_type"

    damaged = copy.copy(context_fixture.success)
    invalid_root = MappingProxyType({"run_manifest": MappingProxyType({})})
    object.__setattr__(damaged, "full_result", invalid_root)
    object.__setattr__(damaged, "run_manifest", invalid_root["run_manifest"])
    with pytest.raises(D3CContextBindingError) as caught:
        context_binding._bind_selected_authority(**{**common, "success": damaged})
    assert caught.value.code == "fresh_projection_failed"


def test_public_future_code_selected_acceptance_path_has_no_injection_parameter(
    context_fixture: _ContextFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected_ids: list[str] = []

    def code_owned_resolver(authority_id: str) -> AcceptedAssemblyAuthority:
        selected_ids.append(authority_id)
        return context_fixture.authority

    monkeypatch.setattr(
        context_binding,
        "resolve_assembly_authority",
        code_owned_resolver,
    )
    result = bind_d3c_context(
        project_case=context_fixture.project_case,
        request=context_fixture.request,
        success=context_fixture.success,
        projection=None,
        authority_id=context_fixture.authority.authority_id,
        artifact_payloads=context_fixture.payloads,
    )
    assert type(result) is D3CContextBindingCandidate
    assert selected_ids == [context_fixture.authority.authority_id]


def test_reciprocal_request_case_and_authority_digests_are_independent_guards(
    context_fixture: _ContextFixture,
) -> None:
    foreign_success = replace(
        context_fixture.success,
        request_id="request:foreign",
    )
    with pytest.raises(D3CContextBindingError) as caught:
        _bind(context_fixture, success=foreign_success)
    assert caught.value.code == "success_request_identity_mismatch"

    payload = _aligned_authority_payload(
        context_fixture.project_case,
        context_fixture.request,
        context_fixture.success,
        {item.role: item.content for item in context_fixture.payloads},
    )
    payload["upstream_digests"]["project_case"] = _digest("0" * 64)
    payload["upstream_digests"]["d3b_embedded_project_case"] = _digest("0" * 64)
    digest_drift = _validate_authority(payload)
    with pytest.raises(D3CContextBindingError) as caught:
        _bind(context_fixture, authority=digest_drift)
    assert caught.value.code == "authority_upstream_digest_mismatch"

    payload = _aligned_authority_payload(
        context_fixture.project_case,
        context_fixture.request,
        context_fixture.success,
        {item.role: item.content for item in context_fixture.payloads},
    )
    payload["report_identity"]["project_id"] = "project:foreign"
    payload["report_identity"]["case_id"] = "case:foreign"
    payload["evaluation_request_identity"]["project_id"] = "project:foreign"
    payload["evaluation_request_identity"]["case_id"] = "case:foreign"
    foreign_authority = _validate_authority(payload)
    with pytest.raises(D3CContextBindingError) as caught:
        _bind(context_fixture, authority=foreign_authority)
    assert caught.value.code == "authority_request_identity_mismatch"


def test_actual_artifact_bytes_are_required_before_candidate_emission(
    context_fixture: _ContextFixture,
) -> None:
    tampered = list(context_fixture.payloads)
    original = tampered[0]
    tampered[0] = GovernedArtifactPayload(
        role=original.role,
        content=original.content[:-1] + b"X",
    )
    with pytest.raises(D3CContextBindingError) as caught:
        _bind(context_fixture, payloads=tuple(tampered))
    assert caught.value.code == "artifact_digest_mismatch"
    assert caught.value.pointer.endswith("/annual_rows")

    shortened = list(context_fixture.payloads)
    shortened[0] = GovernedArtifactPayload(
        role=shortened[0].role,
        content=shortened[0].content[:-1],
    )
    with pytest.raises(D3CContextBindingError) as caught:
        _bind(context_fixture, payloads=tuple(shortened))
    assert caught.value.code == "artifact_byte_length_mismatch"

    with pytest.raises(D3CContextBindingError) as caught:
        _bind(context_fixture, payloads=cast(Any, list(context_fixture.payloads)))
    assert caught.value.code == "invalid_artifact_payload_set"
    duplicated = (
        context_fixture.payloads[0],
        context_fixture.payloads[0],
        context_fixture.payloads[2],
    )
    with pytest.raises(D3CContextBindingError) as caught:
        _bind(context_fixture, payloads=duplicated)
    assert caught.value.code == "artifact_role_set_mismatch"


def test_assumption_origin_edges_are_preserved_without_minting_d2_assumptions() -> None:
    binding = AssumptionReference(reference_id="assumption:controlled")
    source_ids, origins = context_binding._origin_edges(
        "input:controlled",
        (binding,),
        case_source_ids=set(),
        case_assumption_ids={"assumption:controlled"},
        authority_source_ids=set(),
    )
    assert source_ids == ()
    assert origins[0].kind == "assumption"
    assert origins[0].reference_id == "assumption:controlled"

    with pytest.raises(D3CContextBindingError) as caught:
        context_binding._origin_edges(
            "input:controlled",
            (binding,),
            case_source_ids=set(),
            case_assumption_ids=set(),
            authority_source_ids=set(),
        )
    assert caught.value.code == "input_assumption_not_found"


@pytest.mark.parametrize(
    ("missing_field", "absent_input_id"),
    (
        (
            "native",
            "input:project_case.cost.cost:capex:plant.native_amount",
        ),
        (
            "reporting",
            "input:project_case.cost.cost:capex:plant.reporting_amount",
        ),
        ("conversion", _FX_RATE_INPUT_ID),
    ),
)
def test_candidate_input_table_skips_explicit_missing_values(
    context_fixture: _ContextFixture,
    missing_field: str,
    absent_input_id: str,
) -> None:
    payload = _case_payload()
    if missing_field in {"native", "reporting"}:
        line = payload["costs"]["lines"][0]
        line["quantity"] = {
            "state": "resolved",
            "value": "1",
            "unit": "item",
            "bindings": [{"kind": "source", "reference_id": "source:project-basis"}],
        }
        line["unit_rate_native"] = {
            "state": "resolved",
            "value": "2.00",
            "unit": "USD/item",
            "bindings": [{"kind": "source", "reference_id": "source:project-basis"}],
        }
        line["amount"]["native_amount"] = {
            "state": "resolved",
            "value": "2.00",
            "unit": "USD",
            "bindings": [{"kind": "source", "reference_id": "source:project-basis"}],
        }
        line["amount"]["reporting_amount"] = copy.deepcopy(
            line["amount"]["native_amount"]
        )
        selected = f"missing:capex-{missing_field}"
        line["amount"][f"{missing_field}_amount"] = {
            "state": "missing",
            "unit": "USD",
            "missing_input_id": selected,
        }
        field_path = f"/costs/lines/0/amount/{missing_field}_amount"
        expected_unit = "USD"
    else:
        selected = "missing:fx-rate"
        payload["costs"]["currency_conversions"][0]["rate"] = {
            "state": "missing",
            "unit": "USD/LKR",
            "missing_input_id": selected,
        }
        field_path = "/costs/currency_conversions/0/rate"
        expected_unit = "USD/LKR"
    payload["costs"]["reconciliation_status"] = "incomplete_missing_input"
    payload["missing_inputs"] = [
        {
            "missing_input_id": selected,
            "field_path": field_path,
            "expected_unit": expected_unit,
            "reason": "Controlled missing-value branch fixture.",
            "consequence": "The candidate value is unavailable.",
            "remedy": "Supply one governed source-bound value.",
        }
    ]
    project_case = ProjectCase.model_validate_json(json.dumps(payload))
    records, _ = context_binding._candidate_inputs(
        project_case,
        context_fixture.authority,
    )
    assert absent_input_id not in {record.input_id for record in records}
    has_non_generation = any(
        asset.kind != "generation" for asset in project_case.assets
    )
    assert has_non_generation, "fixture must exercise non-generation asset branches"


def test_supplied_projection_must_be_graph_identical(
    context_fixture: _ContextFixture,
) -> None:
    projection = project_d3b_result(context_fixture.success).model_copy(
        update={"request_id": "request:foreign"}
    )
    with pytest.raises(D3CContextBindingError) as caught:
        _bind(context_fixture, projection=projection)
    assert caught.value.code == "projection_graph_mismatch"


def test_equal_projection_does_not_hide_different_opaque_metadata(
    context_fixture: _ContextFixture,
) -> None:
    altered = _mutated_success(
        context_fixture.success,
        lambda root: root["scenario_result"]["metadata"].update(
            {"opaque_counterexample": "different"}
        ),
    )
    assert project_d3b_result(altered) == project_d3b_result(context_fixture.success)
    assert d3b_execution_success_content_digest(altered) != (
        d3b_execution_success_content_digest(context_fixture.success)
    )
    with pytest.raises(D3CContextBindingError) as caught:
        _bind(
            context_fixture,
            success=altered,
            projection=project_d3b_result(context_fixture.success),
        )
    assert caught.value.code == "authority_upstream_digest_mismatch"


def test_equal_projection_does_not_hide_different_annual_fx_rate(
    context_fixture: _ContextFixture,
) -> None:
    first = _mutated_success(
        context_fixture.success,
        lambda root: root["annual_rows"][0].update({"fx_rate": 300.0}),
    )
    second = _mutated_success(
        context_fixture.success,
        lambda root: root["annual_rows"][0].update({"fx_rate": 301.0}),
    )
    assert project_d3b_result(first) == project_d3b_result(second)
    assert d3b_execution_success_content_digest(first) != (
        d3b_execution_success_content_digest(second)
    )
    authority_payload = _aligned_authority_payload(
        context_fixture.project_case,
        context_fixture.request,
        first,
        {payload.role: payload.content for payload in context_fixture.payloads},
    )
    first_authority = _validate_authority(authority_payload)
    with pytest.raises(D3CContextBindingError) as caught:
        _bind(context_fixture, success=second, authority=first_authority)
    assert caught.value.code == "authority_upstream_digest_mismatch"


def test_present_fx_statistics_refuse_reversed_project_case_conversion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def gateway(**kwargs: Any) -> dict[str, Any]:
        result = _gateway_result(kwargs["raw_config"], kwargs["overrides"])
        result["annual_rows"][0]["fx_rate"] = 300.0
        result["debt_result"].update(
            {"fx_min": 299.0, "fx_max": 301.0, "fx_avg": 300.0}
        )
        return result

    project_case, request, success = _d3b_success(
        tmp_path, monkeypatch, gateway=gateway
    )
    payload_bytes = {
        GovernedByteArtifactRole.ANNUAL_ROWS: b"annual",
        GovernedByteArtifactRole.DEBT_RESULT: b"debt",
        GovernedByteArtifactRole.FX_CURVE: b"fx",
    }
    authority = _validate_authority(
        _aligned_authority_payload(project_case, request, success, payload_bytes)
    )
    fixture = _ContextFixture(
        project_case,
        request,
        success,
        authority,
        tuple(
            GovernedArtifactPayload(role=role, content=payload_bytes[role])
            for role in GovernedByteArtifactRole
        ),
    )
    assert project_case.costs.currency_conversions[0].from_currency == "LKR"
    assert project_case.costs.currency_conversions[0].to_currency == "USD"
    with pytest.raises(D3CContextBindingError) as caught:
        _bind(fixture)
    assert caught.value.code == "fx_directional_conversion_missing"


def test_directed_fx_context_has_positive_and_hostile_predicate_oracles(
    context_fixture: _ContextFixture,
) -> None:
    directed_case = _directed_fx_project_case()
    conversion = directed_case.costs.currency_conversions[0]
    scope = context_fixture.request.scope.model_copy(
        update={
            "valuation_date": conversion.valuation_date,
            "price_basis_id": conversion.price_basis_id,
        }
    )
    directed_request = context_fixture.request.model_copy(update={"scope": scope})

    success = _mutated_success(
        context_fixture.success,
        lambda root: (
            root["annual_rows"][0].update({"fx_rate": 300.0}),
            root["debt_result"].update(
                {"fx_min": 299.0, "fx_max": 301.0, "fx_avg": 300.0}
            ),
        ),
    )
    projection = project_d3b_result(success)
    outputs = context_binding._contextual_fx_outputs(
        directed_case,
        directed_request,
        success,
        projection,
        context_fixture.authority,
        context_fixture.authority.report_identity,
    )
    assert tuple(output.output_id for output in outputs) == (
        "output:debt_result.fx_min",
        "output:debt_result.fx_max",
        "output:debt_result.fx_avg",
    )
    assert tuple(
        output.value.unit for output in outputs if output.value is not None
    ) == (
        "LKR/USD",
        "LKR/USD",
        "LKR/USD",
    )

    incomplete = _mutated_success(
        context_fixture.success,
        lambda root: root["debt_result"].update({"fx_min": 299.0}),
    )
    with pytest.raises(D3CContextBindingError) as caught:
        context_binding._contextual_fx_outputs(
            directed_case,
            directed_request,
            incomplete,
            project_d3b_result(incomplete),
            context_fixture.authority,
            context_fixture.authority.report_identity,
        )
    assert caught.value.code == "fx_statistics_incomplete"

    missing_annual = _mutated_success(
        context_fixture.success,
        lambda root: root["debt_result"].update(
            {"fx_min": 299.0, "fx_max": 301.0, "fx_avg": 300.0}
        ),
    )
    with pytest.raises(D3CContextBindingError) as caught:
        context_binding._contextual_fx_outputs(
            directed_case,
            directed_request,
            missing_annual,
            project_d3b_result(missing_annual),
            context_fixture.authority,
            context_fixture.authority.report_identity,
        )
    assert caught.value.code == "annual_fx_predicate_unmet"

    damaged = copy.copy(context_fixture.success)
    object.__setattr__(
        damaged,
        "full_result",
        MappingProxyType({"debt_result": ()}),
    )
    assert (
        context_binding._contextual_fx_outputs(
            directed_case,
            directed_request,
            damaged,
            project_d3b_result(context_fixture.success),
            context_fixture.authority,
            context_fixture.authority.report_identity,
        )
        == []
    )


def test_directed_fx_context_refuses_quote_basis_source_and_statistic_drift(
    context_fixture: _ContextFixture,
) -> None:
    directed_case = _directed_fx_project_case()
    conversion = directed_case.costs.currency_conversions[0]
    scope = context_fixture.request.scope.model_copy(
        update={
            "valuation_date": conversion.valuation_date,
            "price_basis_id": conversion.price_basis_id,
        }
    )
    directed_request = context_fixture.request.model_copy(update={"scope": scope})

    def replace_conversion(updated: Any) -> ProjectCase:
        return directed_case.model_copy(
            update={
                "costs": directed_case.costs.model_copy(
                    update={"currency_conversions": (updated,)}
                )
            }
        )

    wrong_unit = conversion.model_copy(
        update={"rate": conversion.rate.model_copy(update={"unit": "USD/LKR"})}
    )
    with pytest.raises(D3CContextBindingError) as caught:
        context_binding._fx_conversion_context(
            replace_conversion(wrong_unit),
            directed_request,
            context_fixture.authority,
        )
    assert caught.value.code == "fx_quote_direction_mismatch"

    wrong_basis_request = directed_request.model_copy(
        update={
            "scope": scope.model_copy(update={"price_basis_id": "price-basis:foreign"})
        }
    )
    with pytest.raises(D3CContextBindingError) as caught:
        context_binding._fx_conversion_context(
            directed_case,
            wrong_basis_request,
            context_fixture.authority,
        )
    assert caught.value.code == "fx_basis_mismatch"

    assumption_rate = conversion.rate.model_copy(
        update={"bindings": (AssumptionReference(reference_id="assumption:fx"),)}
    )
    with pytest.raises(D3CContextBindingError) as caught:
        context_binding._fx_conversion_context(
            replace_conversion(conversion.model_copy(update={"rate": assumption_rate})),
            directed_request,
            context_fixture.authority,
        )
    assert caught.value.code == "fx_source_binding_missing"

    missing_source = conversion.rate.model_copy(
        update={
            "bindings": (
                conversion.rate.bindings[0].model_copy(
                    update={"reference_id": "source:foreign"}
                ),
            )
        }
    )
    with pytest.raises(D3CContextBindingError) as caught:
        context_binding._fx_conversion_context(
            replace_conversion(conversion.model_copy(update={"rate": missing_source})),
            directed_request,
            context_fixture.authority,
        )
    assert caught.value.code == "fx_source_not_authorized"

    wrong_stat = _mutated_success(
        context_fixture.success,
        lambda root: (
            root["annual_rows"][0].update({"fx_rate": 300.0}),
            root["debt_result"].update(
                {"fx_min": 299, "fx_max": 301.0, "fx_avg": 300.0}
            ),
        ),
    )
    with pytest.raises(D3CContextBindingError) as caught:
        context_binding._contextual_fx_outputs(
            directed_case,
            directed_request,
            wrong_stat,
            project_d3b_result(wrong_stat),
            context_fixture.authority,
            context_fixture.authority.report_identity,
        )
    assert caught.value.code == "fx_statistic_not_binary64"


def test_degraded_warnings_unknown_keys_none_and_limitations_survive_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def gateway(**kwargs: Any) -> dict[str, Any]:
        result = _gateway_result(
            kwargs["raw_config"], kwargs["overrides"], degraded=True
        )
        result["kpis"]["unreviewed_metric"] = 42.0
        return result

    project_case, request, success = _d3b_success(
        tmp_path, monkeypatch, gateway=gateway
    )
    fixture = _fixture_for_success(project_case, request, success)
    candidate = _bind(fixture)

    assert type(candidate) is D3CContextBindingCandidate
    assert candidate.projection.source_outcome == "degraded_success"
    assert candidate.projection.fx_degraded is True
    assert candidate.projection.returned_warnings
    assert candidate.projection.fx_integration.warning == "bounded warning"
    assert candidate.projection.limitations
    assert any(
        item.key_identity == "unreviewed_metric"
        for item in candidate.projection.unrecognized_keys
    )
    assert any(
        item.state is ResultObservationState.NOT_COMPUTED
        or item.state is ResultObservationState.UPSTREAM_NONE
        for item in candidate.projection.route_observations
    )
    assert candidate.release_status == "hold"


def test_runtime_and_origin_mismatches_fail_before_candidate(
    context_fixture: _ContextFixture,
) -> None:
    payload = _aligned_authority_payload(
        context_fixture.project_case,
        context_fixture.request,
        context_fixture.success,
        {item.role: item.content for item in context_fixture.payloads},
    )
    payload["runtime_receipt"]["engine_version"] = "15.4.1"
    authority = _validate_authority(payload)
    with pytest.raises(D3CContextBindingError) as caught:
        _bind(context_fixture, authority=authority)
    assert caught.value.code == "runtime_manifest_mismatch"


def test_no_locator_io_gateway_or_finance_rerun(
    context_fixture: _ContextFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("forbidden execution or I/O")

    source = _MODULE.read_text()
    monkeypatch.setattr(evaluation_v14, "evaluate_with_overrides", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    monkeypatch.setattr(Path, "read_text", forbidden)
    candidate = _bind(context_fixture)
    assert type(candidate) is D3CContextBindingCandidate

    tree = ast.parse(source)
    forbidden_roots = {"finance", "app", "api", "pathlib", "os", "subprocess"}
    imports = {
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    imports.update(
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    assert imports.isdisjoint(forbidden_roots)


def test_duplicate_json_keys_and_non_finite_tokens_are_rejected(
    context_fixture: _ContextFixture,
) -> None:
    candidate = _bind(context_fixture)
    rendered = candidate.model_dump_json()
    duplicate = rendered.replace(
        '"outcome":"candidate",',
        '"outcome":"candidate","outcome":"candidate",',
        1,
    )
    with pytest.raises(D3CContextBindingError) as caught:
        D3CContextBindingCandidate.model_validate_json(duplicate)
    assert caught.value.code == "duplicate_json_key"

    with pytest.raises(D3CContextBindingError) as caught:
        D3CContextBindingCandidate.model_validate_json('{"value":NaN}')
    assert caught.value.code == "non_finite_json_number"


def test_json_ingress_type_encoding_unicode_depth_and_volume_guards(
    context_fixture: _ContextFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _bind(context_fixture)
    rendered = candidate.model_dump_json().encode("utf-8")
    assert D3CContextBindingCandidate.model_validate_json(rendered) == candidate
    assert (
        D3CContextBindingCandidate.model_validate_json(bytearray(rendered)) == candidate
    )

    for invalid in (b"\xff", bytearray(b"\xff")):
        with pytest.raises(D3CContextBindingError) as caught:
            D3CContextBindingCandidate.model_validate_json(invalid)
        assert caught.value.code == "invalid_json_encoding"
    with pytest.raises(D3CContextBindingError) as caught:
        D3CContextBindingCandidate.model_validate_json(cast(Any, 42))
    assert caught.value.code == "invalid_json_type"
    with pytest.raises(D3CContextBindingError) as caught:
        D3CContextBindingCandidate.model_validate_json("{")
    assert caught.value.code == "invalid_json"
    with pytest.raises(D3CContextBindingError) as caught:
        D3CContextBindingCandidate.model_validate_json('{"x":"\\ud800"}')
    assert caught.value.code == "invalid_unicode_scalar"

    monkeypatch.setattr(context_binding, "_MAX_IDENTITY_DEPTH", 0)
    with pytest.raises(D3CContextBindingError) as caught:
        D3CContextBindingCandidate.model_validate_json('{"x":{"y":1}}')
    assert caught.value.code == "json_ingress_depth_exceeded"
    monkeypatch.setattr(context_binding, "_MAX_IDENTITY_DEPTH", 132)
    monkeypatch.setattr(context_binding, "_MAX_IDENTITY_SCALARS", 0)
    with pytest.raises(D3CContextBindingError) as caught:
        D3CContextBindingCandidate.model_validate_json('{"x":1}')
    assert caught.value.code == "json_ingress_out_of_bounds"


@pytest.mark.parametrize(
    ("args", "message"),
    (
        (("INVALID", "/", "detail"), "error code"),
        (("valid", "", "detail"), "error pointer"),
        (("valid", "/", ""), "error detail"),
    ),
)
def test_error_receipt_constructor_is_bounded(
    args: tuple[str, str, str],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        D3CContextBindingError(*args)


def test_payload_and_section_candidate_ingress_are_exact(
    context_fixture: _ContextFixture,
) -> None:
    with pytest.raises(D3CContextBindingError) as caught:
        GovernedArtifactPayload(
            role=cast(Any, "annual_rows"),
            content=b"payload",
        )
    assert caught.value.code == "invalid_artifact_role"
    with pytest.raises(D3CContextBindingError) as caught:
        GovernedArtifactPayload(
            role=GovernedByteArtifactRole.ANNUAL_ROWS,
            content=cast(Any, bytearray(b"payload")),
        )
    assert caught.value.code == "invalid_artifact_payload"

    section = _bind(context_fixture).sections[0]
    payload = section.model_dump(mode="python")
    payload["candidate_input_ids"] = ("input:duplicate", "input:duplicate")
    with pytest.raises(ValidationError, match="duplicate identities"):
        type(section).model_validate(payload)


def test_content_identity_is_order_and_alias_independent_but_type_exact(
    context_fixture: _ContextFixture,
) -> None:
    original = context_fixture.success
    thawed = _thaw(original.full_result)
    reordered = {key: thawed[key] for key in reversed(tuple(thawed))}
    reordered["scenario_result"]["annual_rows"] = reordered["annual_rows"]
    reordered["scenario_result"]["debt_result"] = reordered["debt_result"]
    reordered["scenario_result"]["kpis"] = reordered["kpis"]
    frozen = _freeze(reordered)
    equivalent = replace(
        original,
        full_result=frozen,
        run_manifest=frozen["run_manifest"],
    )
    assert d3b_execution_success_content_digest(equivalent) == (
        d3b_execution_success_content_digest(original)
    )

    negative_zero = _mutated_success(
        original,
        lambda root: root["metrics"].update({"signed_zero": -0.0}),
    )
    positive_zero = _mutated_success(
        original,
        lambda root: root["metrics"].update({"signed_zero": 0.0}),
    )
    assert d3b_execution_success_content_digest(negative_zero) != (
        d3b_execution_success_content_digest(positive_zero)
    )


def test_content_identity_has_cycle_and_payload_bounds(
    context_fixture: _ContextFixture,
) -> None:
    cyclic_backing: dict[str, Any] = {}
    cyclic = MappingProxyType(cyclic_backing)
    cyclic_backing["self"] = cyclic
    damaged = copy.copy(context_fixture.success)
    object.__setattr__(damaged, "full_result", cyclic)
    object.__setattr__(damaged, "run_manifest", cyclic)
    with pytest.raises(D3CContextBindingError) as caught:
        d3b_execution_success_content_digest(damaged)
    assert caught.value.code == "success_identity_cycle"

    with pytest.raises(D3CContextBindingError) as caught:
        GovernedArtifactPayload(
            role=GovernedByteArtifactRole.ANNUAL_ROWS,
            content=b"",
        )
    assert caught.value.code == "artifact_payload_out_of_bounds"


@pytest.mark.parametrize(
    ("limit_name", "error_code"),
    (
        ("_MAX_IDENTITY_DEPTH", "success_identity_depth_exceeded"),
        ("_MAX_IDENTITY_CONTAINERS", "success_identity_out_of_bounds"),
        ("_MAX_IDENTITY_SCALARS", "success_identity_out_of_bounds"),
        ("_MAX_IDENTITY_TEXT_CODEPOINTS", "success_identity_out_of_bounds"),
        ("_MAX_IDENTITY_CANONICAL_BYTES", "success_identity_bytes_exceeded"),
    ),
)
def test_content_identity_resource_limits_have_negative_controls(
    context_fixture: _ContextFixture,
    monkeypatch: pytest.MonkeyPatch,
    limit_name: str,
    error_code: str,
) -> None:
    monkeypatch.setattr(context_binding, limit_name, 1)
    with pytest.raises(D3CContextBindingError) as caught:
        d3b_execution_success_content_digest(context_fixture.success)
    assert caught.value.code == error_code


def test_content_identity_refuses_oversized_integer_even_after_object_tamper(
    context_fixture: _ContextFixture,
) -> None:
    damaged = copy.copy(context_fixture.success)
    hostile = MappingProxyType({"hostile_integer": 1 << 4096})
    object.__setattr__(damaged, "full_result", hostile)
    with pytest.raises(D3CContextBindingError) as caught:
        d3b_execution_success_content_digest(damaged)
    assert caught.value.code == "success_identity_integer_out_of_bounds"


def test_content_identity_refuses_surrogates_key_types_and_value_types(
    context_fixture: _ContextFixture,
) -> None:
    surrogate = replace(context_fixture.success, request_id="request:\ud800")
    with pytest.raises(D3CContextBindingError) as caught:
        d3b_execution_success_content_digest(surrogate)
    assert caught.value.code == "invalid_success_unicode"

    for hostile, error_code in (
        (MappingProxyType({True: "value"}), "success_identity_key_type"),
        (MappingProxyType({"bytes": b"value"}), "success_identity_type"),
        (MappingProxyType({"not_finite": float("inf")}), "success_identity_non_finite"),
    ):
        damaged = copy.copy(context_fixture.success)
        object.__setattr__(damaged, "full_result", hostile)
        with pytest.raises(D3CContextBindingError) as caught:
            d3b_execution_success_content_digest(damaged)
        assert caught.value.code == error_code

    with pytest.raises(D3CContextBindingError) as caught:
        d3b_execution_success_content_digest(cast(Any, object()))
    assert caught.value.code == "invalid_success_type"

    cycle_backing: dict[str, Any] = {}
    cycle_proxy = MappingProxyType(cycle_backing)
    cycle_tuple = (cycle_proxy,)
    cycle_backing["back_to_tuple"] = cycle_tuple
    damaged = copy.copy(context_fixture.success)
    object.__setattr__(
        damaged,
        "full_result",
        MappingProxyType({"tuple_cycle": cycle_tuple}),
    )
    with pytest.raises(D3CContextBindingError) as caught:
        d3b_execution_success_content_digest(damaged)
    assert caught.value.code == "success_identity_cycle"


def test_candidate_models_are_strict_frozen_and_unknown_fields_fail(
    context_fixture: _ContextFixture,
) -> None:
    candidate = _bind(context_fixture)
    with pytest.raises(ValidationError, match="frozen"):
        candidate.release_status = "authorized"
    payload = candidate.model_dump(mode="json")
    payload["package_release"] = {"status": "authorized"}
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        D3CContextBindingCandidate.model_validate(payload)


def test_candidate_reingress_rechecks_every_reciprocal_edge(
    context_fixture: _ContextFixture,
) -> None:
    candidate = _bind(context_fixture)
    assert type(candidate) is D3CContextBindingCandidate

    def rebuild(**updates: Any) -> None:
        values = {
            field_name: getattr(candidate, field_name)
            for field_name in D3CContextBindingCandidate.model_fields
        }
        values.update(updates)
        D3CContextBindingCandidate(**values)

    with pytest.raises(ValidationError, match="cannot alias"):
        rebuild(authority_id=candidate.report_identity.report_id)
    with pytest.raises(ValidationError, match="report identity differs"):
        rebuild(
            report_identity=candidate.report_identity.model_copy(
                update={"project_id": "project:foreign"}
            )
        )
    with pytest.raises(ValidationError, match="request identity differs"):
        rebuild(
            evaluation_request_identity=(
                candidate.evaluation_request_identity.model_copy(
                    update={"request_id": "request:foreign"}
                )
            )
        )
    with pytest.raises(ValidationError, match="content digests differ"):
        rebuild(
            project_case_content_digest=(
                candidate.project_case_content_digest.model_copy(
                    update={"value": "0" * 64}
                )
            )
        )
    with pytest.raises(ValidationError, match="runtime receipt differs"):
        rebuild(
            runtime_receipt=candidate.runtime_receipt.model_copy(
                update={"engine_version": "15.4.1"}
            )
        )
    with pytest.raises(ValidationError, match="duplicate actor_id"):
        rebuild(actor_records=(*candidate.actor_records, candidate.actor_records[0]))
    with pytest.raises(ValidationError, match="artifact identities"):
        rebuild(
            verified_artifact_payloads=(
                candidate.verified_artifact_payloads[0].model_copy(
                    update={"artifact_id": "artifact:foreign"}
                ),
                *candidate.verified_artifact_payloads[1:],
            )
        )
    with pytest.raises(ValidationError, match="byte receipt"):
        rebuild(
            verified_artifact_payloads=(
                candidate.verified_artifact_payloads[0].model_copy(
                    update={"role": GovernedByteArtifactRole.DEBT_RESULT}
                ),
                *candidate.verified_artifact_payloads[1:],
            )
        )
    with pytest.raises(ValidationError, match="dangling source"):
        rebuild(
            input_records=(
                candidate.input_records[0].model_copy(
                    update={"source_ids": ("source:missing",)}
                ),
                *candidate.input_records[1:],
            )
        )
    with pytest.raises(ValidationError, match="input origin is dangling"):
        rebuild(
            input_origins=(
                candidate.input_origins[0].model_copy(
                    update={"input_id": "input:missing"}
                ),
                *candidate.input_origins[1:],
            )
        )
    with pytest.raises(ValidationError, match="duplicate input origins"):
        rebuild(input_origins=(*candidate.input_origins, candidate.input_origins[0]))
    with pytest.raises(ValidationError, match="foreign report/run"):
        rebuild(
            output_references=(
                candidate.output_references[0].model_copy(
                    update={"report_id": "report:foreign"}
                ),
                *candidate.output_references[1:],
            )
        )
    with pytest.raises(ValidationError, match="taxonomy SSOT order"):
        rebuild(
            sections=(
                candidate.sections[1],
                candidate.sections[0],
                *candidate.sections[2:],
            )
        )
    with pytest.raises(ValidationError, match="section contains a dangling"):
        rebuild(
            sections=(
                candidate.sections[0].model_copy(
                    update={"candidate_output_ids": ("output:missing",)}
                ),
                *candidate.sections[1:],
            )
        )
