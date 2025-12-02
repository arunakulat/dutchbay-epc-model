from __future__ import annotations

import csv
import os
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

# Columns we absolutely expect in the v3.0 + v14 merged ruleset.
REQUIRED_COLUMNS = (
    "version",
    "rule_id",
    "category",
    "title",
    "description",
    "enforcement",
    "status",
)
#!/usr/bin/env python3
"""
Tiny helper to sanity-check the Go-with-the-Flow ruleset CSV.

Responsibilities:
- Read DUTCHBAY_FLOW_RULESET_CSV from the environment.
- Validate that key columns are present.
- Print a short summary: N rules, versions present, latest version.
- Exit code 0 on success, 1 on failure (when run as a script).
"""


@dataclass
class RulesetSummary:
    path: Path
    n_rules: int
    versions: List[str]
    latest_version: str
    by_status: Dict[str, int]


def _resolve_ruleset_path(env_var: str = "DUTCHBAY_FLOW_RULESET_CSV") -> Path:
    """Resolve the ruleset path from environment or raise a clear error."""
    raw = os.environ.get(env_var)
    if not raw:
        raise RuntimeError(
            f"{env_var} is not set. Expected it to point at the "
            "Go-with-the-Flow ruleset CSV "
            "(e.g. go_with_the_flow_rules_v3_0_merged_with_v14.csv)."
        )

    path = Path(raw).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(
            f"{env_var}={raw!r} does not exist or is not a file " f"(resolved: {path})"
        )
    return path


def _load_rules(path: Path) -> List[dict]:
    """Load the CSV as a list of dict rows and validate the header."""
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError(f"Ruleset {path} appears empty or has no header row.")

        missing = [col for col in REQUIRED_COLUMNS if col not in reader.fieldnames]
        if missing:
            raise ValueError(
                f"Ruleset {path} is missing required columns: {', '.join(missing)}. "
                f"Found columns: {', '.join(reader.fieldnames)}"
            )

        return list(reader)


def summarise_ruleset(path: Optional[Path] = None) -> RulesetSummary:
    """Load and summarise the ruleset into a compact dataclass."""
    if path is None:
        path = _resolve_ruleset_path()

    rows = _load_rules(path)
    n_rules = len(rows)

    versions = sorted({(row.get("version") or "").strip() or "unknown" for row in rows})
    latest = versions[-1] if versions else "unknown"

    status_counter: Counter[str] = Counter(
        (row.get("status") or "unknown").strip().lower() or "unknown" for row in rows
    )

    return RulesetSummary(
        path=path,
        n_rules=n_rules,
        versions=versions,
        latest_version=latest,
        by_status=dict(sorted(status_counter.items(), key=lambda kv: kv[0])),
    )


def run_ruleset_check(quiet: bool = False) -> RulesetSummary:
    """
    Public entrypoint for bootstrap / CI.

    - Returns a RulesetSummary.
    - Prints a short human-readable summary unless quiet=True.
    - Raises on errors (caller decides whether to treat as fatal).
    """
    summary = summarise_ruleset()

    if not quiet:
        print(
            f"[rules] Go-with-the-Flow ruleset loaded from: {summary.path}",
            file=sys.stderr,
        )
        print(
            "[rules] "
            f"{summary.n_rules} rules; "
            f"versions: {', '.join(summary.versions)}; "
            f"latest = {summary.latest_version}",
            file=sys.stderr,
        )
        if summary.by_status:
            breakdown = ", ".join(
                f"{status}={count}" for status, count in summary.by_status.items()
            )
            print(f"[rules] Status breakdown: {breakdown}", file=sys.stderr)

    return summary


def main(argv: Optional[list] = None) -> int:
    """
    CLI entrypoint:

    python dutchbay_bootstrap_rules.py
    python dutchbay_bootstrap_rules.py --quiet
    """
    argv = list(argv or sys.argv[1:])
    quiet = ("--quiet" in argv) or ("-q" in argv)

    try:
        run_ruleset_check(quiet=quiet)
    except Exception as exc:  # noqa: BLE001
        print(
            f"[rules] Ruleset sanity check FAILED: {exc}",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
