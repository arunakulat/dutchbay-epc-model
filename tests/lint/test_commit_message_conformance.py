"""Measure commit-type conformance instead of freezing a figure into R18.

`R18` drifted because its enforcement pinned a single example commit. Replacing that with
a pinned *percentage* would institutionalise the same decay, so this module computes the
figure instead of storing one.

**What this is, precisely.** The MEASUREMENT half is a local authoring-time and pre-push
aid, not a CI gate and not part of R18's enforcement: every sharded CI job checks out at
the default depth of 1, and `R21` requires the full suite before pushing, which is where it
runs. The BINDING half runs everywhere, including CI, because it reads the CSV rather than
git history -- and the binding is what catches this module and R18 drifting apart.
Verified on a genuine `--depth 1` clone with no `origin/main`: 3 passed, 2 skipped; only
the two history-dependent tests skip. An earlier draft of this docstring claimed the module
"still runs in the full-history jobs" -- two independent reviewers established no such job
exists -- and a later draft said 4 of 5 tests skip, which was true of the superseded
version, not this one.

**Scope is deliberately not gated.** An earlier draft asserted a scope-usage floor. That
was a category error: `R18` makes scope *expected*, not required, and explicitly sanctions
unscoped commits for cross-cutting work and for `REFACTOR-03` Dolphin Strategy commits. A
ratchet cannot gate what the rule leaves optional. The floor was also authored at exactly
the observed value -- 170/200, zero headroom -- which would have failed on the next
sanctioned unscoped commit, on a check that only runs where `R21` now makes it mandatory.

**Measured against `origin/main`, not `HEAD`.** A branch-relative measurement reports on
whichever branch the runner stands on rather than on the shared history under test.
"""

from __future__ import annotations

import csv
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_RULESET = REPO_ROOT / "go_with_the_flow_rules_v3_0_clean.csv"

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
ENUMERATION = re.compile(r"config-conventional - (?P<types>[a-z, ]+?)\.")

REFERENCE = "origin/main"
WINDOW = 200
# A ratchet floor, not a target: measured conformance sits near 99%, so this fails only on
# a genuine collapse of the convention rather than on ordinary variation.
TYPE_CONFORMANCE_FLOOR = 0.90


def _r18_description() -> str:
    """Return R18's description cell from the canonical ruleset."""
    with CANONICAL_RULESET.open(encoding="utf-8", newline="") as handle:
        rules = {row["rule_id"]: row for row in csv.DictReader(handle)}
    return rules["R18"]["description"]


def _subjects() -> list[str]:
    """Return recent `origin/main` subjects, or [] when that history is unavailable."""
    try:
        completed = subprocess.run(
            ["git", "log", "--no-merges", f"-{WINDOW}", "--pretty=%s", REFERENCE],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return []
    return [line for line in completed.stdout.splitlines() if line.strip()]


def _require_history() -> list[str]:
    """Skip rather than fail when the checkout cannot answer the question."""
    subjects = _subjects()
    if len(subjects) < WINDOW:
        pytest.skip(
            f"{REFERENCE} history unavailable or shallow ({len(subjects)} of {WINDOW} "
            "subjects); conformance is measurable only against full history"
        )
    return subjects


def test_sanctioned_types_match_r18_exactly() -> None:
    """Bind this module's set to R18 by SET EQUALITY, in both directions.

    Substring presence bound nothing: `ci` matched inside "explicit", so removing it from
    the rule left the guard green, and adding a type to the rule was not checked at all.
    Parsing the enumeration and comparing sets catches both.
    """
    match = ENUMERATION.search(_r18_description())
    assert match is not None, "R18 no longer enumerates its types in the expected form"

    declared = {token.strip() for token in match.group("types").split(",")}
    assert declared == set(SANCTIONED_TYPES), (
        f"R18 declares {sorted(declared)} but this module tracks "
        f"{sorted(SANCTIONED_TYPES)}; update both together"
    )


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
        f"type conformance {rate:.2%} over the last {len(subjects)} commits on "
        f"{REFERENCE} is below the {TYPE_CONFORMANCE_FLOOR:.0%} floor; examples: {offenders}"
    )


def test_conformance_guard_fires_when_the_floor_is_unmet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A floor never observed to fail is an unverified claim (VERIFY-01)."""
    _require_history()
    monkeypatch.setitem(globals(), "TYPE_CONFORMANCE_FLOOR", 1.01)
    with pytest.raises(AssertionError):
        test_recent_commits_use_sanctioned_types()


@pytest.mark.parametrize("mutation", ["drop", "add"])
def test_type_binding_guard_fires_in_both_directions(
    monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    """Prove the set-equality binding catches removal AND addition."""
    if mutation == "drop":
        mutated = frozenset(SANCTIONED_TYPES - {"revert"})
    else:
        mutated = frozenset(SANCTIONED_TYPES | {"deploy"})

    monkeypatch.setitem(globals(), "SANCTIONED_TYPES", mutated)
    with pytest.raises(AssertionError):
        test_sanctioned_types_match_r18_exactly()
