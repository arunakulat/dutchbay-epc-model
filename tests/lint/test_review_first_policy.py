"""Guard ``REVIEW-01``: review before the full suite, lanes scaled to risk, one evidence pack.

The rule makes three practices permanent, on the project owner's decision of 2026-10-25:
review lanes bind on a frozen draft head before the full sharded suite runs once; the three
bounded low-risk classes in ``RECRUIT-01`` module 1 §3.1 take one lane while everything else
keeps the domain and assurance pair; and the writer publishes one evidence pack that the lanes
verify rather than re-derive.

What is pinned here is the *text* that carries those controls - the rule row, the module 1
classes and their exclusions, the ``RECRUIT-01`` cross-reference, and the routing statements in
``AGENTS.md`` and the steward skill - because each is what a later reader acts on. Every guard is
a pure function over text, so each pinned control has a negative control below that removes it
and watches the guard fail. A guard that cannot fail would only look like a fence.

The ``test-suite.yml`` draft gate is pinned here too: the ``ready_for_review`` trigger, the
summary job's name, which is the required ``Test Summary`` only for a non-draft run, and the
summary script run for a draft. ``tests/lint/test_grid_ci_policy.py`` executes the classify step
for a draft and a non-draft event.
"""

from __future__ import annotations

import csv
import os
import re
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_RULESET = REPO_ROOT / "go_with_the_flow_rules_v3_0_clean.csv"
MODULE_1 = (
    REPO_ROOT / "docs" / "governance" / "recruit_01" / "01_capability_and_risk.md"
)
AGENTS = REPO_ROOT / "AGENTS.md"
STEWARD = REPO_ROOT / ".claude" / "skills" / "steward" / "SKILL.md"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "test-suite.yml"
REQUIRED_CHECK = "Test Summary"
DRAFT_CHECK = "Test Summary (draft: full suite deferred)"

REVIEW_01_REQUIRED_CONTROLS = (
    "opens its pull request as a draft",
    "only the fast gates are relied on",
    "bind to that draft head",
    "runs once on that head",
    "both substantive reviews restart exactly as module 3 section 6 requires",
    "never what voids a binding",
    "section 7's three proofs",
    "R1_ROUTINE work takes one role-appropriate independent lane",
    # Pinned with its subject, like R1's count above: the bare tail would survive a
    # rewrite that lets R2 take one lane (#1390 assurance C-1).
    "R2_LOAD_BEARING and R3_CONSEQUENTIAL keep the separate task-domain and assurance pair",
    "module 1 section 3.1",
    "presentation-only code",
    "test-only guard tightening",
    "record corrections",
    "dependency bumps",
    "CI and merge gates",
    "governance and this ruleset",
    "oracle-defining tests",
    "A mixed change takes its highest class",
    "when unsure, classify R2",
    "the writer cannot argue an escalation down",
    "'Evidence pack'",
    "VERIFY-01 receipts and intake parsers",
    "a claim to verify, never a disposition",
    "does not change which checks are required",
    "what MERGE-01 means by green",
    "tests/lint/test_review_first_policy.py",
    "Its pull_request trigger includes ready_for_review",
    "emits code_changed=false and qsts_execution_changed=false",
    "'Test Summary (draft: full suite deferred)'",
    "while still gating Code Quality Checks and Security Scan",
    "exists on a head only after a non-draft run has completed the full suite there",
    "tests/lint/test_grid_ci_policy.py executes the classify step",
    "latest Test Summary ran on a non-draft event",
)

MODULE_1_REQUIRED_CONTROLS = (
    "### 3.1 Bounded low-risk classes (`REVIEW-01`)",
    "the three bounded low-risk classes in §3.1 | One role-appropriate independent reviewer |",
    # Pinned together with its review cell, like the R1 row above, so moving the
    # two-reviewer phrase to R3 and giving R2 one reviewer fails (#1416 domain W-1).
    (
        "| `R2_LOAD_BEARING` | Any code outside §3.1's bounded classes; contracts; "
        "schemas; tests that define an oracle; governance; charters; handovers; "
        "review records; provenance; security; data ingestion; deployment; report "
        "controls; release/HOLD wording; or other work capable of changing later "
        "action | Two independent reviewers: one task-domain reviewer and one "
        "separate assurance reviewer |"
    ),
    "**Presentation-only code.**",
    "**Test-only guard tightening.**",
    "tightens an existing guard, or adds a negative control for one",
    "without removing, skipping or weakening an assertion",
    "**Record corrections.**",
    "a dependency bump, a CI or merge gate, governance",
    "`go_with_the_flow_rules_v3_0_clean.csv`",
    "an oracle-defining test",
    "a change to a fence or guard whose own evidence could be vacuous",
    "a writer-authorizing handover",
    "A mixed change takes its highest class.",
    "When unsure, classify `R2`.",
    "the writer cannot argue an escalation down.",
)

RECRUIT_01_CROSS_REFERENCE = (
    "R1 routine work, including the bounded low-risk classes REVIEW-01 adds in module 1 "
    "section 3.1, receives one role-appropriate independent review."
)

AGENTS_REQUIRED_CONTROLS = (
    "`REVIEW-01`: review comes before the full suite.",
    "`Evidence pack`",
    "bind to that draft head",
    "module 1 §3.1 take one lane",
    "restarts both reviews (module 3 §6)",
)

STEWARD_REQUIRED_CONTROLS = (
    "**Review comes before the full suite (`REVIEW-01`).**",
    "headed `Evidence pack`",
    "scripts/ci/check_pr_receipts.py",
    "scripts/ci/check_pr_intake.py",
    "it is a claim, never a disposition",
    "The lanes bind to that draft head.",
    "both reviews restart (module 3 §6)",
    "When unsure, it is `R2`.",
    # Pinned with "outside" and the R1 half so inverting the boundary fails
    # (#1416 domain W-2).
    (
        "any code outside module 1 §3.1's bounded low-risk classes are `R2` there; "
        "those classes are `R1` and take one lane (`REVIEW-01`)."
    ),
    "`Test Summary (draft: full suite deferred)`",
)


def _rules_by_id() -> dict[str, dict[str, str]]:
    """Load the canonical ruleset keyed by its unique rule identifiers."""
    with CANONICAL_RULESET.open(encoding="utf-8", newline="") as handle:
        return {row["rule_id"]: row for row in csv.DictReader(handle)}


def _policy_text(rule: dict[str, str]) -> str:
    """Join a rule's human-readable cells the way the canonical-source guards do."""
    return " ".join((rule["title"], rule["description"], rule["enforcement"]))


def _assert_review_01(rule: dict[str, str]) -> None:
    """The rule row is active, filed under review, and carries every control."""
    assert rule["status"] == "active"
    assert rule["category"] == "Recruitment & Review"
    policy = _policy_text(rule)
    missing = [c for c in REVIEW_01_REQUIRED_CONTROLS if c not in policy]
    assert not missing, f"REVIEW-01 lost controls: {missing}"
    # The gate is on main now; the row must not go back to describing it as pending.
    assert "AUTOMATION PENDING" not in policy


def _normalize(text: str) -> str:
    """Collapse whitespace so re-wrapping a paragraph neither breaks nor satisfies a guard."""
    return " ".join(text.split())


def _assert_contains_all(text: str, controls: tuple[str, ...], where: str) -> None:
    """Every pinned control appears in ``text``, compared with whitespace collapsed."""
    flat = _normalize(text)
    missing = [c for c in controls if _normalize(c) not in flat]
    assert not missing, f"{where} lost controls: {missing}"


_SECTION_3_1_HEADING = "### 3.1 Bounded low-risk classes (`REVIEW-01`)"
_SECTION_3_1_EXPECTED_CLASSES = (
    "**Presentation-only code.**",
    "**Test-only guard tightening.**",
    "**Record corrections.**",
)


def _extract_section_3_1(text: str) -> str:
    """Return the Markdown body of module 1 §3.1 up to the next heading."""
    marker = re.search(
        rf"^{re.escape(_SECTION_3_1_HEADING)}\s*$", text, flags=re.MULTILINE
    )
    assert marker is not None, f"missing heading: {_SECTION_3_1_HEADING!r}"
    rest = text[marker.end() :]
    next_heading = re.search(r"^#{1,6}\s+", rest, flags=re.MULTILINE)
    return rest[: next_heading.start()] if next_heading is not None else rest


def _assert_section_3_1_defines_exactly_three_classes(text: str) -> None:
    """Module 1 §3.1 lists exactly the three bounded low-risk classes and no fourth."""
    section = _extract_section_3_1(text)
    items = re.findall(r"^(?:\d+\.|[-*+])\s+(.+)$", section, flags=re.MULTILINE)
    assert len(items) == len(_SECTION_3_1_EXPECTED_CLASSES), (
        f"§3.1 must define exactly {len(_SECTION_3_1_EXPECTED_CLASSES)} classes, "
        f"found {len(items)}: {items!r}"
    )
    for item, expected in zip(items, _SECTION_3_1_EXPECTED_CLASSES, strict=True):
        assert item.startswith(
            expected
        ), f"§3.1 class mismatch: expected prefix {expected!r}, got {item!r}"


def _assert_recruit_01_cross_reference(rule: dict[str, str]) -> None:
    """RECRUIT-01's own lane statement points at the bounded classes rather than contradicting them."""
    assert RECRUIT_01_CROSS_REFERENCE in rule["enforcement"]
    assert "R1 routine documentation receives" not in rule["enforcement"]


def test_review_01_row_carries_its_controls() -> None:
    """The canonical row is present, active and complete."""
    _assert_review_01(_rules_by_id()["REVIEW-01"])


def test_module_1_defines_the_bounded_classes_and_keeps_the_r2_pair() -> None:
    """Module 1 names the three classes, every exclusion, and still binds R2 for other code."""
    _assert_contains_all(
        MODULE_1.read_text(encoding="utf-8"), MODULE_1_REQUIRED_CONTROLS, "module 1"
    )


def test_module_1_section_3_1_defines_exactly_three_classes() -> None:
    """Module 1 §3.1 defines exactly three bounded low-risk classes (#1416 assurance W-2)."""
    _assert_section_3_1_defines_exactly_three_classes(
        MODULE_1.read_text(encoding="utf-8")
    )


def test_recruit_01_points_at_the_bounded_classes() -> None:
    """RECRUIT-01 no longer says R1 is documentation only."""
    _assert_recruit_01_cross_reference(_rules_by_id()["RECRUIT-01"])


def test_agents_md_routes_to_review_01() -> None:
    """The Codex gateway carries the same order and lane rule."""
    _assert_contains_all(
        AGENTS.read_text(encoding="utf-8"), AGENTS_REQUIRED_CONTROLS, "AGENTS.md"
    )


def test_steward_skill_routes_to_review_01() -> None:
    """The pull-request skill carries the order, the evidence pack and the lane count."""
    _assert_contains_all(
        STEWARD.read_text(encoding="utf-8"), STEWARD_REQUIRED_CONTROLS, "steward skill"
    )


def _without(text: str, control: str) -> str:
    """Return ``text`` with one pinned control removed, failing if it was never there."""
    assert control in text, f"control not present to remove: {control!r}"
    return text.replace(control, "REMOVED_CONTROL")


@pytest.mark.parametrize("control", REVIEW_01_REQUIRED_CONTROLS)
def test_review_01_guard_fails_when_a_control_is_removed(control: str) -> None:
    """Negative control: each REVIEW-01 control is load-bearing for its guard."""
    rule = dict(_rules_by_id()["REVIEW-01"])
    for cell in ("title", "description", "enforcement"):
        if control in rule[cell]:
            rule[cell] = _without(rule[cell], control)
    with pytest.raises(AssertionError):
        _assert_review_01(rule)


def test_review_01_guard_fails_if_automation_is_described_as_pending_again() -> None:
    """Negative control: restoring the pending wording beside the new text fails."""
    rule = dict(_rules_by_id()["REVIEW-01"])
    rule["enforcement"] += " AUTOMATION PENDING: a draft still runs the full suite."
    with pytest.raises(AssertionError):
        _assert_review_01(rule)


def test_review_01_guard_fails_if_r2_is_allowed_one_lane() -> None:
    """Negative control: R2 relaxed to one lane fails, with the pair's wording left in place.

    This is the exact rewrite that passed the guard when only the tail of the R2/R3 clause
    was pinned (#1390 assurance C-1).
    """
    rule = dict(_rules_by_id()["REVIEW-01"])
    rule["description"] = rule["description"].replace(
        "R2_LOAD_BEARING and R3_CONSEQUENTIAL keep the separate task-domain and assurance pair",
        "R2_LOAD_BEARING may take one lane where the coordinator judges it safe; "
        "R3_CONSEQUENTIAL keep the separate task-domain and assurance pair",
    )
    assert "keep the separate task-domain and assurance pair" in rule["description"]
    with pytest.raises(AssertionError):
        _assert_review_01(rule)


@pytest.mark.parametrize("cell,value", [("status", "retired"), ("category", "Testing")])
def test_review_01_guard_fails_on_a_demoted_row(cell: str, value: str) -> None:
    """Negative control: a retired or re-filed row does not pass as the live rule."""
    rule = dict(_rules_by_id()["REVIEW-01"])
    rule[cell] = value
    with pytest.raises(AssertionError):
        _assert_review_01(rule)


_TEXT_GUARDS: tuple[tuple[str, Path, tuple[str, ...]], ...] = (
    ("module 1", MODULE_1, MODULE_1_REQUIRED_CONTROLS),
    ("AGENTS.md", AGENTS, AGENTS_REQUIRED_CONTROLS),
    ("steward skill", STEWARD, STEWARD_REQUIRED_CONTROLS),
)


@pytest.mark.parametrize(
    "where,path,control",
    [(where, path, c) for where, path, controls in _TEXT_GUARDS for c in controls],
)
def test_text_guards_fail_when_a_control_is_removed(
    where: str, path: Path, control: str
) -> None:
    """Negative control: each routing and module control is load-bearing for its guard."""
    controls = next(c for w, _, c in _TEXT_GUARDS if w == where)
    altered = _without(
        _normalize(path.read_text(encoding="utf-8")), _normalize(control)
    )
    with pytest.raises(AssertionError):
        _assert_contains_all(altered, controls, where)


def test_module_1_guard_fails_if_r2_row_loses_two_reviewer_cell() -> None:
    """Negative control: moving the two-reviewer phrase to R3 and giving R2 one lane fails.

    This is the exact mutation that stayed green when R2's class and review cell were
    pinned separately (#1416 domain W-1).
    """
    text = MODULE_1.read_text(encoding="utf-8")
    two_reviewers = (
        "Two independent reviewers: one task-domain reviewer and one separate "
        "assurance reviewer"
    )
    mutated = text.replace(
        f"| {two_reviewers} |",
        "| One role-appropriate independent reviewer |",
        1,
    ).replace(
        "| At least the `R2` pair",
        f"| {two_reviewers}; plus every specialist (was At least the `R2` pair)",
        1,
    )
    assert mutated != text
    assert two_reviewers in mutated
    with pytest.raises(AssertionError):
        _assert_contains_all(mutated, MODULE_1_REQUIRED_CONTROLS, "module 1")


def test_module_1_guard_fails_if_class_2_reverts_or_drops_vacuous_exclusion() -> None:
    """Negative control: reverting class 2 or dropping the vacuous-evidence exclusion fails.

    Covers #1416 domain F-1.
    """
    text = MODULE_1.read_text(encoding="utf-8")
    reverted_class_2 = _normalize(text).replace(
        "tightens an existing guard, or adds a negative control for one",
        "adds or tightens a guard, including a negative control",
    )
    assert reverted_class_2 != _normalize(text)
    with pytest.raises(AssertionError):
        _assert_contains_all(reverted_class_2, MODULE_1_REQUIRED_CONTROLS, "module 1")

    dropped_exclusion = _normalize(text).replace(
        "a change to a fence or guard whose own evidence could be vacuous, ",
        "",
    )
    assert dropped_exclusion != _normalize(text)
    with pytest.raises(AssertionError):
        _assert_contains_all(dropped_exclusion, MODULE_1_REQUIRED_CONTROLS, "module 1")


def test_steward_guard_fails_if_r1_r2_boundary_is_inverted() -> None:
    """Negative control: inverting the steward skill's R1/R2 boundary fails (#1416 domain W-2).

    Reproduces the rewrite that stayed green when only "§3.1's bounded low-risk classes
    are `R2` there" was pinned without "outside" or the R1 half.
    """
    flat = _normalize(STEWARD.read_text(encoding="utf-8"))
    mutated = flat.replace(
        "any code outside module 1 §3.1's bounded low-risk classes are `R2` there; "
        "those classes are `R1` and take one lane (`REVIEW-01`).",
        "module 1 §3.1's bounded low-risk classes are `R2` there; "
        "all code takes two lanes (`REVIEW-01`).",
    )
    assert mutated != flat
    assert "§3.1's bounded low-risk classes are `R2` there" in mutated
    with pytest.raises(AssertionError):
        _assert_contains_all(mutated, STEWARD_REQUIRED_CONTROLS, "steward skill")


@pytest.mark.parametrize(
    "mutate",
    [
        lambda text: text.replace(
            "3. **Record corrections.**",
            "3. **Record corrections.**\n4. **Fourth class.** Unapproved extra class.",
        ),
        lambda text: text.replace(
            "3. **Record corrections.**",
            "3. **Record corrections.**\n- **Fourth class.** Unapproved bulleted class.",
        ),
        lambda text: re.sub(
            r"\n3\. \*\*Record corrections\.\*\*[^\n]*(?:\n   [^\n]*)*",
            "",
            text,
            count=1,
        ),
    ],
    ids=["fourth-numbered-class", "fourth-bulleted-class", "third-class-removed"],
)
def test_section_3_1_class_count_guard_fails_on_added_or_removed_class(
    mutate: Callable[[str], str],
) -> None:
    """Negative control: adding a fourth §3.1 class or removing one fails (#1416 assurance W-2)."""
    text = MODULE_1.read_text(encoding="utf-8")
    mutated = mutate(text)
    assert mutated != text
    with pytest.raises(AssertionError):
        _assert_section_3_1_defines_exactly_three_classes(mutated)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda text: _without(text, RECRUIT_01_CROSS_REFERENCE),
        lambda text: text.replace(
            RECRUIT_01_CROSS_REFERENCE,
            RECRUIT_01_CROSS_REFERENCE
            + " R1 routine documentation receives one review.",
        ),
    ],
    ids=["cross-reference-removed", "documentation-only-wording-restored"],
)
def test_recruit_01_guard_fails_on_a_lost_or_contradicted_cross_reference(
    mutate: Callable[[str], str],
) -> None:
    """Negative control: losing the pointer, or restoring the old wording beside it, fails."""
    rule = dict(_rules_by_id()["RECRUIT-01"])
    rule["enforcement"] = mutate(rule["enforcement"])
    with pytest.raises(AssertionError):
        _assert_recruit_01_cross_reference(rule)


def _workflow() -> dict[Any, Any]:
    loaded: dict[Any, Any] = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return loaded


_SUMMARY_NAME = re.compile(
    r"^\$\{\{ github\.event\.pull_request\.draft && '([^']+)' \|\| '([^']+)' \}\}$"
)


def _summary_check_names(name: str) -> tuple[str, str]:
    """Resolve the summary job's ``name`` for a draft and for any other event.

    The expression is matched whole rather than evaluated, so any other shape fails here
    instead of being guessed at. A schedule or dispatch event has no ``pull_request``, so it
    takes the second name, as a non-draft pull request does.
    """
    match = _SUMMARY_NAME.match(name)
    assert match, f"summary job name has an unexpected shape: {name!r}"
    return match.group(1), match.group(2)


def _assert_draft_gate(workflow: dict[Any, Any]) -> None:
    """The trigger runs on ready_for_review, and only a non-draft run is 'Test Summary'."""
    trigger = workflow[True]["pull_request"]  # PyYAML reads the bare key `on` as True.
    assert set(trigger["types"]) >= {
        "opened",
        "synchronize",
        "reopened",
        "ready_for_review",
    }
    draft_name, other_name = _summary_check_names(workflow["jobs"]["summary"]["name"])
    assert other_name == REQUIRED_CHECK
    assert draft_name == DRAFT_CHECK
    classify = next(
        step
        for step in workflow["jobs"]["changes"]["steps"]
        if step.get("id") == "classify"
    )
    assert classify.get("env", {}).get("PR_DRAFT") == (
        "${{ github.event.pull_request.draft }}"
    )
    assert '"${PR_DRAFT:-false}" = "true"' in classify["run"]


def test_test_suite_defers_the_full_suite_on_drafts() -> None:
    """The live workflow carries the REVIEW-01 draft gate."""
    _assert_draft_gate(_workflow())


@pytest.mark.parametrize(
    "mutate",
    [
        lambda w: w[True]["pull_request"].update(
            types=["opened", "synchronize", "reopened"]
        ),
        lambda w: w["jobs"]["summary"].update(name=REQUIRED_CHECK),
        lambda w: w["jobs"]["summary"].update(
            name="${{ github.event.pull_request.draft && 'Test Summary' || "
            "'Test Summary (draft: full suite deferred)' }}"
        ),
        lambda w: w["jobs"]["changes"]["steps"][1].pop("env"),
    ],
    ids=["no-ready-trigger", "plain-name", "names-swapped", "classify-ignores-draft"],
)
def test_draft_gate_guard_fails_on_a_weakened_workflow(
    mutate: Callable[[dict[Any, Any]], None],
) -> None:
    """Negative control: each way of losing the gate fails the guard."""
    workflow = _workflow()
    assert workflow["jobs"]["changes"]["steps"][1].get("id") == "classify"
    mutate(workflow)
    with pytest.raises(AssertionError):
        _assert_draft_gate(workflow)


def _run_summary(
    tmp_path: Path, draft: str, lint: str
) -> subprocess.CompletedProcess[str]:
    """Run the real summary script as a draft run with every deferred job a success."""
    steps = _workflow()["jobs"]["summary"]["steps"]
    script = str(next(s for s in steps if s.get("name") == "Check test status")["run"])
    values = {
        "needs.test.result": "success",
        "needs.lint.result": lint,
        "needs.security.result": "success",
        "needs.coverage.result": "success",
        "needs.coverage.outputs.enforced": "",
        "needs.changes.outputs.code_changed": "false",
        "needs.changes.outputs.qsts_execution_changed": "false",
        "needs.grid-study.result": "skipped",
        "github.event_name": "pull_request",
    }
    for key, value in values.items():
        script = script.replace("${{ " + key + " }}", value)
    assert "${{" not in script
    path = tmp_path / "summary.sh"
    path.write_text(script, encoding="utf-8")
    return subprocess.run(
        ["bash", "-e", str(path)],
        cwd=tmp_path,
        env={**os.environ, "TOTAL_SHARDS": "6", "PR_DRAFT": draft},
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_draft_summary_notes_the_deferral_and_still_gates_lint(tmp_path: Path) -> None:
    """A draft summary says what it deferred, and a lint failure still blocks it."""
    passed = _run_summary(tmp_path, draft="true", lint="success")
    assert passed.returncode == 0, passed.stdout + passed.stderr
    assert "deferred until it is marked ready for review (REVIEW-01)" in passed.stdout

    blocked = _run_summary(tmp_path, draft="true", lint="failure")
    assert blocked.returncode == 1
    assert "Lint job failed" in blocked.stdout

    ready = _run_summary(tmp_path, draft="false", lint="success")
    assert ready.returncode == 0
    assert "REVIEW-01" not in ready.stdout
