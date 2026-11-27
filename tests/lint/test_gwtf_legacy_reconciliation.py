"""G6 real Git preflight and control-preservation fences."""

from __future__ import annotations

import csv
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/gwtf-preflight.sh"


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=root, text=True, stderr=subprocess.PIPE
    ).strip()


@pytest.fixture
def linked(tmp_path: Path) -> tuple[Path, Path, str]:
    main = tmp_path / "primary checkout"
    main.mkdir()
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "--bare", str(remote))
    git(main, "init", "-b", "main")
    git(main, "config", "user.name", "Synthetic fixture")
    git(main, "config", "user.email", "fixture@example.invalid")
    (main / "base.txt").write_text("base\n")
    git(main, "add", "base.txt")
    git(main, "commit", "-m", "base")
    git(main, "remote", "add", "origin", str(remote))
    git(main, "push", "-u", "origin", "main")
    base = git(main, "rev-parse", "HEAD")
    work = tmp_path / "writer worktree"
    git(main, "worktree", "add", "-b", "feat/fixture", str(work), "origin/main")
    git(work, "branch", "--unset-upstream")
    return main, work, base


def preflight(
    cwd: Path, expected: Path, branch: str, base: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), str(expected), branch, base],
        cwd=cwd,
        input="y\ny\n",
        text=True,
        capture_output=True,
        check=False,
    )


def test_linked_worktree_missing_upstream_is_unknown(
    linked: tuple[Path, Path, str],
) -> None:
    _, work, base = linked
    before = git(work, "status", "--porcelain")
    result = preflight(work, work, "feat/fixture", base)
    assert result.returncode == 0, result.stderr
    assert "UNKNOWN (no resolvable upstream)" in result.stdout
    assert "not proof" not in result.stdout
    assert git(work, "status", "--porcelain") == before


@pytest.mark.parametrize(
    "defect",
    [
        "protected",
        "wrong_root",
        "wrong_branch",
        "wrong_base",
        "stale_remote",
        "detached",
        "primary_feature",
    ],
)
def test_preflight_refuses_invalid_state(
    linked: tuple[Path, Path, str], defect: str
) -> None:
    main, work, base = linked
    cwd, expected, branch = work, work, "feat/fixture"
    if defect == "protected":
        cwd, expected, branch = main, main, "main"
    elif defect == "wrong_root":
        expected = main
    elif defect == "wrong_branch":
        branch = "feat/other"
    elif defect == "wrong_base":
        base = "0" * 40
    elif defect == "stale_remote":
        git(main, "commit", "--allow-empty", "-m", "advance remote")
        git(main, "push", "origin", "main")
    elif defect == "detached":
        git(work, "switch", "--detach")
    else:
        git(main, "switch", "-c", "feat/primary")
        cwd, expected, branch = main, main, "feat/primary"
    result = preflight(cwd, expected, branch, base)
    assert result.returncode != 0
    assert "preflight passed" not in result.stdout


def test_retired_formatter_has_no_mutation(linked: tuple[Path, Path, str]) -> None:
    _, work, _ = linked
    before = git(work, "status", "--porcelain")
    result = subprocess.run(
        ["bash", str(ROOT / "fix_precommit.sh")],
        cwd=work,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode != 0
    assert "retired" in result.stderr
    assert git(work, "status", "--porcelain") == before


EXPECTED_R10_PRECOMMIT_HOOKS: frozenset[str] = frozenset(
    {
        "black",
        "ruff",
        "isort",
        "no-commit-to-branch",
        "check-ast",
        "check-yaml",
        "check-toml",
        "check-added-large-files",
        "end-of-file-fixer",
        "trailing-whitespace",
        "check-merge-conflict",
        "debug-statements",
    }
)
REQUIRED_R10_CI_MYPY_WORKFLOWS: tuple[str, ...] = (
    "test-suite.yml",
    "ci_v14_fastlane.yml",
    "fx-tests.yml",
    "regression-smoke.yml",
)


def _assert_r10_reconciled(
    *,
    rules: dict[str, dict[str, str]],
    precommit_text: str,
    dev_docs_text: str,
    workflow_texts: dict[str, str],
) -> None:
    """Assert R10, .pre-commit-config.yaml, docs/DEVELOPMENT.md, and CI gates agree."""
    assert {"R10", "R23", "R21", "CLEANUP-01"} <= rules.keys()
    assert all(
        rules[key]["status"] == "active" for key in ("R10", "R23", "R21", "CLEANUP-01")
    )
    r10_desc = rules["R10"]["description"]
    r10_enf = rules["R10"]["enforcement"]
    policy = r10_desc + "\n" + r10_enf

    config = yaml.safe_load(precommit_text)
    hooks = {hook["id"] for repo in config["repos"] for hook in repo["hooks"]}
    assert hooks == EXPECTED_R10_PRECOMMIT_HOOKS
    assert "mypy" not in hooks
    assert "#1270" in precommit_text
    assert "Sprint Day N" not in precommit_text

    assert "mypy (type checking)" not in r10_desc
    for control in (
        "#1270",
        "#1262",
        "mandatory local type verification",
        *REQUIRED_R10_CI_MYPY_WORKFLOWS,
    ):
        assert control in policy

    normalized_docs = " ".join(dev_docs_text.split())
    assert "#1270" in normalized_docs
    assert "does not enable mypy" in normalized_docs
    for token in ("black", "ruff", "isort", "no-commit-to-branch"):
        assert token in normalized_docs
    for workflow in REQUIRED_R10_CI_MYPY_WORKFLOWS:
        assert workflow in normalized_docs
        assert "mypy" in workflow_texts[workflow]
    assert "mypy scripts/ --ignore-missing-imports" in workflow_texts["test-suite.yml"]
    assert "full suite before pushing" in rules["R23"]["description"]
    assert "CLEANUP-01" in rules["R23"]["description"]


def _load_r10_surface() -> tuple[dict[str, dict[str, str]], str, str, dict[str, str]]:
    with (ROOT / "go_with_the_flow_rules_v3_0_clean.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    rules = {r["rule_id"]: r for r in rows}
    assert len(rules) == len(rows), "duplicate rule identity"
    precommit_text = (ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    dev_docs_text = (ROOT / "docs/DEVELOPMENT.md").read_text(encoding="utf-8")
    workflow_texts = {
        workflow: (ROOT / ".github/workflows" / workflow).read_text(encoding="utf-8")
        for workflow in REQUIRED_R10_CI_MYPY_WORKFLOWS
    }
    return rules, precommit_text, dev_docs_text, workflow_texts


def test_r10_local_hooks_and_ci_type_gates_remain_bound() -> None:
    rules, precommit_text, dev_docs_text, workflow_texts = _load_r10_surface()
    _assert_r10_reconciled(
        rules=rules,
        precommit_text=precommit_text,
        dev_docs_text=dev_docs_text,
        workflow_texts=workflow_texts,
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "enable_mypy_hook",
        "claim_mypy_in_r10",
        "drop_1270_from_r10",
        "drop_workflow_from_r10",
        "drop_workflow_from_docs",
        "restore_sprint_day_n_comment",
    ],
)
def test_r10_reconciliation_fence_rejects_drift(mutation: str) -> None:
    """Hostile negative controls: drift between R10, pre-commit, docs, and CI fails."""
    rules, precommit_text, dev_docs_text, workflow_texts = _load_r10_surface()
    rules = {k: dict(v) for k, v in rules.items()}

    if mutation == "enable_mypy_hook":
        precommit_text += (
            "\n  - repo: https://github.com/pre-commit/mirrors-mypy\n"
            "    rev: v1.18.2\n"
            "    hooks:\n"
            "      - id: mypy\n"
        )
    elif mutation == "claim_mypy_in_r10":
        rules["R10"]["description"] += " mypy (type checking)"
    elif mutation == "drop_1270_from_r10":
        rules["R10"]["description"] = rules["R10"]["description"].replace("#1270", "")
        rules["R10"]["enforcement"] = rules["R10"]["enforcement"].replace("#1270", "")
    elif mutation == "drop_workflow_from_r10":
        rules["R10"]["enforcement"] = rules["R10"]["enforcement"].replace(
            "fx-tests.yml", ""
        )
    elif mutation == "drop_workflow_from_docs":
        dev_docs_text = dev_docs_text.replace("fx-tests.yml", "")
    else:
        precommit_text = precommit_text.replace("#1270", "Sprint Day N")

    with pytest.raises(AssertionError):
        _assert_r10_reconciled(
            rules=rules,
            precommit_text=precommit_text,
            dev_docs_text=dev_docs_text,
            workflow_texts=workflow_texts,
        )


def test_preflight_uses_exact_remote_tracking_ref(
    linked: tuple[Path, Path, str],
) -> None:
    _, work, base = linked
    git(work, "commit", "--allow-empty", "-m", "different head")
    git(work, "tag", "origin/main", "HEAD")
    result = preflight(work, work, "feat/fixture", base)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "key",
    ["GIT_CONFIG_GLOBAL", "GIT_EXEC_PATH", "GIT_REPLACE_REF_BASE", "GIT_CONFIG_KEY_0"],
)
def test_preflight_refuses_git_override(
    linked: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch, key: str
) -> None:
    _, work, base = linked
    monkeypatch.setenv(key, "hostile")
    result = preflight(work, work, "feat/fixture", base)
    assert result.returncode != 0
    assert "execution environment override present" in result.stderr
