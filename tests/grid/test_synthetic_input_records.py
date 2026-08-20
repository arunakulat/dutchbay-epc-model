"""Issue #1077 governed synthetic input-record handoff and refusal controls."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping, cast

import pytest
import yaml

import analytics.grid.synthetic_input_records as input_records_module
from analytics.contracts_v14 import (
    SYNTHETIC_PROCESS_PROVENANCE_WARNING,
    SyntheticInputRecordHandoff,
)
from analytics.grid.synthetic_input_records import (
    SyntheticInputRecordsConfig,
    cli_summary,
    generate_and_ingress_synthetic_input_records,
)
from analytics.run_manifest import config_sha256

REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATOR_CONFIG_PATH = REPO_ROOT / "conf" / "synthetic_feeder_placeholder.yaml"
HANDOFF_CONFIG_PATH = REPO_ROOT / "conf" / "synthetic_input_records.yaml"
GENERATED_AT = "2026-08-20T12:00:00+00:00"


def _generator_raw() -> Mapping[str, Any]:
    raw = yaml.safe_load(GENERATOR_CONFIG_PATH.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    return raw


def _handoff_config() -> SyntheticInputRecordsConfig:
    raw = yaml.safe_load(HANDOFF_CONFIG_PATH.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    handoff = raw["handoff"]
    assert isinstance(handoff, dict)
    return SyntheticInputRecordsConfig.from_mapping(handoff)


@pytest.fixture(scope="module")
def published_handoff(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[SyntheticInputRecordHandoff, str, Path]:
    pytest.importorskip("opendssdirect")
    root = tmp_path_factory.mktemp("issue1077-input-records").resolve()
    record, digest = generate_and_ingress_synthetic_input_records(
        generator_config_raw=_generator_raw(),
        handoff_config=_handoff_config(),
        repo_root=REPO_ROOT,
        package_output_override=root / "package",
        handoff_output_override=root / "handoff",
        generated_at_utc=GENERATED_AT,
    )
    return record, digest, root / "handoff"


def test_handoff_configuration_is_strict_and_config_first() -> None:
    config = _handoff_config()
    assert config.output_dir == "outputs/synthetic_process_provenance/issue_1077"
    raw = yaml.safe_load(HANDOFF_CONFIG_PATH.read_text(encoding="utf-8"))["handoff"]
    with pytest.raises(ValueError, match="keys must be exactly"):
        SyntheticInputRecordsConfig.from_mapping({**raw, "unexpected": True})
    with pytest.raises(ValueError, match="literal boolean"):
        SyntheticInputRecordsConfig.from_mapping({**raw, "allow_existing_identical": 1})
    with pytest.raises(ValueError, match="segregated governed path"):
        SyntheticInputRecordsConfig.from_mapping(
            {**raw, "output_dir": "outputs/substituted"}
        )
    with pytest.raises(ValueError, match="reuse the governed"):
        SyntheticInputRecordsConfig.from_mapping(
            {**raw, "generator_config_source": "conf/substituted.yaml"}
        )


@pytest.mark.grid
def test_handoff_authenticates_all_inputs_and_runtime_ingress(
    published_handoff: tuple[SyntheticInputRecordHandoff, str, Path],
) -> None:
    record, digest, output_dir = published_handoff
    assert record.profile_row_count == 8760
    assert record.profile_start_utc == "2021-01-01T00:00:00Z"
    assert record.profile_end_utc == "2021-12-31T23:00:00Z"
    assert record.profile_timezone == "UTC"
    assert record.profile_timestep_hours == 1.0
    assert record.profile_unit == "MW"
    assert record.export_cap_mw == pytest.approx(150.0)
    assert record.opendss_compile_status == ("passed_compile_only_no_convergence_claim")
    assert record.generator_code_sha256 == record.verifier_code_sha256
    assert record.resolved_generator_config_sha256 == config_sha256(
        {
            key: value
            for key, value in _generator_raw().items()
            if key not in {"defaults", "hydra"}
        }
    )
    assert len(record.source_records) == 9
    assert {item.relative_path for item in record.artifact_records} == {
        "feeder/Master.dss",
        "feeder/Source.dss",
        "feeder/Transformer.dss",
        "feeder/Connection.dss",
        "feeder/Plant.dss",
        "profile/generation_profile.csv",
        "manifest.json",
        "MANIFEST.sha256",
    }
    assert record.operator_schedule_present is False
    assert record.operator_schedule_status == (
        "absent_no_observed_operator_instructions"
    )
    assert record.required_warning == SYNTHETIC_PROCESS_PROVENANCE_WARNING
    assert record.qsts_executed is False
    assert record.finance_executed is False
    assert record.canonical_finance_eligible is False
    assert record.bankable is False
    assert record.publishable is False

    payload = (output_dir / "synthetic_input_records.json").read_bytes()
    assert hashlib.sha256(payload).hexdigest() == digest
    assert (output_dir / "synthetic_input_records.sha256").read_text(
        encoding="ascii"
    ) == f"{digest}  synthetic_input_records.json\n"
    decoded = json.loads(payload)
    assert decoded["required_warning"] == SYNTHETIC_PROCESS_PROVENANCE_WARNING
    assert decoded["qsts_executed"] is False
    assert decoded["finance_executed"] is False
    assert "aep_mwh" not in decoded
    assert "curtailment_mwh" not in decoded
    assert "/Users/" not in payload.decode("utf-8")


@pytest.mark.grid
def test_handoff_summary_repeats_warning_and_refusal_controls(
    published_handoff: tuple[SyntheticInputRecordHandoff, str, Path],
) -> None:
    record, digest, _ = published_handoff
    summary = cli_summary(record, digest, _handoff_config())
    assert summary["status"] == "PASS"
    assert summary["required_warning"] == SYNTHETIC_PROCESS_PROVENANCE_WARNING
    assert summary["profile_row_count"] == 8760
    assert summary["qsts_executed"] is False
    assert summary["finance_executed"] is False
    assert summary["canonical_finance_eligible"] is False
    assert summary["bankable"] is False
    assert summary["publishable"] is False


@pytest.mark.grid
def test_handoff_allows_identical_reverification_but_refuses_replacement(
    published_handoff: tuple[SyntheticInputRecordHandoff, str, Path],
) -> None:
    original, original_digest, output_dir = published_handoff
    package_dir = output_dir.parent / "package"
    repeated, repeated_digest = generate_and_ingress_synthetic_input_records(
        generator_config_raw=_generator_raw(),
        handoff_config=_handoff_config(),
        repo_root=REPO_ROOT,
        package_output_override=package_dir,
        handoff_output_override=output_dir,
        generated_at_utc=GENERATED_AT,
    )
    assert repeated == original
    assert repeated_digest == original_digest

    with pytest.raises(FileExistsError, match="differing or incomplete"):
        generate_and_ingress_synthetic_input_records(
            generator_config_raw=_generator_raw(),
            handoff_config=_handoff_config(),
            repo_root=REPO_ROOT,
            package_output_override=package_dir,
            handoff_output_override=output_dir,
            generated_at_utc="2026-08-20T12:00:01+00:00",
        )


@pytest.mark.grid
def test_handoff_refuses_post_adapter_payload_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("opendssdirect")
    original = input_records_module.build_verified_synthetic_qsts_overlay

    def _mutating_adapter(
        *, manifest_path: str | Path, expected_manifest_sha256: str
    ) -> dict[str, Any]:
        overlay = original(
            manifest_path=manifest_path,
            expected_manifest_sha256=expected_manifest_sha256,
        )
        profile = Path(manifest_path).parent / "profile" / "generation_profile.csv"
        profile.write_bytes(profile.read_bytes() + b"\n")
        return dict(overlay)

    monkeypatch.setattr(
        input_records_module,
        "build_verified_synthetic_qsts_overlay",
        _mutating_adapter,
    )
    root = tmp_path.resolve()
    with pytest.raises(ValueError, match="Payload SHA-256 mismatch"):
        generate_and_ingress_synthetic_input_records(
            generator_config_raw=_generator_raw(),
            handoff_config=_handoff_config(),
            repo_root=REPO_ROOT,
            package_output_override=root / "package",
            handoff_output_override=root / "handoff",
            generated_at_utc=GENERATED_AT,
        )
    assert not (root / "handoff").exists()


@pytest.mark.grid
@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("bankable", True, "bankable must be False"),
        ("publishable", True, "publishable must be False"),
        ("qsts_executed", True, "qsts_executed must be False"),
        ("finance_executed", True, "finance_executed must be False"),
        ("profile_row_count", 8759, "exactly 8760"),
    ],
)
def test_contract_refuses_evidence_upgrade_or_shortened_profile(
    published_handoff: tuple[SyntheticInputRecordHandoff, str, Path],
    field: str,
    value: object,
    message: str,
) -> None:
    record, _, _ = published_handoff
    with pytest.raises(ValueError, match=message):
        cast(Any, replace)(record, **{field: value})
