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
