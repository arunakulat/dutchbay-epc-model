"""Check that a PR has a scoped tracker-linked work item and an open-PR sweep."""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

TRACKER_NUMBER = 1353
BOT_AUTHORS = frozenset(
    {"dependabot[bot]", "github-actions[bot]", "copilot[bot]", "renovate[bot]"}
)
_ISSUE = re.compile(r"^Work item:[ \t]*#([1-9][0-9]*)[ \t]*$", re.MULTILINE)
_TRACKER_COMMENT = re.compile(
    r"^Work item:[ \t]*https://github\.com/arunakulat/dutchbay-epc-model/"
    r"issues/1353#issuecomment-([1-9][0-9]*)[ \t]*$",
    re.MULTILINE,
)
_BASE = re.compile(r"^Base SHA:[ \t]*([0-9a-f]{40})[ \t]*$", re.MULTILINE)
_SWEEP = re.compile(r"^Open PR sweep:[ \t]*([^\r\n]+)$", re.MULTILINE)
_RECORDED = re.compile(r"^Recorded before edits:[ \t]*([^\r\n]+)$", re.MULTILINE)
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


def _sweep_omissions(
    sweep_text: str, open_prs: list[dict[str, Any]], pr_number: int, created_at: str
) -> list[int]:
    """Open PRs the sweep must name but does not.

    INTAKE-01 asks for the sweep "before opening a PR", so it covers the PRs that were
    open when this one was opened. A PR opened later is not required here: its own
    sweep must name this one, so every pair is still recorded once. Without this, each
    new PR failed every older PR's intake on its next run. A PR whose creation time is
    missing or unreadable is still required (fail closed), as is every open PR when this
    PR's own creation time cannot be read.
    """
    try:
        opened = _timestamp(created_at)
    except (TypeError, ValueError):
        opened = None

    def _required(pr: dict[str, Any]) -> bool:
        if opened is None or not pr.get("created_at"):
            return True
        try:
            return _timestamp(str(pr["created_at"])) <= opened
        except (TypeError, ValueError):
            return True

    return sorted(
        int(pr["number"])
        for pr in open_prs
        if int(pr["number"]) != pr_number
        and _required(pr)
        and not _references(sweep_text, int(pr["number"]))
    )


def _last_opened(created_at: str, events: list[dict[str, Any]]) -> str:
    """When this PR last became open: its latest ``reopened`` event, else ``created_at``.

    ``created_at`` does not move when a PR is reopened, so without this a reopened PR
    would not have to name PRs opened while it was closed (#1877). An unreadable
    ``created_at`` is returned unchanged, and an unreadable ``reopened`` time returns
    "", so the sweep then requires every open PR (fail closed).
    """
    try:
        latest = _timestamp(created_at)
    except (TypeError, ValueError):
        return created_at
    opened = created_at
    for event in events:
        if event.get("event") != "reopened":
            continue
        try:
            reopened = _timestamp(str(event["created_at"]))
        except (KeyError, TypeError, ValueError):
            return ""
        if reopened > latest:
            latest, opened = reopened, str(event["created_at"])
    return opened


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
        deliverable = re.search(
            r"^Work item:[ \t]*([^\r\n]+)$", comment_body, re.MULTILINE
        )
        done_when = re.search(
            r"^Done when:[ \t]*([^\r\n]+)$", comment_body, re.MULTILINE
        )
        if (
            work_comment is None
            or work_comment.get("id") != comment_id
            or work_comment.get("issue_url")
            != "https://api.github.com/repos/arunakulat/dutchbay-epc-model/issues/1353"
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
    missing = _sweep_omissions(sweep.group(1), open_prs, pr_number, created_at)
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


#: GitHub returns at most this many issue comments per page.
_PAGE_SIZE = 100


def _comment_pages(count: object) -> int:
    """Return how many comment pages the tracker has, refusing a missing count."""
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise ValueError(f"tracker comment count is missing or invalid: {count!r}")
    return -(-count // _PAGE_SIZE)


def scan_tracker_comments(
    fetch_page: Callable[[int], list[dict[str, Any]]],
    comment_count: object,
    verdict: Callable[[list[dict[str, Any]]], tuple[int, str]],
) -> tuple[int, str]:
    """Read the tracker's comments newest page first and stop once intake passes.

    Every tracker-comment test in :func:`evaluate` asks whether *some* comment
    qualifies, so a verdict that passes on the comments read so far also passes on
    all of them. The scan therefore stops at the first passing verdict, which for a
    new PR is usually the newest page, and otherwise reads every page the tracker's
    own comment count names before failing. There is no fixed page ceiling (#1418):
    the previous ten-page bound failed every PR once #1353 passed 1,000 comments.
    """
    comments: list[dict[str, Any]] = []
    code, message = verdict(comments)
    for page in range(_comment_pages(comment_count), 0, -1):
        if code == 0:
            break
        batch = fetch_page(page)
        if not isinstance(batch, list):
            raise ValueError(f"tracker comment page {page} is not a list")
        comments = batch + comments
        code, message = verdict(comments)
    return code, message


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


def _validate_body_static(body: str) -> tuple[int, str] | None:
    """Fail fast on malformed static PR body fields before making GitHub API calls."""
    work_issue = _ISSUE.search(body)
    direct_comment = _TRACKER_COMMENT.search(body)
    if len(_ISSUE.findall(body)) + len(_TRACKER_COMMENT.findall(body)) != 1 or (
        work_issue is not None and int(work_issue.group(1)) == TRACKER_NUMBER
    ):
        return (
            1,
            "INTAKE-01: name one focused issue or scoped #1353 comment URL.",
        )
    if _BASE.search(body) is None:
        return 1, "INTAKE-01: supply the 40-character observed origin/main 'Base SHA'."
    sweep = _SWEEP.search(body)
    if sweep is None or sweep.group(1).strip().lower() in {"", "...", "tbd", "todo"}:
        return 1, "INTAKE-01: describe the open-PR sweep and overlap dispositions."
    recorded = _RECORDED.search(body)
    if recorded is None:
        return 1, "INTAKE-01: 'Recorded before edits' must cite the work record."
    if work_issue is not None:
        citation_ok = _references(recorded.group(1), int(work_issue.group(1)))
    else:
        assert direct_comment is not None
        citation_ok = bool(
            re.search(
                rf"issuecomment-{int(direct_comment.group(1))}(?![0-9])",
                recorded.group(1),
            )
        )
    if not citation_ok:
        return 1, "INTAKE-01: 'Recorded before edits' must cite the work record."
    return None


def main() -> int:
    """Read event metadata from the environment and verify the live issue/PR index."""
    body = os.environ.get("PR_BODY", "")
    static_error = _validate_body_static(body)
    if static_error is not None:
        code, message = static_error
    else:
        work_issue = _ISSUE.search(body)
        direct_comment = _TRACKER_COMMENT.search(body)
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
                tracker = (
                    _get_json(repository, f"issues/{TRACKER_NUMBER}", token)
                    if work_issue is not None
                    else {"number": TRACKER_NUMBER, "body": "", "comments": 0}
                )
                pr_number = int(os.environ.get("PR_NUMBER", "0"))
                author = os.environ.get("PR_AUTHOR", "")
                author_type = os.environ.get("PR_AUTHOR_TYPE", "")
                created_at = os.environ.get("PR_CREATED_AT", "")
                pr_self_only = [{"number": pr_number}]

                def _verdict_issue_only(
                    comments: list[dict[str, Any]],
                ) -> tuple[int, str]:
                    return evaluate(
                        body,
                        author,
                        author_type,
                        created_at,
                        pr_number,
                        issue,
                        tracker,
                        comments,
                        work_comment,
                        pr_self_only,
                    )

                code, message = (
                    scan_tracker_comments(
                        lambda page: _get_json(
                            repository,
                            f"issues/{TRACKER_NUMBER}/comments"
                            f"?per_page={_PAGE_SIZE}&page={page}",
                            token,
                        ),
                        tracker.get("comments"),
                        _verdict_issue_only,
                    )
                    if work_issue is not None
                    else _verdict_issue_only([])
                )
                if code == 0:
                    open_prs: list[dict[str, Any]] = []
                    for page in range(1, 11):
                        batch = _get_json(
                            repository,
                            f"pulls?state=open&per_page=100&page={page}",
                            token,
                        )
                        open_prs.extend(batch)
                        if len(batch) < 100:
                            break
                    else:
                        raise ValueError("open PR list exceeds bounded ten-page sweep")
                    events: list[dict[str, Any]] = []
                    for page in range(1, 11):
                        batch = _get_json(
                            repository,
                            f"issues/{pr_number}/events?per_page=100&page={page}",
                            token,
                        )
                        events.extend(batch)
                        if len(batch) < 100:
                            break
                    else:
                        raise ValueError("PR event list exceeds bounded ten-page read")
                    sweep = _SWEEP.search(body)
                    assert sweep is not None
                    missing = _sweep_omissions(
                        sweep.group(1),
                        open_prs,
                        pr_number,
                        _last_opened(created_at, events),
                    )
                    if missing:
                        code = 1
                        message = "INTAKE-01: open-PR sweep omits " + ", ".join(
                            f"#{n}" for n in missing
                        )
                    else:
                        item_name = (
                            f"issue #{int(work_issue.group(1))}"
                            if work_issue is not None
                            else f"tracker comment {int(direct_comment.group(1))}"  # type: ignore[union-attr]
                        )
                        message = (
                            f"INTAKE-01: scoped {item_name}, base SHA, work-record citation and "
                            f"{len(open_prs) - int(any(pr['number'] == pr_number for pr in open_prs))} "
                            "other open PR(s) recorded. Semantic overlap and pre-edit timing require review."
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
