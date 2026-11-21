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
    car: str | None = None,
    version: str = "1",
) -> dict[str, Any]:
    block = (
        f"PR #{pr} {role.upper()} review record\n"
        f"Review-Record: {version}\n"
        f"Role: {role}\n"
        f"PR: #{pr}\n"
        f"Commit: {commit}\n"
        f"Reviewer-Session: {reviewer}\n"
        f"Disposition: {disposition}\n"
        + (f"Car: #{car}\n" if car is not None else "")
        + "\nFindings: none blocking.\n"
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
    comments: list[dict[str, Any]],
    body: str = BODY,
    commits: Any = None,
    **kwargs: str,
) -> tuple[int, str]:
    result: tuple[int, str] = check.evaluate(
        body, PR, HEAD, COMMITS if commits is None else commits, comments, **kwargs
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
            _pair(disposition="REJECT"), "one veto blocks", id="rejecting pair"
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


def _triggers() -> dict[Any, Any]:
    workflow = _workflow()
    # PyYAML reads the bare key `on` as the boolean True.
    triggers: dict[Any, Any] = workflow[True] if True in workflow else workflow["on"]
    return triggers


def test_workflow_comes_from_main_not_the_pull_request() -> None:
    """On `pull_request` GitHub runs the PR's own workflow file; `pull_request_target` runs main's."""
    triggers = _triggers()
    assert set(triggers) == {"pull_request_target"}
    assert triggers["pull_request_target"]["branches"] == ["main"]


def test_workflow_runs_the_check_from_the_base_commit() -> None:
    """The judged pull request cannot supply the script that judges it, nor run code."""
    job = _workflow()["jobs"]["review-pair"]
    checkout = job["steps"][0]
    assert checkout["uses"].startswith("actions/checkout@")
    assert checkout["with"]["ref"] == "${{ github.event.pull_request.base.sha }}"
    assert checkout["with"]["persist-credentials"] is False
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "pull_request.head.sha }}" not in "".join(
        str(s.get("with", {})) for s in job["steps"]
    )
    assert "run: python scripts/ci/check_pr_review_pair.py" in text
    assert set(_workflow()["permissions"].values()) == {"read"}
    run = [s for s in job["steps"] if "run" in s]
    assert [s["run"] for s in run] == ["python scripts/ci/check_pr_review_pair.py"]
    assert run[0]["env"]["PR_HEAD_SHA"] == "${{ github.event.pull_request.head.sha }}"
    assert "continue-on-error" not in job and "continue-on-error" not in run[0]


def test_workflow_reports_the_required_name_only_when_ready() -> None:
    """A draft reports under another name; ready_for_review re-runs the check."""
    workflow = _workflow()
    assert "ready_for_review" in _triggers()["pull_request_target"]["types"]
    assert "edited" in _triggers()["pull_request_target"]["types"]
    name = workflow["jobs"]["review-pair"]["name"]
    assert "'Independent review (RECRUIT-01)'" in name
    assert "github.event.pull_request.draft" in name


def test_template_asks_for_the_risk_class() -> None:
    """The pull request template carries the line the check reads."""
    assert "Risk class:" in TEMPLATE.read_text(encoding="utf-8")


# --- One veto blocks acceptance (RECRUIT-01 module 3 section 1) -------------------------------

THIRD = "session_THIRD00000000000000000"


@pytest.mark.parametrize(
    "comments",
    [
        pytest.param(
            [*_pair(), _record("domain", THIRD, disposition="REJECT", comment_id=3)],
            id="third reviewer rejects beside an accepting pair",
        ),
        pytest.param(
            [*_pair(), _record("assurance", THIRD, disposition="REJECT", comment_id=3)],
            id="second assurance reviewer rejects",
        ),
        pytest.param(
            [*_pair(), _record("domain", DOMAIN, disposition="REJECT", comment_id=3)],
            id="a reviewer accepts then rejects at the same head",
        ),
        pytest.param(
            _pair(disposition="ACCEPT with conditions"),
            id="conditional acceptance is not acceptance",
        ),
    ],
)
def test_a_veto_at_the_head_blocks(comments: list[dict[str, Any]]) -> None:
    """VERIFY-01(5): a withheld acceptance at the head fails even beside a pair."""
    code, message = _verdict(comments)
    assert code == 1
    assert "one veto blocks acceptance" in message, message


def test_a_reviewer_may_correct_its_own_record() -> None:
    """The latest record per reviewer counts: REJECT then ACCEPT by the same lane passes."""
    comments = [
        _record("domain", DOMAIN, disposition="CHANGES-REQUESTED", comment_id=1),
        _record("domain", DOMAIN, comment_id=2),
        _record("assurance", ASSURANCE, comment_id=3),
    ]
    assert _verdict(comments)[0] == 0


def test_a_veto_on_an_older_head_does_not_block() -> None:
    """A rejection bound to a superseded head is history, not a veto at this head."""
    comments = [
        _record("domain", THIRD, disposition="REJECT", commit=OLD_HEAD, comment_id=1),
        *_pair(),
    ]
    assert _verdict(comments)[0] == 0


# --- Record shape (mutation survivors on the first head) --------------------------------------


@pytest.mark.parametrize(
    ("comment", "expected"),
    [
        pytest.param(
            _record("reviewer", DOMAIN), "must be domain or assurance", id="role"
        ),
        pytest.param(_record("domain", DOMAIN, version="2"), "unknown", id="version"),
        pytest.param(_record("domain", DOMAIN, car="x"), "`Car:` must be", id="car"),
    ],
)
def test_malformed_records_are_refused(comment: dict[str, Any], expected: str) -> None:
    """Each header field is validated, not just present."""
    record, reason = check.parse_record(comment)
    assert record is None and expected in reason


def test_two_record_blocks_in_one_comment_are_refused() -> None:
    """One comment carries exactly one record, so it cannot hold both roles."""
    one, two = _pair()
    merged = {**one, "body": one["body"] + "\n" + two["body"]}
    record, reason = check.parse_record(merged)
    assert record is None and "exactly one record block" in reason


def test_a_lower_case_disposition_still_accepts() -> None:
    """Dispositions are compared upper-cased."""
    assert _verdict(_pair(disposition="accept"))[0] == 0


def test_a_capitalised_session_prefix_still_matches_the_writer() -> None:
    """`Session_X` and `session_X` name the same session."""
    capitalised = "Session_" + WRITER.split("_", 1)[1]
    code, message = _verdict([_record("domain", capitalised), _pair()[1]])
    assert code == 1 and "wrote a commit here" in message


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("**Risk class:** R2", "R2"),
        ("- Risk class: R3", "R3"),
        ("* **Risk class:** R1", "R1"),
        ("Risk class: r2", None),
        ("Risk class:", None),
        ("The Risk class: R3 line is elsewhere", None),
    ],
)
def test_risk_class_line_forms(line: str, expected: str | None) -> None:
    """A bullet or bold label is read; a lower-case or empty class is not a declaration."""
    assert check.risk_class(f"## Summary\n{line}\n") == expected


def test_the_unedited_template_declares_nothing() -> None:
    """The template's guidance sits above the line, so an unedited body fails closed."""
    assert check.risk_class(TEMPLATE.read_text(encoding="utf-8")) is None


# --- Dependabot ------------------------------------------------------------------------------


def test_a_dependabot_pull_request_is_read_as_r2() -> None:
    """REVIEW-01 classes dependency bumps as R2: no class line still needs the pair."""
    body = "Bumps foo from 1.0 to 1.1."
    code, message = _verdict([], body=body, author="dependabot[bot]")
    assert code == 1 and "R2 needs" in message
    assert _verdict(_pair(), body=body, author="dependabot[bot]")[0] == 0
    assert "declare the risk class" in _verdict(_pair(), body=body, author="someone")[1]


# --- Trains: one pair per car (TRAIN-01, module 3 section 8) ---------------------------------

TRAIN_REF = "train/2026-11-21-1"
TRAIN_COMMITS = [
    {"commit": {"message": "docs: car a (#10)\n\nbody"}},
    {"commit": {"message": "fix: car b (#11)"}},
]


def _car_pair(car: str, base_id: int) -> list[dict[str, Any]]:
    return [
        _record("domain", f"session_D{car}", car=car, comment_id=base_id),
        _record("assurance", f"session_A{car}", car=car, comment_id=base_id + 1),
    ]


def _train(comments: list[dict[str, Any]]) -> tuple[int, str]:
    return _verdict(comments, commits=TRAIN_COMMITS, head_ref=TRAIN_REF)


def test_a_train_needs_a_pair_for_every_car() -> None:
    """One pair is not enough on a train: each car carries its own forward."""
    code, message = _train(_car_pair("10", 1))
    assert code == 1 and "car #11" in message
    assert _train(_car_pair("10", 1) + _car_pair("11", 3))[0] == 0


def test_a_train_record_without_a_car_does_not_count() -> None:
    """Records on a train must say which car they carry forward."""
    code, message = _train(_pair())
    assert code == 1 and "must name one of the cars" in message


def test_a_veto_on_any_car_blocks_the_train() -> None:
    """A withheld acceptance for one car blocks the whole train."""
    comments = _car_pair("10", 1) + _car_pair("11", 3)
    comments.append(
        _record("domain", "session_D11", car="11", disposition="REJECT", comment_id=9)
    )
    code, message = _train(comments)
    assert code == 1 and "one veto blocks acceptance" in message


def test_a_train_with_no_car_subjects_fails_closed() -> None:
    """A train branch whose commits name no car cannot be judged per car."""
    assert _verdict(_pair(), commits=COMMITS, head_ref=TRAIN_REF)[0] == 1


def test_a_car_field_off_a_train_does_not_count() -> None:
    """`Car:` belongs to train records only."""
    code, message = _verdict(_car_pair("10", 1))
    assert code == 1 and "only for train pull requests" in message


# --- main(): environment, paging and fail-closed reads ----------------------------------------


def _env(monkeypatch: pytest.MonkeyPatch, **values: str) -> None:
    base = {
        "PR_BODY": BODY,
        "PR_NUMBER": str(PR),
        "PR_HEAD_SHA": HEAD,
        "PR_HEAD_REF": "feature",
        "PR_AUTHOR": "arunakulat",
        "GITHUB_TOKEN": "token",
        "GITHUB_REPOSITORY": "owner/repo",
    }
    base.update(values)
    for key, value in base.items():
        monkeypatch.setenv(key, value)


def _stub(
    monkeypatch: pytest.MonkeyPatch, pages: dict[str, list[list[dict[str, Any]]]]
) -> list[str]:
    seen: list[str] = []

    def fake(repository: str, path: str, token: str) -> Any:
        seen.append(path)
        kind = "comments" if "/comments?" in path else "commits"
        page = int(path.rsplit("page=", 1)[1])
        batches = pages[kind]
        return batches[page - 1] if page <= len(batches) else []

    monkeypatch.setattr(check, "_get_json", fake)
    return seen


def test_main_reads_every_page_and_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    """A record on the second page of comments is read."""
    _env(monkeypatch)
    filler = [{"id": 1000 + i, "body": "chatter"} for i in range(check._PAGE_SIZE)]
    seen = _stub(monkeypatch, {"commits": [COMMITS], "comments": [filler, _pair()]})
    assert check.main() == 0
    assert any("comments?" in p and "page=2" in p for p in seen)


def test_main_fails_closed_on_a_read_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """An API failure blocks the merge; it never passes."""
    _env(monkeypatch)

    def broken(repository: str, path: str, token: str) -> Any:
        raise OSError("connection reset")

    monkeypatch.setattr(check, "_get_json", broken)
    assert check.main() == 1


def test_main_fails_closed_on_a_non_list_page(monkeypatch: pytest.MonkeyPatch) -> None:
    """An error object in place of a list blocks the merge."""
    _env(monkeypatch)
    monkeypatch.setattr(check, "_get_json", lambda *a: {"message": "Not Found"})
    assert check.main() == 1


@pytest.mark.parametrize(
    "values",
    [
        {"PR_HEAD_SHA": "c" * 12},
        {"PR_HEAD_SHA": ""},
        {"GITHUB_TOKEN": ""},
        {"GITHUB_REPOSITORY": ""},
        {"PR_NUMBER": "not-a-number"},
    ],
)
def test_main_fails_closed_on_missing_inputs(
    monkeypatch: pytest.MonkeyPatch, values: dict[str, str]
) -> None:
    """A short head SHA, missing token, repository or number cannot pass."""
    _env(monkeypatch, **values)
    _stub(monkeypatch, {"commits": [COMMITS], "comments": [_pair()]})
    assert check.main() == 1


def test_main_passes_r1_without_reading(monkeypatch: pytest.MonkeyPatch) -> None:
    """Below R2 nothing is read, so a missing token does not matter."""
    _env(monkeypatch, PR_BODY="Risk class: R1\n", GITHUB_TOKEN="")
    monkeypatch.setattr(check, "_get_json", lambda *a: pytest.fail("read"))
    assert check.main() == 0


def test_main_reads_dependabot_as_r2(monkeypatch: pytest.MonkeyPatch) -> None:
    """The author reaches the class decision through the environment."""
    _env(monkeypatch, PR_BODY="Bumps foo.", PR_AUTHOR="dependabot[bot]")
    _stub(monkeypatch, {"commits": [COMMITS], "comments": [[]]})
    assert check.main() == 1
    _stub(monkeypatch, {"commits": [COMMITS], "comments": [_pair()]})
    assert check.main() == 0


def test_main_reads_a_train_from_the_head_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The head branch reaches the train decision through the environment."""
    _env(monkeypatch, PR_HEAD_REF=TRAIN_REF)
    _stub(monkeypatch, {"commits": [TRAIN_COMMITS], "comments": [_car_pair("10", 1)]})
    assert check.main() == 1
    pairs = _car_pair("10", 1) + _car_pair("11", 3)
    _stub(monkeypatch, {"commits": [TRAIN_COMMITS], "comments": [pairs]})
    assert check.main() == 0
