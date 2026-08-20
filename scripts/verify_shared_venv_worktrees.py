"""Verify one governed environment against two distinct clean worktrees.

Configuration is environment-only so paths cannot be silently substituted by
positional defaults:

``DUTCHBAY_VENV``
    Absolute path to the persistent Python 3.12 environment.
``DUTCHBAY_WORKTREE_A`` and ``DUTCHBAY_WORKTREE_B``
    Absolute, real paths to two worktrees from the same DutchBay repository.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dutchbay_environment import (  # noqa: E402
    EnvironmentContractError,
    resolve_environment,
)

RECEIPT_SCHEMA = "dutchbay.shared_venv_two_worktree_receipt.v1"
WORKTREE_VARIABLES = ("DUTCHBAY_WORKTREE_A", "DUTCHBAY_WORKTREE_B")
FOCUSED_TESTS = (
    "tests/lint/test_dutchbay_environment_contract.py",
    "tests/lint/test_codex_local_environment.py",
)


class WorktreeVerificationError(RuntimeError):
    """Raised when the two-worktree proof cannot be trusted."""


@dataclass(frozen=True)
class WorktreeReceipt:
    """Concise proof facts for one validated worktree."""

    path: str
    branch: str
    head_sha: str
    git_common_dir: str
    python_version: str
    python_prefix: str
    import_path: str
    bootstrap_status: str
    focused_tests_status: str


def verification_paths(environ: Mapping[str, str]) -> tuple[Path, Path]:
    """Resolve two unique absolute real paths without accepting substitution."""

    resolved: list[Path] = []
    for variable in WORKTREE_VARIABLES:
        raw = environ.get(variable)
        if raw is None or not raw.strip():
            raise WorktreeVerificationError(f"{variable} must be set.")
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            raise WorktreeVerificationError(f"{variable} must be an absolute path.")
        try:
            real = candidate.resolve(strict=True)
        except OSError as exc:
            raise WorktreeVerificationError(
                f"{variable} is unavailable: {candidate}: {exc}"
            ) from exc
        if candidate.absolute() != real:
            raise WorktreeVerificationError(
                f"{variable} must name the real worktree path, not a symlink: {candidate}."
            )
        resolved.append(real)
    if resolved[0] == resolved[1]:
        raise WorktreeVerificationError("The two worktree paths must be distinct.")
    return resolved[0], resolved[1]


def _run(
    command: Sequence[str],
    *,
    cwd: Path,
    environ: Mapping[str, str] | None = None,
    timeout_seconds: int = 180,
) -> str:
    """Run one bounded proof command and return its captured standard output."""

    try:
        completed = subprocess.run(
            list(command),
            cwd=cwd,
            env=None if environ is None else dict(environ),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise WorktreeVerificationError(
            f"Command could not complete in {cwd}: {command[0]}: {exc}"
        ) from exc
    if completed.returncode != 0:
        raw_detail = completed.stderr.strip() or completed.stdout.strip()
        detail = raw_detail[-1200:] if raw_detail else "no diagnostic"
        raise WorktreeVerificationError(
            f"Command failed in {cwd}: {' '.join(command)}: {detail}"
        )
    return completed.stdout.strip()


def _git(worktree: Path, *arguments: str) -> str:
    """Run one read-only Git query in a candidate worktree."""

    return _run(("git", *arguments), cwd=worktree)


def _real_git_path(worktree: Path, raw: str) -> Path:
    """Resolve a Git-reported path relative to its worktree."""

    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate.resolve(strict=True)
    return (worktree / candidate).resolve(strict=True)


def _proof_environment(worktree: Path, venv: Path) -> dict[str, str]:
    """Return an isolated subprocess environment bound to one worktree."""

    environ = dict(os.environ)
    environ.pop("PYTHONHOME", None)
    environ.update(
        {
            "DUTCHBAY_FLOW_RULESET_CSV": str(
                worktree / "go_with_the_flow_rules_v3_0_clean.csv"
            ),
            "DUTCHBAY_REPO_ROOT": str(worktree),
            "DUTCHBAY_VENV": str(venv),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": str(worktree),
        }
    )
    return environ


def inspect_worktree(worktree: Path, venv: Path) -> WorktreeReceipt:
    """Validate repository identity, runtime binding, bootstrap, and tests."""

    top_level = _real_git_path(worktree, _git(worktree, "rev-parse", "--show-toplevel"))
    if top_level != worktree:
        raise WorktreeVerificationError(
            f"Git top-level substitution detected: requested {worktree}, got {top_level}."
        )
    if _git(worktree, "status", "--porcelain=v1", "--untracked-files=all"):
        raise WorktreeVerificationError(f"Worktree must be clean: {worktree}.")
    if (worktree / ".venv").exists():
        raise WorktreeVerificationError(
            f"Worktree-local .venv is prohibited during shared proof: {worktree / '.venv'}."
        )
    branch = _git(worktree, "branch", "--show-current")
    if not branch:
        raise WorktreeVerificationError(
            f"Worktree must be on a named branch: {worktree}."
        )
    head_sha = _git(worktree, "rev-parse", "HEAD")
    common_dir = _real_git_path(
        worktree, _git(worktree, "rev-parse", "--git-common-dir")
    )

    proof_environ = _proof_environment(worktree, venv)
    validator_output = _run(
        (str(venv / "bin" / "python"), str(worktree / "dutchbay_environment.py")),
        cwd=worktree,
        environ=proof_environ,
    )
    try:
        validator = json.loads(validator_output)
    except json.JSONDecodeError as exc:
        raise WorktreeVerificationError(
            f"Environment validator returned invalid JSON in {worktree}."
        ) from exc
    if validator.get("status") != "PASS":
        raise WorktreeVerificationError(
            f"Environment validator did not pass in {worktree}."
        )
    if validator.get("selection_source") != "DUTCHBAY_VENV":
        raise WorktreeVerificationError(
            f"Portable fallback is not valid two-worktree proof: {worktree}."
        )
    if Path(str(validator.get("venv_path"))).resolve(strict=True) != venv:
        raise WorktreeVerificationError(f"Python prefix drift detected in {worktree}.")
    import_path = Path(str(validator.get("import_path"))).resolve(strict=True)
    try:
        import_path.relative_to(worktree)
    except ValueError as exc:
        raise WorktreeVerificationError(
            f"DutchBay import escaped the active worktree: {import_path}."
        ) from exc
    if validator.get("editable_project_install") is not False or validator.get(
        "foreign_checkout_paths"
    ):
        raise WorktreeVerificationError(
            f"Shared environment is contaminated while testing {worktree}."
        )

    _run(
        (
            str(venv / "bin" / "python"),
            str(worktree / "dutchbay_bootstrap_rules.py"),
        ),
        cwd=worktree,
        environ=proof_environ,
    )
    _run(
        (
            str(venv / "bin" / "python"),
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            *FOCUSED_TESTS,
            "-q",
        ),
        cwd=worktree,
        environ=proof_environ,
    )
    return WorktreeReceipt(
        path=str(worktree),
        branch=branch,
        head_sha=head_sha,
        git_common_dir=str(common_dir),
        python_version=str(validator["python_version"]),
        python_prefix=str(validator["python_prefix"]),
        import_path=str(import_path),
        bootstrap_status="PASS",
        focused_tests_status="PASS",
    )


def verify(environ: Mapping[str, str]) -> dict[str, object]:
    """Run the governed two-worktree proof and return its concise receipt."""

    if not environ.get("DUTCHBAY_VENV", "").strip():
        raise WorktreeVerificationError(
            "DUTCHBAY_VENV must be configured; portable fallback is not proof."
        )
    worktree_a, worktree_b = verification_paths(environ)
    try:
        selected = resolve_environment(ROOT, environ=environ)
    except EnvironmentContractError as exc:
        raise WorktreeVerificationError(str(exc)) from exc
    if selected.source != "DUTCHBAY_VENV":
        raise WorktreeVerificationError(
            "DUTCHBAY_VENV must select the proof environment explicitly."
        )
    if selected.path.is_symlink():
        raise WorktreeVerificationError(
            f"Configured environment must not be a symlink: {selected.path}."
        )
    try:
        venv = selected.path.resolve(strict=True)
    except OSError as exc:
        raise WorktreeVerificationError(
            f"Configured environment is unavailable: {selected.path}: {exc}"
        ) from exc
    for worktree in (worktree_a, worktree_b):
        if venv == worktree or venv.is_relative_to(worktree):
            raise WorktreeVerificationError(
                f"Shared environment must be outside both worktrees: {venv}."
            )

    receipts = (
        inspect_worktree(worktree_a, venv),
        inspect_worktree(worktree_b, venv),
    )
    if receipts[0].git_common_dir != receipts[1].git_common_dir:
        raise WorktreeVerificationError(
            "The two paths are not worktrees of the same Git repository."
        )
    return {
        "schema": RECEIPT_SCHEMA,
        "status": "PASS",
        "venv_path": str(venv),
        "worktrees": [asdict(receipt) for receipt in receipts],
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Emit one JSON proof receipt or a concise JSON failure."""

    selected_argv = sys.argv[1:] if argv is None else list(argv)
    if selected_argv:
        print(
            json.dumps(
                {
                    "schema": RECEIPT_SCHEMA,
                    "status": "FAIL",
                    "error": "Configuration is accepted through environment variables only.",
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    try:
        receipt = verify(os.environ)
    except WorktreeVerificationError as exc:
        print(
            json.dumps(
                {"schema": RECEIPT_SCHEMA, "status": "FAIL", "error": str(exc)},
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
