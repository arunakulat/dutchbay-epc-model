"""Fail-closed controls for the lender-fillable F5-02 evidence pack."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Iterator, Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
import yaml

from analysis_tools import f5_02_lender_return as f502
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
PRIVATE_INGRESS_MANIFEST = (
    LENDER_INPUT_ROOT / "DUTCHBAY_F5_02_PRIVATE_INGRESS_MANIFEST_TEMPLATE_v1.yaml"
)
VALIDATOR_SCRIPT = REPO_ROOT / "scripts" / "validate_f5_02_lender_return.py"
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
    payload = deepcopy(dict(document))
    if payload.get("conflicts_and_open_items") == _load_template().get(
        "conflicts_and_open_items"
    ):
        payload["conflicts_and_open_items"] = []
    path = tmp_path / "private_return.yaml"
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
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


def _make_structural_document() -> dict[str, Any]:
    document = _load_template()
    record = _add_eligible_evidence_and_citation(document, "F502-EV-001")
    record["status"] = "unknown"
    record["evidence_refs"] = []
    record["claim_citation_ids"] = []
    document["claim_citations"] = []
    document["conflicts_and_open_items"] = []
    document["facilities"][0]["facility_id"] = "FACILITY-1"
    submission = document["submission"]
    submission.update(
        {
            "submission_id": "SUBMISSION-1",
            "submission_date": "2026-08-24",
            "scope_of_confirmation": "Structural completeness only",
        }
    )
    submission["prepared_by"].update(
        {
            "name": "Authorized respondent",
            "organization": "Transaction party",
            "role": "Authorized representative",
            "email": "respondent@example.invalid",
        }
    )
    submission["respondent_authority"].update(
        {
            "authority_type": "board_authority",
            "authority_reference": "AUTH-1",
            "authority_evidence_id": "EVIDENCE-1",
        }
    )
    return document


def _make_closure_candidate(tmp_path: Path) -> tuple[Path, Path]:
    document = _make_structural_document()
    document["document_control"]["evidence_cutoff"] = "2026-08-24"
    retained_evidence = tmp_path / "retained-executed-agreement.bin"
    retained_bytes = b"authenticated executed agreement fixture\n"
    retained_evidence.write_bytes(retained_bytes)
    retained_sha256 = hashlib.sha256(retained_bytes).hexdigest()
    evidence = document["evidence_catalog"][0]
    evidence["retained_path_or_stable_url"] = str(retained_evidence.resolve())
    evidence["sha256"] = retained_sha256

    citation_template = _load_template()["claim_citations"][0]
    citations: list[dict[str, Any]] = []
    mandatory_confirmed = {
        "F502-EV-001",
        "F502-EV-002",
        "F502-EV-004",
        "F502-EV-010",
        "F502-EV-012",
        "F502-EV-013",
        "F502-EV-014",
    }
    for index, record in enumerate(_requirement_records(document), start=1):
        requirement_id = str(record["requirement_id"])
        record["status"] = (
            "confirmed" if requirement_id in mandatory_confirmed else "not_applicable"
        )
        record["evidence_refs"] = ["EVIDENCE-1"]
        citation_id = f"CITATION-{index:03d}"
        record["claim_citation_ids"] = [citation_id]
        citation = deepcopy(citation_template)
        citation.update(
            {
                "citation_id": citation_id,
                "requirement_id": requirement_id,
                "facility_id": (
                    None
                    if requirement_id in f502.PROJECT_REQUIREMENT_IDS
                    else "FACILITY-1"
                ),
                "evidence_id": "EVIDENCE-1",
                "exact_page": "1",
                "exact_section": "Controlling terms",
                "exact_clause": f"fixture-{index}",
                "extracted_value_or_text": "Authenticated controlling text",
                "respondent_name": "Authorized respondent",
                "respondent_role": "Authorized representative",
                "respondent_authority_reference": "AUTH-1",
                "not_applicable_reason": (
                    None
                    if requirement_id in mandatory_confirmed
                    else "Authenticated instrument confirms no such feature applies"
                ),
            }
        )
        citations.append(citation)
        if requirement_id == "F502-EV-001":
            for key in record["value"]:
                record["value"][key] = f"Borrower {key}"
        elif requirement_id == "F502-EV-002":
            for key in record["value"][0]:
                record["value"][0][key] = f"Party {key}"
        elif requirement_id == "F502-EV-004":
            for key in record["value"]:
                record["value"][key] = f"Mapping {key}"
        elif requirement_id in {
            "F502-EV-010",
            "F502-EV-012",
            "F502-EV-013",
            "F502-EV-014",
        }:
            record["value"] = "USD"
    document["claim_citations"] = citations
    document["confirmations"] = {key: True for key in document["confirmations"]}
    for signoff in document["signoff"].values():
        for key in signoff:
            if key.endswith("_evidence_id"):
                signoff[key] = "EVIDENCE-1"
            elif key == "date":
                signoff[key] = "2026-08-24"
            else:
                signoff[key] = f"Authorized {key}"

    return_path = tmp_path / "closure-candidate.yaml"
    return_path.write_text(
        yaml.safe_dump(document, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return_sha256 = hashlib.sha256(return_path.read_bytes()).hexdigest()
    manifest = yaml.safe_load(PRIVATE_INGRESS_MANIFEST.read_text(encoding="utf-8"))
    manifest.update(
        {
            "lender_return_sha256": return_sha256,
            "custodian_role": "evidence_custodian",
            "ingress_timestamp": "2026-08-24T12:00:00+05:30",
        }
    )
    manifest_record = manifest["evidence_records"][0]
    manifest_record.update(
        {
            "evidence_id": "EVIDENCE-1",
            "retained_path": str(retained_evidence.resolve()),
            "sha256": retained_sha256,
            "byte_count": len(retained_bytes),
            "exact_title": evidence["exact_title"],
            "document_type": evidence["document_type"],
            "issuer_or_parties": evidence["issuer_or_parties"],
            "execution_status": evidence["execution_status"],
            "version": evidence["version"],
            "effective_date": evidence["effective_date"],
            "expiry_date": evidence["expiry_date"],
            "amendment_and_waiver_status": evidence["amendment_and_waiver_status"],
            "governing_law_relevance": evidence["governing_law_relevance"],
            "acquisition_date": evidence["acquisition_date"],
            "confidentiality": evidence["confidentiality"],
            "evidence_tier": evidence["evidence_tier"],
            "source_form": evidence["source_form"],
            "authentication_method": evidence["authentication_method"],
            "controlling_original_evidence_id": evidence[
                "controlling_original_evidence_id"
            ],
            "authenticated_by": evidence["authenticated_by"],
            "authentication_date": evidence["authentication_date"],
            "reviewed_by": evidence["reviewed_by"],
            "reviewer_independence": evidence["reviewer_independence"],
            "review_scope": evidence["review_scope"],
            "review_date": evidence["review_date"],
            "review_disposition": evidence["review_disposition"],
            "supersedes_evidence_ids": evidence["supersedes_evidence_ids"],
            "superseded_by_evidence_ids": evidence["superseded_by_evidence_ids"],
            "limitations": evidence["limitations"],
        }
    )
    manifest_path = tmp_path / "private-ingress-manifest.yaml"
    manifest_path.write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return return_path, manifest_path


def _looks_like_f502_return(path: Path, text: str) -> bool:
    lowered_name = path.name.lower()
    content_candidate = path.suffix.lower() in {".json", ".txt", ".yaml", ".yml"}
    schema_signature = content_candidate and (
        "dutchbay.f5_02_lender_confirmation.v1" in text
    )
    population_signature = content_candidate and all(
        token in text
        for token in (
            "F502-EV-001",
            "F502-EV-084",
            "evidence_catalog",
            "claim_citations",
            "repository_owned_controls",
        )
    )
    filename_signature = "f5_02" in lowered_name and any(
        token in lowered_name for token in ("returned", "completed")
    )
    return schema_signature or population_signature or filename_signature


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
    assert summary.bound_custodian_role is None


def test_template_mode_is_restricted_to_the_canonical_blank(tmp_path: Path) -> None:
    copied_template = tmp_path / "copied_template.yaml"
    copied_template.write_bytes(TEMPLATE.read_bytes())

    with pytest.raises(F502LenderReturnError, match="restricted to the canonical"):
        validate_f5_02_lender_return(
            copied_template,
            template_path=TEMPLATE,
            mode="template",
        )


def test_receipt_hashes_exact_source_bytes_without_newline_normalization(
    tmp_path: Path,
) -> None:
    document = _make_structural_document()
    lf_bytes = yaml.safe_dump(document, sort_keys=False, allow_unicode=True).encode(
        "utf-8"
    )
    crlf_bytes = lf_bytes.replace(b"\n", b"\r\n")
    lf_path = tmp_path / "lf.yaml"
    crlf_path = tmp_path / "crlf.yaml"
    lf_path.write_bytes(lf_bytes)
    crlf_path.write_bytes(crlf_bytes)

    lf_summary = validate_f5_02_lender_return(
        lf_path, template_path=TEMPLATE, mode="structural"
    )
    crlf_summary = validate_f5_02_lender_return(
        crlf_path, template_path=TEMPLATE, mode="structural"
    )

    assert lf_summary.sha256 == hashlib.sha256(lf_bytes).hexdigest()
    assert crlf_summary.sha256 == hashlib.sha256(crlf_bytes).hexdigest()
    assert lf_summary.sha256 != crlf_summary.sha256


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
        validate_f5_02_lender_return(path, template_path=TEMPLATE, mode="structural")


def test_template_contains_each_requirement_once_and_unanswered() -> None:
    records = _requirement_records(_load_template())
    requirement_ids = [record["requirement_id"] for record in records]

    assert len(requirement_ids) == len(ALL_REQUIREMENT_IDS) == 53
    assert set(requirement_ids) == ALL_REQUIREMENT_IDS
    assert len(requirement_ids) == len(set(requirement_ids))
    assert {record["status"] for record in records} == {"unknown"}
    assert all(record["evidence_refs"] == [] for record in records)
    assert all(record["claim_citation_ids"] == [] for record in records)


def test_currency_vocabulary_matches_the_frozen_maintenance_list_contract() -> None:
    document = _load_template()
    currency_control = document["response_contract"]["currency_code_list"]

    assert len(f502._CURRENT_ISO_4217_CODES) == 178
    assert {"LKR", "USD", "EUR", "XAD", "XCG"} <= f502._CURRENT_ISO_4217_CODES
    assert {"ZZZ", "BGN"}.isdisjoint(f502._CURRENT_ISO_4217_CODES)
    assert f502._NON_TRANSACTIONAL_ISO_4217_CODES == {"XTS", "XXX"}
    assert currency_control["retained_source_sha256"] == (
        "838dfb991648cf36df939edd5fe3811737962b75a32252847d239cedd1e291c9"
    )


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
    assert privacy["blank_private_ingress_manifest_template_public_commit_allowed"]
    assert privacy["completed_private_ingress_manifest_public_commit_allowed"] is False
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


@pytest.mark.parametrize(
    "bad_timestamp",
    [
        "2026-99-99T99:99:99+99:99",
        "2026-02-29T12:00:00+05:30",
        "2026-08-24T12:00:00",
    ],
)
def test_public_receipt_rejects_invalid_rfc3339_timestamp(
    bad_timestamp: str,
) -> None:
    summary = validate_f5_02_lender_return(
        TEMPLATE,
        template_path=TEMPLATE,
        mode="template",
    )

    with pytest.raises(F502LenderReturnError, match="timestamp"):
        summary.to_public_receipt(
            custodian_role="evidence_custodian",
            receipt_timestamp=bad_timestamp,
        )


def _validator_environment(input_path: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "PYTHONPATH": str(REPO_ROOT),
            "DUTCHBAY_F5_02_RETURN_PATH": str(input_path),
            "DUTCHBAY_F5_02_CUSTODIAN_ROLE": "evidence_custodian",
            "DUTCHBAY_F5_02_RECEIPT_TIMESTAMP": "2026-08-24T12:00:00+05:30",
        }
    )
    environment.pop("HYDRA_FULL_ERROR", None)
    return environment


def test_cli_success_leaves_no_hydra_artifacts_or_private_path_leak(
    tmp_path: Path,
) -> None:
    private_path = tmp_path / "CONFIDENTIAL_LENDER_ALPHA.yaml"
    private_path.write_text(
        yaml.safe_dump(
            _make_structural_document(), sort_keys=False, allow_unicode=True
        ),
        encoding="utf-8",
    )
    before = {path.relative_to(tmp_path) for path in tmp_path.rglob("*")}

    result = subprocess.run(
        [sys.executable, str(VALIDATOR_SCRIPT), "mode=structural"],
        cwd=tmp_path,
        env=_validator_environment(private_path),
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    receipt = json.loads(result.stdout)
    assert set(receipt) == {
        "document_id",
        "custodian_role",
        "receipt_timestamp",
        "confidentiality_classification",
        "sha256",
    }
    assert "CONFIDENTIAL_LENDER_ALPHA" not in result.stdout
    assert "CONFIDENTIAL_LENDER_ALPHA" not in result.stderr
    assert result.stderr == ""
    assert {path.relative_to(tmp_path) for path in tmp_path.rglob("*")} == before


def test_cli_failure_emits_only_stable_error_and_no_private_value(
    tmp_path: Path,
) -> None:
    document = _make_structural_document()
    document["transaction"]["borrower"]["status"] = "CONFIDENTIAL_INVALID_VALUE"
    private_path = tmp_path / "CONFIDENTIAL_LENDER_ALPHA.yaml"
    private_path.write_text(
        yaml.safe_dump(document, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    before = {path.relative_to(tmp_path) for path in tmp_path.rglob("*")}

    result = subprocess.run(
        [sys.executable, str(VALIDATOR_SCRIPT), "mode=structural"],
        cwd=tmp_path,
        env=_validator_environment(private_path),
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert json.loads(result.stderr) == {"error": "F5_02_RETURN_REJECTED"}
    assert "CONFIDENTIAL_LENDER_ALPHA" not in result.stderr
    assert "CONFIDENTIAL_INVALID_VALUE" not in result.stderr
    assert {path.relative_to(tmp_path) for path in tmp_path.rglob("*")} == before


@pytest.mark.parametrize(
    "bad_arguments",
    [
        (),
        ("mode=structural", "+unexpected_control=accepted"),
        ("mode=structural", "hydra.output_subdir=.hydra"),
        ("mode=structural", "hydra.run.dir=private-path-leak"),
    ],
)
def test_cli_rejects_every_non_contract_argument_before_hydra_side_effects(
    tmp_path: Path,
    bad_arguments: tuple[str, ...],
) -> None:
    private_path = tmp_path / "CONFIDENTIAL_LENDER_ALPHA.yaml"
    private_path.write_text(
        yaml.safe_dump(
            _make_structural_document(), sort_keys=False, allow_unicode=True
        ),
        encoding="utf-8",
    )
    before = {path.relative_to(tmp_path) for path in tmp_path.rglob("*")}

    result = subprocess.run(
        [sys.executable, str(VALIDATOR_SCRIPT), *bad_arguments],
        cwd=tmp_path,
        env=_validator_environment(private_path),
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert json.loads(result.stderr) == {"error": "F5_02_RETURN_REJECTED"}
    assert {path.relative_to(tmp_path) for path in tmp_path.rglob("*")} == before


def test_cli_rejects_relative_private_return_path(tmp_path: Path) -> None:
    private_path = tmp_path / "CONFIDENTIAL_LENDER_ALPHA.yaml"
    private_path.write_text(
        yaml.safe_dump(
            _make_structural_document(), sort_keys=False, allow_unicode=True
        ),
        encoding="utf-8",
    )
    environment = _validator_environment(private_path)
    environment["DUTCHBAY_F5_02_RETURN_PATH"] = private_path.name
    before = {path.relative_to(tmp_path) for path in tmp_path.rglob("*")}

    result = subprocess.run(
        [sys.executable, str(VALIDATOR_SCRIPT), "mode=structural"],
        cwd=tmp_path,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert json.loads(result.stderr) == {"error": "F5_02_RETURN_REJECTED"}
    assert {path.relative_to(tmp_path) for path in tmp_path.rglob("*")} == before


def test_closure_candidate_requires_and_accepts_byte_bound_private_manifest(
    tmp_path: Path,
) -> None:
    return_path, manifest_path = _make_closure_candidate(tmp_path)

    with pytest.raises(F502LenderReturnError, match="requires a private ingress"):
        validate_f5_02_lender_return(
            return_path,
            template_path=TEMPLATE,
            mode="closure_candidate",
        )

    summary = validate_f5_02_lender_return(
        return_path,
        template_path=TEMPLATE,
        mode="closure_candidate",
        private_ingress_manifest_path=manifest_path,
    )

    assert summary.mode == "closure_candidate"
    assert summary.sha256 == hashlib.sha256(return_path.read_bytes()).hexdigest()
    assert summary.canonical_binding_status == "blocked"
    assert summary.release_status == "HOLD"
    assert summary.bound_custodian_role == "evidence_custodian"

    with pytest.raises(F502LenderReturnError, match="private ingress manifest"):
        summary.to_public_receipt(
            custodian_role="different_declared_role",
            receipt_timestamp="2026-08-24T12:00:00+05:30",
        )


def test_closure_candidate_rejects_self_labelled_synthetic_evidence(
    tmp_path: Path,
) -> None:
    return_path, manifest_path = _make_closure_candidate(tmp_path)
    document = yaml.safe_load(return_path.read_text(encoding="utf-8"))
    document["evidence_catalog"][0]["document_type"] = "analyst_generated_synthetic"
    return_path.write_text(
        yaml.safe_dump(document, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["lender_return_sha256"] = hashlib.sha256(
        return_path.read_bytes()
    ).hexdigest()
    manifest["evidence_records"][0]["document_type"] = "analyst_generated_synthetic"
    manifest_path.write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    with pytest.raises(F502LenderReturnError, match="document_type is ineligible"):
        validate_f5_02_lender_return(
            return_path,
            template_path=TEMPLATE,
            mode="closure_candidate",
            private_ingress_manifest_path=manifest_path,
        )


def test_closure_candidate_requires_real_evidence_cutoff(tmp_path: Path) -> None:
    return_path, manifest_path = _make_closure_candidate(tmp_path)
    document = yaml.safe_load(return_path.read_text(encoding="utf-8"))
    document["document_control"]["evidence_cutoff"] = None
    return_path.write_text(
        yaml.safe_dump(document, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["lender_return_sha256"] = hashlib.sha256(
        return_path.read_bytes()
    ).hexdigest()
    manifest_path.write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    with pytest.raises(F502LenderReturnError, match="evidence_cutoff"):
        validate_f5_02_lender_return(
            return_path,
            template_path=TEMPLATE,
            mode="closure_candidate",
            private_ingress_manifest_path=manifest_path,
        )


def test_private_manifest_binds_every_catalog_integrity_field() -> None:
    catalog_keys = set(_load_template()["evidence_catalog"][0])
    manifest_keys = set(
        yaml.safe_load(PRIVATE_INGRESS_MANIFEST.read_text(encoding="utf-8"))[
            "evidence_records"
        ][0]
    )
    expected_manifest_keys = (
        catalog_keys - {"evidence_id", "retained_path_or_stable_url", "sha256"}
    ) | {"evidence_id", "retained_path", "sha256", "byte_count"}

    assert manifest_keys == expected_manifest_keys


def test_closure_candidate_rejects_private_metadata_reseal(tmp_path: Path) -> None:
    return_path, manifest_path = _make_closure_candidate(tmp_path)
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["evidence_records"][0]["exact_title"] = "Resealed alternate title"
    manifest_path.write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    with pytest.raises(F502LenderReturnError, match=r"exact_title mismatch"):
        validate_f5_02_lender_return(
            return_path,
            template_path=TEMPLATE,
            mode="closure_candidate",
            private_ingress_manifest_path=manifest_path,
        )


def test_closure_candidate_rejects_invalid_ingress_timestamp(tmp_path: Path) -> None:
    return_path, manifest_path = _make_closure_candidate(tmp_path)
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["ingress_timestamp"] = "2026-99-99T99:99:99+99:99"
    manifest_path.write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    with pytest.raises(F502LenderReturnError, match="ingress_timestamp"):
        validate_f5_02_lender_return(
            return_path,
            template_path=TEMPLATE,
            mode="closure_candidate",
            private_ingress_manifest_path=manifest_path,
        )


def test_structural_return_inside_public_repository_is_rejected() -> None:
    with pytest.raises(F502LenderReturnError, match="every public repository worktree"):
        validate_f5_02_lender_return(
            TEMPLATE,
            template_path=TEMPLATE,
            mode="structural",
        )


def test_structural_return_in_sibling_worktree_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sibling_root = tmp_path / "sibling-worktree"
    sibling_root.mkdir()
    candidate = sibling_root / "return.yaml"
    candidate.write_bytes(TEMPLATE.read_bytes())
    monkeypatch.setattr(
        f502,
        "_repository_worktree_roots",
        lambda: (REPO_ROOT.resolve(), sibling_root.resolve()),
    )

    with pytest.raises(F502LenderReturnError, match="every public repository worktree"):
        validate_f5_02_lender_return(
            candidate,
            template_path=TEMPLATE,
            mode="structural",
        )


def test_structural_symlink_into_public_worktree_is_rejected(tmp_path: Path) -> None:
    symlink_path = tmp_path / "private-looking-return.yaml"
    symlink_path.symlink_to(TEMPLATE)

    with pytest.raises(F502LenderReturnError, match="every public repository worktree"):
        validate_f5_02_lender_return(
            symlink_path,
            template_path=TEMPLATE,
            mode="structural",
        )


@pytest.mark.parametrize(
    ("public_name", "alias_name"),
    [
        ("PublicEvidenceRoot", "publicevidenceroot"),
        ("Evidence-é", "Evidence-e\u0301"),
    ],
)
def test_structural_return_rejects_casefold_and_unicode_public_root_aliases(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    public_name: str,
    alias_name: str,
) -> None:
    public_root = tmp_path / public_name
    public_root.mkdir()
    alias_root = tmp_path / alias_name
    if not alias_root.exists():
        alias_root.mkdir()
    candidate = alias_root / "return.yaml"
    candidate.write_text(
        yaml.safe_dump(
            _make_structural_document(), sort_keys=False, allow_unicode=True
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        f502, "_repository_worktree_roots", lambda: (public_root.resolve(),)
    )

    with pytest.raises(F502LenderReturnError, match="every public repository worktree"):
        validate_f5_02_lender_return(
            candidate,
            template_path=TEMPLATE,
            mode="structural",
        )


def test_structural_return_requires_absolute_private_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate = tmp_path / "return.yaml"
    candidate.write_text(
        yaml.safe_dump(
            _make_structural_document(), sort_keys=False, allow_unicode=True
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    with pytest.raises(F502LenderReturnError, match="absolute path"):
        validate_f5_02_lender_return(
            Path("return.yaml"),
            template_path=TEMPLATE,
            mode="structural",
        )


def test_stale_worktree_inventory_path_fails_with_controlled_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        f502.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout="worktree /definitely/missing/dutchbay-worktree\0",
            stderr="",
        ),
    )

    with pytest.raises(F502LenderReturnError, match="unreadable path"):
        f502._repository_worktree_roots()


def test_worktree_inventory_ignores_caller_git_routing_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_environment: dict[str, str] = {}
    for key in f502._GIT_ROUTING_ENVIRONMENT_KEYS:
        monkeypatch.setenv(key, "/private/adversarial/git-routing")

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        environment = kwargs.get("env")
        assert isinstance(environment, dict)
        captured_environment.update(environment)
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=f"worktree {REPO_ROOT}\0",
            stderr="",
        )

    monkeypatch.setattr(f502.subprocess, "run", fake_run)

    assert f502._repository_worktree_roots() == (REPO_ROOT.resolve(),)
    assert f502._GIT_ROUTING_ENVIRONMENT_KEYS.isdisjoint(captured_environment)


def test_template_has_field_level_provenance_and_separate_authority_signoffs() -> None:
    document = _load_template()
    catalog_record = document["evidence_catalog"][0]
    citation_record = document["claim_citations"][0]
    signoff = document["signoff"]

    assert {
        "evidence_id",
        "exact_title",
        "document_type",
        "issuer_or_parties",
        "execution_status",
        "version",
        "effective_date",
        "expiry_date",
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
        "supersedes_evidence_ids",
        "superseded_by_evidence_ids",
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
    currency_control = document["response_contract"]["currency_code_list"]
    assert currency_control == {
        "maintenance_agency": "SIX Financial Information AG",
        "list": "ISO-4217 List One Current Currency and Funds",
        "source_url": "https://www.six-group.com/dam/download/financial-information/data-center/iso-currrency/lists/list-one.xml",
        "cutoff": "2026-08-24",
        "retained_source_sha256": "838dfb991648cf36df939edd5fe3811737962b75a32252847d239cedd1e291c9",
        "prohibited_non_transactional_codes": ["XTS", "XXX"],
    }


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
        validate_f5_02_lender_return(path, template_path=TEMPLATE, mode="structural")


def test_validator_rejects_confirmed_claim_without_evidence(tmp_path: Path) -> None:
    document = _load_template()
    document["transaction"]["borrower"]["status"] = "confirmed"
    path = _write_candidate(tmp_path, document)

    with pytest.raises(F502LenderReturnError, match="evidence and citations required"):
        validate_f5_02_lender_return(path, template_path=TEMPLATE, mode="structural")


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
        validate_f5_02_lender_return(path, template_path=TEMPLATE, mode="structural")


@pytest.mark.parametrize("placeholder", ["unknown", "N/A", "TBC", "pending"])
def test_validator_rejects_confirmed_unknown_placeholders(
    tmp_path: Path, placeholder: str
) -> None:
    document = _load_template()
    record = _add_eligible_evidence_and_citation(document, "F502-EV-001")
    for key in record["value"]:
        record["value"][key] = placeholder
    path = _write_candidate(tmp_path, document)

    with pytest.raises(F502LenderReturnError, match="unknown placeholder"):
        validate_f5_02_lender_return(path, template_path=TEMPLATE, mode="structural")


def test_validator_rejects_populated_open_conflict_without_id(tmp_path: Path) -> None:
    document = _load_template()
    conflict = document["conflicts_and_open_items"][0]
    conflict.update(
        {
            "requirement_ids": ["F502-EV-010"],
            "description": "Unresolved commitment-currency contradiction",
            "resolution_owner": "Transaction counsel",
            "target_resolution_date": "2026-09-01",
            "status": "open",
        }
    )
    path = tmp_path / "private_return.yaml"
    path.write_text(
        yaml.safe_dump(document, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    with pytest.raises(F502LenderReturnError, match=r"conflict\[0\].conflict_id"):
        validate_f5_02_lender_return(path, template_path=TEMPLATE, mode="structural")


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("requirement_ids", [{}]),
        ("facility_ids", [False]),
        ("evidence_ids", {"EVIDENCE-1": True}),
        ("resolution_evidence_ids", ["EVIDENCE-1", "EVIDENCE-1"]),
        ("resolution_citation_ids", [123]),
    ],
)
def test_validator_rejects_malformed_conflict_reference_lists_with_controlled_error(
    tmp_path: Path,
    field: str,
    bad_value: object,
) -> None:
    document = _make_structural_document()
    conflict = deepcopy(_load_template()["conflicts_and_open_items"][0])
    conflict.update(
        {
            "conflict_id": "CONFLICT-1",
            "requirement_ids": ["F502-EV-010"],
            "description": "Controlled adversarial conflict fixture",
            "resolution_owner": "Transaction counsel",
            "target_resolution_date": "2026-09-01",
            "status": "open",
            field: bad_value,
        }
    )
    document["conflicts_and_open_items"] = [conflict]
    path = _write_candidate(tmp_path, document)

    with pytest.raises(F502LenderReturnError, match=field):
        validate_f5_02_lender_return(path, template_path=TEMPLATE, mode="structural")


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
        validate_f5_02_lender_return(path, template_path=TEMPLATE, mode="structural")


def test_validator_requires_integrity_metadata_for_authority_only_evidence(
    tmp_path: Path,
) -> None:
    document = _make_structural_document()
    document["evidence_catalog"][0]["exact_title"] = None
    path = _write_candidate(tmp_path, document)

    with pytest.raises(F502LenderReturnError, match=r"exact_title: required"):
        validate_f5_02_lender_return(path, template_path=TEMPLATE, mode="structural")


@pytest.mark.parametrize(
    "requirement_id",
    [
        "F502-EV-001",
        "F502-EV-002",
        "F502-EV-004",
        "F502-EV-010",
        "F502-EV-012",
        "F502-EV-013",
        "F502-EV-014",
    ],
)
def test_validator_rejects_not_applicable_for_mandatory_transaction_facts(
    tmp_path: Path, requirement_id: str
) -> None:
    document = _load_template()
    record = _add_eligible_evidence_and_citation(document, requirement_id)
    record["status"] = "not_applicable"
    document["claim_citations"][0]["not_applicable_reason"] = "Claimed absent"
    path = _write_candidate(tmp_path, document)

    with pytest.raises(F502LenderReturnError, match="cannot be not_applicable"):
        validate_f5_02_lender_return(path, template_path=TEMPLATE, mode="structural")


def test_validator_rejects_lossy_party_shape(tmp_path: Path) -> None:
    document = _load_template()
    document["transaction"]["lender_agent_and_trustee_parties"]["value"] = "Lender"
    path = _write_candidate(tmp_path, document)

    with pytest.raises(F502LenderReturnError, match="expected list"):
        validate_f5_02_lender_return(path, template_path=TEMPLATE, mode="structural")


def test_validator_rejects_duplicate_multi_entity_ids(tmp_path: Path) -> None:
    document = _load_template()
    parties = document["transaction"]["lender_agent_and_trustee_parties"]["value"]
    parties[0]["party_id"] = "PARTY-1"
    parties.append(dict(parties[0]))
    path = _write_candidate(tmp_path, document)

    with pytest.raises(F502LenderReturnError, match="duplicate party_id"):
        validate_f5_02_lender_return(path, template_path=TEMPLATE, mode="structural")


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
        validate_f5_02_lender_return(path, template_path=TEMPLATE, mode="structural")


def test_validator_rejects_unknown_nested_hedge_evidence(tmp_path: Path) -> None:
    document = _load_template()
    hedge = _record(document, "F502-EV-072")["value"][0]
    hedge["governing_agreement_evidence_id"] = "MISSING-EVIDENCE"
    hedge["evidence_refs"] = ["ALSO-MISSING"]
    path = _write_candidate(tmp_path, document)

    with pytest.raises(F502LenderReturnError, match="unknown evidence"):
        validate_f5_02_lender_return(path, template_path=TEMPLATE, mode="structural")


def test_validator_rejects_implicit_yaml_date(tmp_path: Path) -> None:
    text = TEMPLATE.read_text(encoding="utf-8").replace(
        'prepared_date: "2026-08-24"',
        "prepared_date: 2026-08-24",
    )
    path = tmp_path / "implicit_date.yaml"
    path.write_text(text, encoding="utf-8")

    with pytest.raises(F502LenderReturnError, match="non-JSON YAML type date"):
        validate_f5_02_lender_return(path, template_path=TEMPLATE, mode="structural")


@pytest.mark.parametrize("bad_value", [False, 83, 1.23])
def test_validator_rejects_non_string_legal_name(
    tmp_path: Path,
    bad_value: object,
) -> None:
    document = _load_template()
    document["transaction"]["borrower"]["value"]["exact_legal_name"] = bad_value
    path = _write_candidate(tmp_path, document)

    with pytest.raises(F502LenderReturnError, match="expected a quoted string"):
        validate_f5_02_lender_return(path, template_path=TEMPLATE, mode="structural")


@pytest.mark.parametrize(
    "bad_currency", [False, 123, "NO", "US", "ZZZ", "XTS", "XXX", "BGN"]
)
def test_validator_rejects_non_iso_or_non_string_currency(
    tmp_path: Path,
    bad_currency: object,
) -> None:
    document = _load_template()
    record = _record(document, "F502-EV-010")
    record["value"] = bad_currency
    path = _write_candidate(tmp_path, document)

    with pytest.raises(F502LenderReturnError, match="quoted string|ISO-4217"):
        validate_f5_02_lender_return(path, template_path=TEMPLATE, mode="structural")


@pytest.mark.parametrize(
    ("field", "bad_date"),
    [
        ("submission_date", "2026-02-31"),
        ("submission_date", "2025-02-29"),
        ("submission_date", "2026-13-01"),
    ],
)
def test_validator_rejects_impossible_calendar_dates(
    tmp_path: Path,
    field: str,
    bad_date: str,
) -> None:
    document = _make_structural_document()
    document["submission"][field] = bad_date
    path = _write_candidate(tmp_path, document)

    with pytest.raises(F502LenderReturnError, match="invalid calendar date"):
        validate_f5_02_lender_return(path, template_path=TEMPLATE, mode="structural")


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
        validate_f5_02_lender_return(path, template_path=TEMPLATE, mode="structural")


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
        if not path.is_file():
            continue
        with path.open("rb") as stream:
            text = stream.read(2_000_000).decode("utf-8", errors="ignore")
        if _looks_like_f502_return(path, text):
            matches.append(path)

    assert matches == [TEMPLATE]
    assert {record["status"] for record in _requirement_records(_load_template())} == {
        "unknown"
    }


def test_public_content_guard_detects_minified_neutral_json() -> None:
    minified = json.dumps(_load_template(), separators=(",", ":"))

    assert _looks_like_f502_return(Path("innocent.json"), minified)
    assert _looks_like_f502_return(Path("innocent.txt"), minified)


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
    assert "/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python" in text
    assert "SIX ISO-4217 Maintenance Agency List One cutoff" in text
    assert "separate 56-row controlled ledger" in text
    assert "separate 23-row controlled gate ledger" in text
    assert "only valid release disposition is **HOLD**" in text
