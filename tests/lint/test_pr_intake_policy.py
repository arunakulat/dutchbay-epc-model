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
TRACKER = {"number": 1353, "body": "Current work: #1354"}
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
        "created_at": "2026-10-12T07:00:00Z",
        "pr_number": 1355,
        "issue": ISSUE,
        "tracker": TRACKER,
        "open_prs": OPEN_PRS,
    }
    arguments.update(kwargs)
    return check.evaluate(**arguments)


def test_valid_scoped_record_and_complete_sweep_pass() -> None:
    assert _evaluate(_body())[0] == 0


@pytest.mark.parametrize(
    "body, expected",
    [
        (_body().replace("Work item: #1354", ""), "Work item"),
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
        issue={**ISSUE, "body": "No parent"},
        tracker={**TRACKER, "body": "No child"},
    )
    assert code == 1
    assert "not cross-linked" in message


def test_issue_created_after_human_pr_fails() -> None:
    code, message = _evaluate(
        _body(), issue={**ISSUE, "created_at": "2026-10-12T08:00:00Z"}
    )
    assert code == 1
    assert "after this human/agent PR" in message


def test_bot_pr_requires_triage_but_can_link_issue_after_creation() -> None:
    late_issue = {**ISSUE, "created_at": "2026-10-12T08:00:00Z"}
    assert _evaluate("", author="dependabot[bot]", issue=late_issue)[0] == 1
    assert _evaluate(_body(), author="dependabot[bot]", issue=late_issue)[0] == 0


def test_pull_request_number_cannot_be_work_item() -> None:
    code, message = _evaluate(_body(), issue={**ISSUE, "pull_request": {"url": "x"}})
    assert code == 1
    assert "GitHub issue" in message


def test_exact_issue_references_do_not_match_larger_numbers() -> None:
    assert not check._references("#13540 /issues/13540", 1354)
    assert check._references("See #1354", 1354)


def test_workflow_keeps_required_job_and_uses_env_for_untrusted_body() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    parsed = yaml.safe_load(workflow)
    assert parsed["jobs"]["receipts"]["name"] == "Verification receipts (VERIFY-01)"
    assert "run: python scripts/ci/check_pr_intake.py" in workflow
    assert parsed["permissions"]["issues"] == "read"
    assert parsed["permissions"]["pull-requests"] == "read"
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
