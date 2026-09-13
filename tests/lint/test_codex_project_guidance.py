"""Guard the repository-level Codex instruction gateway."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_FILE = REPO_ROOT / "AGENTS.md"
CANONICAL_RULESET = "go_with_the_flow_rules_v3_0_clean.csv"
RETIRED_RULESET = "go_with_the_flow_rules_v3_0_merged_with_v14.csv"
RETIRED_BRANCH = "feature/add-finance-contracts-pydantic-v2-20251219"


def _guidance() -> str:
    """Return the complete repository-level Codex guidance."""
    return AGENTS_FILE.read_text(encoding="utf-8")


def test_codex_guidance_is_present_and_bounded() -> None:
    """Keep project guidance discoverable and below Codex's default size limit."""
    assert AGENTS_FILE.is_file()
    assert AGENTS_FILE.stat().st_size < 32 * 1024


def test_codex_guidance_uses_current_gwtf_authority() -> None:
    """Route Codex to the canonical ruleset and current governance rules."""
    guidance = _guidance()

    assert CANONICAL_RULESET in guidance
    for rule_id in (
        "WORKTREE-01",
        "GOV-02",
        "R23",
        "R25",
        "DELIVERY-01",
        "PERSIST-01",
        "THREAD-01",
        "RECRUIT-01",
    ):
        assert rule_id in guidance
    assert RETIRED_RULESET not in guidance
    assert RETIRED_BRANCH not in guidance


def test_codex_guidance_preserves_required_safety_and_quality_gates() -> None:
    """Prevent the Codex gateway from losing core workflow and model safeguards."""
    guidance = _guidance()

    required_phrases = (
        "dedicated worktree",
        "Dolphin Strategy",
        "origin/main",
        "finance/irr.py",
        "evaluate_with_overrides()",
        "strict=False",
        "DATA-01",
        "PYTHONDONTWRITEBYTECODE=1",
        "git diff --check",
        "DutchBay_EPC_Model",
        "/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python",
        "DUTCHBAY_VENV",
        "PYTHONPATH",
        "portable `.venv` fallback",
        "verify_shared_venv_worktrees.py",
        "every relevant task hereafter",
        "docs/governance/recruit_01/",
        "Load-bearing documentation",
    )
    for phrase in required_phrases:
        assert phrase in guidance


BOOTSTRAP_HEADING = "## Bootstrap — run this first"
ILLUSTRATION_MARKER = "Illustration, not authority"
# Matches a concrete record name, not a glob: `docs/H*_HANDOVER*.md` has no digits
# after the H and `docs/SESSION_HANDOVER_*.md` has no `.md` after the class, so the
# globs the prose uses as examples do not trip the guard.
HANDOVER_PATTERN = re.compile(r"docs/(?:SESSION_HANDOVER|H\d+)[0-9A-Za-z_\-]*\.md")


def _session_continuity_section() -> str:
    """Return the body of the AGENTS.md 'Session continuity' section."""
    guidance = _guidance()
    start = guidance.index("## Session continuity")
    end = guidance.index("\n## ", start + 1)
    return guidance[start:end]


def _carries_bootstrap_section(record_text: str) -> bool:
    """Report whether a record carries a bootstrap checklist to execute.

    This is a necessary condition for a startup record, not a kind classifier:
    `docs/SESSION_HANDOVER_2026-09-07_PR1178.md` calls itself a scoped successor
    and still carries the heading, though its body defers to its predecessor.
    What the illustration guard needs is exactly this weaker claim -- that the
    record it names has something to execute.
    """
    return BOOTSTRAP_HEADING in record_text


def _named_records_are_illustration_only(section: str) -> bool:
    """Report whether every named handover file sits in the illustration.

    The gateway may name a record to show what the resolution currently returns,
    but a name inside the instruction itself is the failure mode: it goes stale
    the moment a successor is written, and the reader follows it anyway.
    """
    named = list(HANDOVER_PATTERN.finditer(section))
    if not named:
        return True
    marker = section.find(ILLUSTRATION_MARKER)
    if marker < 0:
        return False
    return all(match.start() > marker for match in named)


def test_session_continuity_resolves_the_pointer_rather_than_pinning_a_filename() -> (
    None
):
    """Keep the startup pointer derivable, so it cannot silently go stale.

    The hardcoded form went stale between 2026-09-07 and 2026-09-13: eleven
    later handover records were written while the gateway still asserted that
    one named file *was* the newest record.
    """
    section = _session_continuity_section()

    assert "resolve the pointer rather than trusting a filename" in section
    assert "repository startup/bootstrap pointer" in section
    assert "Order by commit date" in section
    assert _named_records_are_illustration_only(section)

    # Negative control: the wording this replaced must fail the same predicate,
    # or the guard is defending against nothing.
    historical = (
        "## Session continuity\n\n"
        "Before starting work, read the newest record in `docs/SESSION_HANDOVER_*.md` "
        "\u2014 currently\n`docs/SESSION_HANDOVER_2026-09-07.md` \u2014 and execute its "
        "**Bootstrap \u2014 run this first**\nsection before substantive work.\n"
    )
    assert not _named_records_are_illustration_only(historical)

    # Second negative control: the same defect spelled with an H-family record.
    # The prose names that family, so a guard blind to it would be narrower than
    # the text it defends.
    h_family = (
        "## Session continuity\n\n"
        "Before starting work, read `docs/H08_DELIVERY_HANDOVER.md` and execute "
        "its bootstrap.\n"
    )
    assert not _named_records_are_illustration_only(h_family)


def test_session_continuity_illustration_is_a_real_startup_record() -> None:
    """The dated illustration must still resolve to an executable bootstrap.

    This is the guard a naive 'newest file by date' rule would fail: the newest
    record by filename is a scope-specific successor with no bootstrap section,
    so pointing at it would leave the next session with nothing to execute.
    """
    section = _session_continuity_section()
    marker = section.find(ILLUSTRATION_MARKER)
    assert marker >= 0, "the gateway must label its named record as an illustration"
    named = HANDOVER_PATTERN.findall(section[marker:])
    assert named, "the illustration must name the record it resolved to"

    record = REPO_ROOT / named[0]
    assert record.is_file(), f"{named[0]} is named in AGENTS.md but does not exist"
    assert _carries_bootstrap_section(record.read_text(encoding="utf-8"))

    # Negative control: the predicate must reject a scope-specific successor,
    # or it is asserting nothing about the record it just accepted.
    assert not _carries_bootstrap_section(
        "# Session handover — scope-specific successor\n\n"
        "## Verified checkpoint\n\nNo bootstrap section here.\n"
    )
