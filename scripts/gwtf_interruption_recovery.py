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
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__:
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


def capture(
    root: Path, lease: dict[str, Any], output: Path, *, preserve_bytes: bool = False
) -> dict[str, Any]:
    root = root.resolve()
    require(
        not any(k in os.environ for k in ready.FORBIDDEN_ENV),
        "execution environment override present",
    )
    require(
        Path(ready.git_text(root, "rev-parse", "--show-toplevel")).resolve() == root,
        "incorrect worktree",
    )
    require(
        Path(lease["worktree"]).resolve() == root and bool(lease["lease_id"]),
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
    output = receipt.safe_external(output)
    output.mkdir(mode=0o700)
    before = state(root)
    ident = before["identity"]
    expected_identity = all(
        ident[k] == lease[k] for k in ("branch", "head", "tree", "base")
    ) and ident["branch"] not in {"", "main", "master"}
    unexpected = sorted(set(before["changed_paths"]) - set(scope))
    # Do not copy bytes from an unowned or out-of-scope tree. Explicit opt-in
    # is required even for a matching lease, and the coordinator must verify rights.
    preserved: dict[str, dict[str, Any]] = {}
    if preserve_bytes and expected_identity and not unexpected:
        for i, name in enumerate(sorted(set(before["changed_paths"]) & set(scope))):
            path = ready.path_at(root, name)
            item: dict[str, Any] = {}
            if path.is_symlink() or (path.exists() and not path.is_file()):
                item["unsupported_working_object"] = True
            elif path.is_file():
                filename = f"{i:04d}-working.bin"
                item["working"] = {
                    "file": filename,
                    "sha256": write_new(output / filename, path.read_bytes()),
                }
            else:
                item["working_missing"] = True
            index = subprocess.run(
                ["git", "show", ":" + name], cwd=root, capture_output=True, check=False
            )
            if index.returncode == 0:
                filename = f"{i:04d}-index.bin"
                item["index"] = {
                    "file": filename,
                    "sha256": write_new(output / filename, index.stdout),
                }
            else:
                item["index_unavailable"] = True
            preserved[name] = item
    after = state(root)
    stable = before == after
    record = {
        "schema": 1,
        "state": "OBSERVED_READ_ONLY",
        "observed_utc": datetime.now(timezone.utc).isoformat(),
        "lease_id": lease["lease_id"],
        "worktree": str(root),
        "prior_identity_matches": expected_identity,
        "unexpected_paths": unexpected,
        "stable_observation": stable,
        "before": before,
        "after": after,
        "preserved": preserved,
        "preserve_bytes_requested": preserve_bytes,
        "writer_authorized": False,
        "limitations": "Git-visible state only. Copying requires independently established source rights. No owner/worker identity, process termination, live base, secret absence or platform permission authenticated.",
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
    observation = receipt.safe_external(observation)
    require(
        not any(k in os.environ for k in ready.FORBIDDEN_ENV),
        "execution environment override present",
    )
    require(ready.digest(observation) == expected_digest, "observation digest mismatch")
    data = json.loads(observation.read_text())
    require(
        prior["state"] == "REVOKED" and prior["lease_id"] == data["lease_id"],
        "prior lease must be revoked",
    )
    require(
        Path(prior["worktree"]).resolve() == root
        and Path(data["worktree"]).resolve() == root,
        "recovery worktree mismatch",
    )
    require(
        data["stable_observation"]
        and data["prior_identity_matches"]
        and not data["unexpected_paths"],
        "drift or ownership uncertainty requires separate reconciliation",
    )
    require(state(root) == data["after"], "observed state has changed")
    for item in data["preserved"].values():
        for kind in ("working", "index"):
            if kind in item:
                blob = item[kind]
                require(
                    ready.digest(
                        receipt.evidence_file(observation.parent, blob["file"])
                    )
                    == blob["sha256"],
                    "preserved bytes digest mismatch",
                )
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
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--preserve-authorized-bytes", action="store_true")
    args = parser.parse_args()
    try:
        result = capture(
            args.worktree,
            json.loads(args.lease.read_text()),
            args.output,
            preserve_bytes=args.preserve_authorized_bytes,
        )
    except (
        OSError,
        ValueError,
        KeyError,
        ready.ReadinessError,
        subprocess.CalledProcessError,
    ) as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "state",
                    "stable_observation",
                    "prior_identity_matches",
                    "unexpected_paths",
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
        and not result["unexpected_paths"]
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
