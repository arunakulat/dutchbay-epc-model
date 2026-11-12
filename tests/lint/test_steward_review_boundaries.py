"""Guard the merge decisions carried forward from reviews #1322 and #1340."""

from collections.abc import Callable
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
STEWARD = Path("skills/steward/SKILL.md")


def _words(text: str) -> str:
    return " ".join(text.split())


def _check_dependency_rules(skill: str) -> None:
    review = _words(skill.split("## Review\n")[1].split("## Merging\n")[0])
    assert (
        "Before recruiting reviewers or starting work, search open issues and open pull"
        " requests for the same package and check active writer leases" in review
    )
    merge = _words(skill.split("## Merging\n")[1])
    assert (
        "- Before merging each dependency pull request, re-run `make audit` on the"
        " exact head (D1340-A-04)." in merge
    )


def _check_unattributed_condition(skill: str) -> None:
    merge = _words(skill.split("## Merging\n")[1])
    assert (
        "While the author is unknown, only the owner may withdraw the block." in merge
    )
    assert (
        "An independent reviewer who did not make the fix may discharge a satisfied"
        " condition by citing the unattributed record and the evidence of fulfillment"
        in merge
    )


def _check_record_recovery(skill: str) -> None:
    # Check the two remedies in their own paragraphs. An access exception in the
    # invalid-record paragraph gives the merger a route around module 3 §6.
    start = "it names the reviewer, the exact commit, tree and base, and the subject-manifest digest."
    end = "   - A condition set by a review"
    recovery = skill.split(start, 1)[1].split(end, 1)[0].strip()
    invalid, inaccessible = map(_words, recovery.split("\n\n"))
    assert (
        "An edited or deleted comment, a missing content digest or a mismatch"
        " invalidates the disposition." in invalid
    )
    assert (
        "Require a replacement on the exact merge head from the original reviewer"
        " or from a new independent reviewer after a fresh review." in invalid
    )
    assert "container" not in invalid
    assert (
        "If the only obstacle is access to the named durable file, the merger may"
        " perform all the checks above in the container holding that file and merge"
        " there once they pass." in inaccessible
    )


def _check_local_commands(skill: str) -> None:
    run = 'PYTHONPATH="$PWD" "$DUTCHBAY_VENV/bin/python"'
    assert f'{run} - "$PR"' in skill
    assert f"{run} scripts/compile_changelog.py --dry-run" in skill
    assert 'PATH="$DUTCHBAY_VENV/bin:$PATH" PYTHONPATH="$PWD" make audit' in skill
    assert ".venv/bin/python" not in skill


def test_both_stewards_carry_the_review_and_runtime_rules() -> None:
    """Claude and Codex must make the same decision from identical source bytes."""
    source = (ROOT / ".claude" / STEWARD).read_bytes()
    assert (ROOT / ".agents" / STEWARD).read_bytes() == source
    text = source.decode()
    _check_dependency_rules(text)
    _check_unattributed_condition(text)
    _check_record_recovery(text)
    _check_local_commands(text)


@pytest.mark.parametrize(
    ("check", "original", "replacement"),
    [
        (_check_dependency_rules, "open issues and open pull", "open pull"),
        (_check_dependency_rules, "and check active writer leases", ""),
        (
            _check_dependency_rules,
            "Before merging each dependency pull request,",
            "If the previous audit is more than 24 hours old,",
        ),
        (
            _check_unattributed_condition,
            "only the owner may withdraw",
            "anyone may withdraw",
        ),
        (_check_unattributed_condition, "who did not make the fix", "who made the fix"),
        (_check_unattributed_condition, "and the evidence of fulfillment", ""),
        (
            _check_record_recovery,
            "after a fresh review.",
            "after a fresh review. Alternatively merge from the file's container.",
        ),
        (
            _check_record_recovery,
            "the only obstacle is access",
            "any check fails on access",
        ),
        (_check_record_recovery, "once they pass", "without those checks"),
        (_check_local_commands, '"$DUTCHBAY_VENV/bin/python"', ".venv/bin/python"),
        (_check_local_commands, 'PYTHONPATH="$PWD"', 'PYTHONPATH="/another/worktree"'),
    ],
)
def test_weakened_instruction_fails_its_guard(
    check: Callable[[str], None], original: str, replacement: str
) -> None:
    """Exercise the guard with a plausible wrong rule in its normal context."""
    text = (ROOT / ".claude" / STEWARD).read_text(encoding="utf-8")
    assert original in text
    with pytest.raises(AssertionError):
        check(text.replace(original, replacement))
