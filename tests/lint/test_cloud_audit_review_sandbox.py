"""Fail-closed static controls for the private P02/P03 Codespaces sandbox."""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
import py_compile
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[2]
DEVCONTAINER = REPO_ROOT / ".devcontainer" / "devcontainer.json"
DEVCONTAINER_LOCK = REPO_ROOT / ".devcontainer" / "devcontainer-lock.json"
DOCKERFILE = REPO_ROOT / ".devcontainer" / "Dockerfile"
SSHD_INSTALLER = REPO_ROOT / ".devcontainer" / "install_audit_review_sshd.sh"
SSHD_START = REPO_ROOT / ".devcontainer" / "start_audit_review_sshd.sh"
SSHD_ATTESTOR = REPO_ROOT / ".devcontainer" / "attest_audit_review_sshd.sh"
SSHD_READINESS = REPO_ROOT / ".devcontainer" / "sshd_readiness.py"
BOOTSTRAP = REPO_ROOT / ".devcontainer" / "bootstrap_audit_review.sh"
IDENTITY = REPO_ROOT / ".devcontainer" / "audit_review_identity.py"
VERIFY = REPO_ROOT / "scripts" / "verify_1110_cloud_review_sandbox.sh"
CREATE_CODESPACE = REPO_ROOT / "scripts" / "create_1110_cloud_review_codespace.sh"
CANDIDATE_CODESPACE = REPO_ROOT / "scripts" / "prove_1110_candidate_codespace.sh"
UPLOAD = REPO_ROOT / "scripts" / "upload_1110_p03_sources_to_codespace.sh"
DOC = REPO_ROOT / "docs" / "audit" / "CLOUD_REVIEW_SANDBOX.md"
IMAGE_SMOKE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "audit-cloud-sandbox.yml"
PATH_CLASSIFIER = REPO_ROOT / "scripts" / "classify_1110_cloud_sandbox_paths.sh"

EXPECTED_IMAGE = (
    "mcr.microsoft.com/devcontainers/python:1-3.12-bookworm@"
    "sha256:7876580dc67fd460fd962f004cbeb480027e9bbc0657096f1087db11f9eaff39"
)
PRIVATE_SOURCE_ROOT = "/workspaces/.dutchbay-private/p03/sources"
SANDBOX_VENV = "/workspaces/.dutchbay-audit-review-venv"
REQUIRED_SSHD_EFFECTIVE_POLICY = {
    "allowagentforwarding": "no",
    "allowgroups": "ssh",
    "allowstreamlocalforwarding": "no",
    "allowtcpforwarding": "no",
    "authenticationmethods": "publickey",
    "authorizedkeyscommand": "none",
    "authorizedkeyscommanduser": "none",
    "authorizedkeysfile": ".ssh/authorized_keys",
    "authorizedprincipalscommand": "none",
    "authorizedprincipalscommanduser": "none",
    "authorizedprincipalsfile": "none",
    "chrootdirectory": "none",
    "disableforwarding": "yes",
    "forcecommand": "none",
    "gatewayports": "no",
    "gssapiauthentication": "no",
    "hostbasedauthentication": "no",
    "kbdinteractiveauthentication": "no",
    "kerberosauthentication": "no",
    "passwordauthentication": "no",
    "permitemptypasswords": "no",
    "permitrootlogin": "no",
    "permittunnel": "no",
    "port": "2222",
    "pubkeyauthentication": "yes",
    "permituserenvironment": "no",
    "strictmodes": "yes",
    "trustedusercakeys": "none",
    "usepam": "yes",
    "x11forwarding": "no",
}
REQUIRED_SSHD_SETENV_POLICY = {
    "DUTCHBAY_P03_SOURCE_ROOT=/workspaces/.dutchbay-private/p03/sources",
    "DUTCHBAY_VENV=/workspaces/.dutchbay-audit-review-venv",
    (
        "PATH=/workspaces/.dutchbay-audit-review-venv/bin:/usr/local/bin:"
        "/usr/local/sbin:/usr/bin:/usr/sbin:/bin:/sbin"
    ),
    "PYTHONPATH=/workspaces/dutchbay-epc-model",
}
REQUIRED_SSHD_SETENV_DIRECTIVE = (
    "SetEnv DUTCHBAY_VENV=/workspaces/.dutchbay-audit-review-venv "
    "DUTCHBAY_P03_SOURCE_ROOT=/workspaces/.dutchbay-private/p03/sources "
    "PYTHONPATH=/workspaces/dutchbay-epc-model "
    "PATH=/workspaces/.dutchbay-audit-review-venv/bin:/usr/local/bin:"
    "/usr/local/sbin:/usr/bin:/usr/sbin:/bin:/sbin"
)
REQUIRED_SSHD_INSTALLER_DIRECTIVES = {
    "AllowAgentForwarding no",
    "AllowGroups ssh",
    "AllowStreamLocalForwarding no",
    "AllowTcpForwarding no",
    "AuthenticationMethods publickey",
    "AuthorizedKeysCommand none",
    "AuthorizedKeysFile .ssh/authorized_keys",
    "AuthorizedPrincipalsCommand none",
    "AuthorizedPrincipalsFile none",
    "ChrootDirectory none",
    "DisableForwarding yes",
    "ForceCommand none",
    "GatewayPorts no",
    "GSSAPIAuthentication no",
    "HostbasedAuthentication no",
    "KbdInteractiveAuthentication no",
    "KerberosAuthentication no",
    "PasswordAuthentication no",
    "PermitEmptyPasswords no",
    "PermitRootLogin no",
    "PermitTunnel no",
    "PermitUserEnvironment no",
    "PubkeyAuthentication yes",
    "StrictModes yes",
    "TrustedUserCAKeys none",
    "UsePAM yes",
    "X11Forwarding no",
    REQUIRED_SSHD_SETENV_DIRECTIVE,
}
VALID_SSH_HOST_PUBLIC_KEYS = [
    (
        "ecdsa-sha2-nistp256 "
        "AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNTYAAABBBC/luIx3r4Aj"
        "onGUUqe+wFqozx9LwdzJGTLwXfTNO6ZpFUtbGmQMo9/J3LWOQAlAmhTOi0CqdbT"
        "CQa9WxDh6BM4="
    ),
    (
        "ssh-ed25519 "
        "AAAAC3NzaC1lZDI1NTE5AAAAIJl+s4QDJ217EWiQ1IbrD64el5EqIn08jryrIRS/yfy1"
    ),
    (
        "ssh-rsa "
        "AAAAB3NzaC1yc2EAAAADAQABAAABAQDDn2OpZJ1xb7yKVEC/DSgFqw0ELsNzfRGE"
        "HIz+HB2R22aLa+UNCsvZN+JpduS6u2cLyZsP4srwGCJqs4vYlz5iuwqG0ml497hv"
        "CMIBIh5xvOxSCMDERHr3z3IfVX9V5Iw7/weTXf9TvB7iS2Az/deNGQX8s42n3nU+"
        "b/DLxyxZKgiBc+mxPUFkC8zW4G2h3rrEfPQTO8XlATckfUTIrgGNcAZ7bMnbvbXB"
        "PU2RW0cXN4tT+PlRNesDtM+VyP7j4Lf5NuQ/3//w4mBMB8jwx4Md2TqEPyFRXBhkc"
        "8Jey+VOCWOVtYWhEcj/VNx4ct1nrX4JmB0VE+rumOeXI/1WngXJ"
    ),
]
VALID_SSH_HOST_FINGERPRINTS = [
    "SHA256:G6DtjboP0xJ+v9+06j+30NN48HtV3VpQZy2hw/IeQ9k",
    "SHA256:pG0K4wv35j35K8FrqCpcDPIn78prGMX/KIVPmq8Ff0s",
    "SHA256:SjN5PWOvgfrRwCaWyf/gOyrXdQ6cFOrpZJUyDhoTfWU",
]
INDEPENDENT_DEPENDENCY_INPUT_RELATIVES = (
    "requirements.txt",
    "pyproject.toml",
    "constraints.txt",
    "check_venv.sh",
    "dutchbay_bootstrap_rules.py",
    "go_with_the_flow_rules_v3_0_clean.csv",
    ".devcontainer/devcontainer.json",
    ".devcontainer/devcontainer-lock.json",
    ".devcontainer/Dockerfile",
    ".devcontainer/install_audit_review_sshd.sh",
    ".devcontainer/start_audit_review_sshd.sh",
    ".devcontainer/attest_audit_review_sshd.sh",
    ".devcontainer/sshd_readiness.py",
    ".devcontainer/bootstrap_audit_review.sh",
    ".devcontainer/audit_review_identity.py",
    "scripts/create_1110_cloud_review_codespace.sh",
    "scripts/prove_1110_candidate_codespace.sh",
)
INDEPENDENT_CONTROLLED_INPUT_RELATIVES = (
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
    "scripts/create_1110_cloud_review_codespace.sh",
    "scripts/prove_1110_candidate_codespace.sh",
    ".devcontainer/devcontainer.json",
    ".devcontainer/devcontainer-lock.json",
    ".devcontainer/Dockerfile",
    ".devcontainer/install_audit_review_sshd.sh",
    ".devcontainer/start_audit_review_sshd.sh",
    ".devcontainer/attest_audit_review_sshd.sh",
    ".devcontainer/sshd_readiness.py",
    ".devcontainer/bootstrap_audit_review.sh",
    ".devcontainer/audit_review_identity.py",
)
INDEPENDENT_BOOTSTRAP_SOURCE_STATES = {
    "private_root_empty",
    "private_root_populated",
}
INDEPENDENT_VERIFICATION_SOURCE_STATES = {
    "private_root_empty_p03_not_executed",
    "private_root_populated_p03_structural_verification_passed",
}


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


def _load_sshd_readiness() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "sandbox_sshd_readiness", SSHD_READINESS
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ssh_wire_string(value: bytes) -> bytes:
    return len(value).to_bytes(4, "big") + value


def _ssh_public_key_line(algorithm: str, *fields: bytes) -> str:
    blob = b"".join(
        [_ssh_wire_string(algorithm.encode("ascii"))]
        + [_ssh_wire_string(field) for field in fields]
    )
    return f"{algorithm} {base64.b64encode(blob).decode('ascii')}"


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


def _sample_sandbox_identity(controlled_paths: tuple[str, ...]) -> dict[str, object]:
    return {
        "git_commit": "1" * 40,
        "git_tree": "2" * 40,
        "devcontainer_base_image_digest": (
            "sha256:7876580dc67fd460fd962f004cbeb480027e9bbc0657096f1087db11f9eaff39"
        ),
        "repository_configured_devcontainer_features": [
            "ghcr.io/devcontainers/features/sshd@"
            "sha256:f5251b8e4325f68f7280973c6cd65daff414449c66f240621502d4e8e74eb7ee"
        ],
        "base_image_embedded_feature_metadata": [
            "ghcr.io/devcontainers/features/common-utils:2",
            "ghcr.io/devcontainers/features/git:1",
            "ghcr.io/devcontainers/features/node:1",
            "ghcr.io/devcontainers/features/python:1",
        ],
        "dependency_input_sha256": "4" * 64,
        "installed_distribution_set_sha256": "5" * 64,
        "installed_environment_content_sha256": "6" * 64,
        "controlled_input_sha256": {path: "7" * 64 for path in controlled_paths},
    }


def _with_sshd_self_digest(payload: dict[str, object]) -> dict[str, object]:
    """Return a copied SSH identity with a self-digest for its current fields."""
    result = dict(payload)
    result.pop("sshd_identity_sha256", None)
    canonical = json.dumps(result, sort_keys=True, separators=(",", ":"))
    result["sshd_identity_sha256"] = hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()
    return result


def _sample_sshd_identity() -> dict[str, object]:
    payload: dict[str, object] = {
        "ssh_transport_packages": [
            "lsof|amd64|install ok installed|4.95.0",
            "openssh-client|amd64|install ok installed|1:9.2p1",
            "openssh-server|amd64|install ok installed|1:9.2p1",
            "openssh-sftp-server|amd64|install ok installed|1:9.2p1",
        ],
        "sshd_effective_config_sha256": "8" * 64,
        "sshd_transport_content_sha256": "9" * 64,
        "sshd_host_public_key_fingerprints": [
            f"SHA256:{'A' * 43}",
            f"SHA256:{'B' * 43}",
            f"SHA256:{'C' * 43}",
        ],
    }
    return _with_sshd_self_digest(payload)


def test_devcontainer_is_digest_pinned_private_and_portless() -> None:
    """The cloud environment must not float, publish the corpus or expose a port."""
    payload = json.loads(DEVCONTAINER.read_text(encoding="utf-8"))

    assert payload["build"] == {"dockerfile": "Dockerfile", "context": ".."}
    assert "image" not in payload
    assert payload["features"] == {"ghcr.io/devcontainers/features/sshd:1.1.0": {}}
    assert json.loads(DEVCONTAINER_LOCK.read_text(encoding="utf-8")) == {
        "features": {
            "ghcr.io/devcontainers/features/sshd:1.1.0": {
                "version": "1.1.0",
                "resolved": (
                    "ghcr.io/devcontainers/features/sshd@"
                    "sha256:f5251b8e4325f68f7280973c6cd65daff414449c66f240621502d4e8e74eb7ee"
                ),
                "integrity": (
                    "sha256:f5251b8e4325f68f7280973c6cd65daff414449c66f240621502d4e8e74eb7ee"
                ),
            }
        }
    }
    assert not DEVCONTAINER_LOCK.read_bytes().endswith(b"\n")
    assert payload["overrideCommand"] is True
    assert payload["init"] is True
    assert payload["containerUser"] == "root"
    assert payload["remoteUser"] == "vscode"
    assert payload["postCreateCommand"] == (
        "bash .devcontainer/bootstrap_audit_review.sh"
    )
    assert payload["postStartCommand"] == (
        "bash .devcontainer/start_audit_review_sshd.sh --start"
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


def test_repository_owned_ssh_transport_is_narrow_and_base_pinned() -> None:
    """The CLI transport must avoid mutable Features and unrelated apt sources."""
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    installer = SSHD_INSTALLER.read_text(encoding="utf-8")

    assert dockerfile.splitlines()[0] == f"FROM {EXPECTED_IMAGE}"
    assert dockerfile.count("FROM ") == 1
    assert "install_audit_review_sshd.sh" in dockerfile
    assert "sshd_readiness.py" in dockerfile
    assert "ENTRYPOINT" not in dockerfile
    assert "CMD" not in dockerfile
    assert "Dir::Etc::sourcelist=$DEBIAN_SOURCES" in installer
    assert "Dir::Etc::sourceparts=-" in installer
    assert "lsof openssh-client openssh-server" in installer
    for directive in REQUIRED_SSHD_INSTALLER_DIRECTIVES:
        assert directive in installer
    assert "\nPort 2222\n" not in installer
    assert "official sshd Feature owns the single Port 2222 directive" in installer
    assert "yarn" not in installer.lower()
    assert installer.index("/usr/sbin/sshd -t") < installer.index(
        "-name 'ssh_host_*_key*' -delete"
    )
    start = SSHD_START.read_text(encoding="utf-8")
    assert "/usr/bin/ssh-keygen -A" in start
    assert '/usr/bin/flock --exclusive --wait "$LOCK_WAIT_SECONDS" 9' in start
    assert start.count("/usr/bin/timeout --signal=TERM --kill-after=2") == 3
    assert "exec 9>/run/dutchbay-sshd-start.lock" in start
    assert start.index('/usr/bin/unlink -- "$SSHD_READY_MARKER"') < start.index(
        "/usr/bin/ssh-keygen -A"
    )
    assert start.index("/etc/init.d/ssh start") < start.index(
        "/usr/local/lib/dutchbay/sshd_readiness.py 15"
    )
    assert start.index("/usr/local/lib/dutchbay/sshd_readiness.py 15") < (
        start.index("marker_tmp=$(")
    )
    assert 'SSHD_READY_VALUE="sshd_ready_before_audit_bootstrap"' in start
    assert "/run/dutchbay-sshd-runtime.ready" in start
    attestor = SSHD_ATTESTOR.read_text(encoding="utf-8")
    assert "build_sshd_transport_identity" in attestor
    assert "/usr/sbin/sshd -T" in attestor
    assert '-C "$connection_context"' in attestor
    assert "build_sshd_session_connection_context" in attestor
    assert '"${SSH_CONNECTION:-}"' in attestor
    assert '"${SSH_CLIENT:-}"' in attestor
    assert "--construction" in attestor
    assert "--session" in attestor
    assert "sshd_drop_in_population=(/etc/ssh/sshd_config.d/*)" in attestor
    assert 'Path("/etc/ssh/sshd_config")' not in attestor
    assert "SSHD_CONFIGURATION_PATHS" in attestor
    assert 'Path("/usr/local/share/ssh-init.sh")' in attestor
    assert '/usr/bin/ssh-keygen -y -f "$key"' in attestor
    assert '[ "${derived%% *}" = "$expected_algorithm" ]' in attestor
    assert SSHD_INSTALLER.stat().st_mode & 0o111


def test_ci_builds_and_boots_exact_audit_review_image() -> None:
    """The merge gate must exercise the locked Dev Container lifecycle."""
    workflow = IMAGE_SMOKE_WORKFLOW.read_text(encoding="utf-8")
    classifier = PATH_CLASSIFIER.read_text(encoding="utf-8")

    assert "pull_request:\n    paths:" not in workflow
    assert "permissions:\n  contents: read" in workflow
    assert "persist-credentials: false" in workflow
    assert "pull_request.head.sha || github.sha" in workflow
    assert 'test "$(git rev-parse HEAD)" = "$EXPECTED_SHA"' in workflow
    assert "Exact candidate head: `%s`" in workflow
    assert "scripts/classify_1110_cloud_sandbox_paths.sh" in workflow
    assert "git diff --name-only -z --diff-filter=ACDMRT" in classifier
    assert ".devcontainer/*|.dockerignore" in classifier
    assert "done < <(git diff" not in classifier
    assert '"$BASE_SHA" "$HEAD_SHA" > "$changed_paths"' in classifier
    assert "base commit is unavailable" in classifier
    assert "head commit is unavailable" in classifier
    assert 'if [ ! -s "$changed_paths" ]' in classifier
    assert "relevant=%s" in workflow
    assert "@devcontainers/cli@0.88.0" in workflow
    assert "sha512-sMkruPy/icfov20mdQh2EjFYZogxvMEZptDEvg5/" in workflow
    assert "npm view @devcontainers/cli@0.88.0 dist.integrity" in workflow
    assert 'test "$(devcontainer --version)" = "0.88.0"' in workflow
    assert "devcontainer up" in workflow
    assert workflow.count("devcontainer up") == 2
    assert '--workspace-folder "$GITHUB_WORKSPACE"' in workflow
    assert "--expect-existing-container" in workflow
    assert "--frozen-lockfile" in workflow
    assert "--remote-env CODESPACES=true" in workflow
    assert "--remote-env CODESPACE_NAME=dutchbay-ci-audit-review" in workflow
    assert (
        workflow.count(
            "--remote-env DUTCHBAY_SANDBOX_EXECUTION_HOST="
            "github_actions_devcontainer_emulation"
        )
        == 2
    )
    assert workflow.count("checkout_status=$(git status --porcelain=v1)") == 4
    assert 'test -z "$(git status' not in workflow
    assert "bootstrap-receipt.json" in workflow
    assert '"environment": "github_actions_devcontainer_emulation"' in workflow
    assert (
        '"network_boundary": "github_actions_hosted_runner_outbound_egress_available"'
    ) in workflow
    assert '"git_commit": sys.argv[2]' in workflow
    assert "label=devcontainer.local_folder=$GITHUB_WORKSPACE" in workflow
    assert "docker exec --user vscode" in workflow
    assert "--workdir /workspaces/dutchbay-epc-model" in workflow
    assert "/usr/local/lib/dutchbay/sshd_readiness.py" in workflow
    assert "/run/dutchbay-sshd-runtime.ready" in workflow
    assert "ssh-keygen -q -t ed25519" in workflow
    assert "/home/vscode/.ssh/authorized_keys" in workflow
    assert "IdentitiesOnly=yes" in workflow
    assert "StrictHostKeyChecking=yes" in workflow
    assert 'UserKnownHostsFile="$probe_root/known_hosts"' in workflow
    assert "vscode@127.0.0.1" in workflow
    assert 'test "${DUTCHBAY_VENV:-}" = ' in workflow
    assert 'test "${DUTCHBAY_P03_SOURCE_ROOT:-}" = ' in workflow
    assert 'test "${PYTHONPATH:-}" = ' in workflow
    assert "bash .devcontainer/attest_audit_review_sshd.sh" in workflow
    assert workflow.count("\n          exercise_authenticated_transport\n") == 2
    assert workflow.count("bash .devcontainer/start_audit_review_sshd.sh --start") == 2
    assert "before_marker" in workflow
    assert "after_resume_marker" in workflow
    assert 'docker stop "$CONTAINER_ID"' in workflow
    assert 'docker start "$CONTAINER_ID"' not in workflow
    assert 'test "${resumed_ids[0]}" = "$CONTAINER_ID"' in workflow
    assert 'docker logs "$CONTAINER_ID"' in workflow
    assert "if: failure()" in workflow
    assert PATH_CLASSIFIER.stat().st_mode & 0o111


def test_candidate_codespace_control_is_exact_head_empty_and_disposable() -> None:
    """The pre-merge proof must remain separate from protected-main review."""
    candidate = CANDIDATE_CODESPACE.read_text(encoding="utf-8")

    assert '[[ "$CANDIDATE_BRANCH" =~ ^codex/' in candidate
    assert '[[ "$EXPECTED_SHA" =~ ^[0-9a-f]{40}$ ]]' in candidate
    assert 'git ls-remote --heads origin "refs/heads/$CANDIDATE_BRANCH"' in candidate
    assert "checkout_head=$(git rev-parse HEAD) || exit 2" in candidate
    assert 'test "$checkout_head" = "$expected_sha"' in candidate
    assert "checkout_status=$(git status --porcelain=v1) ||" in candidate
    assert 'source_probe=$(find "$source_root" -mindepth 1 -print -quit) ||' in (
        candidate
    )
    assert 'test -z "$(git status' not in candidate
    assert 'test -z "$(find ' not in candidate
    assert "gh codespace cp --expand" in candidate
    assert "gh codespace stop" in candidate
    assert '"$(codespace_identity | jq -r .state)" = "Shutdown"' in candidate
    assert 'before_marker=$(gh codespace ssh -c "$codespace_name"' in candidate
    assert 'after_marker=$(gh codespace ssh -c "$codespace_name"' in candidate
    assert candidate.count("verify_remote_candidate") == 3
    assert "bash .devcontainer/attest_audit_review_sshd.sh" in candidate
    assert "--retention-period 24h" in candidate
    assert 'gh codespace delete -c "$codespace_name" --force' in candidate
    assert 'readonly bootstrap_receipt="/workspaces/.dutchbay-private/' in candidate
    assert '"environment": "github_codespaces"' in candidate
    assert '"git_commit": sys.argv[2]' in candidate
    assert 'delete_candidate_and_confirm_absent "$CANDIDATE_BRANCH"' in candidate
    assert 'creation_pending="true"' in candidate
    assert "recover_unique_pending_candidate" in candidate
    assert 'display_name="DutchBay 1110 candidate $EXPECTED_SHA"' in candidate
    assert candidate.index(
        'delete_candidate_and_confirm_absent "$CANDIDATE_BRANCH"'
    ) < candidate.index("jq -n")
    assert candidate.index("trap - EXIT") < candidate.index("jq -n")
    assert 'deletion: "confirmed_absent_via_codespaces_api"' in candidate
    assert "candidate_codespace_name: $codespace_name" in candidate
    assert 'release_status: "HOLD"' in candidate
    assert "DUTCHBAY_P03_CLOUD_INGRESS_AUTHORIZED" not in candidate
    assert CANDIDATE_CODESPACE.stat().st_mode & 0o111


def test_candidate_codespace_control_rejects_non_allowlisted_identity() -> None:
    """Invalid candidate identity must fail before any GitHub mutation."""
    invalid_branch = subprocess.run(
        (str(CANDIDATE_CODESPACE), "main", "a" * 40),
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert invalid_branch.returncode == 2
    assert "allowlisted codex/* branch" in invalid_branch.stderr

    invalid_sha = subprocess.run(
        (str(CANDIDATE_CODESPACE), "codex/probe", "abc"),
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert invalid_sha.returncode == 2
    assert "full SHA-1" in invalid_sha.stderr


def test_candidate_recovers_ambiguous_creation_before_exit(tmp_path: Path) -> None:
    """Malformed create output must discover and delete only the exact candidate."""
    tool_root = tmp_path / "bin"
    state_path = tmp_path / "created"
    call_log = tmp_path / "calls.log"
    tool_root.mkdir()
    sha = "a" * 40
    branch = "codex/ambiguous-create-control"
    git_stub = tool_root / "git"
    git_stub.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
case "$1" in
  check-ref-format) exit 0 ;;
  status) exit 0 ;;
  ls-remote) printf '%s\\trefs/heads/%s\\n' "$STUB_SHA" "$STUB_BRANCH" ;;
  *) exit 91 ;;
esac
""",
        encoding="utf-8",
    )
    gh_stub = tool_root / "gh"
    gh_stub.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$*" >> "$STUB_CALL_LOG"
case "$1 $2" in
  "api --paginate")
    if [ -e "$STUB_STATE" ]; then
      printf '[{"codespaces":[{"name":"candidate123","display_name":"DutchBay 1110 candidate %s","repository":{"full_name":"arunakulat/dutchbay-epc-model"},"git_status":{"ref":"%s"}}]}]\\n' "$STUB_SHA" "$STUB_BRANCH"
    else
      printf '[{"codespaces":[]}]\\n'
    fi
    ;;
  "codespace create")
    : > "$STUB_STATE"
    printf 'malformed/name\\n'
    ;;
  "codespace delete")
    rm -- "$STUB_STATE"
    ;;
  *) exit 92 ;;
esac
""",
        encoding="utf-8",
    )
    git_stub.chmod(0o755)
    gh_stub.chmod(0o755)
    lock_path = Path("/tmp/dutchbay-1110-candidate-codespace.lock")
    assert not lock_path.exists()
    environment = {
        **os.environ,
        "PATH": f"{tool_root}:/usr/bin:/bin",
        "DUTCHBAY_VENV": "/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv",
        "STUB_SHA": sha,
        "STUB_BRANCH": branch,
        "STUB_STATE": str(state_path),
        "STUB_CALL_LOG": str(call_log),
    }
    result = subprocess.run(
        (str(CANDIDATE_CODESPACE), branch, sha),
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "created candidate Codespace name is malformed" in result.stderr
    assert "codespace delete -c candidate123 --force" in call_log.read_text(
        encoding="utf-8"
    )
    assert not state_path.exists()
    assert not lock_path.exists()


def test_shell_population_and_status_probes_fail_closed(tmp_path: Path) -> None:
    """A silent command error must not become an empty or clean result."""
    tool_root = tmp_path / "bin"
    tool_root.mkdir()
    for name in ("find", "git"):
        stub = tool_root / name
        stub.write_text("#!/usr/bin/env bash\nexit 61\n", encoding="utf-8")
        stub.chmod(0o755)
    environment = {**os.environ, "PATH": f"{tool_root}:/usr/bin:/bin"}
    for fragment in (
        "source_probe=$(find /tmp -mindepth 1 -print -quit) || exit 2; "
        'test -z "$source_probe"',
        "checkout_status=$(git status --porcelain=v1) || exit 2; "
        'test -z "$checkout_status"',
    ):
        result = subprocess.run(
            ("/bin/bash", "-euo", "pipefail", "-c", fragment),
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 2

    governed = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (BOOTSTRAP, VERIFY, CANDIDATE_CODESPACE, UPLOAD)
    )
    assert 'test -z "$(git status' not in governed
    assert 'test -z "$(find ' not in governed
    assert 'if find "$SOURCE_ROOT"' not in governed


def test_cloud_sandbox_path_classifier_fails_closed(tmp_path: Path) -> None:
    """Invalid, deleted and empty diffs must never bypass the heavy gate."""

    def git(*arguments: str) -> str:
        return subprocess.run(
            ("git", *arguments),
            cwd=tmp_path,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    def classify(base: str, head: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            (str(PATH_CLASSIFIER), base, head),
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=False,
        )

    git("init", "-q")
    git("config", "user.name", "DutchBay CI")
    git("config", "user.email", "ci@example.invalid")
    (tmp_path / "unrelated.txt").write_text("base\n", encoding="utf-8")
    git("add", "unrelated.txt")
    git("commit", "-qm", "base")
    base = git("rev-parse", "HEAD")

    (tmp_path / "unrelated.txt").write_text("head\n", encoding="utf-8")
    git("commit", "-qam", "unrelated")
    unrelated = git("rev-parse", "HEAD")
    result = classify(base, unrelated)
    assert result.returncode == 0
    assert result.stdout.strip() == "false"

    relevant_path = tmp_path / ".devcontainer" / "probe"
    relevant_path.parent.mkdir()
    relevant_path.write_text("probe\n", encoding="utf-8")
    git("add", ".devcontainer/probe")
    git("commit", "-qm", "relevant")
    relevant = git("rev-parse", "HEAD")
    result = classify(unrelated, relevant)
    assert result.returncode == 0
    assert result.stdout.strip() == "true"

    relevant_path.unlink()
    git("add", "-u")
    git("commit", "-qm", "delete relevant")
    deletion = git("rev-parse", "HEAD")
    result = classify(relevant, deletion)
    assert result.returncode == 0
    assert result.stdout.strip() == "true"

    dependency_base = deletion
    for index, relative in enumerate(INDEPENDENT_DEPENDENCY_INPUT_RELATIVES):
        dependency_path = tmp_path / relative
        dependency_path.parent.mkdir(parents=True, exist_ok=True)
        dependency_path.write_text(f"dependency-{index}\n", encoding="utf-8")
        git("add", relative)
        git("commit", "-qm", f"dependency {index}")
        dependency_head = git("rev-parse", "HEAD")
        result = classify(dependency_base, dependency_head)
        assert result.returncode == 0
        assert result.stdout.strip() == "true", relative
        dependency_base = dependency_head

    git("commit", "--allow-empty", "-qm", "empty")
    empty = git("rev-parse", "HEAD")
    result = classify(dependency_base, empty)
    assert result.returncode == 0
    assert result.stdout.strip() == "true"

    result = classify(base, "f" * 40)
    assert result.returncode == 2
    assert result.stdout == ""
    assert "head commit is unavailable" in result.stderr


def test_scripts_keep_private_inputs_outside_checkout_and_hold_side() -> None:
    """Setup and preflight must preserve the evidence and release boundaries."""
    bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
    identity = IDENTITY.read_text(encoding="utf-8")
    verify = VERIFY.read_text(encoding="utf-8")
    upload = UPLOAD.read_text(encoding="utf-8")
    create_codespace = CREATE_CODESPACE.read_text(encoding="utf-8")
    candidate_codespace = CANDIDATE_CODESPACE.read_text(encoding="utf-8")
    combined = (
        bootstrap + identity + verify + upload + create_codespace + candidate_codespace
    )

    assert PRIVATE_SOURCE_ROOT in combined
    assert SANDBOX_VENV in combined
    assert "CODESPACES" in combined
    assert '"$(id -un)" = "vscode"' in bootstrap
    assert "-d -m 0755 -o vscode -g vscode /workspaces" in bootstrap
    assert '"vscode:vscode:755"' in bootstrap
    assert bootstrap.index("-d -m 0755 -o vscode -g vscode /workspaces") < (
        bootstrap.index('install -d -m 0700 \\\n  "$PRIVATE_ROOT"')
    )
    assert ".devcontainer/devcontainer.json" in identity
    assert ".devcontainer/devcontainer-lock.json" in identity
    assert ".devcontainer/Dockerfile" in identity
    assert ".devcontainer/install_audit_review_sshd.sh" in identity
    assert ".devcontainer/start_audit_review_sshd.sh" in identity
    assert ".devcontainer/attest_audit_review_sshd.sh" in identity
    assert ".devcontainer/bootstrap_audit_review.sh" in identity
    assert 'realpath -e "$SOURCE_ROOT"' in combined
    assert "private P03 source root must not be a symlink" in combined
    assert "SSH transport did not become ready before the audit bootstrap" in (
        bootstrap
    )
    assert bootstrap.index(
        "/usr/local/sbin/dutchbay-sshd-start.sh --start"
    ) < bootstrap.index("/usr/local/lib/dutchbay/sshd_readiness.py")
    assert "/run/dutchbay-sshd-runtime.ready" in bootstrap
    assert "/usr/local/lib/dutchbay/sshd_readiness.py" in bootstrap
    assert "/usr/local/lib/dutchbay/sshd_readiness.py" in verify
    assert '"completion_authorized": False' in identity
    assert '"release_status": "HOLD"' in identity
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
    assert "checkout_status=$(git status --porcelain=v1) ||" in upload
    assert 'test -z "$(git status' not in upload
    assert "REMOTE_TRANSPORT_SMOKE" in upload
    assert upload.count("gh codespace cp --expand") == 2
    assert "remote:$REMOTE_SMOKE_PATH" in upload
    assert '"remote:$REMOTE_SOURCE_ROOT/"' in upload
    assert 'cmp -- "$repo_root/.devcontainer/devcontainer.json"' in upload
    assert "REMOTE_TRANSPORT_CLEANUP" in upload
    assert "trap cleanup_transport_probe EXIT" in upload
    assert 'return "$exit_status"' in upload
    assert "delete and recreate it before retrying" in upload
    assert "DUTCHBAY_P03_CLOUD_INGRESS_AUTHORIZED" in upload
    assert "DUTCHBAY_1110_REVIEW_CODESPACE_NAME" in upload
    assert "gh codespace list" not in upload
    assert upload.count('verify_codespace_identity "$codespace_name"') == 2
    assert '"/user/codespaces/$codespace_name"' in upload
    assert ".repository.full_name == $repository" in upload
    assert "gh codespace create" in create_codespace
    assert "create -s" not in create_codespace
    assert "-m standardLinux32gb" in create_codespace
    assert "gh api --paginate --slurp" in create_codespace
    assert 'readonly CREATE_LOCK="/tmp/dutchbay-1110-codespace-create.lock"' in (
        create_codespace
    )
    assert "trap release_create_lock EXIT" in create_codespace
    assert "post-create Codespace identity/collision check failed" in create_codespace
    assert "readonly MAX_TRANSPORT_TIMEOUT_SECONDS=300" in create_codespace
    assert "readonly POLL_SECONDS=5" in create_codespace
    assert "start_new_session=True" in create_codespace
    assert "os.killpg" in create_codespace
    assert "deadline = time.monotonic() + timeout - cleanup_budget" in (
        create_codespace
    )
    assert "process.wait(timeout=min(10.0, remaining))" in create_codespace
    assert "sshd_readiness.py 5" in create_codespace
    assert '["gh", "codespace", "ssh"' in create_codespace
    document = DOC.read_text(encoding="utf-8")
    assignment = 'DUTCHBAY_1110_REVIEW_CODESPACE_NAME="$('
    assert assignment in document
    assert f"export {assignment}" not in document
    assert "export DUTCHBAY_1110_REVIEW_CODESPACE_NAME" in document
    assert 'CONTAINER_PYTHON="/usr/local/bin/python3.12"' in bootstrap
    assert 'CONTAINER_PYTHON="/usr/local/bin/python3.12"' in verify
    assert '"$CONTAINER_PYTHON" -S' in bootstrap
    assert '"$CONTAINER_PYTHON" -S' in verify
    assert 'PYTHONPATH="$PWD/.devcontainer" python3.12' not in combined
    assert "PYTHONDONTWRITEBYTECODE=1" in bootstrap
    assert "PYTHONDONTWRITEBYTECODE=1" in verify
    assert '"installed_environment_content_sha256"' in identity
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
        "devcontainer_base_image_digest",
        "repository_configured_devcontainer_features",
        "base_image_embedded_feature_metadata",
        "ssh_transport_packages",
        "sshd_effective_config_sha256",
        "sshd_transport_content_sha256",
        "sshd_host_public_key_fingerprints",
        "sshd_identity_sha256",
        "dependency_input_sha256",
        "installed_distribution_set_sha256",
        "installed_environment_content_sha256",
        "controlled_input_sha256",
        "network_boundary",
    ):
        assert receipt_field in identity
    assert "actions/upload-artifact" not in combined
    assert "forwardPorts" not in combined
    assert BOOTSTRAP.stat().st_mode & 0o111
    assert SSHD_START.stat().st_mode & 0o111
    assert SSHD_ATTESTOR.stat().st_mode & 0o111
    assert VERIFY.stat().st_mode & 0o111
    assert UPLOAD.stat().st_mode & 0o111
    assert CREATE_CODESPACE.stat().st_mode & 0o111


def test_sshd_readiness_waits_for_banner_and_rejects_process_only(
    tmp_path: Path,
) -> None:
    """Readiness must wait for the OpenSSH listener and time out without one."""
    readiness = _load_sshd_readiness()
    assert readiness.EXPECTED_BANNER_PREFIX == b"SSH-2.0-OpenSSH_"
    assert readiness.MAX_IDENTIFICATION_LINE_BYTES == 255
    marker = tmp_path / "ready"
    marker.write_text(f"{readiness.EXPECTED_MARKER}\n", encoding="ascii")

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]

    def delayed_banner() -> None:
        time.sleep(0.15)
        connection, _ = listener.accept()
        with connection:
            connection.sendall(b"SSH-2.0-Open")
            time.sleep(0.05)
            connection.sendall(b"SSH_9.2p1 test\r\n")
        listener.close()

    server = threading.Thread(target=delayed_banner)
    server.start()
    started = time.monotonic()
    readiness.wait_for_sshd(
        host="127.0.0.1",
        port=port,
        timeout_seconds=1.0,
        marker_path=marker,
    )
    assert time.monotonic() - started >= 0.1
    server.join(timeout=1.0)
    assert not server.is_alive()

    def rejected_peer(payload: bytes) -> None:
        rejected_listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        rejected_listener.bind(("127.0.0.1", 0))
        rejected_listener.listen(1)
        rejected_port = rejected_listener.getsockname()[1]

        def send_rejected() -> None:
            connection, _ = rejected_listener.accept()
            with connection:
                connection.sendall(payload)
            rejected_listener.close()

        peer = threading.Thread(target=send_rejected)
        peer.start()
        try:
            readiness.wait_for_sshd(
                host="127.0.0.1",
                port=rejected_port,
                timeout_seconds=0.2,
                marker_path=marker,
            )
        except readiness.SshdReadinessError as exc:
            assert "not ready" in str(exc)
        else:  # pragma: no cover - explicit fail branch
            raise AssertionError("invalid SSH identification peer was accepted")
        peer.join(timeout=1.0)
        assert not peer.is_alive()

    rejected_peer(b"SSH-2.0-OpenSSH_")
    rejected_peer(b"SSH-2.0-OpenSSH_" + b"x" * 300)

    process_only = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    process_only.bind(("127.0.0.1", 0))
    unavailable_port = process_only.getsockname()[1]
    try:
        readiness.wait_for_sshd(
            host="127.0.0.1",
            port=unavailable_port,
            timeout_seconds=0.15,
            marker_path=marker,
        )
    except readiness.SshdReadinessError as exc:
        assert "not ready" in str(exc)
    else:  # pragma: no cover - explicit fail branch
        raise AssertionError("process without an OpenSSH listener was accepted")
    finally:
        process_only.close()


def test_codespace_creation_watchdog_bounds_a_hung_ssh_probe(
    tmp_path: Path,
) -> None:
    """The create wrapper must kill a hung transport probe at one deadline."""
    fake_gh = tmp_path / "gh"
    child_pid_file = tmp_path / "child.pid"
    fake_gh.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
case "${1:-}:${2:-}" in
  api:*) printf '%s\\n' '[{"codespaces":[]}]' ;;
  codespace:create) printf '%s\\n' 'mock-codespace' ;;
  codespace:ssh)
    trap 'exit 0' TERM
    python3 -c 'import os, signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); open(os.environ["DUTCHBAY_TEST_CHILD_PID_FILE"], "w", encoding="ascii").write(str(os.getpid())); time.sleep(10)' &
    wait
    ;;
  *) exit 2 ;;
esac
""",
        encoding="utf-8",
    )
    fake_gh.chmod(0o755)
    started = time.monotonic()
    result = subprocess.run(
        (str(CREATE_CODESPACE),),
        cwd=REPO_ROOT,
        env={
            **os.environ,
            "PATH": f"{tmp_path}:{os.environ['PATH']}",
            "DUTCHBAY_VENV": str(Path(sys.executable).parents[1]),
            "DUTCHBAY_CODESPACE_TRANSPORT_TIMEOUT_SECONDS": "1",
            "DUTCHBAY_TEST_CHILD_PID_FILE": str(child_pid_file),
        },
        capture_output=True,
        text=True,
        timeout=5,
    )
    elapsed = time.monotonic() - started
    assert result.returncode == 2
    assert 0.5 <= elapsed < 4.0
    assert "inspect or delete: mock-codespace" in result.stderr
    child_pid = int(child_pid_file.read_text(encoding="ascii"))
    child_alive = True
    for _ in range(20):
        try:
            os.kill(child_pid, 0)
        except ProcessLookupError:
            child_alive = False
            break
        time.sleep(0.05)
    if child_alive:  # pragma: no cover - cleanup before explicit failure
        os.kill(child_pid, signal.SIGKILL)
    assert not child_alive


def test_identity_contract_binds_ingress_and_rejects_stale_markers(
    tmp_path: Path,
) -> None:
    """Receipts must bind the transfer control and reject changed inputs."""
    identity = _load_identity_contract()
    dependency_digest = identity.dependency_input_sha256(REPO_ROOT)
    image_digest = identity.configured_base_image_digest(REPO_ROOT)
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
    assert receipt["devcontainer_base_image_digest"] == image_digest
    assert receipt["repository_configured_devcontainer_features"] == [
        "ghcr.io/devcontainers/features/sshd@"
        "sha256:f5251b8e4325f68f7280973c6cd65daff414449c66f240621502d4e8e74eb7ee"
    ]
    assert receipt["base_image_embedded_feature_metadata"] == [
        "ghcr.io/devcontainers/features/common-utils:2",
        "ghcr.io/devcontainers/features/git:1",
        "ghcr.io/devcontainers/features/node:1",
        "ghcr.io/devcontainers/features/python:1",
    ]
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


def test_sshd_policy_content_and_host_identity_fail_closed(tmp_path: Path) -> None:
    """The attestor must reject policy drift and bind every transport byte."""
    identity = _load_identity_contract()
    assert identity.EXPECTED_SSHD_EFFECTIVE_VALUES == REQUIRED_SSHD_EFFECTIVE_POLICY
    assert identity.EXPECTED_SSHD_SETENV_VALUES == REQUIRED_SSHD_SETENV_POLICY
    effective = "\n".join(
        [
            *(
                f"{key} {value}"
                for key, value in REQUIRED_SSHD_EFFECTIVE_POLICY.items()
            ),
            f"setenv {' '.join(sorted(REQUIRED_SSHD_SETENV_POLICY))}",
        ]
    )
    package_inventory = "\n".join(
        (
            "lsof|amd64|install ok installed|4.95.0",
            "openssh-client|amd64|install ok installed|1:9.2p1",
            "openssh-server|amd64|install ok installed|1:9.2p1",
            "openssh-sftp-server|amd64|install ok installed|1:9.2p1",
        )
    )
    executable = tmp_path / "sshd"
    pam = tmp_path / "pam-sshd"
    executable.write_bytes(b"binary-v1")
    pam.write_text("session optional pam_loginuid.so\n", encoding="utf-8")
    arguments = {
        "effective_config": effective,
        "package_inventory": package_inventory,
        "package_paths": [executable],
        "extra_paths": [pam],
        "host_public_key_material": list(VALID_SSH_HOST_PUBLIC_KEYS),
        "host_public_key_sidecars": list(VALID_SSH_HOST_PUBLIC_KEYS),
    }

    first = identity.build_sshd_transport_identity(**arguments)
    assert first["sshd_effective_config_sha256"]
    assert first["sshd_transport_content_sha256"]
    assert first["sshd_host_public_key_fingerprints"] == (VALID_SSH_HOST_FINGERPRINTS)

    equivalent_sidecars = list(arguments["host_public_key_sidecars"])
    equivalent_sidecars[0] = equivalent_sidecars[0].rstrip("=")
    equivalent = identity.build_sshd_transport_identity(
        **{**arguments, "host_public_key_sidecars": equivalent_sidecars}
    )
    assert equivalent == first

    commented_material = list(arguments["host_public_key_material"])
    commented_material[1] = f"{commented_material[1]} runtime-generated-host-key"
    commented = identity.build_sshd_transport_identity(
        **{**arguments, "host_public_key_material": commented_material}
    )
    assert commented == first

    try:
        identity._validated_ssh_public_key_blob(
            f"{VALID_SSH_HOST_PUBLIC_KEYS[1]}\n{VALID_SSH_HOST_PUBLIC_KEYS[2]}"
        )
    except identity.SandboxIdentityError as exc:
        assert "public-key identity" in str(exc)
    else:  # pragma: no cover - explicit fail branch
        raise AssertionError("multiline SSH public-key material was accepted")

    wrong_environment = effective.replace(
        "DUTCHBAY_VENV=/workspaces/.dutchbay-audit-review-venv",
        "DUTCHBAY_VENV=/tmp/untrusted",
    )
    try:
        identity.build_sshd_transport_identity(
            **{**arguments, "effective_config": wrong_environment}
        )
    except identity.SandboxIdentityError as exc:
        assert "session environment" in str(exc)
    else:  # pragma: no cover - explicit fail branch
        raise AssertionError("redirected SSH session environment was accepted")

    unsafe_effective_values = {
        "authorizedkeyscommand none": "authorizedkeyscommand /tmp/accept-any-key",
        "authorizedkeyscommanduser none": "authorizedkeyscommanduser root",
        "authorizedkeysfile .ssh/authorized_keys": "authorizedkeysfile /tmp/keys",
        "authorizedprincipalscommand none": (
            "authorizedprincipalscommand /tmp/accept-principal"
        ),
        "authorizedprincipalscommanduser none": (
            "authorizedprincipalscommanduser root"
        ),
        "authorizedprincipalsfile none": "authorizedprincipalsfile /tmp/principals",
        "chrootdirectory none": "chrootdirectory /tmp/untrusted",
        "forcecommand none": "forcecommand /tmp/untrusted-command",
        "permituserenvironment no": "permituserenvironment yes",
        "strictmodes yes": "strictmodes no",
        "trustedusercakeys none": "trustedusercakeys /tmp/untrusted-ca.pub",
    }
    for safe_value, unsafe_value in unsafe_effective_values.items():
        try:
            identity.validate_sshd_effective_config(
                effective.replace(safe_value, unsafe_value)
            )
        except identity.SandboxIdentityError as exc:
            assert "effective SSH policy" in str(exc)
        else:  # pragma: no cover - explicit fail branch
            raise AssertionError(f"unsafe SSH policy was accepted: {unsafe_value}")

    resolved_match_override = effective.replace(
        "passwordauthentication no", "passwordauthentication yes"
    )
    try:
        identity.validate_sshd_effective_config(resolved_match_override)
    except identity.SandboxIdentityError as exc:
        assert "effective SSH policy" in str(exc)
    else:  # pragma: no cover - explicit fail branch
        raise AssertionError("resolved Match User override was accepted")

    executable.write_bytes(b"binary-v2")
    second = identity.build_sshd_transport_identity(**arguments)
    assert (
        second["sshd_transport_content_sha256"]
        != first["sshd_transport_content_sha256"]
    )
    assert second["sshd_identity_sha256"] != first["sshd_identity_sha256"]

    mismatched_sidecars = list(arguments["host_public_key_sidecars"])
    mismatched_sidecars[1] = VALID_SSH_HOST_PUBLIC_KEYS[0]
    try:
        identity.build_sshd_transport_identity(
            **{**arguments, "host_public_key_sidecars": mismatched_sidecars}
        )
    except identity.SandboxIdentityError as exc:
        assert "private/public" in str(exc)
    else:  # pragma: no cover - explicit fail branch
        raise AssertionError("mismatched SSH private/public key pair was accepted")

    transposed_sidecars = list(arguments["host_public_key_sidecars"])
    transposed_sidecars[0], transposed_sidecars[1] = (
        transposed_sidecars[1],
        transposed_sidecars[0],
    )
    try:
        identity.build_sshd_transport_identity(
            **{**arguments, "host_public_key_sidecars": transposed_sidecars}
        )
    except identity.SandboxIdentityError as exc:
        assert "private/public" in str(exc)
    else:  # pragma: no cover - explicit fail branch
        raise AssertionError("transposed SSH public-key sidecars were accepted")

    malformed_keys = list(arguments["host_public_key_material"])
    malformed_keys[0] = "ecdsa-sha2-nistp256 not-base64!"
    try:
        identity.build_sshd_transport_identity(
            **{
                **arguments,
                "host_public_key_material": malformed_keys,
                "host_public_key_sidecars": malformed_keys,
            }
        )
    except identity.SandboxIdentityError as exc:
        assert "public-key identity" in str(exc)
    else:  # pragma: no cover - explicit fail branch
        raise AssertionError("malformed SSH public-key material was accepted")

    malformed_wire_keys = list(arguments["host_public_key_material"])
    malformed_wire_keys[0] = "ecdsa-sha2-nistp256 QUJD"
    try:
        identity.build_sshd_transport_identity(
            **{
                **arguments,
                "host_public_key_material": malformed_wire_keys,
                "host_public_key_sidecars": malformed_wire_keys,
            }
        )
    except identity.SandboxIdentityError as exc:
        assert "wire data" in str(exc)
    else:  # pragma: no cover - explicit fail branch
        raise AssertionError("malformed SSH public-key wire data was accepted")

    mismatched_algorithm_keys = list(arguments["host_public_key_material"])
    _, ed25519_blob = VALID_SSH_HOST_PUBLIC_KEYS[1].split()
    mismatched_algorithm_keys[0] = f"ecdsa-sha2-nistp256 {ed25519_blob}"
    try:
        identity.build_sshd_transport_identity(
            **{
                **arguments,
                "host_public_key_material": mismatched_algorithm_keys,
                "host_public_key_sidecars": mismatched_algorithm_keys,
            }
        )
    except identity.SandboxIdentityError as exc:
        assert "text/wire algorithms" in str(exc)
    else:  # pragma: no cover - explicit fail branch
        raise AssertionError("SSH text/wire algorithm mismatch was accepted")

    invalid_ecdsa_point = _ssh_public_key_line(
        "ecdsa-sha2-nistp256",
        b"nistp256",
        b"\x04" + b"\x00" * 64,
    )
    negative_rsa_modulus = _ssh_public_key_line(
        "ssh-rsa",
        b"\x01\x00\x01",
        b"\x80" + b"\x01" * 127,
    )
    subminimum_rsa_modulus = _ssh_public_key_line(
        "ssh-rsa",
        b"\x01\x00\x01",
        b"\x7f" + b"\xff" * 126,
    )
    for name, invalid_key in (
        ("invalid-ecdsa", invalid_ecdsa_point),
        ("negative-rsa", negative_rsa_modulus),
        ("subminimum-rsa", subminimum_rsa_modulus),
    ):
        public_key_path = tmp_path / f"{name}.pub"
        public_key_path.write_text(f"{invalid_key}\n", encoding="ascii")
        independent = subprocess.run(
            ("ssh-keygen", "-E", "sha256", "-lf", str(public_key_path)),
            check=False,
            capture_output=True,
            text=True,
        )
        assert independent.returncode != 0
        try:
            identity._validated_ssh_public_key_blob(invalid_key)
        except identity.SandboxIdentityError as exc:
            assert "SSH" in str(exc)
        else:  # pragma: no cover - explicit fail branch
            raise AssertionError(f"{name} public key was accepted")

    for key, expected in REQUIRED_SSHD_EFFECTIVE_POLICY.items():
        replacement = "22" if key == "port" else ("yes" if expected == "no" else "no")
        changed = effective.replace(f"{key} {expected}", f"{key} {replacement}")
        try:
            identity.build_sshd_transport_identity(
                **{**arguments, "effective_config": changed}
            )
        except identity.SandboxIdentityError as exc:
            assert key in str(exc)
        else:  # pragma: no cover - explicit fail branch
            raise AssertionError(f"unsafe effective SSH value was accepted: {key}")


def test_authenticated_ssh_connection_context_is_exact_and_fail_closed() -> None:
    """Session attestation must use the real, approved tunnel connection tuple."""
    identity = _load_identity_contract()
    assert identity.build_sshd_session_connection_context(
        "127.0.0.1 49152 127.0.0.1 2222",
        "127.0.0.1 49152 2222",
    ) == ("user=vscode,host=localhost,addr=127.0.0.1,laddr=127.0.0.1,lport=2222")
    assert (
        identity.build_sshd_session_connection_context(
            "::1 49153 ::1 2222",
            "::1 49153 2222",
        )
        == "user=vscode,host=localhost,addr=::1,laddr=::1,lport=2222"
    )

    rejected = (
        ("", ""),
        ("127.0.0.1 1 127.0.0.1", "127.0.0.1 1 2222"),
        ("127.0.0.1 49152 127.0.0.1 2222", "127.0.0.1 49153 2222"),
        ("10.0.0.1 49152 127.0.0.1 2222", "10.0.0.1 49152 2222"),
        ("127.0.0.1 49152 10.0.0.2 2222", "127.0.0.1 49152 2222"),
        ("127.0.0.1 49152 127.0.0.1 22", "127.0.0.1 49152 22"),
    )
    for connection, client in rejected:
        try:
            identity.build_sshd_session_connection_context(connection, client)
        except identity.SandboxIdentityError:
            pass
        else:  # pragma: no cover - explicit fail branch
            raise AssertionError(f"unsafe SSH tuple was accepted: {connection!r}")


def test_base_image_policy_cannot_drift_from_reported_digest(tmp_path: Path) -> None:
    """One FROM reference must select both its digest and metadata policy."""
    identity = _load_identity_contract()
    devcontainer_dir = tmp_path / ".devcontainer"
    devcontainer_dir.mkdir()
    config = {
        "build": {"dockerfile": "Dockerfile", "context": ".."},
        "features": {identity.EXPECTED_REPOSITORY_FEATURE: {}},
        "overrideCommand": False,
        "init": True,
        "containerUser": "root",
        "remoteUser": "vscode",
        "postStartCommand": "bash .devcontainer/start_audit_review_sshd.sh --start",
    }
    config_path = devcontainer_dir / "devcontainer.json"
    lock_path = devcontainer_dir / "devcontainer-lock.json"
    dockerfile_path = devcontainer_dir / "Dockerfile"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    lock_path.write_text(
        json.dumps(
            {
                "features": {
                    identity.EXPECTED_REPOSITORY_FEATURE: {
                        "version": "1.1.0",
                        "resolved": identity.EXPECTED_REPOSITORY_FEATURE_RESOLVED,
                        "integrity": identity.EXPECTED_REPOSITORY_FEATURE_DIGEST,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    dockerfile_path.write_text(
        f"FROM {identity.EXPECTED_BASE_IMAGE}\n", encoding="utf-8"
    )
    try:
        identity.configured_base_image_digest(tmp_path)
    except identity.SandboxIdentityError as exc:
        assert "keepalive" in str(exc)
    else:  # pragma: no cover - explicit fail branch
        raise AssertionError("disabled devcontainer keepalive was accepted")

    config["overrideCommand"] = True
    config_path.write_text(json.dumps(config), encoding="utf-8")
    replacement = "mcr.microsoft.com/devcontainers/python:test@" + f"sha256:{'b' * 64}"
    dockerfile_path.write_text(f"FROM {replacement}\n", encoding="utf-8")
    original = identity.EXPECTED_BASE_IMAGE
    identity.EXPECTED_BASE_IMAGE = replacement
    try:
        identity.configured_base_image_digest(tmp_path)
    except identity.SandboxIdentityError as exc:
        assert "metadata policy" in str(exc)
    else:  # pragma: no cover - explicit fail branch
        raise AssertionError("unreviewed base-image metadata was accepted")
    finally:
        identity.EXPECTED_BASE_IMAGE = original


def test_v3_receipt_builders_enforce_exact_independent_schemas() -> None:
    """Bootstrap and verification receipts must each preserve their v3 contract."""
    identity = _load_identity_contract()
    assert identity.DEPENDENCY_INPUT_RELATIVES == (
        INDEPENDENT_DEPENDENCY_INPUT_RELATIVES
    )
    assert identity.CONTROLLED_INPUT_RELATIVES == (
        INDEPENDENT_CONTROLLED_INPUT_RELATIVES
    )
    assert identity.BOOTSTRAP_SOURCE_STATES == INDEPENDENT_BOOTSTRAP_SOURCE_STATES
    assert identity.VERIFICATION_SOURCE_STATES == INDEPENDENT_VERIFICATION_SOURCE_STATES
    sandbox_identity = _sample_sandbox_identity(INDEPENDENT_CONTROLLED_INPUT_RELATIVES)
    sshd_identity = _sample_sshd_identity()

    bootstrap = identity.build_bootstrap_receipt(
        identity=sandbox_identity,
        sshd_identity=sshd_identity,
        source_state="private_root_empty",
        execution_host="github_codespaces",
    )
    verification = identity.build_verification_receipt(
        identity=sandbox_identity,
        sshd_identity=sshd_identity,
        source_state="private_root_empty_p03_not_executed",
        execution_host="github_codespaces",
    )
    common_keys = (
        set(sandbox_identity)
        | set(sshd_identity)
        | {
            "schema",
            "status",
            "environment",
            "p03_source_state",
            "network_boundary",
            "completion_authorized",
            "release_status",
        }
    )
    assert set(bootstrap) == common_keys | {"python"}
    assert bootstrap["schema"] == "dutchbay.audit_review_sandbox_bootstrap.v3"
    assert bootstrap["status"] == "PASS"
    assert bootstrap["environment"] == "github_codespaces"
    assert bootstrap["network_boundary"] == (
        "creator_private_codespace_outbound_egress_available"
    )
    assert bootstrap["completion_authorized"] is False
    assert bootstrap["release_status"] == "HOLD"
    assert set(verification) == common_keys | {
        "sshd_process",
        "p02_structural_controls",
        "semantic_review_completed",
    }
    assert verification["schema"] == "dutchbay.audit_review_sandbox_receipt.v3"
    assert verification["status"] == "PASS"
    assert verification["environment"] == "github_codespaces"
    assert verification["network_boundary"] == (
        "creator_private_codespace_outbound_egress_available"
    )
    assert verification["sshd_process"] == "running"
    assert verification["p02_structural_controls"] == "passed"
    assert verification["semantic_review_completed"] is False
    assert verification["completion_authorized"] is False
    assert verification["release_status"] == "HOLD"

    hosted_bootstrap = identity.build_bootstrap_receipt(
        identity=sandbox_identity,
        sshd_identity=sshd_identity,
        source_state="private_root_empty",
        execution_host="github_actions_devcontainer_emulation",
    )
    assert hosted_bootstrap["environment"] == ("github_actions_devcontainer_emulation")
    assert hosted_bootstrap["network_boundary"] == (
        "github_actions_hosted_runner_outbound_egress_available"
    )

    missing = dict(sshd_identity)
    missing.pop("sshd_transport_content_sha256")
    extra = {**sshd_identity, "unexpected": "value"}
    for invalid in (missing, extra):
        try:
            identity.build_verification_receipt(
                identity=sandbox_identity,
                sshd_identity=invalid,
                source_state="private_root_empty_p03_not_executed",
                execution_host="github_codespaces",
            )
        except identity.SandboxIdentityError as exc:
            assert "receipt fields" in str(exc)
        else:  # pragma: no cover - explicit fail branch
            raise AssertionError("invalid verification receipt identity was accepted")

    missing_controlled = dict(sandbox_identity)
    missing_controlled["controlled_input_sha256"] = dict(
        sandbox_identity["controlled_input_sha256"]
    )
    missing_controlled["controlled_input_sha256"].pop(
        INDEPENDENT_CONTROLLED_INPUT_RELATIVES[0]
    )
    extra_controlled = dict(sandbox_identity)
    extra_controlled["controlled_input_sha256"] = {
        **sandbox_identity["controlled_input_sha256"],
        "unexpected": "7" * 64,
    }
    for invalid_identity in (missing_controlled, extra_controlled):
        try:
            identity.build_bootstrap_receipt(
                identity=invalid_identity,
                sshd_identity=sshd_identity,
                source_state="private_root_empty",
                execution_host="github_codespaces",
            )
        except identity.SandboxIdentityError as exc:
            assert "controlled-input" in str(exc)
        else:  # pragma: no cover - explicit fail branch
            raise AssertionError("invalid controlled-input population was accepted")

    bad_status = dict(sshd_identity)
    bad_status["ssh_transport_packages"] = list(sshd_identity["ssh_transport_packages"])
    bad_status["ssh_transport_packages"][0] = "lsof|amd64|BROKEN|4.95.0"
    bad_status = _with_sshd_self_digest(bad_status)
    duplicate_fingerprints = dict(sshd_identity)
    duplicate_fingerprints["sshd_host_public_key_fingerprints"] = [
        f"SHA256:{'A' * 43}"
    ] * 3
    duplicate_fingerprints = _with_sshd_self_digest(duplicate_fingerprints)
    for invalid_sshd, expected_error in (
        (bad_status, "SSH transport package inventory"),
        (duplicate_fingerprints, "SSH identity populations"),
    ):
        try:
            identity.build_verification_receipt(
                identity=sandbox_identity,
                sshd_identity=invalid_sshd,
                source_state="private_root_empty_p03_not_executed",
                execution_host="github_codespaces",
            )
        except identity.SandboxIdentityError as exc:
            assert expected_error in str(exc)
        else:  # pragma: no cover - explicit fail branch
            raise AssertionError("invalid nested SSH identity was accepted")

    stale_self_digest = dict(sshd_identity)
    stale_self_digest["sshd_identity_sha256"] = "f" * 64
    try:
        identity.build_verification_receipt(
            identity=sandbox_identity,
            sshd_identity=stale_self_digest,
            source_state="private_root_empty_p03_not_executed",
            execution_host="github_codespaces",
        )
    except identity.SandboxIdentityError as exc:
        assert "self-digest" in str(exc)
    else:  # pragma: no cover - explicit fail branch
        raise AssertionError("stale SSH identity self-digest was accepted")

    for invalid_state in (None, "semantic_review_complete"):
        try:
            identity.build_bootstrap_receipt(
                identity=sandbox_identity,
                sshd_identity=sshd_identity,
                source_state=invalid_state,
                execution_host="github_codespaces",
            )
        except identity.SandboxIdentityError as exc:
            assert "source state" in str(exc)
        else:  # pragma: no cover - explicit fail branch
            raise AssertionError("invalid bootstrap source state was accepted")
        try:
            identity.build_verification_receipt(
                identity=sandbox_identity,
                sshd_identity=sshd_identity,
                source_state=invalid_state,
                execution_host="github_codespaces",
            )
        except identity.SandboxIdentityError as exc:
            assert "source state" in str(exc)
        else:  # pragma: no cover - explicit fail branch
            raise AssertionError("invalid verification source state was accepted")

    for invalid_host in (None, "", "ambiguous_host"):
        try:
            identity.build_bootstrap_receipt(
                identity=sandbox_identity,
                sshd_identity=sshd_identity,
                source_state="private_root_empty",
                execution_host=invalid_host,
            )
        except identity.SandboxIdentityError as exc:
            assert "execution-host provenance" in str(exc)
        else:  # pragma: no cover - explicit fail branch
            raise AssertionError("invalid bootstrap execution host was accepted")


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


def test_identity_rejects_unlocked_or_extra_repository_features(
    tmp_path: Path,
) -> None:
    """Only the exact digest-locked SSH integration Feature is permitted."""
    identity = _load_identity_contract()
    config = json.loads(DEVCONTAINER.read_text(encoding="utf-8"))
    devcontainer_dir = tmp_path / ".devcontainer"
    devcontainer_dir.mkdir()
    config_path = devcontainer_dir / "devcontainer.json"
    lock_path = devcontainer_dir / "devcontainer-lock.json"

    original_lock = DEVCONTAINER_LOCK.read_text(encoding="utf-8")
    added_feature = json.loads(json.dumps(config))
    added_feature["features"]["ghcr.io/example/extra:1"] = {}
    wrong_lock = json.loads(original_lock)
    wrong_feature = wrong_lock["features"][identity.EXPECTED_REPOSITORY_FEATURE]
    wrong_feature["integrity"] = f"sha256:{'0' * 64}"
    invalid_cases = (
        (added_feature, original_lock),
        (config, None),
        (config, json.dumps(wrong_lock)),
    )
    for candidate_config, lock_content in invalid_cases:
        config_path.write_text(json.dumps(candidate_config), encoding="utf-8")
        if lock_path.exists():
            lock_path.unlink()
        if lock_content is not None:
            lock_path.write_text(lock_content, encoding="utf-8")
        try:
            identity.configured_base_image_digest(tmp_path)
        except identity.SandboxIdentityError as exc:
            assert "feature" in str(exc).lower()
        else:  # pragma: no cover - explicit fail branch
            raise AssertionError("unlocked or extra devcontainer Feature was accepted")


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
        "declares one repository-configured Dev Container Feature",
        "locked to its exact OCI digest",
        "The base image itself carries separate embedded Dev Container Feature metadata",
        "Debian-only package source",
        "Host private keys are removed in the same image-build layer",
        "allowlist-validated effective SSH policy",
        "host public-key fingerprints",
        "installed environment-content fingerprint",
        "three Python launchers must resolve to `/usr/local/bin/python3.12`",
        "content-bound reuse control, not a hash-complete external package lock",
    ):
        assert required in normalized
