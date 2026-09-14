#!/usr/bin/env python3
"""List session handovers by the commit that first introduced each record.

The command is intentionally argument-free so AGENTS.md can use one canonical
invocation. It prints the five newest committed records and rejects uncommitted
additions rather than silently ordering records without a durable introduction commit.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

RECORD_PREFIX_EXPRESSION = r"(?:SESSION_HANDOVER_|H[0-9]+_(?:HANDOVER|DELIVERY_))"
RECORD_FILENAME_EXPRESSION = rf"{RECORD_PREFIX_EXPRESSION}[0-9A-Za-z_. -]*\.md"
RECORD_PATTERN = re.compile(rf"^docs/{RECORD_FILENAME_EXPRESSION}$")
NEAR_FAMILY_PATTERN = re.compile(
    rf"^docs/{RECORD_PREFIX_EXPRESSION}[^/]*\.md$", re.DOTALL
)
NEAR_FAMILY_SHAPE = re.compile(
    r"^docs/(?:SESSION[^/]*_HANDOVER_|H[^/_]+_(?:HANDOVER|DELIVERY_))[^/]*\.md$",
    re.DOTALL,
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


def _git_bytes(*args: str) -> bytes:
    """Run Git and return unmodified bytes for filename-safe parsing."""
    completed = subprocess.run(
        ["git", *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        detail = os.fsdecode(completed.stderr).strip() or "no diagnostic returned"
        raise ResolutionError(f"git {' '.join(args)} failed: {detail}")
    return completed.stdout


def _nul_paths(output: bytes) -> set[str]:
    """Return non-empty paths from NUL-delimited Git output.

    Args:
        output: NUL-delimited path bytes.

    Returns:
        Matching path strings without empty terminators.
    """
    return {os.fsdecode(path) for path in output.split(b"\0") if path}


def _candidate_paths(output: bytes) -> set[str]:
    """Filter NUL-delimited Git output to session-handover records.

    Args:
        output: NUL-delimited path bytes.

    Returns:
        Paths belonging to either supported handover family.
    """
    return _validated_candidate_paths(_nul_paths(output))


def _validated_candidate_paths(paths: set[str]) -> set[str]:
    """Return supported records and reject unsafe near-family paths."""
    unsupported = sorted(
        path
        for path in paths
        if _looks_like_near_family(path) and not RECORD_PATTERN.fullmatch(path)
    )
    if unsupported:
        rendered = ", ".join(repr(path) for path in unsupported)
        raise ResolutionError(
            "handover-like filenames use unsupported display characters: " + rendered
        )
    return {path for path in paths if RECORD_PATTERN.fullmatch(path)}


def _looks_like_near_family(path: str) -> bool:
    """Detect family names obscured by Unicode digits or control/format marks."""
    normalized: list[str] = []
    for character in path:
        if unicodedata.category(character) in {"Cc", "Cf", "Cs"}:
            continue
        if character.isdecimal() and not character.isascii():
            normalized.append(str(unicodedata.decimal(character)))
        else:
            normalized.append(character)
    normalized_path = "".join(normalized)
    return any(
        pattern.fullmatch(normalized_path) is not None
        for pattern in (NEAR_FAMILY_PATTERN, NEAR_FAMILY_SHAPE)
    )


def _introduction(path: str) -> Introduction:
    """Resolve the unique entry of a file lineage into the handover family.

    Args:
        path: Repository-relative handover path.

    Returns:
        The record's first durable introduction.

    Raises:
        ResolutionError: History is incomplete, ambiguous, or malformed.
    """
    history = _git_bytes(
        "log",
        "--follow",
        "--find-renames=1%",
        "-z",
        "--format=%H%x00%ct%x00%cI",
        "--",
        path,
    )
    metadata = history.split(b"\0")
    if metadata and metadata[-1] == b"":
        metadata.pop()
    if len(metadata) % 3:
        raise ResolutionError(f"malformed NUL-framed history metadata for {path}")
    entries: list[tuple[str, str, str]] = []
    current_path = path
    for offset in range(0, len(metadata), 3):
        try:
            commit_sha, epoch_text, iso_date = (
                field.decode("ascii") for field in metadata[offset : offset + 3]
            )
        except UnicodeDecodeError as exc:
            raise ResolutionError(f"malformed lineage header for {path}") from exc
        header = (epoch_text, iso_date, commit_sha)
        changes = [
            field
            for field in _git_bytes(
                "diff-tree",
                "--root",
                "-r",
                "-M1%",
                "-C1%",
                "--find-copies-harder",
                "--name-status",
                "-z",
                "--no-commit-id",
                commit_sha,
            ).split(b"\0")
            if field
        ]
        cursor = 0
        copied_entry = False
        while cursor < len(changes):
            try:
                status = changes[cursor].decode("ascii", errors="strict")
            except UnicodeDecodeError as exc:
                raise ResolutionError(f"malformed lineage status for {path}") from exc
            width = 3 if status.startswith(("R", "C")) else 2
            if cursor + width > len(changes):
                raise ResolutionError(f"malformed NUL-framed lineage for {path}")
            names = [os.fsdecode(field) for field in changes[cursor + 1 : cursor + width]]
            cursor += width
            if status == "A":
                if names[0] == current_path and RECORD_PATTERN.fullmatch(current_path):
                    entries.append(header)
            elif status.startswith("C"):
                if names[1] == current_path and RECORD_PATTERN.fullmatch(current_path):
                    entries.append(header)
                    # A copy introduces a distinct record; its source is not an
                    # earlier incarnation of the copied destination.
                    copied_entry = True
                    break
            elif status.startswith("R"):
                if names[1] != current_path:
                    continue
                old_matches = RECORD_PATTERN.fullmatch(names[0]) is not None
                new_matches = RECORD_PATTERN.fullmatch(names[1]) is not None
                if not old_matches and new_matches:
                    entries.append(header)
                current_path = names[0]
        if copied_entry:
            break
    if not entries:
        raise ResolutionError(
            f"no handover-family entry found for {path}; "
            "fetch complete history before retrying"
        )
    if len(entries) != 1:
        raise ResolutionError(
            f"multiple handover-family entries found for {path}; lineage is ambiguous"
        )
    fields = entries[0]
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
    return _validated_candidate_paths(
        {path.relative_to(root).as_posix() for path in docs.iterdir() if path.is_file()}
    )


def _reject_uncommitted_records(root: Path, head_candidates: set[str]) -> None:
    """Fail when HEAD, index, and worktree handover path sets differ.

    Args:
        root: Resolved repository root.
        head_candidates: Matching records committed in ``HEAD``.

    Raises:
        ResolutionError: A matching record is added, removed, renamed, or untracked.
    """
    index_candidates = _candidate_paths(
        _git_bytes("ls-files", "--cached", "-z", "--", "docs")
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
    states.extend(f"worktree deletion: {path}" for path in sorted(worktree_deletions))
    raise ResolutionError(
        "HEAD, index, and worktree handover records differ; reconcile them:\n"
        + "\n".join(states)
    )


def _validate_introduction_topology(introductions: list[Introduction]) -> None:
    """Require comparable introductions and reject backdated descendants.

    Args:
        introductions: Resolved introduction records.

    Raises:
        ResolutionError: Introductions are incomparable or timestamps contradict
            topology.
    """
    parent_graph: dict[str, tuple[str, ...]] = {}
    for line in _git("rev-list", "--parents", "HEAD").splitlines():
        fields = line.split()
        if fields:
            parent_graph[fields[0]] = tuple(fields[1:])

    introduction_shas = {record.commit_sha for record in introductions}
    missing = introduction_shas - parent_graph.keys()
    if missing:
        raise ResolutionError(
            "introduction commits are absent from HEAD history: "
            + ", ".join(sorted(missing))
        )

    ancestors: dict[str, set[str]] = {}
    for commit_sha in introduction_shas:
        seen: set[str] = set()
        pending = list(parent_graph[commit_sha])
        while pending:
            candidate = pending.pop()
            if candidate in seen:
                continue
            seen.add(candidate)
            pending.extend(parent_graph.get(candidate, ()))
        ancestors[commit_sha] = seen

    for index, left in enumerate(introductions):
        for right in introductions[index + 1 :]:
            left_precedes = left.commit_sha in ancestors[right.commit_sha]
            right_precedes = right.commit_sha in ancestors[left.commit_sha]
            if left.commit_sha == right.commit_sha:
                left_precedes = right_precedes = True
            if not left_precedes and not right_precedes:
                raise ResolutionError(
                    f"introduction commits are incomparable: {left.path}, {right.path}"
                )
            if left_precedes and left.epoch > right.epoch:
                raise ResolutionError(
                    f"descendant introduction {right.path} is backdated before "
                    f"ancestor introduction {left.path}"
                )
            if right_precedes and right.epoch > left.epoch:
                raise ResolutionError(
                    f"descendant introduction {left.path} is backdated before "
                    f"ancestor introduction {right.path}"
                )


def _reject_ambiguous_newest(introductions: list[Introduction]) -> None:
    """Reject a tied newest introduction timestamp.

    Equal older timestamps affect display order only. A tie at the maximum
    timestamp would make the startup choice depend on a lexical path rule, so it
    cannot be resolved.

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
            raise ResolutionError(
                f"indeterminate shallow-repository state: {shallow!r}"
            )
        committed = _candidate_paths(
            _git_bytes("ls-tree", "-r", "-z", "--name-only", "HEAD", "--", "docs")
        )
        _reject_uncommitted_records(root, committed)
        if not committed:
            raise ResolutionError("no committed session-handover records found")
        resolved = [_introduction(path) for path in committed]
        _validate_introduction_topology(resolved)
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
