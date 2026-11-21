"""Pin the independent-review-pair check (#1486) and its negative controls.

Owner decision on #1486, 2026-11-21: an R2 or R3 pull request is not green until a domain
record and an assurance record, each bound to its exact head, are on it, and neither comes from
the head's writer. These tests exercise ``scripts/ci/check_pr_review_pair.py`` on crafted
objects, including the three controls the decision names (a stale-head record, a
writer-authored record and a missing pair), and pin the workflow that runs it.
"""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/ci/check_pr_review_pair.py"
WORKFLOW = ROOT / ".github/workflows/pr-review-pair.yml"
TEMPLATE = ROOT / ".github/pull_request_template.md"


def _load() -> Any:
    spec = importlib.util.spec_from_file_location("check_pr_review_pair", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check = _load()
PR = 1900
HEAD = "c" * 40
OLD_HEAD = "b" * 40
WRITER = "session_WRITER0000000000000000"
DOMAIN = "session_DOMAIN0000000000000000"
ASSURANCE = "session_ASSURE0000000000000000"
BODY = "## Summary\nA change.\n\nRisk class: **R2**. Lanes bind to the draft head.\n"
COMMITS = [
    {
        "commit": {
            "message": "feat: a change (#1900)\n\nCo-Authored-By: Claude\n"
            f"Claude-Session: https://claude.ai/code/{WRITER}\n"
        }
    },
    {"commit": {"message": "Merge branch 'main' into feature"}},
]


def _record(
    role: str,
    reviewer: str,
    *,
    commit: str = HEAD,
    pr: int = PR,
    disposition: str = "ACCEPT",
    association: str = "OWNER",
    digest: str | None = None,
    comment_id: int = 1,
) -> dict[str, Any]:
    block = (
        f"PR #{pr} {role.upper()} review record\n"
        "Review-Record: 1\n"
        f"Role: {role}\n"
        f"PR: #{pr}\n"
        f"Commit: {commit}\n"
        f"Reviewer-Session: {reviewer}\n"
        f"Disposition: {disposition}\n"
        "\nFindings: none blocking.\n"
    )
    stated = digest or hashlib.sha256(block.encode()).hexdigest()
    return {
        "id": comment_id,
        "author_association": association,
        "body": f"**{role} lane record**, sha256 `{stated}`.\n\n8<\n{block}8<\n\n---\n_footer_",
    }


def _pair(**overrides: Any) -> list[dict[str, Any]]:
    return [
        _record("domain", DOMAIN, comment_id=1, **overrides),
        _record("assurance", ASSURANCE, comment_id=2, **overrides),
    ]


def _verdict(
    comments: list[dict[str, Any]], body: str = BODY, commits: Any = None
) -> tuple[int, str]:
    result: tuple[int, str] = check.evaluate(
        body, PR, HEAD, COMMITS if commits is None else commits, comments
    )
    return result


def test_an_accepting_pair_on_the_head_passes() -> None:
    """The positive case: both roles, bound to the head, from two non-writers."""
    code, message = _verdict(_pair())
    assert code == 0, message
    assert DOMAIN in message and ASSURANCE in message


@pytest.mark.parametrize(
    ("comments", "expected"),
    [
        pytest.param([], "no review record found", id="missing pair"),
        pytest.param(_pair()[:1], "assurance", id="assurance missing"),
        pytest.param(_pair()[1:], "domain", id="domain missing"),
        pytest.param(_pair(commit=OLD_HEAD), "not head", id="stale head"),
        pytest.param(
            [_record("domain", DOMAIN), _record("assurance", WRITER, comment_id=2)],
            "wrote a commit here",
            id="writer-authored assurance record",
        ),
        pytest.param(
            [_record("domain", f"https://claude.ai/code/{WRITER}"), _pair()[1]],
            "wrote a commit here",
            id="writer named by session URL",
        ),
        pytest.param(
            [_record("domain", DOMAIN), _record("assurance", DOMAIN, comment_id=2)],
            "two distinct reviewers",
            id="one reviewer fills both roles",
        ),
        pytest.param(
            _pair(disposition="REJECT"), "does not accept", id="rejecting pair"
        ),
        pytest.param(_pair(pr=PR + 1), "not #1900", id="record for another PR"),
        pytest.param(
            _pair(association="NONE"), "not the owner or a collaborator", id="outsider"
        ),
        pytest.param(_pair(digest="0" * 64), "SHA-256 does not match", id="bad digest"),
    ],
)
def test_the_check_refuses(comments: list[dict[str, Any]], expected: str) -> None:
    """VERIFY-01(5): each refusal is observed firing, not assumed."""
    code, message = _verdict(comments)
    assert code == 1
    assert expected in message, message


def test_an_edited_record_breaks_its_digest() -> None:
    """A record changed after its digest was stated no longer counts."""
    comments = _pair()
    comments[1]["body"] = comments[1]["body"].replace("none blocking", "one blocking")
    code, message = _verdict(comments)
    assert code == 1 and "SHA-256 does not match" in message


def test_crlf_bodies_are_read_as_lf() -> None:
    """GitHub may return CRLF line endings; the digest is over LF bytes."""
    comments = [{**c, "body": c["body"].replace("\n", "\r\n")} for c in _pair()]
    assert _verdict(comments)[0] == 0


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("Risk class: **R2**.", "R2"),
        ("Risk class: R3_CONSEQUENTIAL", "R3"),
        (
            "Risk class: **R1 (doc), reviewed as R2 because it scopes finance work**",
            "R2",
        ),
        ("risk class: R1", "R1"),
        ("Risk class: R0_READ_ONLY", "R0"),
    ],
)
def test_risk_class_takes_the_highest_declared(line: str, expected: str) -> None:
    """A mixed declaration takes its highest class (REVIEW-01)."""
    assert check.risk_class(f"## Summary\n{line}\n") == expected


def test_an_undeclared_class_fails_closed() -> None:
    """Omitting the class cannot skip the review pair."""
    code, message = _verdict(_pair(), body="## Summary\nNo class here; R3 elsewhere.\n")
    assert code == 1 and "declare the risk class" in message


@pytest.mark.parametrize("level", ["R0", "R1"])
def test_r0_and_r1_need_no_pair(level: str) -> None:
    """Below R2 the check passes without reading any record."""
    assert _verdict([], body=f"Risk class: {level}\n")[0] == 0


def test_r3_needs_the_same_pair() -> None:
    """R3 needs at least the R2 pair."""
    assert _verdict([], body="Risk class: R3\n")[0] == 1
    assert _verdict(_pair(), body="Risk class: R3\n")[0] == 0


def test_writer_sessions_read_every_trailer() -> None:
    """Every Claude-Session trailer on the pull request's commits is a writer."""
    assert check.writer_sessions(COMMITS) == {WRITER}


def _workflow() -> dict[Any, Any]:
    loaded: dict[Any, Any] = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return loaded


def test_workflow_runs_the_check_from_the_base_commit() -> None:
    """The judged pull request cannot supply the script that judges it."""
    job = _workflow()["jobs"]["review-pair"]
    checkout = job["steps"][0]
    assert checkout["uses"].startswith("actions/checkout@")
    assert checkout["with"]["ref"] == "${{ github.event.pull_request.base.sha }}"
    run = [s for s in job["steps"] if "run" in s]
    assert [s["run"] for s in run] == ["python scripts/ci/check_pr_review_pair.py"]
    assert run[0]["env"]["PR_HEAD_SHA"] == "${{ github.event.pull_request.head.sha }}"
    assert "continue-on-error" not in job and "continue-on-error" not in run[0]


def test_workflow_reports_the_required_name_only_when_ready() -> None:
    """A draft reports under another name; ready_for_review re-runs the check."""
    workflow = _workflow()
    # PyYAML reads the bare key `on` as the boolean True.
    triggers: dict[Any, Any] = workflow[True] if True in workflow else workflow["on"]
    assert "ready_for_review" in triggers["pull_request"]["types"]
    name = workflow["jobs"]["review-pair"]["name"]
    assert "'Independent review (RECRUIT-01)'" in name
    assert "github.event.pull_request.draft" in name


def test_template_asks_for_the_risk_class() -> None:
    """The pull request template carries the line the check reads."""
    assert "Risk class:" in TEMPLATE.read_text(encoding="utf-8")
