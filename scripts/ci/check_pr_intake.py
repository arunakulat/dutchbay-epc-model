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
_TRACKER_COMMENT = re.compile(
    r"^Work item:\s*https://github\.com/arunakulat/dutchbay-epc-model/"
    r"issues/1353#issuecomment-([1-9][0-9]*)\s*$",
    re.MULTILINE,
)
_BASE = re.compile(r"^Base SHA:\s*([0-9a-f]{40})\s*$", re.MULTILINE)
_SWEEP = re.compile(r"^Open PR sweep:\s*(.+)$", re.MULTILINE)
_RECORDED = re.compile(r"^Recorded before edits:\s*(.+)$", re.MULTILINE)
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def _references(body: str, number: int) -> bool:
    """Recognize an exact issue reference, not a numeric substring."""
    return bool(
        re.search(rf"(?<![\w#])#{number}\b", body)
        or re.search(rf"/issues/{number}(?![A-Za-z0-9_-])", body)
    )


def _timestamp(value: str) -> datetime:
    """Parse GitHub's UTC timestamp without losing timezone information."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _is_bot(login: str, actor_type: str) -> bool:
    """Use GitHub's actor type, with a login fallback for unlisted bots."""
    return (
        actor_type == "Bot" or login.lower().endswith("[bot]") or login in BOT_AUTHORS
    )


def _human_comment(comment: dict[str, Any]) -> bool:
    """Distinguish a human/agent intake record from a bot-created reference."""
    user = comment.get("user") or {}
    login = user.get("login") or ""
    return bool(login) and not _is_bot(login, user.get("type") or "")


def _specific(text: str) -> bool:
    """Reject empty and obvious placeholder fields in a direct tracker record."""
    value = text.strip().lower()
    return len(value) >= 12 and not value.startswith(
        ("tbd", "todo", "n/a", "unknown", "select later", "decide later", "placeholder")
    )


def evaluate(
    body: str,
    author: str,
    author_type: str,
    created_at: str,
    pr_number: int,
    issue: dict[str, Any] | None,
    tracker: dict[str, Any],
    tracker_comments: list[dict[str, Any]],
    work_comment: dict[str, Any] | None,
    open_prs: list[dict[str, Any]],
) -> tuple[int, str]:
    """Return a fail-closed intake result for already-fetched GitHub objects."""
    work_issue = _ISSUE.search(body)
    direct_comment = _TRACKER_COMMENT.search(body)
    bot_author = _is_bot(author, author_type)
    if len(_ISSUE.findall(body)) + len(_TRACKER_COMMENT.findall(body)) != 1:
        return (
            1,
            "INTAKE-01: name one focused issue or one scoped #1353 comment URL.",
        )
    if work_issue is not None:
        issue_number = int(work_issue.group(1))
        if issue_number == TRACKER_NUMBER:
            return (
                1,
                "INTAKE-01: #1353 alone is a generic index, not a scoped work item.",
            )
        if (
            issue is None
            or issue.get("number") != issue_number
            or "pull_request" in issue
        ):
            return (
                1,
                "INTAKE-01: the work item must be a GitHub issue in this repository.",
            )
        linked_comments = [
            comment
            for comment in tracker_comments
            if _references(comment.get("body") or "", issue_number)
        ]
        if not (
            _references(tracker.get("body") or "", issue_number) or linked_comments
        ):
            return 1, "INTAKE-01: the focused issue is not recorded on tracker #1353."
        if bot_author:
            try:
                triaged = any(
                    _human_comment(comment)
                    and _references(comment.get("body") or "", pr_number)
                    and _timestamp(comment["created_at"]) >= _timestamp(created_at)
                    for comment in linked_comments
                )
            except (KeyError, TypeError, ValueError):
                return 1, "INTAKE-01: bot triage timestamp is invalid."
            if not triaged:
                return (
                    1,
                    "INTAKE-01: a bot PR needs post-creation non-bot triage naming this PR.",
                )
        if not bot_author and not _references(tracker.get("body") or "", issue_number):
            try:
                if not any(
                    _timestamp(comment["created_at"]) <= _timestamp(created_at)
                    for comment in linked_comments
                ):
                    return 1, "INTAKE-01: tracker link was added after this PR."
            except (KeyError, TypeError, ValueError):
                return 1, "INTAKE-01: tracker comment timestamp is invalid."
        item_name = f"issue #{issue_number}"
        item_created_at = issue.get("created_at")
    else:
        assert direct_comment is not None
        comment_id = int(direct_comment.group(1))
        comment_body = (work_comment or {}).get("body") or ""
        deliverable = re.search(r"^Work item:\s*(.+)$", comment_body, re.MULTILINE)
        done_when = re.search(r"^Done when:\s*(.+)$", comment_body, re.MULTILINE)
        if (
            work_comment is None
            or work_comment.get("id") != comment_id
            or not (work_comment.get("issue_url") or "").endswith(
                f"/issues/{TRACKER_NUMBER}"
            )
            or not _human_comment(work_comment)
            or deliverable is None
            or done_when is None
            or not _specific(deliverable.group(1))
            or not _specific(done_when.group(1))
        ):
            return 1, "INTAKE-01: tracker comment is missing, unscoped or bot-authored."
        if bot_author:
            try:
                if not _references(comment_body, pr_number) or _timestamp(
                    work_comment["created_at"]
                ) < _timestamp(created_at):
                    return (
                        1,
                        "INTAKE-01: bot tracker comment must triage this PR after creation.",
                    )
            except (KeyError, TypeError, ValueError):
                return 1, "INTAKE-01: bot tracker comment timestamp is invalid."
        item_name = f"tracker comment {comment_id}"
        item_created_at = work_comment.get("created_at")
    if not bot_author:
        try:
            if _timestamp(str(item_created_at)) > _timestamp(created_at):
                return (
                    1,
                    "INTAKE-01: the work record was created after this human/agent PR.",
                )
        except (KeyError, TypeError, ValueError):
            return 1, "INTAKE-01: work-record/PR creation times are missing or invalid."
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
    if recorded is None:
        return 1, "INTAKE-01: 'Recorded before edits' must cite the work record."
    if work_issue is not None:
        citation_ok = _references(recorded.group(1), issue_number)
    else:
        citation_ok = bool(
            re.search(rf"issuecomment-{comment_id}(?![0-9])", recorded.group(1))
        )
    if not citation_ok:
        return 1, "INTAKE-01: 'Recorded before edits' must cite the work record."
    return 0, (
        f"INTAKE-01: scoped {item_name}, base SHA, work-record citation and "
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
    work_issue = _ISSUE.search(body)
    direct_comment = _TRACKER_COMMENT.search(body)
    if len(_ISSUE.findall(body)) + len(_TRACKER_COMMENT.findall(body)) != 1 or (
        work_issue is not None and int(work_issue.group(1)) == TRACKER_NUMBER
    ):
        code, message = (
            1,
            "INTAKE-01: name one focused issue or scoped #1353 comment URL.",
        )
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
                issue = (
                    _get_json(repository, f"issues/{work_issue.group(1)}", token)
                    if work_issue is not None
                    else None
                )
                work_comment = (
                    _get_json(
                        repository, f"issues/comments/{direct_comment.group(1)}", token
                    )
                    if direct_comment is not None
                    else None
                )
                tracker = _get_json(repository, f"issues/{TRACKER_NUMBER}", token)
                tracker_comments: list[dict[str, Any]] = []
                for page in range(1, 11):
                    batch = _get_json(
                        repository,
                        f"issues/{TRACKER_NUMBER}/comments?per_page=100&page={page}",
                        token,
                    )
                    tracker_comments.extend(batch)
                    if len(batch) < 100:
                        break
                else:
                    raise ValueError("tracker comments exceed bounded ten-page scan")
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
                    os.environ.get("PR_AUTHOR_TYPE", ""),
                    os.environ.get("PR_CREATED_AT", ""),
                    int(os.environ.get("PR_NUMBER", "0")),
                    issue,
                    tracker,
                    tracker_comments,
                    work_comment,
                    open_prs,
                )
            except (
                HTTPError,
                URLError,
                OSError,
                ValueError,
                TypeError,
                KeyError,
                AttributeError,
            ) as exc:
                code, message = (
                    1,
                    f"INTAKE-01: live GitHub intake verification failed: {exc}",
                )
    print(message)
    return code


if __name__ == "__main__":
    sys.exit(main())
