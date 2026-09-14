#!/usr/bin/env python3
"""List session handovers by the commit that first introduced each record.

The command is intentionally argument-free so AGENTS.md can use one canonical invocation.
It prints the five newest committed records and rejects uncommitted additions rather than
silently ordering records that have no durable introduction commit.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

RECORD_PATTERN = re.compile(
    r"^docs/(?:SESSION_HANDOVER_[^/]+|H\d+_(?:HANDOVER[^/]*|DELIVERY_[^/]*))\.md$"
)
DISPLAY_LIMIT = 5


class ResolutionError(RuntimeError):
    """Signal that handover ordering cannot be resolved safely."""


@dataclass(frozen=True)
class Introduction:
    """Identify the durable commit that introduced one handover record."""

    epoch: int
    iso_date: str
    commit_sha: str
    path: str


def _git(*args: str) -> str:
    """Run Git in the active worktree and return stdout.

    Args:
        *args: Git subcommand and arguments.

    Returns:
        The command's decoded standard output.

    Raises:
        ResolutionError: The Git command fails.
    """
    completed = subprocess.run(
        ["git", *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or "no diagnostic returned"
        raise ResolutionError(f"git {' '.join(args)} failed: {detail}")
    return completed.stdout


def _nul_paths(output: str) -> set[str]:
    """Return non-empty paths from NUL-delimited Git output.

    Args:
        output: NUL-delimited path text.

    Returns:
        Matching path strings without empty terminators.
    """
    return {path for path in output.split("\0") if path}


def _candidate_paths(output: str) -> set[str]:
    """Filter NUL-delimited Git output to session-handover records.

    Args:
        output: NUL-delimited path text.

    Returns:
        Paths belonging to either supported handover family.
    """
    return {path for path in _nul_paths(output) if RECORD_PATTERN.fullmatch(path)}


def _introduction(path: str) -> Introduction:
    """Resolve the oldest add commit for a committed record.

    Args:
        path: Repository-relative handover path.

    Returns:
        The record's first durable introduction.

    Raises:
        ResolutionError: History is incomplete or the add record is malformed.
    """
    history = _git(
        "log",
        "--follow",
        "--diff-filter=A",
        "--format=%ct%x09%cI%x09%H",
        "--",
        path,
    )
    additions = [line for line in history.splitlines() if line]
    if not additions:
        raise ResolutionError(
            f"no introduction commit found for {path}; fetch complete history before retrying"
        )
    fields = additions[-1].split("\t")
    if len(fields) != 3:
        raise ResolutionError(f"malformed introduction record for {path}: {additions[-1]!r}")
    try:
        epoch = int(fields[0])
    except ValueError as exc:
        raise ResolutionError(
            f"non-numeric introduction timestamp for {path}: {fields[0]!r}"
        ) from exc
    return Introduction(epoch, fields[1], fields[2], path)


def _reject_uncommitted_records() -> None:
    """Fail when a staged or untracked handover lacks a durable introduction.

    Raises:
        ResolutionError: At least one new handover is staged or untracked.
    """
    staged = _candidate_paths(
        _git("diff", "--cached", "--name-only", "--diff-filter=A", "-z", "--", "docs")
    )
    untracked = _candidate_paths(
        _git("ls-files", "--others", "--exclude-standard", "-z", "--", "docs")
    )
    if not staged and not untracked:
        return
    states = [f"staged: {path}" for path in sorted(staged)]
    states.extend(f"untracked: {path}" for path in sorted(untracked))
    raise ResolutionError(
        "uncommitted handover records have no introduction order; commit or remove them:\n"
        + "\n".join(states)
    )


def main() -> int:
    """Print the newest committed handovers or a fail-loud diagnostic.

    Returns:
        Zero on success; two when deterministic resolution is unavailable.
    """
    try:
        root_text = _git("rev-parse", "--show-toplevel").strip()
        if not root_text:
            raise ResolutionError("Git returned an empty worktree root")
        root = Path(root_text).resolve()
        if Path.cwd().resolve() != root:
            raise ResolutionError(f"run from the repository root: {root}")
        _reject_uncommitted_records()
        committed = _candidate_paths(
            _git("ls-tree", "-r", "-z", "--name-only", "HEAD", "--", "docs")
        )
        if not committed:
            raise ResolutionError("no committed session-handover records found")
        introductions = sorted(
            (_introduction(path) for path in committed),
            key=lambda record: (-record.epoch, record.path),
        )
    except ResolutionError as exc:
        print(f"handover resolution failed: {exc}", file=sys.stderr)
        return 2

    for record in introductions[:DISPLAY_LIMIT]:
        print(f"{record.epoch}\t{record.iso_date}\t{record.commit_sha}\t{record.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
