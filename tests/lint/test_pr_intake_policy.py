"""Pin the tracker-first PR check and its negative controls."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/ci/check_pr_intake.py"
WORKFLOW = ROOT / ".github/workflows/pr-receipts.yml"
TEMPLATE = ROOT / ".github/pull_request_template.md"


def _load() -> Any:
    spec = importlib.util.spec_from_file_location("check_pr_intake", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check = _load()
BASE = "a" * 40
ISSUE = {
    "number": 1354,
    "body": "Parent tracker: #1353",
    "created_at": "2026-10-12T06:00:00Z",
}
TRACKER = {"number": 1353, "body": "The roadmap index."}
TRACKER_COMMENTS = [
    {
        "id": 6119665269,
        "body": "Intake recorded before edits: #1354 is the tracker-first rule.",
        "created_at": "2026-10-12T06:30:00Z",
        "user": {"login": "arunakulat", "type": "User"},
    }
]
DIRECT_COMMENT = {
    "id": 6119665270,
    "body": "Work item: Add a strict F-03 schema preflight.\nDone when: Invalid profiles fail before evaluation.",
    "issue_url": "https://api.github.com/repos/arunakulat/dutchbay-epc-model/issues/1353",
    "created_at": "2026-10-12T06:30:00Z",
    "user": {"login": "arunakulat", "type": "User"},
}
OPEN_PRS = [{"number": 1346}, {"number": 1355}]


def _body(sweep: str = "#1346 blocked; revisit bitarray 3.12.1") -> str:
    return (
        "Work item: #1354\n"
        f"Base SHA: {BASE}\n"
        f"Open PR sweep: {sweep}\n"
        "Recorded before edits: #1354 on 2026-10-12\n"
    )


def _evaluate(body: str, **kwargs: Any) -> tuple[int, str]:
    arguments = {
        "body": body,
        "author": "human",
        "author_type": "User",
        "created_at": "2026-10-12T07:00:00Z",
        "pr_number": 1355,
        "issue": ISSUE,
        "tracker": TRACKER,
        "tracker_comments": TRACKER_COMMENTS,
        "work_comment": None,
        "open_prs": OPEN_PRS,
    }
    arguments.update(kwargs)
    return check.evaluate(**arguments)


def test_valid_scoped_record_and_complete_sweep_pass() -> None:
    assert _evaluate(_body())[0] == 0


def test_duplicate_work_items_fail() -> None:
    assert _evaluate(_body() + "Work item: #1354\n")[0] == 1


@pytest.mark.parametrize(
    "old,new",
    [
        ("Work item: #1354", "Work item:\n#1354"),
        (f"Base SHA: {BASE}", f"Base SHA:\n{BASE}"),
        (
            "Open PR sweep: #1346 blocked; revisit bitarray 3.12.1",
            "Open PR sweep:\n#1346 blocked; revisit bitarray 3.12.1",
        ),
        ("Recorded before edits: #1354", "Recorded before edits:\n#1354"),
    ],
)
def test_blank_pr_field_cannot_borrow_next_line(old: str, new: str) -> None:
    assert _evaluate(_body().replace(old, new))[0] == 1


@pytest.mark.parametrize(
    "body, expected",
    [
        (_body().replace("Work item: #1354", ""), "name one focused issue"),
        (_body().replace("Work item: #1354", "Work item: #1353"), "generic index"),
        (_body().replace(f"Base SHA: {BASE}", "Base SHA: short"), "Base SHA"),
        (
            _body().replace(
                "Open PR sweep: #1346 blocked; revisit bitarray 3.12.1",
                "Open PR sweep: none",
            ),
            "omits #1346",
        ),
        (
            _body().replace(
                "Recorded before edits: #1354", "Recorded before edits: #1353"
            ),
            "Recorded before edits",
        ),
    ],
)
def test_missing_or_generic_intake_fails(body: str, expected: str) -> None:
    code, message = _evaluate(body)
    assert code == 1
    assert expected in message


def test_unlinked_issue_fails() -> None:
    code, message = _evaluate(
        _body(),
        issue={**ISSUE, "body": "Parent tracker: #1353"},
        tracker_comments=[],
    )
    assert code == 1
    assert "not recorded on tracker" in message


def test_malformed_issue_url_does_not_link_to_tracker() -> None:
    code, message = _evaluate(
        _body(),
        tracker={**TRACKER, "body": "See /issues/1354abc"},
        tracker_comments=[],
    )
    assert code == 1
    assert "not recorded on tracker" in message


def test_tracker_comment_added_after_human_pr_fails() -> None:
    late = [{**TRACKER_COMMENTS[0], "created_at": "2026-10-12T08:00:00Z"}]
    code, message = _evaluate(_body(), tracker_comments=late)
    assert code == 1
    assert "tracker link was added after" in message


def test_issue_created_after_human_pr_fails() -> None:
    code, message = _evaluate(
        _body(), issue={**ISSUE, "created_at": "2026-10-12T08:00:00Z"}
    )
    assert code == 1
    assert "after this human/agent PR" in message


def test_bot_pr_requires_triage_but_can_link_issue_after_creation() -> None:
    late_issue = {**ISSUE, "created_at": "2026-10-12T08:00:00Z"}
    assert (
        _evaluate("", author="dependabot[bot]", author_type="Bot", issue=late_issue)[0]
        == 1
    )
    assert (
        _evaluate(
            _body(),
            author="dependabot[bot]",
            author_type="Bot",
            issue=late_issue,
            tracker_comments=[],
        )[0]
        == 1
    )
    bot_only = [
        {
            **TRACKER_COMMENTS[0],
            "user": {"login": "dependabot[bot]", "type": "Bot"},
        }
    ]
    assert (
        _evaluate(
            _body(),
            author="dependabot[bot]",
            author_type="Bot",
            issue=late_issue,
            tracker_comments=bot_only,
        )[0]
        == 1
    )
    assert (
        _evaluate(
            _body(), author="dependabot[bot]", author_type="Bot", issue=late_issue
        )[0]
        == 1
    )
    triage = [
        {
            **TRACKER_COMMENTS[0],
            "body": "Human triage of bot PR #1355 for focused issue #1354; proceed after checks.",
            "created_at": "2026-10-12T08:30:00Z",
        }
    ]
    assert (
        _evaluate(
            _body(),
            author="dependabot[bot]",
            author_type="Bot",
            issue=late_issue,
            tracker_comments=triage,
        )[0]
        == 0
    )


def test_unlisted_bot_does_not_take_human_path() -> None:
    code, message = _evaluate(_body(), author="snyk[bot]", author_type="Bot")
    assert code == 1
    assert "bot PR needs" in message


def test_scoped_direct_tracker_comment_passes_without_child_issue() -> None:
    url = "https://github.com/arunakulat/dutchbay-epc-model/issues/1353#issuecomment-6119665270"
    body = (
        _body()
        .replace("Work item: #1354", f"Work item: {url}")
        .replace("Recorded before edits: #1354", f"Recorded before edits: {url}")
    )
    code, message = _evaluate(body, issue=None, work_comment=DIRECT_COMMENT)
    assert code == 0, message
    assert "tracker comment" in message


@pytest.mark.parametrize(
    "comment",
    [
        {
            **DIRECT_COMMENT,
            "issue_url": "https://api.github.com/repos/example/repo/issues/1",
        },
        {
            **DIRECT_COMMENT,
            "issue_url": "https://api.github.com/repos/example/repo/issues/1353",
        },
        {**DIRECT_COMMENT, "body": "hello"},
        {**DIRECT_COMMENT, "user": {"login": "dependabot[bot]", "type": "Bot"}},
    ],
)
def test_wrong_unscoped_or_bot_direct_comment_fails(comment: dict[str, Any]) -> None:
    url = "https://github.com/arunakulat/dutchbay-epc-model/issues/1353#issuecomment-6119665270"
    body = (
        _body()
        .replace("Work item: #1354", f"Work item: {url}")
        .replace("Recorded before edits: #1354", f"Recorded before edits: {url}")
    )
    assert _evaluate(body, issue=None, work_comment=comment)[0] == 1


def test_generic_direct_comment_fails() -> None:
    url = "https://github.com/arunakulat/dutchbay-epc-model/issues/1353#issuecomment-6119665270"
    body = (
        _body()
        .replace("Work item: #1354", f"Work item: {url}")
        .replace("Recorded before edits: #1354", f"Recorded before edits: {url}")
    )
    generic = {
        **DIRECT_COMMENT,
        "body": "Work item: TBD - select later after development starts.\nDone when: TBD later",
    }
    assert _evaluate(body, issue=None, work_comment=generic)[0] == 1


def test_blank_direct_deliverable_cannot_borrow_done_when_line() -> None:
    url = "https://github.com/arunakulat/dutchbay-epc-model/issues/1353#issuecomment-6119665270"
    body = (
        _body()
        .replace("Work item: #1354", f"Work item: {url}")
        .replace("Recorded before edits: #1354", f"Recorded before edits: {url}")
    )
    blank = {
        **DIRECT_COMMENT,
        "body": "Work item:\nDone when: Invalid profiles fail before evaluation.",
    }
    assert _evaluate(body, issue=None, work_comment=blank)[0] == 1


def test_bot_direct_comment_must_name_the_new_pr() -> None:
    url = "https://github.com/arunakulat/dutchbay-epc-model/issues/1353#issuecomment-6119665270"
    body = (
        _body()
        .replace("Work item: #1354", f"Work item: {url}")
        .replace("Recorded before edits: #1354", f"Recorded before edits: {url}")
    )
    assert (
        _evaluate(
            body,
            author="snyk[bot]",
            author_type="Bot",
            issue=None,
            work_comment=DIRECT_COMMENT,
        )[0]
        == 1
    )
    triage = {
        **DIRECT_COMMENT,
        "body": DIRECT_COMMENT["body"]
        + "\nTriage: PR #1355 was reviewed by a non-bot actor.",
        "created_at": "2026-10-12T08:30:00Z",
    }
    assert (
        _evaluate(
            body, author="snyk[bot]", author_type="Bot", issue=None, work_comment=triage
        )[0]
        == 0
    )


def test_direct_comment_created_after_human_pr_fails() -> None:
    url = "https://github.com/arunakulat/dutchbay-epc-model/issues/1353#issuecomment-6119665270"
    body = (
        _body()
        .replace("Work item: #1354", f"Work item: {url}")
        .replace("Recorded before edits: #1354", f"Recorded before edits: {url}")
    )
    late = {**DIRECT_COMMENT, "created_at": "2026-10-12T08:00:00Z"}
    assert _evaluate(body, issue=None, work_comment=late)[0] == 1


def test_pull_request_number_cannot_be_work_item() -> None:
    code, message = _evaluate(_body(), issue={**ISSUE, "pull_request": {"url": "x"}})
    assert code == 1
    assert "GitHub issue" in message


def test_exact_issue_references_do_not_match_larger_numbers() -> None:
    assert not check._references("#13540 /issues/13540", 1354)
    assert not check._references("/issues/1354abc", 1354)
    assert check._references("See #1354", 1354)


def test_workflow_keeps_required_job_and_uses_env_for_untrusted_body() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    parsed = yaml.safe_load(workflow)
    assert parsed["jobs"]["receipts"]["name"] == "Verification receipts (VERIFY-01)"
    assert parsed["jobs"]["intake"]["name"] == "Verification intake (INTAKE-01)"
    intake_steps = parsed["jobs"]["intake"]["steps"]
    intake_run_steps = [
        step
        for step in intake_steps
        if "python scripts/ci/check_pr_intake.py" in step.get("run", "")
    ]
    assert len(intake_run_steps) == 1
    intake_env = intake_run_steps[0].get("env", {})
    for key in (
        "PR_BODY",
        "PR_AUTHOR",
        "PR_AUTHOR_TYPE",
        "PR_CREATED_AT",
        "PR_NUMBER",
        "GITHUB_TOKEN",
        "GITHUB_REPOSITORY",
    ):
        assert key in intake_env, f"intake job step missing env key {key!r}"
    assert "run: python scripts/ci/check_pr_intake.py" in workflow
    assert parsed["permissions"]["issues"] == "read"
    assert parsed["permissions"]["pull-requests"] == "read"
    assert "PR_AUTHOR_TYPE: ${{ github.event.pull_request.user.type }}" in workflow
    assert workflow.count("PR_BODY: ${{ github.event.pull_request.body }}") == 2
    assert "run: ${{ github.event.pull_request.body }}" not in workflow
    template = TEMPLATE.read_text(encoding="utf-8")
    for label in (
        "Work item:",
        "Base SHA:",
        "Open PR sweep:",
        "Recorded before edits:",
    ):
        assert label in template


# INTAKE-01 asks for the sweep "before opening a PR": a PR opened after this one is not
# required in this one's sweep (its own sweep names this one). Before this, each new PR
# failed every older PR's intake on its next run.
_THIS_PR_OPENED = "2026-10-12T07:00:00Z"


@pytest.mark.parametrize(
    "later, required",
    [
        ({"number": 1360, "created_at": "2026-10-12T09:00:00Z"}, False),
        ({"number": 1360, "created_at": "2026-10-12T06:59:59Z"}, True),
        ({"number": 1360, "created_at": _THIS_PR_OPENED}, True),
        ({"number": 1360}, True),
        ({"number": 1360, "created_at": "not a time"}, True),
    ],
)
def test_sweep_requires_only_prs_open_when_this_one_opened(
    later: dict[str, Any], required: bool
) -> None:
    code, message = _evaluate(_body(), open_prs=[*OPEN_PRS, later])
    if required:
        assert code == 1 and "omits #1360" in message
    else:
        assert code == 0, message


def test_unreadable_own_creation_time_requires_every_open_pr() -> None:
    later = {"number": 1360, "created_at": "2026-10-12T09:00:00Z"}
    assert check._sweep_omissions("#1346", [*OPEN_PRS, later], 1355, "") == [1360]
    assert (
        check._sweep_omissions("#1346", [*OPEN_PRS, later], 1355, _THIS_PR_OPENED) == []
    )


def test_main_ignores_prs_opened_later(monkeypatch: pytest.MonkeyPatch) -> None:
    """The live path applies the same rule to the GitHub open-PR list."""
    pulls = [
        {"number": 1346, "created_at": "2026-10-12T05:00:00Z"},
        {"number": 1355, "created_at": _THIS_PR_OPENED},
        {"number": 1360, "created_at": "2026-10-12T09:00:00Z"},
    ]
    tracker = {**TRACKER, "comments": len(TRACKER_COMMENTS)}
    events: list[dict[str, Any]] = [
        {"event": "labeled", "created_at": "2026-10-12T07:05:00Z"},
        {"event": "closed", "created_at": "2026-10-12T08:00:00Z"},
    ]

    def fake_get_json(repository: str, path: str, token: str) -> Any:
        if path.startswith("pulls?"):
            return pulls
        if path.startswith("issues/1355/events"):
            return events
        if path.startswith("issues/1353/comments"):
            return TRACKER_COMMENTS
        if path == "issues/1353":
            return tracker
        if path == "issues/1354":
            return ISSUE
        raise AssertionError(path)

    monkeypatch.setattr(check, "_get_json", fake_get_json)
    for key, value in {
        "PR_BODY": _body(),
        "GITHUB_REPOSITORY": "arunakulat/dutchbay-epc-model",
        "GITHUB_TOKEN": "token",
        "PR_NUMBER": "1355",
        "PR_AUTHOR": "human",
        "PR_AUTHOR_TYPE": "User",
        "PR_CREATED_AT": _THIS_PR_OPENED,
    }.items():
        monkeypatch.setenv(key, value)
    assert check.main() == 0
    # Reopened after #1360 opened: #1360 is now required (#1877).
    events.append({"event": "reopened", "created_at": "2026-10-12T10:00:00Z"})
    assert check.main() == 1
    events.pop()
    pulls[2]["created_at"] = "2026-10-12T06:00:00Z"
    assert check.main() == 1


@pytest.mark.parametrize(
    "events, expected",
    [
        ([], _THIS_PR_OPENED),
        ([{"event": "closed", "created_at": "2026-10-12T08:00:00Z"}], _THIS_PR_OPENED),
        (
            [
                {"event": "reopened", "created_at": "2026-10-12T08:00:00Z"},
                {"event": "reopened", "created_at": "2026-10-12T10:00:00Z"},
                {"event": "reopened", "created_at": "2026-10-12T09:00:00Z"},
            ],
            "2026-10-12T10:00:00Z",
        ),
        (
            [{"event": "reopened", "created_at": "2026-10-12T06:00:00Z"}],
            _THIS_PR_OPENED,
        ),
        ([{"event": "reopened", "created_at": "not a time"}], ""),
        ([{"event": "reopened"}], ""),
    ],
)
def test_last_opened_uses_the_latest_reopen(
    events: list[dict[str, Any]], expected: str
) -> None:
    assert check._last_opened(_THIS_PR_OPENED, events) == expected


def test_last_opened_keeps_an_unreadable_creation_time() -> None:
    reopened = [{"event": "reopened", "created_at": "2026-10-12T10:00:00Z"}]
    assert check._last_opened("", reopened) == ""
