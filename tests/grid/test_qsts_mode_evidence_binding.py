"""#1072 — real/site QSTS identity binding, immutable runtime, and mode refusal."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from analytics.contracts_v14 import (
    QSTS_CONTROLLED_OUTPUT_CLASS,
    QSTS_RUN_MANIFEST_SCHEMA,
)
from analytics.grid import curtailment_qsts as cq
from analytics.grid.qsts_evidence import (
    QSTS_EVIDENCE_MANIFEST_SCHEMA,
    QSTS_PROFILE_SCHEMA,
    QSTSEvidenceError,
    verify_qsts_evidence_package,
)


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _profile(values: list[float]) -> bytes:
    return _json_bytes({"schema": QSTS_PROFILE_SCHEMA, "unit": "MW", "values": values})


def _write_evidence_package(
    tmp_path: Path,
    *,
    input_kind: str = "engineer_prepared_site_model",
    generation_mw: list[float] | None = None,
    instructed_mw: list[float] | None = None,
    export_cap_mw: float = 15.0,
    timestep_hours: float = 0.5,
    master_payload: bytes | None = None,
) -> tuple[dict[str, Any], Path, Path, str, dict[str, bytes]]:
    root = tmp_path / "qsts-evidence"
    master = root / "feeder" / "Master.dss"
    generation_path = root / "profiles" / "generation.json"
    for parent in {master.parent, generation_path.parent}:
        parent.mkdir(parents=True, exist_ok=True)

    payloads = {
        "feeder/Master.dss": master_payload
        or (
            b"Clear\n"
            b"New Circuit.dutchbay basekv=33 pu=1 phases=3 bus1=source\n"
            b'Redirect "Lines.dss"\n'
        ),
        "feeder/Lines.dss": (
            b"New Line.connection bus1=source bus2=poc phases=3 r1=0.1 x1=0.2 "
            b"length=1\n"
        ),
        "profiles/generation.json": _profile(generation_mw or [20.0, 10.0]),
        "profiles/instructions.json": _profile(instructed_mw or [1.0, 0.0]),
    }
    for relative_path, payload in payloads.items():
        path = root.joinpath(*relative_path.split("/"))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)

    observed = input_kind == "utility_observed_model"
    manifest = {
        "schema": QSTS_EVIDENCE_MANIFEST_SCHEMA,
        "package_id": "issue1072-test-package",
        "input_kind": input_kind,
        "classification": {
            "generated_input": False,
            "observed_network_data": observed,
            "site_representative": True,
            "bankable": False,
        },
        "provenance": {
            "source_authority": "Test evidence authority",
            "source_reference": "TEST-ONLY-1072",
            "issued_at_utc": "2026-08-20T00:00:00Z",
        },
        "feeder_model_path": "feeder/Master.dss",
        "runtime_inputs": {
            "generation_profile_mw_path": "profiles/generation.json",
            "grid_instructed_profile_mw_path": "profiles/instructions.json",
            "export_cap_mw": export_cap_mw,
            "timestep_hours": timestep_hours,
        },
        "payload_sha256": {
            relative_path: _sha256(payload)
            for relative_path, payload in payloads.items()
        },
    }
    manifest_path = root / "evidence-manifest.json"
    manifest_bytes = _json_bytes(manifest)
    manifest_path.write_bytes(manifest_bytes)
    manifest_sha256 = _sha256(manifest_bytes)
    config = {
        "grid": {
            "qsts": {
                "enabled": True,
                "input_kind": input_kind,
                "feeder_model_path": str(master),
                "evidence_manifest_path": str(manifest_path),
                "evidence_manifest_sha256": manifest_sha256,
                "finance_wiring": {
                    "enabled": False,
                    "mode": "canonical",
                    "canonical_eligible": True,
                },
            }
        }
    }
    return config, manifest_path, master, manifest_sha256, payloads


def test_verified_site_package_binds_result_and_typed_run_receipt(
    tmp_path: Path,
) -> None:
    config, _manifest, master, digest, payloads = _write_evidence_package(tmp_path)

    result = cq.run_qsts_curtailment(
        config,
        generation_mwh=[10.0, 5.0],
        grid_instructed_mwh=[0.5, 0.0],
    )

    assert result.ran is True
    assert result.feeder_source == str(master)
    assert result.feeder_input_kind == "engineer_prepared_site_model"
    assert result.generated_input is False
    assert result.observed_network_data is False
    assert result.site_representative is True
    assert result.bankable is False
    assert result.evidence_manifest_sha256 == digest
    assert result.source_manifest_sha256 is None
    assert result.export_cap_mw == pytest.approx(15.0)
    assert result.gross_energy_mwh == pytest.approx(15.0)
    assert result.self_curtailed_pre_bess_mwh == pytest.approx(2.5)
    assert result.deemed_paid_energy_mwh == pytest.approx(0.5)

    receipt = result.qsts_run_manifest
    assert receipt is not None
    assert receipt.schema == QSTS_RUN_MANIFEST_SCHEMA
    assert receipt.package_id == "issue1072-test-package"
    assert receipt.output_class == QSTS_CONTROLLED_OUTPUT_CLASS
    assert receipt.evidence_manifest_sha256 == digest
    assert receipt.source_manifest_sha256 is None
    assert receipt.bankable is False
    assert receipt.lender_eligible is False
    assert receipt.board_approval_eligible is False
    assert receipt.release_eligible is False
    assert dict(receipt.payload_sha256) == {
        path: _sha256(payload) for path, payload in payloads.items()
    }
    serialized = result.model_dump()
    assert serialized["evidence_manifest_sha256"] == digest
    assert serialized["qsts_run_manifest"]["package_id"] == "issue1072-test-package"


def test_utility_kind_derives_observed_flag_from_verified_manifest(
    tmp_path: Path,
) -> None:
    config, _manifest, _master, _digest, _payloads = _write_evidence_package(
        tmp_path, input_kind="utility_observed_model"
    )
    result = cq.run_qsts_curtailment(
        config,
        generation_mwh=[10.0, 5.0],
        grid_instructed_mwh=[0.5, 0.0],
    )
    assert result.observed_network_data is True
    assert result.site_representative is True


def test_manifest_digest_mismatch_refuses_reseal(tmp_path: Path) -> None:
    config, manifest, _master, _digest, _payloads = _write_evidence_package(tmp_path)
    document = json.loads(manifest.read_text(encoding="utf-8"))
    document["package_id"] = "resealed-package"
    manifest.write_bytes(_json_bytes(document))

    with pytest.raises(QSTSEvidenceError, match="manifest digest mismatch"):
        cq.run_qsts_curtailment(
            config,
            generation_mwh=[10.0, 5.0],
            grid_instructed_mwh=[0.5, 0.0],
        )


def test_payload_substitution_is_refused_before_result(tmp_path: Path) -> None:
    config, _manifest, master, _digest, _payloads = _write_evidence_package(tmp_path)
    master.write_text("Clear\n! substituted after manifest\n", encoding="utf-8")

    with pytest.raises(QSTSEvidenceError, match="payload digest mismatch"):
        cq.run_qsts_curtailment(
            config,
            generation_mwh=[10.0, 5.0],
            grid_instructed_mwh=[0.5, 0.0],
        )


def test_cross_mode_reclassification_is_refused(tmp_path: Path) -> None:
    config, _manifest, _master, _digest, _payloads = _write_evidence_package(
        tmp_path, input_kind="utility_observed_model"
    )
    config["grid"]["qsts"]["input_kind"] = "engineer_prepared_site_model"

    with pytest.raises(QSTSEvidenceError, match="cross-mode reclassification"):
        cq.run_qsts_curtailment(
            config,
            generation_mwh=[10.0, 5.0],
            grid_instructed_mwh=[0.5, 0.0],
        )


def test_configured_master_must_match_manifest_master(tmp_path: Path) -> None:
    config, manifest, _master, digest, _payloads = _write_evidence_package(tmp_path)
    substitute = manifest.parent / "feeder" / "Substitute.dss"
    substitute.write_text("Clear\n", encoding="utf-8")
    config["grid"]["qsts"]["feeder_model_path"] = str(substitute)

    with pytest.raises(QSTSEvidenceError, match="does not match"):
        verify_qsts_evidence_package(
            manifest_path=manifest,
            expected_manifest_sha256=digest,
            expected_input_kind="engineer_prepared_site_model",
            configured_master_path=substitute,
        )


def test_manifest_symlink_is_refused(tmp_path: Path) -> None:
    config, manifest, _master, _digest, _payloads = _write_evidence_package(tmp_path)
    target = manifest.with_name("real-evidence-manifest.json")
    manifest.rename(target)
    manifest.symlink_to(target.name)

    with pytest.raises(QSTSEvidenceError, match="manifest.*symlink"):
        cq.run_qsts_curtailment(
            config,
            generation_mwh=[10.0, 5.0],
            grid_instructed_mwh=[0.5, 0.0],
        )


def test_payload_symlink_is_refused_even_with_matching_bytes(tmp_path: Path) -> None:
    config, _manifest, master, _digest, _payloads = _write_evidence_package(tmp_path)
    target = master.with_name("Master-target.dss")
    target.write_bytes(master.read_bytes())
    master.unlink()
    master.symlink_to(target.name)

    with pytest.raises(QSTSEvidenceError, match="resolves through symlink"):
        cq.run_qsts_curtailment(
            config,
            generation_mwh=[10.0, 5.0],
            grid_instructed_mwh=[0.5, 0.0],
        )


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("generation_profile_mw", [19.0, 10.0], "first mismatch"),
        ("grid_instructed_profile_mw", [0.0, 0.0], "first mismatch"),
        ("export_cap_mw", 14.0, "export cap"),
        ("timestep_hours", 1.0, "QSTS timestep"),
    ],
)
def test_config_runtime_substitution_is_refused(
    tmp_path: Path, field: str, value: Any, match: str
) -> None:
    config, _manifest, _master, _digest, _payloads = _write_evidence_package(tmp_path)
    config["grid"]["qsts"][field] = value
    with pytest.raises((QSTSEvidenceError, ValueError), match=match):
        cq.run_qsts_curtailment(
            config,
            generation_mwh=[10.0, 5.0],
            grid_instructed_mwh=[0.5, 0.0],
        )


def test_caller_profile_substitution_is_refused(tmp_path: Path) -> None:
    config, _manifest, _master, _digest, _payloads = _write_evidence_package(tmp_path)
    with pytest.raises(ValueError, match="generation_mwh override.*first mismatch"):
        cq.run_qsts_curtailment(
            config,
            generation_mwh=[9.0, 5.0],
            grid_instructed_mwh=[0.5, 0.0],
        )


def test_dss_reference_outside_pinned_payloads_is_refused(tmp_path: Path) -> None:
    config, _manifest, _master, _digest, _payloads = _write_evidence_package(
        tmp_path, master_payload=b'Redirect "../../outside.dss"\n'
    )
    with pytest.raises(QSTSEvidenceError, match="escapes the package"):
        cq.run_qsts_curtailment(
            config,
            generation_mwh=[10.0, 5.0],
            grid_instructed_mwh=[0.5, 0.0],
        )


def test_solver_uses_private_snapshot_after_source_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, _manifest, master, _digest, payloads = _write_evidence_package(tmp_path)
    accepted_master = payloads["feeder/Master.dss"]
    seen_snapshot: list[Path] = []

    def _recording_solver(
        _grid: Any,
        *,
        feeder_path: str,
        timestep_hours: float,
        generation_profile_mw: Any,
        grid_instructed_profile_mw: Any,
    ) -> tuple[list[float], list[float]]:
        master.write_text("Clear\n! malicious TOCTOU replacement\n", encoding="utf-8")
        snapshot = Path(feeder_path)
        seen_snapshot.append(snapshot)
        assert snapshot != master
        assert snapshot.read_bytes() == accepted_master
        assert timestep_hours == pytest.approx(0.5)
        assert tuple(generation_profile_mw) == (20.0, 10.0)
        assert tuple(grid_instructed_profile_mw) == (1.0, 0.0)
        return [10.0, 5.0], [0.5, 0.0]

    monkeypatch.setattr(cq, "_solve_qsts", _recording_solver)
    result = cq.run_qsts_curtailment(config)
    assert result.ran is True
    assert len(seen_snapshot) == 1
    assert not seen_snapshot[0].exists()  # private snapshot is removed after the solve


def test_duplicate_manifest_key_is_refused(tmp_path: Path) -> None:
    config, manifest, _master, _digest, _payloads = _write_evidence_package(tmp_path)
    original = manifest.read_text(encoding="utf-8").rstrip()
    duplicate = original[:-1] + ',"schema":"dutchbay_qsts_evidence_manifest_v1"}\n'
    manifest.write_text(duplicate, encoding="utf-8")
    config["grid"]["qsts"]["evidence_manifest_sha256"] = _sha256(duplicate.encode())

    with pytest.raises(QSTSEvidenceError, match="repeats key 'schema'"):
        cq.run_qsts_curtailment(
            config,
            generation_mwh=[10.0, 5.0],
            grid_instructed_mwh=[0.5, 0.0],
        )
