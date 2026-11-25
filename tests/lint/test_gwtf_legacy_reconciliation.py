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


def test_r10_local_hooks_and_ci_type_gates_remain_bound() -> None:
    with (ROOT / "go_with_the_flow_rules_v3_0_clean.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
        rules = {r["rule_id"]: r for r in rows}
    assert len(rules) == len(rows), "duplicate rule identity"
    assert set(("R10", "R23", "R21", "CLEANUP-01")) <= rules.keys()
    assert all(
        rules[key]["status"] == "active" for key in ("R10", "R23", "R21", "CLEANUP-01")
    )
    policy = rules["R10"]["description"] + rules["R10"]["enforcement"]
    config = yaml.safe_load((ROOT / ".pre-commit-config.yaml").read_text())
    hooks = {hook["id"] for repo in config["repos"] for hook in repo["hooks"]}
    assert {
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
    } <= hooks
    assert "mypy" not in hooks
    for control in (
        "#1270",
        "#1262",
        "mandatory local type verification",
        "test-suite.yml",
        "ci_v14_fastlane.yml",
        "fx-tests.yml",
        "regression-smoke.yml",
    ):
        assert control in policy
    for workflow in (
        "test-suite.yml",
        "ci_v14_fastlane.yml",
        "fx-tests.yml",
        "regression-smoke.yml",
    ):
        assert "mypy" in (ROOT / ".github/workflows" / workflow).read_text()
    assert (
        "mypy scripts/ --ignore-missing-imports"
        in (ROOT / ".github/workflows/test-suite.yml").read_text()
    )
    assert "full suite before pushing" in rules["R23"]["description"]
    assert "CLEANUP-01" in rules["R23"]["description"]


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
