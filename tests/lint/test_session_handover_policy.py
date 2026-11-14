"""CI and governance policy tests for session handover records and the lineage resolver (#1409, PERSIST-01)."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
RESOLVER_SCRIPT = REPO_ROOT / "scripts/list_session_handover_records.py"

_STARTUP_RECORD_PATTERN = re.compile(r"startup[- ]record", re.IGNORECASE)
_CARRIED_STATE_PATTERNS = (
    re.compile(r"carried[- ]forward", re.IGNORECASE),
    re.compile(r"carries\s+forward", re.IGNORECASE),
    re.compile(r"successor", re.IGNORECASE),
    re.compile(r"predecessor", re.IGNORECASE),
)


def verify_handover_record_declaration(
    content: str, filename: str = "record.md"
) -> None:
    """Verify that a session handover record declares its startup record and carried-forward state.

    Args:
        content: Markdown text of the handover record.
        filename: Name of the record file for error reporting.

    Raises:
        ValueError: If the record fails to declare its startup record or carried-forward lineage.
    """
    has_startup = bool(_STARTUP_RECORD_PATTERN.search(content))
    has_lineage = any(pattern.search(content) for pattern in _CARRIED_STATE_PATTERNS)
    if not (has_startup and has_lineage):
        raise ValueError(
            f"Handover record {filename!r} missing required PERSIST-01 startup-record and "
            f"carried-forward state declaration (has_startup={has_startup}, has_lineage={has_lineage})."
        )


def format_malformed_iso_refusal(rejected_field: str, git_version: str) -> str:
    """Format refusal message naming the rejected field and observed git version.

    Args:
        rejected_field: The invalid ISO timestamp string that was rejected.
        git_version: The observed git version string.

    Returns:
        Structured refusal message.
    """
    if not rejected_field:
        raise ValueError("rejected_field must not be empty")
    if not git_version:
        raise ValueError("git_version must not be empty")
    return (
        f"malformed batched lineage ISO timestamp: rejected field {rejected_field!r} "
        f"under observed {git_version}"
    )


def _git(cwd: Path, *args: str) -> str:
    """Run git in cwd and return stripped stdout."""
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def test_handover_resolver_live_history_execution() -> None:
    """Item 1: Run the handover resolver against this repository's own full history in CI."""
    result = subprocess.run(
        [sys.executable, str(RESOLVER_SCRIPT)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Resolver failed on live history:\n{result.stderr}"
    lines = result.stdout.strip().splitlines()
    assert lines, "Resolver produced no output on repository history."

    for line in lines:
        parts = line.split("\t")
        assert len(parts) == 4, f"Malformed resolver output line: {line!r}"
        epoch_str, iso_date, commit_sha, path = parts
        assert epoch_str.isdigit(), f"Invalid epoch: {epoch_str!r}"
        assert re.match(
            r"^[0-9a-f]{40}$", commit_sha
        ), f"Invalid commit SHA: {commit_sha!r}"
        assert path.startswith("docs/"), f"Path outside docs/: {path!r}"
        assert (REPO_ROOT / path).is_file(), f"Resolved path does not exist: {path!r}"


def test_committed_handover_records_declare_startup_and_carried_forward_state() -> None:
    """Item 3 (Positive): All active post-v15.6.1 session handover records declare startup and carried-forward state."""
    docs_dir = REPO_ROOT / "docs"
    # Check all active handover records from v15.6.1 (2026-10-05) onwards
    recent_handover_files = sorted(docs_dir.glob("SESSION_HANDOVER_2026-1[0-9]*.md"))
    assert recent_handover_files, "No active SESSION_HANDOVER files found in docs/."

    for path in recent_handover_files:
        content = path.read_text(encoding="utf-8")
        verify_handover_record_declaration(content, filename=path.name)

    # Also verify that every record returned by the resolver satisfies the fence
    resolver_result = subprocess.run(
        [sys.executable, str(RESOLVER_SCRIPT)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    for line in resolver_result.stdout.strip().splitlines():
        rel_path = line.split("\t")[3]
        record_content = (REPO_ROOT / rel_path).read_text(encoding="utf-8")
        verify_handover_record_declaration(record_content, filename=rel_path)


def test_handover_record_omitting_declaration_fails_fence() -> None:
    """Item 3 (Negative Control): A handover record omitting startup or carried-forward state fails closed."""
    # Omit both
    plain_content = (
        "# Session Handover — Undated\n\n"
        "## Summary\n\n"
        "This document describes local developer notes and performance improvements.\n"
        "No continuity, predecessor, or baseline information is provided here.\n"
    )
    with pytest.raises(ValueError, match="missing required PERSIST-01 startup-record"):
        verify_handover_record_declaration(plain_content, filename="OMITTED_ALL.md")

    # Has startup record only, lacks carried-forward / successor lineage
    startup_only = (
        "# Session Handover\n\n"
        "This is the current repository startup-record.\n"
        "No previous sessions or baseline tasks are mentioned.\n"
    )
    with pytest.raises(ValueError, match="missing required PERSIST-01 startup-record"):
        verify_handover_record_declaration(startup_only, filename="STARTUP_ONLY.md")

    # Has successor lineage only, lacks startup-record
    lineage_only = (
        "# Session Handover\n\n"
        "This document is a successor to the previous work.\n"
        "It carries forward the open tickets.\n"
    )
    with pytest.raises(ValueError, match="missing required PERSIST-01 startup-record"):
        verify_handover_record_declaration(lineage_only, filename="LINEAGE_ONLY.md")


def test_git_version_recorded_and_refusal_details() -> None:
    """Item 2 (Positive): Verify git version is discoverable and format lineage timestamp refusal."""
    git_version_str = _git(REPO_ROOT, "--version")
    assert re.search(r"git\s+version\s+\d+\.\d+", git_version_str, re.IGNORECASE)

    bad_field = "2026-13-45T99:99:99Z"
    refusal_msg = format_malformed_iso_refusal(bad_field, git_version_str)
    assert bad_field in refusal_msg
    assert git_version_str in refusal_msg
    assert "malformed batched lineage ISO timestamp" in refusal_msg


def test_malformed_iso_refusal_negative_controls() -> None:
    """Item 2 (Negative Control): Refusal formatting rejects missing field or git version."""
    with pytest.raises(ValueError, match="rejected_field must not be empty"):
        format_malformed_iso_refusal("", "git version 2.45.0")

    with pytest.raises(ValueError, match="git_version must not be empty"):
        format_malformed_iso_refusal("2026-13-45T99:99:99Z", "")


def test_handover_resolver_refuses_shallow_history(tmp_path: Path) -> None:
    """Item 1 (Negative Control A): Handover resolver refuses shallow repository history."""
    origin = tmp_path / "origin"
    origin.mkdir()
    _git(origin, "init")
    _git(origin, "config", "user.name", "Test Author")
    _git(origin, "config", "user.email", "test@example.invalid")

    docs = origin / "docs"
    docs.mkdir()
    file1 = docs / "SESSION_HANDOVER_2026-01-01.md"
    file1.write_text(
        "handover 1 with startup record and carried-forward state\n", encoding="utf-8"
    )
    _git(origin, "add", ".")
    _git(origin, "commit", "-m", "commit 1")

    # Create shallow clone
    shallow = tmp_path / "shallow"
    subprocess.run(
        ["git", "clone", "--depth", "1", f"file://{origin}", str(shallow)],
        capture_output=True,
        check=True,
    )

    result = subprocess.run(
        [sys.executable, str(RESOLVER_SCRIPT)],
        cwd=shallow,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert (
        "shallow" in result.stderr.lower() or "resolutionerror" in result.stderr.lower()
    )


def test_handover_resolver_refuses_uncommitted_near_family_record(
    tmp_path: Path,
) -> None:
    """Item 1 (Negative Control B): Handover resolver refuses uncommitted near-family additions."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.name", "Test Author")
    _git(repo, "config", "user.email", "test@example.invalid")

    docs = repo / "docs"
    docs.mkdir()
    committed = docs / "SESSION_HANDOVER_2026-01-01.md"
    committed.write_text("committed handover with startup record\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial commit")

    # Add uncommitted near-family file
    uncommitted = docs / "SESSION_HANDOVER_2026-01-02.md"
    uncommitted.write_text("uncommitted handover without commit\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(RESOLVER_SCRIPT)],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    stderr_lower = result.stderr.lower()
    assert (
        "differ" in stderr_lower
        or "worktree-only" in stderr_lower
        or "uncommitted" in stderr_lower
        or "resolutionerror" in stderr_lower
    )
