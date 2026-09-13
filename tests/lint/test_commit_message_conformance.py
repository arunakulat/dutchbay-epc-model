"""Measure commit-message conformance instead of freezing a figure into R18.

`R18` drifted in the first place because its enforcement cell pinned a single example
commit, which went stale and then demonstrated the minority form. Replacing that with a
pinned *percentage* would institutionalise the same decay -- a number in normative text
that nothing re-measures. A review of the amendment that introduced this test caught
exactly that: a "504 consecutive commits conform" claim which was ~15x overstated and,
worse, counted as conformance the very `deploy(fly):` commits the same cell declared
unsanctioned. A computed check would have caught it at authoring time. This is that check.

The floors are ratchets, not targets: they sit well below observed conformance so ordinary
variation does not fail the gate, while a genuine collapse in convention does.

This test SKIPS on a shallow checkout. Several CI jobs clone with the default depth, and a
test that failed there would be testing the runner rather than the repository. It still
runs locally and in the full-history jobs, which is where a bad figure gets authored.
"""

from __future__ import annotations

import csv
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_RULESET = REPO_ROOT / "go_with_the_flow_rules_v3_0_clean.csv"

# Must match R18's sanctioned set. `test_r18_sanctioned_types_match_the_rule` below binds
# these to the rule text, so the two cannot drift apart silently.
SANCTIONED_TYPES = frozenset(
    {
        "feat",
        "fix",
        "docs",
        "style",
        "refactor",
        "perf",
        "test",
        "build",
        "ci",
        "chore",
        "revert",
    }
)

CONVENTIONAL = re.compile(r"^(?P<type>[a-z]+)(?:\([^)]+\))?!?: ")
SCOPED = re.compile(r"^[a-z]+\([^)]+\)!?: ")

WINDOW = 200
TYPE_CONFORMANCE_FLOOR = 0.95
SCOPE_CONFORMANCE_FLOOR = 0.85


def _subjects(limit: int) -> list[str]:
    """Return recent commit subjects, or an empty list when history is unavailable."""
    try:
        completed = subprocess.run(
            ["git", "log", "--no-merges", f"-{limit}", "--pretty=%s"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):  # pragma: no cover - env dependent
        return []
    return [line for line in completed.stdout.splitlines() if line.strip()]


def _require_history() -> list[str]:
    """Skip rather than fail when the checkout cannot answer the question."""
    subjects = _subjects(WINDOW)
    if len(subjects) < WINDOW:
        pytest.skip(
            f"shallow or truncated history ({len(subjects)} of {WINDOW} subjects); "
            "conformance is measurable only against full history"
        )
    return subjects


def test_r18_sanctioned_types_match_the_rule() -> None:
    """Bind this module's type set to R18 so the two cannot drift apart."""
    with CANONICAL_RULESET.open(encoding="utf-8", newline="") as handle:
        rules = {row["rule_id"]: row for row in csv.DictReader(handle)}
    policy = rules["R18"]["description"]

    for sanctioned in SANCTIONED_TYPES:
        assert sanctioned in policy
    # `deploy` is explicitly unsanctioned; if that ever changes, this module must change too.
    assert "'deploy' is NOT sanctioned" in policy


def test_recent_commits_use_sanctioned_types() -> None:
    """Fail when the convention R18 describes stops being the convention in use."""
    subjects = _require_history()

    conforming = [
        subject
        for subject in subjects
        if (match := CONVENTIONAL.match(subject))
        and match.group("type") in SANCTIONED_TYPES
    ]
    rate = len(conforming) / len(subjects)
    offenders = [s for s in subjects if s not in conforming][:5]

    assert rate >= TYPE_CONFORMANCE_FLOOR, (
        f"type conformance {rate:.2%} over the last {len(subjects)} commits is below the "
        f"{TYPE_CONFORMANCE_FLOOR:.0%} floor; examples: {offenders}"
    )


def test_recent_commits_carry_a_scope() -> None:
    """R18 makes scope *expected*, not required, so this floor is deliberately looser."""
    subjects = _require_history()

    scoped = [subject for subject in subjects if SCOPED.match(subject)]
    rate = len(scoped) / len(subjects)

    assert rate >= SCOPE_CONFORMANCE_FLOOR, (
        f"scope usage {rate:.2%} over the last {len(subjects)} commits is below the "
        f"{SCOPE_CONFORMANCE_FLOOR:.0%} floor"
    )


@pytest.mark.parametrize(
    ("guard", "impossible_floor"),
    [
        (test_recent_commits_use_sanctioned_types, "TYPE_CONFORMANCE_FLOOR"),
        (test_recent_commits_carry_a_scope, "SCOPE_CONFORMANCE_FLOOR"),
    ],
)
def test_conformance_guards_fire_when_the_floor_is_unmet(
    monkeypatch: pytest.MonkeyPatch, guard: object, impossible_floor: str
) -> None:
    """A floor never observed to fail is an unverified claim (VERIFY-01)."""
    _require_history()
    monkeypatch.setitem(globals(), impossible_floor, 1.01)
    with pytest.raises(AssertionError):
        guard()  # type: ignore[operator]
