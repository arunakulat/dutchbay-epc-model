#!/usr/bin/env python3
"""
Auto-close resolved GitHub issues using the GitHub CLI (`gh`).

Requirements:
    - `gh` installed and authenticated (`gh auth status` should be OK).
    - Run this script from inside the target repo's working directory.
    - Python 3.8+.

Behavior:
    1. Fetch all OPEN issues via `gh issue list --state open --json ...`.
    2. Decide which issues are ready to close using ISSUE_CLOSE_NOTES
       (mapping issue_number -> explanation text).
    3. For each candidate:
        - Post a closing comment.
        - Close the issue.
    4. Fetch and print the remaining open issues.

Use `--dry-run` to see what *would* be closed without actually calling `gh`.
"""

import argparse
import json
import subprocess
import textwrap
from typing import Any, Dict, List, Tuple


# ---------------------------------------------------------------------------
# Configuration: per-issue close notes (you can extend/modify this mapping)
# ---------------------------------------------------------------------------

ISSUE_CLOSE_NOTES: Dict[int, str] = {
    1: textwrap.dedent(
        """\
        Closing as resolved.

        The v14 analytics path now attaches `scenario_name` to the KPI block via
        `calculate_scenario_kpis(...)` / `compute_kpis(...)`, and
        `ScenarioAnalytics` propagates this into `summary_df` and `timeseries_df`.
        The executive report flow normalises `scenario_name` before exporting,
        and the Excel + chart exports now show correct scenario labels.
        """
    ),
    2: textwrap.dedent(
        """\
        Closing as a duplicate of #1.

        The same changes that resolved #1 (scenario_name propagation through
        `calculate_scenario_kpis(...)`, `compute_kpis(...)`, `ScenarioAnalytics`
        and the export normalisation path) fully address this issue as well.
        """
    ),
    3: textwrap.dedent(
        """\
        Closing as resolved.

        KPI naming is now canonicalised via the analytics layer:
        - `project_irr` is the canonical IRR column and is normalised from
          any existing `irr`-like column via `normalise_kpis_for_export(...)`.
        - `dscr` is the canonical DSCR column; DSCR-like columns are aliased
          into `dscr` with clear logging when needed.

        ExcelExporter and ChartExporter both consume these canonical names.
        """
    ),
    4: textwrap.dedent(
        """\
        Closing as resolved.

        Excel board views have been hardened by:
        - Normalising `scenario_name`, `project_irr` and `dscr` before export.
        - Ensuring the exporter can safely skip or fall back when KPIs are
          missing, without raising.

        The executive report now produces a stable workbook with `Summary` and
        timeseries sheets and IRR/DSCR views where data is available, and
        CI smokes for export are green.
        """
    ),
    5: textwrap.dedent(
        """\
        Closing as resolved.

        A unified `export_charts(...)` entry point now drives chart creation:
        - Resolves canonical DSCR + IRR columns from the normalised frames.
        - Filters by `scenario_name` for the requested scenario.
        - Emits the DSCR line series and IRR histogram PNGs used in the
          executive report.

        The latest `make_executive_report.py` run produces both charts.
        """
    ),
    6: textwrap.dedent(
        """\
        Closing as resolved.

        `make_executive_report.py` has been thinned to a CLI + orchestration
        wrapper. It now:
        - Calls `ScenarioAnalytics` for batch analysis.
        - Filters to the requested scenario.
        - Normalises KPIs (`scenario_name`, `project_irr`, `dscr`).
        - Delegates Excel + chart generation to the exporter helpers.

        All heavy lifting for exports lives in the analytics/export layer now.
        """
    ),
    7: textwrap.dedent(
        """\
        Closing as resolved.

        Duplicate `'Batch analysis complete'` logging has been removed. The
        message is emitted once by the analytics layer, and the executive
        report script no longer re-logs the same banner. Console output is
        now clean and single-sourced.
        """
    ),
    # You can add more entries as you resolve additional issues, e.g.:
    # 8: "Closing after adding construction + IDC + grace-period regression tests...",
}


# ---------------------------------------------------------------------------
# Helpers to talk to `gh`
# ---------------------------------------------------------------------------


def run_gh(cmd: List[str]) -> str:
    """Run a `gh` command and return stdout, raising on failure."""
    result = subprocess.run(
        ["gh"] + cmd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def load_open_issues() -> List[Dict[str, Any]]:
    """Return all open issues as a list of dicts."""
    stdout = run_gh(
        [
            "issue",
            "list",
            "--state",
            "open",
            "--json",
            "number,title,labels,url,state",
        ]
    )
    issues = json.loads(stdout)
    return issues


def get_label_names(issue: Dict[str, Any]) -> List[str]:
    """Extract label names from a gh issue JSON object."""
    return [lbl.get("name", "") for lbl in issue.get("labels", [])]


# ---------------------------------------------------------------------------
# Logic: decide which issues to close
# ---------------------------------------------------------------------------


def decide_issues_to_close(
    issues: List[Dict[str, Any]],
    notes_mapping: Dict[int, str],
) -> List[Tuple[Dict[str, Any], str]]:
    """
    Decide which issues should be auto-closed.

    Current strategy:
        - Close only issues whose number appears in ISSUE_CLOSE_NOTES.
        - Attach the corresponding explanation text as the closing comment.

    This is intentionally conservative and repo-agnostic: for a different repo
    or a new batch, update ISSUE_CLOSE_NOTES.
    """
    candidates: List[Tuple[Dict[str, Any], str]] = []

    for issue in issues:
        number = int(issue["number"])
        if number in notes_mapping:
            comment = notes_mapping[number].strip()
            candidates.append((issue, comment))

    return candidates


def build_closing_comment(issue: Dict[str, Any], base_comment: str) -> str:
    """
    Wrap the base comment into a final message.

    You can tweak this template to include commit SHAs, branch names, etc.
    """
    heading = f"Auto-closing issue #{issue['number']}: {issue['title']}\n\n"
    footer = "\n\nIf you believe this issue is not fully addressed, feel free to reopen or comment with additional details."
    return heading + base_comment.strip() + footer


# ---------------------------------------------------------------------------
# Actions: comment + close, then list remaining open issues
# ---------------------------------------------------------------------------


def comment_and_close_issue(
    issue_number: int,
    comment: str,
    dry_run: bool = False,
) -> None:
    """
    Post a comment to an issue and close it using gh.

    In dry-run mode, only prints what would happen.
    """
    if dry_run:
        print(f"[DRY-RUN] Would comment on #{issue_number}:\n{comment}\n")
        print(f"[DRY-RUN] Would close issue #{issue_number}\n")
        return

    # Post comment
    run_gh(
        [
            "issue",
            "comment",
            str(issue_number),
            "--body",
            comment,
        ]
    )
    print(f"Commented on issue #{issue_number}")

    # Close issue
    run_gh(["issue", "close", str(issue_number)])
    print(f"Closed issue #{issue_number}\n")


def print_open_issues(issues: List[Dict[str, Any]]) -> None:
    """Pretty-print remaining open issues."""
    if not issues:
        print("No open issues remaining 🎉")
        return

    print("\nRemaining open issues:")
    print("-" * 72)
    for issue in issues:
        num = issue["number"]
        title = issue["title"]
        labels = ", ".join(get_label_names(issue))
        print(f"#{num:<4} {title}")
        if labels:
            print(f"      labels: {labels}")
        print(f"      url: {issue['url']}")
        print("-" * 72)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Auto-close resolved GitHub issues using `gh`.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show which issues would be closed without modifying GitHub.",
    )
    args = parser.parse_args()

    print("Loading open issues via `gh issue list`...")
    open_issues = load_open_issues()
    print(f"Found {len(open_issues)} open issue(s).")

    to_close = decide_issues_to_close(open_issues, ISSUE_CLOSE_NOTES)

    if not to_close:
        print("No issues matched ISSUE_CLOSE_NOTES; nothing to close.")
    else:
        print(f"\nIssues selected for closure ({len(to_close)}):")
        for issue, _ in to_close:
            print(f"  - #{issue['number']}: {issue['title']}")

        print()
        for issue, base_comment in to_close:
            number = int(issue["number"])
            final_comment = build_closing_comment(issue, base_comment)
            comment_and_close_issue(number, final_comment, dry_run=args.dry_run)

    # Reload open issues after closing operations
    print("\nReloading open issues after operations...")
    remaining = load_open_issues()
    print_open_issues(remaining)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())