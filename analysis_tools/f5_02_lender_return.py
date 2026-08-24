"""Fail-closed validation for confidential F5-02 lender evidence returns.

This module validates structure and evidence traceability only. It never authorizes a
canonical model binding or a lender/Board release.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterator, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal, cast

import yaml

ValidationMode = Literal["template", "structural", "closure_candidate"]
RequirementContext = tuple[Mapping[str, Any], str | None]

SCHEMA_VERSION = "dutchbay.f5_02_lender_confirmation.v1"
ALLOWED_STATUSES = {
    "unknown",
    "provisional",
    "confirmed",
    "not_applicable",
    "conflicted",
}
PROJECT_REQUIREMENT_IDS = {
    "F502-EV-001",
    "F502-EV-002",
    "F502-EV-003",
    "F502-EV-005",
    "F502-EV-020",
}
ALL_REQUIREMENT_IDS = {
    "F502-EV-001",
    "F502-EV-002",
    "F502-EV-003",
    "F502-EV-004",
    "F502-EV-005",
    "F502-EV-010",
    "F502-EV-011",
    "F502-EV-012",
    "F502-EV-013",
    "F502-EV-014",
    "F502-EV-015",
    "F502-EV-016",
    "F502-EV-017",
    "F502-EV-018",
    "F502-EV-019",
    "F502-EV-020",
    "F502-EV-025",
    "F502-EV-026",
    "F502-EV-027",
    "F502-EV-028",
    "F502-EV-029",
    "F502-EV-030",
    "F502-EV-035",
    "F502-EV-036",
    "F502-EV-037",
    "F502-EV-038",
    "F502-EV-039",
    "F502-EV-040",
    "F502-EV-045",
    "F502-EV-046",
    "F502-EV-047",
    "F502-EV-048",
    "F502-EV-049",
    "F502-EV-050",
    "F502-EV-051",
    "F502-EV-052",
    "F502-EV-060",
    "F502-EV-061",
    "F502-EV-062",
    "F502-EV-063",
    "F502-EV-064",
    "F502-EV-065",
    "F502-EV-070",
    "F502-EV-071",
    "F502-EV-072",
    "F502-EV-073",
    "F502-EV-074",
    "F502-EV-075",
    "F502-EV-080",
    "F502-EV-081",
    "F502-EV-082",
    "F502-EV-083",
    "F502-EV-084",
}
FACILITY_REQUIREMENT_IDS = ALL_REQUIREMENT_IDS - PROJECT_REQUIREMENT_IDS
_SCALAR_CURRENCY_REQUIREMENT_IDS = {
    "F502-EV-010",
    "F502-EV-012",
    "F502-EV-013",
    "F502-EV-014",
}
REQUIREMENT_RECORD_KEYS = {
    "requirement_id",
    "status",
    "value",
    "evidence_refs",
    "claim_citation_ids",
    "comment",
}
CLAIM_CITATION_KEYS = {
    "citation_id",
    "requirement_id",
    "facility_id",
    "evidence_id",
    "exact_page",
    "exact_section",
    "exact_clause",
    "extracted_value_or_text",
    "respondent_name",
    "respondent_role",
    "respondent_authority_reference",
    "not_applicable_reason",
}
PINNED_DOCUMENT_CONTROL_KEYS = {
    "document_id",
    "project",
    "purpose",
    "confidentiality",
    "release_status",
    "canonical_model_input_authorized",
    "prepared_date",
    "supersedes",
    "related_finding",
    "related_issue",
    "requirements_register",
    "instructions",
}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_DECIMAL_RE = re.compile(r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIMESTAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})$"
)
_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
_CURRENCY_SCALAR_KEYS = {
    "account_currency",
    "accounting_currency",
    "break_cost_currency",
    "claim_payment_currency",
    "commitment_currency",
    "coupon_currency",
    "currency",
    "currency_of_account",
    "currency_of_payment",
    "default_interest_currency",
    "drawdown_currency",
    "fee_currency",
    "functional_currency",
    "indemnity_currency",
    "interest_payment_currency",
    "invoicing_currency",
    "judgment_currency",
    "native_principal_currency",
    "pay_currency",
    "payment_currency",
    "premium_currency",
    "principal_accounting_currency",
    "principal_repayment_currency",
    "receive_currency",
    "reporting_currency",
    "security_currency",
    "tariff_currency",
    "tranche_limit_currency",
}
_NULL_BOOLEAN_KEYS = {
    "distinction_from_legal_currency_confirmed",
    "ecba_required",
    "interest_capitalized",
    "interest_deductibility",
}
_CONFIRMED_EXECUTION_STATUSES = {
    "executed_and_effective",
    "signed_and_current",
    "certified_current",
    "official_current",
    "authenticated_current",
}
_CONFIRMED_EVIDENCE_TIERS = {f"tier_{index}" for index in range(1, 8)}
_CONFIRMED_SOURCE_FORMS = {
    "verified_executed_original",
    "authenticated_data_room_copy",
    "certified_true_copy",
    "official_publication_verified",
    "issuer_confirmation",
}
_CONFIRMED_AUTHENTICATION_METHODS = {
    "signature_and_effectiveness_verified",
    "custodian_hash_and_original_verified",
    "certified_copy_verified",
    "official_source_verified",
    "issuer_direct_confirmation",
}
_CONFIRMED_REVIEW_DISPOSITIONS = {"accepted", "accepted_with_qualifications"}


class F502LenderReturnError(ValueError):
    """Raised when a lender return violates the controlled ingress contract."""


class _UniqueKeySafeLoader(yaml.SafeLoader):
    """SafeLoader variant that rejects aliases and duplicate mapping keys."""

    yaml_implicit_resolvers = deepcopy(yaml.SafeLoader.yaml_implicit_resolvers)

    def compose_node(self, parent: Any, index: Any) -> yaml.Node:
        if self.check_event(yaml.AliasEvent):
            event = self.peek_event()  # type: ignore[no-untyped-call]
            raise yaml.constructor.ConstructorError(
                None,
                None,
                f"YAML aliases are prohibited: {event.anchor}",
                event.start_mark,
            )
        return cast(yaml.Node, super().compose_node(parent, index))


for _resolver_character in "yYnNoOtTfF":
    _UniqueKeySafeLoader.yaml_implicit_resolvers[_resolver_character] = [
        resolver
        for resolver in _UniqueKeySafeLoader.yaml_implicit_resolvers.get(
            _resolver_character, []
        )
        if resolver[0] != "tag:yaml.org,2002:bool"
    ]
_UniqueKeySafeLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool",
    re.compile(r"^(?:true|false|True|False|TRUE|FALSE)$"),
    list("tTfF"),
)


def _construct_unique_mapping(
    loader: _UniqueKeySafeLoader,
    node: yaml.MappingNode,
    deep: bool = False,
) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, (str, int, float, bool, type(None))):
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "complex YAML mapping keys are prohibited",
                key_node.start_mark,
            )
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


@dataclass(frozen=True)
class F502ValidationSummary:
    """Non-confidential validation receipt safe for JSON serialization."""

    schema_version: str
    document_id: str
    confidentiality_classification: str
    mode: ValidationMode
    sha256: str
    facility_count: int
    requirement_record_count: int
    evidence_count: int
    citation_count: int
    conflict_count: int
    status_counts: Mapping[str, int]
    canonical_binding_status: str = "blocked"
    release_status: str = "HOLD"

    def to_private_dict(self) -> dict[str, Any]:
        """Return detailed private validation facts without lender-entered values."""

        return {
            "schema_version": self.schema_version,
            "document_id": self.document_id,
            "confidentiality_classification": self.confidentiality_classification,
            "mode": self.mode,
            "sha256": self.sha256,
            "facility_count": self.facility_count,
            "requirement_record_count": self.requirement_record_count,
            "evidence_count": self.evidence_count,
            "citation_count": self.citation_count,
            "conflict_count": self.conflict_count,
            "status_counts": dict(sorted(self.status_counts.items())),
            "canonical_binding_status": self.canonical_binding_status,
            "release_status": self.release_status,
        }

    def to_public_receipt(
        self, *, custodian_role: str, receipt_timestamp: str
    ) -> dict[str, str]:
        """Return the exact five-field public receipt allowed by the template."""

        _require(_is_nonempty_string(custodian_role), "custodian_role is required")
        _require(
            _TIMESTAMP_RE.fullmatch(receipt_timestamp) is not None,
            "receipt_timestamp must be RFC3339 with seconds and timezone",
        )
        return {
            "document_id": self.document_id,
            "custodian_role": custodian_role,
            "receipt_timestamp": receipt_timestamp,
            "confidentiality_classification": self.confidentiality_classification,
            "sha256": self.sha256,
        }


def _fail(message: str) -> None:
    raise F502LenderReturnError(message)


def _require(condition: bool, message: str) -> None:
    if not condition:
        _fail(message)


def _is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _load_one_mapping(text: str, *, label: str) -> dict[str, Any]:
    try:
        documents = list(yaml.load_all(text, Loader=_UniqueKeySafeLoader))
    except yaml.YAMLError as exc:
        raise F502LenderReturnError(f"{label}: unsafe or invalid YAML: {exc}") from exc
    _require(len(documents) == 1, f"{label}: expected one YAML document")
    document = documents[0]
    _require(isinstance(document, dict), f"{label}: document must be one mapping")
    return cast(dict[str, Any], document)


def _walk(value: Any, path: str = "$") -> Iterator[tuple[str, Any]]:
    yield path, value
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield from _walk(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, f"{path}[{index}]")


def _validate_json_safe_scalars(document: Mapping[str, Any]) -> None:
    for path, value in _walk(document):
        _require(
            value is None or type(value) in {str, int, float, bool, list, dict},
            f"{path}: implicit or non-JSON YAML type {type(value).__name__} is prohibited",
        )
        if isinstance(value, float):
            _require(
                value == value and abs(value) != float("inf"),
                f"{path}: non-finite number",
            )


def _validate_shape(candidate: Any, template: Any, path: str) -> None:
    if isinstance(template, Mapping):
        _require(isinstance(candidate, Mapping), f"{path}: expected mapping")
        _require(
            set(candidate) == set(template),
            f"{path}: keys differ from the versioned template",
        )
        for key, template_value in template.items():
            _validate_shape(candidate[key], template_value, f"{path}.{key}")
        return
    if isinstance(template, list):
        _require(isinstance(candidate, list), f"{path}: expected list")
        if template and isinstance(template[0], Mapping):
            for index, item in enumerate(candidate):
                _validate_shape(item, template[0], f"{path}[{index}]")
        return
    if template is None:
        if candidate is None:
            return
        key = path.rsplit(".", 1)[-1]
        if key in _NULL_BOOLEAN_KEYS:
            _require(
                type(candidate) is bool, f"{path}: expected explicit true or false"
            )
        else:
            _require(isinstance(candidate, str), f"{path}: expected a quoted string")
        return
    if isinstance(template, bool):
        _require(type(candidate) is bool, f"{path}: expected boolean")
        return
    if isinstance(template, int):
        _require(type(candidate) is int, f"{path}: expected integer")
        return
    if isinstance(template, str):
        _require(isinstance(candidate, str), f"{path}: expected string")


def _validate_named_scalar_contracts(document: Mapping[str, Any]) -> None:
    for path, value in _walk(document):
        key = path.rsplit(".", 1)[-1]
        if value is None:
            continue
        if key.endswith("_decimal_string"):
            _require(
                isinstance(value, str) and _DECIMAL_RE.fullmatch(value) is not None,
                f"{path}: expected a plain decimal string",
            )
            try:
                decimal_value = Decimal(value)
                _require(decimal_value.is_finite(), f"{path}: decimal must be finite")
            except InvalidOperation as exc:
                raise F502LenderReturnError(f"{path}: invalid decimal string") from exc
            if "amount" in key:
                _require(
                    decimal_value >= 0, f"{path}: monetary amount cannot be negative"
                )
            if "rate_pct" in key or key.endswith("_pct_decimal_string"):
                _require(
                    Decimal("-100") <= decimal_value <= Decimal("1000"),
                    f"{path}: percentage rate is dimensionally implausible",
                )
            if "margin_bps" in key:
                _require(
                    Decimal("-10000") <= decimal_value <= Decimal("100000"),
                    f"{path}: basis-point margin is dimensionally implausible",
                )
        if key.endswith("unit_scale") or key == "unit_scale":
            _require(value == "base_units", f"{path}: only base_units is permitted")
        if key.endswith("_date") or key in {"date", "prepared_date", "evidence_cutoff"}:
            _require(
                isinstance(value, str) and _DATE_RE.fullmatch(value) is not None,
                f"{path}: expected a quoted YYYY-MM-DD string",
            )
        if key in _CURRENCY_SCALAR_KEYS and isinstance(value, str):
            _require(
                _CURRENCY_RE.fullmatch(value) is not None,
                f"{path}: expected ISO-4217 code",
            )
        if key.endswith("currencies") and isinstance(value, list):
            _require(
                all(
                    isinstance(item, str) and _CURRENCY_RE.fullmatch(item)
                    for item in value
                ),
                f"{path}: expected ISO-4217 code list",
            )


def _collect_requirement_records(value: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if isinstance(value, Mapping):
        if "requirement_id" in value:
            records.append(cast(dict[str, Any], value))
        else:
            for child in value.values():
                records.extend(_collect_requirement_records(child))
    elif isinstance(value, list):
        for child in value:
            records.extend(_collect_requirement_records(child))
    return records


def _validate_requirement_population(
    document: Mapping[str, Any],
) -> tuple[list[RequirementContext], int]:
    project_records = _collect_requirement_records(document["transaction"])
    project_ids = [str(record["requirement_id"]) for record in project_records]
    _require(
        len(project_ids) == len(set(project_ids))
        and set(project_ids) == PROJECT_REQUIREMENT_IDS,
        "$.transaction: project-wide requirement population is incomplete or duplicated",
    )

    facilities = document["facilities"]
    _require(
        bool(isinstance(facilities, list) and facilities),
        "$.facilities: at least one facility is required",
    )
    facilities = cast(list[Any], facilities)
    facility_ids: list[str] = []
    all_contexts: list[RequirementContext] = [
        (cast(Mapping[str, Any], record), None) for record in project_records
    ]
    for index, facility in enumerate(facilities):
        _require(
            isinstance(facility, Mapping), f"$.facilities[{index}]: expected mapping"
        )
        facility_id = facility.get("facility_id")
        if facility_id is not None:
            _require(
                _is_nonempty_string(facility_id),
                f"$.facilities[{index}].facility_id: invalid",
            )
            facility_ids.append(cast(str, facility_id))
        records = _collect_requirement_records(facility)
        requirement_ids = [str(record["requirement_id"]) for record in records]
        _require(
            len(requirement_ids) == len(set(requirement_ids))
            and set(requirement_ids) == FACILITY_REQUIREMENT_IDS,
            f"$.facilities[{index}]: requirement population is incomplete or duplicated",
        )
        all_contexts.extend(
            (cast(Mapping[str, Any], record), cast(str | None, facility_id))
            for record in records
        )
    _require(
        len(facility_ids) == len(set(facility_ids)),
        "$.facilities: duplicate facility_id",
    )
    return all_contexts, len(facilities)


def _validate_evidence_catalog(
    document: Mapping[str, Any], *, mode: ValidationMode
) -> dict[str, Mapping[str, Any]]:
    catalog = document["evidence_catalog"]
    _require(isinstance(catalog, list), "$.evidence_catalog: expected list")
    indexed: dict[str, Mapping[str, Any]] = {}
    for index, record in enumerate(catalog):
        _require(
            isinstance(record, Mapping),
            f"$.evidence_catalog[{index}]: expected mapping",
        )
        evidence_id = record.get("evidence_id")
        if evidence_id is None and mode == "template":
            continue
        _require(
            _is_nonempty_string(evidence_id),
            f"$.evidence_catalog[{index}].evidence_id: required",
        )
        evidence_id = cast(str, evidence_id)
        _require(evidence_id not in indexed, f"duplicate evidence_id {evidence_id}")
        indexed[evidence_id] = record
    return indexed


def _validate_claim_citations(
    document: Mapping[str, Any], *, mode: ValidationMode
) -> dict[str, Mapping[str, Any]]:
    citations = document["claim_citations"]
    _require(isinstance(citations, list), "$.claim_citations: expected list")
    indexed: dict[str, Mapping[str, Any]] = {}
    for index, record in enumerate(citations):
        _require(
            isinstance(record, Mapping), f"$.claim_citations[{index}]: expected mapping"
        )
        _require(
            set(record) == CLAIM_CITATION_KEYS,
            f"$.claim_citations[{index}]: wrong fields",
        )
        citation_id = record.get("citation_id")
        if citation_id is None and mode == "template":
            continue
        _require(
            _is_nonempty_string(citation_id),
            f"$.claim_citations[{index}].citation_id: required",
        )
        citation_id = cast(str, citation_id)
        _require(citation_id not in indexed, f"duplicate citation_id {citation_id}")
        indexed[citation_id] = record
    return indexed


def _require_complete_confirmed_value(
    value: Any, path: str, *, require_nonempty_list: bool = True
) -> None:
    if isinstance(value, Mapping):
        _require(bool(value), f"{path}: confirmed mapping cannot be empty")
        for key, child in value.items():
            _require_complete_confirmed_value(
                child,
                f"{path}.{key}",
                require_nonempty_list=False,
            )
        return
    if isinstance(value, list):
        if require_nonempty_list:
            _require(bool(value), f"{path}: confirmed list cannot be empty")
        for index, child in enumerate(value):
            _require_complete_confirmed_value(
                child,
                f"{path}[{index}]",
                require_nonempty_list=False,
            )
        return
    _require(
        value is True or value is False or _is_nonempty_string(value),
        f"{path}: confirmed value is incomplete",
    )


def _require_confirmed_evidence_eligible(
    evidence_id: str, record: Mapping[str, Any]
) -> None:
    _require(
        record.get("execution_status") in _CONFIRMED_EXECUTION_STATUSES,
        f"evidence {evidence_id}: execution_status is not eligible for confirmation",
    )
    _require(
        record.get("evidence_tier") in _CONFIRMED_EVIDENCE_TIERS,
        f"evidence {evidence_id}: evidence_tier is not eligible for confirmation",
    )
    _require(
        record.get("source_form") in _CONFIRMED_SOURCE_FORMS,
        f"evidence {evidence_id}: source_form is not eligible for confirmation",
    )
    _require(
        record.get("authentication_method") in _CONFIRMED_AUTHENTICATION_METHODS,
        f"evidence {evidence_id}: authentication_method is not eligible for confirmation",
    )
    _require(
        record.get("reviewer_independence") == "independent",
        f"evidence {evidence_id}: independent review is required for confirmation",
    )
    _require(
        record.get("review_disposition") in _CONFIRMED_REVIEW_DISPOSITIONS,
        f"evidence {evidence_id}: review_disposition is not eligible for confirmation",
    )


def _validate_embedded_evidence_references(
    value: Any,
    *,
    evidence: Mapping[str, Mapping[str, Any]],
    path: str,
    require_eligible: bool,
) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            is_catalog_definition = (
                path.startswith("$.evidence_catalog[") and key == "evidence_id"
            )
            if key.endswith("_evidence_id") or (
                key == "evidence_id" and not is_catalog_definition
            ):
                if child is not None:
                    _require(
                        _is_nonempty_string(child),
                        f"{child_path}: expected evidence ID",
                    )
                    evidence_id = cast(str, child)
                    _require(
                        evidence_id in evidence,
                        f"{child_path}: unknown evidence {evidence_id}",
                    )
                    if require_eligible:
                        _require_confirmed_evidence_eligible(
                            evidence_id, evidence[evidence_id]
                        )
            elif key.endswith("_evidence_ids") or key == "evidence_refs":
                _require(
                    isinstance(child, list), f"{child_path}: expected evidence ID list"
                )
                child = cast(list[Any], child)
                _require(
                    all(_is_nonempty_string(item) for item in child),
                    f"{child_path}: expected evidence ID strings",
                )
                _require(
                    len(child) == len(set(child)),
                    f"{child_path}: duplicate evidence ID",
                )
                for evidence_id in cast(list[str], child):
                    _require(
                        evidence_id in evidence,
                        f"{child_path}: unknown evidence {evidence_id}",
                    )
                    if require_eligible:
                        _require_confirmed_evidence_eligible(
                            evidence_id, evidence[evidence_id]
                        )
            _validate_embedded_evidence_references(
                child,
                evidence=evidence,
                path=child_path,
                require_eligible=require_eligible,
            )
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _validate_embedded_evidence_references(
                child,
                evidence=evidence,
                path=f"{path}[{index}]",
                require_eligible=require_eligible,
            )


def _validate_requirement_records(
    contexts: Sequence[RequirementContext],
    *,
    evidence: Mapping[str, Mapping[str, Any]],
    citations: Mapping[str, Mapping[str, Any]],
    conflicts: Sequence[Mapping[str, Any]],
    mode: ValidationMode,
) -> dict[str, int]:
    status_counts = {status: 0 for status in sorted(ALLOWED_STATUSES)}
    referenced_citations: set[str] = set()
    for record, facility_id in contexts:
        requirement_id = str(record.get("requirement_id"))
        _require(
            set(record) == REQUIREMENT_RECORD_KEYS,
            f"{requirement_id}: wrong response fields",
        )
        status = record.get("status")
        _require(
            status in ALLOWED_STATUSES, f"{requirement_id}: invalid status {status!r}"
        )
        status = cast(str, status)
        status_counts[status] += 1
        if requirement_id in _SCALAR_CURRENCY_REQUIREMENT_IDS:
            value = record.get("value")
            if value is not None:
                _require(
                    isinstance(value, str)
                    and _CURRENCY_RE.fullmatch(value) is not None,
                    f"{requirement_id}.value: expected ISO-4217 code",
                )
        evidence_refs = record.get("evidence_refs")
        citation_ids = record.get("claim_citation_ids")
        _require(
            isinstance(evidence_refs, list)
            and all(_is_nonempty_string(item) for item in evidence_refs),
            f"{requirement_id}: evidence_refs must be a string list",
        )
        _require(
            isinstance(citation_ids, list)
            and all(_is_nonempty_string(item) for item in citation_ids),
            f"{requirement_id}: claim_citation_ids must be a string list",
        )
        evidence_refs = cast(list[str], evidence_refs)
        citation_ids = cast(list[str], citation_ids)
        _require(
            len(evidence_refs) == len(set(evidence_refs)),
            f"{requirement_id}: duplicate evidence ref",
        )
        _require(
            len(citation_ids) == len(set(citation_ids)),
            f"{requirement_id}: duplicate citation ref",
        )
        for evidence_id in evidence_refs:
            _require(
                evidence_id in evidence,
                f"{requirement_id}: unknown evidence {evidence_id}",
            )
        for citation_id in citation_ids:
            _require(
                citation_id in citations,
                f"{requirement_id}: unknown citation {citation_id}",
            )
            citation = citations[citation_id]
            _require(
                citation["requirement_id"] == requirement_id,
                f"{citation_id}: requirement mismatch",
            )
            _require(
                citation["facility_id"] == facility_id,
                f"{citation_id}: facility mismatch",
            )
            _require(
                citation["evidence_id"] in evidence_refs,
                f"{citation_id}: evidence mismatch",
            )
            referenced_citations.add(citation_id)
        if status in {"confirmed", "not_applicable"}:
            _require(
                bool(evidence_refs) and bool(citation_ids),
                f"{requirement_id}: evidence and citations required",
            )
            for citation_id in citation_ids:
                citation = citations[citation_id]
                for field in (
                    "evidence_id",
                    "exact_page",
                    "exact_clause",
                    "extracted_value_or_text",
                    "respondent_name",
                    "respondent_role",
                    "respondent_authority_reference",
                ):
                    _require(
                        _is_nonempty_string(citation[field]),
                        f"{citation_id}.{field}: required",
                    )
                if status == "not_applicable":
                    _require(
                        _is_nonempty_string(citation["not_applicable_reason"]),
                        f"{citation_id}.not_applicable_reason: required",
                    )
            for evidence_id in evidence_refs:
                _require_confirmed_evidence_eligible(evidence_id, evidence[evidence_id])
            _validate_embedded_evidence_references(
                record.get("value"),
                evidence=evidence,
                path=f"{requirement_id}.value",
                require_eligible=True,
            )
        if status == "confirmed":
            _require_complete_confirmed_value(
                record.get("value"), f"{requirement_id}.value"
            )
        if status == "provisional":
            _require(
                bool(evidence_refs), f"{requirement_id}: provisional source required"
            )
            _require(
                _is_nonempty_string(record.get("comment")),
                f"{requirement_id}: provisional condition required",
            )
        if status == "conflicted":
            _require(
                len(evidence_refs) >= 2,
                f"{requirement_id}: conflicting evidence required",
            )
            _require(
                _is_nonempty_string(record.get("comment")),
                f"{requirement_id}: conflict explanation required",
            )
            _require(
                any(
                    requirement_id in conflict.get("requirement_ids", [])
                    and (
                        facility_id in conflict.get("facility_ids", [])
                        if facility_id is not None
                        else not conflict.get("facility_ids", [])
                    )
                    for conflict in conflicts
                ),
                f"{requirement_id}: conflict register record required",
            )
        if mode == "closure_candidate":
            _require(
                status in {"confirmed", "not_applicable"},
                f"{requirement_id}: unresolved status {status}",
            )
    _require(set(citations) == referenced_citations, "orphan claim citation record")
    return status_counts


def _validate_referenced_evidence(
    evidence: Mapping[str, Mapping[str, Any]], contexts: Sequence[RequirementContext]
) -> None:
    referenced = {
        str(evidence_id)
        for record, _facility_id in contexts
        for evidence_id in cast(list[Any], record["evidence_refs"])
    }
    for evidence_id in referenced:
        record = evidence[evidence_id]
        for field in (
            "exact_title",
            "document_type",
            "execution_status",
            "retained_path_or_stable_url",
            "sha256",
            "evidence_tier",
            "source_form",
            "authentication_method",
            "authenticated_by",
            "authentication_date",
            "reviewed_by",
            "reviewer_independence",
            "review_scope",
            "review_date",
            "review_disposition",
        ):
            _require(
                _is_nonempty_string(record.get(field)),
                f"evidence {evidence_id}.{field}: required",
            )
        _require(
            _SHA256_RE.fullmatch(cast(str, record["sha256"])) is not None,
            f"evidence {evidence_id}: invalid sha256",
        )


def _nested_list(value: Any, keys: Sequence[str]) -> list[Any]:
    current = value
    for key in keys:
        _require(
            isinstance(current, Mapping),
            f"entity path {'.'.join(keys)}: expected mapping",
        )
        current = current.get(key)
    _require(isinstance(current, list), f"entity path {'.'.join(keys)}: expected list")
    return cast(list[Any], current)


def _validate_multi_entity_ids(
    contexts: Sequence[RequirementContext], *, mode: ValidationMode
) -> None:
    entity_contracts: dict[str, tuple[tuple[str, ...], str]] = {
        "F502-EV-002": ((), "party_id"),
        "F502-EV-019": ((), "utilization_id"),
        "F502-EV-025": (("caps",), "cap_id"),
        "F502-EV-030": (("other_fees",), "fee_id"),
        "F502-EV-047": (("native_currency_installments",), "installment_id"),
        "F502-EV-049": (("mandatory_prepayments",), "prepayment_id"),
        "F502-EV-072": ((), "instrument_id"),
        "F502-EV-075": ((), "reserve_or_facility_id"),
    }
    for record, facility_id in contexts:
        requirement_id = cast(str, record["requirement_id"])
        if requirement_id not in entity_contracts:
            continue
        keys, id_key = entity_contracts[requirement_id]
        items = (
            _nested_list(record["value"], keys)
            if keys
            else cast(list[Any], record["value"])
        )
        ids: list[str] = []
        for index, item in enumerate(items):
            _require(
                isinstance(item, Mapping),
                f"{requirement_id}[{index}]: expected mapping",
            )
            entity_id = item.get(id_key)
            if entity_id is None and mode == "template":
                continue
            if entity_id is None and record["status"] == "unknown":
                populated = any(
                    not (
                        value is None
                        or value == ""
                        or value == "base_units"
                        or value == []
                    )
                    for key, value in item.items()
                    if key != id_key
                )
                _require(not populated, f"{requirement_id}[{index}].{id_key}: required")
                continue
            _require(
                _is_nonempty_string(entity_id),
                f"{requirement_id}[{index}].{id_key}: required",
            )
            ids.append(cast(str, entity_id))
        _require(
            len(ids) == len(set(ids)),
            f"{requirement_id} facility {facility_id}: duplicate {id_key}",
        )


def _validate_conflicts(
    document: Mapping[str, Any], *, evidence_ids: set[str], facility_ids: set[str]
) -> list[Mapping[str, Any]]:
    conflicts = document["conflicts_and_open_items"]
    _require(isinstance(conflicts, list), "$.conflicts_and_open_items: expected list")
    indexed: set[str] = set()
    retained: list[Mapping[str, Any]] = []
    for index, conflict in enumerate(conflicts):
        _require(isinstance(conflict, Mapping), f"conflict[{index}]: expected mapping")
        conflict_id = conflict.get("conflict_id")
        if conflict_id is None:
            continue
        _require(
            _is_nonempty_string(conflict_id), f"conflict[{index}].conflict_id: required"
        )
        conflict_id = cast(str, conflict_id)
        _require(conflict_id not in indexed, f"duplicate conflict_id {conflict_id}")
        indexed.add(conflict_id)
        _require(
            set(conflict.get("requirement_ids", [])) <= ALL_REQUIREMENT_IDS,
            f"{conflict_id}: unknown requirement",
        )
        _require(
            set(conflict.get("evidence_ids", [])) <= evidence_ids,
            f"{conflict_id}: unknown evidence",
        )
        _require(
            set(conflict.get("facility_ids", [])) <= facility_ids,
            f"{conflict_id}: unknown facility",
        )
        _require(
            _is_nonempty_string(conflict.get("description")),
            f"{conflict_id}: description required",
        )
        _require(
            _is_nonempty_string(conflict.get("resolution_owner")),
            f"{conflict_id}: resolution owner required",
        )
        _require(
            conflict.get("status") in {"open", "resolved"},
            f"{conflict_id}: status must be open or resolved",
        )
        retained.append(conflict)
    return retained


def _require_all_leaf_values(mapping: Mapping[str, Any], path: str) -> None:
    for key, value in mapping.items():
        child_path = f"{path}.{key}"
        if isinstance(value, Mapping):
            _require_all_leaf_values(value, child_path)
        elif isinstance(value, list):
            _require(bool(value), f"{child_path}: required")
        else:
            _require(
                value is True or _is_nonempty_string(value), f"{child_path}: required"
            )


def validate_f5_02_lender_return(
    path: Path,
    *,
    template_path: Path,
    mode: ValidationMode = "structural",
) -> F502ValidationSummary:
    """Validate one confidential lender return and emit a non-secret receipt.

    Args:
        path: Private path to the returned YAML. Do not place it in the repository.
        template_path: Immutable public blank template defining the versioned shape.
        mode: ``template`` for the public blank, ``structural`` for partial returns,
            or ``closure_candidate`` for a fully evidenced confirmation package.

    Returns:
        A compact receipt that contains no lender-entered values or identities.

    Raises:
        F502LenderReturnError: If parsing, schema, provenance, or protected controls fail.
    """

    _require(
        mode in {"template", "structural", "closure_candidate"}, f"invalid mode {mode}"
    )
    resolved_path = path.resolve(strict=True)
    repository_root = template_path.resolve(strict=True).parents[3]
    if mode != "template":
        _require(
            not resolved_path.is_relative_to(repository_root),
            "confidential structural/closure returns must be outside the public repository",
        )
    text = path.read_text(encoding="utf-8")
    template_text = template_path.read_text(encoding="utf-8")
    document = _load_one_mapping(text, label=str(path))
    template = _load_one_mapping(template_text, label=str(template_path))
    _validate_json_safe_scalars(document)
    _validate_shape(document, template, "$")
    _require(document.get("schema_version") == SCHEMA_VERSION, "wrong schema_version")

    document_control = cast(Mapping[str, Any], document["document_control"])
    template_control = cast(Mapping[str, Any], template["document_control"])
    for key in PINNED_DOCUMENT_CONTROL_KEYS:
        _require(
            document_control[key] == template_control[key],
            f"document_control.{key} is protected",
        )
    for key in (
        "field_status_protocol",
        "response_contract",
        "privacy_and_return_handling",
        "repository_owned_controls",
    ):
        _require(
            document[key] == template[key], f"{key} is repository-owned and protected"
        )

    _validate_named_scalar_contracts(document)
    contexts, facility_count = _validate_requirement_population(document)
    evidence = _validate_evidence_catalog(document, mode=mode)
    citations = _validate_claim_citations(document, mode=mode)
    for reference_section in (
        "submission",
        "evidence_catalog",
        "claim_citations",
        "transaction",
        "facilities",
        "conflicts_and_open_items",
        "signoff",
    ):
        _validate_embedded_evidence_references(
            document[reference_section],
            evidence=evidence,
            path=f"$.{reference_section}",
            require_eligible=False,
        )
    facility_ids = {
        cast(str, facility["facility_id"])
        for facility in cast(list[dict[str, Any]], document["facilities"])
        if _is_nonempty_string(facility.get("facility_id"))
    }
    conflicts = _validate_conflicts(
        document,
        evidence_ids=set(evidence),
        facility_ids=facility_ids,
    )
    status_counts = _validate_requirement_records(
        contexts,
        evidence=evidence,
        citations=citations,
        conflicts=conflicts,
        mode=mode,
    )
    _validate_multi_entity_ids(contexts, mode=mode)
    _validate_referenced_evidence(evidence, contexts)

    if mode != "template":
        submission = cast(Mapping[str, Any], document["submission"])
        _require(
            _is_nonempty_string(submission.get("submission_id")),
            "submission_id is required",
        )
        _require(
            _is_nonempty_string(submission.get("submission_date")),
            "submission_date is required",
        )
        _require_all_leaf_values(
            cast(Mapping[str, Any], submission["prepared_by"]), "submission.prepared_by"
        )
        _require_all_leaf_values(
            cast(Mapping[str, Any], submission["respondent_authority"]),
            "submission.respondent_authority",
        )
        _require(
            _is_nonempty_string(submission.get("scope_of_confirmation")),
            "submission.scope_of_confirmation is required",
        )
        submitted_facility_ids = [
            facility["facility_id"]
            for facility in cast(list[dict[str, Any]], document["facilities"])
        ]
        _require(
            all(_is_nonempty_string(item) for item in submitted_facility_ids),
            "every facility_id is required",
        )

    if mode == "closure_candidate":
        confirmations = cast(Mapping[str, Any], document["confirmations"])
        _require(
            all(value is True for value in confirmations.values()),
            "all lender confirmations must be true",
        )
        _require_all_leaf_values(
            cast(Mapping[str, Any], document["signoff"]), "signoff"
        )
        _validate_embedded_evidence_references(
            document["signoff"],
            evidence=evidence,
            path="$.signoff",
            require_eligible=True,
        )
        _validate_embedded_evidence_references(
            cast(Mapping[str, Any], document["submission"])["respondent_authority"],
            evidence=evidence,
            path="$.submission.respondent_authority",
            require_eligible=True,
        )
        _require(
            all(conflict.get("status") == "resolved" for conflict in conflicts),
            "all conflicts must be resolved for a closure candidate",
        )

    return F502ValidationSummary(
        schema_version=SCHEMA_VERSION,
        document_id=cast(str, document_control["document_id"]),
        confidentiality_classification=cast(str, document_control["confidentiality"]),
        mode=mode,
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        facility_count=facility_count,
        requirement_record_count=len(contexts),
        evidence_count=len(evidence),
        citation_count=len(citations),
        conflict_count=len(conflicts),
        status_counts=status_counts,
    )


__all__ = [
    "ALL_REQUIREMENT_IDS",
    "F502LenderReturnError",
    "F502ValidationSummary",
    "PROJECT_REQUIREMENT_IDS",
    "SCHEMA_VERSION",
    "ValidationMode",
    "validate_f5_02_lender_return",
]
