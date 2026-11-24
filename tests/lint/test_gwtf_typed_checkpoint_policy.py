"""Fence the owner-required typed checkpoint routine and its authority boundary."""

from __future__ import annotations

import csv
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RULES = ROOT / "go_with_the_flow_rules_v3_0_clean.csv"
CONTROLS = (
    "targeted mypy",
    "final formatter-stable bytes",
    "governed interpreter",
    "Missing or failing type evidence blocks qualification",
    "persistence-only rescue is not qualified",
)


def check_policy(text: str, controls: tuple[str, ...]) -> None:
    normalized = " ".join(text.split()).casefold()
    for control in controls:
        assert control.casefold() in normalized, control


@pytest.mark.parametrize(
    "path",
    [
        "AGENTS.md",
        ".claude/skills/steward/SKILL.md",
        "docs/governance/recruit_01/02_writer_lease_and_recovery.md",
    ],
)
def test_routine_routed(path: str) -> None:
    text = (ROOT / path).read_text()
    check_policy(text, CONTROLS)


def test_canonical_rule_controls() -> None:
    with RULES.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
        rules = {row["rule_id"]: row for row in rows}
    assert len(rules) == len(rows), "duplicate rule identity"
    assert set(("R21", "VERIFY-01", "R23", "RECRUIT-01")) <= rules.keys()
    assert all(
        rules[key]["status"] == "active"
        for key in ("R21", "VERIFY-01", "R23", "RECRUIT-01")
    )
    r21 = rules["R21"]["description"]
    check_policy(
        r21,
        (
            "targeted mypy",
            "final formatter-stable candidate bytes",
            "governed interpreter",
            "Missing or failing type evidence blocks qualification",
            "persistence-only rescue is not qualified",
            "full suite before pushing",
            "all existing local and CI type gates remain mandatory",
        ),
    )
    check_policy(
        rules["VERIFY-01"]["description"],
        (
            "targeted mypy",
            "configuration identity",
            "log digest",
            "final candidate hashes",
            "Missing or failing type evidence blocks qualification",
            "not run is not PASS",
        ),
    )


@pytest.mark.parametrize("removed", CONTROLS)
def test_hostile_control_removal_rejected(removed: str) -> None:
    text = (
        ROOT / "docs/governance/recruit_01/02_writer_lease_and_recovery.md"
    ).read_text()
    normalized = " ".join(text.split()).casefold()
    assert removed.casefold() in normalized
    with pytest.raises(AssertionError, match=removed):
        check_policy(normalized.replace(removed.casefold(), "REMOVED"), CONTROLS)


# Deliberately pin full normative clauses in their operative section, rather
# than claiming that a substring test understands arbitrary natural language.
TYPED_CLAUSES = (
    "Before qualifying a checkpoint that changes typed Python, stubs, or a type/import contract, run successful targeted mypy against the affected surface with the governed interpreter and applicable existing CI gate configuration.",
    "Missing or failing type evidence blocks qualification.",
    "A persistence-only rescue is not qualified and grants no review or merge authority.",
    "No error suppression or gate weakening is a remedy for a failed type check.",
)


def section(text: str, heading: str) -> str:
    lines = text.splitlines()
    positions = [i for i, line in enumerate(lines) if line == heading]
    assert len(positions) == 1, heading
    start = positions[0]
    depth = len(heading.split()[0])
    end = next(
        (
            i
            for i in range(start + 1, len(lines))
            if re.match(r"^#{1," + str(depth) + r"} ", lines[i])
        ),
        len(lines),
    )
    return " ".join(" ".join(lines[start + 1 : end]).split())


def normative_clauses(text: str, heading: str, clauses: tuple[str, ...]) -> None:
    body = section(text, heading)
    for clause in clauses:
        # Sentence-boundary requirement rejects a prefixed negation or
        # quotation; scope excludes occurrences in unrelated headings.
        assert re.search(
            r"(?:^|(?<=[.!?]) )" + re.escape(clause) + r"(?= |$)", body
        ), clause


def test_typed_normative_scope() -> None:
    text = (
        ROOT / "docs/governance/recruit_01/02_writer_lease_and_recovery.md"
    ).read_text()
    normative_clauses(
        text, "### 4.1 Typed-code checkpoint qualification", TYPED_CLAUSES
    )


@pytest.mark.parametrize("mutation", ["negate", "relocate", "quote"])
def test_typed_normative_hostile_context(mutation: str) -> None:
    heading = "### 4.1 Typed-code checkpoint qualification"
    body = " ".join(TYPED_CLAUSES)
    clause = TYPED_CLAUSES[1]
    if mutation == "negate":
        body = body.replace(clause, "It is false that " + clause)
    elif mutation == "quote":
        body = body.replace(clause, "Reject the statement: " + clause)
    else:
        body = body.replace(clause, "") + "\n### unrelated\n" + clause
    with pytest.raises(AssertionError):
        normative_clauses(heading + "\n" + body, heading, TYPED_CLAUSES)


def test_typed_normative_whitespace_is_not_semantic_drift() -> None:
    heading = "### 4.1 Typed-code checkpoint qualification"
    normative_clauses(
        heading + "\n" + "  \n".join(TYPED_CLAUSES), heading, TYPED_CLAUSES
    )
