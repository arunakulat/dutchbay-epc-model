"""Fail-closed controls for the lender-fillable F5-02 evidence pack."""

from __future__ import annotations

import re
import subprocess
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest
import yaml

from analysis_tools.f5_02_lender_return import (
    ALL_REQUIREMENT_IDS,
    F502LenderReturnError,
    validate_f5_02_lender_return,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER_INPUT_ROOT = REPO_ROOT / "docs" / "audit" / "lender-input"
TEMPLATE = LENDER_INPUT_ROOT / "DUTCHBAY_F5_02_LENDER_CONFIRMATION_TEMPLATE_v1.yaml"
INTERNAL_DECISION = (
    LENDER_INPUT_ROOT / "DUTCHBAY_F5_02_INTERNAL_DECISION_RECORD_TEMPLATE_v1.yaml"
)
CHECKLIST = (
    LENDER_INPUT_ROOT / "DUTCHBAY_1110_NONCANONICAL_QA_AND_REINGRESS_CHECKLIST_v1.md"
)

REQUIRED_NOT_RUN_CONTROLS = {
    "P4-CFG-1-SCHEMA-GUARD",
    "P4-CFG-2-YAML-SAFE-LOAD",
    "P4-F1-CI-GATE-RUNS",
    "P5-REPRO-A14-001",
    "P5-REPRO-C1-001",
    "P5-REPRO-C2-001",
    "P5-REPRO-C8-001",
    "P5-REPRO-D4-001",
    "P5-REPRO-LLCR-001",
    "P5-REPRO-RISK-001",
    "P5-REPRO-WIND-001",
}

UNAVAILABLE_CONTROL_IDS = {
    "P2-SCRATCH-R1_F1_CHECK",
    "P2-SCRATCH-R1_F1_CHECK2",
    "P2-SCRATCH-R1_F1_CHECK3",
    "P2-SCRATCH-R2_CHECK",
    "P2-SCRATCH-R2_FEE",
}

RECONSTRUCTED_CONTROL_IDS = {
    "P2-REPRO-F1-01-SCALE-V1",
    "P2-REPRO-F1-05-CAPEX-TIMING-V1",
    "P2-REPRO-F1-CANON-TIMELINE-V1",
    "P2-REPRO-F2-DEBT-SEAMS-V1",
    "P2-REPRO-F2-FEE-BASIS-V1",
}


def _load_template() -> dict[str, Any]:
    document = yaml.safe_load(TEMPLATE.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def _walk_mappings(value: Any) -> Iterator[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        yield value
        for child in value.values():
            yield from _walk_mappings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_mappings(child)


def _requirement_records(document: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [
        mapping
        for mapping in _walk_mappings(document)
        if {"requirement_id", "status", "evidence_refs", "claim_citation_ids"}
        <= mapping.keys()
    ]


def _write_candidate(tmp_path: Path, document: Mapping[str, Any]) -> Path:
    path = tmp_path / "private_return.yaml"
    path.write_text(
        yaml.safe_dump(dict(document), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path


def _record(document: Mapping[str, Any], requirement_id: str) -> dict[str, Any]:
    for record in _requirement_records(document):
        if record["requirement_id"] == requirement_id:
            assert isinstance(record, dict)
            return record
    raise AssertionError(f"missing requirement {requirement_id}")


def _add_eligible_evidence_and_citation(
    document: dict[str, Any], requirement_id: str
) -> dict[str, Any]:
    evidence = document["evidence_catalog"][0]
    evidence.update(
        {
            "evidence_id": "EVIDENCE-1",
            "exact_title": "Authenticated controlling instrument",
            "document_type": "executed_agreement",
            "issuer_or_parties": ["Issuer"],
            "execution_status": "executed_and_effective",
            "version": "1",
            "effective_date": "2026-08-24",
            "amendment_and_waiver_status": "current",
            "governing_law_relevance": "controlling",
            "retained_path_or_stable_url": "private:evidence/EVIDENCE-1",
            "acquisition_date": "2026-08-24",
            "sha256": "a" * 64,
            "confidentiality": "confidential",
            "evidence_tier": "tier_1",
            "source_form": "verified_executed_original",
            "authentication_method": "signature_and_effectiveness_verified",
            "authenticated_by": "Evidence custodian",
            "authentication_date": "2026-08-24",
            "reviewed_by": "Independent reviewer",
            "reviewer_independence": "independent",
            "review_scope": "source to claim",
            "review_date": "2026-08-24",
            "review_disposition": "accepted",
        }
    )
    citation = document["claim_citations"][0]
    citation.update(
        {
            "citation_id": "CITATION-1",
            "requirement_id": requirement_id,
            "facility_id": None,
            "evidence_id": "EVIDENCE-1",
            "exact_page": "1",
            "exact_section": "Parties",
            "exact_clause": "1.1",
            "extracted_value_or_text": "Controlled extracted value",
            "respondent_name": "Authorized respondent",
            "respondent_role": "Authorized representative",
            "respondent_authority_reference": "AUTH-1",
        }
    )
    record = _record(document, requirement_id)
    record["status"] = "confirmed"
    record["evidence_refs"] = ["EVIDENCE-1"]
    record["claim_citation_ids"] = ["CITATION-1"]
    return record


def test_blank_template_passes_executable_template_validation() -> None:
    summary = validate_f5_02_lender_return(
        TEMPLATE,
        template_path=TEMPLATE,
        mode="template",
    )

    assert summary.facility_count == 1
    assert summary.requirement_record_count == 53
    assert summary.evidence_count == 0
    assert summary.citation_count == 0
    assert summary.status_counts["unknown"] == 53
    assert summary.canonical_binding_status == "blocked"
    assert summary.release_status == "HOLD"


@pytest.mark.parametrize(
    "invalid_text",
    [
        "a: 1\na: 2\n",
        "a: &value 1\nb: *value\n",
        "a: 1\n---\nb: 2\n",
        "!!python/object/apply:os.system ['false']\n",
    ],
)
def test_validator_rejects_unsafe_or_ambiguous_yaml(
    tmp_path: Path,
    invalid_text: str,
) -> None:
    path = tmp_path / "invalid.yaml"
    path.write_text(invalid_text, encoding="utf-8")

    with pytest.raises(F502LenderReturnError):
        validate_f5_02_lender_return(path, template_path=TEMPLATE, mode="template")


def test_template_contains_each_requirement_once_and_unanswered() -> None:
    records = _requirement_records(_load_template())
    requirement_ids = [record["requirement_id"] for record in records]

    assert len(requirement_ids) == len(ALL_REQUIREMENT_IDS) == 53
    assert set(requirement_ids) == ALL_REQUIREMENT_IDS
    assert len(requirement_ids) == len(set(requirement_ids))
    assert {record["status"] for record in records} == {"unknown"}
    assert all(record["evidence_refs"] == [] for record in records)
    assert all(record["claim_citation_ids"] == [] for record in records)


def test_lender_template_remains_noncanonical_private_and_hold_preserving() -> None:
    document = _load_template()
    controls = document["document_control"]
    requirements_register = controls["requirements_register"]
    privacy = document["privacy_and_return_handling"]
    repository_controls = document["repository_owned_controls"]

    assert controls["purpose"] == "transaction_evidence_questionnaire_only"
    assert controls["release_status"] == "HOLD"
    assert controls["canonical_model_input_authorized"] is False
    assert requirements_register["sha256"] == (
        "7f3199867ae6aaae2e7365b0cb15fe7ca81b3348060e9ac443622fbc231a9416"
    )
    assert requirements_register["requirement_count"] == 53
    assert privacy["completed_return_public_commit_allowed"] is False
    assert repository_controls["edit_allowed_by_lender_or_transaction_team"] is False
    assert repository_controls["canonical_binding_status"] == "blocked"
    assert repository_controls["board_lender_release_status"] == "HOLD"
    assert repository_controls["canonical_model_input_authorized"] is False
    assert repository_controls["canonical_binding_d4_allowed"] is False
    assert (
        repository_controls["rebaseline_and_external_regeneration_d5_allowed"] is False
    )
    assert "scenarios" not in TEMPLATE.parts


def test_public_receipt_has_exactly_the_five_permitted_fields() -> None:
    summary = validate_f5_02_lender_return(
        TEMPLATE,
        template_path=TEMPLATE,
        mode="template",
    )
    receipt = summary.to_public_receipt(
        custodian_role="evidence_custodian",
        receipt_timestamp="2026-08-24T12:00:00+05:30",
    )

    assert set(receipt) == {
        "document_id",
        "custodian_role",
        "receipt_timestamp",
        "confidentiality_classification",
        "sha256",
    }


def test_structural_return_inside_public_repository_is_rejected() -> None:
    with pytest.raises(F502LenderReturnError, match="outside the public repository"):
        validate_f5_02_lender_return(
            TEMPLATE,
            template_path=TEMPLATE,
            mode="structural",
        )


def test_template_has_field_level_provenance_and_separate_authority_signoffs() -> None:
    document = _load_template()
    catalog_record = document["evidence_catalog"][0]
    citation_record = document["claim_citations"][0]
    signoff = document["signoff"]

    assert {
        "evidence_id",
        "exact_title",
        "document_type",
        "effective_date",
        "amendment_and_waiver_status",
        "retained_path_or_stable_url",
        "acquisition_date",
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
        "limitations",
    } <= catalog_record.keys()
    assert {
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
    } == citation_record.keys()
    assert {
        "borrower_authorized_representative",
        "facility_agent_or_lender_representative",
        "sri_lankan_legal_counsel",
        "tax_adviser",
        "authorized_dealer",
    } == signoff.keys()


def test_multi_entity_values_and_units_are_explicit() -> None:
    document = _load_template()
    records = {
        record["requirement_id"]: record for record in _requirement_records(document)
    }

    assert set(records["F502-EV-002"]["value"][0]) >= {
        "party_id",
        "exact_legal_name",
        "jurisdiction",
        "tax_residence",
        "regulatory_status",
        "transaction_role",
    }
    assert set(records["F502-EV-019"]["value"][0]) >= {
        "utilization_id",
        "commitment_currency_amount_decimal_string",
        "commitment_currency_unit_scale",
        "contractual_fx_fixing",
        "native_principal_amount_decimal_string",
        "native_principal_unit_scale",
    }
    assert set(records["F502-EV-072"]["value"][0]) >= {
        "instrument_id",
        "instrument_type",
        "linked_facility_or_exposure_id",
        "pay_currency",
        "pay_amount_decimal_string",
        "receive_currency",
        "receive_amount_decimal_string",
        "unit_scale",
    }
    assert set(records["F502-EV-075"]["value"][0]) >= {
        "reserve_or_facility_id",
        "currency",
        "target_or_limit_amount_decimal_string",
        "unit_scale",
    }


def test_validator_rejects_lender_attempt_to_change_hold(tmp_path: Path) -> None:
    document = _load_template()
    document["repository_owned_controls"]["board_lender_release_status"] = "RELEASED"
    path = _write_candidate(tmp_path, document)

    with pytest.raises(F502LenderReturnError, match="repository_owned_controls"):
        validate_f5_02_lender_return(path, template_path=TEMPLATE, mode="template")


def test_validator_rejects_confirmed_claim_without_evidence(tmp_path: Path) -> None:
    document = _load_template()
    document["transaction"]["borrower"]["status"] = "confirmed"
    path = _write_candidate(tmp_path, document)

    with pytest.raises(F502LenderReturnError, match="evidence and citations required"):
        validate_f5_02_lender_return(path, template_path=TEMPLATE, mode="template")


@pytest.mark.parametrize("blank_kind", ["null_mapping", "empty_list", "null_row"])
def test_validator_rejects_confirmed_claim_with_blank_value(
    tmp_path: Path,
    blank_kind: str,
) -> None:
    document = _load_template()
    if blank_kind == "null_mapping":
        record = _add_eligible_evidence_and_citation(document, "F502-EV-001")
    else:
        record = _add_eligible_evidence_and_citation(document, "F502-EV-002")
        if blank_kind == "empty_list":
            record["value"] = []
    path = _write_candidate(tmp_path, document)

    with pytest.raises(
        F502LenderReturnError, match="confirmed .*incomplete|confirmed list"
    ):
        validate_f5_02_lender_return(path, template_path=TEMPLATE, mode="template")


def test_validator_rejects_ineligible_synthetic_confirming_evidence(
    tmp_path: Path,
) -> None:
    document = _load_template()
    record = _add_eligible_evidence_and_citation(document, "F502-EV-001")
    record["value"].update(
        {
            "exact_legal_name": "Borrower SPV",
            "incorporation_number": "PV-1",
            "jurisdiction": "Sri Lanka",
            "tax_residence": "Sri Lanka",
            "project_spv_role": "Borrower",
        }
    )
    document["evidence_catalog"][0]["source_form"] = "analyst_generated"
    path = _write_candidate(tmp_path, document)

    with pytest.raises(F502LenderReturnError, match="source_form is not eligible"):
        validate_f5_02_lender_return(path, template_path=TEMPLATE, mode="template")


def test_validator_rejects_lossy_party_shape(tmp_path: Path) -> None:
    document = _load_template()
    document["transaction"]["lender_agent_and_trustee_parties"]["value"] = "Lender"
    path = _write_candidate(tmp_path, document)

    with pytest.raises(F502LenderReturnError, match="expected list"):
        validate_f5_02_lender_return(path, template_path=TEMPLATE, mode="template")


def test_validator_rejects_duplicate_multi_entity_ids(tmp_path: Path) -> None:
    document = _load_template()
    parties = document["transaction"]["lender_agent_and_trustee_parties"]["value"]
    parties[0]["party_id"] = "PARTY-1"
    parties.append(dict(parties[0]))
    path = _write_candidate(tmp_path, document)

    with pytest.raises(F502LenderReturnError, match="duplicate party_id"):
        validate_f5_02_lender_return(path, template_path=TEMPLATE, mode="template")


@pytest.mark.parametrize(
    ("section", "field"),
    [
        ("respondent_authority", "authority_evidence_id"),
        ("sri_lankan_legal_counsel", "opinion_evidence_id"),
        ("tax_adviser", "opinion_evidence_id"),
        ("authorized_dealer", "confirmation_evidence_id"),
    ],
)
def test_validator_rejects_unknown_embedded_evidence_references(
    tmp_path: Path,
    section: str,
    field: str,
) -> None:
    document = _load_template()
    if section == "respondent_authority":
        document["submission"][section][field] = "MISSING-EVIDENCE"
    else:
        document["signoff"][section][field] = "MISSING-EVIDENCE"
    path = _write_candidate(tmp_path, document)

    with pytest.raises(F502LenderReturnError, match="unknown evidence"):
        validate_f5_02_lender_return(path, template_path=TEMPLATE, mode="template")


def test_validator_rejects_unknown_nested_hedge_evidence(tmp_path: Path) -> None:
    document = _load_template()
    hedge = _record(document, "F502-EV-072")["value"][0]
    hedge["governing_agreement_evidence_id"] = "MISSING-EVIDENCE"
    hedge["evidence_refs"] = ["ALSO-MISSING"]
    path = _write_candidate(tmp_path, document)

    with pytest.raises(F502LenderReturnError, match="unknown evidence"):
        validate_f5_02_lender_return(path, template_path=TEMPLATE, mode="template")


def test_validator_rejects_implicit_yaml_date(tmp_path: Path) -> None:
    text = TEMPLATE.read_text(encoding="utf-8").replace(
        'prepared_date: "2026-08-24"',
        "prepared_date: 2026-08-24",
    )
    path = tmp_path / "implicit_date.yaml"
    path.write_text(text, encoding="utf-8")

    with pytest.raises(F502LenderReturnError, match="non-JSON YAML type date"):
        validate_f5_02_lender_return(path, template_path=TEMPLATE, mode="template")


@pytest.mark.parametrize("bad_value", [False, 83, 1.23])
def test_validator_rejects_non_string_legal_name(
    tmp_path: Path,
    bad_value: object,
) -> None:
    document = _load_template()
    document["transaction"]["borrower"]["value"]["exact_legal_name"] = bad_value
    path = _write_candidate(tmp_path, document)

    with pytest.raises(F502LenderReturnError, match="expected a quoted string"):
        validate_f5_02_lender_return(path, template_path=TEMPLATE, mode="template")


@pytest.mark.parametrize("bad_currency", [False, 123, "NO", "US"])
def test_validator_rejects_non_iso_or_non_string_currency(
    tmp_path: Path,
    bad_currency: object,
) -> None:
    document = _load_template()
    record = _record(document, "F502-EV-010")
    record["value"] = bad_currency
    path = _write_candidate(tmp_path, document)

    with pytest.raises(F502LenderReturnError, match="quoted string|ISO-4217"):
        validate_f5_02_lender_return(path, template_path=TEMPLATE, mode="template")


def test_validator_rejects_unlabelled_numeric_amount(tmp_path: Path) -> None:
    document = _load_template()
    value = document["facilities"][0]["amount_availability_and_drawdown"][
        "native_limits_reallocations_and_caps"
    ]["value"]
    value["commitment_amount_decimal_string"] = 500
    path = _write_candidate(tmp_path, document)

    with pytest.raises(
        F502LenderReturnError, match="quoted string|plain decimal string"
    ):
        validate_f5_02_lender_return(path, template_path=TEMPLATE, mode="template")


def test_public_repository_contains_only_the_blank_lender_return() -> None:
    matches: list[Path] = []
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )
    tracked_and_candidate_paths = [
        REPO_ROOT / relative
        for relative in result.stdout.decode("utf-8").rstrip("\0").split("\0")
        if relative
    ]
    for path in tracked_and_candidate_paths:
        if not path.is_file() or path.stat().st_size > 5_000_000:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        yaml_signature = re.search(
            r"(?m)^schema_version:\s*dutchbay\.f5_02_lender_confirmation\.v1\s*$",
            text,
        ) is not None or all(
            re.search(pattern, text) is not None
            for pattern in (
                r"(?m)^transaction:\s*$",
                r"(?m)^facilities:\s*$",
                r"(?m)^evidence_catalog:\s*$",
                r"(?m)^\s*requirement_id:\s*F502-EV-001\s*$",
                r"(?m)^\s*requirement_id:\s*F502-EV-084\s*$",
            )
        )
        json_signature = all(
            re.search(pattern, text) is not None
            for pattern in (
                r'(?m)^\s*"transaction"\s*:\s*\{',
                r'(?m)^\s*"facilities"\s*:\s*\[',
                r'(?m)^\s*"evidence_catalog"\s*:\s*\[',
                r'(?m)^\s*"requirement_id"\s*:\s*"F502-EV-001"',
                r'(?m)^\s*"requirement_id"\s*:\s*"F502-EV-084"',
            )
        )
        filename_signature = "f5_02" in path.name.lower() and any(
            token in path.name.lower() for token in ("returned", "completed")
        )
        if yaml_signature or json_signature or filename_signature:
            matches.append(path)

    assert matches == [TEMPLATE]
    assert {record["status"] for record in _requirement_records(_load_template())} == {
        "unknown"
    }


def test_internal_decision_record_cannot_pre_authorize_canon() -> None:
    document = yaml.safe_load(INTERNAL_DECISION.read_text(encoding="utf-8"))

    assert document["document_control"]["release_status"] == "HOLD"
    assert document["document_control"]["canonical_model_input_authorized"] is False
    assert document["independent_review"]["disposition"] == "not_reviewed"
    assert document["approval"]["release_authority"]["decision"] == "HOLD"
    assert document["protected_controls"]["canonical_binding_status"] == "blocked"
    assert document["protected_controls"]["board_lender_release_status"] == "HOLD"
    assert document["protected_controls"]["canonical_binding_d4_allowed"] is False
    assert (
        document["protected_controls"][
            "rebaseline_and_external_regeneration_d5_allowed"
        ]
        is False
    )


def test_work_programme_names_every_open_and_reconstructed_control() -> None:
    text = CHECKLIST.read_text(encoding="utf-8")

    for control_id in REQUIRED_NOT_RUN_CONTROLS:
        assert f"`{control_id}`" in text
    for old_id in UNAVAILABLE_CONTROL_IDS:
        assert f"`{old_id}`" in text
    for new_id in RECONSTRUCTED_CONTROL_IDS:
        assert f"`{new_id}`" in text

    assert "F5-01 and F5-02 remain completely separate" in text
    assert "Formal independent review requires a separate reviewer" in text
    assert "all 53 requirement IDs" in text
    assert "Never commit a completed return" in text
    assert "separate 56-row controlled ledger" in text
    assert "separate 23-row controlled gate ledger" in text
    assert "only valid release disposition is **HOLD**" in text
