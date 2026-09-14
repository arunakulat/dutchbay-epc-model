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

RECORD_FILENAME_EXPRESSION = (
    r"(?:SESSION_HANDOVER_[0-9A-Za-z_.-]+|"
    r"H\d+_(?:HANDOVER[0-9A-Za-z_.-]*|DELIVERY_[0-9A-Za-z_.-]+))\.md"
)
RECORD_PATTERN = re.compile(rf"^docs/{RECORD_FILENAME_EXPRESSION}$")
PROSE_RECORD_PATTERN = re.compile(
    rf"(?<![0-9A-Za-z_./-])(?:docs/)?{RECORD_FILENAME_EXPRESSION}"
    rf"(?![0-9A-Za-z_.-])"
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
    """Resolve the unique add commit for a committed record.

    Args:
        path: Repository-relative handover path.

    Returns:
        The record's first durable introduction.

    Raises:
        ResolutionError: History is incomplete, ambiguous, or malformed.
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
    if len(additions) != 1:
        raise ResolutionError(
            f"multiple add events found for {path}; delete/re-add history is ambiguous"
        )
    fields = additions[0].split("\t")
    if len(fields) != 3:
        raise ResolutionError(
            f"malformed introduction record for {path}: {additions[0]!r}"
        )
    try:
        epoch = int(fields[0])
    except ValueError as exc:
        raise ResolutionError(
            f"non-numeric introduction timestamp for {path}: {fields[0]!r}"
        ) from exc
    return Introduction(epoch, fields[1], fields[2], path)


def _worktree_candidates(root: Path) -> set[str]:
    """Return matching records physically present in the worktree.

    This filesystem view deliberately includes ignored files, which Git's ordinary
    untracked listing omits.

    Args:
        root: Resolved repository root.

    Returns:
        Matching repository-relative paths currently present on disk.
    """
    docs = root / "docs"
    if not docs.is_dir():
        return set()
    return {
        path.relative_to(root).as_posix()
        for path in docs.iterdir()
        if path.is_file()
        and RECORD_PATTERN.fullmatch(path.relative_to(root).as_posix())
    }


def _reject_uncommitted_records(root: Path, head_candidates: set[str]) -> None:
    """Fail when HEAD, index, and worktree handover path sets differ.

    Args:
        root: Resolved repository root.
        head_candidates: Matching records committed in ``HEAD``.

    Raises:
        ResolutionError: A matching record is added, removed, renamed, or untracked.
    """
    index_candidates = _candidate_paths(
        _git("ls-files", "--cached", "-z", "--", "docs")
    )
    worktree_candidates = _worktree_candidates(root)
    staged_additions = index_candidates - head_candidates
    staged_deletions = head_candidates - index_candidates
    worktree_additions = worktree_candidates - index_candidates
    worktree_deletions = index_candidates - worktree_candidates
    if not any(
        (staged_additions, staged_deletions, worktree_additions, worktree_deletions)
    ):
        return
    states = [f"staged addition: {path}" for path in sorted(staged_additions)]
    states.extend(f"staged deletion: {path}" for path in sorted(staged_deletions))
    states.extend(
        f"worktree-only (untracked or ignored): {path}"
        for path in sorted(worktree_additions)
    )
    states.extend(
        f"worktree deletion: {path}" for path in sorted(worktree_deletions)
    )
    raise ResolutionError(
        "HEAD, index, and worktree handover records differ; reconcile them:\n"
        + "\n".join(states)
    )


def _is_ancestor(ancestor_sha: str, descendant_sha: str) -> bool:
    """Report whether one introduction commit is an ancestor of another.

    Args:
        ancestor_sha: Candidate ancestor commit.
        descendant_sha: Candidate descendant commit.

    Returns:
        ``True`` only when Git proves the ancestry relation.

    Raises:
        ResolutionError: Git cannot determine the relation.
    """
    completed = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor_sha, descendant_sha],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed.returncode == 0:
        return True
    if completed.returncode == 1:
        return False
    detail = completed.stderr.strip() or "no diagnostic returned"
    raise ResolutionError(
        f"git could not compare introduction commits {ancestor_sha} and "
        f"{descendant_sha}: {detail}"
    )


def _reject_backdated_descendants(introductions: list[Introduction]) -> None:
    """Reject descendant introductions timestamped before an ancestor introduction.

    Args:
        introductions: Resolved introduction records.

    Raises:
        ResolutionError: Commit topology and introduction timestamps disagree.
    """
    for ancestor in introductions:
        for descendant in introductions:
            if ancestor.epoch <= descendant.epoch:
                continue
            if _is_ancestor(ancestor.commit_sha, descendant.commit_sha):
                raise ResolutionError(
                    f"descendant introduction {descendant.path} is backdated before "
                    f"ancestor introduction {ancestor.path}"
                )


def _reject_ambiguous_newest(introductions: list[Introduction]) -> None:
    """Reject a tied newest introduction timestamp.

    Equal older timestamps affect display order only. A tie at the maximum timestamp
    would make the startup choice depend on a lexical path rule, so it cannot be resolved.

    Args:
        introductions: Resolved introduction records.

    Raises:
        ResolutionError: More than one record shares the newest introduction epoch.
    """
    newest_epoch = max(record.epoch for record in introductions)
    newest = sorted(
        record.path for record in introductions if record.epoch == newest_epoch
    )
    if len(newest) > 1:
        raise ResolutionError(
            f"newest introduction timestamp {newest_epoch} is shared by: "
            + ", ".join(newest)
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
        shallow = _git("rev-parse", "--is-shallow-repository").strip()
        if shallow != "false":
            if shallow == "true":
                raise ResolutionError(
                    "repository history is shallow; fetch complete history"
                )
            raise ResolutionError(f"indeterminate shallow-repository state: {shallow!r}")
        committed = _candidate_paths(
            _git("ls-tree", "-r", "-z", "--name-only", "HEAD", "--", "docs")
        )
        _reject_uncommitted_records(root, committed)
        if not committed:
            raise ResolutionError("no committed session-handover records found")
        resolved = [_introduction(path) for path in committed]
        _reject_backdated_descendants(resolved)
        _reject_ambiguous_newest(resolved)
        introductions = sorted(
            resolved,
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
