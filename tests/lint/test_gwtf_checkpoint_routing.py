"""Pin operational routing and reject removal of its safety boundaries."""

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
