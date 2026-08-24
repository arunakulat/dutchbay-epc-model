"""Deterministic identity contract for the disposable #1110 review sandbox."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import re
import subprocess
from pathlib import Path

EXPECTED_IMAGE_DIGEST = (
    "sha256:7876580dc67fd460fd962f004cbeb480027e9bbc0657096f1087db11f9eaff39"
)
EXPECTED_SSHD_FEATURE = "ghcr.io/devcontainers/features/sshd:1.1.0"
EXPECTED_SSHD_MANIFEST_DIGEST = (
    "sha256:f5251b8e4325f68f7280973c6cd65daff414449c66f240621502d4e8e74eb7ee"
)
HEX_64 = re.compile(r"[0-9a-f]{64}\Z")

DEPENDENCY_INPUT_RELATIVES = (
    "requirements.txt",
    "pyproject.toml",
    "constraints.txt",
    ".devcontainer/devcontainer.json",
    ".devcontainer/devcontainer-lock.json",
    ".devcontainer/bootstrap_audit_review.sh",
    ".devcontainer/audit_review_identity.py",
)

CONTROLLED_INPUT_RELATIVES = (
    "docs/audit/2026-08-controlled-successor/PUBLICATION_MANIFEST.sha256",
    "docs/audit/2026-08-controlled-successor/registers/programme_gate_ledger.v1.json",
    "docs/audit/2026-08-controlled-successor/registers/findings_register.v2.json",
    "docs/audit/2026-08-controlled-successor/registers/findings_current_state_plan.v1.json",
    "docs/audit/2026-08-controlled-successor/registers/findings_current_state_overlay.v1.json",
    "docs/audit/2026-08-controlled-successor/qa/P02_REPOSITORY_HISTORY_IMPLEMENTER_SELF_CHECK_2026-08-24.json",
    "docs/audit/2026-08-controlled-successor/registers/primary_source_register.v2.json",
    "docs/audit/2026-08-controlled-successor/registers/primary_source_register.v2.csv",
    "docs/audit/2026-08-controlled-successor/registers/primary_source_review_plan.v1.json",
    "docs/audit/2026-08-controlled-successor/source-controls/SOURCE_ARCHIVE_MANIFEST.v2.sha256",
    "docs/audit/2026-08-controlled-successor/qa/P03_PRIMARY_SOURCE_IMPLEMENTER_SELF_CHECK_2026-08-24.json",
    "docs/audit/2026-08-controlled-successor/scripts/build_findings_current_state_overlay.py",
    "docs/audit/2026-08-controlled-successor/scripts/build_primary_source_review_plan.py",
    "docs/audit/2026-08-controlled-successor/scripts/validate_published_pack.py",
    "scripts/verify_p03_primary_sources.py",
    "scripts/upload_1110_p03_sources_to_codespace.sh",
    "scripts/verify_1110_cloud_review_sandbox.sh",
    ".devcontainer/devcontainer.json",
    ".devcontainer/devcontainer-lock.json",
    ".devcontainer/bootstrap_audit_review.sh",
    ".devcontainer/audit_review_identity.py",
)


class SandboxIdentityError(RuntimeError):
    """Raised when a sandbox identity input is stale, missing or malformed."""


def _sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of one regular repository input."""
    if not path.is_file() or path.is_symlink():
        raise SandboxIdentityError(
            f"controlled input is missing or unsafe: {path.name}"
        )
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dependency_input_sha256(repo_root: Path) -> str:
    """Hash the exact dependency and sandbox-construction inputs in order."""
    digest = hashlib.sha256()
    for relative in DEPENDENCY_INPUT_RELATIVES:
        path = repo_root / relative
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        if not path.is_file() or path.is_symlink():
            raise SandboxIdentityError(
                f"dependency input is missing or unsafe: {path.name}"
            )
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def configured_image_digest(repo_root: Path) -> str:
    """Return and validate the digest-pinned devcontainer image identity."""
    payload = json.loads(
        (repo_root / ".devcontainer" / "devcontainer.json").read_text(encoding="utf-8")
    )
    image = payload.get("image")
    if not isinstance(image, str) or "@" not in image:
        raise SandboxIdentityError("devcontainer image is not digest pinned")
    digest = image.rsplit("@", 1)[1]
    if digest != EXPECTED_IMAGE_DIGEST:
        raise SandboxIdentityError("devcontainer image digest differs from policy")
    return digest


def configured_features(repo_root: Path) -> dict[str, dict[str, str]]:
    """Return and validate the exact feature and OCI lock entry."""
    payload = json.loads(
        (repo_root / ".devcontainer" / "devcontainer.json").read_text(encoding="utf-8")
    )
    expected: dict[str, dict[str, object]] = {EXPECTED_SSHD_FEATURE: {}}
    if payload.get("features") != expected:
        raise SandboxIdentityError(
            "devcontainer features differ from the reviewed SSH surface"
        )
    lock_path = repo_root / ".devcontainer" / "devcontainer-lock.json"
    if not lock_path.is_file() or lock_path.is_symlink():
        raise SandboxIdentityError("devcontainer feature lock is unavailable")
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    expected_entry = {
        "version": "1.1.0",
        "resolved": (
            f"ghcr.io/devcontainers/features/sshd@{EXPECTED_SSHD_MANIFEST_DIGEST}"
        ),
        "integrity": EXPECTED_SSHD_MANIFEST_DIGEST,
    }
    expected_lock = {"features": {EXPECTED_SSHD_FEATURE: expected_entry}}
    if lock != expected_lock:
        raise SandboxIdentityError(
            "devcontainer feature lock differs from the reviewed OCI artifact"
        )
    return {EXPECTED_SSHD_FEATURE: expected_entry}


def installed_distribution_set_sha256(site_packages: Path | None = None) -> str:
    """Hash installed distribution names and versions without local paths."""
    if site_packages is None:
        distributions = importlib.metadata.distributions()
    else:
        distributions = importlib.metadata.distributions(path=[str(site_packages)])
    installed = sorted(
        f"{distribution.metadata['Name'].lower()}=={distribution.version}"
        for distribution in distributions
    )
    return hashlib.sha256("\n".join(installed).encode("utf-8")).hexdigest()


def installed_distribution_content_sha256(site_packages: Path) -> str:
    """Hash immutable installed content without importing the environment."""
    if not site_packages.is_dir() or site_packages.is_symlink():
        raise SandboxIdentityError("installed site-packages root is unavailable")
    resolved_root = site_packages.resolve(strict=True)
    if resolved_root != site_packages:
        raise SandboxIdentityError("installed site-packages root is aliased")

    digest = hashlib.sha256()
    paths = sorted(
        resolved_root.rglob("*"),
        key=lambda candidate: candidate.relative_to(resolved_root).as_posix(),
    )
    for path in paths:
        relative = path.relative_to(resolved_root)
        if path.is_symlink():
            raise SandboxIdentityError(
                f"installed package content contains a symlink: {relative.as_posix()}"
            )
        if not path.is_file():
            continue
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(f"{path.stat().st_mode & 0o7777:o}".encode("ascii"))
        digest.update(b"\0")
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()


def installed_environment_content_sha256(
    venv_root: Path,
    approved_interpreter: Path,
) -> str:
    """Hash package and launcher content while trusting only the pinned image."""
    if not venv_root.is_dir() or venv_root.is_symlink():
        raise SandboxIdentityError("installed environment root is unavailable")
    resolved_venv = venv_root.resolve(strict=True)
    if resolved_venv != venv_root:
        raise SandboxIdentityError("installed environment root is aliased")

    approved = approved_interpreter.resolve(strict=True)
    if approved != approved_interpreter or not approved.is_file():
        raise SandboxIdentityError("approved container interpreter is unsafe")
    bin_root = venv_root / "bin"
    site_packages = venv_root / "lib" / "python3.12" / "site-packages"
    pyvenv_config = venv_root / "pyvenv.cfg"
    if not bin_root.is_dir() or bin_root.is_symlink():
        raise SandboxIdentityError("installed environment bin directory is unsafe")
    if not pyvenv_config.is_file() or pyvenv_config.is_symlink():
        raise SandboxIdentityError("installed environment pyvenv.cfg is unsafe")

    for name in ("python", "python3", "python3.12"):
        launcher = bin_root / name
        if not launcher.is_symlink() or launcher.resolve(strict=True) != approved:
            raise SandboxIdentityError(
                f"installed environment launcher is untrusted: {name}"
            )

    digest = hashlib.sha256()
    digest.update(b"pyvenv.cfg\0")
    digest.update(f"{pyvenv_config.stat().st_mode & 0o7777:o}".encode("ascii"))
    digest.update(b"\0")
    digest.update(pyvenv_config.read_bytes())
    digest.update(b"\0")

    for path in sorted(
        bin_root.rglob("*"),
        key=lambda candidate: candidate.relative_to(bin_root).as_posix(),
    ):
        relative = path.relative_to(bin_root).as_posix()
        digest.update(f"bin/{relative}".encode("utf-8"))
        digest.update(b"\0")
        if path.is_symlink():
            digest.update(b"symlink\0")
            digest.update(os.readlink(path).encode("utf-8"))
            digest.update(b"\0")
            digest.update(str(path.resolve(strict=True)).encode("utf-8"))
            digest.update(b"\0")
        elif path.is_file():
            digest.update(f"{path.stat().st_mode & 0o7777:o}".encode("ascii"))
            digest.update(b"\0")
            with path.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    digest.update(chunk)
            digest.update(b"\0")
        elif not path.is_dir():
            raise SandboxIdentityError(
                f"installed environment bin entry is unsafe: {relative}"
            )

    digest.update(b"site-packages\0")
    digest.update(installed_distribution_content_sha256(site_packages).encode("ascii"))
    digest.update(b"\0")
    return digest.hexdigest()


def _read_marker(path: Path, label: str) -> str:
    """Read one narrow digest marker and reject malformed state."""
    if not path.is_file() or path.is_symlink():
        raise SandboxIdentityError(f"{label} marker is unavailable")
    value = path.read_text(encoding="ascii").strip()
    if HEX_64.fullmatch(value) is None:
        raise SandboxIdentityError(f"{label} marker is malformed")
    return value


def _git(repo_root: Path, *arguments: str) -> str:
    """Return one Git identity value without exposing the checkout path."""
    return subprocess.run(
        ("git", *arguments),
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def build_identity(
    repo_root: Path,
    dependency_marker: Path,
    image_marker: Path,
    package_marker: Path,
    venv_root: Path,
    approved_interpreter: Path,
) -> dict[str, object]:
    """Validate construction markers and return a path-free identity mapping."""
    current_dependency = dependency_input_sha256(repo_root)
    if _read_marker(dependency_marker, "dependency input") != current_dependency:
        raise SandboxIdentityError(
            "sandbox inputs changed; delete and recreate the Codespace"
        )
    current_image = configured_image_digest(repo_root)
    if _read_marker(image_marker, "container image") != current_image.removeprefix(
        "sha256:"
    ):
        raise SandboxIdentityError(
            "container image changed; delete and recreate the Codespace"
        )
    current_package_content = installed_environment_content_sha256(
        venv_root,
        approved_interpreter,
    )
    if (
        _read_marker(package_marker, "installed environment content")
        != current_package_content
    ):
        raise SandboxIdentityError(
            "installed environment content changed; delete and recreate the Codespace"
        )
    site_packages = venv_root / "lib" / "python3.12" / "site-packages"
    current_packages = installed_distribution_set_sha256(site_packages)
    features = configured_features(repo_root)
    feature_lock_path = repo_root / ".devcontainer" / "devcontainer-lock.json"

    return {
        "git_commit": _git(repo_root, "rev-parse", "HEAD"),
        "git_tree": _git(repo_root, "rev-parse", "HEAD^{tree}"),
        "devcontainer_image_digest": current_image,
        "devcontainer_features": list(features),
        "devcontainer_feature_lock": features,
        "devcontainer_feature_lock_sha256": _sha256_file(feature_lock_path),
        "dependency_input_sha256": current_dependency,
        "installed_distribution_set_sha256": current_packages,
        "installed_environment_content_sha256": current_package_content,
        "controlled_input_sha256": {
            relative: _sha256_file(repo_root / relative)
            for relative in CONTROLLED_INPUT_RELATIVES
        },
    }
