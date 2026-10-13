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
from datetime import datetime
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
SINGLE_PATH_STATUSES = frozenset({"A", "D", "M", "T", "U", "X", "B"})
GIT_STRICT_ISO_PATTERN = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:Z|[+-][0-9]{2}:[0-9]{2})$"
)


class ResolutionError(RuntimeError):
    """Signal that handover ordering cannot be resolved safely."""


@dataclass(frozen=True)
class Introduction:
    """Identify the durable commit that introduced one handover record."""

    epoch: int
    iso_date: str
    commit_sha: str
    path: str


@dataclass(frozen=True)
class CommitChange:
    """Describe one NUL-framed name-status entry from a commit."""

    status: str
    names: tuple[str, ...]


@dataclass(frozen=True)
class CommitDelta:
    """Bind commit metadata to its whole-tree name-status entries."""

    epoch_text: str
    iso_date: str
    commit_sha: str
    changes: tuple[CommitChange, ...]


def _valid_name_status(status: str) -> bool:
    """Return whether status matches this command's name-status grammar."""
    if status in SINGLE_PATH_STATUSES:
        return True
    if len(status) != 4 or status[:1] not in {"C", "R"}:
        return False
    score = status[1:]
    return score.isascii() and score.isdigit() and 1 <= int(score) <= 100


def _object_id_length() -> int:
    """Return the full object-ID length for the active repository."""
    object_format = _git("rev-parse", "--show-object-format").strip()
    try:
        return {"sha1": 40, "sha256": 64}[object_format]
    except KeyError as exc:
        raise ResolutionError(
            f"unsupported Git object format: {object_format!r}"
        ) from exc


def _valid_object_id(value: str, expected_length: int) -> bool:
    """Return whether value is a full lowercase hexadecimal object ID."""
    return len(value) == expected_length and all(
        character in "0123456789abcdef" for character in value
    )


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


def _git_bytes_input(stdin: bytes, *args: str) -> bytes:
    """Run Git with byte input and return unmodified byte output."""
    completed = subprocess.run(
        ["git", *args],
        input=stdin,
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


def _history_headers(paths: set[str]) -> tuple[tuple[str, str, str], ...]:
    """Return commit metadata for every commit touching any requested path."""
    history = _git_bytes(
        "--literal-pathspecs",
        "log",
        "--full-history",
        "-z",
        "--format=%H%x00%ct%x00%cI",
        "HEAD",
        "--",
        *sorted(paths),
    )
    metadata = history.split(b"\0")
    if metadata and metadata[-1] == b"":
        metadata.pop()
    if len(metadata) % 3:
        raise ResolutionError("malformed NUL-framed batched history metadata")
    object_id_length = _object_id_length()
    headers: list[tuple[str, str, str]] = []
    seen_commits: set[str] = set()
    for offset in range(0, len(metadata), 3):
        try:
            commit_sha, epoch_text, iso_date = (
                field.decode("ascii") for field in metadata[offset : offset + 3]
            )
        except UnicodeDecodeError as exc:
            raise ResolutionError("malformed batched lineage header") from exc
        if not _valid_object_id(commit_sha, object_id_length):
            raise ResolutionError("malformed batched lineage commit object ID")
        if (
            not epoch_text
            or len(epoch_text) > 12
            or not epoch_text.isascii()
            or not epoch_text.isdigit()
        ):
            raise ResolutionError("malformed batched lineage epoch")
        if GIT_STRICT_ISO_PATTERN.fullmatch(iso_date) is None:
            raise ResolutionError("malformed batched lineage ISO timestamp")
        try:
            parsed_date = datetime.strptime(iso_date, "%Y-%m-%dT%H:%M:%S%z")
            iso_epoch = int(parsed_date.timestamp())
            epoch = int(epoch_text)
        except (OSError, OverflowError, ValueError) as exc:
            raise ResolutionError("malformed batched lineage ISO timestamp") from exc
        if iso_epoch != epoch:
            raise ResolutionError(
                "malformed batched lineage timestamps: contradictory epoch and ISO"
            )
        if commit_sha in seen_commits:
            raise ResolutionError(f"duplicate batched lineage commit: {commit_sha}")
        seen_commits.add(commit_sha)
        headers.append((commit_sha, epoch_text, iso_date))
    return tuple(headers)


def _commit_deltas(
    headers: tuple[tuple[str, str, str], ...],
) -> dict[str, CommitDelta]:
    """Resolve whole-tree changes for many commits in one Git subprocess."""
    if not headers:
        return {}
    stdin = b"".join(f"{sha}\n".encode("ascii") for sha, _, _ in headers)
    output = _git_bytes_input(
        stdin,
        "diff-tree",
        "--stdin",
        "--root",
        "-r",
        "-M1%",
        "-C1%",
        "--find-copies-harder",
        "--name-status",
        "-z",
        "--pretty=format:%x00%H%x00",
    )
    header_by_sha = {sha: (epoch, iso) for sha, epoch, iso in headers}
    object_id_length = _object_id_length()
    if any(
        not _valid_object_id(commit_sha, object_id_length)
        for commit_sha in header_by_sha
    ):
        raise ResolutionError("malformed batched lineage commit object ID")
    tokens = output.split(b"\0")
    deltas: dict[str, CommitDelta] = {}
    cursor = 0
    while cursor < len(tokens):
        if tokens[cursor] != b"":
            raise ResolutionError("malformed NUL-framed batched lineage")
        while cursor < len(tokens) and tokens[cursor] == b"":
            cursor += 1
        if cursor == len(tokens):
            break
        try:
            commit_sha = tokens[cursor].decode("ascii")
        except (IndexError, UnicodeDecodeError) as exc:
            raise ResolutionError("malformed batched lineage commit header") from exc
        cursor += 1
        changes: list[CommitChange] = []
        while cursor < len(tokens) and tokens[cursor] != b"":
            status_field = tokens[cursor]
            if status_field.startswith(b"\n"):
                status_field = status_field[1:]
            try:
                status = status_field.decode("ascii", errors="strict")
            except UnicodeDecodeError as exc:
                raise ResolutionError("malformed batched lineage status") from exc
            if not _valid_name_status(status):
                raise ResolutionError(f"malformed batched lineage status: {status!r}")
            width = 3 if status.startswith(("R", "C")) else 2
            if not status or cursor + width > len(tokens):
                raise ResolutionError("malformed NUL-framed batched lineage")
            name_fields = tokens[cursor + 1 : cursor + width]
            if any(not field for field in name_fields):
                raise ResolutionError("malformed NUL-framed batched lineage")
            names = tuple(os.fsdecode(field) for field in name_fields)
            changes.append(CommitChange(status, names))
            cursor += width
        if commit_sha not in header_by_sha or commit_sha in deltas:
            raise ResolutionError(f"unexpected batched lineage commit: {commit_sha}")
        epoch_text, iso_date = header_by_sha[commit_sha]
        deltas[commit_sha] = CommitDelta(
            epoch_text, iso_date, commit_sha, tuple(changes)
        )
    missing_commits = header_by_sha.keys() - deltas.keys()
    parent_counts: dict[str, int] = {}
    if missing_commits:
        topology = _git(
            "rev-list",
            "--parents",
            "--no-walk=unsorted",
            *sorted(missing_commits),
        )
        for line in topology.splitlines():
            fields = line.split()
            if not fields or fields[0] in parent_counts:
                raise ResolutionError("malformed missing-commit topology")
            subject, *parents = fields
            if (
                not _valid_object_id(subject, object_id_length)
                or any(
                    not _valid_object_id(parent, object_id_length) for parent in parents
                )
                or len(set(parents)) != len(parents)
            ):
                raise ResolutionError("malformed missing-commit topology")
            parent_counts[subject] = len(parents)
        if parent_counts.keys() != missing_commits:
            raise ResolutionError("incomplete missing-commit topology")
    for commit_sha in missing_commits:
        # ``diff-tree`` emits no record for a merge without ``-m``. Prove the
        # topology before representing that known omission as an empty delta.
        if parent_counts[commit_sha] < 2:
            raise ResolutionError(
                f"missing non-merge batched lineage commit: {commit_sha}"
            )
        epoch_text, iso_date = header_by_sha[commit_sha]
        deltas[commit_sha] = CommitDelta(epoch_text, iso_date, commit_sha, ())
    return deltas


def _lineage_entries(
    path: str,
    deltas: list[CommitDelta],
    queried_paths: set[str],
) -> tuple[list[tuple[str, str, str]], set[str]]:
    """Trace one path through already-batched whole-tree commit changes."""
    entries: list[tuple[str, str, str]] = []
    missing_paths: set[str] = set()
    current_path = path
    for delta in deltas:
        copied_entry = False
        for change in delta.changes:
            names = change.names
            header = (delta.epoch_text, delta.iso_date, delta.commit_sha)
            if change.status == "A":
                if names[0] == current_path and RECORD_PATTERN.fullmatch(current_path):
                    entries.append(header)
            elif change.status.startswith("C"):
                if names[1] == current_path and RECORD_PATTERN.fullmatch(current_path):
                    entries.append(header)
                    copied_entry = True
                    break
            elif change.status.startswith("R"):
                if names[1] != current_path:
                    continue
                old_matches = RECORD_PATTERN.fullmatch(names[0]) is not None
                new_matches = RECORD_PATTERN.fullmatch(names[1]) is not None
                if not old_matches and new_matches:
                    entries.append(header)
                current_path = names[0]
                if current_path not in queried_paths:
                    missing_paths.add(current_path)
        if copied_entry:
            break
    return entries, missing_paths


def _introductions(paths: set[str]) -> list[Introduction]:
    """Resolve all handover introductions with batched history traversal."""
    commit_order = _git("rev-list", "HEAD").splitlines()
    queried_paths: set[str] = set()
    pending_paths = set(paths)
    deltas_by_sha: dict[str, CommitDelta] = {}
    while pending_paths:
        batch = pending_paths - queried_paths
        if not batch:
            break
        headers = _history_headers(batch)
        new_headers = tuple(
            header for header in headers if header[0] not in deltas_by_sha
        )
        deltas_by_sha.update(_commit_deltas(new_headers))
        queried_paths.update(batch)
        ordered = [deltas_by_sha[sha] for sha in commit_order if sha in deltas_by_sha]
        pending_paths = set()
        for path in paths:
            _, missing = _lineage_entries(path, ordered, queried_paths)
            pending_paths.update(missing - queried_paths)

    ordered = [deltas_by_sha[sha] for sha in commit_order if sha in deltas_by_sha]
    introductions: list[Introduction] = []
    for path in paths:
        entries, _ = _lineage_entries(path, ordered, queried_paths)
        if not entries:
            raise ResolutionError(
                f"no handover-family entry found for {path}; "
                "fetch complete history before retrying"
            )
        if len(entries) != 1:
            raise ResolutionError(
                f"multiple handover-family entries found for {path}; lineage is ambiguous"
            )
        epoch_text, iso_date, commit_sha = entries[0]
        try:
            epoch = int(epoch_text)
        except ValueError as exc:
            raise ResolutionError(
                f"non-numeric introduction timestamp for {path}: {epoch_text!r}"
            ) from exc
        introductions.append(Introduction(epoch, iso_date, commit_sha, path))
    return introductions


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
        resolved = _introductions(committed)
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
