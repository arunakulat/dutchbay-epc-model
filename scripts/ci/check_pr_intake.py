"""Check that a PR has a scoped tracker-linked work item and an open-PR sweep."""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

TRACKER_NUMBER = 1353
BOT_AUTHORS = frozenset(
    {"dependabot[bot]", "github-actions[bot]", "copilot[bot]", "renovate[bot]"}
)
_ISSUE = re.compile(r"^Work item:\s*#([1-9][0-9]*)\s*$", re.MULTILINE)
_BASE = re.compile(r"^Base SHA:\s*([0-9a-f]{40})\s*$", re.MULTILINE)
_SWEEP = re.compile(r"^Open PR sweep:\s*(.+)$", re.MULTILINE)
_RECORDED = re.compile(r"^Recorded before edits:\s*(.+)$", re.MULTILINE)
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def _references(body: str, number: int) -> bool:
    """Recognize an exact issue reference, not a numeric substring."""
    return bool(
        re.search(rf"(?<![\w#])#{number}\b", body)
        or re.search(rf"/issues/{number}(?![0-9])", body)
    )


def _timestamp(value: str) -> datetime:
    """Parse GitHub's UTC timestamp without losing timezone information."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def evaluate(
    body: str,
    author: str,
    created_at: str,
    pr_number: int,
    issue: dict[str, Any],
    tracker: dict[str, Any],
    open_prs: list[dict[str, Any]],
) -> tuple[int, str]:
    """Return a fail-closed intake result for already-fetched GitHub objects."""
    work_item = _ISSUE.search(body)
    if work_item is None:
        return (
            1,
            "INTAKE-01: supply 'Work item: #<focused issue number>' in the PR body.",
        )
    issue_number = int(work_item.group(1))
    if issue_number == TRACKER_NUMBER:
        return 1, "INTAKE-01: #1353 alone is a generic index, not a scoped work item."
    if issue.get("number") != issue_number or "pull_request" in issue:
        return 1, "INTAKE-01: the work item must be a GitHub issue in this repository."
    if not (
        _references(issue.get("body") or "", TRACKER_NUMBER)
        or _references(tracker.get("body") or "", issue_number)
    ):
        return 1, "INTAKE-01: the focused issue is not cross-linked with tracker #1353."
    if author not in BOT_AUTHORS:
        try:
            if _timestamp(issue["created_at"]) > _timestamp(created_at):
                return (
                    1,
                    "INTAKE-01: the focused issue was created after this human/agent PR.",
                )
        except (KeyError, TypeError, ValueError):
            return 1, "INTAKE-01: issue/PR creation times are missing or invalid."
    if _BASE.search(body) is None:
        return 1, "INTAKE-01: supply the 40-character observed origin/main 'Base SHA'."
    sweep = _SWEEP.search(body)
    if sweep is None or sweep.group(1).strip().lower() in {"", "...", "tbd", "todo"}:
        return 1, "INTAKE-01: describe the open-PR sweep and overlap dispositions."
    missing = sorted(
        int(pr["number"])
        for pr in open_prs
        if int(pr["number"]) != pr_number
        and not _references(sweep.group(1), int(pr["number"]))
    )
    if missing:
        return 1, "INTAKE-01: open-PR sweep omits " + ", ".join(
            f"#{n}" for n in missing
        )
    recorded = _RECORDED.search(body)
    if recorded is None or not _references(recorded.group(1), issue_number):
        return 1, "INTAKE-01: 'Recorded before edits' must cite the focused issue."
    return 0, (
        f"INTAKE-01: scoped issue #{issue_number}, base SHA, pre-edit citation and "
        f"{len(open_prs) - int(any(pr['number'] == pr_number for pr in open_prs))} "
        "other open PR(s) recorded. Semantic overlap and pre-edit timing require review."
    )


def _get_json(repository: str, path: str, token: str) -> Any:
    """Read GitHub REST JSON with a bounded request; errors block intake."""
    request = Request(
        f"https://api.github.com/repos/{repository}/{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "dutchbay-pr-intake-check",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urlopen(request, timeout=15) as response:
        return json.load(response)


def main() -> int:
    """Read event metadata from the environment and verify the live issue/PR index."""
    body = os.environ.get("PR_BODY", "")
    match = _ISSUE.search(body)
    if match is None or int(match.group(1)) == TRACKER_NUMBER:
        code, message = (1, "INTAKE-01: name a focused issue other than #1353.")
    else:
        repository = os.environ.get("GITHUB_REPOSITORY", "")
        token = os.environ.get("GITHUB_TOKEN", "")
        if not _REPOSITORY.fullmatch(repository) or not token:
            code, message = (
                1,
                "INTAKE-01: GitHub repository or read token unavailable.",
            )
        else:
            try:
                issue = _get_json(repository, f"issues/{match.group(1)}", token)
                tracker = _get_json(repository, f"issues/{TRACKER_NUMBER}", token)
                open_prs: list[dict[str, Any]] = []
                for page in range(1, 11):
                    batch = _get_json(
                        repository, f"pulls?state=open&per_page=100&page={page}", token
                    )
                    open_prs.extend(batch)
                    if len(batch) < 100:
                        break
                else:
                    raise ValueError("open PR list exceeds bounded ten-page sweep")
                code, message = evaluate(
                    body,
                    os.environ.get("PR_AUTHOR", ""),
                    os.environ.get("PR_CREATED_AT", ""),
                    int(os.environ.get("PR_NUMBER", "0")),
                    issue,
                    tracker,
                    open_prs,
                )
            except (
                HTTPError,
                URLError,
                OSError,
                ValueError,
                TypeError,
                KeyError,
            ) as exc:
                code, message = (
                    1,
                    f"INTAKE-01: live GitHub intake verification failed: {exc}",
                )
    print(message)
    return code


if __name__ == "__main__":
    sys.exit(main())
