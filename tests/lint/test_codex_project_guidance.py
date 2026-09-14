"""Guard the repository-level Codex instruction gateway."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

from scripts.list_session_handover_records import prose_record_matches
from scripts.list_session_handover_records import prose_record_references

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
RESOLVER_SCRIPT = REPO_ROOT / "scripts/list_session_handover_records.py"


def _session_continuity_section() -> str:
    """Return the body of the AGENTS.md 'Session continuity' section."""
    guidance = _guidance()
    start = guidance.index("## Session continuity")
    end = guidance.index("\n## ", start + 1)
    return guidance[start:end]


def _carries_bootstrap_section(record_text: str) -> bool:
    """Report whether an unfenced bootstrap H2 has a nonempty section body."""
    lines = record_text.splitlines()
    fence: tuple[str, int] | None = None
    delimiter_lines: set[int] = set()
    unfenced: list[bool] = []
    html_comment = False
    raw_tag: str | None = None
    for index, line in enumerate(lines):
        stripped = line.lstrip(" ")
        indent = len(line) - len(stripped)
        line_hidden = html_comment or raw_tag is not None
        if "<!--" in line and not html_comment:
            line_hidden = True
            html_comment = "-->" not in line.split("<!--", 1)[1]
        elif html_comment and "-->" in line:
            html_comment = False
        if raw_tag is None:
            opening_tag = re.match(
                r"<(pre|script|style|textarea)(?:\s|>)", stripped, re.IGNORECASE
            )
            if opening_tag:
                raw_tag = opening_tag.group(1).lower()
                line_hidden = True
        elif re.search(rf"</{raw_tag}\s*>", stripped, re.IGNORECASE):
            raw_tag = None
        unfenced.append(fence is None and not line_hidden)
        if indent > 3:
            continue
        if fence is None:
            opening = re.match(r"(`{3,}|~{3,})", stripped)
            if opening is None:
                continue
            token = opening.group(1)
            fence = (token[0], len(token))
            delimiter_lines.add(index)
            continue
        closing = re.fullmatch(
            rf"{re.escape(fence[0])}{{{fence[1]},}}[ \t]*", stripped
        )
        if closing is not None:
            fence = None
            delimiter_lines.add(index)

    for index, line in enumerate(lines):
        if not unfenced[index] or line.rstrip() != BOOTSTRAP_HEADING:
            continue
        end = len(lines)
        for candidate in range(index + 1, len(lines)):
            if unfenced[candidate] and re.match(r"^#{1,2}\s+", lines[candidate]):
                end = candidate
                break
        return any(
            line.strip() and body_index not in delimiter_lines
            for body_index, line in enumerate(lines[index + 1 : end], start=index + 1)
        )
    return False


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
    named = prose_record_matches(section)
    if not named:
        return True
    span = _illustration_span(section)
    if span is None:
        return False
    start, end = span
    return all(start <= match_start < end for match_start, _, _ in named)


def _illustration_records(section: str) -> list[str]:
    """Return normalized record paths named in the illustration paragraph."""
    span = _illustration_span(section)
    if span is None:
        return []
    start, end = span
    return [
        name if name.startswith("docs/") else f"docs/{name}"
        for name in prose_record_references(section[start:end])
    ]


def _illustration_records_exist(section: str) -> bool:
    """Report whether every concrete illustration record exists."""
    return all((REPO_ROOT / name).is_file() for name in _illustration_records(section))


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
        "Before starting work, read the newest record in "
        "`docs/SESSION_HANDOVER_*.md` \u2014 currently\n"
        "`docs/SESSION_HANDOVER_2026-09-07.md` \u2014 and execute its "
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

    dotted_before = section.replace(
        "*Illustration, not authority",
        "Pinned startup: `H99_HANDOVER.review.v2.md`.\n\n"
        "*Illustration, not authority",
        1,
    )
    assert not _named_records_are_illustration_only(dotted_before)

    dotted_after = section + "\nPinned: `docs/H99_DELIVERY_RECORD.v2.md`.\n"
    assert not _named_records_are_illustration_only(dotted_after)

    unquoted_space_before = section.replace(
        "*Illustration, not authority",
        "Pinned startup: H99_HANDOVER review.v2.md.\n\n"
        "*Illustration, not authority",
        1,
    )
    assert not _named_records_are_illustration_only(unquoted_space_before)

    unquoted_space_after = (
        section + "\nPinned startup: docs/H99_DELIVERY_RECORD review.v2.md.\n"
    )
    assert not _named_records_are_illustration_only(unquoted_space_after)

    bounded_forms = (
        "Ignore `docs/SESSION_HANDOVER_*.md`; then use "
        "[docs/H91_HANDOVER link.v2.md](target), "
        "\"H92_HANDOVER quoted.md\", 'H93_DELIVERY_RECORD single.md', "
        "(H94_HANDOVER parenthesized.md), and —H95_HANDOVER unicode.md.\n"
        "A rejected cross-line glob `docs/H96_HANDOVER_*\n"
        "must not hide docs/H97_HANDOVER next-line.md."
    )
    assert prose_record_references(bounded_forms) == [
        "docs/H91_HANDOVER link.v2.md",
        "H92_HANDOVER quoted.md",
        "H93_DELIVERY_RECORD single.md",
        "H94_HANDOVER parenthesized.md",
        "H95_HANDOVER unicode.md",
        "docs/H97_HANDOVER next-line.md",
    ]
    qualified = (
        "Ignore SESSION_HANDOVER_* without a terminator; use "
        "./docs/H81_HANDOVER repo.md, ../docs/H82_HANDOVER parent.md, and "
        "/tmp/project/docs/H83_HANDOVER absolute.md."
    )
    assert prose_record_references(qualified) == [
        "docs/H81_HANDOVER repo.md",
        "docs/H82_HANDOVER parent.md",
        "docs/H83_HANDOVER absolute.md",
    ]

    span = _illustration_span(section)
    assert span is not None
    nonexistent_inside = (
        section[: span[1]]
        + " Also compare `docs/H99_HANDOVER.review.v2.md`."
        + section[span[1] :]
    )
    assert _named_records_are_illustration_only(nonexistent_inside)
    assert not _illustration_records_exist(nonexistent_inside)


def test_session_continuity_illustration_names_existing_records() -> None:
    """Require illustration records to exist and startup target to bootstrap."""
    section = _session_continuity_section()
    span = _illustration_span(section)
    assert span is not None, (
        "the gateway must label its named record as an illustration"
    )
    named = _illustration_records(section)
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
    assert not _carries_bootstrap_section(
        "# Session handover\n\nThis record does not carry "
        "## Bootstrap — run this first and must defer.\n"
    )
    assert not _carries_bootstrap_section(
        "# Session handover\n\n```markdown\n"
        "## Bootstrap — run this first\n- not executable here\n```\n"
    )
    assert not _carries_bootstrap_section(
        "# Session handover\n\n```markdown\n```not a close\n"
        "## Bootstrap — run this first\n- still fenced\n```\n"
    )
    assert not _carries_bootstrap_section(
        "# Session handover\n\n~~~markdown\n~~~not a close\n"
        "## Bootstrap — run this first\n- still fenced\n~~~\n"
    )
    assert not _carries_bootstrap_section(
        "# Session handover\n\n## Bootstrap — run this first\n\n## Next section\n"
    )
    assert not _carries_bootstrap_section(
        "# Handover\n<!--\n## Bootstrap — run this first\n- hidden\n-->\n"
    )
    assert not _carries_bootstrap_section(
        "# Handover\n<pre>\n## Bootstrap — run this first\n- hidden\n</pre>\n"
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
    assert "worktree-only (untracked or ignored): docs/H02_DELIVERY_HANDOVER.md" in (
        untracked.stderr
    )

    _git(repo, "add", candidate.relative_to(repo).as_posix())
    staged = _run_resolver(repo)
    assert staged.returncode == 2
    assert "staged addition: docs/H02_DELIVERY_HANDOVER.md" in staged.stderr


def test_handover_resolver_rejects_rename_and_intent_to_add(tmp_path: Path) -> None:
    """Index paths absent from HEAD must block, regardless of staging mechanism."""
    repo = tmp_path / "repo"
    docs = repo / "docs"
    docs.mkdir(parents=True)
    _git(repo, "init")
    _git(repo, "config", "user.name", "Resolver Test")
    _git(repo, "config", "user.email", "resolver@example.invalid")

    baseline = docs / "SESSION_HANDOVER_2026-01-01.md"
    baseline.write_text("committed\n", encoding="utf-8")
    _git(repo, "add", baseline.relative_to(repo).as_posix())
    _commit(repo, "docs: add baseline", "2026-01-01T00:00:00+00:00")

    renamed = docs / "H03_DELIVERY_RECORD.md"
    _git(
        repo,
        "mv",
        baseline.relative_to(repo).as_posix(),
        renamed.relative_to(repo).as_posix(),
    )
    rename_result = _run_resolver(repo)
    assert rename_result.returncode == 2
    assert "staged addition: docs/H03_DELIVERY_RECORD.md" in rename_result.stderr

    _git(
        repo,
        "mv",
        renamed.relative_to(repo).as_posix(),
        baseline.relative_to(repo).as_posix(),
    )
    nonmatching = docs / "not_a_handover.md"
    _git(
        repo,
        "mv",
        baseline.relative_to(repo).as_posix(),
        nonmatching.relative_to(repo).as_posix(),
    )
    nonmatching_result = _run_resolver(repo)
    assert nonmatching_result.returncode == 2
    assert "staged deletion: docs/SESSION_HANDOVER_2026-01-01.md" in (
        nonmatching_result.stderr
    )
    _git(
        repo,
        "mv",
        nonmatching.relative_to(repo).as_posix(),
        baseline.relative_to(repo).as_posix(),
    )
    intent = docs / "H04_HANDOVER.md"
    intent.write_text("intent to add\n", encoding="utf-8")
    _git(repo, "add", "--intent-to-add", intent.relative_to(repo).as_posix())
    intent_result = _run_resolver(repo)
    assert intent_result.returncode == 2
    assert "staged addition: docs/H04_HANDOVER.md" in intent_result.stderr


def test_handover_resolver_rejects_deletions_and_ignored_records(
    tmp_path: Path,
) -> None:
    """HEAD/index/worktree divergence must fail in both directions."""
    repo = tmp_path / "repo"
    docs = repo / "docs"
    docs.mkdir(parents=True)
    _git(repo, "init")
    _git(repo, "config", "user.name", "Resolver Test")
    _git(repo, "config", "user.email", "resolver@example.invalid")
    baseline = docs / "SESSION_HANDOVER_2026-01-01.md"
    baseline.write_text("committed\n", encoding="utf-8")
    _git(repo, "add", baseline.relative_to(repo).as_posix())
    _commit(repo, "docs: add baseline", "2026-01-01T00:00:00+00:00")

    _git(repo, "rm", baseline.relative_to(repo).as_posix())
    staged_delete = _run_resolver(repo)
    assert staged_delete.returncode == 2
    assert "staged deletion: docs/SESSION_HANDOVER_2026-01-01.md" in (
        staged_delete.stderr
    )
    _git(
        repo,
        "restore",
        "--staged",
        "--worktree",
        baseline.relative_to(repo).as_posix(),
    )

    baseline.unlink()
    unstaged_delete = _run_resolver(repo)
    assert unstaged_delete.returncode == 2
    assert "worktree deletion: docs/SESSION_HANDOVER_2026-01-01.md" in (
        unstaged_delete.stderr
    )
    baseline.write_text("committed\n", encoding="utf-8")

    ignored = docs / "H09_DELIVERY_IGNORED.md"
    (repo / ".gitignore").write_text(
        f"/{ignored.relative_to(repo)}\n", encoding="utf-8"
    )
    ignored.write_text("ignored\n", encoding="utf-8")
    assert ignored.relative_to(repo).as_posix() not in _git(
        repo, "status", "--porcelain", "--untracked-files=all"
    )
    ignored_result = _run_resolver(repo)
    assert ignored_result.returncode == 2
    assert "worktree-only (untracked or ignored): docs/H09_DELIVERY_IGNORED.md" in (
        ignored_result.stderr
    )


def test_handover_resolver_rejects_delete_and_readd_history(tmp_path: Path) -> None:
    """Multiple add events cannot be collapsed into one asserted introduction."""
    repo = tmp_path / "repo"
    docs = repo / "docs"
    docs.mkdir(parents=True)
    _git(repo, "init")
    _git(repo, "config", "user.name", "Resolver Test")
    _git(repo, "config", "user.email", "resolver@example.invalid")

    record = docs / "SESSION_HANDOVER_2026-01-01.md"
    record.write_text("first\n", encoding="utf-8")
    _git(repo, "add", record.relative_to(repo).as_posix())
    _commit(repo, "docs: add record", "2026-01-01T00:00:00+00:00")
    _git(repo, "rm", record.relative_to(repo).as_posix())
    _commit(repo, "docs: remove record", "2026-01-02T00:00:00+00:00")
    record.parent.mkdir()
    record.write_text("re-added\n", encoding="utf-8")
    _git(repo, "add", record.relative_to(repo).as_posix())
    _commit(repo, "docs: re-add record", "2026-01-03T00:00:00+00:00")

    result = _run_resolver(repo)
    assert result.returncode == 2
    assert "multiple handover-family entries found" in result.stderr


def test_handover_resolver_dates_entry_into_supported_namespace(tmp_path: Path) -> None:
    """Date namespace entry, preserve renames, and treat copies as new records."""
    outside_repo = tmp_path / "outside"
    outside_docs = outside_repo / "docs"
    outside_docs.mkdir(parents=True)
    _git(outside_repo, "init")
    _git(outside_repo, "config", "user.name", "Resolver Test")
    _git(outside_repo, "config", "user.email", "resolver@example.invalid")
    note = outside_docs / "ordinary\x1enote.md"
    note.write_text("same lineage\n", encoding="utf-8")
    _git(outside_repo, "add", note.relative_to(outside_repo).as_posix())
    _commit(outside_repo, "docs: add ordinary note", "2026-01-01T00:00:00+00:00")
    entered = outside_docs / "H01_HANDOVER renamed.md"
    _git(
        outside_repo,
        "mv",
        note.relative_to(outside_repo).as_posix(),
        entered.relative_to(outside_repo).as_posix(),
    )
    _commit(outside_repo, "docs: enter handover family", "2026-01-02T00:00:00+00:00")
    outside_result = _run_resolver(outside_repo)
    assert outside_result.returncode == 0, outside_result.stderr
    assert outside_result.stdout.split("\t", 1)[0] == "1767312000"

    inside_repo = tmp_path / "inside"
    inside_docs = inside_repo / "docs"
    inside_docs.mkdir(parents=True)
    _git(inside_repo, "init")
    _git(inside_repo, "config", "user.name", "Resolver Test")
    _git(inside_repo, "config", "user.email", "resolver@example.invalid")
    original = inside_docs / "SESSION_HANDOVER_2026-01-01.md"
    original.write_text("same lineage\n", encoding="utf-8")
    _git(inside_repo, "add", original.relative_to(inside_repo).as_posix())
    _commit(inside_repo, "docs: add handover", "2026-01-01T00:00:00+00:00")
    renamed = inside_docs / "H01_HANDOVER renamed.md"
    _git(
        inside_repo,
        "mv",
        original.relative_to(inside_repo).as_posix(),
        renamed.relative_to(inside_repo).as_posix(),
    )
    _commit(inside_repo, "docs: rename handover", "2026-01-02T00:00:00+00:00")
    inside_result = _run_resolver(inside_repo)
    assert inside_result.returncode == 0, inside_result.stderr
    assert inside_result.stdout.split("\t", 1)[0] == "1767225600"

    copy_repo = tmp_path / "copy"
    copy_docs = copy_repo / "docs"
    copy_docs.mkdir(parents=True)
    _git(copy_repo, "init")
    _git(copy_repo, "config", "user.name", "Resolver Test")
    _git(copy_repo, "config", "user.email", "resolver@example.invalid")
    source = copy_docs / "H01_HANDOVER.md"
    source.write_text("copied lineage\n", encoding="utf-8")
    _git(copy_repo, "add", source.relative_to(copy_repo).as_posix())
    _commit(copy_repo, "docs: add source handover", "2026-01-01T00:00:00+00:00")
    copied = copy_docs / "H02_HANDOVER copied.md"
    copied.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    _git(copy_repo, "add", copied.relative_to(copy_repo).as_posix())
    _commit(copy_repo, "docs: add copied successor", "2026-01-02T00:00:00+00:00")
    copy_result = _run_resolver(copy_repo)
    assert copy_result.returncode == 0, copy_result.stderr
    assert copy_result.stdout.split("\t", 1)[0] == "1767312000"



def test_handover_resolver_rejects_control_character_filenames(
    tmp_path: Path,
) -> None:
    """Control-bearing near-family names must fail before ambiguous display."""
    repo = tmp_path / "repo"
    docs = repo / "docs"
    docs.mkdir(parents=True)
    _git(repo, "init")
    _git(repo, "config", "user.name", "Resolver Test")
    _git(repo, "config", "user.email", "resolver@example.invalid")
    baseline = docs / "SESSION_HANDOVER_2026-01-01.md"
    baseline.write_text("baseline\n", encoding="utf-8")
    hostile = [
        docs / "H01_HANDOVER tab\tfield.md",
        docs / "H02_HANDOVER line\nbreak.md",
        docs / "H03_HANDOVER record\x1eseparator.md",
        docs / "H04_HANDOVER unicode\u0085control.md",
        docs / "H05_HANDOVER zero\u200bwidth.md",
        docs / "H06_HANDOVER_*.md",
        docs / "H07_HANDOVER_[draft].md",
    ]
    for path in hostile:
        path.write_text("hostile\n", encoding="utf-8")
    _git(repo, "add", "docs")
    _commit(repo, "docs: add control names", "2026-01-01T00:00:00+00:00")

    result = _run_resolver(repo)
    assert result.returncode == 2
    assert "unsupported display characters" in result.stderr
    assert "\\t" in result.stderr
    assert "\\n" in result.stderr
    assert "\\x1e" in result.stderr
    assert result.stdout == ""


def test_handover_resolver_rejects_tied_newest_introductions(tmp_path: Path) -> None:
    """Same-commit predecessor and successor additions cannot gain lexical authority."""
    repo = tmp_path / "repo"
    docs = repo / "docs"
    docs.mkdir(parents=True)
    _git(repo, "init")
    _git(repo, "config", "user.name", "Resolver Test")
    _git(repo, "config", "user.email", "resolver@example.invalid")

    baseline = docs / "SESSION_HANDOVER_2026-01-01.md"
    baseline.write_text("baseline\n", encoding="utf-8")
    _git(repo, "add", baseline.relative_to(repo).as_posix())
    _commit(repo, "docs: add baseline", "2026-01-01T00:00:00+00:00")

    predecessor = docs / "H05_HANDOVER.md"
    successor = docs / "H06_HANDOVER.md"
    predecessor.write_text("predecessor\n", encoding="utf-8")
    successor.write_text("successor\n", encoding="utf-8")
    _git(repo, "add", "docs/H05_HANDOVER.md", "docs/H06_HANDOVER.md")
    _commit(repo, "docs: add tied records", "2026-01-02T00:00:00+00:00")

    result = _run_resolver(repo)
    assert result.returncode == 2
    assert "newest introduction timestamp" in result.stderr
    assert "docs/H05_HANDOVER.md, docs/H06_HANDOVER.md" in result.stderr


def test_handover_resolver_rejects_backdated_descendant(tmp_path: Path) -> None:
    """Topology must defeat a descendant introduction with an earlier epoch."""
    repo = tmp_path / "repo"
    docs = repo / "docs"
    docs.mkdir(parents=True)
    _git(repo, "init")
    _git(repo, "config", "user.name", "Resolver Test")
    _git(repo, "config", "user.email", "resolver@example.invalid")

    predecessor = docs / "SESSION_HANDOVER_2026-01-01.md"
    predecessor.write_text("predecessor\n", encoding="utf-8")
    _git(repo, "add", predecessor.relative_to(repo).as_posix())
    _commit(repo, "docs: add predecessor", "2026-01-02T00:00:00+00:00")

    descendant = docs / "H01_HANDOVER.md"
    descendant.write_text("descendant\n", encoding="utf-8")
    _git(repo, "add", descendant.relative_to(repo).as_posix())
    _commit(repo, "docs: add backdated descendant", "2026-01-01T00:00:00+00:00")

    result = _run_resolver(repo)
    assert result.returncode == 2
    assert "descendant introduction docs/H01_HANDOVER.md is backdated" in result.stderr


def test_handover_resolver_rejects_parallel_introductions(tmp_path: Path) -> None:
    """Parallel handover introductions cannot obtain authority from timestamps."""
    repo = tmp_path / "repo"
    docs = repo / "docs"
    docs.mkdir(parents=True)
    _git(repo, "init")
    _git(repo, "config", "user.name", "Resolver Test")
    _git(repo, "config", "user.email", "resolver@example.invalid")
    (repo / "README.md").write_text("root\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _commit(repo, "docs: add root", "2026-01-01T00:00:00+00:00")
    root_sha = _git(repo, "rev-parse", "HEAD").strip()

    _git(repo, "checkout", "-b", "left")
    left = docs / "SESSION_HANDOVER_left.md"
    left.write_text("left\n", encoding="utf-8")
    _git(repo, "add", left.relative_to(repo).as_posix())
    _commit(repo, "docs: add left", "2026-01-02T00:00:00+00:00")

    _git(repo, "checkout", "-b", "right", root_sha)
    right = docs / "H01_HANDOVER.md"
    right.parent.mkdir()
    right.write_text("right\n", encoding="utf-8")
    _git(repo, "add", right.relative_to(repo).as_posix())
    _commit(repo, "docs: add right", "2026-01-03T00:00:00+00:00")

    _git(repo, "checkout", "left")
    merge_env = {
        **os.environ,
        "GIT_AUTHOR_DATE": "2026-01-04T00:00:00+00:00",
        "GIT_COMMITTER_DATE": "2026-01-04T00:00:00+00:00",
    }
    _git(
        repo,
        "merge",
        "--no-ff",
        "right",
        "-m",
        "docs: merge histories",
        env=merge_env,
    )

    result = _run_resolver(repo)
    assert result.returncode == 2
    assert "introduction commits are incomparable" in result.stderr


def test_handover_resolver_rejects_shallow_history(tmp_path: Path) -> None:
    """Shallow history must stop resolution before record interpretation."""
    source = tmp_path / "source"
    docs = source / "docs"
    docs.mkdir(parents=True)
    _git(source, "init")
    _git(source, "config", "user.name", "Resolver Test")
    _git(source, "config", "user.email", "resolver@example.invalid")
    record = docs / "SESSION_HANDOVER_2026-01-01.md"
    record.write_text("baseline\n", encoding="utf-8")
    _git(source, "add", record.relative_to(source).as_posix())
    _commit(source, "docs: add baseline", "2026-01-01T00:00:00+00:00")

    shallow = tmp_path / "shallow"
    _git(tmp_path, "clone", "--depth", "1", source.as_uri(), shallow.as_posix())
    assert _git(shallow, "rev-parse", "--is-shallow-repository").strip() == "true"
    result = _run_resolver(shallow)
    assert result.returncode == 2
    assert "repository history is shallow" in result.stderr
