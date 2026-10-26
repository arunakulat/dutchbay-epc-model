"""Guard ``RECRUIT-01``: a writer reimplements reviewer-supplied code, never copies it.

The project owner decided this on 2026-10-26, closing the gap #1381's ``O-3`` exposed: a writer
committed test lines copied verbatim from a reviewer's record, and nothing in ``RECRUIT-01`` said
who then reviews those lines. Module 3 §1 now does, and the steward skill carries it to the
writer at the step where a review forces a change.

What is pinned here is the *text*, because text is what a later reader acts on. Each guard is a
pure function over the file's bytes, and every pinned control has a negative control that removes
it and watches the guard fail -- a guard that cannot fail would only look like a fence.

Two mutations past the removals are pinned deliberately. A permission added *beside* the rule
("the coordinator may allow the writer to commit them") leaves every pinned phrase in place while
inverting the rule, which is the shape that slipped past ``REVIEW-01``'s first guard (#1390
assurance ``C-1``). And a rule reduced to crediting, with the reimplementation clause dropped,
still reads like a rule about reviewer-supplied code while permitting the copy.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_3 = (
    REPO_ROOT
    / "docs"
    / "governance"
    / "recruit_01"
    / "03_independent_review_and_attestation.md"
)
STEWARD = REPO_ROOT / ".claude" / "skills" / "steward" / "SKILL.md"

MODULE_3_REQUIRED_CONTROLS = (
    "A reviewer supplies findings, not subject bytes.",
    "the writer reimplements it in its own terms rather than committing the reviewer's lines",
    "makes that reviewer a co-author of the subject",
    "a pass over its own work rather than an independent review",
    "Reimplementing is what keeps the lane eligible to review the result",
    "The finding stays credited to the reviewer; the implementation is the writer's.",
)

STEWARD_REQUIRED_CONTROLS = (
    "Treat a reviewer's snippet as a description of the gap, never as code to commit",
    "reimplement it in your own terms",
    "still reviewing work it did not write",
    "(module 3 §1)",
)

# Wordings that invert the rule while leaving the pinned phrases in place.
CONTRADICTIONS = (
    "The coordinator may allow the writer to commit a reviewer's lines where the fix is small.",
    "A writer may adopt reviewer-supplied code verbatim when the reviewer agrees.",
    "This does not apply to tests.",
)


def _normalize(text: str) -> str:
    """Collapse whitespace so re-wrapping a paragraph neither breaks nor satisfies a guard."""
    return " ".join(text.split())


def _assert_contains_all(text: str, controls: tuple[str, ...], where: str) -> None:
    """Every pinned control appears in ``text``, compared with whitespace collapsed."""
    flat = _normalize(text)
    missing = [c for c in controls if _normalize(c) not in flat]
    assert not missing, f"{where} lost controls: {missing}"


def _assert_no_contradiction(text: str, where: str) -> None:
    """No wording beside the rule gives back the permission the rule removes."""
    flat = _normalize(text)
    found = [c for c in CONTRADICTIONS if _normalize(c) in flat]
    assert not found, f"{where} contradicts the reimplementation rule: {found}"


def _assert_module_3(text: str) -> None:
    """Module 3 states the rule, keeps its reasoning, and grants no exception."""
    _assert_contains_all(text, MODULE_3_REQUIRED_CONTROLS, "module 3")
    _assert_no_contradiction(text, "module 3")


def _without(text: str, control: str) -> str:
    """Return ``text`` with one pinned control removed, failing if it was never there."""
    flat = _normalize(text)
    target = _normalize(control)
    assert target in flat, f"control not present to remove: {control!r}"
    return flat.replace(target, "REMOVED_CONTROL")


def test_module_3_requires_the_writer_to_reimplement() -> None:
    """The rule is in the module that governs independence, with its reasoning intact."""
    _assert_module_3(MODULE_3.read_text(encoding="utf-8"))


def test_the_rule_sits_in_the_independence_section() -> None:
    """Placement is load-bearing: §1 is what a lane reads when it asks whether it may review.

    The same sentences under §3 (review method) or §4 (the disposition receipt) would read as
    advice about how to review rather than as a condition of independence.
    """
    text = MODULE_3.read_text(encoding="utf-8")
    start = text.index("## 1. Independence")
    end = text.index("## 2. Frozen subject manifest")
    section = text[start:end]

    _assert_contains_all(section, MODULE_3_REQUIRED_CONTROLS, "module 3 §1")


def test_steward_skill_carries_the_rule_to_the_writer() -> None:
    """The pull-request skill says it where a review forces a change, not only in the module."""
    _assert_contains_all(
        STEWARD.read_text(encoding="utf-8"), STEWARD_REQUIRED_CONTROLS, "steward skill"
    )


@pytest.mark.parametrize("control", MODULE_3_REQUIRED_CONTROLS)
def test_module_3_guard_fails_when_a_control_is_removed(control: str) -> None:
    """Negative control: each clause is load-bearing for the guard."""
    altered = _without(MODULE_3.read_text(encoding="utf-8"), control)
    with pytest.raises(AssertionError):
        _assert_module_3(altered)


@pytest.mark.parametrize("control", STEWARD_REQUIRED_CONTROLS)
def test_steward_guard_fails_when_a_control_is_removed(control: str) -> None:
    """Negative control: the routing line cannot lose its clauses unnoticed."""
    altered = _without(STEWARD.read_text(encoding="utf-8"), control)
    with pytest.raises(AssertionError):
        _assert_contains_all(altered, STEWARD_REQUIRED_CONTROLS, "steward skill")


@pytest.mark.parametrize(
    "contradiction", CONTRADICTIONS, ids=range(len(CONTRADICTIONS))
)
def test_module_3_guard_fails_on_a_permission_added_beside_the_rule(
    contradiction: str,
) -> None:
    """Negative control: the rule inverted by an exception, every pinned phrase still present.

    This is the shape that passed ``REVIEW-01``'s first guard, where only the tail of a clause
    was pinned and a rewrite relaxed the rule while keeping the tail (#1390 assurance ``C-1``).
    """
    text = MODULE_3.read_text(encoding="utf-8") + f"\n{contradiction}\n"

    _assert_contains_all(text, MODULE_3_REQUIRED_CONTROLS, "module 3")
    with pytest.raises(AssertionError):
        _assert_module_3(text)


def test_module_3_guard_fails_if_the_rule_is_reduced_to_crediting() -> None:
    """Negative control: crediting the finding is not the rule.

    A module that kept only the attribution sentence would still look like it governed
    reviewer-supplied code while permitting the writer to commit the reviewer's lines.
    """
    altered = _without(
        MODULE_3.read_text(encoding="utf-8"),
        "the writer reimplements it in its own terms rather than committing the reviewer's lines",
    )

    assert (
        _normalize(
            "The finding stays credited to the reviewer; the implementation is the writer's."
        )
        in altered
    )
    with pytest.raises(AssertionError):
        _assert_module_3(altered)
