"""The intake check reads every tracker comment it needs, past 1,000 comments (#1418).

The check used to read #1353's comments oldest page first and fail closed after ten
100-comment pages. #1353 passed 600 comments on 2026-11-15 and was gaining about 25 an
hour, so every PR's intake check was about to fail. The scan now reads newest page
first, stops at the first passing verdict, and otherwise reads every page the tracker's
own comment count names before failing.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Dict, List

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/ci/check_pr_intake.py"

REPOSITORY = "arunakulat/dutchbay-epc-model"
WORK_ISSUE = 1800
PR_NUMBER = 1801
PR_CREATED_AT = "2026-11-15T03:00:00Z"
OPEN_PRS = [{"number": 1692}, {"number": PR_NUMBER}]


def _load() -> Any:
    spec = importlib.util.spec_from_file_location("check_pr_intake_1418", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check = _load()


def _comment(index: int, body: str = "queue heartbeat", **extra: Any) -> Dict[str, Any]:
    comment = {
        "id": 7_000_000_000 + index,
        "body": body,
        "created_at": f"2026-11-{1 + index // 100:02d}T{index % 24:02d}:00:00Z",
        "user": {"login": "arunakulat", "type": "User"},
    }
    comment.update(extra)
    return comment


def _intake(index: int, created_at: str = "2026-11-15T02:50:00Z") -> Dict[str, Any]:
    return _comment(
        index,
        f"INTAKE-01: #{WORK_ISSUE} recorded before edits.",
        created_at=created_at,
    )


def _body() -> str:
    return (
        f"Work item: #{WORK_ISSUE}\n"
        f"Base SHA: {'a' * 40}\n"
        "Open PR sweep: #1692 disjoint\n"
        f"Recorded before edits: #{WORK_ISSUE}\n"
    )


class FakeGitHub:
    """Serve the tracker, the work item and the open PRs, and count comment pages."""

    def __init__(
        self,
        comments: List[Dict[str, Any]],
        *,
        tracker_body: str = "The roadmap index.",
        comment_count: Any = None,
        work_comment: Dict[str, Any] | None = None,
    ) -> None:
        self.comments = comments
        self.tracker = {
            "number": 1353,
            "body": tracker_body,
            "comments": len(comments) if comment_count is None else comment_count,
        }
        self.work_comment = work_comment
        self.pages_read: List[int] = []
        self.tracker_issue_read = False
        self.paths: List[str] = []

    def __call__(self, repository: str, path: str, token: str) -> Any:
        assert repository == REPOSITORY and token == "token"
        self.paths.append(path)
        if path == f"issues/{WORK_ISSUE}":
            return {"number": WORK_ISSUE, "created_at": "2026-11-15T02:40:00Z"}
        if path.startswith("issues/comments/"):
            return self.work_comment
        if path == "issues/1353":
            self.tracker_issue_read = True
            return self.tracker
        if path.startswith("issues/1353/comments?"):
            query = dict(part.split("=") for part in path.split("?", 1)[1].split("&"))
            assert query["per_page"] == "100"
            page = int(query["page"])
            self.pages_read.append(page)
            return self.comments[(page - 1) * 100 : page * 100]
        if path.startswith("pulls?state=open"):
            return OPEN_PRS if path.endswith("page=1") else []
        raise AssertionError(f"unexpected path {path}")


def _run(
    monkeypatch: pytest.MonkeyPatch,
    fake: FakeGitHub,
    capsys: pytest.CaptureFixture[str],
    *,
    body: str | None = None,
    author: str = "claude",
    author_type: str = "User",
) -> tuple[int, str]:
    monkeypatch.setattr(check, "_get_json", fake)
    for key, value in {
        "PR_BODY": _body() if body is None else body,
        "PR_AUTHOR": author,
        "PR_AUTHOR_TYPE": author_type,
        "PR_CREATED_AT": PR_CREATED_AT,
        "PR_NUMBER": str(PR_NUMBER),
        "GITHUB_REPOSITORY": REPOSITORY,
        "GITHUB_TOKEN": "token",
    }.items():
        monkeypatch.setenv(key, value)
    code = check.main()
    return code, capsys.readouterr().out


def _tracker(total: int, records: Dict[int, Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [records.get(i, _comment(i)) for i in range(total)]


def test_record_on_the_newest_page_passes_past_1000_comments(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Negative control: the ten-page scan failed this PR with "exceed bounded ten-page"."""
    fake = FakeGitHub(_tracker(1250, {1249: _intake(1249)}))
    code, out = _run(monkeypatch, fake, capsys)
    assert code == 0, out
    assert "ten-page" not in out
    assert fake.pages_read == [13]


def test_record_on_the_oldest_page_is_still_found(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeGitHub(_tracker(1250, {3: _intake(3)}))
    code, out = _run(monkeypatch, fake, capsys)
    assert code == 0, out
    assert fake.pages_read == list(range(13, 0, -1))


def test_missing_record_fails_only_after_every_page_is_read(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeGitHub(_tracker(1250, {}))
    code, out = _run(monkeypatch, fake, capsys)
    assert code == 1
    assert "not recorded on tracker #1353" in out
    assert fake.pages_read == list(range(13, 0, -1))


def test_a_late_link_does_not_hide_an_earlier_one(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The newest page alone says "added after this PR"; the scan keeps reading."""
    late = _intake(1249, created_at="2026-11-15T04:00:00Z")
    fake = FakeGitHub(_tracker(1250, {1249: late, 40: _intake(40)}))
    code, out = _run(monkeypatch, fake, capsys)
    assert code == 0, out
    assert fake.pages_read == list(range(13, 0, -1))


def test_only_a_late_link_still_fails(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    late = _intake(1249, created_at="2026-11-15T04:00:00Z")
    fake = FakeGitHub(_tracker(1250, {1249: late}))
    code, out = _run(monkeypatch, fake, capsys)
    assert code == 1
    assert "tracker link was added after this PR" in out


def test_bot_triage_on_the_newest_page_passes(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    triage = _comment(
        1249,
        f"Triage: #{PR_NUMBER} is Dependabot's bump for #{WORK_ISSUE}.",
        created_at="2026-11-15T03:30:00Z",
    )
    fake = FakeGitHub(_tracker(1250, {1249: triage}))
    code, out = _run(
        monkeypatch, fake, capsys, author="dependabot[bot]", author_type="Bot"
    )
    assert code == 0, out
    assert fake.pages_read == [13]


def test_a_tracker_body_link_reads_no_comment_page(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeGitHub(_tracker(1250, {}), tracker_body=f"Index: #{WORK_ISSUE}")
    code, out = _run(monkeypatch, fake, capsys)
    assert code == 0, out
    assert fake.pages_read == []


def test_a_direct_tracker_comment_reads_no_comment_page(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    direct = _comment(
        5,
        "Work item: Lift the intake scan bound.\nDone when: PRs pass past 1,000 comments.",
        created_at="2026-11-15T02:50:00Z",
        issue_url=f"https://api.github.com/repos/{REPOSITORY}/issues/1353",
    )
    body = (
        _body()
        .replace(
            f"Work item: #{WORK_ISSUE}",
            f"Work item: https://github.com/{REPOSITORY}/issues/1353"
            f"#issuecomment-{direct['id']}",
        )
        .replace(
            f"Recorded before edits: #{WORK_ISSUE}",
            f"Recorded before edits: issuecomment-{direct['id']}",
        )
    )
    fake = FakeGitHub(_tracker(1250, {}), work_comment=direct)
    code, out = _run(monkeypatch, fake, capsys, body=body)
    assert code == 0, out
    assert not fake.tracker_issue_read
    assert fake.pages_read == []


@pytest.mark.parametrize("count", [None, -1, True, "616", 6.5])
def test_a_missing_or_invalid_comment_count_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    count: Any,
) -> None:
    fake = FakeGitHub(_tracker(1250, {1249: _intake(1249)}))
    fake.tracker["comments"] = count
    code, out = _run(monkeypatch, fake, capsys)
    assert code == 1
    assert "tracker comment count is missing or invalid" in out
    assert fake.pages_read == []


def test_a_non_list_page_fails_closed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class RateLimited(FakeGitHub):
        def __call__(self, repository: str, path: str, token: str) -> Any:
            if path.startswith("issues/1353/comments?"):
                return {"message": "rate limited"}
            return super().__call__(repository, path, token)

    code, out = _run(monkeypatch, RateLimited(_tracker(250, {})), capsys)
    assert code == 1
    assert "tracker comment page 3 is not a list" in out


def test_an_empty_tracker_reads_no_page_and_fails_unlinked(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeGitHub([])
    code, out = _run(monkeypatch, fake, capsys)
    assert code == 1
    assert "not recorded on tracker #1353" in out
    assert fake.pages_read == []
    assert not any(path.startswith("pulls?") for path in fake.paths)


def test_malformed_static_body_fails_fast_without_api_calls(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeGitHub(_tracker(10, {9: _intake(9)}))
    bad_body = _body().replace(f"Base SHA: {'a' * 40}", "Base SHA: short")
    code, out = _run(monkeypatch, fake, capsys, body=bad_body)
    assert code == 1
    assert "Base SHA" in out
    assert fake.paths == []
