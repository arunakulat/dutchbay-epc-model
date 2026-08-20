"""Refusal and interface tests for the two-worktree environment proof."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import verify_shared_venv_worktrees as verifier


def test_verification_paths_require_both_absolute_paths(tmp_path: Path) -> None:
    first = tmp_path / "first"
    first.mkdir()

    with pytest.raises(verifier.WorktreeVerificationError, match="WORKTREE_B"):
        verifier.verification_paths({"DUTCHBAY_WORKTREE_A": str(first)})

    with pytest.raises(verifier.WorktreeVerificationError, match="absolute"):
        verifier.verification_paths(
            {
                "DUTCHBAY_WORKTREE_A": "relative/first",
                "DUTCHBAY_WORKTREE_B": str(first),
            }
        )


def test_verification_paths_refuse_duplicates(tmp_path: Path) -> None:
    worktree = tmp_path / "worktree"
    worktree.mkdir()

    with pytest.raises(verifier.WorktreeVerificationError, match="distinct"):
        verifier.verification_paths(
            {
                "DUTCHBAY_WORKTREE_A": str(worktree),
                "DUTCHBAY_WORKTREE_B": str(worktree),
            }
        )


def test_verification_paths_refuse_symlink_substitution(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    alias = tmp_path / "alias"
    first.mkdir()
    second.mkdir()
    alias.symlink_to(first, target_is_directory=True)

    with pytest.raises(verifier.WorktreeVerificationError, match="symlink"):
        verifier.verification_paths(
            {
                "DUTCHBAY_WORKTREE_A": str(alias),
                "DUTCHBAY_WORKTREE_B": str(second),
            }
        )


def test_verify_requires_an_explicit_shared_environment() -> None:
    with pytest.raises(verifier.WorktreeVerificationError, match="DUTCHBAY_VENV"):
        verifier.verify({})


def test_cli_rejects_positional_path_configuration(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert verifier.main(["/tmp/a", "/tmp/b"]) == 2
    failure = json.loads(capsys.readouterr().err)

    assert failure["status"] == "FAIL"
    assert "environment variables only" in failure["error"]


def test_verifier_keeps_proof_bounded_and_fail_closed() -> None:
    script = Path(verifier.__file__).read_text(encoding="utf-8")

    for required in (
        '"--git-common-dir"',
        '"--porcelain=v1"',
        'worktree / ".venv"',
        '"dutchbay_environment.py"',
        '"dutchbay_bootstrap_rules.py"',
        '"pytest"',
        '"PYTHONPATH": str(worktree)',
        '"foreign_checkout_paths"',
    ):
        assert required in script
