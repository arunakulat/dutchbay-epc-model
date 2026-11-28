"""Guard installation of the configured pre-commit checks and GOV-02 hook.

The configured set enables black, ruff, isort, file checks and GOV-02's
`no-commit-to-branch` defence. The local mypy hook remains disabled by owner decision
#1270; mandatory local and CI type verification remain in force. These tests do not
claim complete R10 enforcement.

These tests deliberately do NOT assert that a hook is installed on the running host: CI
checks out a fresh clone and correctly has none, and a test that failed there would be
testing the runner rather than the repository. Instead, hook installation lives in the
separately invocable `scripts/install_precommit_hooks.sh` helper, which these tests
execute directly against a throwaway Git repository (`git init`) with a stubbed
interpreter to prove both positive hook creation and hostile failure modes without
mutating any persistent environment.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SETUP_SCRIPT = REPO_ROOT / "setup_venv.sh"
INSTALL_SCRIPT = REPO_ROOT / "scripts" / "install_precommit_hooks.sh"
MAKEFILE = REPO_ROOT / "Makefile"
DEV_DOCS = REPO_ROOT / "docs" / "DEVELOPMENT.md"


def _init_throwaway_repo(tmp_path: Path, name: str = "repo") -> Path:
    """Create a fresh throwaway Git repository for isolated hook tests."""
    repo = tmp_path / name
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", str(repo)],
        check=True,
        capture_output=True,
        text=True,
    )
    return repo


def _make_stub_python(tmp_path: Path, *, exit_code: int = 0) -> tuple[Path, Path, Path]:
    """Create a stub Python interpreter in a spaced path for hook-install tests."""
    venv_dir = tmp_path / "governed venv"
    python = venv_dir / "bin" / "python"
    python.parent.mkdir(parents=True, exist_ok=True)
    args_log = tmp_path / "stub-args.log"
    cwd_log = tmp_path / "stub-cwd.log"
    python.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        'printf \'%s\\n\' "$@" > "$DUTCHBAY_HOOK_ARGS_LOG"\n'
        'pwd > "$DUTCHBAY_HOOK_CWD_LOG"\n'
        f"if [ {exit_code} -ne 0 ]; then\n"
        f"  exit {exit_code}\n"
        "fi\n"
        "mkdir -p .git/hooks\n"
        "printf '#!/usr/bin/env bash\\nexit 0\\n' > .git/hooks/pre-commit\n"
        "chmod +x .git/hooks/pre-commit\n",
        encoding="utf-8",
    )
    python.chmod(0o755)
    return python, args_log, cwd_log


def _run_install_script(
    script_path: Path,
    project_root: Path,
    python_path: Path,
    *,
    args_log: Path | None = None,
    cwd_log: Path | None = None,
    skip_hooks: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Execute the pre-commit hook installer against an isolated target directory."""
    env = os.environ.copy()
    if skip_hooks is None:
        env.pop("DUTCHBAY_SKIP_HOOKS", None)
    else:
        env["DUTCHBAY_SKIP_HOOKS"] = skip_hooks
    if args_log is not None:
        env["DUTCHBAY_HOOK_ARGS_LOG"] = str(args_log)
    if cwd_log is not None:
        env["DUTCHBAY_HOOK_CWD_LOG"] = str(cwd_log)
    return subprocess.run(
        [str(script_path), str(project_root), str(python_path)],
        check=False,
        capture_output=True,
        env=env,
        text=True,
    )


def _assert_install_failure_is_fatal(script_text: str, tmp_path: Path) -> None:
    """Run a candidate installer script against a failing interpreter and assert failure."""
    repo = _init_throwaway_repo(tmp_path, name="fail-repo")
    python, args_log, cwd_log = _make_stub_python(tmp_path, exit_code=1)
    candidate = tmp_path / "candidate_install_precommit_hooks.sh"
    candidate.write_text(script_text, encoding="utf-8")
    candidate.chmod(0o755)

    result = _run_install_script(
        candidate, repo, python, args_log=args_log, cwd_log=cwd_log
    )
    assert result.returncode != 0
    assert "Pre-commit hook installation failed" in result.stderr
    assert not (repo / ".git" / "hooks" / "pre-commit").exists()


def _run_make_hooks(
    makefile: str, tmp_path: Path
) -> tuple[subprocess.CompletedProcess[str], str | None]:
    """Run the hooks recipe through a stub interpreter in a path containing spaces."""
    makefile_path = tmp_path / "Makefile"
    makefile_path.write_text(makefile, encoding="utf-8")
    venv_dir = tmp_path / "governed venv"
    python = venv_dir / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text(
        "#!/usr/bin/env bash\n" 'printf \'%s\\n\' "$@" > "$DUTCHBAY_HOOK_ARGS_LOG"\n',
        encoding="utf-8",
    )
    python.chmod(0o755)
    args_log = tmp_path / "hook-args.log"
    env = os.environ.copy()
    env.update(
        {
            "DUTCHBAY_HOOK_ARGS_LOG": str(args_log),
            "DUTCHBAY_VENV": str(venv_dir),
        }
    )
    result = subprocess.run(
        ["make", "--no-print-directory", "-f", str(makefile_path), "hooks"],
        check=False,
        capture_output=True,
        cwd=REPO_ROOT,
        env=env,
        text=True,
    )
    captured_args = args_log.read_text(encoding="utf-8") if args_log.exists() else None
    return result, captured_args


def test_setup_script_delegates_hook_installation() -> None:
    """Keep hook installation inside the governed setup path via the extracted helper."""
    script = SETUP_SCRIPT.read_text(encoding="utf-8")

    assert '"$PROJECT_ROOT/scripts/install_precommit_hooks.sh"' in script
    assert '"$PROJECT_ROOT" "$VENV_PYTHON"' in script
    assert "#1270" in script
    assert "GOV-02" in script


def test_install_script_contains_required_controls() -> None:
    """Ensure the extracted hook installer preserves all required governance controls."""
    assert INSTALL_SCRIPT.is_file()
    assert os.access(INSTALL_SCRIPT, os.X_OK)
    script = INSTALL_SCRIPT.read_text(encoding="utf-8")

    assert "set -euo pipefail" in script
    assert "-m pre_commit install" in script
    # The owner-decided type-check scope must travel with the step.
    assert "#1270" in script
    assert "GOV-02" in script
    # An opt-out must exist and be named, so a host that cannot install is not stuck.
    assert "DUTCHBAY_SKIP_HOOKS" in script
    # Failure must stop setup rather than merely warn and declare the environment ready.
    assert ") || fail" in script


def test_install_script_installs_hook_in_throwaway_repo(tmp_path: Path) -> None:
    """Execute the real installer against a throwaway git repo and observe the hook."""
    repo = _init_throwaway_repo(tmp_path)
    python, args_log, cwd_log = _make_stub_python(tmp_path, exit_code=0)

    result = _run_install_script(
        INSTALL_SCRIPT, repo, python, args_log=args_log, cwd_log=cwd_log
    )

    assert result.returncode == 0, result.stderr
    assert "Installing configured pre-commit hooks" in result.stdout
    hook_path = repo / ".git" / "hooks" / "pre-commit"
    assert hook_path.is_file()
    assert os.access(hook_path, os.X_OK)
    assert args_log.read_text(encoding="utf-8") == "-m\npre_commit\ninstall\n"
    assert Path(cwd_log.read_text(encoding="utf-8").strip()) == repo.resolve()


def test_install_script_skips_when_dutchbay_skip_hooks_is_set(tmp_path: Path) -> None:
    """Explicit opt-out via DUTCHBAY_SKIP_HOOKS must skip without invoking Python."""
    repo = _init_throwaway_repo(tmp_path)
    python, args_log, cwd_log = _make_stub_python(tmp_path, exit_code=0)

    result = _run_install_script(
        INSTALL_SCRIPT,
        repo,
        python,
        args_log=args_log,
        cwd_log=cwd_log,
        skip_hooks="1",
    )

    assert result.returncode == 0, result.stderr
    assert "Skipping pre-commit hook installation" in result.stdout
    assert not args_log.exists()
    assert not (repo / ".git" / "hooks" / "pre-commit").exists()


def test_install_script_skips_non_git_checkout(tmp_path: Path) -> None:
    """Non-git directories must skip gracefully without invoking pre_commit."""
    non_git = tmp_path / "not-a-git-repo"
    non_git.mkdir()
    python, args_log, cwd_log = _make_stub_python(tmp_path, exit_code=0)

    result = _run_install_script(
        INSTALL_SCRIPT, non_git, python, args_log=args_log, cwd_log=cwd_log
    )

    assert result.returncode == 0, result.stderr
    assert "Not a git checkout; skipping pre-commit hook installation." in result.stdout
    assert not args_log.exists()


def test_install_script_fails_closed_on_missing_arguments() -> None:
    """Invoking the helper without both required arguments must fail closed."""
    result = subprocess.run(
        [str(INSTALL_SCRIPT)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "Usage:" in result.stderr


def test_setup_fails_closed_when_hook_installation_fails(tmp_path: Path) -> None:
    """A failed mandatory hook install must exit non-zero and leave no hook."""
    _assert_install_failure_is_fatal(
        INSTALL_SCRIPT.read_text(encoding="utf-8"), tmp_path
    )


def test_fail_closed_guard_rejects_nonfatal_mutation(tmp_path: Path) -> None:
    """Observe the fatal-install guard fail against the previous warning-only behavior."""
    script = INSTALL_SCRIPT.read_text(encoding="utf-8")
    mutated = script.replace(
        ') || fail \\\n    "Pre-commit hook installation failed;',
        ') || echo \\\n    "Pre-commit hook installation failed;',
        1,
    )
    assert mutated != script
    with pytest.raises(AssertionError):
        _assert_install_failure_is_fatal(mutated, tmp_path)


def test_install_call_sits_inside_the_documented_guard_chain() -> None:
    """Pin the install call's position inside the helper's guard chain."""
    script = INSTALL_SCRIPT.read_text(encoding="utf-8")

    skip_guard = script.index('if [ -n "${DUTCHBAY_SKIP_HOOKS:-}" ]')
    non_git_guard = script.index("rev-parse --git-dir", skip_guard)
    else_branch = script.index("else", non_git_guard)
    install = script.index("-m pre_commit install", else_branch)
    closing_fi = script.index("\nfi", install)

    assert skip_guard < non_git_guard < else_branch < install < closing_fi


def test_makefile_exposes_a_standalone_hooks_target() -> None:
    """An existing checkout must be able to restore hooks without a full reconcile."""
    makefile = MAKEFILE.read_text(encoding="utf-8")

    assert "\nhooks:" in makefile
    assert "pre_commit" in makefile or "pre-commit" in makefile
    phony = next(line for line in makefile.splitlines() if line.startswith(".PHONY:"))
    assert "hooks" in phony.split()


def test_make_hooks_handles_a_governed_venv_path_with_spaces(tmp_path: Path) -> None:
    """Execute the recipe and preserve the spaced interpreter path as one shell word."""
    result, captured_args = _run_make_hooks(
        MAKEFILE.read_text(encoding="utf-8"), tmp_path
    )

    assert result.returncode == 0, result.stderr
    assert captured_args == "-m\npre_commit\ninstall\n"


def test_make_hooks_rejects_unquoted_spaced_path_mutation(tmp_path: Path) -> None:
    """Observe the path oracle fail when the interpreter loses its shell quotes."""
    makefile = MAKEFILE.read_text(encoding="utf-8")
    mutated = makefile.replace('"$(HOOK_PY)"', "$(HOOK_PY)", 1)
    assert mutated != makefile

    result, captured_args = _run_make_hooks(mutated, tmp_path)

    assert result.returncode != 0
    assert captured_args is None


def test_development_docs_point_at_the_governed_path() -> None:
    """Documentation must not describe installation as a purely manual step."""
    docs = " ".join(DEV_DOCS.read_text(encoding="utf-8").split())

    assert "make hooks" in docs
    assert "git does not track" in docs
    assert "#1270" in docs
    assert "does not enable" in docs


@pytest.mark.parametrize(
    ("target", "removed_control", "guard"),
    [
        (
            SETUP_SCRIPT,
            "scripts/install_precommit_hooks.sh",
            test_setup_script_delegates_hook_installation,
        ),
        (
            INSTALL_SCRIPT,
            "-m pre_commit install",
            test_install_script_contains_required_controls,
        ),
        (MAKEFILE, "\nhooks:", test_makefile_exposes_a_standalone_hooks_target),
        (DEV_DOCS, "make hooks", test_development_docs_point_at_the_governed_path),
    ],
)
def test_hook_installation_guards_reject_control_loss(
    monkeypatch: pytest.MonkeyPatch,
    target: Path,
    removed_control: str,
    guard: object,
) -> None:
    """Observe each guard firing on control loss, without changing source files."""
    original_read = Path.read_text

    def altered_read(
        path: Path, encoding: str | None = None, errors: str | None = None
    ) -> str:
        text = original_read(path, encoding=encoding, errors=errors)
        if path == target:
            return text.replace(removed_control, "\nREMOVED_CONTROL:")
        return text

    monkeypatch.setattr(Path, "read_text", altered_read)
    with pytest.raises(AssertionError):
        guard()  # type: ignore[operator]
