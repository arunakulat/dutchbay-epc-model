"""Helpers for machine-resolvable finding anchors and typed dependencies."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

AUDITED_COMMIT = "7e99f34d75b9c3d44a5c5b260cedbe403d2f79e8"
DEPENDENCY_KINDS = {
    "implementation",
    "validation",
    "transaction_evidence",
    "monitoring",
    "cross_finding",
}
DEPENDENCY_STATUSES = {
    "required_not_started",
    "in_progress",
    "completed",
    "unavailable",
    "not_applicable",
}

_BRACE_PATH = re.compile(r"([A-Za-z0-9_./-]+/)\{([^{}]+)\}")
_PATH_TOKEN = re.compile(
    r"(?<![A-Za-z0-9_.-])"
    r"((?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+"
    r"\.(?:py|yaml|yml|json|toml|ini|md|j2)|Makefile)"
)


def _expand_braced_paths(text: str) -> str:
    """Expand compact ``prefix/{a.py,b.py}`` anchor notation."""
    previous = None
    expanded = text
    while previous != expanded:
        previous = expanded

        def replacement(match: re.Match[str]) -> str:
            prefix, body = match.groups()
            return "; ".join(prefix + item.strip() for item in body.split(","))

        expanded = _BRACE_PATH.sub(replacement, expanded)
    return expanded


def _repo_file_index(repo_root: Path) -> tuple[set[str], dict[str, list[str]]]:
    files: set[str] = set()
    by_basename: dict[str, list[str]] = {}
    ignored_parts = {".git", ".venv", ".mypy_cache", ".pytest_cache", "__pycache__"}
    for path in repo_root.rglob("*"):
        if not path.is_file() or any(part in ignored_parts for part in path.parts):
            continue
        relative = path.relative_to(repo_root).as_posix()
        files.add(relative)
        by_basename.setdefault(path.name, []).append(relative)
    return files, by_basename


def _resolve_path(
    token: str, files: set[str], by_basename: dict[str, list[str]]
) -> str:
    if token in files:
        return token
    suffix_matches = sorted(path for path in files if path.endswith(f"/{token}"))
    if len(suffix_matches) == 1:
        return suffix_matches[0]
    matches = by_basename.get(Path(token).name, [])
    if len(matches) == 1:
        return matches[0]
    scenario_match = f"scenarios/{token}"
    if scenario_match in files:
        return scenario_match
    raise ValueError(f"cannot uniquely resolve code-anchor path {token!r}: {matches}")


def _line_ranges(segment: str) -> list[tuple[int, int]]:
    """Extract explicit line/range locators from one path's anchor segment."""
    ranges: list[tuple[int, int]] = []
    for start, end in re.findall(r"(?<![A-Za-z0-9.])([0-9]+)-([0-9]+)", segment):
        ranges.append((int(start), int(end)))
    for number in re.findall(r":([0-9]+)(?![-0-9])", segment):
        value = int(number)
        if not any(start <= value <= end for start, end in ranges):
            ranges.append((value, value))
    # A compact first locator may list comma-separated lines without repeating ':'.
    compact = re.search(r":([0-9]+(?:\s*,\s*[0-9]+)+)", segment)
    if compact:
        for number in re.findall(r"[0-9]+", compact.group(1)):
            value = int(number)
            if not any(start <= value <= end for start, end in ranges):
                ranges.append((value, value))
    return sorted(set(ranges))


def atomize_code_anchors(
    anchors: Iterable[str | dict[str, Any]], repo_root: Path
) -> list[dict[str, Any]]:
    """Convert legacy compound anchor strings to atomic, validated objects."""
    files, by_basename = _repo_file_index(repo_root)
    output: list[dict[str, Any]] = []
    for raw in anchors:
        if isinstance(raw, dict):
            output.append(dict(raw))
            continue
        expanded = _expand_braced_paths(str(raw))
        matches = list(_PATH_TOKEN.finditer(expanded))
        if not matches:
            raise ValueError(f"code anchor contains no repository path: {raw!r}")
        for index, match in enumerate(matches):
            token = match.group(1)
            relative = _resolve_path(token, files, by_basename)
            next_start = (
                matches[index + 1].start()
                if index + 1 < len(matches)
                else len(expanded)
            )
            segment = expanded[match.end() : next_start]
            path = repo_root / relative
            line_count = len(
                path.read_text(encoding="utf-8", errors="replace").splitlines()
            )
            ranges = _line_ranges(segment) or [(1, max(1, line_count))]
            for start, end in ranges:
                if start < 1 or end < start or end > max(1, line_count):
                    raise ValueError(
                        f"anchor line range outside file: {relative}:{start}-{end} "
                        f"(file has {line_count} lines; legacy={raw!r})"
                    )
                output.append(
                    {
                        "repository_commit": AUDITED_COMMIT,
                        "path": relative,
                        "start_line": start,
                        "end_line": end,
                        "symbol": "",
                        "note": f"Normalized from legacy anchor: {raw}",
                    }
                )
    unique: list[dict[str, Any]] = []
    seen: set[tuple[str, int, int]] = set()
    for row in output:
        key = (str(row["path"]), int(row["start_line"]), int(row["end_line"]))
        if key not in seen:
            seen.add(key)
            unique.append(row)
    return unique


def _dependency_kind(finding_id: str, requirement: str) -> tuple[str, str]:
    text = requirement.lower()
    if re.fullmatch(r"(?:p[235]-[a-z0-9-]+|rs-[a-f][0-9]+)", requirement, re.I):
        return "cross_finding", requirement
    if requirement.startswith("P5-REPRO-") or requirement.startswith("P4-"):
        return "validation", requirement
    if requirement.startswith("/Users/"):
        return "validation", requirement
    transaction_words = (
        "transaction",
        "term sheet",
        "facility",
        "lender",
        "legal debt",
        "statutory",
        "site measurement",
        "oem",
    )
    if any(word in text for word in transaction_words):
        return "transaction_evidence", ""
    validation_words = (
        "independent",
        "verify",
        "validate",
        "reproduction",
        "refuter",
        "evidence",
        "source",
        "confirm",
        "review",
        "approve",
        "correct wording",
    )
    if any(word in text for word in validation_words):
        return "validation", ""
    if text.startswith("no implementation action"):
        return "monitoring", ""
    return "implementation", ""


def type_dependencies(
    finding_id: str,
    requirements: Iterable[str | dict[str, Any]],
    *,
    owner_role: str,
) -> list[dict[str, Any]]:
    """Convert prose/mixed dependency lists into stable typed dependency objects."""
    output: list[dict[str, Any]] = []
    serial = 0
    for raw in requirements:
        if isinstance(raw, dict):
            output.append(dict(raw))
            continue
        for requirement in str(raw).split(" || "):
            requirement = requirement.strip()
            if not requirement:
                continue
            serial += 1
            kind, target = _dependency_kind(finding_id, requirement)
            non_action = requirement.lower().startswith("no implementation action")
            output.append(
                {
                    "dependency_id": f"DEP-{finding_id}-{serial:02d}",
                    "kind": kind,
                    "target": target,
                    "owner_role": owner_role,
                    "status": (
                        "not_applicable" if non_action else "required_not_started"
                    ),
                    "blocking": not non_action,
                    "requirement": requirement,
                }
            )
    return output
