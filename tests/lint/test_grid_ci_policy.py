"""Govern the independent, blocking Grid Study CI contract (TEST-05, #1107)."""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.ci.classify_grid_study_paths import load_policy, requires_grid_study

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "test-suite.yml"


@pytest.mark.parametrize(
    "path",
    [
        ".github/workflows/test-suite.yml",
        "analytics/grid/qsts.py",
        "analytics/grid/synthetic_aep_qsts_output_records.py",
        "finance/grid/qsts_finance_boundary.py",
        "tests/grid/test_qsts_output_records.py",
        "scripts/run_synthetic_qsts_output_records_v14.py",
        "conf/synthetic_aep_qsts.yaml",
        "pyproject.toml",
    ],
)
def test_qsts_and_grid_governance_paths_require_independent_ci(path: str) -> None:
    assert requires_grid_study([path]) is True


@pytest.mark.parametrize(
    "path",
    [
        "README.md",
        "docs/knowledge_base/issue_923_synthetic_qsts_workflow_design.md",
        "finance/cashflow_v14.py",
        "app/routes.py",
        "conf/synthetic_input_records.yaml",
    ],
)
def test_unrelated_paths_retain_governed_grid_skip(path: str) -> None:
    assert requires_grid_study([path]) is False


def test_classifier_fails_closed_for_empty_or_unsafe_diff() -> None:
    assert requires_grid_study([]) is True
    assert requires_grid_study(["../analytics/grid/qsts.py"]) is True
    assert requires_grid_study(["/analytics/grid/qsts.py"]) is True


def test_policy_schema_is_exact_and_json_first_cli_writes_actions_output(
    tmp_path: Path,
) -> None:
    policy = load_policy()
    assert policy.empty_diff_requires_grid is True

    github_output = tmp_path / "github-output.txt"
    env = dict(os.environ, GITHUB_OUTPUT=str(github_output))
    completed = subprocess.run(
        [
            str(Path(os.sys.executable)),
            str(REPO_ROOT / "scripts" / "ci" / "classify_grid_study_paths.py"),
        ],
        input=b"analytics/grid/qsts.py\0README.md\0",
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        check=True,
    )
    payload = json.loads(completed.stdout)
    assert payload == {
        "changed_path_count": 2,
        "qsts_execution_changed": True,
        "rule_id": "TEST-05",
        "schema_version": "1.0",
    }
    assert github_output.read_text(encoding="utf-8") == (
        "qsts_execution_changed=true\n"
    )


def test_workflow_binds_pr_head_and_blocks_summary_on_grid_failure() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    grid_job = workflow.split("  grid-study:\n", maxsplit=1)[1]

    assert (
        "qsts_execution_changed: ${{ steps.classify.outputs.qsts_execution_changed }}"
        in workflow
    )
    assert "github.event.pull_request.head.sha" in grid_job
    assert "EXPECTED_HEAD_SHA: ${{" in grid_job
    assert 'actual_head_sha="$(git rev-parse HEAD)"' in grid_job
    assert 'if [ "$actual_head_sha" != "$EXPECTED_HEAD_SHA" ]; then' in grid_job
    assert "DUTCHBAY_GRID_CI_EXECUTION: independent" in grid_job
    assert 'python -c "import opendssdirect"' in grid_job
    assert "python -m pytest tests/ -m grid -n auto --tb=short" in grid_job
    assert "--junit-xml=grid-study-results.xml" in grid_job
    assert "continue-on-error" not in grid_job

    summary = workflow.split("  summary:\n", maxsplit=1)[1].split(
        "  # TEST-03 scale lane", maxsplit=1
    )[0]
    assert "needs: [changes, test, lint, security, coverage, grid-study]" in summary
    assert "needs.grid-study.result" in summary
    assert "Grid Study is required but did not succeed" in summary


def test_gwtf_and_agents_require_independent_qsts_ci() -> None:
    with (REPO_ROOT / "go_with_the_flow_rules_v3_0_clean.csv").open(
        newline="", encoding="utf-8"
    ) as stream:
        rules = {row["rule_id"]: row for row in csv.DictReader(stream)}

    rule = rules["TEST-05"]
    assert "exact pull-request head SHA" in rule["description"]
    assert "Local execution alone" in rule["description"]
    assert "Test Summary" in rule["enforcement"]

    agents = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "QSTS execution" in agents
    assert "exact pull-request head SHA" in agents
    assert "local evidence is supplementary" in agents


# ---------------------------------------------------------------------------
# #1323: the classification's input is recorded, and a missing receipt names its cause
# ---------------------------------------------------------------------------


def _workflow_step_run(job: str, step_name: str) -> str:
    """Return the ``run`` script of one named step in the test-suite workflow."""
    import yaml

    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    for step in workflow["jobs"][job]["steps"]:
        if step.get("name") == step_name:
            return str(step["run"])
    raise AssertionError(f"step {step_name!r} not found in job {job!r}")


_STRIPPED_ENV_VARS = ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE", "BASH_ENV")


def _hermetic_env(**extra: str) -> dict[str, str]:
    """Environment whose ``python`` is the interpreter running these tests (#1324 G-A1-06).

    Isolates throwaway Git repositories and ``bash -e`` runs from host Git config and
    shell-startup hooks (#1421 G-A2-06, G-D2-04).
    """
    env = {
        key: value for key, value in os.environ.items() if key not in _STRIPPED_ENV_VARS
    }
    path = os.pathsep.join([str(Path(sys.executable).parent), env.get("PATH", "")])
    env.update(
        {
            "PATH": path,
            "PYTHONDONTWRITEBYTECODE": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            **extra,
        }
    )
    return env


def _git(repo: Path, *args: str) -> str:
    """Run Git in a throwaway repository and return stdout."""
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        env=_hermetic_env(),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _run_like_ci(
    script: str, cwd: Path, env: dict[str, str], tmp_path: Path, name: str
) -> subprocess.CompletedProcess[str]:
    """Run a ``run:`` block the way the runner does: ``bash -e {0}`` on a script file."""
    script_path = tmp_path / f"{name}.sh"
    script_path.write_text(script, encoding="utf-8")
    return subprocess.run(
        ["bash", "-e", str(script_path)],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )


def test_classify_step_records_its_base_merge_base_and_result() -> None:
    """The run's log and summary must show which base classified it (#1323)."""
    run = _workflow_step_run("changes", "Classify diff against the PR base")

    assert 'base_sha="${{ github.event.pull_request.base.sha }}"' in run
    assert 'git diff --name-only -z "${base_sha}...HEAD"' in run
    assert 'merge_base="$(git merge-base "$base_sha" HEAD' in run
    assert "### Changed-path classification" in run
    assert '} | tee -a "$GITHUB_STEP_SUMMARY"' in run
    block = run.split("### Changed-path classification", 1)[1]
    for recorded in (
        "$base_sha",
        "$merge_base",
        "git rev-parse HEAD",
        "- code_changed: $code",
        "$grid_classification",
    ):
        assert recorded in block


def _render_classify_step(base_sha: str, *, event_name: str = "pull_request") -> str:
    """Substitute the two GitHub expressions the classify step reads."""
    run = _workflow_step_run("changes", "Classify diff against the PR base")
    rendered = run.replace("${{ github.event_name }}", event_name).replace(
        "${{ github.event.pull_request.base.sha }}", base_sha
    )
    assert "${{" not in rendered
    return rendered


def _classify_repo(tmp_path: Path) -> tuple[Path, str]:
    """Create a throwaway repository holding the real classifier and its policy."""
    repo = tmp_path / "repo"
    (repo / "scripts" / "ci").mkdir(parents=True)
    (repo / "config").mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.name", "Classify Test")
    _git(repo, "config", "user.email", "classify@example.invalid")
    for relative in (
        "scripts/ci/classify_grid_study_paths.py",
        "config/grid_ci_policy.json",
    ):
        (repo / relative).write_bytes((REPO_ROOT / relative).read_bytes())
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "base")
    return repo, _git(repo, "rev-parse", "HEAD")


def _run_classify_step(
    repo: Path, tmp_path: Path, bases: dict[str, str], *, draft: str = "false"
) -> dict[str, tuple[str, str, str]]:
    """Run the real classify step at HEAD against each base: (outputs, summary, log).

    ``draft`` is the step's ``PR_DRAFT`` value, ``github.event.pull_request.draft`` in CI.
    """
    results = {}
    for label, base in bases.items():
        output = tmp_path / f"{label}.output"
        summary = tmp_path / f"{label}.summary"
        env = _hermetic_env(
            GITHUB_OUTPUT=str(output),
            GITHUB_STEP_SUMMARY=str(summary),
            RUNNER_TEMP=str(tmp_path),
            PR_DRAFT=draft,
        )
        completed = _run_like_ci(
            _render_classify_step(base), repo, env, tmp_path, f"classify-{label}"
        )
        assert completed.returncode == 0, completed.stderr
        summary_text = summary.read_text(encoding="utf-8")
        # The block reaches the log as well as the summary (#1324 G-D1-01).
        assert summary_text in completed.stdout
        if draft != "true":
            # Pin the direct JSON log line (#1421 G-D2-05 R8).
            assert "grid classification: {" in completed.stdout
        results[label] = (
            output.read_text(encoding="utf-8"),
            summary_text,
            completed.stdout,
        )
    return results


def _recorded(label: str, sha: str) -> str:
    return f"- {label}: `{sha}`"


def test_classify_step_runs_and_a_stale_base_can_widen_the_diff(
    tmp_path: Path,
) -> None:
    """Execute the real classify step against fresh, stale and unmerged bases (#1323).

    The PR head merges a ``main`` that changed the grid surface, then adds one doc.
    Against the fresh base only the doc is in the diff and Grid Study is not required.
    Against a stale base, ``main``'s grid change is swept in and Grid Study is required.
    Against a base the head has not merged, the merge base differs from the base, and the
    log and summary record both.
    """
    repo, stale_base = _classify_repo(tmp_path)

    (repo / "analytics" / "grid").mkdir(parents=True)
    (repo / "analytics" / "grid" / "ride_through.py").write_text(
        "X = 1\n", encoding="utf-8"
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "main changes the grid surface")
    fresh_base = _git(repo, "rev-parse", "HEAD")

    _git(repo, "checkout", "-q", "-b", "pr", stale_base)
    (repo / "docs").mkdir()
    (repo / "docs" / "note.md").write_text("note\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "docs")
    _git(repo, "merge", "-q", "--no-ff", "-m", "merge main", "main")
    head = _git(repo, "rev-parse", "HEAD")

    _git(repo, "checkout", "-q", "main")
    (repo / "later.md").write_text("later\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "main moves on")
    unmerged_base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "pr")

    results = _run_classify_step(
        repo,
        tmp_path,
        {"fresh": fresh_base, "stale": stale_base, "unmerged": unmerged_base},
    )

    fresh_output, fresh_summary, fresh_log = results["fresh"]
    assert "qsts_execution_changed=false" in fresh_output
    assert "code_changed=false" in fresh_output
    assert "- code_changed: false" in fresh_summary
    assert '"changed_path_count": 1' in fresh_summary
    assert _recorded("Merge base with the PR head", fresh_base) in fresh_log
    assert _recorded("PR head", head) in fresh_log

    stale_output, stale_summary, stale_log = results["stale"]
    assert "qsts_execution_changed=true" in stale_output
    assert _recorded("Event `pull_request.base.sha`", stale_base) in stale_summary
    assert _recorded("Merge base with the PR head", stale_base) in stale_log
    assert '"changed_path_count": 2' in stale_summary

    unmerged_output, unmerged_summary, unmerged_log = results["unmerged"]
    assert "qsts_execution_changed=false" in unmerged_output
    assert _recorded("Event `pull_request.base.sha`", unmerged_base) in unmerged_log
    assert _recorded("Merge base with the PR head", fresh_base) in unmerged_log
    assert '"changed_path_count": 1' in unmerged_summary


def test_classify_step_defers_the_full_suite_on_a_draft(tmp_path: Path) -> None:
    """REVIEW-01: a draft classifies as no tests and no Grid Study, whatever it changes.

    The head changes the grid surface, so the same step run for a non-draft event must
    require both. That second run is the negative control: without it, a step that always
    printed ``false`` would pass.
    """
    repo, base = _classify_repo(tmp_path)
    (repo / "analytics" / "grid").mkdir(parents=True)
    (repo / "analytics" / "grid" / "ride_through.py").write_text(
        "X = 1\n", encoding="utf-8"
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "change the grid surface")
    head = _git(repo, "rev-parse", "HEAD")

    draft_output, draft_summary, draft_log = _run_classify_step(
        repo, tmp_path, {"draft": base}, draft="true"
    )["draft"]
    assert "code_changed=false" in draft_output
    assert "qsts_execution_changed=false" in draft_output
    assert "full suite deferred until ready for review (REVIEW-01)" in draft_summary
    assert _recorded("PR head", head) in draft_log

    ready_output, _, _ = _run_classify_step(
        repo, tmp_path, {"ready": base}, draft="false"
    )["ready"]
    assert "code_changed=true" in ready_output
    assert "qsts_execution_changed=true" in ready_output


def test_classify_step_a_stale_base_can_also_narrow_the_diff(tmp_path: Path) -> None:
    """A stale base does not only err toward running Grid Study (#1323, #1322 S-A4-03).

    ``main`` changes the grid surface. The PR head merges that ``main``, reverts the
    grid change and adds one doc. Against the fresh base the revert is a grid change and
    Grid Study is required. Against the stale base the grid file is unchanged, so only
    the doc is in the diff and Grid Study would be skipped. This is why the step records
    which base classified the run.
    """
    repo, _ = _classify_repo(tmp_path)

    grid_file = repo / "analytics" / "grid" / "ride_through.py"
    grid_file.parent.mkdir(parents=True)
    grid_file.write_text("X = 1\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "grid surface exists at the stale base")
    stale_base = _git(repo, "rev-parse", "HEAD")

    grid_file.write_text("X = 2\n", encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "main changes the grid surface")
    fresh_base = _git(repo, "rev-parse", "HEAD")

    _git(repo, "checkout", "-q", "-b", "pr", stale_base)
    (repo / "docs").mkdir()
    (repo / "docs" / "note.md").write_text("note\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "docs")
    _git(repo, "merge", "-q", "--no-ff", "-m", "merge main", "main")
    grid_file.write_text("X = 1\n", encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "revert main's grid change")

    results = _run_classify_step(
        repo, tmp_path, {"fresh": fresh_base, "stale": stale_base}
    )

    fresh_output, fresh_summary, fresh_log = results["fresh"]
    assert "qsts_execution_changed=true" in fresh_output
    assert '"changed_path_count": 2' in fresh_summary
    assert _recorded("Merge base with the PR head", fresh_base) in fresh_log

    stale_output, stale_summary, stale_log = results["stale"]
    assert "qsts_execution_changed=false" in stale_output
    assert '"changed_path_count": 1' in stale_summary
    assert _recorded("Merge base with the PR head", stale_base) in stale_log


def test_classify_step_an_empty_own_diff_requires_grid_study(tmp_path: Path) -> None:
    """An empty diff fails closed, and a stale base can still skip it (#1324 G-A1-09).

    The PR head is exactly ``main`` after ``main`` added one doc. Against the fresh base
    the diff is empty, so both the full gate and Grid Study are required. Against the
    stale base the diff widens to the doc, and neither is required.
    """
    repo, stale_base = _classify_repo(tmp_path)
    (repo / "docs").mkdir()
    (repo / "docs" / "a.md").write_text("a\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "main adds a doc")
    fresh_base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "-b", "pr", fresh_base)

    results = _run_classify_step(
        repo, tmp_path, {"fresh": fresh_base, "stale": stale_base}
    )

    fresh_output, fresh_summary, _ = results["fresh"]
    assert "code_changed=true" in fresh_output
    assert "qsts_execution_changed=true" in fresh_output
    assert '"changed_path_count": 0' in fresh_summary

    stale_output, stale_summary, _ = results["stale"]
    assert "code_changed=false" in stale_output
    assert "qsts_execution_changed=false" in stale_output
    assert '"changed_path_count": 1' in stale_summary


def test_classify_step_fails_when_the_classifier_crashes(tmp_path: Path) -> None:
    """A classifier crash fails the step instead of yielding a skip (#1324 G-A1-05)."""
    repo, base = _classify_repo(tmp_path)
    (repo / "config" / "grid_ci_policy.json").write_text("{}", encoding="utf-8")
    (repo / "note.md").write_text("note\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "break the policy")

    output = tmp_path / "crash.output"
    env = _hermetic_env(
        GITHUB_OUTPUT=str(output),
        GITHUB_STEP_SUMMARY=str(tmp_path / "crash.summary"),
        RUNNER_TEMP=str(tmp_path),
    )
    completed = _run_like_ci(
        _render_classify_step(base), repo, env, tmp_path, "classify-crash"
    )

    assert completed.returncode != 0
    assert "grid CI policy keys must be exact" in completed.stderr
    # Under an ``|| true`` mask the step would succeed with no Grid Study output, and
    # the grid-study job would skip. Failing the step is what keeps that closed.
    written = output.read_text(encoding="utf-8") if output.exists() else ""
    assert "qsts_execution_changed=" not in written


@pytest.mark.parametrize("event_name", ["push", "schedule", "workflow_dispatch"])
def test_classify_step_non_pr_events_run_full_gate_without_grid_flag(
    tmp_path: Path, event_name: str
) -> None:
    """Non-PR events always run the full gate without setting PR grid flag (#1421 G-D2-07).

    Kills the fail-open mutant that writes ``code_changed=false`` on non-PR triggers
    (``schedule`` and ``workflow_dispatch``) and verifies no checkout is required.
    """
    output = tmp_path / f"{event_name}.output"
    summary = tmp_path / f"{event_name}.summary"
    env = _hermetic_env(
        GITHUB_OUTPUT=str(output),
        GITHUB_STEP_SUMMARY=str(summary),
        RUNNER_TEMP=str(tmp_path),
        PR_DRAFT="",
    )
    completed = _run_like_ci(
        _render_classify_step("", event_name=event_name),
        tmp_path,
        env,
        tmp_path,
        f"classify-{event_name}",
    )

    assert completed.returncode == 0, completed.stderr
    assert "non-PR event: full gate" in completed.stdout
    assert output.read_text(encoding="utf-8").splitlines() == [
        "code_changed=true",
        "qsts_execution_changed=false",
    ]


def test_classify_step_records_undeterminable_merge_base_on_empty_base(
    tmp_path: Path,
) -> None:
    """An empty PR base records ``undeterminable`` and fails closed (#1421 G-D2-05 R6)."""
    repo, _ = _classify_repo(tmp_path)
    (repo / "docs").mkdir()
    (repo / "docs" / "note.md").write_text("note\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "docs")

    empty_output, empty_summary, empty_log = _run_classify_step(
        repo, tmp_path, {"empty": ""}
    )["empty"]
    assert "code_changed=true" in empty_output
    assert "qsts_execution_changed=true" in empty_output
    assert _recorded("Merge base with the PR head", "undeterminable") in empty_summary
    assert _recorded("Merge base with the PR head", "undeterminable") in empty_log


def test_classify_step_fails_closed_on_unrelated_history_base(tmp_path: Path) -> None:
    """An unrelated-history base fails the classify step without writing outputs (#1421 G-D2-05)."""
    repo, _ = _classify_repo(tmp_path)
    _git(repo, "checkout", "-q", "--orphan", "unrelated")
    _git(repo, "rm", "-rfq", ".")
    (repo / "orphan.md").write_text("orphan\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "unrelated history")
    orphan_base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "main")

    output = tmp_path / "unrelated.output"
    env = _hermetic_env(
        GITHUB_OUTPUT=str(output),
        GITHUB_STEP_SUMMARY=str(tmp_path / "unrelated.summary"),
        RUNNER_TEMP=str(tmp_path),
        PR_DRAFT="false",
    )
    completed = _run_like_ci(
        _render_classify_step(orphan_base), repo, env, tmp_path, "classify-unrelated"
    )

    assert completed.returncode != 0
    written = output.read_text(encoding="utf-8") if output.exists() else ""
    assert "qsts_execution_changed=" not in written


def test_classify_step_fails_closed_when_step_summary_is_unwritable(
    tmp_path: Path,
) -> None:
    """An unwritable job summary fails the step via ``tee`` (#1421 G-D2-05 R7)."""
    repo, base = _classify_repo(tmp_path)
    (repo / "docs").mkdir()
    (repo / "docs" / "note.md").write_text("note\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "docs")

    unwritable_summary = tmp_path / "summary-dir"
    unwritable_summary.mkdir()
    env = _hermetic_env(
        GITHUB_OUTPUT=str(tmp_path / "unwritable.output"),
        GITHUB_STEP_SUMMARY=str(unwritable_summary),
        RUNNER_TEMP=str(tmp_path),
        PR_DRAFT="false",
    )
    completed = _run_like_ci(
        _render_classify_step(base), repo, env, tmp_path, "classify-unwritable"
    )

    assert completed.returncode != 0


def test_throwaway_git_and_shell_ignore_host_config_and_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Throwaway repos and shell runs ignore host Git config and hooks (#1421 G-A2-06, G-D2-04)."""
    bad_gitconfig = tmp_path / "bad.gitconfig"
    bad_gitconfig.write_text(
        "[commit]\n\tgpgsign = true\n[gpg]\n\tprogram = /nonexistent/gpg-signer\n",
        encoding="utf-8",
    )
    bad_bash_env = tmp_path / "bad_bash_env.sh"
    bad_bash_env.write_text("exit 99\n", encoding="utf-8")

    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(bad_gitconfig))
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "decoy.git"))
    monkeypatch.setenv("GIT_INDEX_FILE", str(tmp_path / "decoy.index"))
    monkeypatch.setenv("GIT_WORK_TREE", str(tmp_path / "decoy.worktree"))
    monkeypatch.setenv("BASH_ENV", str(bad_bash_env))

    repo, base = _classify_repo(tmp_path)
    output, _, _ = _run_classify_step(repo, tmp_path, {"isolated": base})["isolated"]
    assert "code_changed=true" in output
    assert "qsts_execution_changed=true" in output


def _run_evidence_step(
    workdir: Path,
    junit_xml: str | None,
    receipt: dict[str, object] | bytes | None,
    head_sha: str,
    *,
    receipt_kind: str = "file",
) -> subprocess.CompletedProcess[str]:
    """Execute the whole evidence step, shell guard included, in a constructed workspace."""
    run = _workflow_step_run("grid-study", "Validate complete Grid Study evidence")
    workspace = workdir / "workspace"
    workspace.mkdir()
    if junit_xml is not None:
        (workspace / "grid-study-results.xml").write_text(junit_xml, encoding="utf-8")
    receipt_path = workspace / "outputs" / "grid_base_candidate_numerical_receipt.json"
    if receipt_kind == "directory":
        receipt_path.mkdir(parents=True)
    elif receipt_kind == "dangling_symlink":
        receipt_path.parent.mkdir(parents=True)
        receipt_path.symlink_to(workspace / "outputs" / "nonexistent-target.json")
    elif receipt is not None:
        receipt_path.parent.mkdir()
        if isinstance(receipt, bytes):
            receipt_path.write_bytes(receipt)
        else:
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    env = _hermetic_env(
        EXPECTED_HEAD_SHA=head_sha,
        GITHUB_STEP_SUMMARY=str(workdir / "summary.md"),
    )
    return _run_like_ci(run, workspace, env, workdir, "evidence")


_RECEIPT_REL = "outputs/grid_base_candidate_numerical_receipt.json"
_RECEIPT_CLASS = "tests.grid.test_base_candidate_physical_receipt"
_RECEIPT_NAME = "test_base_candidate_physical_numerical_receipt"
_PASSED_RECEIPT_CASE = (
    f'<testcase classname="{_RECEIPT_CLASS}" name="{_RECEIPT_NAME}"/>'
)


def _junit(receipt_case: str) -> str:
    return (
        '<testsuites><testsuite name="pytest">'
        '<testcase classname="tests.grid.test_other" name="test_runs"/>'
        f"{receipt_case}"
        "</testsuite></testsuites>"
    )


def _complete_receipt(head: str) -> dict[str, object]:
    return {
        "candidate_commit": head,
        "base_commit": "4da2a82352d532138ee7f2483b82dfbf5a1d9c2b",
        "case_count": 6,
        "cases": [
            {"id": case_id}
            for case_id in (
                "lvrt_mild",
                "lvrt_severe",
                "hvrt_default",
                "hvrt_severe",
                "frequency_default",
                "frequency_severe",
            )
        ],
    }


@pytest.mark.parametrize(
    ("skip_tag", "expected_cause"),
    [
        (
            "<skipped message=\"could not import 'andes': No module named 'andes'\"/>",
            "its test was skipped (could not import 'andes': No module named 'andes'); "
            "it skips when andes cannot be imported, and the [grid] extra must install andes",
        ),
        (
            "<skipped/>",
            "its test was skipped; "
            "it skips when andes cannot be imported, and the [grid] extra must install andes",
        ),
    ],
    ids=["with_reason", "without_reason"],
)
def test_evidence_step_names_a_skipped_receipt_test(
    tmp_path: Path, skip_tag: str, expected_cause: str
) -> None:
    """A skipped receipt test is named with its exact cause, not a bare exit (#1323, #1421)."""
    skipped = (
        f'<testcase classname="{_RECEIPT_CLASS}" name="{_RECEIPT_NAME}">'
        f"{skip_tag}</testcase>"
    )
    completed = _run_evidence_step(tmp_path, _junit(skipped), None, "a" * 40)

    assert completed.returncode != 0
    assert completed.stderr.strip() == (
        f"paired receipt {_RECEIPT_REL} is missing: {expected_cause}"
    )


def test_evidence_step_names_an_absent_receipt_test(tmp_path: Path) -> None:
    """A receipt test missing from the JUnit evidence is named as absent (#1323, #1421)."""
    completed = _run_evidence_step(tmp_path, _junit(""), None, "a" * 40)

    assert completed.returncode != 0
    assert completed.stderr.strip() == (
        f"paired receipt {_RECEIPT_REL} is missing: "
        f"its test, {_RECEIPT_NAME}, is absent from the JUnit evidence"
    )


def test_evidence_step_names_a_receipt_test_that_wrote_nothing(tmp_path: Path) -> None:
    """A receipt test that passed without writing its file is named (#1324 G-D1-02, #1421)."""
    completed = _run_evidence_step(
        tmp_path, _junit(_PASSED_RECEIPT_CASE), None, "a" * 40
    )

    assert completed.returncode != 0
    assert completed.stderr.strip() == (
        f"paired receipt {_RECEIPT_REL} is missing: "
        "its test passed without writing the receipt"
    )


@pytest.mark.parametrize(
    ("receipt", "receipt_kind"),
    [
        (b"", "file"),
        (None, "directory"),
        (None, "dangling_symlink"),
    ],
    ids=["empty_file", "directory", "dangling_symlink"],
)
def test_evidence_step_names_an_empty_or_irregular_receipt_path(
    tmp_path: Path, receipt: bytes | None, receipt_kind: str
) -> None:
    """Empty, directory, and dangling-symlink receipts are named as irregular (#1421 G-D1-05, G-A1-08)."""
    completed = _run_evidence_step(
        tmp_path,
        _junit(_PASSED_RECEIPT_CASE),
        receipt,
        "a" * 40,
        receipt_kind=receipt_kind,
    )

    assert completed.returncode != 0
    assert completed.stderr.strip() == (
        f"paired receipt {_RECEIPT_REL} is missing: "
        "the path exists but is empty or not a regular file"
    )
    assert "passed without writing the receipt" not in completed.stderr


def test_evidence_step_still_accepts_a_complete_receipt(tmp_path: Path) -> None:
    """Positive control: the diagnosis does not reject valid evidence (#1323)."""
    head = "b" * 40
    completed = _run_evidence_step(
        tmp_path, _junit(_PASSED_RECEIPT_CASE), _complete_receipt(head), head
    )

    assert completed.returncode == 0, completed.stderr
    assert "six cases and exact head validated" in (tmp_path / "summary.md").read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize("tag", ["failure", "error"])
def test_evidence_step_rejects_a_failed_grid_test(tmp_path: Path, tag: str) -> None:
    """A failure or error in JUnit fails the step even with a receipt (#1324 G-A1-05, #1421)."""
    head = "b" * 40
    failed = (
        '<testcase classname="tests.grid.test_other" name="test_fails">'
        f'<{tag} message="boom"/></testcase>'
        f"{_PASSED_RECEIPT_CASE}"
    )
    completed = _run_evidence_step(
        tmp_path, _junit(failed), _complete_receipt(head), head
    )

    assert completed.returncode != 0
    assert completed.stderr.strip() == (
        "Grid Study JUnit evidence contains a failure or error"
    )


@pytest.mark.parametrize("junit_xml", [None, ""], ids=["missing", "empty"])
def test_evidence_step_names_a_missing_or_empty_junit_file(
    tmp_path: Path, junit_xml: str | None
) -> None:
    """Missing or empty JUnit fails with a named error, killing ``-s``->``-e`` (#1421 G-A2-04)."""
    run = _workflow_step_run("grid-study", "Validate complete Grid Study evidence")
    assert "test -s grid-study-results.xml" not in run
    assert "test -s outputs/grid_base_candidate_numerical_receipt.json" not in run

    completed = _run_evidence_step(tmp_path, junit_xml, None, "a" * 40)

    assert completed.returncode != 0
    assert (
        "::error::Grid Study JUnit evidence grid-study-results.xml is missing or empty: "
        "the grid-marked pytest run did not complete (#1323)"
    ) in completed.stdout


def test_evidence_step_rejects_junit_with_no_testcases(tmp_path: Path) -> None:
    """JUnit with zero testcases is rejected by its own guard (#1421 G-A2-05 A19)."""
    head = "b" * 40
    empty_suite = '<testsuites><testsuite name="pytest"></testsuite></testsuites>'
    completed = _run_evidence_step(tmp_path, empty_suite, _complete_receipt(head), head)

    assert completed.returncode != 0
    assert completed.stderr.strip() == "Grid Study JUnit evidence contains no testcases"


def test_evidence_step_rejects_junit_with_only_skipped_testcases(
    tmp_path: Path,
) -> None:
    """JUnit containing only skipped testcases is rejected even with a receipt (#1421 G-A2-05 A10)."""
    head = "b" * 40
    only_skipped = (
        '<testsuites><testsuite name="pytest">'
        '<testcase classname="tests.grid.test_other" name="test_runs">'
        '<skipped message="skipped"/></testcase>'
        f'<testcase classname="{_RECEIPT_CLASS}" name="{_RECEIPT_NAME}">'
        '<skipped message="skipped"/></testcase>'
        "</testsuite></testsuites>"
    )
    completed = _run_evidence_step(
        tmp_path, only_skipped, _complete_receipt(head), head
    )

    assert completed.returncode != 0
    assert completed.stderr.strip() == (
        "Grid Study JUnit evidence contains only skipped testcases"
    )


def test_evidence_step_rejects_receipt_with_mismatched_candidate_head(
    tmp_path: Path,
) -> None:
    """A receipt whose candidate_commit differs from EXPECTED_HEAD_SHA fails (#1421 G-A2-05 A11)."""
    completed = _run_evidence_step(
        tmp_path,
        _junit(_PASSED_RECEIPT_CASE),
        _complete_receipt("c" * 40),
        "b" * 40,
    )

    assert completed.returncode != 0
    assert completed.stderr.strip() == (
        "paired receipt candidate commit does not match exact head"
    )


def test_evidence_step_rejects_receipt_with_non_protected_base_commit(
    tmp_path: Path,
) -> None:
    """A receipt whose base_commit is not protected main fails (#1421 G-A2-05 A17)."""
    head = "b" * 40
    receipt = {**_complete_receipt(head), "base_commit": "0" * 40}
    completed = _run_evidence_step(
        tmp_path, _junit(_PASSED_RECEIPT_CASE), receipt, head
    )

    assert completed.returncode != 0
    assert completed.stderr.strip() == (
        "paired receipt base commit is not protected main"
    )


@pytest.mark.parametrize(
    "mutation",
    ["wrong_count", "duplicate_case", "wrong_case_id"],
)
def test_evidence_step_rejects_incomplete_or_mismatched_physical_cases(
    tmp_path: Path, mutation: str
) -> None:
    """Each clause of the six-case check is pinned (#1421 G-A2-05 A18)."""
    head = "b" * 40
    receipt = _complete_receipt(head)
    cases = list(receipt["cases"])  # type: ignore[arg-type]
    if mutation == "wrong_count":
        receipt["case_count"] = 5
    elif mutation == "duplicate_case":
        cases.append({"id": "lvrt_mild"})
        receipt["cases"] = cases
    elif mutation == "wrong_case_id":
        cases[-1] = {"id": "unexpected_case"}
        receipt["cases"] = cases
    completed = _run_evidence_step(
        tmp_path, _junit(_PASSED_RECEIPT_CASE), receipt, head
    )

    assert completed.returncode != 0
    assert completed.stderr.strip() == (
        "paired receipt does not contain all six physical cases"
    )
