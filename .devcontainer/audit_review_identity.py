"""Deterministic identity contract for the disposable #1110 review sandbox."""

from __future__ import annotations

import base64
import binascii
import hashlib
import importlib.metadata
import ipaddress
import json
import os
import re
import subprocess
from pathlib import Path

EXPECTED_BASE_IMAGE = (
    "mcr.microsoft.com/devcontainers/python:1-3.12-bookworm@"
    "sha256:7876580dc67fd460fd962f004cbeb480027e9bbc0657096f1087db11f9eaff39"
)
EXPECTED_REPOSITORY_FEATURE = "ghcr.io/devcontainers/features/sshd:1.1.0"
EXPECTED_REPOSITORY_FEATURE_RESOLVED = (
    "ghcr.io/devcontainers/features/sshd@"
    "sha256:f5251b8e4325f68f7280973c6cd65daff414449c66f240621502d4e8e74eb7ee"
)
EXPECTED_REPOSITORY_FEATURE_DIGEST = (
    "sha256:f5251b8e4325f68f7280973c6cd65daff414449c66f240621502d4e8e74eb7ee"
)
BASE_IMAGE_EMBEDDED_FEATURE_METADATA_BY_DIGEST = {
    "sha256:7876580dc67fd460fd962f004cbeb480027e9bbc0657096f1087db11f9eaff39": (
        "ghcr.io/devcontainers/features/common-utils:2",
        "ghcr.io/devcontainers/features/git:1",
        "ghcr.io/devcontainers/features/node:1",
        "ghcr.io/devcontainers/features/python:1",
    )
}
EXPECTED_SSHD_EFFECTIVE_VALUES = {
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
EXPECTED_SSHD_SETENV_VALUES = {
    "DUTCHBAY_P03_SOURCE_ROOT=/workspaces/.dutchbay-private/p03/sources",
    "DUTCHBAY_VENV=/workspaces/.dutchbay-audit-review-venv",
    (
        "PATH=/workspaces/.dutchbay-audit-review-venv/bin:/usr/local/bin:"
        "/usr/local/sbin:/usr/bin:/usr/sbin:/bin:/sbin"
    ),
    "PYTHONPATH=/workspaces/dutchbay-epc-model",
}
EXPECTED_SSH_TRANSPORT_PACKAGES = {
    "lsof",
    "openssh-client",
    "openssh-server",
    "openssh-sftp-server",
}
EXPECTED_SSH_HOST_KEY_ALGORITHMS = {
    "ecdsa-sha2-nistp256",
    "ssh-ed25519",
    "ssh-rsa",
}
BOOTSTRAP_RECEIPT_SCHEMA = "dutchbay.audit_review_sandbox_bootstrap.v3"
VERIFICATION_RECEIPT_SCHEMA = "dutchbay.audit_review_sandbox_receipt.v3"
BOOTSTRAP_SOURCE_STATES = {
    "private_root_empty",
    "private_root_populated",
}
VERIFICATION_SOURCE_STATES = {
    "private_root_empty_p03_not_executed",
    "private_root_populated_p03_structural_verification_passed",
}
EXECUTION_HOST_NETWORK_BOUNDARIES = {
    "github_codespaces": "creator_private_codespace_outbound_egress_available",
    "github_actions_devcontainer_emulation": (
        "github_actions_hosted_runner_outbound_egress_available"
    ),
}
HEX_64 = re.compile(r"[0-9a-f]{64}\Z")
SSH_FINGERPRINT = re.compile(r"SHA256:[A-Za-z0-9+/]{43}\Z")
CODESPACE_NAME = re.compile(r"[A-Za-z0-9_-]+\Z")
P256_PRIME = 0xFFFFFFFF00000001000000000000000000000000FFFFFFFFFFFFFFFFFFFFFFFF
P256_B = 0x5AC635D8AA3A93E7B3EBBD55769886BC651D06B0CC53B0F63BCE3C3E27D2604B

DEPENDENCY_INPUT_RELATIVES = (
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
    "scripts/run_1110_cloud_review_verification.sh",
    "scripts/prove_1110_candidate_codespace.sh",
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
    "scripts/create_1110_cloud_review_codespace.sh",
    "scripts/run_1110_cloud_review_verification.sh",
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


def configured_base_image_digest(repo_root: Path) -> str:
    """Return and validate the repository-owned devcontainer build identity."""
    payload = json.loads(
        (repo_root / ".devcontainer" / "devcontainer.json").read_text(encoding="utf-8")
    )
    expected_build = {"dockerfile": "Dockerfile", "context": ".."}
    if payload.get("build") != expected_build or "image" in payload:
        raise SandboxIdentityError("devcontainer build differs from policy")
    if payload.get("overrideCommand") is not True:
        raise SandboxIdentityError("devcontainer keepalive command must be enabled")
    if payload.get("init") is not True:
        raise SandboxIdentityError("devcontainer init/reaper must be enabled")
    if payload.get("containerUser") != "root" or payload.get("remoteUser") != "vscode":
        raise SandboxIdentityError("devcontainer user boundary differs from policy")
    if payload.get("postStartCommand") != (
        "bash .devcontainer/start_audit_review_sshd.sh --start"
    ):
        raise SandboxIdentityError("devcontainer SSH lifecycle differs from policy")
    expected_features = {EXPECTED_REPOSITORY_FEATURE: {}}
    if payload.get("features") != expected_features:
        raise SandboxIdentityError("repository SSH Feature differs from policy")
    lock_path = repo_root / ".devcontainer" / "devcontainer-lock.json"
    if not lock_path.is_file() or lock_path.is_symlink():
        raise SandboxIdentityError("devcontainer Feature lock is unavailable or unsafe")
    lock_payload = json.loads(lock_path.read_text(encoding="utf-8"))
    expected_lock = {
        "features": {
            EXPECTED_REPOSITORY_FEATURE: {
                "version": "1.1.0",
                "resolved": EXPECTED_REPOSITORY_FEATURE_RESOLVED,
                "integrity": EXPECTED_REPOSITORY_FEATURE_DIGEST,
            }
        }
    }
    if lock_payload != expected_lock:
        raise SandboxIdentityError("devcontainer SSH Feature lock differs from policy")
    dockerfile = repo_root / ".devcontainer" / "Dockerfile"
    if not dockerfile.is_file() or dockerfile.is_symlink():
        raise SandboxIdentityError("devcontainer Dockerfile is unavailable or unsafe")
    from_lines = [
        line.strip()
        for line in dockerfile.read_text(encoding="utf-8").splitlines()
        if line.strip().upper().startswith("FROM ")
    ]
    expected_from = f"FROM {EXPECTED_BASE_IMAGE}"
    if from_lines != [expected_from]:
        raise SandboxIdentityError("devcontainer base image differs from policy")
    digest = EXPECTED_BASE_IMAGE.rsplit("@", 1)[-1]
    if (
        not digest.startswith("sha256:")
        or HEX_64.fullmatch(digest.removeprefix("sha256:")) is None
    ):
        raise SandboxIdentityError("devcontainer base-image digest is malformed")
    if digest not in BASE_IMAGE_EMBEDDED_FEATURE_METADATA_BY_DIGEST:
        raise SandboxIdentityError(
            "devcontainer base-image metadata policy is unavailable"
        )
    return digest


def configured_image_digest(repo_root: Path) -> str:
    """Compatibility alias for the digest-pinned base-image identity."""
    return configured_base_image_digest(repo_root)


def _filesystem_content_sha256(paths: list[Path]) -> str:
    """Hash regular files, symlinks and directory modes without following links."""
    digest = hashlib.sha256()
    unique_paths = sorted({path for path in paths}, key=lambda path: path.as_posix())
    if not unique_paths:
        raise SandboxIdentityError("SSH transport content population is empty")
    for path in unique_paths:
        if not path.is_absolute():
            raise SandboxIdentityError("SSH transport content path is not absolute")
        try:
            mode = path.lstat().st_mode & 0o7777
        except FileNotFoundError as exc:
            raise SandboxIdentityError(
                f"SSH transport content is missing: {path.name}"
            ) from exc
        digest.update(path.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(f"{mode:o}".encode("ascii"))
        digest.update(b"\0")
        if path.is_symlink():
            digest.update(b"symlink\0")
            digest.update(os.readlink(path).encode("utf-8"))
        elif path.is_file():
            digest.update(b"file\0")
            with path.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    digest.update(chunk)
        elif path.is_dir():
            digest.update(b"directory\0")
        else:
            raise SandboxIdentityError(f"SSH transport content is unsafe: {path.name}")
        digest.update(b"\0")
    return digest.hexdigest()


def validate_sshd_effective_config(config_text: str) -> str:
    """Return normalized sshd output after enforcing the complete hardening policy."""
    lines = sorted(line.strip() for line in config_text.splitlines() if line.strip())
    values: dict[str, list[str]] = {}
    for line in lines:
        key, separator, value = line.partition(" ")
        if not separator:
            raise SandboxIdentityError("effective SSH configuration is malformed")
        if key in EXPECTED_SSHD_EFFECTIVE_VALUES or key == "setenv":
            values.setdefault(key, []).append(value.strip())
    for key, expected in EXPECTED_SSHD_EFFECTIVE_VALUES.items():
        if values.get(key) != [expected]:
            raise SandboxIdentityError(
                f"effective SSH policy differs for {key}: expected {expected}"
            )
    setenv_values = [
        assignment for value in values.get("setenv", []) for assignment in value.split()
    ]
    if (
        len(setenv_values) != len(EXPECTED_SSHD_SETENV_VALUES)
        or set(setenv_values) != EXPECTED_SSHD_SETENV_VALUES
    ):
        raise SandboxIdentityError("effective SSH session environment differs")
    return "\n".join(lines) + "\n"


def validate_sshd_include_graph(
    main_config: Path,
    drop_in_population: list[Path],
    *,
    expected_include_pattern: str = "/etc/ssh/sshd_config.d/*.conf",
) -> None:
    """Require one closed, regular-file OpenSSH Include graph."""
    paths = [main_config, *drop_in_population]
    if len(set(paths)) != len(paths):
        raise SandboxIdentityError("SSH configuration population is duplicated")
    for path in paths:
        if not path.is_file() or path.is_symlink():
            raise SandboxIdentityError("SSH configuration population is unsafe")

    def include_arguments(path: Path) -> list[list[str]]:
        directives: list[list[str]] = []
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.partition("#")[0].strip()
            parts = line.split()
            if parts and parts[0].lower() == "include":
                directives.append(parts[1:])
        return directives

    if include_arguments(main_config) != [[expected_include_pattern]]:
        raise SandboxIdentityError("SSH main configuration Include graph differs")
    if any(include_arguments(path) for path in drop_in_population):
        raise SandboxIdentityError("nested SSH configuration Include is unsupported")
    resolved = sorted(main_config.parent.joinpath("sshd_config.d").glob("*.conf"))
    configured = sorted(path for path in drop_in_population if path.suffix == ".conf")
    if configured != resolved:
        raise SandboxIdentityError("SSH drop-in Include population differs")


def build_sshd_session_connection_context(
    ssh_connection: str,
    ssh_client: str,
) -> str:
    """Validate one authenticated Codespaces tunnel tuple for ``sshd -T -C``."""
    connection_parts = ssh_connection.split()
    client_parts = ssh_client.split()
    if len(connection_parts) != 4 or len(client_parts) != 3:
        raise SandboxIdentityError("authenticated SSH connection context is malformed")
    client_address, client_port_text, server_address, server_port_text = (
        connection_parts
    )
    if client_parts != [client_address, client_port_text, server_port_text]:
        raise SandboxIdentityError("SSH_CONNECTION and SSH_CLIENT differ")
    try:
        client = ipaddress.ip_address(client_address)
        server = ipaddress.ip_address(server_address)
        client_port = int(client_port_text)
        server_port = int(server_port_text)
    except ValueError as exc:
        raise SandboxIdentityError(
            "authenticated SSH connection context is malformed"
        ) from exc
    if not client.is_loopback or not server.is_loopback:
        raise SandboxIdentityError(
            "authenticated SSH connection is outside the approved tunnel model"
        )
    if not 1 <= client_port <= 65535 or server_port != 2222:
        raise SandboxIdentityError(
            "authenticated SSH connection ports differ from the approved tunnel model"
        )
    return (
        "user=vscode,host=localhost,"
        f"addr={client.compressed},laddr={server.compressed},lport={server_port}"
    )


def _validate_ssh_transport_package_inventory(inventory: list[str]) -> None:
    """Require one exact installed record for every SSH transport package."""
    if len(inventory) != len(EXPECTED_SSH_TRANSPORT_PACKAGES) or len(
        set(inventory)
    ) != len(inventory):
        raise SandboxIdentityError("SSH transport package inventory is malformed")
    package_names: set[str] = set()
    for line in inventory:
        parts = line.split("|", 3)
        if (
            len(parts) != 4
            or not parts[0]
            or not parts[1]
            or parts[2] != "install ok installed"
            or not parts[3]
            or parts[0] in package_names
        ):
            raise SandboxIdentityError("SSH transport package inventory is malformed")
        package_names.add(parts[0])
    if package_names != EXPECTED_SSH_TRANSPORT_PACKAGES:
        raise SandboxIdentityError("SSH transport package inventory is incomplete")


def _read_ssh_wire_string(blob: bytes, offset: int) -> tuple[bytes, int]:
    """Read one RFC 4251 length-prefixed string from an SSH key blob."""
    if offset + 4 > len(blob):
        raise SandboxIdentityError("SSH host public-key wire data is malformed")
    length = int.from_bytes(blob[offset : offset + 4], "big")
    start = offset + 4
    end = start + length
    if length == 0 or end > len(blob):
        raise SandboxIdentityError("SSH host public-key wire data is malformed")
    return blob[start:end], end


def _positive_ssh_mpint(value: bytes) -> int:
    """Decode one canonical positive RFC 4251 mpint."""
    if value[0] & 0x80 or (len(value) > 1 and value[0] == 0 and value[1] & 0x80 == 0):
        raise SandboxIdentityError("SSH RSA public-key mpint is malformed")
    decoded = int.from_bytes(value, "big")
    if decoded <= 0:
        raise SandboxIdentityError("SSH RSA public-key mpint is malformed")
    return decoded


def _validated_ssh_public_key_blob(value: str) -> bytes:
    """Decode one allowed OpenSSH public key and validate its wire structure."""
    if "\n" in value or "\r" in value:
        raise SandboxIdentityError("SSH host public-key identity is malformed")
    parts = value.split(maxsplit=2)
    if len(parts) < 2 or parts[0] not in EXPECTED_SSH_HOST_KEY_ALGORITHMS:
        raise SandboxIdentityError("SSH host public-key identity is malformed")
    algorithm, encoded = parts[:2]
    try:
        key_blob = base64.b64decode(
            encoded + "=" * (-len(encoded) % 4),
            validate=True,
        )
    except (ValueError, binascii.Error) as exc:
        raise SandboxIdentityError("SSH host public-key identity is malformed") from exc

    wire_algorithm, offset = _read_ssh_wire_string(key_blob, 0)
    try:
        wire_algorithm_name = wire_algorithm.decode("ascii")
    except UnicodeDecodeError as exc:
        raise SandboxIdentityError(
            "SSH host public-key wire algorithm is malformed"
        ) from exc
    if wire_algorithm_name != algorithm:
        raise SandboxIdentityError("SSH host public-key text/wire algorithms differ")

    if algorithm == "ssh-ed25519":
        public_key, offset = _read_ssh_wire_string(key_blob, offset)
        valid_structure = len(public_key) == 32
    elif algorithm == "ecdsa-sha2-nistp256":
        curve, offset = _read_ssh_wire_string(key_blob, offset)
        public_key, offset = _read_ssh_wire_string(key_blob, offset)
        x = int.from_bytes(public_key[1:33], "big") if len(public_key) == 65 else -1
        y = int.from_bytes(public_key[33:65], "big") if len(public_key) == 65 else -1
        valid_structure = (
            curve == b"nistp256"
            and len(public_key) == 65
            and public_key.startswith(b"\x04")
            and 0 <= x < P256_PRIME
            and 0 <= y < P256_PRIME
            and pow(y, 2, P256_PRIME)
            == (pow(x, 3, P256_PRIME) - 3 * x + P256_B) % P256_PRIME
        )
    else:
        exponent_bytes, offset = _read_ssh_wire_string(key_blob, offset)
        modulus_bytes, offset = _read_ssh_wire_string(key_blob, offset)
        exponent = _positive_ssh_mpint(exponent_bytes)
        modulus = _positive_ssh_mpint(modulus_bytes)
        valid_structure = (
            exponent > 1
            and exponent % 2 == 1
            and modulus.bit_length() >= 1024
            and modulus % 2 == 1
        )
    if not valid_structure or offset != len(key_blob):
        raise SandboxIdentityError("SSH host public-key wire data is malformed")
    return key_blob


def build_sshd_transport_identity(
    *,
    effective_config: str,
    package_inventory: str,
    package_paths: list[Path],
    extra_paths: list[Path],
    host_public_key_material: list[str],
    host_public_key_sidecars: list[str],
) -> dict[str, object]:
    """Build a path-free identity for the installed SSH transport surface."""
    normalized_config = validate_sshd_effective_config(effective_config)
    inventory = sorted(
        line.strip() for line in package_inventory.splitlines() if line.strip()
    )
    _validate_ssh_transport_package_inventory(inventory)

    if len(host_public_key_material) != 3 or len(host_public_key_sidecars) != 3:
        raise SandboxIdentityError("SSH host private/public key population differs")
    for derived, sidecar in zip(
        host_public_key_material,
        host_public_key_sidecars,
        strict=True,
    ):
        if _validated_ssh_public_key_blob(derived) != _validated_ssh_public_key_blob(
            sidecar
        ):
            raise SandboxIdentityError("SSH host private/public key population differs")
    derived_public_keys = sorted(set(host_public_key_material))
    if len(derived_public_keys) != 3:
        raise SandboxIdentityError("SSH host private/public key population differs")
    algorithms = {
        value.split(" ", 1)[0] for value in derived_public_keys if " " in value
    }
    if algorithms != EXPECTED_SSH_HOST_KEY_ALGORITHMS:
        raise SandboxIdentityError("SSH host-key algorithm population differs")

    fingerprints: list[str] = []
    for value in derived_public_keys:
        key_blob = _validated_ssh_public_key_blob(value)
        encoded_fingerprint = base64.b64encode(
            hashlib.sha256(key_blob).digest()
        ).decode("ascii")
        fingerprints.append(f"SHA256:{encoded_fingerprint.rstrip('=')}")
    if len(set(fingerprints)) != 3:
        raise SandboxIdentityError("SSH host public-key identity is malformed")

    payload: dict[str, object] = {
        "ssh_transport_packages": inventory,
        "sshd_effective_config_sha256": hashlib.sha256(
            normalized_config.encode("utf-8")
        ).hexdigest(),
        "sshd_transport_content_sha256": _filesystem_content_sha256(
            package_paths + extra_paths
        ),
        "sshd_host_public_key_fingerprints": fingerprints,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    payload["sshd_identity_sha256"] = hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()
    return payload


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
    current_image = configured_base_image_digest(repo_root)
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

    return {
        "git_commit": _git(repo_root, "rev-parse", "HEAD"),
        "git_tree": _git(repo_root, "rev-parse", "HEAD^{tree}"),
        "devcontainer_base_image_digest": current_image,
        "repository_configured_devcontainer_features": [
            EXPECTED_REPOSITORY_FEATURE_RESOLVED
        ],
        "base_image_embedded_feature_metadata": list(
            BASE_IMAGE_EMBEDDED_FEATURE_METADATA_BY_DIGEST[current_image]
        ),
        "dependency_input_sha256": current_dependency,
        "installed_distribution_set_sha256": current_packages,
        "installed_environment_content_sha256": current_package_content,
        "controlled_input_sha256": {
            relative: _sha256_file(repo_root / relative)
            for relative in CONTROLLED_INPUT_RELATIVES
        },
    }


def _validate_receipt_inputs(
    identity: dict[str, object],
    sshd_identity: dict[str, object],
) -> None:
    """Fail closed when a receipt builder receives an incomplete identity."""
    expected_identity_keys = {
        "git_commit",
        "git_tree",
        "devcontainer_base_image_digest",
        "repository_configured_devcontainer_features",
        "base_image_embedded_feature_metadata",
        "dependency_input_sha256",
        "installed_distribution_set_sha256",
        "installed_environment_content_sha256",
        "controlled_input_sha256",
    }
    if set(identity) != expected_identity_keys:
        raise SandboxIdentityError("sandbox identity receipt fields differ from schema")
    expected_sshd_keys = {
        "ssh_transport_packages",
        "sshd_effective_config_sha256",
        "sshd_transport_content_sha256",
        "sshd_host_public_key_fingerprints",
        "sshd_identity_sha256",
    }
    if set(sshd_identity) != expected_sshd_keys:
        raise SandboxIdentityError("SSH identity receipt fields differ from schema")
    for key in (
        "dependency_input_sha256",
        "installed_distribution_set_sha256",
        "installed_environment_content_sha256",
    ):
        if (
            not isinstance(identity[key], str)
            or HEX_64.fullmatch(identity[key]) is None
        ):
            raise SandboxIdentityError(f"sandbox identity digest is malformed: {key}")
    for key in (
        "sshd_effective_config_sha256",
        "sshd_transport_content_sha256",
        "sshd_identity_sha256",
    ):
        if (
            not isinstance(sshd_identity[key], str)
            or HEX_64.fullmatch(sshd_identity[key]) is None
        ):
            raise SandboxIdentityError(f"SSH identity digest is malformed: {key}")
    for key in ("git_commit", "git_tree"):
        value = identity[key]
        if (
            not isinstance(value, str)
            or re.fullmatch(r"[0-9a-f]{40,64}", value) is None
        ):
            raise SandboxIdentityError(f"Git identity is malformed: {key}")
    base_digest = identity["devcontainer_base_image_digest"]
    if (
        not isinstance(base_digest, str)
        or not base_digest.startswith("sha256:")
        or HEX_64.fullmatch(base_digest.removeprefix("sha256:")) is None
    ):
        raise SandboxIdentityError("base-image identity is malformed")
    if identity["repository_configured_devcontainer_features"] != [
        EXPECTED_REPOSITORY_FEATURE_RESOLVED
    ]:
        raise SandboxIdentityError(
            "repository-configured Feature identity is malformed"
        )
    embedded = identity["base_image_embedded_feature_metadata"]
    expected_embedded = BASE_IMAGE_EMBEDDED_FEATURE_METADATA_BY_DIGEST.get(base_digest)
    if (
        not isinstance(embedded, list)
        or expected_embedded is None
        or embedded != list(expected_embedded)
    ):
        raise SandboxIdentityError("base-image Feature metadata is malformed")
    controlled = identity["controlled_input_sha256"]
    if (
        not isinstance(controlled, dict)
        or set(controlled) != set(CONTROLLED_INPUT_RELATIVES)
        or not all(
            isinstance(path, str)
            and path
            and isinstance(digest, str)
            and HEX_64.fullmatch(digest) is not None
            for path, digest in controlled.items()
        )
    ):
        raise SandboxIdentityError("controlled-input identity is malformed")
    packages = sshd_identity["ssh_transport_packages"]
    fingerprints = sshd_identity["sshd_host_public_key_fingerprints"]
    if (
        not isinstance(packages, list)
        or not all(isinstance(value, str) and value for value in packages)
        or not isinstance(fingerprints, list)
        or len(fingerprints) != 3
        or len(set(fingerprints)) != 3
        or not all(
            isinstance(value, str) and SSH_FINGERPRINT.fullmatch(value) is not None
            for value in fingerprints
        )
    ):
        raise SandboxIdentityError("SSH identity populations are malformed")
    _validate_ssh_transport_package_inventory(packages)
    canonical_sshd = dict(sshd_identity)
    recorded_sshd_digest = canonical_sshd.pop("sshd_identity_sha256")
    canonical = json.dumps(canonical_sshd, sort_keys=True, separators=(",", ":"))
    if recorded_sshd_digest != hashlib.sha256(canonical.encode("utf-8")).hexdigest():
        raise SandboxIdentityError("SSH identity self-digest is malformed")


def build_bootstrap_receipt(
    *,
    identity: dict[str, object],
    sshd_identity: dict[str, object],
    source_state: str,
    execution_host: str,
    codespace_name: str,
) -> dict[str, object]:
    """Build the exact v3 bootstrap receipt on the release-HOLD side."""
    _validate_receipt_inputs(identity, sshd_identity)
    if source_state not in BOOTSTRAP_SOURCE_STATES:
        raise SandboxIdentityError("bootstrap P03 source state differs from schema")
    try:
        network_boundary = EXECUTION_HOST_NETWORK_BOUNDARIES[execution_host]
    except KeyError as exc:
        raise SandboxIdentityError(
            "bootstrap execution-host provenance differs from schema"
        ) from exc
    if (
        not isinstance(codespace_name, str)
        or CODESPACE_NAME.fullmatch(codespace_name) is None
    ):
        raise SandboxIdentityError("bootstrap Codespace identity is malformed")
    return {
        "schema": BOOTSTRAP_RECEIPT_SCHEMA,
        "status": "PASS",
        "environment": execution_host,
        "codespace_name": codespace_name,
        "python": "3.12",
        **identity,
        **sshd_identity,
        "p03_source_state": source_state,
        "network_boundary": network_boundary,
        "completion_authorized": False,
        "release_status": "HOLD",
    }


def build_verification_receipt(
    *,
    identity: dict[str, object],
    sshd_identity: dict[str, object],
    source_state: str,
    execution_host: str,
    codespace_name: str,
) -> dict[str, object]:
    """Build the exact v3 structural-verification receipt without semantic closure."""
    _validate_receipt_inputs(identity, sshd_identity)
    if source_state not in VERIFICATION_SOURCE_STATES:
        raise SandboxIdentityError("verification P03 source state differs from schema")
    try:
        network_boundary = EXECUTION_HOST_NETWORK_BOUNDARIES[execution_host]
    except KeyError as exc:
        raise SandboxIdentityError(
            "verification execution-host provenance differs from schema"
        ) from exc
    if (
        not isinstance(codespace_name, str)
        or CODESPACE_NAME.fullmatch(codespace_name) is None
    ):
        raise SandboxIdentityError("verification Codespace identity is malformed")
    return {
        "schema": VERIFICATION_RECEIPT_SCHEMA,
        "status": "PASS",
        "environment": execution_host,
        "codespace_name": codespace_name,
        **identity,
        **sshd_identity,
        "sshd_process": "running",
        "p02_structural_controls": "passed",
        "p03_source_state": source_state,
        "network_boundary": network_boundary,
        "semantic_review_completed": False,
        "completion_authorized": False,
        "release_status": "HOLD",
    }
