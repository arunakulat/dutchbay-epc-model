"""G2: canonical hook readiness, not a checkpoint or approval.

Detect Git-visible drift; this is not a sandbox or a writer-lease authenticator.
Any formatter mutation invalidates readiness and requires a fresh lease.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

CONFIG = ".pre-commit-config.yaml"
FORBIDDEN_ENV = (
    "SKIP",
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_COMMON_DIR",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_CONFIG_COUNT",
    "GIT_CONFIG_PARAMETERS",
    "PRE_COMMIT_ALLOW_NO_CONFIG",
)


class ReadinessError(RuntimeError):
    """The candidate cannot be declared ready."""


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ReadinessError(message)


def git(root: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=root)


def git_text(root: Path, *args: str) -> str:
    return git(root, *args).decode().strip()


def names(raw: bytes) -> set[str]:
    return {os.fsdecode(item) for item in raw.split(b"\0") if item}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def path_at(root: Path, name: str) -> Path:
    rel = Path(name)
    require(
        bool(name)
        and name != "."
        and not rel.is_absolute()
        and not name.startswith("-")
        and ".." not in rel.parts
        and ".git" not in rel.parts
        and rel.as_posix() == name,
        "unsafe path",
    )
    path = root / rel
    require(path.parent.resolve().is_relative_to(root), "path escapes worktree")
    require(
        all(
            not p.is_symlink()
            for p in path.parents
            if p != root and p.is_relative_to(root)
        ),
        "symlink ancestor",
    )
    return path


def changed(root: Path) -> set[str]:
    return (
        names(git(root, "diff", "--name-only", "--no-renames", "-z", "HEAD"))
        | names(git(root, "diff", "--cached", "--name-only", "--no-renames", "-z"))
        | names(git(root, "diff", "--name-only", "--no-renames", "-z"))
        | names(git(root, "ls-files", "--others", "--exclude-standard", "-z"))
    )


def identity(root: Path) -> dict[str, str]:
    return {
        "branch": git_text(root, "branch", "--show-current"),
        "head": git_text(root, "rev-parse", "HEAD"),
        "tree": git_text(root, "rev-parse", "HEAD^{tree}"),
        "base": git_text(root, "rev-parse", "origin/main"),
        "index_sha256": sha(git(root, "ls-files", "--stage", "-z")),
    }


def snapshot(root: Path) -> dict[str, str]:
    """Hash tracked and nonignored untracked files, including modes and links."""
    flags = git(root, "ls-files", "-v", "-z").split(b"\0")
    require(
        not any(x and (x[:1].islower() or x[:1] == b"S") for x in flags),
        "assume-unchanged or skip-worktree entries unsupported",
    )
    files = names(
        git(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z")
    )
    result = {}
    for name in sorted(files):
        p = path_at(root, name)
        if p.is_symlink():
            result[name] = "link:" + sha(os.fsencode(os.readlink(p)))
        elif not p.exists():
            result[name] = "missing"
        else:
            mode = p.stat().st_mode
            require(stat.S_ISREG(mode), f"unsupported Git-visible object: {name}")
            result[name] = f"{stat.S_IMODE(mode):o}:" + digest(p)
    return result


def verify_candidate(
    root: Path, lease: dict[str, Any]
) -> tuple[dict[str, str], dict[str, str], list[str]]:
    require(
        not any(k in os.environ for k in FORBIDDEN_ENV),
        "execution environment override present",
    )
    require(
        Path(git_text(root, "rev-parse", "--show-toplevel")).resolve() == root,
        "incorrect worktree",
    )
    require(Path(lease["worktree"]).resolve() == root, "lease worktree mismatch")
    require(
        lease["state"] == "PATCH_APPLIED" and bool(lease["lease_id"]),
        "fresh applied-patch lease required",
    )
    require(
        bool(lease["holder"]) and bool(lease["coordinator"]),
        "writer authority not recorded",
    )
    ident = identity(root)
    require(
        bool(ident["branch"]) and ident["branch"] not in {"main", "master"},
        "protected or detached branch",
    )
    require(
        all(ident[k] == lease[k] for k in ("branch", "head", "tree", "base")),
        "lease Git identity mismatch",
    )
    scope = lease["allowlist"]
    require(
        isinstance(scope, list)
        and bool(scope)
        and all(isinstance(x, str) for x in scope)
        and len(set(scope)) == len(scope),
        "invalid exact file allowlist",
    )
    require(changed(root) == set(scope), "candidate changes differ from allowlist")
    require(
        CONFIG not in scope
        and (root / CONFIG).is_file()
        and not (root / CONFIG).is_symlink(),
        "canonical hook configuration change requires separate review",
    )
    require(
        (root / CONFIG).read_bytes() == git(root, "show", f"HEAD:{CONFIG}"),
        "canonical hook configuration differs from HEAD",
    )
    cfg = subprocess.run(
        ["git", "config", "--get", "core.hooksPath"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    require(cfg.returncode == 1, "custom or indeterminate hooks path")
    hook = root / git_text(root, "rev-parse", "--git-path", "hooks/pre-commit")
    require(
        hook.is_file() and os.access(hook, os.X_OK),
        "installed executable pre-commit hook required",
    )
    candidate = {}
    for name in scope:
        p = path_at(root, name)
        require(
            p.is_file() and not p.is_symlink(),
            "G2 requires regular candidate files; deletions require separate handling",
        )
        candidate[name] = digest(p)
    require(candidate == lease["candidate_sha256"], "candidate content drift")
    return ident, snapshot(root), sorted(scope)


def run_readiness(root: Path, lease: dict[str, Any], receipt: Path) -> None:
    """Two clean pinned-hook passes; stop on any visible drift, never stage."""
    root = root.resolve()
    receipt = receipt.resolve()
    require(
        not receipt.is_relative_to(root)
        and not any(
            (p / ".git").exists() for p in (receipt.parent, *receipt.parent.parents)
        ),
        "receipt must be outside Git worktrees",
    )
    require(receipt.parent.is_dir(), "receipt parent must already exist")
    fd = os.open(receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:

        def emit(state: str, **fields: Any) -> None:
            stream.write(
                json.dumps(
                    {"state": state, "lease_id": lease.get("lease_id"), **fields}
                )
                + "\n"
            )
            stream.flush()
            os.fsync(stream.fileno())

        emit(
            "STARTED",
            checkpoint_verified=False,
            tests_verified=False,
            independent_review_complete=False,
            limitations="Git-visible tracked/nonignored paths only; not a sandbox, live remote-base attestation, lease authentication, installed-hook authentication or release authority. Coordinator verifies live base and exclusive writer.",
        )
        try:
            ident, before, scope = verify_candidate(root, lease)
            emit(
                "PREFLIGHTED",
                identity=ident,
                candidate_sha256=lease["candidate_sha256"],
                config_sha256=digest(root / CONFIG),
            )
            command = [
                sys.executable,
                "-m",
                "pre_commit",
                "run",
                "--config",
                CONFIG,
                "--hook-stage",
                "pre-commit",
                "--files",
                *scope,
            ]
            for attempt in (1, 2):
                result = subprocess.run(
                    command, cwd=root, capture_output=True, check=False
                )
                log = receipt.with_name(receipt.name + f".pass{attempt}.log")
                logfd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(logfd, "wb") as out:
                    out.write(result.stdout + result.stderr)
                    out.flush()
                    os.fsync(out.fileno())
                after = snapshot(root)
                drift = sorted(
                    k
                    for k in before.keys() | after.keys()
                    if before.get(k) != after.get(k)
                )
                same_identity = identity(root) == ident
                emit(
                    "HOOK_PASS_OBSERVED",
                    pass_number=attempt,
                    command=command,
                    exit_code=result.returncode,
                    log_sha256=digest(log),
                    drift=drift,
                    index_and_identity_unchanged=same_identity,
                )
                require(
                    same_identity and not drift,
                    "hook changed candidate, index or worktree; preserve state and revoke lease",
                )
                require(result.returncode == 0, "canonical pre-commit readiness failed")
                require(changed(root) == set(scope), "scope drift after hook pass")
            emit(
                "READY_FOR_FINAL_BYTE_TESTS",
                candidate_sha256=lease["candidate_sha256"],
                identity=ident,
                checkpoint_verified=False,
                tests_verified=False,
                independent_review_complete=False,
            )
        except BaseException as exc:
            emit(
                "STOPPED_RECONCILIATION_REQUIRED",
                error_type=type(exc).__name__,
                message=str(exc),
            )
            raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worktree", type=Path, required=True)
    parser.add_argument("--lease", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    try:
        run_readiness(args.worktree, json.loads(args.lease.read_text()), args.receipt)
    except (
        OSError,
        ValueError,
        KeyError,
        ReadinessError,
        subprocess.CalledProcessError,
    ) as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 1
    print("READY_FOR_FINAL_BYTE_TESTS — no staging or commit performed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
