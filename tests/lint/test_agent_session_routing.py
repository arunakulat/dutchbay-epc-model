"""Keep ``docs/governance/agent_session_routing.md`` a router, not a second ruleset.

The note sends any agent session to the sources that govern it and restates none of them.
Its value rests on three things a later edit could silently break, so each is pinned:

1. every rule ID it cites in backticks is a row of the canonical ruleset;
2. every repository path it cites exists, and every ``AGENTS.md`` or ``CLAUDE.md`` section
   it quotes by heading is still a heading there; and
3. the line stating that the note grants no merge, review, lease or approval authority is
   present, and ``AGENTS.md`` still points at the note.

#1498 proposed a longer skill that paraphrased five rules and drifted from them before it
merged. A router whose citations are checked cannot drift that way. Each guard is a pure
function over text, with a negative control below that breaks it and watches it fail.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_RULESET = REPO_ROOT / "go_with_the_flow_rules_v3_0_clean.csv"
NOTE = REPO_ROOT / "docs" / "governance" / "agent_session_routing.md"
AGENTS = REPO_ROOT / "AGENTS.md"
NOTE_PATH = "docs/governance/agent_session_routing.md"
AUTHORITY_LINE = (
    "This note grants no merge, review, lease or approval authority to any session."
)

_BACKTICKED = re.compile(r"`([^`\n]+)`")
_RULE_ID = re.compile(r"^(?:[A-Z][A-Z0-9_]*-\d{2}|R\d+)$")
_PATH = re.compile(r"^[\w.][\w./-]*(?:/|\.(?:md|py|csv|sh|yml|yaml|toml))$")
_QUOTED_SECTION = re.compile(r'`(AGENTS\.md|CLAUDE\.md)` "([^"]+)"')


def _rule_ids() -> set[str]:
    with CANONICAL_RULESET.open(encoding="utf-8", newline="") as handle:
        return {row["rule_id"] for row in csv.DictReader(handle)}


def cited_rule_ids(text: str) -> set[str]:
    """Return the backticked tokens shaped like a GWTF rule ID."""
    return {token for token in _BACKTICKED.findall(text) if _RULE_ID.match(token)}


def cited_paths(text: str) -> set[str]:
    """Return the backticked tokens shaped like a repository path."""
    return {token for token in _BACKTICKED.findall(text) if _PATH.match(token)}


def unknown_rule_ids(text: str, known: set[str]) -> list[str]:
    """Return cited rule IDs that the ruleset does not carry."""
    return sorted(cited_rule_ids(text) - known)


def missing_paths(text: str, root: Path) -> list[str]:
    """Return cited paths that do not exist under ``root``."""
    return sorted(path for path in cited_paths(text) if not (root / path).exists())


def missing_sections(text: str, root: Path) -> list[str]:
    """Return quoted ``AGENTS.md``/``CLAUDE.md`` sections that are no longer headings."""
    missing = []
    for filename, quoted in _QUOTED_SECTION.findall(text):
        heading = " ".join(quoted.split())  # a quote may wrap across a Markdown line
        source = (root / filename).read_text(encoding="utf-8")
        if not re.search(rf"^#{{2,4}} {re.escape(heading)}$", source, re.MULTILINE):
            missing.append(f"{filename}: {heading}")
    return sorted(missing)


def states_no_authority(text: str) -> bool:
    """Return whether the note carries its authority line on a line of its own."""
    return AUTHORITY_LINE in text.splitlines()


def test_note_cites_rules_and_paths() -> None:
    """The note cites at least the rules and files its routing depends on."""
    text = NOTE.read_text(encoding="utf-8")
    assert {"MERGE-01", "REVIEW-01", "RECRUIT-01", "INTAKE-01", "VERIFY-01"} <= (
        cited_rule_ids(text)
    )
    assert {"AGENTS.md", "CLAUDE.md", "go_with_the_flow_rules_v3_0_clean.csv"} <= (
        cited_paths(text)
    )


def test_every_cited_rule_id_is_in_the_ruleset() -> None:
    """A cited rule that the CSV does not carry is a rule the note invented."""
    text = NOTE.read_text(encoding="utf-8")
    assert unknown_rule_ids(text, _rule_ids()) == []


def test_every_cited_path_exists() -> None:
    """A cited path that is gone sends the reader nowhere."""
    text = NOTE.read_text(encoding="utf-8")
    assert missing_paths(text, REPO_ROOT) == []


def test_every_quoted_section_is_still_a_heading() -> None:
    """A renamed section in ``AGENTS.md`` or ``CLAUDE.md`` must be renamed here too."""
    text = NOTE.read_text(encoding="utf-8")
    assert _QUOTED_SECTION.search(text) is not None
    assert missing_sections(text, REPO_ROOT) == []


def test_note_grants_no_authority() -> None:
    """The authority line is what keeps the note from reading as a grant."""
    assert states_no_authority(NOTE.read_text(encoding="utf-8"))


def test_agents_md_points_at_the_note() -> None:
    """``AGENTS.md`` is where a non-Codex session is told to start."""
    agents = AGENTS.read_text(encoding="utf-8")
    assert f"`{NOTE_PATH}`" in agents
    assert "grants no merge, review, lease or approval" in agents


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Follow `AGENT-01` before work.", ["AGENT-01"]),
        ("Commits follow `R999`.", ["R999"]),
        ("Merge under `MERGE-01`.", []),
    ],
)
def test_unknown_rule_guard_fails_on_an_invented_rule(
    text: str, expected: list[str]
) -> None:
    """Negative control: an ID absent from the CSV is reported."""
    assert unknown_rule_ids(text, _rule_ids()) == expected


def test_missing_path_guard_fails_on_a_removed_file() -> None:
    """Negative control: a path that does not exist is reported."""
    text = "Read `docs/governance/multi_agent_operating_skill.md` and `AGENTS.md`."
    assert missing_paths(text, REPO_ROOT) == [
        "docs/governance/multi_agent_operating_skill.md"
    ]


def test_missing_section_guard_fails_on_a_renamed_heading() -> None:
    """Negative control: a quoted heading that is not in the file is reported."""
    text = '`AGENTS.md` "Session continuity" and `CLAUDE.md` "No such section".'
    assert missing_sections(text, REPO_ROOT) == ["CLAUDE.md: No such section"]


def test_authority_guard_fails_without_the_line() -> None:
    """Negative control: dropping or rewording the authority line is caught."""
    text = NOTE.read_text(encoding="utf-8")
    assert not states_no_authority(text.replace(AUTHORITY_LINE, ""))
    assert not states_no_authority(
        text.replace(AUTHORITY_LINE, AUTHORITY_LINE.replace("no merge, ", ""))
    )
