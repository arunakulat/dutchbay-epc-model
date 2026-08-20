"""Classify whether a pull-request diff requires independent Grid Study CI.

The script reads NUL- or newline-delimited repository-relative paths from stdin and
emits one JSON object.  Under GitHub Actions it also writes the boolean output
``qsts_execution_changed`` to ``GITHUB_OUTPUT``.  Empty, unsafe, or indeterminate
input fails closed by requiring the Grid Study.
"""

from __future__ import annotations

import fnmatch
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, TextIO

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY_PATH = REPO_ROOT / "config" / "grid_ci_policy.json"
_POLICY_KEYS = {
    "schema_version",
    "rule_id",
    "empty_diff_requires_grid",
    "exact_paths",
    "path_prefixes",
    "glob_patterns",
}


@dataclass(frozen=True)
class GridCiPathPolicy:
    """Strict path-routing policy for independent Grid Study CI."""

    exact_paths: frozenset[str]
    path_prefixes: tuple[str, ...]
    glob_patterns: tuple[str, ...]
    empty_diff_requires_grid: bool


def _validated_string_list(value: Any, *, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field} must be a non-empty list of strings")
    if not all(isinstance(item, str) and item for item in value):
        raise ValueError(f"{field} must contain only non-empty strings")
    if len(value) != len(set(value)):
        raise ValueError(f"{field} must not contain duplicate entries")
    return tuple(value)


def load_policy(path: Path = DEFAULT_POLICY_PATH) -> GridCiPathPolicy:
    """Load and strictly validate the governed Grid Study path policy.

    Args:
        path: JSON policy path.

    Returns:
        The validated immutable path policy.

    Raises:
        ValueError: If the policy schema or any controlled value is invalid.
    """

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or set(raw) != _POLICY_KEYS:
        actual = set(raw) if isinstance(raw, dict) else set()
        raise ValueError(
            "grid CI policy keys must be exact; "
            f"missing={sorted(_POLICY_KEYS - actual)}, extra={sorted(actual - _POLICY_KEYS)}"
        )
    if raw["schema_version"] != "1.0":
        raise ValueError("grid CI policy schema_version must be '1.0'")
    if raw["rule_id"] != "TEST-05":
        raise ValueError("grid CI policy rule_id must be 'TEST-05'")
    if raw["empty_diff_requires_grid"] is not True:
        raise ValueError("empty_diff_requires_grid must remain true (fail closed)")

    exact_paths = _validated_string_list(raw["exact_paths"], field="exact_paths")
    prefixes = _validated_string_list(raw["path_prefixes"], field="path_prefixes")
    patterns = _validated_string_list(raw["glob_patterns"], field="glob_patterns")

    for candidate in (*exact_paths, *prefixes, *patterns):
        if (
            candidate.startswith("/")
            or "\\" in candidate
            or ".." in candidate.split("/")
        ):
            raise ValueError(
                f"grid CI policy path must be safe and relative: {candidate!r}"
            )
    if not all(prefix.endswith("/") for prefix in prefixes):
        raise ValueError("every path_prefixes entry must end with '/'")

    return GridCiPathPolicy(
        exact_paths=frozenset(exact_paths),
        path_prefixes=prefixes,
        glob_patterns=patterns,
        empty_diff_requires_grid=True,
    )


def _is_safe_relative_path(path: str) -> bool:
    pure = PurePosixPath(path)
    return (
        bool(path)
        and not pure.is_absolute()
        and "\\" not in path
        and ".." not in pure.parts
    )


def requires_grid_study(
    changed_paths: list[str], policy: GridCiPathPolicy | None = None
) -> bool:
    """Return whether changed paths require independent Grid Study execution.

    Unsafe or empty input fails closed.  This prevents a malformed or
    indeterminate diff from being converted into a governed CI skip.
    """

    active_policy = policy or load_policy()
    paths = [path.strip() for path in changed_paths if path.strip()]
    if not paths:
        return active_policy.empty_diff_requires_grid

    for path in paths:
        if not _is_safe_relative_path(path):
            return True
        if path in active_policy.exact_paths:
            return True
        if any(path.startswith(prefix) for prefix in active_policy.path_prefixes):
            return True
        if any(
            fnmatch.fnmatchcase(path, pattern)
            for pattern in active_policy.glob_patterns
        ):
            return True
    return False


def _read_changed_paths() -> list[str]:
    raw = sys.stdin.buffer.read()
    separator = b"\0" if b"\0" in raw else None
    chunks = raw.split(separator) if separator is not None else raw.splitlines()
    return [chunk.decode("utf-8", errors="strict") for chunk in chunks if chunk]


def _write_github_output(stream: TextIO, *, requires_grid: bool) -> None:
    stream.write(f"qsts_execution_changed={str(requires_grid).lower()}\n")


def main() -> None:
    """Emit the JSON-first classification and optional GitHub Actions output."""

    changed_paths = _read_changed_paths()
    requires_grid = requires_grid_study(changed_paths)
    payload = {
        "changed_path_count": len(changed_paths),
        "qsts_execution_changed": requires_grid,
        "rule_id": "TEST-05",
        "schema_version": "1.0",
    }
    print(json.dumps(payload, sort_keys=True))

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with Path(github_output).open("a", encoding="utf-8") as stream:
            _write_github_output(stream, requires_grid=requires_grid)


if __name__ == "__main__":
    main()
