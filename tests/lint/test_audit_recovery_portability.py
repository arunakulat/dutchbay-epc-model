"""Adversarial controls for the portable P01 audit recovery surface."""

from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

from analysis_tools import audit_recovery as recovery

REPO_ROOT = Path(__file__).resolve().parents[2]
DESCRIPTOR = (
    REPO_ROOT
    / "docs"
    / "audit"
    / "2026-08-controlled-successor"
    / "recovery"
    / "P01_RECOVERY_DESCRIPTOR.v1.json"
)
CLI = REPO_ROOT / "scripts" / "validate_audit_recovery.py"


def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _manifest_line(relative: str, payload: bytes = b"payload\n") -> bytes:
    return f"{_digest(payload)}  {relative}\n".encode()


def _write_tar(
    path: Path,
    *,
    name: str,
    payload: bytes = b"payload\n",
    member_type: bytes | None = None,
) -> bytes:
    with tarfile.open(path, "w:gz") as archive:
        member = tarfile.TarInfo(name)
        member.size = len(payload) if member_type is None else 0
        if member_type is not None:
            member.type = member_type
            member.linkname = "outside"
        archive.addfile(member, io.BytesIO(payload) if member_type is None else None)
    return path.read_bytes()


def _initialize_clean_repository(path: Path, origin: str) -> str:
    path.mkdir()
    subprocess.run(["git", "init", "--quiet"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "P01 Test"], cwd=path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "p01-test@example.invalid"],
        cwd=path,
        check=True,
    )
    (path / "README.md").write_text("fixture\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=path, check=True)
    subprocess.run(["git", "commit", "--quiet", "-m", "fixture"], cwd=path, check=True)
    subprocess.run(["git", "remote", "add", "origin", origin], cwd=path, check=True)
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def test_production_descriptor_is_hash_only_pending_and_hold_bound() -> None:
    """Published P01 metadata must not claim review, completion or release."""
    descriptor, descriptor_sha = recovery._load_descriptor(DESCRIPTOR)

    assert len(descriptor_sha) == 64
    assert descriptor["gate_id"] == "P01"
    assert descriptor["release_status"] == "HOLD"
    assert descriptor["independent_review_status"] == "pending_independent_review"
    assert descriptor["checkpoint"]["checkpoint_payload_manifest"]["entries"] == 68
    assert descriptor["checkpoint"]["source_manifest"] == {
        "relative_path": (
            "remediation_workspace/sources/SOURCE_ARCHIVE_MANIFEST.sha256"
        ),
        "sha256": ("568c54095213821a683fd385fe5f7dabfb8d026ddfa9b4d750c386ed145aed93"),
        "entries": 23,
        "parent_governed_unlisted_paths": ["IEC_CATALOGUE_QUERY_LOG.json"],
    }
    assert descriptor["audit_corpus"]["publication_classification"] == (
        "retained_private_external_dependency"
    )
    assert "/Users/" not in DESCRIPTOR.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (_manifest_line("a.txt") * 2, "MANIFEST_DUPLICATE"),
        (
            _manifest_line("A.txt") + _manifest_line("a.txt"),
            "MANIFEST_COLLISION",
        ),
        (_manifest_line("../outside.txt"), "UNSAFE_PATH"),
        (_manifest_line("directory//file.txt"), "UNSAFE_PATH"),
        (_manifest_line("a.txt").replace(b"\n", b"\r\n"), "MANIFEST_FORMAT"),
        (b"", "MANIFEST_EMPTY"),
    ],
)
def test_manifest_parser_rejects_ambiguous_or_unsafe_payloads(
    payload: bytes, code: str
) -> None:
    """Manifest normalization must not hide duplicates, collisions or escapes."""
    with pytest.raises(recovery.AuditRecoveryError) as raised:
        recovery._parse_manifest_bytes(payload, "fixture_manifest")

    assert raised.value.code == code


def test_nested_manifest_has_one_explicit_parent_governed_exception(
    tmp_path: Path,
) -> None:
    """The source query log is explicit, while any second unlisted file is refused."""
    governed = b"governed\n"
    parent_governed = b"parent-governed\n"
    manifest = _manifest_line("original/governed.txt", governed)
    (tmp_path / "original").mkdir()
    (tmp_path / "original/governed.txt").write_bytes(governed)
    (tmp_path / "IEC_CATALOGUE_QUERY_LOG.json").write_bytes(parent_governed)
    (tmp_path / "SOURCE_ARCHIVE_MANIFEST.sha256").write_bytes(manifest)
    contract = {
        "relative_path": "unused-by-helper",
        "sha256": _digest(manifest),
        "entries": 1,
    }

    summary = recovery._validate_manifest_directory(
        tmp_path,
        contract,
        label="source_manifest",
        manifest_relative_to_root="SOURCE_ARCHIVE_MANIFEST.sha256",
        parent_governed_unlisted_paths=["IEC_CATALOGUE_QUERY_LOG.json"],
    )
    assert summary.entries == 1

    (tmp_path / "claims.json").write_text('{"bankable":true}\n')
    with pytest.raises(recovery.AuditRecoveryError) as raised:
        recovery._validate_manifest_directory(
            tmp_path,
            contract,
            label="source_manifest",
            manifest_relative_to_root="SOURCE_ARCHIVE_MANIFEST.sha256",
            parent_governed_unlisted_paths=["IEC_CATALOGUE_QUERY_LOG.json"],
        )
    assert raised.value.code == "MANIFEST_UNEXPECTED"
    assert "claims.json" in str(raised.value)


def test_post_ingress_derivative_is_separately_attested_not_promoted(
    tmp_path: Path,
) -> None:
    """A derived report is allowed only under its distinct exact hash contract."""
    received = b"received evidence\n"
    derived = b"derived evaluation\n"
    manifest = _manifest_line("received.txt", received)
    (tmp_path / "received.txt").write_bytes(received)
    (tmp_path / "06_CODEX_INGRESS_EVALUATION.md").write_bytes(derived)
    (tmp_path / "INGRESS_MANIFEST.sha256").write_bytes(manifest)
    contract = {
        "relative_path": "unused-by-helper",
        "sha256": _digest(manifest),
        "entries": 1,
    }
    attested = recovery.ManifestEntry(
        relative_path="06_CODEX_INGRESS_EVALUATION.md",
        sha256=_digest(derived),
    )

    summary = recovery._validate_manifest_directory(
        tmp_path,
        contract,
        label="audit_corpus_manifest",
        manifest_relative_to_root="INGRESS_MANIFEST.sha256",
        additional_attested_entries=[attested],
    )
    assert summary.entries == 1
    assert summary.manifest_scope_root_digest_sha256 != summary.root_digest_sha256

    (tmp_path / "06_CODEX_INGRESS_EVALUATION.md").write_bytes(b"mutated\n")
    with pytest.raises(recovery.AuditRecoveryError) as raised:
        recovery._validate_manifest_directory(
            tmp_path,
            contract,
            label="audit_corpus_manifest",
            manifest_relative_to_root="INGRESS_MANIFEST.sha256",
            additional_attested_entries=[attested],
        )
    assert raised.value.code == "ATTESTED_FILE_HASH_MISMATCH"


@pytest.mark.parametrize(
    ("member_name", "member_type", "code"),
    [
        ("root/../escape.txt", None, "UNSAFE_PATH"),
        ("root/item.txt", tarfile.SYMTYPE, "ARCHIVE_LINK"),
    ],
)
def test_archive_rejects_escape_and_link_members(
    tmp_path: Path, member_name: str, member_type: bytes | None, code: str
) -> None:
    """Tar inspection must not extract or accept traversal and link members."""
    archive_path = tmp_path / "fixture.tar.gz"
    archive_payload = _write_tar(
        archive_path,
        name=member_name,
        member_type=member_type,
    )
    contract = {
        "filename": archive_path.name,
        "sha256": _digest(archive_payload),
        "tar_root": "root",
        "governed_file_members": 1,
        "appledouble_metadata_members": 0,
        "total_regular_file_members": 1,
    }
    outer = [
        recovery.ManifestEntry(
            relative_path="remediation_workspace/item.txt",
            sha256=_digest(b"payload\n"),
        )
    ]

    with pytest.raises(recovery.AuditRecoveryError) as raised:
        recovery._validate_archive(archive_path, contract, outer)
    assert raised.value.code == code


def test_missing_outer_payload_fails_with_exact_manifest_path(
    tmp_path: Path,
) -> None:
    """The required P01 deletion control reports MANIFEST_MISSING, not a path leak."""
    checkpoint = tmp_path / "checkpoint"
    checkpoint.mkdir()
    output = tmp_path / "recovered"
    outer_manifest = checkpoint / "CHECKPOINT_PAYLOAD_MANIFEST.sha256"
    outer_manifest.write_bytes(_manifest_line("README.md"))
    entries = recovery._parse_manifest_bytes(
        outer_manifest.read_bytes(), "checkpoint_payload_manifest"
    )

    with pytest.raises(recovery.AuditRecoveryError) as raised:
        recovery._materialize_successor(
            checkpoint,
            output,
            outer_manifest,
            entries,
            {},
        )
    assert raised.value.code == "MANIFEST_MISSING"
    assert str(raised.value).endswith("README.md")
    assert not output.exists()
    assert not list(tmp_path.glob(".recovered.stage-*"))


def test_input_output_overlap_and_symlink_components_fail_closed(
    tmp_path: Path,
) -> None:
    """Recovery must not write inside an input or through a symlink alias."""
    checkpoint = tmp_path / "checkpoint"
    checkpoint.mkdir()
    with pytest.raises(recovery.AuditRecoveryError) as overlap:
        recovery._assert_distinct_roots(
            (
                (checkpoint, "checkpoint root"),
                (checkpoint / "recovered", "output root"),
            )
        )
    assert overlap.value.code == "PATH_OVERLAP"

    alias = tmp_path / "alias"
    alias.symlink_to(checkpoint, target_is_directory=True)
    with pytest.raises(recovery.AuditRecoveryError) as symlink:
        recovery._assert_no_symlink_components(
            alias / "recovered", "output root", allow_missing=True
        )
    assert symlink.value.code == "PATH_SYMLINK"

    with pytest.raises(recovery.AuditRecoveryError) as noncanonical:
        recovery._assert_no_symlink_components(
            checkpoint / ".." / "other", "output root", allow_missing=True
        )
    assert noncanonical.value.code == "PATH_NON_CANONICAL"


def test_duplicate_descriptor_keys_and_premature_review_are_refused(
    tmp_path: Path,
) -> None:
    """Governed JSON cannot exploit last-key-wins or claim a completed review."""
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"gate_id":"P01","gate_id":"R08"}\n')
    with pytest.raises(recovery.AuditRecoveryError) as duplicate_error:
        recovery._load_descriptor(duplicate)
    assert duplicate_error.value.code == "DESCRIPTOR_DUPLICATE"

    descriptor = json.loads(DESCRIPTOR.read_text(encoding="utf-8"))
    descriptor["independent_review_status"] = "completed"
    premature = tmp_path / "premature.json"
    premature.write_text(json.dumps(descriptor))
    with pytest.raises(recovery.AuditRecoveryError) as review_error:
        recovery._load_descriptor(premature)
    assert review_error.value.code == "DESCRIPTOR_REVIEW"


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        ("origin", "REPOSITORY_IDENTITY"),
        ("audited_commit", "AUDITED_COMMIT_MISSING"),
    ],
)
def test_repository_identity_and_audited_commit_fail_closed(
    tmp_path: Path, mutation: str, code: str
) -> None:
    """A clean unrelated repository cannot satisfy the P01 Git boundary."""
    repository = tmp_path / "repository"
    actual_origin = (
        "https://github.com/example/unrelated.git"
        if mutation == "origin"
        else "https://github.com/arunakulat/dutchbay-epc-model.git"
    )
    head = _initialize_clean_repository(repository, actual_origin)
    contract = {
        "origin_repository": "arunakulat/dutchbay-epc-model",
        "audited_commit": "0" * 40 if mutation == "audited_commit" else head,
    }

    with pytest.raises(recovery.AuditRecoveryError) as raised:
        recovery._validate_repository(repository, contract)
    assert raised.value.code == code


def test_wrong_bundle_digest_is_rejected_before_git_parsing(tmp_path: Path) -> None:
    """A replacement bundle cannot rely on its internal ref listing to self-attest."""
    repository = tmp_path / "repository"
    _initialize_clean_repository(
        repository, "https://github.com/arunakulat/dutchbay-epc-model.git"
    )
    bundle = tmp_path / "replacement.bundle"
    bundle.write_bytes(b"not the governed bundle\n")
    contract = {"sha256": "0" * 64, "refs": {"refs/heads/main": "0" * 40}}

    with pytest.raises(recovery.AuditRecoveryError) as raised:
        recovery._validate_bundle(repository, bundle, contract)
    assert raised.value.code == "BUNDLE_DIGEST"


def test_failure_receipt_is_concise_path_free_and_hold_bound() -> None:
    """Machine-local roots must never escape through the public refusal receipt."""
    error = recovery.AuditRecoveryError(
        "MANIFEST_MISSING",
        "checkpoint_payload_manifest",
        "checkpoint_payload_manifest is missing README.md",
    )
    receipt = recovery.failure_receipt(error)
    rendered = json.dumps(receipt, sort_keys=True, allow_nan=False)

    assert receipt["status"] == "FAIL"
    assert receipt["gate_status"] == "pending_independent_review"
    assert receipt["release_status"] == "HOLD"
    assert "/Users/" not in rendered


def test_hydra_cli_missing_environment_is_one_line_and_log_free(
    tmp_path: Path,
) -> None:
    """Expected CLI refusal is deterministic and creates no Hydra/runtime logs."""
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(REPO_ROOT)
    for name in (
        "DUTCHBAY_AUDIT_CHECKPOINT_ROOT",
        "DUTCHBAY_AUDIT_CORPUS_ROOT",
        "DUTCHBAY_AUDIT_REPOSITORY_ROOT",
        "DUTCHBAY_AUDIT_RECOVERY_OUTPUT_ROOT",
    ):
        environment.pop(name, None)

    completed = subprocess.run(
        [sys.executable, str(CLI)],
        cwd=tmp_path,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 2
    assert completed.stdout == ""
    lines = completed.stderr.splitlines()
    assert len(lines) == 1
    receipt = json.loads(lines[0])
    assert receipt["error"]["code"] == "ENVIRONMENT_PATH"
    assert receipt["release_status"] == "HOLD"
    assert not list(tmp_path.rglob("*"))


def test_hydra_cli_rejects_unsupported_overrides_before_configuration(
    tmp_path: Path,
) -> None:
    """Hydra overrides cannot replace environment-only root or recovery policy."""
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(REPO_ROOT)
    completed = subprocess.run(
        [sys.executable, str(CLI), "mode=skip_validation"],
        cwd=tmp_path,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 2
    assert completed.stdout == ""
    receipt = json.loads(completed.stderr)
    assert receipt["error"]["code"] == "CLI_ARGUMENTS"
    assert receipt["gate_status"] == "pending_independent_review"
    assert receipt["release_status"] == "HOLD"
    assert not list(tmp_path.rglob("*"))
