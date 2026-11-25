"""Bounded policy and CI-step contract fences, not a general semantic parser."""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]

ROUTING = (
    "- **Checkpoint routing.** Use canonical allowlisted hook readiness, final-byte "
    "verification, staged and committed blob/mode reconciliation, and the external "
    "evidence journal (RECRUIT-01 module 2 §4.2). Record execution completion "
    "separately from reporting observation. Poll active processes while executing; "
    "persist outstanding process identity and handover on interruption. Use "
    "read-only recovery and fixed-schema incident classification; never bypass "
    "platform restrictions or treat helper output as writer or merge authority."
)
AGENT_TYPED = (
    "Before typed-code checkpoint qualification, run successful targeted mypy on final "
    "formatter-stable bytes using the governed interpreter and applicable CI gate "
    "configuration, including the affected type/import surface. Bind the command, "
    "versions, configuration, scope, result, log digest and candidate hashes to the "
    "receipt (R21, VERIFY-01, RECRUIT-01 module 2 §4.1). Missing or failing type "
    "evidence blocks qualification. A persistence-only rescue is not qualified. "
    "All existing pre-push and CI gates remain mandatory. Preferred focused commands are:"
)
STEWARD_TYPED = (
    "- **Typed-code checkpoints.** Require successful targeted mypy on final formatter-stable "
    "bytes, with the governed interpreter and applicable CI gate configuration. "
    "Record command, versions, configuration, scope, result, log digest and candidate "
    "hashes. Missing or failing type evidence blocks qualification; persistence-only "
    "rescue is not qualified. Re-run after relevant drift; preserve all existing "
    "local and CI type gates (R21, VERIFY-01, RECRUIT-01 module 2 §4.1)."
)
DEV_ROUTING = (
    "For checkpoint operations follow RECRUIT-01 module 2 §4.2: canonical allowlisted "
    "hook readiness, final-byte tests/type evidence, staged and committed blob/mode "
    "reconciliation, and an external evidence journal. Record execution completion "
    "separately from reporting observation. Use read-only recovery and fixed-schema "
    "incident classification; never bypass platform restrictions. These tools "
    "do not authenticate a writer or grant approval."
)
DEV_TYPED = (
    "Typed-code checkpoint qualification requires successful targeted mypy on final "
    "formatter-stable bytes in the governed environment, using the applicable "
    "existing CI configuration and covering the affected type/import surface. Record "
    "command, versions, configuration identity, scope, result, log digest and final "
    "candidate hashes. Missing or failing type evidence blocks qualification; a "
    "persistence-only rescue is not qualified. This routine does not replace the "
    "existing full pre-push or CI gates or enable the disabled local mypy hook "
    "(see RECRUIT-01 module 2 §4.1 and #1270)."
)
SURFACES = (
    ("AGENTS.md", "## Verification", (ROUTING, AGENT_TYPED)),
    (
        ".claude/skills/steward/SKILL.md",
        "## Changes you push",
        (ROUTING, STEWARD_TYPED),
    ),
    (
        ".agents/skills/steward/SKILL.md",
        "## Changes you push",
        (ROUTING, STEWARD_TYPED),
    ),
    ("docs/DEVELOPMENT.md", "### Pre-commit hooks", (DEV_ROUTING, DEV_TYPED)),
)


def normalized(text: str) -> str:
    return " ".join(text.split())


def operative_blocks(text: str, heading: str) -> list[str]:
    """Ignore fenced examples, comments and quoted blocks; scope to one heading."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    visible: list[str] = []
    fence: str | None = None
    for line in text.splitlines():
        match = re.match(r"^ {0,3}(```+|~~~+)", line)
        if match:
            mark = match[1]
            if fence is None:
                fence = mark
            elif mark[0] == fence[0] and len(mark) >= len(fence):
                fence = None
            continue
        if fence is None and not re.match(r"^\s*>", line):
            visible.append(line)
    positions = [i for i, line in enumerate(visible) if line == heading]
    assert len(positions) == 1, heading
    start = positions[0]
    depth = len(heading.split()[0])
    end = next(
        (
            i
            for i in range(start + 1, len(visible))
            if re.match(r"^#{1," + str(depth) + r"} ", visible[i])
        ),
        len(visible),
    )
    # Treat each list item or blank-line-delimited prose paragraph as a block.
    blocks: list[str] = []
    current: list[str] = []
    for line in visible[start + 1 : end]:
        if not line.strip() or re.match(r"^- ", line):
            if current:
                blocks.append(normalized(" ".join(current)))
                current = []
        if line.strip():
            current.append(line)
    if current:
        blocks.append(normalized(" ".join(current)))
    return blocks


def check_surface(text: str, heading: str, clauses: tuple[str, ...]) -> None:
    blocks = operative_blocks(text, heading)
    for clause in clauses:
        assert blocks.count(clause) == 1, clause


@pytest.mark.parametrize(("path", "heading", "clauses"), SURFACES)
def test_policy_surface(path: str, heading: str, clauses: tuple[str, ...]) -> None:
    check_surface((ROOT / path).read_text(), heading, clauses)


@pytest.mark.parametrize(("path", "heading", "clauses"), SURFACES)
@pytest.mark.parametrize(
    "mutation", ["negate", "comment", "fence", "quote", "relocate"]
)
def test_hidden_or_negated_policy_not_operative(
    path: str, heading: str, clauses: tuple[str, ...], mutation: str
) -> None:
    # Exercise actual routed policy content, not just the search phrase.
    body = "\n\n".join(clauses)
    check_surface(heading + "\n\n" + body, heading, clauses)
    clause = clauses[-1]
    replacements = {
        "negate": "It is false that " + clause,
        "comment": "<!-- " + clause + " -->",
        "fence": "```text\n" + clause + "\n```",
        "quote": "> " + clause,
        "relocate": heading + " unrelated\n\n" + clause,
    }
    assert path
    with pytest.raises(AssertionError):
        check_surface(
            heading + "\n\n" + body.replace(clause, replacements[mutation]),
            heading,
            clauses,
        )


RULE_SUFFIXES = {
    "R21": "Typed-code checkpoint qualification requires successful targeted mypy using the governed interpreter, on the final formatter-stable candidate bytes and affected type/import surface; use the applicable existing CI gate configuration. Missing or failing type evidence blocks qualification. A persistence-only rescue is not qualified. The full suite before pushing and all existing local and CI type gates remain mandatory.",
    "VERIFY-01": "For typed-code checkpoint qualification, persist the targeted mypy command, interpreter and mypy version, configuration identity, scope, exit result, log digest and final candidate hashes; repeat after relevant byte or environment drift. Missing or failing type evidence blocks qualification. A not-applicable claim requires a recorded scope rationale and independent challenge; not run is not PASS. See RECRUIT-01 module 2.",
}


def check_rule_suffix(text: str, clause: str) -> None:
    assert re.search(
        r"(?:^|(?<=[.!?]) )" + re.escape(clause) + r"$", normalized(text)
    ), clause


@pytest.mark.parametrize(("rule", "clause"), RULE_SUFFIXES.items())
def test_canonical_operative_rule(rule: str, clause: str) -> None:
    with (ROOT / "go_with_the_flow_rules_v3_0_clean.csv").open(newline="") as stream:
        rows = [r for r in csv.DictReader(stream) if r["rule_id"] == rule]
    assert len(rows) == 1 and rows[0]["status"] == "active"
    text = rows[0]["description"]
    check_rule_suffix(text, clause)
    for replacement in (
        "It is false that " + clause,
        '"' + clause + '"',
        clause + " This clause is optional.",
    ):
        with pytest.raises(AssertionError):
            check_rule_suffix(text.replace(clause, replacement), clause)


# Independently inspected predecessor CI steps. The FX scoped check is
# advisory in the inherited workflow; never misrepresent it as blocking.
CI_STEPS = (
    (
        "test-suite.yml",
        "lint",
        "Run mypy (library + engine surface — strict, fail-loud)",
        "mypy finance/ analytics/ wind_resource/ solar_resource/ api/ app/ analysis_tools/ run_full_pipeline_v14.py run_scenario_analytics_v14.py dutchbay_bootstrap.py dutchbay_bootstrap_rules.py constants.py",
        False,
    ),
    (
        "test-suite.yml",
        "lint",
        "Run mypy (scripts/ — real-error gate)",
        "mypy scripts/ --ignore-missing-imports --allow-untyped-defs --allow-untyped-calls --allow-any-generics",
        False,
    ),
    (
        "ci_v14_fastlane.yml",
        "fastlane",
        "Mypy - focused v14 surface",
        "python -m mypy --follow-imports=skip analytics/contracts_v14.py analytics/contracts/__init__.py analytics/scenario_loader.py analytics/fx_sensitivity_real.py run_full_pipeline_v14.py",
        False,
    ),
    (
        "fx-tests.yml",
        "code-quality",
        "Type check with mypy",
        "mypy analytics/fx/ --ignore-missing-imports",
        True,
    ),
    (
        "regression-smoke.yml",
        "smoke",
        "Type check focused smoke surface",
        "python -m mypy --follow-imports=skip analytics/contracts_v14.py analytics/contracts/__init__.py analytics/scenario_loader.py run_full_pipeline_v14.py",
        False,
    ),
)


def check_ci_step(
    doc: dict[str, Any], job_id: str, name: str, command: str, advisory: bool
) -> None:
    job = doc["jobs"][job_id]
    assert "if" not in job and "continue-on-error" not in job
    matches = [step for step in job["steps"] if step.get("name") == name]
    assert len(matches) == 1
    step = matches[0]
    assert "if" not in step
    assert step.get("continue-on-error", False) is advisory
    assert normalized(step["run"].replace("\\\n", " ")) == command


@pytest.mark.parametrize(("file", "job", "name", "command", "advisory"), CI_STEPS)
def test_ci_type_step_preserved(
    file: str, job: str, name: str, command: str, advisory: bool
) -> None:
    doc = yaml.safe_load((ROOT / ".github/workflows" / file).read_text())
    check_ci_step(doc, job, name, command, advisory)


@pytest.mark.parametrize(("file", "job", "name", "command", "advisory"), CI_STEPS)
@pytest.mark.parametrize(
    "mutation", ["swallow", "skip", "failure_flag", "job_skip", "job_failure_flag"]
)
def test_ci_type_step_mutations_rejected(
    file: str, job: str, name: str, command: str, advisory: bool, mutation: str
) -> None:
    doc = yaml.safe_load((ROOT / ".github/workflows" / file).read_text())
    check_ci_step(doc, job, name, command, advisory)
    j = doc["jobs"][job]
    step = next(s for s in j["steps"] if s.get("name") == name)
    if mutation == "swallow":
        step["run"] += " || true"
    elif mutation == "skip":
        step["if"] = False
    elif mutation == "failure_flag":
        step["continue-on-error"] = not advisory
    elif mutation == "job_skip":
        j["if"] = False
    else:
        j["continue-on-error"] = True
    with pytest.raises(AssertionError):
        check_ci_step(doc, job, name, command, advisory)
