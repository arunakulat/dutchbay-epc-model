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


RESOLVER_SCRIPT = REPO_ROOT / "scripts/list_session_handover_records.py"


def _session_continuity_section() -> str:
    """Return the body of the AGENTS.md 'Session continuity' section."""
    guidance = _guidance()
    start = guidance.index("## Session continuity")
    end = guidance.index("\n## ", start + 1)
    return guidance[start:end]


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


def test_session_continuity_has_no_concrete_record_tokens() -> None:
    """Keep every concrete handover pointer out of the instruction gateway."""
    section = _session_continuity_section()

    assert "python scripts/list_session_handover_records.py" in section
    assert "first record" in section
    assert "SESSION_HANDOVER_" not in section
    assert re.search(r"H[0-9]+_(?:HANDOVER|DELIVERY_)", section) is None


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
        docs / "H*_HANDOVER.md",
        docs / "SESSION?_HANDOVER_masked.md",
        docs / "H\u0661_HANDOVER.md",
        docs / "H0\u200b1_HANDOVER.md",
        docs / "H0\udcff1_HANDOVER.md",
        docs / "SESSION\u200b_HANDOVER_hidden.md",
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
