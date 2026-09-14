"""Guard installation of the configured pre-commit checks and GOV-02 hook.

The configured set enables black, ruff, isort, file checks and GOV-02's
`no-commit-to-branch` defence. R10 also names mypy, but that hook is currently disabled;
#1270 tracks the contract/configuration mismatch. These tests do not claim complete R10
enforcement.

These tests deliberately do NOT assert that a hook is installed on the running host: CI
checks out a fresh clone and correctly has none, and a test that failed there would be
testing the runner rather than the repository. What is checkable, and what these pin, is
that the governed setup path still performs the installation.

LIMIT, declared rather than left silent (`VERIFY-01`): these are text assertions. They
prove the install call is PRESENT and sits inside the expected guard chain. They cannot
prove it is REACHABLE. A reviewer demonstrated the gap concretely by wrapping the call in
an `if false` branch, after which every assertion here still passed. Closing it properly
means extracting the block into a separately invocable script that a test can run against
a throwaway repository and observe a hook appear; #1262 tracks that work. Until then,
treat a green run as evidence the call has not been deleted or reworded, never as evidence
the complete setup path executes.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SETUP_SCRIPT = REPO_ROOT / "setup_venv.sh"
MAKEFILE = REPO_ROOT / "Makefile"
DEV_DOCS = REPO_ROOT / "docs" / "DEVELOPMENT.md"
HOOK_BLOCK_MARKER = "# Install the configured pre-commit hook set"


def _run_hook_setup_tail(
    script: str, tmp_path: Path
) -> subprocess.CompletedProcess[str]:
    """Execute the exact hook-installation tail with a deliberately failing installer."""
    start = script.index(HOOK_BLOCK_MARKER)
    probe = tmp_path / "hook-install-probe.sh"
    probe.write_text(
        "set -euo pipefail\n"
        'fail() { echo "ERROR: $*" >&2; exit 1; }\n' + script[start:],
        encoding="utf-8",
    )
    env = os.environ.copy()
    env.update(
        {
            "PROJECT_ROOT": str(REPO_ROOT),
            "VENV_DIR": "/tmp/nonexistent-governed-venv",
            "VENV_PYTHON": "/bin/false",
        }
    )
    env.pop("DUTCHBAY_SKIP_HOOKS", None)
    return subprocess.run(
        ["bash", str(probe)],
        check=False,
        capture_output=True,
        env=env,
        text=True,
    )


def _assert_install_failure_is_fatal(script: str, tmp_path: Path) -> None:
    result = _run_hook_setup_tail(script, tmp_path)
    assert result.returncode != 0
    assert "Pre-commit hook installation failed" in result.stderr
    assert "Environment ready" not in result.stdout


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


def test_setup_script_installs_the_precommit_hooks() -> None:
    """Keep hook installation inside the governed setup path, not a manual doc step."""
    script = SETUP_SCRIPT.read_text(encoding="utf-8")

    assert "-m pre_commit install" in script
    # The scope and unresolved contract mismatch must travel with the step.
    assert "#1270" in script
    assert "GOV-02" in script
    # An opt-out must exist and be named, so a host that cannot install is not stuck.
    assert "DUTCHBAY_SKIP_HOOKS" in script
    # Failure must stop setup rather than merely warn and declare the environment ready.
    assert ") || fail" in script


def test_setup_fails_closed_when_hook_installation_fails(tmp_path: Path) -> None:
    """A failed mandatory hook install must prevent the final ready declaration."""
    _assert_install_failure_is_fatal(SETUP_SCRIPT.read_text(encoding="utf-8"), tmp_path)


def test_fail_closed_guard_rejects_nonfatal_mutation(tmp_path: Path) -> None:
    """Observe the fatal-install guard fail against the previous warning-only behavior."""
    script = SETUP_SCRIPT.read_text(encoding="utf-8")
    mutated = script.replace(
        ') || fail \\\n    "Pre-commit hook installation failed;',
        ') || echo \\\n    "Pre-commit hook installation failed;',
        1,
    )
    assert mutated != script
    with pytest.raises(AssertionError):
        _assert_install_failure_is_fatal(mutated, tmp_path)


def test_install_call_sits_inside_the_documented_guard_chain() -> None:
    """Pin the install call's position, not merely its presence.

    Presence alone is satisfied by a call anywhere in the file, including one a refactor
    has stranded. This asserts the documented shape -- skip-guard, then non-git guard,
    then the install in the `else` -- so moving the call out of that chain fails loudly.
    See the LIMIT in this module's docstring: position is checkable, reachability is not.
    """
    script = SETUP_SCRIPT.read_text(encoding="utf-8")

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
    docs = DEV_DOCS.read_text(encoding="utf-8")

    assert "make hooks" in docs
    assert "git does not track" in docs
    assert "#1270" in docs
    assert "does not enable" in docs


@pytest.mark.parametrize(
    ("target", "removed_control", "guard"),
    [
        (
            SETUP_SCRIPT,
            "-m pre_commit install",
            test_setup_script_installs_the_precommit_hooks,
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
