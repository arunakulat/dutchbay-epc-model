"""Fail-closed static controls for the private P02/P03 Codespaces sandbox."""

from __future__ import annotations

import importlib.util
import json
import os
import py_compile
import subprocess
import sys
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[2]
DEVCONTAINER = REPO_ROOT / ".devcontainer" / "devcontainer.json"
DEVCONTAINER_LOCK = REPO_ROOT / ".devcontainer" / "devcontainer-lock.json"
BOOTSTRAP = REPO_ROOT / ".devcontainer" / "bootstrap_audit_review.sh"
IDENTITY = REPO_ROOT / ".devcontainer" / "audit_review_identity.py"
VERIFY = REPO_ROOT / "scripts" / "verify_1110_cloud_review_sandbox.sh"
UPLOAD = REPO_ROOT / "scripts" / "upload_1110_p03_sources_to_codespace.sh"
DOC = REPO_ROOT / "docs" / "audit" / "CLOUD_REVIEW_SANDBOX.md"

EXPECTED_IMAGE = (
    "mcr.microsoft.com/devcontainers/python:1-3.12-bookworm@"
    "sha256:7876580dc67fd460fd962f004cbeb480027e9bbc0657096f1087db11f9eaff39"
)
EXPECTED_SSHD_FEATURE = "ghcr.io/devcontainers/features/sshd:1.1.0"
EXPECTED_SSHD_MANIFEST_DIGEST = (
    "sha256:f5251b8e4325f68f7280973c6cd65daff414449c66f240621502d4e8e74eb7ee"
)
PRIVATE_SOURCE_ROOT = "/workspaces/.dutchbay-private/p03/sources"
SANDBOX_VENV = "/workspaces/.dutchbay-audit-review-venv"


def _load_p03_builder() -> ModuleType:
    builder_path = (
        REPO_ROOT
        / "docs"
        / "audit"
        / "2026-08-controlled-successor"
        / "scripts"
        / "build_primary_source_review_plan.py"
    )
    spec = importlib.util.spec_from_file_location("sandbox_p03_builder", builder_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_identity_contract() -> ModuleType:
    identity_path = REPO_ROOT / ".devcontainer" / "audit_review_identity.py"
    spec = importlib.util.spec_from_file_location("sandbox_identity", identity_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_fake_venv(root: Path) -> tuple[Path, Path, Path]:
    """Create the minimal immutable shape needed by the identity contract."""
    venv_root = root.resolve()
    bin_root = venv_root / "bin"
    site_packages = venv_root / "lib" / "python3.12" / "site-packages"
    bin_root.mkdir(parents=True)
    site_packages.mkdir(parents=True)
    (venv_root / "pyvenv.cfg").write_text(
        "home = /usr/local/bin\nversion = 3.12.13\n",
        encoding="utf-8",
    )
    approved = Path(sys.executable).resolve()
    (bin_root / "python3.12").symlink_to(approved)
    (bin_root / "python3").symlink_to("python3.12")
    (bin_root / "python").symlink_to("python3.12")
    return venv_root, site_packages, approved


def test_devcontainer_is_digest_pinned_private_and_portless() -> None:
    """The cloud environment must not float, publish the corpus or expose a port."""
    payload = json.loads(DEVCONTAINER.read_text(encoding="utf-8"))

    assert payload["image"] == EXPECTED_IMAGE
    assert payload["features"] == {EXPECTED_SSHD_FEATURE: {}}
    lock = json.loads(DEVCONTAINER_LOCK.read_text(encoding="utf-8"))
    assert lock == {
        "features": {
            EXPECTED_SSHD_FEATURE: {
                "version": "1.1.0",
                "resolved": (
                    "ghcr.io/devcontainers/features/sshd@"
                    f"{EXPECTED_SSHD_MANIFEST_DIGEST}"
                ),
                "integrity": EXPECTED_SSHD_MANIFEST_DIGEST,
            }
        }
    }
    assert payload["postCreateCommand"] == (
        "bash .devcontainer/bootstrap_audit_review.sh"
    )
    assert payload["remoteEnv"] == {
        "DUTCHBAY_VENV": SANDBOX_VENV,
        "DUTCHBAY_P03_SOURCE_ROOT": PRIVATE_SOURCE_ROOT,
        "PATH": f"{SANDBOX_VENV}/bin:${{containerEnv:PATH}}",
        "PYTHONPATH": "${containerWorkspaceFolder}",
    }
    assert payload["forwardPorts"] == []
    assert payload["portsAttributes"] == {}
    assert "/workspaces/${localWorkspaceFolderBasename}" not in json.dumps(payload)


def test_scripts_keep_private_inputs_outside_checkout_and_hold_side() -> None:
    """Setup and preflight must preserve the evidence and release boundaries."""
    bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
    identity = IDENTITY.read_text(encoding="utf-8")
    verify = VERIFY.read_text(encoding="utf-8")
    upload = UPLOAD.read_text(encoding="utf-8")
    combined = bootstrap + identity + verify + upload

    assert PRIVATE_SOURCE_ROOT in combined
    assert SANDBOX_VENV in combined
    assert "CODESPACES" in combined
    assert ".devcontainer/devcontainer.json" in identity
    assert ".devcontainer/devcontainer-lock.json" in identity
    assert ".devcontainer/bootstrap_audit_review.sh" in identity
    assert 'realpath -e "$SOURCE_ROOT"' in combined
    assert "private P03 source root must not be a symlink" in combined
    assert '"completion_authorized": False' in bootstrap
    assert '"completion_authorized": False' in verify
    assert '"release_status": "HOLD"' in bootstrap
    assert '"release_status": "HOLD"' in verify
    assert "tests/lint/test_audit_findings_current_state_overlay.py" in verify
    assert "tests/lint/test_audit_primary_source_control.py" in verify
    assert "scripts/verify_p03_primary_sources.py" in verify
    assert "validate_published_pack.py" in verify
    assert '"$resolved_source_root/original"' in upload
    assert '"$resolved_source_root/converted"' in upload
    assert '"$resolved_source_root/."' not in upload
    assert "git merge --ff-only origin/main" not in upload
    assert "git switch --detach origin/main" in upload
    assert 'main|"")' in upload
    assert 'test -z "$(git status --porcelain)"' in upload
    assert "REMOTE_TRANSPORT_SMOKE" in upload
    assert 'cmp -- "$repo_root/.devcontainer/devcontainer.json"' in upload
    assert "REMOTE_TRANSPORT_CLEANUP" in upload
    assert "trap cleanup_transport_probe EXIT" in upload
    assert 'return "$exit_status"' in upload
    assert "delete and recreate it before retrying" in upload
    assert "DUTCHBAY_P03_CLOUD_INGRESS_AUTHORIZED" in upload
    assert 'CONTAINER_PYTHON="/usr/local/bin/python3.12"' in bootstrap
    assert 'CONTAINER_PYTHON="/usr/local/bin/python3.12"' in verify
    assert '"$CONTAINER_PYTHON" -S' in bootstrap
    assert '"$CONTAINER_PYTHON" -S' in verify
    assert 'PYTHONPATH="$PWD/.devcontainer" python3.12' not in combined
    assert "PYTHONDONTWRITEBYTECODE=1" in bootstrap
    assert "PYTHONDONTWRITEBYTECODE=1" in verify
    assert '"installed_environment_content_sha256"' in bootstrap
    assert '"installed_distribution_content_sha256"' not in bootstrap
    assert bootstrap.index("package_content_digest=$(package_content_fingerprint)") < (
        bootstrap.index("./check_venv.sh --no-bootstrap")
    )
    assert verify.index('"$CONTAINER_PYTHON" -S') < verify.index(
        '"$VENV_ROOT/bin/python" -m pytest'
    )
    for receipt_field in (
        "git_commit",
        "git_tree",
        "devcontainer_image_digest",
        "devcontainer_features",
        "devcontainer_feature_lock",
        "devcontainer_feature_lock_sha256",
        "dependency_input_sha256",
        "installed_distribution_set_sha256",
        "installed_environment_content_sha256",
        "controlled_input_sha256",
        "network_boundary",
    ):
        assert receipt_field in combined
    assert "actions/upload-artifact" not in combined
    assert "forwardPorts" not in combined
    assert BOOTSTRAP.stat().st_mode & 0o111
    assert VERIFY.stat().st_mode & 0o111
    assert UPLOAD.stat().st_mode & 0o111


def test_identity_contract_binds_ingress_and_rejects_stale_markers(
    tmp_path: Path,
) -> None:
    """Receipts must bind the transfer control and reject changed inputs."""
    identity = _load_identity_contract()
    dependency_digest = identity.dependency_input_sha256(REPO_ROOT)
    image_digest = identity.configured_image_digest(REPO_ROOT)
    dependency_marker = tmp_path / "dependency.sha256"
    image_marker = tmp_path / "image.sha256"
    package_marker = tmp_path / "packages.sha256"
    venv_root, site_packages, approved_interpreter = _make_fake_venv(tmp_path / "venv")
    (site_packages / "probe.py").write_text("VALUE = 1\n", encoding="utf-8")
    dependency_marker.write_text(f"{dependency_digest}\n", encoding="ascii")
    image_marker.write_text(
        f"{image_digest.removeprefix('sha256:')}\n", encoding="ascii"
    )
    package_marker.write_text(
        f"{identity.installed_environment_content_sha256(venv_root, approved_interpreter)}\n",
        encoding="ascii",
    )

    receipt = identity.build_identity(
        REPO_ROOT,
        dependency_marker,
        image_marker,
        package_marker,
        venv_root,
        approved_interpreter,
    )
    assert receipt["dependency_input_sha256"] == dependency_digest
    assert receipt["devcontainer_image_digest"] == image_digest
    assert receipt["devcontainer_features"] == [EXPECTED_SSHD_FEATURE]
    assert receipt["devcontainer_feature_lock"] == {
        EXPECTED_SSHD_FEATURE: {
            "version": "1.1.0",
            "resolved": (
                f"ghcr.io/devcontainers/features/sshd@{EXPECTED_SSHD_MANIFEST_DIGEST}"
            ),
            "integrity": EXPECTED_SSHD_MANIFEST_DIGEST,
        }
    }
    assert receipt["devcontainer_feature_lock_sha256"]
    assert receipt["installed_environment_content_sha256"] == (
        identity.installed_environment_content_sha256(
            venv_root,
            approved_interpreter,
        )
    )
    assert (
        "scripts/upload_1110_p03_sources_to_codespace.sh"
        in receipt["controlled_input_sha256"]
    )

    dependency_marker.write_text(f"{'0' * 64}\n", encoding="ascii")
    try:
        identity.build_identity(
            REPO_ROOT,
            dependency_marker,
            image_marker,
            package_marker,
            venv_root,
            approved_interpreter,
        )
    except identity.SandboxIdentityError as exc:
        assert "delete and recreate" in str(exc)
    else:  # pragma: no cover - explicit fail branch
        raise AssertionError("stale sandbox dependency marker was accepted")

    dependency_marker.write_text(f"{dependency_digest}\n", encoding="ascii")
    package_marker.write_text(f"{'0' * 64}\n", encoding="ascii")
    try:
        identity.build_identity(
            REPO_ROOT,
            dependency_marker,
            image_marker,
            package_marker,
            venv_root,
            approved_interpreter,
        )
    except identity.SandboxIdentityError as exc:
        assert "installed environment content" in str(exc)
        assert "delete and recreate" in str(exc)
    else:  # pragma: no cover - explicit fail branch
        raise AssertionError("stale installed environment-content marker was accepted")


def test_package_content_fingerprint_detects_drift_without_importing_site(
    tmp_path: Path,
) -> None:
    """Same-version edits must fail without executing .pth or sitecustomize code."""
    identity = _load_identity_contract()
    site_packages = (tmp_path / "site-packages").resolve()
    site_packages.mkdir()
    package = site_packages / "probe.py"
    package.write_text("VALUE = 1\n", encoding="utf-8")
    metadata = site_packages / "probe-1.0.dist-info"
    metadata.mkdir()
    (metadata / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: probe\nVersion: 1.0\n",
        encoding="utf-8",
    )
    first = identity.installed_distribution_content_sha256(site_packages)
    package.write_text("VALUE = 2\n", encoding="utf-8")
    second = identity.installed_distribution_content_sha256(site_packages)
    assert second != first

    sentinel = tmp_path / "sitecustomize-executed"
    (site_packages / "sitecustomize.py").write_text(
        f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('executed')\n",
        encoding="utf-8",
    )
    code = (
        f"import sys; sys.path.insert(0, {str(IDENTITY.parent)!r}); "
        "from pathlib import Path; "
        "from audit_review_identity import installed_distribution_content_sha256; "
        f"print(installed_distribution_content_sha256(Path({str(site_packages)!r})))"
    )
    result = subprocess.run(
        (sys.executable, "-S", "-c", code),
        env={**os.environ, "PYTHONPATH": str(site_packages)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert not sentinel.exists()

    before_bytecode = identity.installed_distribution_content_sha256(site_packages)
    bytecode = site_packages / "sitecustomize.pyc"
    py_compile.compile(
        str(site_packages / "sitecustomize.py"),
        cfile=str(bytecode),
        doraise=True,
    )
    with_bytecode = identity.installed_distribution_content_sha256(site_packages)
    assert with_bytecode != before_bytecode
    bytecode.write_bytes(bytecode.read_bytes() + b"tamper")
    after_tamper = identity.installed_distribution_content_sha256(site_packages)
    assert after_tamper != with_bytecode


def test_absolute_attestor_rejects_shadowed_venv_launcher(tmp_path: Path) -> None:
    """A PATH-preferred venv launcher must never execute before attestation."""
    venv_root, _, approved_interpreter = _make_fake_venv(tmp_path / "venv")
    identity = _load_identity_contract()
    identity.installed_environment_content_sha256(venv_root, approved_interpreter)

    sentinel = tmp_path / "shadow-launcher-executed"
    shadow = venv_root / "bin" / "python3.12"
    shadow.unlink()
    shadow.write_text(
        f"#!/usr/bin/env bash\nprintf executed > {str(sentinel)!r}\n",
        encoding="utf-8",
    )
    shadow.chmod(0o755)
    code = (
        f"import sys; sys.path.insert(0, {str(IDENTITY.parent)!r}); "
        "from pathlib import Path; "
        "from audit_review_identity import installed_environment_content_sha256; "
        f"print(installed_environment_content_sha256(Path({str(venv_root)!r}), "
        f"Path({str(approved_interpreter)!r})))"
    )
    result = subprocess.run(
        (str(approved_interpreter), "-S", "-c", code),
        env={
            **os.environ,
            "PATH": f"{venv_root / 'bin'}:{os.environ['PATH']}",
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "launcher is untrusted" in result.stderr
    assert not sentinel.exists()


def test_feature_lock_rejects_missing_changed_or_extra_entries(tmp_path: Path) -> None:
    """The executable SSH feature must remain bound to one reviewed OCI artifact."""
    identity = _load_identity_contract()
    config = json.loads(DEVCONTAINER.read_text(encoding="utf-8"))
    lock = json.loads(DEVCONTAINER_LOCK.read_text(encoding="utf-8"))
    devcontainer_dir = tmp_path / ".devcontainer"
    devcontainer_dir.mkdir()
    config_path = devcontainer_dir / "devcontainer.json"
    lock_path = devcontainer_dir / "devcontainer-lock.json"

    changed_resolved = json.loads(json.dumps(lock))
    changed_resolved["features"][EXPECTED_SSHD_FEATURE]["resolved"] = (
        "ghcr.io/devcontainers/features/sshd@" + f"sha256:{'0' * 64}"
    )
    changed_integrity = json.loads(json.dumps(lock))
    changed_integrity["features"][EXPECTED_SSHD_FEATURE][
        "integrity"
    ] = f"sha256:{'0' * 64}"
    extra_feature = json.loads(json.dumps(lock))
    extra_feature["features"]["ghcr.io/example/extra:1"] = {
        "version": "1.0.0",
        "resolved": f"ghcr.io/example/extra@sha256:{'0' * 64}",
        "integrity": f"sha256:{'0' * 64}",
    }
    mismatched_config = json.loads(json.dumps(config))
    mismatched_config["features"] = {"ghcr.io/devcontainers/features/sshd:1": {}}

    invalid_cases = (
        (config, None),
        (config, changed_resolved),
        (config, changed_integrity),
        (config, extra_feature),
        (mismatched_config, lock),
    )
    for candidate_config, candidate_lock in invalid_cases:
        config_path.write_text(json.dumps(candidate_config), encoding="utf-8")
        if candidate_lock is None:
            if lock_path.exists():
                lock_path.unlink()
        else:
            lock_path.write_text(json.dumps(candidate_lock), encoding="utf-8")
        try:
            identity.configured_features(tmp_path)
        except identity.SandboxIdentityError:
            pass
        else:  # pragma: no cover - explicit fail branch
            raise AssertionError("invalid SSH feature lock was accepted")


def test_private_source_root_satisfies_the_merged_p03_scope_contract(
    tmp_path: Path,
) -> None:
    """The configured terminal-directory shape must remain accepted by P03."""
    builder = _load_p03_builder()
    source_root = tmp_path / "private" / "p03" / "sources"
    source_root.mkdir(parents=True)

    assert builder._safe_external_root(source_root) == source_root

    rejected = tmp_path / "private" / "p03-sources"
    rejected.mkdir()
    try:
        builder._safe_external_root(rejected)
    except builder.PrimarySourceControlError as exc:
        assert exc.code == "SOURCE_ROOT_SCOPE"
    else:  # pragma: no cover - explicit fail branch
        raise AssertionError("broad P03 source-root name was accepted")


def test_upload_helper_rejects_unsafe_roots_before_calling_gh(tmp_path: Path) -> None:
    """Unset, root, broad and symlinked inputs must fail before cloud access."""
    marker = tmp_path / "gh-was-called"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_gh = fake_bin / "gh"
    fake_gh.write_text(
        f"#!/usr/bin/env bash\nprintf called > {marker!s}\nexit 99\n",
        encoding="utf-8",
    )
    fake_gh.chmod(0o755)

    base_env = os.environ.copy()
    base_env.update(
        {
            "PATH": f"{fake_bin}:{base_env['PATH']}",
            "DUTCHBAY_P03_CLOUD_INGRESS_AUTHORIZED": "YES",
            "DUTCHBAY_VENV": "/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv",
        }
    )
    base_env.pop("DUTCHBAY_P03_RETAINED_SOURCE_ROOT", None)

    unsafe_roots: list[str | None] = [None, "/", str(tmp_path)]
    real_sources = tmp_path / "narrow" / "sources"
    real_sources.mkdir(parents=True)
    symlinked_sources = tmp_path / "linked-sources"
    symlinked_sources.symlink_to(real_sources, target_is_directory=True)
    unsafe_roots.append(str(symlinked_sources))

    for unsafe_root in unsafe_roots:
        env = base_env.copy()
        if unsafe_root is not None:
            env["DUTCHBAY_P03_RETAINED_SOURCE_ROOT"] = unsafe_root
        result = subprocess.run(
            (str(UPLOAD),),
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 2
        assert not marker.exists()


def test_transport_smoke_cleans_probe_after_copy_or_ssh_failure(
    tmp_path: Path,
) -> None:
    """The exact non-sensitive probe must not poison a reusable sandbox."""
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_gh = fake_bin / "gh"
    fake_gh.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
case "$2" in
  cp)
    printf copied > "$FAKE_REMOTE_MARKER"
    exit "${FAKE_CP_EXIT:-0}"
    ;;
  ssh)
    count=0
    if [ -f "$FAKE_SSH_COUNT" ]; then
      count=$(<"$FAKE_SSH_COUNT")
    fi
    count=$((count + 1))
    printf '%s\n' "$count" > "$FAKE_SSH_COUNT"
    if [ "$count" -eq 1 ] && [ "${FAKE_FIRST_SSH_EXIT:-0}" -ne 0 ]; then
      exit "$FAKE_FIRST_SSH_EXIT"
    fi
    if [ -e "$FAKE_REMOTE_MARKER" ]; then
      rm -- "$FAKE_REMOTE_MARKER"
    fi
    ;;
  *) exit 99 ;;
esac
""",
        encoding="utf-8",
    )
    fake_gh.chmod(0o755)

    for cp_exit, ssh_exit in ((33, 0), (0, 44)):
        marker = tmp_path / f"remote-{cp_exit}-{ssh_exit}"
        ssh_count = tmp_path / f"ssh-count-{cp_exit}-{ssh_exit}"
        env = {
            **os.environ,
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "FAKE_REMOTE_MARKER": str(marker),
            "FAKE_SSH_COUNT": str(ssh_count),
            "FAKE_CP_EXIT": str(cp_exit),
            "FAKE_FIRST_SSH_EXIT": str(ssh_exit),
        }
        command = f"source {UPLOAD!s}; run_transport_smoke fake-codespace"
        result = subprocess.run(
            ("bash", "-c", command),
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == (cp_exit or ssh_exit)
        assert not marker.exists()
        assert ssh_count.read_text(encoding="ascii").strip() == (
            "1" if cp_exit else "2"
        )


def test_runbook_requires_population_exact_additive_results() -> None:
    """The operator contract must reject structural PASS as semantic closure."""
    text = DOC.read_text(encoding="utf-8")
    normalized = " ".join(text.split())

    for required in (
        "all 111 finding IDs",
        "all 74 retained objects",
        "all 42 claims",
        "new additive result artifact",
        "completion_authorized=false",
        "release_status=HOLD",
        "Do not commit, publish, upload as an Actions artifact",
        "Structural or hash PASS does not establish semantic support",
        "scripts/upload_1110_p03_sources_to_codespace.sh",
        "creator-private Codespace attached to the public source repository",
        "GitHub Codespaces permits outbound internet access",
        "HEAD == origin/main",
        "git switch --detach origin/main",
        "clean detached exact-main state",
        "SSH daemon feature is pinned to version `1.1.0`",
        "`.devcontainer/devcontainer-lock.json`",
        "resolved OCI manifest digest and integrity",
        "installed environment-content fingerprint",
        "three Python launchers must resolve to `/usr/local/bin/python3.12`",
        "content-bound reuse control, not a hash-complete external package lock",
    ):
        assert required in normalized
