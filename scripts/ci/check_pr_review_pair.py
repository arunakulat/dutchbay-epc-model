"""Check that an R2 or R3 pull request carries its independent review pair (#1486).

Owner decision on #1486 (2026-11-21): a mandatory review belongs in the required-check set
(``MERGE-01``), so an ``R2_LOAD_BEARING`` or ``R3_CONSEQUENTIAL`` pull request is not green
until a **domain** record and an **assurance** record are on it, each bound to its exact current
head and neither from the writer of that head (``RECRUIT-01``: no implementation
self-approval), and no counted reviewer's latest record at that head withholds acceptance
(``RECRUIT-01`` module 3 section 1: one veto blocks acceptance).

What counts as a record. A comment on the pull request, by the owner or a collaborator, that
states a SHA-256 (64 hex digits) and holds exactly one block between two lines that start with
``8<``. The digest must equal the SHA-256 of the block's bytes (LF line endings, one trailing
LF). Inside the block these header lines are read, each at the start of a line:

    Review-Record: 1
    Role: domain | assurance
    PR: #<number>
    Commit: <40-hex head the lane reviewed>
    Reviewer-Session: <the lane's session id or other reviewer identity>
    Disposition: ACCEPT | APPROVE | PASS     (the whole value; anything else withholds)
    Car: #<number>                           (train pull requests only)

Veto. For each reviewer and role, only the reviewer's latest record at the current head counts,
so a lane can correct its own record. If any such latest record does not accept, the check
fails, whatever other accepting records exist. A record bound to an older head is ignored.

Independence, and its limits. Every author of a Claude commit carries a ``Claude-Session:``
trailer naming its session. A record whose ``Reviewer-Session`` names any session that wrote a
commit on the pull request does not count, and the domain and assurance records must name two
different reviewers. All agents post as the owner's account, so the check cannot authenticate
the identity a record declares: an invented session name passes, and a commit without a
``Claude-Session:`` trailer (Codex, manual or train commits) names no writer to compare against.
The check stops an honest mistake, not a determined forger; the coordinator still verifies
independence under module 3 section 1 before merging.

Risk class. The body declares ``Risk class: R0`` to ``R3`` on one line, optionally as a list
item or in bold; a line naming several classes takes the highest. A body that declares none
fails, so a class cannot be skipped by omission, except a Dependabot pull request, which is
read as ``R2`` because ``REVIEW-01`` classes dependency bumps as ``R2``. ``R0`` and ``R1`` need
no pair here (``R1`` takes one lane under ``REVIEW-01``, which this check does not enforce).

Trains (``TRAIN-01``). On a ``train/`` branch, each commit subject ends with its car's
pull-request number. Each car needs its own pair: its lanes post their module 3 section 8
carry-forward records on the train pull request, bound to the train head, with ``Car: #<car>``.

Where it runs. The workflow triggers on ``pull_request_target``, so GitHub runs the workflow
file from ``main``, and it checks out the base commit, so the script is ``main``'s too: a pull
request cannot edit the check that judges it. No pull-request code is executed. Under
``REVIEW-01`` the lanes bind to the draft head before the pull request is marked ready, so the
job is deferred on a draft and runs on ``ready_for_review``. A record posted after the run is
read by re-running the job.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from typing import Any, Callable
from urllib.request import Request, urlopen

REVIEWED_CLASSES = frozenset({"R2", "R3"})
#: Bot authors whose pull requests are read as R2 when the body declares no class (REVIEW-01
#: classes dependency bumps as R2; a bot cannot be relied on to keep a body line).
BOT_R2_AUTHORS = frozenset({"dependabot[bot]"})
TRAIN_BRANCH_PREFIX = "train/"
ROLES = ("domain", "assurance")
ACCEPTING = frozenset({"ACCEPT", "APPROVE", "PASS"})
TRUSTED_ASSOCIATIONS = frozenset({"OWNER", "MEMBER", "COLLABORATOR"})
_PAGE_SIZE = 100

_RISK_LINE = re.compile(
    r"^[ \t]*(?:[-*+][ \t]+)?(?:\*\*|__)?Risk class:(?:\*\*|__)?([^\r\n]*)$",
    re.MULTILINE | re.IGNORECASE,
)
_RISK_TOKEN = re.compile(r"\bR([0-3])(?:_[A-Z_]+)?\b")
_MARKER = re.compile(r"^[ \t]*8<[^\n]*$", re.MULTILINE)
_DIGEST = re.compile(r"(?<![0-9a-fA-F])([0-9a-f]{64})(?![0-9a-fA-F])")
_SESSION_TRAILER = re.compile(r"^Claude-Session:[ \t]*(\S+)[ \t]*$", re.MULTILINE)
_SESSION_ID = re.compile(r"session_([A-Za-z0-9]+)", re.IGNORECASE)
_CAR_SUBJECT = re.compile(r"\(#(\d+)\)[ \t]*$")
_CAR_FIELD = re.compile(r"#?(\d+)")


def _field(block: str, name: str) -> str | None:
    """Return one header field's value from a record block, or ``None``."""
    match = re.search(
        rf"^{re.escape(name)}:[ \t]*([^\r\n]*?)[ \t]*$", block, re.MULTILINE
    )
    return match.group(1) if match else None


def _identity(value: str) -> str:
    """Reduce a session URL or label to a comparable identity."""
    found = _SESSION_ID.search(value)
    return f"session_{found.group(1)}" if found else value.strip().lower()


def risk_class(body: str) -> str | None:
    """Return the highest risk class the body declares, or ``None`` if it declares none."""
    levels = [
        int(token)
        for value in _RISK_LINE.findall(body)
        for token in _RISK_TOKEN.findall(value)
    ]
    return f"R{max(levels)}" if levels else None


def declared_class(body: str, author: str = "") -> str | None:
    """Return the class to judge: the body's, else R2 for a Dependabot pull request."""
    level = risk_class(body)
    if level is None and author in BOT_R2_AUTHORS:
        return "R2"
    return level


def train_cars(head_ref: str, commits: list[dict[str, Any]]) -> list[str]:
    """Return the car numbers of a ``TRAIN-01`` train, or ``[]`` for any other branch."""
    if not head_ref.startswith(TRAIN_BRANCH_PREFIX):
        return []
    cars: list[str] = []
    for commit in commits:
        message = ((commit.get("commit") or {}).get("message")) or ""
        found = _CAR_SUBJECT.search(message.split("\n", 1)[0])
        if found and found.group(1) not in cars:
            cars.append(found.group(1))
    return cars


def writer_sessions(commits: list[dict[str, Any]]) -> set[str]:
    """Return the session identities that wrote any commit on the pull request."""
    sessions: set[str] = set()
    for commit in commits:
        message = ((commit.get("commit") or {}).get("message")) or ""
        sessions.update(_identity(v) for v in _SESSION_TRAILER.findall(message))
    return sessions


def _blocks(text: str) -> list[str]:
    """Return the text between consecutive pairs of ``8<`` marker lines."""
    text = text.replace("\r\n", "\n")
    marks = list(_MARKER.finditer(text))
    return [
        text[marks[i].end() : marks[i + 1].start()].strip("\n") + "\n"
        for i in range(0, len(marks) - 1, 2)
    ]


def parse_record(comment: dict[str, Any]) -> tuple[dict[str, str] | None, str]:
    """Parse one comment into a record, or say why it is not one.

    Returns:
        ``(record, "")`` for a well-formed record, else ``(None, reason)``.
    """
    body = comment.get("body") or ""
    if "Review-Record:" not in body:
        return None, "not a review record"
    if comment.get("author_association") not in TRUSTED_ASSOCIATIONS:
        return None, "posted by an account that is not the owner or a collaborator"
    blocks = [b for b in _blocks(body) if "Review-Record:" in b]
    if len(blocks) != 1:
        return None, "needs exactly one record block between 8< marker lines"
    block = blocks[0]
    # The digest is stated outside the block (a block cannot state its own hash).
    outside = body.replace("\r\n", "\n").replace(block.rstrip("\n"), "")
    stated = set(_DIGEST.findall(outside))
    if hashlib.sha256(block.encode("utf-8")).hexdigest() not in stated:
        return None, "the stated SHA-256 does not match the record block's bytes"
    record: dict[str, str] = {}
    for name in (
        "Review-Record",
        "Role",
        "PR",
        "Commit",
        "Reviewer-Session",
        "Disposition",
    ):
        value = _field(block, name)
        if not value:
            return None, f"record has no `{name}:` line"
        record[name] = value
    if record["Review-Record"] != "1":
        return None, "unknown `Review-Record:` version"
    record["Role"] = record["Role"].lower()
    if record["Role"] not in ROLES:
        return None, "`Role:` must be domain or assurance"
    if not re.fullmatch(r"[0-9a-f]{40}", record["Commit"]):
        return None, "`Commit:` must be a full 40-character SHA"
    record["Disposition"] = record["Disposition"].strip().upper()
    record["Reviewer-Session"] = _identity(record["Reviewer-Session"])
    car = _field(block, "Car")
    if car is None:
        record["Car"] = ""
    else:
        found = _CAR_FIELD.fullmatch(car.strip())
        if not found:
            return None, "`Car:` must be a pull-request number"
        record["Car"] = found.group(1)
    return record, ""


def evaluate(
    body: str,
    pr_number: int,
    head_sha: str,
    commits: list[dict[str, Any]],
    comments: list[dict[str, Any]],
    *,
    author: str = "",
    head_ref: str = "",
) -> tuple[int, str]:
    """Return a fail-closed verdict for already-fetched pull request objects."""
    level = declared_class(body, author)
    if level is None:
        return 1, (
            "RECRUIT-01 (#1486): declare the risk class on a 'Risk class:' line "
            "(R0, R1, R2 or R3) in the pull request body."
        )
    if level not in REVIEWED_CLASSES:
        return (
            0,
            f"RECRUIT-01 (#1486): {level} declared; no review pair is required here.",
        )
    writers = writer_sessions(commits)
    cars = train_cars(head_ref, commits)
    if head_ref.startswith(TRAIN_BRANCH_PREFIX) and not cars:
        return 1, (
            "RECRUIT-01 (#1486): a train branch whose commit subjects name no car "
            "'(#<number>)' cannot be judged per car."
        )
    # (car, role, reviewer) -> (position, record, where); the latest record wins.
    latest: dict[tuple[str, str, str], tuple[int, dict[str, str], str]] = {}
    notes: list[str] = []
    for position, comment in enumerate(comments):
        record, reason = parse_record(comment)
        where = f"comment {comment.get('id')}"
        if record is None:
            if reason != "not a review record":
                notes.append(f"{where}: {reason}")
            continue
        if record["PR"].lstrip("#") != str(pr_number):
            notes.append(f"{where}: bound to {record['PR']}, not #{pr_number}")
        elif record["Commit"] != head_sha:
            notes.append(
                f"{where}: bound to {record['Commit'][:12]}, not head {head_sha[:12]}"
            )
        elif record["Reviewer-Session"] in writers:
            notes.append(
                f"{where}: reviewer {record['Reviewer-Session']} wrote a commit here"
            )
        elif cars and record["Car"] not in cars:
            notes.append(f"{where}: a train record must name one of the cars {cars}")
        elif not cars and record["Car"]:
            notes.append(f"{where}: `Car:` is only for train pull requests")
        else:
            key = (record["Car"], record["Role"], record["Reviewer-Session"])
            latest[key] = (position, record, where)
    vetoes = [
        f"{where} ({record['Role']} {record['Reviewer-Session']}: "
        f"{record['Disposition']})"
        for _, record, where in sorted(latest.values(), key=lambda item: item[0])
        if record["Disposition"] not in ACCEPTING
    ]
    if vetoes:
        return 1, (
            f"RECRUIT-01 (#1486): {level} head {head_sha[:12]} carries a withheld "
            f"acceptance, and one veto blocks acceptance (module 3 section 1): "
            f"{'; '.join(vetoes)}."
        )
    passed: list[str] = []
    missing: list[str] = []
    for car in cars or [""]:
        accepted = {
            role: {
                reviewer
                for (unit, kind, reviewer) in latest
                if unit == car and kind == role
            }
            for role in ROLES
        }
        pair = [
            (domain, assurance)
            for domain in sorted(accepted["domain"])
            for assurance in sorted(accepted["assurance"])
            if domain != assurance
        ]
        label = f"car #{car} " if car else ""
        if pair:
            passed.append(f"{label}domain {pair[0][0]}, assurance {pair[0][1]}")
        else:
            lacking = [role for role in ROLES if not accepted[role]] or [
                "two distinct reviewers"
            ]
            missing.append(f"{label}{', '.join(lacking)}")
    if not missing:
        return 0, (
            f"RECRUIT-01 (#1486): {level} pair on head {head_sha[:12]}: "
            f"{'; '.join(passed)}."
        )
    detail = "; ".join(notes) if notes else "no review record found"
    return 1, (
        f"RECRUIT-01 (#1486): {level} needs an accepting domain and assurance record "
        f"bound to head {head_sha} by reviewers who did not write it. Missing: "
        f"{'; '.join(missing)}. {detail}."
    )


def _get_json(repository: str, path: str, token: str) -> Any:
    """Read GitHub REST JSON with a bounded request; errors fail the check."""
    request = Request(
        f"https://api.github.com/repos/{repository}/{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "dutchbay-pr-review-pair-check",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urlopen(request, timeout=15) as response:  # nosec B310 - fixed https host
        return json.load(response)


def _all_pages(fetch: Callable[[int], Any]) -> list[dict[str, Any]]:
    """Read every page of a list endpoint until a short page."""
    items: list[dict[str, Any]] = []
    page = 1
    while True:
        batch = fetch(page)
        if not isinstance(batch, list):
            raise ValueError(f"page {page} is not a list")
        items.extend(batch)
        if len(batch) < _PAGE_SIZE:
            return items
        page += 1


def main() -> int:
    """Read the pull request from the Actions environment and print the verdict."""
    body = os.environ.get("PR_BODY", "")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    head_sha = os.environ.get("PR_HEAD_SHA", "")
    author = os.environ.get("PR_AUTHOR", "")
    head_ref = os.environ.get("PR_HEAD_REF", "")
    try:
        pr_number = int(os.environ.get("PR_NUMBER", ""))
    except ValueError:
        print("RECRUIT-01 (#1486): PR_NUMBER is missing.", file=sys.stderr)
        return 1
    level = declared_class(body, author)
    if level is not None and level not in REVIEWED_CLASSES:
        code, message = evaluate(body, pr_number, head_sha, [], [], author=author)
        print(message)
        return code
    if not (repository and token and re.fullmatch(r"[0-9a-f]{40}", head_sha)):
        print(
            "RECRUIT-01 (#1486): repository, token or head SHA missing.",
            file=sys.stderr,
        )
        return 1
    try:
        commits = _all_pages(
            lambda p: _get_json(
                repository,
                f"pulls/{pr_number}/commits?per_page={_PAGE_SIZE}&page={p}",
                token,
            )
        )
        comments = _all_pages(
            lambda p: _get_json(
                repository,
                f"issues/{pr_number}/comments?per_page={_PAGE_SIZE}&page={p}",
                token,
            )
        )
    except Exception as exc:  # noqa: BLE001 - any read failure blocks the merge
        print(
            f"RECRUIT-01 (#1486): could not read the pull request: {exc}",
            file=sys.stderr,
        )
        return 1
    code, message = evaluate(
        body,
        pr_number,
        head_sha,
        commits,
        comments,
        author=author,
        head_ref=head_ref,
    )
    print(message, file=sys.stderr if code else sys.stdout)
    return code


if __name__ == "__main__":
    sys.exit(main())
