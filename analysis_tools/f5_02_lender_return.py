"""Fail-closed validation for confidential F5-02 lender evidence returns.

This module validates structure and evidence traceability only. It never authorizes a
canonical model binding or a lender/Board release.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import unicodedata
from collections.abc import Callable, Iterator, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal, cast

import yaml

ValidationMode = Literal["template", "structural", "closure_candidate"]
RequirementContext = tuple[Mapping[str, Any], str | None]

SCHEMA_VERSION = "dutchbay.f5_02_lender_confirmation.v1"
PRIVATE_INGRESS_MANIFEST_SCHEMA_VERSION = "dutchbay.f5_02_private_ingress_manifest.v1"
REPO_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_TEMPLATE_PATH = (
    REPO_ROOT
    / "docs"
    / "audit"
    / "lender-input"
    / "DUTCHBAY_F5_02_LENDER_CONFIRMATION_TEMPLATE_v1.yaml"
)
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
# Frozen from SIX ISO-4217 Maintenance Agency List One on 2026-08-24.
# Source: https://www.six-group.com/dam/download/financial-information/
# data-center/iso-currrency/lists/list-one.xml
# Retained source SHA-256 at the cutoff:
# 838dfb991648cf36df939edd5fe3811737962b75a32252847d239cedd1e291c9
_CURRENT_ISO_4217_CODES = frozenset("""
    AED AFN ALL AMD AOA ARS AUD AWG AZN BAM BBD BDT BHD BIF BMD BND BOB BOV
    BRL BSD BTN BWP BYN BZD CAD CDF CHE CHF CHW CLF CLP CNY COP COU CRC CUP
    CVE CZK DJF DKK DOP DZD EGP ERN ETB EUR FJD FKP GBP GEL GHS GIP GMD GNF
    GTQ GYD HKD HNL HTG HUF IDR ILS INR IQD IRR ISK JMD JOD JPY KES KGS KHR
    KMF KPW KRW KWD KYD KZT LAK LBP LKR LRD LSL LYD MAD MDL MGA MKD MMK MNT
    MOP MRU MUR MVR MWK MXN MXV MYR MZN NAD NGN NIO NOK NPR NZD OMR PAB PEN
    PGK PHP PKR PLN PYG QAR RON RSD RUB RWF SAR SBD SCR SDG SEK SGD SHP SLE
    SOS SRD SSP STN SVC SYP SZL THB TJS TMT TND TOP TRY TTD TWD TZS UAH UGX
    USD USN UYI UYU UYW UZS VED VES VND VUV WST XAD XAF XAG XAU XBA XBB XBC
    XBD XCD XCG XDR XOF XPD XPF XPT XSU XTS XUA XXX YER ZAR ZMW ZWG
    """.split())
_NON_TRANSACTIONAL_ISO_4217_CODES = {"XTS", "XXX"}
_GIT_ROUTING_ENVIRONMENT_KEYS = {
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_CEILING_DIRECTORIES",
    "GIT_COMMON_DIR",
    "GIT_DIR",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_WORK_TREE",
}
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
_CONFIRMED_PLACEHOLDER_VALUES = {
    "awaiting confirmation",
    "not available",
    "not confirmed",
    "not known",
    "not provided",
    "null",
    "pending",
    "tbc",
    "tbd",
    "unknown",
}
_NOT_APPLICABLE_PROHIBITED_REQUIREMENT_IDS = {
    "F502-EV-001",  # borrower identity
    "F502-EV-002",  # lender, agent, and trustee identities
    "F502-EV-004",  # legal facility/tranche to model mapping
    "F502-EV-010",  # commitment currency
    "F502-EV-012",  # principal-accounting currency
    "F502-EV-013",  # interest-payment currency
    "F502-EV-014",  # principal-repayment currency
}
_PRIVATE_INGRESS_MANIFEST_KEYS = {
    "schema_version",
    "lender_return_sha256",
    "custodian_role",
    "ingress_timestamp",
    "evidence_records",
}
_INGRESS_BOUND_EVIDENCE_FIELDS = (
    "exact_title",
    "document_type",
    "issuer_or_parties",
    "execution_status",
    "version",
    "effective_date",
    "expiry_date",
    "amendment_and_waiver_status",
    "governing_law_relevance",
    "acquisition_date",
    "confidentiality",
    "evidence_tier",
    "source_form",
    "authentication_method",
    "controlling_original_evidence_id",
    "authenticated_by",
    "authentication_date",
    "reviewed_by",
    "reviewer_independence",
    "review_scope",
    "review_date",
    "review_disposition",
    "supersedes_evidence_ids",
    "superseded_by_evidence_ids",
    "limitations",
)
_PRIVATE_INGRESS_EVIDENCE_KEYS = {
    "evidence_id",
    "retained_path",
    "sha256",
    "byte_count",
    *_INGRESS_BOUND_EVIDENCE_FIELDS,
}
_PROHIBITED_CLOSURE_DOCUMENT_TYPE_TOKENS = {
    "analyst",
    "draft",
    "model",
    "reproduction",
    "simulation",
    "synthetic",
    "working_paper",
}


class F502LenderReturnError(ValueError):
    """Raised when a lender return violates the controlled ingress contract."""


class _UniqueKeySafeLoader(yaml.SafeLoader):
    """SafeLoader variant that rejects aliases and duplicate mapping keys."""

    yaml_implicit_resolvers = deepcopy(yaml.SafeLoader.yaml_implicit_resolvers)

    def compose_node(self, parent: Any, index: Any) -> yaml.Node:
        if self.check_event(yaml.AliasEvent):
            peek_alias_event = cast(Callable[[], yaml.AliasEvent], self.peek_event)
            event = peek_alias_event()
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
    bound_custodian_role: str | None = None

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
            "bound_custodian_role": self.bound_custodian_role,
        }

    def to_public_receipt(
        self, *, custodian_role: str, receipt_timestamp: str
    ) -> dict[str, str]:
        """Return the exact five-field public receipt allowed by the template."""

        _require(_is_nonempty_string(custodian_role), "custodian_role is required")
        if self.bound_custodian_role is not None:
            _require(
                custodian_role == self.bound_custodian_role,
                "custodian_role does not match the private ingress manifest",
            )
        _require_valid_timestamp(receipt_timestamp, "receipt_timestamp")
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


def _is_confirmed_placeholder(value: str) -> bool:
    normalized = re.sub(r"[\s._/\\-]+", " ", value.strip().lower()).strip()
    return normalized in _CONFIRMED_PLACEHOLDER_VALUES or normalized in {
        "n a",
        "na",
        "none",
    }


def _is_blank_template_row(record: Mapping[str, Any]) -> bool:
    return all(value is None or value == [] for value in record.values())


def _require_valid_date(value: Any, path: str) -> str:
    """Require a real Gregorian calendar date, not only date-shaped text."""

    _require(
        isinstance(value, str) and _DATE_RE.fullmatch(value) is not None,
        f"{path}: expected a quoted YYYY-MM-DD string",
    )
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise F502LenderReturnError(f"{path}: invalid calendar date") from exc
    return cast(str, value)


def _require_valid_timestamp(value: Any, path: str) -> str:
    """Require RFC3339 seconds precision and a valid explicit timezone."""

    _require(
        isinstance(value, str) and _TIMESTAMP_RE.fullmatch(value) is not None,
        f"{path}: expected RFC3339 timestamp with seconds and timezone",
    )
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise F502LenderReturnError(f"{path}: invalid RFC3339 timestamp") from exc
    _require(
        parsed.tzinfo is not None and parsed.utcoffset() is not None,
        f"{path}: timezone is required",
    )
    return cast(str, value)


def _require_currency_code(value: Any, path: str) -> str:
    """Require a transactional code from the frozen current ISO-4217 list."""

    _require(
        isinstance(value, str) and value in _CURRENT_ISO_4217_CODES,
        f"{path}: expected current ISO-4217 code",
    )
    _require(
        value not in _NON_TRANSACTIONAL_ISO_4217_CODES,
        f"{path}: ISO-4217 test/no-currency code is not transactional",
    )
    return cast(str, value)


def _require_string_list(value: Any, path: str) -> list[str]:
    """Require a duplicate-free list of non-empty strings with controlled errors."""

    _require(isinstance(value, list), f"{path}: expected list")
    result = cast(list[Any], value)
    _require(
        all(_is_nonempty_string(item) for item in result),
        f"{path}: every member must be a non-empty string",
    )
    strings = cast(list[str], result)
    _require(len(strings) == len(set(strings)), f"{path}: duplicate member")
    return strings


def _normalized_path_identity_parts(path: Path) -> tuple[str, ...]:
    """Return conservative NFC/casefold components for an existing path."""

    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise F502LenderReturnError("protected path identity is unavailable") from exc
    return tuple(
        unicodedata.normalize("NFC", component).casefold()
        for component in resolved.parts
    )


def _path_is_same_or_descendant(path: Path, root: Path) -> bool:
    """Detect public-root overlap across case, Unicode, symlink, and samefile aliases."""

    path_parts = _normalized_path_identity_parts(path)
    root_parts = _normalized_path_identity_parts(root)
    if path_parts[: len(root_parts)] == root_parts:
        return True

    try:
        if path.samefile(root):
            return True
        return any(ancestor.samefile(root) for ancestor in path.resolve().parents)
    except OSError:
        return False


def _repository_worktree_roots() -> tuple[Path, ...]:
    """Return every worktree that shares this public repository's common Git dir."""

    git_environment = os.environ.copy()
    for key in _GIT_ROUTING_ENVIRONMENT_KEYS:
        git_environment.pop(key, None)
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain", "-z"],
            cwd=REPO_ROOT,
            env=git_environment,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError, UnicodeError) as exc:
        raise F502LenderReturnError(
            "public repository worktree inventory is unavailable"
        ) from exc
    root_paths = [
        Path(token.removeprefix("worktree "))
        for token in result.stdout.split("\0")
        if token.startswith("worktree ")
    ]
    _require(
        all(root.is_absolute() for root in root_paths),
        "public repository worktree inventory contains a relative path",
    )
    try:
        roots = tuple(root.resolve(strict=True) for root in root_paths)
    except OSError as exc:
        raise F502LenderReturnError(
            "public repository worktree inventory contains an unreadable path"
        ) from exc
    _require(bool(roots), "public repository worktree inventory is empty")
    _require(
        any(_path_is_same_or_descendant(REPO_ROOT, root) for root in roots),
        "validator checkout is absent from the public worktree inventory",
    )
    return roots


def _require_path_outside_public_worktrees(path: Path, *, label: str) -> Path:
    _require(path.is_absolute(), f"{label} must be an absolute path")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise F502LenderReturnError(f"{label}: path is unavailable") from exc
    for root in _repository_worktree_roots():
        _require(
            not _path_is_same_or_descendant(path, root),
            f"{label} must be outside every public repository worktree",
        )
    return resolved


def _read_utf8_bytes(path: Path, *, label: str) -> tuple[bytes, str]:
    try:
        raw_bytes = path.read_bytes()
        text = raw_bytes.decode("utf-8", errors="strict")
    except (OSError, UnicodeError) as exc:
        raise F502LenderReturnError(f"{label}: unreadable UTF-8 input") from exc
    return raw_bytes, text


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
            _require_valid_date(value, path)
        if key.endswith("_timestamp") or key == "timestamp":
            _require_valid_timestamp(value, path)
        if key in _CURRENCY_SCALAR_KEYS and isinstance(value, str):
            _require_currency_code(value, path)
        if key.endswith("currencies") and isinstance(value, list):
            currencies = _require_string_list(value, path)
            for index, currency in enumerate(currencies):
                _require_currency_code(currency, f"{path}[{index}]")


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
        if (
            evidence_id is None
            and mode != "closure_candidate"
            and _is_blank_template_row(record)
        ):
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
        if (
            citation_id is None
            and mode != "closure_candidate"
            and _is_blank_template_row(record)
        ):
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
    if isinstance(value, str):
        _require(
            not _is_confirmed_placeholder(value),
            f"{path}: confirmed value cannot be an unknown placeholder",
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
                _require_currency_code(value, f"{requirement_id}.value")
        evidence_refs = _require_string_list(
            record.get("evidence_refs"), f"{requirement_id}.evidence_refs"
        )
        citation_ids = _require_string_list(
            record.get("claim_citation_ids"),
            f"{requirement_id}.claim_citation_ids",
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
            if status == "not_applicable":
                _require(
                    requirement_id not in _NOT_APPLICABLE_PROHIBITED_REQUIREMENT_IDS,
                    f"{requirement_id}: this transaction fact cannot be not_applicable",
                )
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


def _validate_evidence_integrity(
    evidence: Mapping[str, Mapping[str, Any]],
) -> None:
    """Require complete claim-level integrity metadata for every admitted item."""

    evidence_ids = set(evidence)
    for evidence_id, record in evidence.items():
        for field in (
            "exact_title",
            "document_type",
            "execution_status",
            "version",
            "effective_date",
            "amendment_and_waiver_status",
            "governing_law_relevance",
            "retained_path_or_stable_url",
            "acquisition_date",
            "sha256",
            "confidentiality",
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
        parties = _require_string_list(
            record.get("issuer_or_parties"),
            f"evidence {evidence_id}.issuer_or_parties",
        )
        _require(bool(parties), f"evidence {evidence_id}.issuer_or_parties: required")
        _require(
            _SHA256_RE.fullmatch(cast(str, record["sha256"])) is not None,
            f"evidence {evidence_id}: invalid sha256",
        )
        for field in ("supersedes_evidence_ids", "superseded_by_evidence_ids"):
            references = _require_string_list(
                record.get(field), f"evidence {evidence_id}.{field}"
            )
            _require(
                set(references) <= evidence_ids,
                f"evidence {evidence_id}.{field}: unknown evidence",
            )
            _require(
                evidence_id not in references,
                f"evidence {evidence_id}.{field}: self-reference",
            )
        limitations = _require_string_list(
            record.get("limitations"), f"evidence {evidence_id}.limitations"
        )
        if record.get("review_disposition") == "accepted_with_qualifications":
            _require(
                bool(limitations),
                f"evidence {evidence_id}.limitations: qualification required",
            )
        original_id = record.get("controlling_original_evidence_id")
        if original_id is not None:
            _require(
                _is_nonempty_string(original_id),
                f"evidence {evidence_id}.controlling_original_evidence_id: invalid",
            )
            _require(
                original_id in evidence_ids and original_id != evidence_id,
                f"evidence {evidence_id}.controlling_original_evidence_id: unknown or self-referential",
            )
        for superseded_id in cast(list[str], record["supersedes_evidence_ids"]):
            _require(
                evidence_id
                in cast(
                    list[Any], evidence[superseded_id]["superseded_by_evidence_ids"]
                ),
                f"evidence {evidence_id}: supersession link is not reciprocal",
            )
        for superseding_id in cast(list[str], record["superseded_by_evidence_ids"]):
            _require(
                evidence_id
                in cast(list[Any], evidence[superseding_id]["supersedes_evidence_ids"]),
                f"evidence {evidence_id}: superseded-by link is not reciprocal",
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
        if record["status"] == "not_applicable":
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
    document: Mapping[str, Any],
    *,
    evidence: Mapping[str, Mapping[str, Any]],
    citation_ids: set[str],
    facility_ids: set[str],
    mode: ValidationMode,
) -> list[Mapping[str, Any]]:
    conflicts = document["conflicts_and_open_items"]
    _require(isinstance(conflicts, list), "$.conflicts_and_open_items: expected list")
    indexed: set[str] = set()
    retained: list[Mapping[str, Any]] = []
    for index, conflict in enumerate(conflicts):
        _require(isinstance(conflict, Mapping), f"conflict[{index}]: expected mapping")
        conflict_id = conflict.get("conflict_id")
        blank_placeholder = conflict == {
            "conflict_id": None,
            "requirement_ids": [],
            "facility_ids": [],
            "evidence_ids": [],
            "description": None,
            "order_of_precedence_analysis": None,
            "resolution_text": None,
            "resolution_evidence_ids": [],
            "resolution_citation_ids": [],
            "resolution_owner": None,
            "target_resolution_date": None,
            "status": "open",
        }
        if mode == "template" and blank_placeholder:
            continue
        _require(
            _is_nonempty_string(conflict_id), f"conflict[{index}].conflict_id: required"
        )
        conflict_id = cast(str, conflict_id)
        _require(conflict_id not in indexed, f"duplicate conflict_id {conflict_id}")
        indexed.add(conflict_id)
        requirement_ids = _require_string_list(
            conflict.get("requirement_ids"), f"{conflict_id}.requirement_ids"
        )
        conflict_evidence_ids = _require_string_list(
            conflict.get("evidence_ids"), f"{conflict_id}.evidence_ids"
        )
        resolution_evidence_ids = _require_string_list(
            conflict.get("resolution_evidence_ids"),
            f"{conflict_id}.resolution_evidence_ids",
        )
        resolution_citation_ids = _require_string_list(
            conflict.get("resolution_citation_ids"),
            f"{conflict_id}.resolution_citation_ids",
        )
        conflict_facility_ids = _require_string_list(
            conflict.get("facility_ids"), f"{conflict_id}.facility_ids"
        )
        _require(bool(requirement_ids), f"{conflict_id}: requirement_ids required")
        _require(
            set(requirement_ids) <= ALL_REQUIREMENT_IDS,
            f"{conflict_id}: unknown requirement",
        )
        _require(
            set(conflict_evidence_ids) <= set(evidence),
            f"{conflict_id}: unknown evidence",
        )
        _require(
            set(resolution_evidence_ids) <= set(evidence),
            f"{conflict_id}: unknown resolution evidence",
        )
        _require(
            set(resolution_citation_ids) <= citation_ids,
            f"{conflict_id}: unknown resolution citation",
        )
        _require(
            set(conflict_facility_ids) <= facility_ids,
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
        if mode == "closure_candidate":
            _require(
                conflict.get("status") == "resolved",
                f"{conflict_id}: open conflict blocks closure candidate",
            )
            _require(
                _is_nonempty_string(conflict.get("resolution_text")),
                f"{conflict_id}: resolution text required",
            )
            _require(
                _is_nonempty_string(conflict.get("order_of_precedence_analysis")),
                f"{conflict_id}: order-of-precedence analysis required",
            )
            _require(
                bool(resolution_evidence_ids) and bool(resolution_citation_ids),
                f"{conflict_id}: resolution evidence and citations required",
            )
            for evidence_id in resolution_evidence_ids:
                _require_confirmed_evidence_eligible(evidence_id, evidence[evidence_id])
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


def _validate_private_ingress_manifest(
    path: Path,
    *,
    lender_return_sha256: str,
    evidence: Mapping[str, Mapping[str, Any]],
) -> str:
    """Bind closure evidence to retained bytes reviewed outside the lender return."""

    resolved_manifest = _require_path_outside_public_worktrees(
        path, label="private ingress manifest"
    )
    _manifest_bytes, manifest_text = _read_utf8_bytes(
        resolved_manifest, label="private ingress manifest"
    )
    manifest = _load_one_mapping(manifest_text, label="private ingress manifest")
    _validate_json_safe_scalars(manifest)
    _validate_named_scalar_contracts(manifest)
    _require(
        set(manifest) == _PRIVATE_INGRESS_MANIFEST_KEYS,
        "private ingress manifest has wrong fields",
    )
    _require(
        manifest.get("schema_version") == PRIVATE_INGRESS_MANIFEST_SCHEMA_VERSION,
        "private ingress manifest has wrong schema_version",
    )
    _require(
        manifest.get("lender_return_sha256") == lender_return_sha256,
        "private ingress manifest does not bind the returned file bytes",
    )
    _require(
        _is_nonempty_string(manifest.get("custodian_role")),
        "private ingress manifest custodian_role is required",
    )
    ingress_timestamp = manifest.get("ingress_timestamp")
    _require_valid_timestamp(
        ingress_timestamp, "private ingress manifest ingress_timestamp"
    )
    records = manifest.get("evidence_records")
    _require(
        isinstance(records, list),
        "private ingress manifest evidence_records must be a list",
    )
    indexed: dict[str, Mapping[str, Any]] = {}
    for index, candidate in enumerate(cast(list[Any], records)):
        _require(
            isinstance(candidate, Mapping),
            f"private ingress evidence record {index} must be a mapping",
        )
        record = cast(Mapping[str, Any], candidate)
        _require(
            set(record) == _PRIVATE_INGRESS_EVIDENCE_KEYS,
            f"private ingress evidence record {index} has wrong fields",
        )
        evidence_id = record.get("evidence_id")
        _require(
            _is_nonempty_string(evidence_id),
            f"private ingress evidence record {index} requires evidence_id",
        )
        evidence_id = cast(str, evidence_id)
        _require(
            evidence_id in evidence,
            f"private ingress manifest has unknown evidence {evidence_id}",
        )
        _require(
            evidence_id not in indexed,
            f"private ingress manifest duplicates evidence {evidence_id}",
        )
        retained_path_value = record.get("retained_path")
        _require(
            _is_nonempty_string(retained_path_value),
            f"private ingress evidence {evidence_id} retained_path is required",
        )
        retained_path = Path(cast(str, retained_path_value))
        _require(
            retained_path.is_absolute(),
            f"private ingress evidence {evidence_id} retained_path must be absolute",
        )
        resolved_evidence_path = _require_path_outside_public_worktrees(
            retained_path, label=f"private ingress evidence {evidence_id}"
        )
        try:
            retained_bytes = resolved_evidence_path.read_bytes()
        except OSError as exc:
            raise F502LenderReturnError(
                f"private ingress evidence {evidence_id} is unreadable"
            ) from exc
        retained_sha256 = hashlib.sha256(retained_bytes).hexdigest()
        _require(
            record.get("sha256") == retained_sha256,
            f"private ingress evidence {evidence_id} raw sha256 mismatch",
        )
        _require(
            type(record.get("byte_count")) is int
            and record.get("byte_count") == len(retained_bytes),
            f"private ingress evidence {evidence_id} byte_count mismatch",
        )
        catalog_record = evidence[evidence_id]
        _require(
            catalog_record.get("sha256") == retained_sha256,
            f"evidence catalog {evidence_id} does not bind retained bytes",
        )
        catalog_path = catalog_record.get("retained_path_or_stable_url")
        _require(
            catalog_path == str(resolved_evidence_path),
            f"evidence catalog {evidence_id} retained path mismatch",
        )
        for field in _INGRESS_BOUND_EVIDENCE_FIELDS:
            _require(
                record.get(field) == catalog_record.get(field),
                f"private ingress evidence {evidence_id}.{field} mismatch",
            )
        _require(
            _is_nonempty_string(record.get("document_type")),
            f"private ingress evidence {evidence_id}.document_type is required",
        )
        _require(
            isinstance(record.get("issuer_or_parties"), list)
            and bool(record["issuer_or_parties"])
            and all(
                _is_nonempty_string(party)
                for party in cast(list[Any], record["issuer_or_parties"])
            ),
            f"private ingress evidence {evidence_id}.issuer_or_parties is required",
        )
        document_type = cast(str, record["document_type"])
        normalized_document_type = document_type.strip().lower()
        _require(
            not any(
                token in normalized_document_type
                for token in _PROHIBITED_CLOSURE_DOCUMENT_TYPE_TOKENS
            ),
            f"private ingress evidence {evidence_id} document_type is ineligible",
        )
        _require_confirmed_evidence_eligible(evidence_id, record)
        indexed[evidence_id] = record
    _require(
        set(indexed) == set(evidence),
        "private ingress manifest must bind every catalogued evidence record",
    )
    return cast(str, manifest["custodian_role"])


def validate_f5_02_lender_return(
    path: Path,
    *,
    template_path: Path,
    mode: ValidationMode = "structural",
    private_ingress_manifest_path: Path | None = None,
) -> F502ValidationSummary:
    """Validate one confidential lender return and emit a non-secret receipt.

    Args:
        path: Private path to the returned YAML. Do not place it in the repository.
        template_path: Immutable public blank template defining the versioned shape.
        mode: ``template`` for the public blank, ``structural`` for partial returns,
            or ``closure_candidate`` for a fully evidenced confirmation package.
        private_ingress_manifest_path: Custodian-produced manifest that binds every
            closure-candidate evidence record to retained bytes outside the repository.

    Returns:
        A compact receipt that contains no lender-entered values or identities.

    Raises:
        F502LenderReturnError: If parsing, schema, provenance, or protected controls fail.
    """

    _require(
        isinstance(mode, str)
        and mode in {"template", "structural", "closure_candidate"},
        "invalid validation mode",
    )
    try:
        canonical_template = CANONICAL_TEMPLATE_PATH.resolve(strict=True)
        supplied_template = template_path.resolve(strict=True)
    except OSError as exc:
        raise F502LenderReturnError("canonical template path is unavailable") from exc
    _require(
        supplied_template == canonical_template,
        "template_path must be the canonical public blank template",
    )
    if mode == "template":
        try:
            resolved_path = path.resolve(strict=True)
        except OSError as exc:
            raise F502LenderReturnError("template-mode path is unavailable") from exc
        _require(
            path.absolute() == canonical_template
            and resolved_path == canonical_template,
            "template mode is restricted to the canonical public blank template",
        )
    else:
        resolved_path = _require_path_outside_public_worktrees(
            path, label="confidential lender return"
        )
    raw_bytes, text = _read_utf8_bytes(resolved_path, label="lender return")
    _template_bytes, template_text = _read_utf8_bytes(
        canonical_template, label="canonical template"
    )
    lender_return_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    document = _load_one_mapping(text, label="lender return")
    template = _load_one_mapping(template_text, label="canonical template")
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
        evidence=evidence,
        citation_ids=set(citations),
        facility_ids=facility_ids,
        mode=mode,
    )
    status_counts = _validate_requirement_records(
        contexts,
        evidence=evidence,
        citations=citations,
        conflicts=conflicts,
        mode=mode,
    )
    _validate_multi_entity_ids(contexts, mode=mode)
    _validate_evidence_integrity(evidence)

    bound_custodian_role: str | None = None
    if mode == "closure_candidate":
        _require_valid_date(
            document_control.get("evidence_cutoff"),
            "document_control.evidence_cutoff",
        )
        _require(
            private_ingress_manifest_path is not None,
            "closure_candidate requires a private ingress manifest",
        )
        bound_custodian_role = _validate_private_ingress_manifest(
            cast(Path, private_ingress_manifest_path),
            lender_return_sha256=lender_return_sha256,
            evidence=evidence,
        )
    else:
        _require(
            private_ingress_manifest_path is None,
            "private ingress manifest is only permitted for closure_candidate mode",
        )

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
        sha256=lender_return_sha256,
        facility_count=facility_count,
        requirement_record_count=len(contexts),
        evidence_count=len(evidence),
        citation_count=len(citations),
        conflict_count=len(conflicts),
        status_counts=status_counts,
        bound_custodian_role=bound_custodian_role,
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
