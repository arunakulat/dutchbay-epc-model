"""Pin operational routing and reject removal of its safety boundaries."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "docs/governance/recruit_01/02_writer_lease_and_recovery.md"
CONTROLS = (
    "canonical allowlisted hook readiness",
    "execution completion separately from reporting observation",
    "never bypass platform restrictions",
    "do not grant writer authority",
    "fresh lease",
    "ordinary commit hooks",
    "preserve its digest independently",
)


def fence(text: str) -> None:
    normalized = " ".join(text.split()).casefold()
    for control in CONTROLS:
        assert control.casefold() in normalized, control


def test_checkpoint_operational_module() -> None:
    fence(MODULE.read_text())
    text = MODULE.read_text()
    for name in (
        "gwtf_checkpoint_readiness",
        "gwtf_checkpoint_receipt",
        "gwtf_interruption_recovery",
        "gwtf_incident",
    ):
        assert name in text
        assert (ROOT / "scripts" / f"{name}.py").is_file()


@pytest.mark.parametrize("control", CONTROLS)
def test_hostile_routing_removal(control: str) -> None:
    text = " ".join(MODULE.read_text().split()).casefold()
    with pytest.raises(AssertionError, match=control):
        fence(text.replace(control.casefold(), "REMOVED"))


@pytest.mark.parametrize(
    "name", ["AGENTS.md", ".claude/skills/steward/SKILL.md", "docs/DEVELOPMENT.md"]
)
def test_operational_routing(name: str) -> None:
    text = " ".join((ROOT / name).read_text().split()).casefold()
    assert "canonical allowlisted hook readiness" in text
    assert "execution completion separately from reporting observation" in text
    assert "never bypass platform restrictions" in text


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


ROUTING_CLAUSES = (
    "Use the R25 preflight with the exact coordinator-verified worktree, branch and live base.",
    "Reconcile committed blobs, parent, tree and clean worktree.",
    "A journal entry alone is not proof of execution, approval, signer identity or notification delivery.",
    "These tools do not grant writer authority, retry permission, independent acceptance, required CI or merge authority.",
    "The stricter applicable rule always wins.",
)


def test_operational_normative_scope() -> None:
    normative_clauses(
        MODULE.read_text(),
        "### 4.2 Operational checkpoint and incident routing",
        ROUTING_CLAUSES,
    )


@pytest.mark.parametrize("mutation", ["negate", "relocate", "quote"])
def test_operational_normative_hostile_context(mutation: str) -> None:
    heading = "### 4.2 Operational checkpoint and incident routing"
    clause = ROUTING_CLAUSES[3]
    body = " ".join(ROUTING_CLAUSES)
    if mutation == "negate":
        body = body.replace(clause, "It is false that " + clause)
    elif mutation == "quote":
        body = body.replace(clause, "Reject the statement: " + clause)
    else:
        body = body.replace(clause, "") + "\n### unrelated\n" + clause
    with pytest.raises(AssertionError):
        normative_clauses(heading + "\n" + body, heading, ROUTING_CLAUSES)
