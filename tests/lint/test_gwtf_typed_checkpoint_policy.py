"""Fence the owner-required typed checkpoint routine and its authority boundary."""

from __future__ import annotations

import csv
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
        rules = {row["rule_id"]: row for row in csv.DictReader(stream)}
    assert len(rules) == 79
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
