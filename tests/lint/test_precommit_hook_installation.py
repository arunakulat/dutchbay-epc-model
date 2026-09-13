"""Guard that governed setup installs the pre-commit hooks R10 and GOV-02 rely on.

`R10` states that hooks "run automatically on git commit" and that "failed hooks prevent
commit". `GOV-02` relies on the same hook set for its first line of defence, blocking a
commit on `main` locally before the confusing push-time ruleset rejection. Hooks live in
`.git/hooks`, which git does not track, so both claims are silently false in any checkout
where nobody ran the install -- as was observed in this repository on 2026-09-13.

These tests deliberately do NOT assert that a hook is installed on the running host: CI
checks out a fresh clone and correctly has none, and a test that failed there would be
testing the runner rather than the repository. What is checkable, and what these pin, is
that the governed setup path still performs the installation.

LIMIT, declared rather than left silent (`VERIFY-01`): these are text assertions. They
prove the install call is PRESENT and sits inside the expected guard chain. They cannot
prove it is REACHABLE. A reviewer demonstrated the gap concretely by wrapping the call in
an `if false` branch, after which every assertion here still passed. Closing it properly
means extracting the block into a separately invocable script that a test can run against
a throwaway repository and observe a hook appear; that is tracked as follow-up work and is
deliberately not attempted here. Until then, treat a green run as evidence the call has
not been deleted or reworded, never as evidence it executes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SETUP_SCRIPT = REPO_ROOT / "setup_venv.sh"
MAKEFILE = REPO_ROOT / "Makefile"
DEV_DOCS = REPO_ROOT / "docs" / "DEVELOPMENT.md"


def test_setup_script_installs_the_precommit_hooks() -> None:
    """Keep hook installation inside the governed setup path, not a manual doc step."""
    script = SETUP_SCRIPT.read_text(encoding="utf-8")

    assert "-m pre_commit install" in script
    # The reason must travel with the step, or a later tidy-up removes it as noise.
    assert "R10" in script
    assert "GOV-02" in script
    # An opt-out must exist and be named, so a host that cannot install is not stuck.
    assert "DUTCHBAY_SKIP_HOOKS" in script
    # Failure must be announced rather than swallowed.
    assert "is NOT active" in script


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


def test_development_docs_point_at_the_governed_path() -> None:
    """Documentation must not describe installation as a purely manual step."""
    docs = DEV_DOCS.read_text(encoding="utf-8")

    assert "make hooks" in docs
    assert "git does not track" in docs


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
