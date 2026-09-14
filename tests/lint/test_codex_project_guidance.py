"""Guard the repository-level Codex instruction gateway."""

from __future__ import annotations

import os
import re
import subprocess
import sys
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
# globs the prose uses as examples do not trip the guard. The `docs/` prefix is
# optional because ten of the eleven live records name the pointer without it --
# requiring the prefix would miss the spelling the corpus itself models.
HANDOVER_PATTERN = re.compile(r"(?:docs/)?(?:SESSION_HANDOVER|H\d+)[0-9A-Za-z_\-]*\.md")
RESOLVER_SCRIPT = REPO_ROOT / "scripts/list_session_handover_records.py"


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


def _illustration_span(section: str) -> tuple[int, int] | None:
    """Return the exact illustration paragraph span, if present."""
    start = section.find(ILLUSTRATION_MARKER)
    if start < 0:
        return None
    paragraph_start = section.rfind("\n", 0, start) + 1
    paragraph_end = section.find("\n\n", start)
    if paragraph_end < 0:
        paragraph_end = len(section)
    return paragraph_start, paragraph_end


def _named_records_are_illustration_only(section: str) -> bool:
    """Report whether every named handover sits inside one illustration paragraph.

    The gateway may name a record to show what the resolution currently returns,
    but a name inside the instruction itself is the failure mode: it goes stale
    the moment a successor is written, and the reader follows it anyway.
    """
    named = list(HANDOVER_PATTERN.finditer(section))
    if not named:
        return True
    span = _illustration_span(section)
    if span is None:
        return False
    start, end = span
    return all(start <= match.start() < end for match in named)


def _git(repo: Path, *args: str, env: dict[str, str] | None = None) -> str:
    """Run a Git command in a hostile-oracle repository."""
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return completed.stdout


def _commit(repo: Path, message: str, iso_date: str) -> None:
    """Commit the complete hostile-oracle index at a controlled timestamp."""
    env = {
        **os.environ,
        "GIT_AUTHOR_DATE": iso_date,
        "GIT_COMMITTER_DATE": iso_date,
    }
    _git(repo, "commit", "-m", message, env=env)


def _run_resolver(repo: Path) -> subprocess.CompletedProcess[str]:
    """Execute the production resolver against a temporary Git repository."""
    return subprocess.run(
        [sys.executable, str(RESOLVER_SCRIPT)],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )


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
    assert "python scripts/list_session_handover_records.py" in section
    assert "commit that introduced each record" in section
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

    # Third negative control: the same defect spelled without the `docs/` prefix,
    # which is how ten of the eleven live records write it.
    bare = (
        "## Session continuity\n\n"
        "Before starting work, read `SESSION_HANDOVER_2026-09-07.md` and execute "
        "its **Bootstrap — run this first** section.\n"
    )
    assert not _named_records_are_illustration_only(bare)

    # A pointer appended below the illustration paragraph is still authoritative
    # prose and must not pass merely because it occurs after the marker.
    appended = section + "\nPinned startup: `docs/SESSION_HANDOVER_2099-01-01.md`.\n"
    assert not _named_records_are_illustration_only(appended)


def test_session_continuity_illustration_names_existing_records() -> None:
    """Require every illustration record to exist and its startup target to bootstrap."""
    section = _session_continuity_section()
    span = _illustration_span(section)
    assert span is not None, "the gateway must label its named record as an illustration"
    start, end = span
    named = HANDOVER_PATTERN.findall(section[start:end])
    assert len(named) >= 2, "the illustration must name its target and successor"

    records = [REPO_ROOT / path for path in named]
    for path, record in zip(named, records, strict=True):
        assert record.is_file(), f"{path} is named in AGENTS.md but does not exist"
    assert _carries_bootstrap_section(records[0].read_text(encoding="utf-8"))

    # Negative control: the predicate must reject a scope-specific successor,
    # or it is asserting nothing about the record it just accepted.
    assert not _carries_bootstrap_section(
        "# Session handover — scope-specific successor\n\n"
        "## Verified checkpoint\n\nNo bootstrap section here.\n"
    )


def test_handover_resolver_orders_by_introduction_not_last_touch(
    tmp_path: Path,
) -> None:
    """A later correction to an old record must not outrank its newer successor."""
    repo = tmp_path / "repo"
    docs = repo / "docs"
    docs.mkdir(parents=True)
    _git(repo, "init")
    _git(repo, "config", "user.name", "Resolver Test")
    _git(repo, "config", "user.email", "resolver@example.invalid")

    old = docs / "SESSION_HANDOVER_2026-01-01.md"
    old.write_text("old\n", encoding="utf-8")
    _git(repo, "add", old.relative_to(repo).as_posix())
    _commit(repo, "docs: add old handover", "2026-01-01T00:00:00+00:00")

    successor = docs / "H04_DELIVERY_RECORD.md"
    successor.write_text("newer\n", encoding="utf-8")
    _git(repo, "add", successor.relative_to(repo).as_posix())
    _commit(repo, "docs: add successor", "2026-01-02T00:00:00+00:00")

    old.write_text("old corrected later\n", encoding="utf-8")
    _git(repo, "add", old.relative_to(repo).as_posix())
    _commit(repo, "docs: correct old handover", "2026-01-03T00:00:00+00:00")

    result = _run_resolver(repo)
    assert result.returncode == 0, result.stderr
    paths = [line.split("\t")[-1] for line in result.stdout.splitlines()]
    assert paths[:2] == [
        "docs/H04_DELIVERY_RECORD.md",
        "docs/SESSION_HANDOVER_2026-01-01.md",
    ]


def test_handover_resolver_rejects_untracked_and_staged_records(
    tmp_path: Path,
) -> None:
    """Uncommitted successors must be visible as fail-loud ordering blockers."""
    repo = tmp_path / "repo"
    docs = repo / "docs"
    docs.mkdir(parents=True)
    _git(repo, "init")
    _git(repo, "config", "user.name", "Resolver Test")
    _git(repo, "config", "user.email", "resolver@example.invalid")

    committed = docs / "SESSION_HANDOVER_2026-01-01.md"
    committed.write_text("committed\n", encoding="utf-8")
    _git(repo, "add", committed.relative_to(repo).as_posix())
    _commit(repo, "docs: add baseline", "2026-01-01T00:00:00+00:00")

    candidate = docs / "H02_DELIVERY_HANDOVER.md"
    candidate.write_text("not durable\n", encoding="utf-8")
    untracked = _run_resolver(repo)
    assert untracked.returncode == 2
    assert "untracked: docs/H02_DELIVERY_HANDOVER.md" in untracked.stderr

    _git(repo, "add", candidate.relative_to(repo).as_posix())
    staged = _run_resolver(repo)
    assert staged.returncode == 2
    assert "staged: docs/H02_DELIVERY_HANDOVER.md" in staged.stderr
