"""Guard the canonical GWTF source and current branch-integration policy."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_RULESET = REPO_ROOT / "go_with_the_flow_rules_v3_0_clean.csv"
RETIRED_RULESET_NAME = "go_with_the_flow_rules_v3_0_merged_with_v14.csv"
RETIRED_INTEGRATION_BRANCH = "feature/add-finance-contracts-pydantic-v2-20251219"
RECRUIT_MODULES = (
    "docs/governance/recruit_01/01_capability_and_risk.md",
    "docs/governance/recruit_01/02_writer_lease_and_recovery.md",
    "docs/governance/recruit_01/03_independent_review_and_attestation.md",
    "docs/governance/recruit_01/04_staged_delegation_and_ingress.md",
)


def _rules_by_id() -> dict[str, dict[str, str]]:
    """Load the canonical ruleset keyed by its unique rule identifiers."""
    with CANONICAL_RULESET.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {row["rule_id"]: row for row in rows}


def test_bootstrap_uses_the_canonical_ruleset() -> None:
    """Keep executable bootstrap paths pinned to the tracked canonical CSV."""
    venv_script = (REPO_ROOT / "scripts" / "venv_up.sh").read_text(encoding="utf-8")
    environment_helper = (
        REPO_ROOT / "scripts" / "development_environment.sh"
    ).read_text(encoding="utf-8")
    bootstrap = (REPO_ROOT / "dutchbay_bootstrap.py").read_text(encoding="utf-8")
    bootstrap_helper = (REPO_ROOT / "dutchbay_bootstrap_rules.py").read_text(
        encoding="utf-8"
    )

    assert CANONICAL_RULESET.is_file()
    assert "development_environment.sh" in venv_script
    assert CANONICAL_RULESET.name in environment_helper
    assert CANONICAL_RULESET.name in bootstrap
    assert CANONICAL_RULESET.name in bootstrap_helper
    assert RETIRED_RULESET_NAME not in venv_script
    assert RETIRED_RULESET_NAME not in environment_helper
    assert RETIRED_RULESET_NAME not in bootstrap
    assert RETIRED_RULESET_NAME not in bootstrap_helper


def test_r25_uses_current_pr_and_worktree_flow() -> None:
    """Prevent R25 enforcement from reverting to a retired sprint branch."""
    r25 = _rules_by_id()["R25"]
    policy = " ".join((r25["title"], r25["description"], r25["enforcement"]))

    assert r25["status"] == "active"
    assert "origin/main" in policy
    assert "worktree" in policy.lower()
    assert "PR" in policy
    assert "CI" in policy
    assert RETIRED_INTEGRATION_BRANCH not in policy


def test_r21_uses_the_governed_python312_environment() -> None:
    """Keep the active developer workflow off the retired Python 3.11 venv."""

    r21 = _rules_by_id()["R21"]
    policy = " ".join((r21["title"], r21["description"], r21["enforcement"]))

    assert r21["status"] == "active"
    assert "Python 3.12" in policy
    assert "./setup_venv.sh" in policy
    assert "source .venv/bin/activate" in policy
    assert "source .venv311/bin/activate" not in policy
    assert "do not use .venv311" in policy


def test_r26_uses_the_governed_ingestion_toolchain() -> None:
    """Pin PDF ingestion to the reconstructable Python 3.12 dependency lock."""

    r26 = _rules_by_id()["R26"]
    policy = " ".join((r26["title"], r26["description"], r26["enforcement"]))

    assert r26["status"] == "active"
    assert "Python 3.12" in policy
    assert "[ingestion]" in policy
    assert ".venv/bin/python -m markitdown" in policy
    assert "pdfplumber/PyMuPDF" in policy


def test_thread_01_requires_the_project_and_persistent_venv() -> None:
    """Keep every new thread bound to the durable Codex project runtime."""

    thread_01 = _rules_by_id()["THREAD-01"]
    policy = " ".join(
        (thread_01["title"], thread_01["description"], thread_01["enforcement"])
    )

    assert thread_01["status"] == "active"
    assert "regardless of subject" in policy
    assert "DutchBay_EPC_Model" in policy
    assert "/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python" in policy
    assert "DUTCHBAY_VENV" in policy
    assert "PYTHONPATH" in policy
    assert "Python 3.12" in policy
    assert "/Users/aruna/Downloads/dutchbay-epc-model" in policy
    assert "portable fallback" in policy
    assert "unconfigured developer host" in policy
    assert "ephemeral CI/container host" in policy
    for prohibited in ("temporary venv", ".venv311", "bare/system Python"):
        assert prohibited in policy


def test_env_01_binds_one_shared_environment_to_each_active_worktree() -> None:
    """Keep repository identity separate from persistent environment identity."""

    env_01 = _rules_by_id()["ENV-01"]
    policy = " ".join((env_01["title"], env_01["description"], env_01["enforcement"]))

    assert env_01["status"] == "active"
    for required in (
        "DUTCHBAY_VENV",
        "PYTHONPATH",
        "git rev-parse --show-toplevel",
        "git worktree list",
        "verify_shared_venv_worktrees.py",
        "two distinct clean worktrees",
        "no worktree-local .venv",
        "PERSIST-01",
    ):
        assert required in policy


def test_test_01_requires_an_independent_oracle() -> None:
    """Keep the independent-oracle clause in TEST-01 and its AGENTS.md echo together."""

    test_01 = _rules_by_id()["TEST-01"]
    policy = " ".join(
        (test_01["title"], test_01["description"], test_01["enforcement"])
    )

    assert test_01["status"] == "active"
    for required in (
        "responsiveness guard",
        "did not originate in the same change",
        "property/invariant",
        "tests/finance/test_canon_vector_is_computed.py",
    ):
        assert required in policy

    agents = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "independent-oracle clause" in agents
    assert "responsiveness guard" in agents


def test_verify_01_requires_receipts_for_claimed_checks() -> None:
    """Keep VERIFY-01 bound to its template, workflow, checker and yield clause."""

    verify_01 = _rules_by_id()["VERIFY-01"]
    policy = " ".join(
        (verify_01["title"], verify_01["description"], verify_01["enforcement"])
    )

    assert verify_01["status"] == "active"
    assert verify_01["category"] == "Verification"
    for required in (
        "not run",
        "required-not-run",
        ".github/pull_request_template.md",
        "scripts/ci/check_pr_receipts.py",
        ".github/workflows/pr-receipts.yml",
        "TEST-05",
        "negative control",
        "the SPECIFIC rule wins",
    ):
        assert required in policy


def test_intake_01_binds_tracker_first_work_to_required_pr_check() -> None:
    """Keep the owner-requested sequencing rule and executable echo aligned."""
    intake_01 = _rules_by_id()["INTAKE-01"]
    policy = " ".join(
        (intake_01["title"], intake_01["description"], intake_01["enforcement"])
    )
    assert intake_01["status"] == "active"
    for required in (
        "origin/main",
        "#1353",
        "every open PR",
        "before editing",
        "actionable overlapping PR",
        "blocked",
        "scripts/ci/check_pr_intake.py",
        "Verification receipts (VERIFY-01)",
    ):
        assert required in policy
    agents = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    steward = (REPO_ROOT / ".claude/skills/steward/SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "INTAKE-01" in agents
    assert "INTAKE-01" in steward


def test_recruit_01_routes_all_relevant_tasks_to_canonical_modules() -> None:
    """Keep recruitment global, risk-scaled, and backed by tracked modules."""
    recruit_01 = _rules_by_id()["RECRUIT-01"]
    policy = " ".join(
        (
            recruit_01["title"],
            recruit_01["description"],
            recruit_01["enforcement"],
        )
    )

    assert recruit_01["status"] == "active"
    assert recruit_01["category"] == "Recruitment & Review"
    for required in (
        "every relevant task hereafter",
        "regardless of subject",
        "not limited to D0-D3",
        "at most one active writer lease",
        "load-bearing governance",
        "NO_EVIDENCE",
    ):
        assert required in policy

    required_module_controls = {
        RECRUIT_MODULES[0]: (
            "Semantic risk classes",
            "Load-bearing documentation",
            "R3_CONSEQUENTIAL",
        ),
        RECRUIT_MODULES[1]: (
            "at most one participant holds",
            "DEAD_WORKER_TAKEOVER",
            "PERSISTENCE_CHECKPOINT",
        ),
        RECRUIT_MODULES[2]: (
            "subject manifest",
            "independent positive/negative oracle",
            "without SHA recursion",
            "squash merge",
            "BLOB-HASH IDENTITY",
            "BIDIRECTIONAL IMPORT ISOLATION",
            "complete diff between reviewed and updated head",
            "disposition LAPSES",
        ),
        RECRUIT_MODULES[3]: (
            "not limited to D0–D3",
            "Capacity admission",
            "NO_EVIDENCE",
            "Staged waves",
        ),
    }
    for relative_path, required_controls in required_module_controls.items():
        assert relative_path in policy
        module_path = REPO_ROOT / relative_path
        assert module_path.is_file()
        module = " ".join(module_path.read_text(encoding="utf-8").split()).casefold()
        for control in required_controls:
            assert control.casefold() in module


def test_active_r25_scripts_do_not_hardcode_a_retired_branch() -> None:
    """Keep operational R25 scripts branch-agnostic."""
    for relative_path in (
        "scripts/gwtf-preflight.sh",
        "scripts/gwtf-daily-audit.sh",
        "scripts/README.md",
    ):
        content = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
        assert RETIRED_INTEGRATION_BRANCH not in content


@pytest.mark.parametrize(
    ("module_index", "removed_control"),
    [
        (0, "R3_CONSEQUENTIAL"),
        (1, "DEAD_WORKER_TAKEOVER"),
        (2, "BIDIRECTIONAL IMPORT ISOLATION"),
        (3, "NO_EVIDENCE"),
    ],
)
def test_recruit_policy_guard_rejects_removed_controls(
    monkeypatch: pytest.MonkeyPatch, module_index: int, removed_control: str
) -> None:
    """Observe the policy guard rejecting control loss without changing source files."""
    target = REPO_ROOT / RECRUIT_MODULES[module_index]
    original_read = Path.read_text

    def altered_read(
        path: Path, encoding: str | None = None, errors: str | None = None
    ) -> str:
        text = original_read(path, encoding=encoding, errors=errors)
        return (
            text.replace(removed_control, "REMOVED_CONTROL") if path == target else text
        )

    monkeypatch.setattr(Path, "read_text", altered_read)
    with pytest.raises(AssertionError):
        test_recruit_01_routes_all_relevant_tasks_to_canonical_modules()


R18_REQUIRED_CONTROLS = (
    "Conventional Commits",
    "commitlint config-conventional",
    "type(scope): summary",
    "'deploy' is NOT sanctioned",
    "REFACTOR-03",
    "RECEIPT under VERIFY-01",
    "NO frozen conformance figure",
    "test_commit_message_conformance.py",
    # Assert the ENUMERATION, not each type: substring presence bound nothing, because
    # `ci` matches inside "explicit" and `test`/`chore` appear elsewhere in the cell, so
    # removing a type from the rule left the guard green. Set-equality binding, which also
    # catches ADDITION, lives in tests/lint/test_commit_message_conformance.py.
    "feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert",
)
R21_REQUIRED_CONTROLS = (
    "narrowest meaningful check before each commit",
    "full suite before pushing",
    "AGENTS.md",
)


def _policy(rule_id: str) -> str:
    """Join a rule's human-readable cells the way the other guards in this file do."""
    rule = _rules_by_id()[rule_id]
    return " ".join((rule["title"], rule["description"], rule["enforcement"]))


def test_r18_states_the_sanctioned_commit_convention() -> None:
    """Pin R18 to the standard type set and to carrying no frozen statistic."""
    policy = _policy("R18")

    assert _rules_by_id()["R18"]["status"] == "active"
    assert _rules_by_id()["R18"]["category"] == "Git Workflow"
    for control in R18_REQUIRED_CONTROLS:
        assert control in policy
    # The retired example citation must not creep back. The historical text was
    # "...cleanup commit (fb3b1f7) as example." - match the SHA itself, because an
    # earlier draft of this guard banned "fb3b1f7 as example", a substring the real
    # citation never contained, and so could never fire.
    assert "fb3b1f7" not in policy


def test_r21_scales_verification_to_the_commit_boundary() -> None:
    """Pin the graduated cadence and the absence of a frozen test count."""
    policy = _policy("R21")

    assert _rules_by_id()["R21"]["status"] == "active"
    for control in R21_REQUIRED_CONTROLS:
        assert control in policy
    assert "run 'pytest' before committing or pushing" not in policy
    # The figure previously drafted here was lifted from a stale workflow comment.
    assert "3,600" not in policy


def test_r21_agents_md_echo_is_present() -> None:
    """R21 cites AGENTS.md as authority, so bind them the way TEST-01's guard does."""
    agents = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")

    assert "Run the narrowest meaningful checks while iterating" in agents


def test_refactor_03_does_not_claim_a_commit_message_hook() -> None:
    """No commit-message hook exists; REFACTOR-03 must not contradict R18 by claiming one."""
    policy = _policy("REFACTOR-03")

    assert "Git hooks: NONE" in policy
    assert "pre-commit check warns if" not in policy


@pytest.mark.parametrize(
    ("rule_id", "removed_control", "guard"),
    [
        *(
            ("R18", control, test_r18_states_the_sanctioned_commit_convention)
            for control in R18_REQUIRED_CONTROLS
        ),
        *(
            ("R21", control, test_r21_scales_verification_to_the_commit_boundary)
            for control in R21_REQUIRED_CONTROLS
        ),
        (
            "REFACTOR-03",
            "Git hooks: NONE",
            test_refactor_03_does_not_claim_a_commit_message_hook,
        ),
    ],
)
def test_commit_convention_guards_reject_control_loss(
    monkeypatch: pytest.MonkeyPatch,
    rule_id: str,
    removed_control: str,
    guard: object,
) -> None:
    """Observe every asserted control being load-bearing, one at a time."""
    mutated = {key: dict(row) for key, row in _rules_by_id().items()}
    for cell in ("title", "description", "enforcement"):
        mutated[rule_id][cell] = mutated[rule_id][cell].replace(
            removed_control, "REMOVED_CONTROL"
        )

    monkeypatch.setitem(globals(), "_rules_by_id", lambda: mutated)
    with pytest.raises(AssertionError):
        guard()  # type: ignore[operator]


@pytest.mark.parametrize(
    ("rule_id", "injected", "guard"),
    [
        ("R18", " fb3b1f7 ", test_r18_states_the_sanctioned_commit_convention),
        (
            "R21",
            " run 'pytest' before committing or pushing ",
            test_r21_scales_verification_to_the_commit_boundary,
        ),
        (
            "REFACTOR-03",
            " pre-commit check warns if ",
            test_refactor_03_does_not_claim_a_commit_message_hook,
        ),
    ],
)
def test_commit_convention_guards_reject_retired_text_returning(
    monkeypatch: pytest.MonkeyPatch,
    rule_id: str,
    injected: str,
    guard: object,
) -> None:
    """The inverse assertions need their own control: re-inject the retired text."""
    mutated = {key: dict(row) for key, row in _rules_by_id().items()}
    mutated[rule_id]["enforcement"] += injected

    monkeypatch.setitem(globals(), "_rules_by_id", lambda: mutated)
    with pytest.raises(AssertionError):
        guard()  # type: ignore[operator]


SECDEP_01_REQUIRED_CONTROLS = (
    "dated claim about the world",
    "--ignore-vuln",
    "PIP_AUDIT_IGNORES",
    "exactly one literal :=",
    "computed variable names",
    "option abbreviations",
    "direct recipe flags",
    "make -n security",
    "make -n audit",
    "security-only recipe suppression",
    "pip-audit's own parser",
    "ambiguous prefixes",
    "every emitted command",
    "each command on its own",
    "three audit passes",
    "complete command sequence",
    ".ONESHELL alias interception",
    "discards a governed exit status",
    ".IGNORE",
    "MAKEFLAGS",
    "GNUMAKEFLAGS",
    "form-independently",
    "dash-prefixed",
    "runtime sentinels",
    "sentinels forced to fail",
    "no-fix-published",
    "release that would lift it",
    "REMOVED rather than re-justified",
    "is not evidence",
    ".github/dependabot.yml",
    "constraints.txt",
    "SHAPE of the declaration",
    "caller-supplied make -i",
    "command-line variable override",
    "CI surface",
    "two committed workflows",
    "authoritative gate receipts",
    "clean execution context",
    "workflow environment",
    "job environment and container",
    "runs-on pinned to ubuntu-latest",
    "needs is rejected",
    "reports skipped rather than failed",
    "step environment, shell and working directory",
    "Arbitrary local Make callers",
    "committed declarative keys",
    "runner-host state",
    "runtime environment files",
    "environment-selected vulnerability service",
    "asserted clean against the committed Makefile",
    "No expectation assumes the allowlist is empty",
    "packaging primitives",
    "tests/lint/test_pip_audit_allowlist.py",
    "RELEASING.md",
    "hostile controls",
    "before make lock",
    "partial delivery of P-1",
)

SECDEP_01_RELEASING_CONTROLS = (
    "**Before regenerating, re-check every suppressed advisory",
    "PIP_AUDIT_IGNORES",
    "check the cap against the index",
    "dependency or constraint",
    "input is updated to admit",
    "before `make lock`",
    "never regenerate first",
    "tests/lint/test_pip_audit_allowlist.py",
    "make audit",
)


def _assert_secdep_01_release_order(releasing: str) -> None:
    """Bind the substantive cap check and require it before lock regeneration."""
    section = releasing.split("## 2) Refresh the dependency lock", 1)[1].split(
        "## 3) Verify the wheel builds", 1
    )[0]
    section = " ".join(section.split())
    for control in SECDEP_01_RELEASING_CONTROLS:
        assert control in section
    assert section.index("**Before regenerating") < section.index("make lock")


def test_secdep_01_binds_a_suppressed_advisory_to_its_lift_condition() -> None:
    """Pin SECDEP-01 to its fence, workflow boundary, scope and stated limits."""
    secdep_01 = _rules_by_id()["SECDEP-01"]
    policy = _policy("SECDEP-01")

    assert secdep_01["status"] == "active"
    assert secdep_01["category"] == "Dependency Security"
    for control in SECDEP_01_REQUIRED_CONTROLS:
        assert control in policy

    # The rule names two places a human reads it and one that enforces it. A rule citing
    # an enforcement point that does not carry it is the P-10 shape, so bind all three.
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    releasing = (REPO_ROOT / "RELEASING.md").read_text(encoding="utf-8")

    assert "SECDEP-01" in makefile
    assert "ignore-vuln:" in makefile
    _assert_secdep_01_release_order(releasing)
    assert (REPO_ROOT / "tests/lint/test_pip_audit_allowlist.py").is_file()
    assert (REPO_ROOT / "tests/lint/test_security_gate_coverage.py").is_file()


@pytest.mark.parametrize("removed_control", SECDEP_01_REQUIRED_CONTROLS)
def test_secdep_01_guard_rejects_control_loss(
    monkeypatch: pytest.MonkeyPatch, removed_control: str
) -> None:
    """Observe every asserted SECDEP-01 control being load-bearing, one at a time."""
    mutated = {key: dict(row) for key, row in _rules_by_id().items()}
    for cell in ("title", "description", "enforcement"):
        mutated["SECDEP-01"][cell] = mutated["SECDEP-01"][cell].replace(
            removed_control, "REMOVED_CONTROL"
        )

    monkeypatch.setitem(globals(), "_rules_by_id", lambda: mutated)
    with pytest.raises(AssertionError):
        test_secdep_01_binds_a_suppressed_advisory_to_its_lift_condition()


@pytest.mark.parametrize("removed_control", SECDEP_01_RELEASING_CONTROLS)
def test_secdep_01_release_guard_rejects_control_loss(
    removed_control: str,
) -> None:
    """A label-only release note cannot satisfy the cross-surface binding."""
    releasing = (REPO_ROOT / "RELEASING.md").read_text(encoding="utf-8")
    mutated = releasing.replace(removed_control, "REMOVED_RELEASE_CONTROL", 1)
    with pytest.raises(AssertionError):
        _assert_secdep_01_release_order(mutated)


def test_secdep_01_release_guard_rejects_lock_before_recheck() -> None:
    """The cap/index decision must precede, not follow, lock regeneration."""
    releasing = (REPO_ROOT / "RELEASING.md").read_text(encoding="utf-8")
    heading = "## 2) Refresh the dependency lock"
    insertion = releasing.index(heading) + len(heading)
    reordered = releasing[:insertion] + "\nmake lock\n" + releasing[insertion:]
    with pytest.raises(AssertionError):
        _assert_secdep_01_release_order(reordered)


CLEANUP_01_REQUIRED_CONTROLS = (
    "INFORM TASKLIST & GITHUB ISSUES",
    "capability tracker #1353",
    "CLEAR, PRUNE & CLOSE WORKTREES",
    "synchronize the clean primary checkout, when no other session is using it",
    "git worktree remove",
    "git worktree prune",
    "DELETE MERGED BRANCHES",
    "git branch -D",
    "git push origin --delete",
    "CLEAN NON-PROTECTED VENVS",
    "HARD BOUNDARY - PROTECTED PERSISTENT VENV",
    "/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv",
    # Guard (a), owner decision 2026-11-07: cleanup closes only the merged PR's focused
    # issue, never tracker #1353 and never a pull request; an unmerged PR closes only on a
    # cited owner decision.
    "close only the focused GitHub issue named by number on the merged PR's own Work item: line or closing line",
    "only when its deliverable is complete",
    "A Work item: line that names a #1353 comment closes nothing",
    "cleanup never closes tracker #1353",
    "Cleanup never closes a pull request",
    "HARD BOUNDARY - NO PULL REQUEST CLOSURE",
    "cited owner decision",
    "posted as a comment on that pull request before it is closed",
    "proves its car commit is on origin/main",
    "OWNER DECISIONS:",
    "owner instruction to the Nov 6 agent session, 2026-11-06T02:22:07Z",
    "'clean and amend please', project thread, 2026-11-07T11:06:49Z",
    "'yes please to all', project thread, 2026-11-07T05:29:05Z",
    "decision card at 2026-11-07T05:33:39Z",
    # Guard (b), owner decision 2026-11-07: a branch is deleted only after its PR merged.
    "BRANCH DELETION GATE",
    "merged_at is set and the branch head equals that pull request's merged head",
    "head.ref must name the branch",
    "the remote ref, if it still exists, must equal the merged head",
    "skip the remote delete and record that it was auto-deleted",
    "the local ref, if it exists, must equal the merged head before any local delete",
    "no open pull request may have the branch as its base",
    "the train pull request's merged_at is set",
    "never deleted by cleanup",
)

# Wording that let post-merge cleanup close pull requests. It must not come back anywhere.
CLEANUP_01_RETIRED_PHRASES = (
    "(or each car PR and train issue for a train)",
    "(or each car pull request and the train issue for a train)",
    "Otherwise close each car's pull request with a pointer",
    "close completed focused GitHub issues",
)

# Every surface that restates CLEANUP-01 must carry both guards, not only the rule's name.
CLEANUP_01_SURFACES = (
    "AGENTS.md",
    "CLAUDE.md",
    ".claude/skills/steward/SKILL.md",
    "docs/governance/agent_session_routing.md",
    "docs/governance/recruit_01/02_writer_lease_and_recovery.md",
    "Rules to follow.md",
)
CLEANUP_01_SURFACE_CONTROLS = (
    "CLEANUP-01",
    "/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv",
    "focused issue",
    "never closes tracker #1353",
    "Cleanup never closes a pull request",
    "cited owner decision",
    "merged_at",
    "merged head",
)

# Surfaces that tell a session to synchronize the primary checkout must not do it under
# another session's feet (#1549 domain re-review, N-2).
CLEANUP_01_SYNC_SURFACES = (
    "AGENTS.md",
    "CLAUDE.md",
    ".claude/skills/steward/SKILL.md",
    "docs/governance/recruit_01/02_writer_lease_and_recovery.md",
    "Rules to follow.md",
)
CLEANUP_01_SYNC_CONTROL = "when no other session is using it"

STEWARD_SKILL = ".claude/skills/steward/SKILL.md"
# The steward's executable branch deletion gate, pinned line by line, and the train-car order.
CLEANUP_01_STEWARD_CONTROLS = (
    'test "$(gh api "repos/$repo/pulls/$PR" --jq \'.head.ref\')" = "$BRANCH"',
    'test -n "$(gh api "repos/$repo/pulls/$PR" --jq \'.merged_at // ""\')"',
    "want=$(gh api \"repos/$repo/pulls/$PR\" --jq '.head.sha')",
    'test "$(gh api "repos/$repo/pulls/$PR" --jq \'.state\')" = "closed"',
    'test "$(gh api "repos/$repo/pulls/$PR" --jq \'.head.sha\')" = "$CAR_HEAD"',
    'test -n "$(gh api "repos/$repo/pulls/$TRAIN_PR" --jq \'.merged_at // ""\')"',
    'test -z "$(gh api -X GET "repos/$repo/pulls" -f state=open -f base="$BRANCH" --jq \'.[].number\')"',
    'if [ -n "$remote_head" ]; then test "$remote_head" = "$want"; fi',
    'test "$(git rev-parse --verify "refs/heads/$BRANCH")" = "$want"',
    "first post a pointer comment naming its commit on `main`, then close that pull request",
)


def _flat(text: str) -> str:
    """Collapse line wrapping so a phrase is found wherever a surface wraps it."""
    return " ".join(text.split())


def _assert_cleanup_01_surface(relative_path: str, surface: str) -> None:
    """Check one restating surface for the rule name, the venv boundary and both guards."""
    flat = _flat(surface)
    for control in CLEANUP_01_SURFACE_CONTROLS:
        assert control in flat, f"{relative_path} lacks {control!r}"
    for phrase in CLEANUP_01_RETIRED_PHRASES:
        assert phrase not in flat, f"{relative_path} restores {phrase!r}"
    if relative_path in CLEANUP_01_SYNC_SURFACES:
        assert CLEANUP_01_SYNC_CONTROL in flat, f"{relative_path} lacks the sync guard"
    if relative_path == STEWARD_SKILL:
        for control in CLEANUP_01_STEWARD_CONTROLS:
            assert _flat(control) in flat, f"{relative_path} lacks {control!r}"


def test_cleanup_01_requires_post_merge_tracker_issue_and_workspace_retirement() -> (
    None
):
    """Pin CLEANUP-01 to post-merge issue/tracker updates, worktree/branch pruning, and protected-venv preservation."""
    cleanup_01 = _rules_by_id()["CLEANUP-01"]
    policy = _policy("CLEANUP-01")

    assert cleanup_01["status"] == "active"
    assert cleanup_01["category"] == "Git Workflow"
    for control in CLEANUP_01_REQUIRED_CONTROLS:
        assert control in policy
    for phrase in CLEANUP_01_RETIRED_PHRASES:
        assert phrase not in policy

    for relative_path in CLEANUP_01_SURFACES:
        surface = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
        _assert_cleanup_01_surface(relative_path, surface)


@pytest.mark.parametrize("removed_control", CLEANUP_01_REQUIRED_CONTROLS)
def test_cleanup_01_guard_rejects_control_loss(
    monkeypatch: pytest.MonkeyPatch, removed_control: str
) -> None:
    """Observe every asserted CLEANUP-01 control being load-bearing, one at a time."""
    mutated = {key: dict(row) for key, row in _rules_by_id().items()}
    for cell in ("title", "description", "enforcement"):
        mutated["CLEANUP-01"][cell] = mutated["CLEANUP-01"][cell].replace(
            removed_control, "REMOVED_CONTROL"
        )

    monkeypatch.setitem(globals(), "_rules_by_id", lambda: mutated)
    with pytest.raises(AssertionError):
        test_cleanup_01_requires_post_merge_tracker_issue_and_workspace_retirement()


@pytest.mark.parametrize("restored_phrase", CLEANUP_01_RETIRED_PHRASES)
def test_cleanup_01_guard_rejects_restored_pull_request_closure(
    monkeypatch: pytest.MonkeyPatch, restored_phrase: str
) -> None:
    """Restoring a retired PR-closing clause fails even with every control present."""
    mutated = {key: dict(row) for key, row in _rules_by_id().items()}
    mutated["CLEANUP-01"]["description"] += " " + restored_phrase

    monkeypatch.setitem(globals(), "_rules_by_id", lambda: mutated)
    with pytest.raises(AssertionError):
        test_cleanup_01_requires_post_merge_tracker_issue_and_workspace_retirement()


def _surface_mutation_cases() -> list[tuple[str, str]]:
    cases = [
        (path, control)
        for path in CLEANUP_01_SURFACES
        for control in CLEANUP_01_SURFACE_CONTROLS
    ]
    cases += [(STEWARD_SKILL, control) for control in CLEANUP_01_STEWARD_CONTROLS]
    cases += [(path, CLEANUP_01_SYNC_CONTROL) for path in CLEANUP_01_SYNC_SURFACES]
    return cases


@pytest.mark.parametrize(
    ("relative_path", "removed_control"), _surface_mutation_cases()
)
def test_cleanup_01_surface_guard_rejects_control_loss(
    relative_path: str, removed_control: str
) -> None:
    """Observe each surface control being load-bearing on each restating surface."""
    flat = _flat((REPO_ROOT / relative_path).read_text(encoding="utf-8"))
    _assert_cleanup_01_surface(relative_path, flat)
    mutated = flat.replace(_flat(removed_control), "REMOVED_CONTROL")
    assert mutated != flat
    with pytest.raises(AssertionError):
        _assert_cleanup_01_surface(relative_path, mutated)


@pytest.mark.parametrize("relative_path", CLEANUP_01_SURFACES)
@pytest.mark.parametrize("restored_phrase", CLEANUP_01_RETIRED_PHRASES)
def test_cleanup_01_surface_guard_rejects_restored_closure(
    relative_path: str, restored_phrase: str
) -> None:
    """A surface that brings back a retired PR-closing clause fails."""
    surface = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
    with pytest.raises(AssertionError):
        _assert_cleanup_01_surface(relative_path, surface + "\n" + restored_phrase)


# --- Executing the steward's branch deletion block against stubbed gh and git ---

_MERGED = "a" * 40
_MOVED = "b" * 40
_CAR = "c" * 40

_GH_STUB = """#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
assert args[0] == "api", args
key = " ".join(args[1:])
answers = json.loads(open(os.environ["STUB_GH"], encoding="utf-8").read())
if key not in answers:
    sys.stderr.write("unexpected gh call: " + key + "\\n")
    sys.exit(3)
if answers[key]:
    print(answers[key])
"""

_GIT_STUB = """#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
refs = json.loads(open(os.environ["STUB_GIT"], encoding="utf-8").read())
with open(os.environ["STUB_LOG"], "a", encoding="utf-8") as log:
    log.write(" ".join(args) + "\\n")
if args[:2] == ["config", "--get"]:
    pairs = {
        os.environ.get(f"GIT_CONFIG_KEY_{i}"): os.environ.get(f"GIT_CONFIG_VALUE_{i}")
        for i in range(int(os.environ.get("GIT_CONFIG_COUNT", "0")))
    }
    if args[2] not in pairs:
        sys.exit(1)
    print(pairs[args[2]])
elif args[:2] == ["check-ref-format", "--branch"]:
    print(args[2])
elif args[0] == "ls-remote":
    sha = refs.get("remote")
    if sha:
        print(sha + "\\t" + args[2])
elif args[0] == "show-ref":
    sys.exit(0 if refs.get("local") else 1)
elif args[0] == "rev-parse":
    print(refs["local"])
elif args[0] in ("push", "branch", "fetch"):
    pass
else:
    sys.exit(4)
"""


def _steward_branch_block() -> str:
    """Extract the bash block that holds the branch deletion gate from the steward skill."""
    text = (REPO_ROOT / STEWARD_SKILL).read_text(encoding="utf-8")
    anchor = text.index(
        "Delete a branch only when its pull request's `merged_at` is set"
    )
    start = text.index("```bash\n", anchor) + len("```bash\n")
    end = text.index("```", start)
    return "\n".join(line.strip() for line in text[start:end].splitlines())


def _gh_answers(
    *,
    head_ref: str = "feature",
    merged_at: str = "2026-11-07T00:00:00Z",
    head_sha: str = _MERGED,
    state: str = "closed",
    open_on_base: str = "",
    train_merged_at: str = "2026-11-07T00:00:00Z",
) -> dict[str, str]:
    pr = "repos/arunakulat/dutchbay-epc-model/pulls/7"
    return {
        f"{pr} --jq .head.ref": head_ref,
        f'{pr} --jq .merged_at // ""': merged_at,
        f"{pr} --jq .head.sha": head_sha,
        f"{pr} --jq .state": state,
        'repos/arunakulat/dutchbay-epc-model/pulls/9 --jq .merged_at // ""': train_merged_at,
        "-X GET repos/arunakulat/dutchbay-epc-model/pulls -f state=open -f base=feature "
        "--jq .[].number": open_on_base,
    }


def _run_branch_block(
    tmp_path: Path,
    gh: dict[str, str],
    refs: dict[str, str],
    *,
    car_head: str = "",
    train_pr: str = "",
    pr: str = "7",
) -> tuple[int, str, list[str]]:
    import json
    import os
    import shutil
    import subprocess
    import sys

    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash is not available")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in (("gh", _GH_STUB), ("git", _GIT_STUB)):
        stub = bin_dir / name
        stub.write_text(
            body.replace("/usr/bin/env python3", sys.executable, 1), encoding="utf-8"
        )
        stub.chmod(0o755)
    (tmp_path / "gh.json").write_text(json.dumps(gh), encoding="utf-8")
    (tmp_path / "git.json").write_text(json.dumps(refs), encoding="utf-8")
    log = tmp_path / "git.log"
    log.write_text("", encoding="utf-8")
    script = _steward_branch_block()
    env = {
        **os.environ,
        "PR": pr,
        "BRANCH": "feature",
        "CAR_HEAD": car_head,
        "TRAIN_PR": train_pr,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
        "STUB_GH": str(tmp_path / "gh.json"),
        "STUB_GIT": str(tmp_path / "git.json"),
        "STUB_LOG": str(log),
    }
    result = subprocess.run(
        [bash, "-c", script], env=env, capture_output=True, text=True, check=False
    )
    calls = log.read_text(encoding="utf-8").splitlines()
    # A stub refusing an unexpected call would fail the block for the wrong reason.
    assert "unexpected gh call" not in result.stderr, result.stderr
    assert "Traceback" not in result.stderr, result.stderr
    return result.returncode, result.stdout, calls


def _deletes(calls: list[str]) -> list[str]:
    return [c for c in calls if c.startswith(("push origin --delete", "branch -D"))]


@pytest.mark.parametrize(
    ("refs", "expected_deletes"),
    [
        ({}, []),
        ({"remote": _MERGED}, ["push origin --delete feature"]),
        ({"local": _MERGED}, ["branch -D feature"]),
        (
            {"remote": _MERGED, "local": _MERGED},
            ["push origin --delete feature", "branch -D feature"],
        ),
    ],
    ids=["auto-deleted", "remote-only", "local-only", "both"],
)
def test_cleanup_01_branch_gate_passes_a_merged_branch(
    tmp_path: Path, refs: dict[str, str], expected_deletes: list[str]
) -> None:
    """A merged PR passes whether or not GitHub already auto-deleted its remote branch."""
    code, out, calls = _run_branch_block(tmp_path, _gh_answers(), refs)
    assert code == 0
    assert out.startswith("CLEANUP-01 branch retirement: OK: #7")
    assert _deletes(calls) == expected_deletes


@pytest.mark.parametrize(
    ("gh", "refs"),
    [
        (_gh_answers(merged_at=""), {"remote": _MERGED}),
        (_gh_answers(head_ref="other"), {"remote": _MERGED}),
        (_gh_answers(), {"remote": _MOVED}),
        (_gh_answers(), {"local": _MOVED}),
        (_gh_answers(), {"remote": _MERGED, "local": _MOVED}),
        (_gh_answers(open_on_base="8"), {"remote": _MERGED}),
    ],
    ids=[
        "unmerged",
        "head-ref-mismatch",
        "remote-moved",
        "local-moved",
        "local-moved-remote-ok",
        "base-of-open-pr",
    ],
)
def test_cleanup_01_branch_gate_refuses_before_any_delete(
    tmp_path: Path, gh: dict[str, str], refs: dict[str, str]
) -> None:
    """Every failing check stops the block with no OK line and no delete."""
    code, out, calls = _run_branch_block(tmp_path, gh, refs)
    assert code != 0
    assert "OK:" not in out
    assert _deletes(calls) == []


def test_cleanup_01_branch_gate_passes_a_landed_train_car(tmp_path: Path) -> None:
    """A closed car whose train merged passes at the recorded car head."""
    gh = _gh_answers(merged_at="", head_sha=_CAR)
    code, out, calls = _run_branch_block(
        tmp_path, gh, {"remote": _CAR}, car_head=_CAR, train_pr="9"
    )
    assert code == 0
    assert out.startswith("CLEANUP-01 branch retirement: OK: #7")
    assert _deletes(calls) == ["push origin --delete feature"]


@pytest.mark.parametrize(
    ("gh", "refs"),
    [
        (_gh_answers(merged_at="", head_sha=_CAR, state="open"), {"remote": _CAR}),
        (
            _gh_answers(merged_at="", head_sha=_CAR, train_merged_at=""),
            {"remote": _CAR},
        ),
        (_gh_answers(merged_at="", head_sha=_MOVED), {"remote": _CAR}),
        (_gh_answers(merged_at="", head_sha=_CAR), {"remote": _MOVED}),
    ],
    ids=["car-pr-open", "train-unmerged", "car-pr-moved", "car-branch-moved"],
)
def test_cleanup_01_branch_gate_refuses_an_unproven_train_car(
    tmp_path: Path, gh: dict[str, str], refs: dict[str, str]
) -> None:
    """A car branch is never deleted unless its PR closed, the train merged and refs match."""
    code, out, calls = _run_branch_block(
        tmp_path, gh, refs, car_head=_CAR, train_pr="9"
    )
    assert code != 0
    assert "OK:" not in out
    assert _deletes(calls) == []


@pytest.mark.parametrize(
    ("pr", "car_head", "train_pr"),
    [
        ("7; true", "", ""),
        ("", "", ""),
        ("7", _CAR, ""),
        ("7", "", "9"),
        ("7", "not-a-sha", "9"),
    ],
    ids=[
        "pr-not-a-number",
        "pr-empty",
        "car-without-train",
        "train-without-car",
        "car-not-a-sha",
    ],
)
def test_cleanup_01_branch_gate_refuses_malformed_inputs(
    tmp_path: Path, pr: str, car_head: str, train_pr: str
) -> None:
    """Inputs arrive as data and are validated before any API call or delete."""
    code, out, calls = _run_branch_block(
        tmp_path,
        _gh_answers(),
        {"remote": _MERGED},
        car_head=car_head,
        train_pr=train_pr,
        pr=pr,
    )
    assert code != 0
    assert "OK:" not in out
    assert _deletes(calls) == []
