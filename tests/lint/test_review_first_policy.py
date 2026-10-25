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

Deliberately not pinned yet: the ``test-suite.yml`` draft gate. It lands as its own change once
#1386 settles that workflow, and the row says ``AUTOMATION PENDING`` until then. That phrase is
pinned so the rule cannot start claiming automation that is not on ``main``.
"""

from __future__ import annotations

import csv
from collections.abc import Callable
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_RULESET = REPO_ROOT / "go_with_the_flow_rules_v3_0_clean.csv"
MODULE_1 = (
    REPO_ROOT / "docs" / "governance" / "recruit_01" / "01_capability_and_risk.md"
)
AGENTS = REPO_ROOT / "AGENTS.md"
STEWARD = REPO_ROOT / ".claude" / "skills" / "steward" / "SKILL.md"

REVIEW_01_REQUIRED_CONTROLS = (
    "opens its pull request as a draft",
    "only the fast gates are relied on",
    "bind to that draft head",
    "runs once on that head",
    "both substantive reviews restart exactly as module 3 section 6 requires",
    "never what voids a binding",
    "section 7's three proofs",
    "R1_ROUTINE work takes one role-appropriate independent lane",
    "keep the separate task-domain and assurance pair",
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
    "AUTOMATION PENDING",
    "latest Test Summary ran on a non-draft event",
)

MODULE_1_REQUIRED_CONTROLS = (
    "### 3.1 Bounded low-risk classes (`REVIEW-01`)",
    "the three bounded low-risk classes in §3.1 | One role-appropriate independent reviewer |",
    "| `R2_LOAD_BEARING` | Any code outside §3.1's bounded classes;",
    "Two independent reviewers: one task-domain reviewer and one separate assurance reviewer",
    "**Presentation-only code.**",
    "**Test-only guard tightening.**",
    "without removing, skipping or weakening an assertion",
    "**Record corrections.**",
    "a dependency bump, a CI or merge gate, governance",
    "`go_with_the_flow_rules_v3_0_clean.csv`",
    "an oracle-defining test",
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
    "§3.1's bounded low-risk classes are `R2` there",
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


def _normalize(text: str) -> str:
    """Collapse whitespace so re-wrapping a paragraph neither breaks nor satisfies a guard."""
    return " ".join(text.split())


def _assert_contains_all(text: str, controls: tuple[str, ...], where: str) -> None:
    """Every pinned control appears in ``text``, compared with whitespace collapsed."""
    flat = _normalize(text)
    missing = [c for c in controls if _normalize(c) not in flat]
    assert not missing, f"{where} lost controls: {missing}"


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
