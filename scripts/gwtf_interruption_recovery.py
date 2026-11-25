"""G4: preserve and reconcile observed state without granting writer authority.

Only an independently authorized coordinator may issue a new lease. This helper
never restores, stages, commits, stops processes or retries a blocked operation.
Git-visible state excludes ignored files and is not a filesystem sandbox.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if not TYPE_CHECKING and __package__:
    from . import gwtf_checkpoint_readiness as ready
    from . import gwtf_checkpoint_receipt as receipt
else:
    import gwtf_checkpoint_readiness as ready
    import gwtf_checkpoint_receipt as receipt


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def state(root: Path) -> dict[str, Any]:
    return {
        "identity": ready.identity(root),
        "changed_paths": sorted(ready.changed(root)),
        "snapshot": ready.snapshot(root),
        "status_hex": ready.git(
            root, "--no-optional-locks", "status", "--porcelain=v1", "-z"
        ).hex(),
    }


def write_new(path: Path, data: bytes) -> str:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as out:
        out.write(data)
        out.flush()
        os.fsync(out.fileno())
    return hashlib.sha256(data).hexdigest()


def read_regular(path: Path) -> bytes:
    """Read/hash the same regular-file bytes; refuse final-component links/FIFOs."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode), "regular evidence file required")
        raw = stream.read()
        after = os.fstat(stream.fileno())
        require(
            (
                before.st_dev,
                before.st_ino,
                before.st_size,
                before.st_mtime_ns,
                before.st_ctime_ns,
            )
            == (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            ),
            "file changed while reading",
        )
    return raw


def lease_binding(root: Path, lease: dict[str, Any]) -> dict[str, Any]:
    require(isinstance(lease, dict), "invalid prior lease")
    require(
        Path(lease["worktree"]).resolve() == root
        and isinstance(lease["lease_id"], str)
        and bool(lease["lease_id"]),
        "prior lease worktree or identity mismatch",
    )
    scope = lease["allowlist"]
    require(
        isinstance(scope, list)
        and bool(scope)
        and all(isinstance(x, str) for x in scope)
        and len(set(scope)) == len(scope),
        "invalid prior allowlist",
    )
    for name in scope:
        ready.path_at(root, name)
    require(
        all(
            receipt.hex_value(lease[k], receipt.HEX40) for k in ("head", "tree", "base")
        ),
        "invalid prior Git identity",
    )
    require(receipt.hex_value(lease["index_sha256"]), "initial index evidence required")
    require(
        isinstance(lease["branch"], str)
        and lease["branch"] not in {"", "main", "master"},
        "protected or detached prior branch",
    )
    return {
        **{
            k: lease[k]
            for k in (
                "lease_id",
                "worktree",
                "branch",
                "head",
                "tree",
                "base",
                "index_sha256",
            )
        },
        "allowlist": sorted(scope),
    }


def check_root(root: Path) -> None:
    require(
        not any(k in os.environ for k in ready.FORBIDDEN_ENV),
        "execution environment override present",
    )
    require(
        Path(ready.git_text(root, "rev-parse", "--show-toplevel")).resolve() == root,
        "incorrect worktree",
    )


def state_summary(observed: dict[str, Any], binding: dict[str, Any]) -> dict[str, Any]:
    """Persist a whole-state commitment, not unrelated names or per-file hashes."""
    changed = set(observed["changed_paths"])
    scope = set(binding["allowlist"])
    return {
        "state_sha256": receipt.digest(receipt.canonical(observed)),
        "identity": observed["identity"],
        "scoped_changed_paths": sorted(changed & scope),
        "unexpected_path_count": len(changed - scope),
    }


def identity_matches(observed: dict[str, Any], binding: dict[str, Any]) -> bool:
    # The original index is bound to the lease but may legitimately differ now.
    return all(
        observed["identity"][k] == binding[k]
        for k in ("branch", "head", "tree", "base")
    )


def scoped_bytes(
    root: Path, observed: dict[str, Any], scope: list[str]
) -> dict[str, dict[str, bytes]]:
    """Re-derive scoped working bytes and actual stage-zero objects."""
    require(ready.identity(root) == observed["identity"], "index or identity drift")
    entries = ready.staged_entries(root)
    values: dict[str, dict[str, bytes]] = {}
    for name in scope:
        path = ready.path_at(root, name)
        snap = observed["snapshot"].get(name, "missing")
        item: dict[str, bytes] = {}
        if snap != "missing":
            require(
                not path.is_symlink() and path.is_file(),
                "unsupported scoped working object",
            )
            raw = read_regular(path)
            mode = stat.S_IMODE(path.lstat().st_mode)
            require(
                snap == f"{mode:o}:" + receipt.digest(raw),
                "working bytes differ from observed snapshot",
            )
            item["working"] = raw
        else:
            require(
                not path.exists() and not path.is_symlink(),
                "missing working object changed",
            )
        if name in entries:
            index_mode, oid = entries[name]
            require(
                index_mode in {"100644", "100755"}, "unsupported scoped index object"
            )
            item["index"] = ready.git(root, "cat-file", "blob", oid)
        values[name] = item
    require(ready.identity(root) == observed["identity"], "index or identity drift")
    return values


def capture(
    root: Path, lease: dict[str, Any], output: Path, *, preserve_bytes: bool = False
) -> dict[str, Any]:
    root = root.resolve()
    check_root(root)
    binding = lease_binding(root, lease)
    output = receipt.safe_external(output)
    output.mkdir(mode=0o700)
    before = state(root)
    summary = state_summary(before, binding)
    matches = identity_matches(before, binding)
    preserved: dict[str, dict[str, Any]] = {}
    if preserve_bytes and matches and not summary["unexpected_path_count"]:
        values = scoped_bytes(root, before, summary["scoped_changed_paths"])
        for i, (name, item) in enumerate(values.items()):
            preserved[name] = {}
            for kind, raw in item.items():
                filename = f"{i:04d}-{kind}.bin"
                preserved[name][kind] = {
                    "file": filename,
                    "sha256": write_new(output / filename, raw),
                }
    after = state(root)
    stable = before == after
    record = {
        "schema": 2,
        "state": "OBSERVED_READ_ONLY",
        "observed_utc": datetime.now(timezone.utc).isoformat(),
        "lease_id": binding["lease_id"],
        "lease_binding_sha256": receipt.digest(receipt.canonical(binding)),
        "prior_identity_matches": matches,
        "unexpected_path_count": summary["unexpected_path_count"],
        "stable_observation": stable,
        "before": summary,
        "after": state_summary(after, binding),
        "preserved": preserved,
        "preserve_bytes_requested": preserve_bytes,
        "writer_authorized": False,
        "limitations": "Git-visible state only; aggregate digest is not anonymization. Copying requires independently established source rights. No sandbox, owner/worker identity, process termination, live base, secret absence or platform permission authenticated. Concurrent changes between observations and ignored paths remain limitations.",
    }
    write_new(output / "observation.json", receipt.canonical(record) + b"\n")
    return record


def assess(
    root: Path,
    prior: dict[str, Any],
    observation: Path,
    expected_digest: str,
    coordinator_evidence: dict[str, Any],
) -> dict[str, Any]:
    """Return eligibility for coordinator review, never a new writer lease."""
    root = root.resolve()
    check_root(root)
    observation = receipt.safe_external(observation)
    raw = read_regular(observation)
    require(receipt.digest(raw) == expected_digest, "observation digest mismatch")
    data = ready.strict_json(raw)
    require(
        isinstance(data, dict)
        and data.get("schema") == 2
        and data.get("state") == "OBSERVED_READ_ONLY",
        "unsupported recovery observation",
    )
    binding = lease_binding(root, prior)
    require(
        prior["state"] == "REVOKED" and binding["lease_id"] == data["lease_id"],
        "prior lease must be revoked",
    )
    require(
        data["lease_binding_sha256"] == receipt.digest(receipt.canonical(binding)),
        "revoked lease binding mismatch",
    )
    current = state(root)
    summary = state_summary(current, binding)
    require(
        identity_matches(current, binding)
        and summary["unexpected_path_count"] == 0
        and data["before"] == summary == data["after"]
        and data["stable_observation"] is True
        and data["prior_identity_matches"] is True
        and data["unexpected_path_count"] == 0,
        "drift or ownership uncertainty requires separate reconciliation",
    )
    preserved = data["preserved"]
    require(
        isinstance(preserved, dict) and type(data["preserve_bytes_requested"]) is bool,
        "invalid preserved evidence",
    )
    if data["preserve_bytes_requested"]:
        values = scoped_bytes(root, current, summary["scoped_changed_paths"])
        require(set(preserved) == set(values), "preserved scope mismatch")
        for i, (name, item) in enumerate(values.items()):
            require(
                isinstance(preserved[name], dict) and set(preserved[name]) == set(item),
                "preserved object set mismatch",
            )
            for kind, raw in item.items():
                blob = preserved[name][kind]
                filename = f"{i:04d}-{kind}.bin"
                require(
                    blob == {"file": filename, "sha256": receipt.digest(raw)},
                    "preserved object binding mismatch",
                )
                require(
                    read_regular(receipt.evidence_file(observation.parent, filename))
                    == raw,
                    "preserved bytes digest mismatch",
                )
    else:
        require(not preserved, "unexpected preserved evidence")
    require(state(root) == current, "observed state has changed")
    require(
        bool(coordinator_evidence.get("coordinator"))
        and bool(coordinator_evidence.get("ownership_reference"))
        and bool(coordinator_evidence.get("stop_request_reference")),
        "coordinator ownership and stop evidence required",
    )
    require(
        coordinator_evidence.get("prior_worker_disposition")
        in {"ACKNOWLEDGED_STOP", "INDEPENDENT_TERMINATION_OBSERVED"}
        and bool(coordinator_evidence.get("stop_proof_reference")),
        "no acknowledgement or termination evidence",
    )
    require(
        coordinator_evidence.get("platform_restriction_pending") is False,
        "platform restriction unresolved; do not retry",
    )
    return {
        "state": "COORDINATOR_REVIEW_REQUIRED",
        "prior_lease_id": prior["lease_id"],
        "observation_sha256": expected_digest,
        "writer_authorized": False,
        "fresh_lease_required": True,
        "evidence_authenticated": False,
        "limitations": "References are supplied claims; coordinator independently verifies ownership, stop proof, authority, live base and source rights before issuing any new lease.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worktree", type=Path, required=True)
    parser.add_argument("--lease", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--assess-observation", type=Path)
    parser.add_argument("--expected-digest")
    parser.add_argument("--coordinator-evidence", type=Path)
    parser.add_argument("--preserve-authorized-bytes", action="store_true")
    args = parser.parse_args()
    try:
        lease = ready.strict_json(read_regular(receipt.safe_external(args.lease)))
        if args.assess_observation is not None:
            require(
                args.output is None
                and not args.preserve_authorized_bytes
                and args.expected_digest is not None
                and args.coordinator_evidence is not None,
                "invalid assessment arguments",
            )
            result = assess(
                args.worktree,
                lease,
                args.assess_observation,
                args.expected_digest,
                ready.strict_json(
                    read_regular(receipt.safe_external(args.coordinator_evidence))
                ),
            )
            print(json.dumps(result, indent=2))
            return 0
        require(
            args.output is not None
            and args.expected_digest is None
            and args.coordinator_evidence is None,
            "invalid capture arguments",
        )
        result = capture(
            args.worktree,
            lease,
            args.output,
            preserve_bytes=args.preserve_authorized_bytes,
        )
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
        ready.ReadinessError,
        subprocess.CalledProcessError,
    ):
        print(
            "STOP: recovery refused; preserve evidence and reconcile", file=sys.stderr
        )
        return 1
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "state",
                    "stable_observation",
                    "prior_identity_matches",
                    "unexpected_path_count",
                    "writer_authorized",
                )
            },
            indent=2,
        )
    )
    return (
        0
        if result["stable_observation"]
        and result["prior_identity_matches"]
        and not result["unexpected_path_count"]
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
