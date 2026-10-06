"""Govern the independent, blocking Grid Study CI contract (TEST-05, #1107)."""

from __future__ import annotations

import csv
import json
import os
import subprocess
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


def _git(repo: Path, *args: str) -> str:
    """Run Git in a throwaway repository and return stdout."""
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def test_classify_step_records_its_base_merge_base_and_result() -> None:
    """The run's own summary must show which base classified it (#1323)."""
    run = _workflow_step_run("changes", "Classify diff against the PR base")

    assert 'base_sha="${{ github.event.pull_request.base.sha }}"' in run
    assert 'git diff --name-only -z "${base_sha}...HEAD"' in run
    assert 'merge_base="$(git merge-base "$base_sha" HEAD' in run
    assert "### Changed-path classification" in run
    assert '>> "$GITHUB_STEP_SUMMARY"' in run
    for recorded in (
        "$base_sha",
        "$merge_base",
        "git rev-parse HEAD",
        "$grid_classification",
    ):
        assert recorded in run.split("### Changed-path classification", 1)[1]


def _render_classify_step(base_sha: str) -> str:
    """Substitute the two GitHub expressions the classify step reads."""
    run = _workflow_step_run("changes", "Classify diff against the PR base")
    rendered = run.replace("${{ github.event_name }}", "pull_request").replace(
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
    repo: Path, tmp_path: Path, bases: dict[str, str]
) -> dict[str, tuple[str, str]]:
    """Run the real classify step at the repository's HEAD against each named base."""
    results = {}
    for label, base in bases.items():
        output = tmp_path / f"{label}.output"
        summary = tmp_path / f"{label}.summary"
        env = {
            **os.environ,
            "GITHUB_OUTPUT": str(output),
            "GITHUB_STEP_SUMMARY": str(summary),
            "RUNNER_TEMP": str(tmp_path),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        completed = subprocess.run(
            ["bash", "-eo", "pipefail", "-c", _render_classify_step(base)],
            cwd=repo,
            env=env,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr
        results[label] = (
            output.read_text(encoding="utf-8"),
            summary.read_text(encoding="utf-8"),
        )
    return results


def test_classify_step_runs_and_a_stale_base_can_widen_the_diff(
    tmp_path: Path,
) -> None:
    """Execute the real classify step against a fresh and a stale base (#1323).

    The PR head merges a ``main`` that changed the grid surface, then adds one doc.
    Against the fresh base only the doc is in the diff and Grid Study is not required.
    Against a stale base, ``main``'s grid change is swept in and Grid Study is required.
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

    results = _run_classify_step(
        repo, tmp_path, {"fresh": fresh_base, "stale": stale_base}
    )

    fresh_output, fresh_summary = results["fresh"]
    assert "qsts_execution_changed=false" in fresh_output
    assert "code_changed=false" in fresh_output
    assert f"`{fresh_base}`" in fresh_summary
    assert '"changed_path_count": 1' in fresh_summary

    stale_output, stale_summary = results["stale"]
    assert "qsts_execution_changed=true" in stale_output
    assert f"`{stale_base}`" in stale_summary
    assert '"changed_path_count": 2' in stale_summary


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

    fresh_output, fresh_summary = results["fresh"]
    assert "qsts_execution_changed=true" in fresh_output
    assert '"changed_path_count": 2' in fresh_summary

    stale_output, stale_summary = results["stale"]
    assert "qsts_execution_changed=false" in stale_output
    assert '"changed_path_count": 1' in stale_summary


def _run_evidence_validator(
    workdir: Path, junit_xml: str, receipt: dict[str, object] | None, head_sha: str
) -> subprocess.CompletedProcess[str]:
    """Execute the evidence step's real Python against a constructed workspace."""
    run = _workflow_step_run("grid-study", "Validate complete Grid Study evidence")
    assert "python - <<'PY'\n" in run
    validator = run.split("python - <<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
    (workdir / "grid-study-results.xml").write_text(junit_xml, encoding="utf-8")
    if receipt is not None:
        (workdir / "outputs").mkdir(exist_ok=True)
        (workdir / "outputs" / "grid_base_candidate_numerical_receipt.json").write_text(
            json.dumps(receipt), encoding="utf-8"
        )
    env = {
        **os.environ,
        "EXPECTED_HEAD_SHA": head_sha,
        "GITHUB_STEP_SUMMARY": str(workdir / "summary.md"),
    }
    return subprocess.run(
        ["python", "-c", validator],
        cwd=workdir,
        env=env,
        capture_output=True,
        text=True,
    )


_RECEIPT_CLASS = "tests.grid.test_base_candidate_physical_receipt"
_RECEIPT_NAME = "test_base_candidate_physical_numerical_receipt"


def _junit(receipt_case: str) -> str:
    return (
        '<testsuites><testsuite name="pytest">'
        '<testcase classname="tests.grid.test_other" name="test_runs"/>'
        f"{receipt_case}"
        "</testsuite></testsuites>"
    )


def test_evidence_step_names_a_skipped_receipt_test(tmp_path: Path) -> None:
    """A skipped receipt test is named, with the andes cause, not a bare exit (#1323)."""
    skipped = (
        f'<testcase classname="{_RECEIPT_CLASS}" name="{_RECEIPT_NAME}">'
        "<skipped message=\"could not import 'andes': No module named 'andes'\"/>"
        "</testcase>"
    )
    completed = _run_evidence_validator(tmp_path, _junit(skipped), None, "a" * 40)

    assert completed.returncode != 0
    assert "paired receipt" in completed.stderr
    assert "its test was skipped" in completed.stderr
    assert "could not import 'andes'" in completed.stderr
    assert "[grid] extra must install andes" in completed.stderr


def test_evidence_step_names_an_absent_receipt_test(tmp_path: Path) -> None:
    """A receipt test missing from the JUnit evidence is named as absent (#1323)."""
    completed = _run_evidence_validator(tmp_path, _junit(""), None, "a" * 40)

    assert completed.returncode != 0
    assert "is absent from the JUnit evidence" in completed.stderr


def test_evidence_step_still_accepts_a_complete_receipt(tmp_path: Path) -> None:
    """Positive control: the diagnosis does not reject valid evidence (#1323)."""
    head = "b" * 40
    receipt = {
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
    passed = f'<testcase classname="{_RECEIPT_CLASS}" name="{_RECEIPT_NAME}"/>'
    completed = _run_evidence_validator(tmp_path, _junit(passed), receipt, head)

    assert completed.returncode == 0, completed.stderr
    assert "six cases and exact head validated" in (tmp_path / "summary.md").read_text(
        encoding="utf-8"
    )


def test_evidence_step_names_a_missing_junit_file() -> None:
    """The bare ``test -s`` on the JUnit file is replaced by a named error (#1323)."""
    run = _workflow_step_run("grid-study", "Validate complete Grid Study evidence")

    assert "test -s grid-study-results.xml" not in run
    assert "test -s outputs/grid_base_candidate_numerical_receipt.json" not in run
    assert "Grid Study JUnit evidence grid-study-results.xml is missing or empty" in run
