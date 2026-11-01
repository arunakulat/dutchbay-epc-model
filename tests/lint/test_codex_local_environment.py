"""Regression guards for the Codex desktop local environment."""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROJECT_CONFIG = ROOT / ".codex" / "config.toml"
ENVIRONMENT_FILE = ROOT / ".codex" / "environments" / "environment.toml"
ENVRC = ROOT / ".envrc"
SETUP_SCRIPT = ROOT / "setup_venv.sh"
SESSION_HOOK = ROOT / ".claude" / "hooks" / "session-start.sh"
SOURCED_SETUP_SCRIPT = ROOT / "scripts" / "venv_up.sh"
SHELL_ENVIRONMENT_HELPER = ROOT / "scripts" / "development_environment.sh"
VENV_CHECK_SCRIPT = ROOT / "check_venv.sh"
BOOTSTRAP_HELPER = ROOT / "dutchbay_bootstrap.py"
DOCKERFILE = ROOT / "Dockerfile"
MAKEFILE = ROOT / "Makefile"


def _environment() -> dict[str, object]:
    """Load the Codex-generated project environment configuration."""

    with ENVIRONMENT_FILE.open("rb") as stream:
        return tomllib.load(stream)


def test_codex_project_config_tracks_the_recorded_defaults() -> None:
    """Pin the project defaults Codex applies to every trusted checkout.

    These settings let a local Codex task run without approval prompts and outside
    the sandbox, so a change to them is an agent-permission change and must arrive
    as a reviewed diff. The digest is the one H02, H05, H06 and H08 recorded for the
    copy that sat untracked in the primary checkout, so tracking the file moved its
    bytes into review without changing them.
    """

    with PROJECT_CONFIG.open("rb") as stream:
        config = tomllib.load(stream)

    assert config == {
        "approval_policy": "never",
        "sandbox_mode": "danger-full-access",
        "model_verbosity": "medium",
        "model_reasoning_summary": "concise",
    }
    assert (
        hashlib.sha256(PROJECT_CONFIG.read_bytes()).hexdigest()
        == "42dac680fc1f9e47c5cbc864ca50984445019be946ac09b470981fd25bd2969d"
    )


def test_codex_environment_uses_supported_location_and_version() -> None:
    """Keep the environment discoverable by Codex desktop worktrees."""

    environment = _environment()

    assert environment["version"] == 1
    assert environment["name"] == "DutchBay EPC"


def test_codex_environment_uses_the_persistent_project_venv() -> None:
    """Fresh Codex tasks must verify and use the durable project environment."""

    environment = _environment()
    setup = environment["setup"]

    assert isinstance(setup, dict)
    script = setup["script"]
    assert "/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv" in script
    assert 'export DUTCHBAY_VENV="' in script
    assert "dutchbay_environment.py" in script
    assert 'export PYTHONPATH="$PWD' in script
    assert "./setup_venv.sh" not in script


def test_bootstrap_prefers_the_supported_ci_python() -> None:
    """Require the tested 3.12 minor instead of silently selecting a newer Python."""

    for path in (
        SETUP_SCRIPT,
        SESSION_HOOK,
        SHELL_ENVIRONMENT_HELPER,
    ):
        script = path.read_text(encoding="utf-8")

        assert "sys.version_info[:2] != (3, 12)" in script

    script = SHELL_ENVIRONMENT_HELPER.read_text(encoding="utf-8")
    assert (
        "for candidate in python3.12 /opt/homebrew/bin/python3.12 python3 python"
        in script
    )
    assert "Python 3.12 interpreter was not found" in SETUP_SCRIPT.read_text(
        encoding="utf-8"
    )

    for path in (SETUP_SCRIPT, SOURCED_SETUP_SCRIPT, VENV_CHECK_SCRIPT):
        script = path.read_text(encoding="utf-8")
        assert "development_environment.sh" in script
        assert "dutchbay_resolve_venv" in script
        assert "dutchbay_validate_venv" in script


def test_local_setup_reuses_the_shared_contract_without_path_laundering() -> None:
    """Provision dependencies without binding a shared venv to one checkout."""

    setup = SETUP_SCRIPT.read_text(encoding="utf-8")
    activation = SOURCED_SETUP_SCRIPT.read_text(encoding="utf-8")
    helper = SHELL_ENVIRONMENT_HELPER.read_text(encoding="utf-8")
    makefile = MAKEFILE.read_text(encoding="utf-8")

    assert '"$VENV_PYTHON" -m pip install --quiet -r "$REQUIREMENTS"' in setup
    assert "pip install -e" not in setup
    assert 'VENV_DIR=$(dutchbay_resolve_venv "$PROJECT_ROOT" "$PYTHON_CMD")' in setup
    assert 'mkdir -p "$(dirname "$VENV_DIR")"' in setup
    assert '"$PYTHON_CMD" -m venv "$VENV_DIR"' in setup
    assert 'VENV_DIR="$PROJECT_ROOT/.venv"' not in setup
    assert "pip install" not in activation
    assert "cp " not in activation
    assert 'export PYTHONPATH="$repo_root${PYTHONPATH:+:$PYTHONPATH}"' in helper
    assert "go_with_the_flow_rules_v3_0_clean.csv" in helper
    assert "setup:\n\t./setup_venv.sh" in makefile


def test_local_setup_reconciles_an_existing_environment_with_the_lock() -> None:
    """R21 step (2) is "create or reconcile"; validation alone is not reconciliation.

    Observed 2026-09-14: weasyprint stayed at 69.0 in the governed environment for
    a day after #1256 raised the pin to 70.0 for PYSEC-2026-3940, because the
    existing-environment branch validated "without modifying it" and the health
    contract only checks that the governed distributions are PRESENT, not that
    they match the lock. ./setup_venv.sh printed "Environment ready" and exited 0
    while tests/integration/test_report_jobs_tooling.py failed on the stale pin --
    so the one command R21 names as the repair path could not perform the repair,
    and two further packages (scipy-stubs, websocket-client) had drifted unnoticed
    because no test asserted their versions at all.
    """

    setup = SETUP_SCRIPT.read_text(encoding="utf-8")
    install = '-m pip install --quiet -r "$REQUIREMENTS"'

    existing_branch, separator, created_branch = setup.partition("\nelse\n")
    assert separator, "setup_venv.sh no longer branches on an existing environment"

    # Both paths must land the committed lock, not just the freshly-created one.
    assert install in existing_branch
    assert install in created_branch

    # The reconcile must precede the health check, or a drifted environment is
    # still judged on its pre-reconcile state.
    assert existing_branch.index(install) < existing_branch.index(
        "dutchbay_validate_venv"
    )


def test_envrc_activation_reuses_the_shared_contract_without_provisioning() -> None:
    """Entering the checkout must not select or build an ungoverned environment."""

    envrc = ENVRC.read_text(encoding="utf-8")

    assert "development_environment.sh" in envrc
    for helper in (
        "dutchbay_find_python312",
        "dutchbay_resolve_venv",
        "dutchbay_validate_venv",
        "dutchbay_activate_checkout",
    ):
        assert helper in envrc
    for prohibited in (".venv311", "~/.venvs", "./setup_venv.sh", "pip install"):
        assert prohibited not in envrc


def _run_venv_lock(
    selected: str, locked: str | None
) -> subprocess.CompletedProcess[str]:
    """Call the portable shell lock with an isolated environment."""

    environ = dict(os.environ)
    if locked is None:
        environ.pop("DUTCHBAY_VENV_LOCK", None)
    else:
        environ["DUTCHBAY_VENV_LOCK"] = locked
    return subprocess.run(
        [
            "bash",
            "-c",
            '. "$1"; dutchbay_require_venv_lock "$2"',
            "venv-lock-probe",
            str(SHELL_ENVIRONMENT_HELPER),
            selected,
        ],
        capture_output=True,
        text=True,
        check=False,
        env=environ,
    )


def test_interactive_activation_lock_is_fail_closed_and_portable() -> None:
    """Reject local-path drift while preserving unconfigured-host portability."""

    expected = "/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv"
    assert _run_venv_lock(expected, expected).returncode == 0
    assert _run_venv_lock(expected, None).returncode == 0

    relative = _run_venv_lock(expected, "relative/.venv")
    assert relative.returncode != 0
    assert "must be an absolute path" in relative.stderr

    mismatch = _run_venv_lock("/tmp/other-venv", expected)
    assert mismatch.returncode != 0
    assert "/tmp/other-venv" in mismatch.stderr
    assert expected in mismatch.stderr

    activation = SOURCED_SETUP_SCRIPT.read_text(encoding="utf-8")
    assert 'dutchbay_require_venv_lock "$_DUTCHBAY_VENV"' in activation


def _emitted_path_line() -> str:
    """The PATH export the hook appends to CLAUDE_ENV_FILE, with a venv substituted."""

    hook = SESSION_HOOK.read_text(encoding="utf-8")
    match = re.search(
        r"printf '(case \":\$PATH:\".*?esac)\\n' \"\$VENV\" \"\$VENV\"", hook
    )
    assert match is not None, "the hook no longer emits a recognisable PATH export"
    return match.group(1).replace("%s", "/tmp/probe-venv")


def _path_after_sourcing(line: str, times: int) -> str:
    """Source `line` `times` times in one shell and return the resulting PATH."""

    script = (
        "export PATH=/usr/bin:/bin\n" + (line + "\n") * times + 'printf "%s" "$PATH"'
    )
    return subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, check=True
    ).stdout


def test_session_hook_path_export_is_idempotent() -> None:
    """Re-sourcing the env file must not grow PATH by one entry per session.

    CLAUDE_ENV_FILE is APPENDED to on every session start and re-sourced by every
    shell, so an unconditional prepend accumulates a duplicate per resume. PATH was
    observed carrying 18 copies of .venv/bin (32 entries, 15 unique) before the
    guard. Harmless -- first match wins -- but unbounded, and the hook is documented
    as idempotent.
    """

    line = _emitted_path_line()
    entries = _path_after_sourcing(line, 5).split(":")

    assert entries.count("/tmp/probe-venv/bin") == 1


def test_session_hook_path_export_still_prepends_when_absent() -> None:
    """The negative control: a guard that never fires would also look idempotent.

    Without this, `case ... esac` collapsing to a no-op would pass the test above
    while silently breaking the resolution the export exists to provide -- every
    tool would fall back to whatever the image ships rather than the pinned venv.
    """

    line = _emitted_path_line()
    entries = _path_after_sourcing(line, 1).split(":")

    assert entries[0] == "/tmp/probe-venv/bin"

    # And the unguarded form it replaced must genuinely accumulate, or this whole
    # guard is defending against nothing.
    unguarded = 'export PATH="/tmp/probe-venv/bin:$PATH"'
    assert (
        _path_after_sourcing(unguarded, 5).split(":").count("/tmp/probe-venv/bin") == 5
    )


def test_bootstrap_rejects_the_retired_python311_venv_name() -> None:
    """Do not let a retired .venv311 tree satisfy the active bootstrap."""

    script = BOOTSTRAP_HELPER.read_text(encoding="utf-8")

    assert 'REPO_ROOT / ".venv"' in script
    assert ".venv311" not in script


def test_container_uses_the_supported_python312_image() -> None:
    """Keep both Docker stages aligned with the repository Python floor."""

    dockerfile = DOCKERFILE.read_text(encoding="utf-8")

    assert dockerfile.count("FROM python:3.12-slim-bookworm") == 2
    assert "python:3.11" not in dockerfile
    assert "cp311" not in dockerfile


def test_codex_environment_exposes_safe_project_actions() -> None:
    """Actions should use the persistent project venv and current checkout imports."""

    environment = _environment()
    actions = environment["actions"]

    assert isinstance(actions, list)
    by_name = {action["name"]: action for action in actions}
    assert set(by_name) == {"Fast validation", "Full tests", "Run API"}
    assert all(
        "/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv" in action["command"]
        for action in actions
    )
    assert all("PYTHONPATH" in action["command"] for action in actions)
    assert all("DUTCHBAY_VENV" in action["command"] for action in actions)
    assert all("dutchbay_environment.py" in action["command"] for action in actions)
    assert all(action["command"].lstrip().startswith("set -e") for action in actions)
    assert "--reload" in by_name["Run API"]["command"]
    assert "app.api.main:app" in by_name["Run API"]["command"]


def _emitted_checkout_pth_lines() -> str:
    """The two lines the hook uses to write the checkout ``.pth``, as a snippet."""

    hook = SESSION_HOOK.read_text(encoding="utf-8")
    match = re.search(
        r"^(CHECKOUT_PTH=.*\nprintf '%s\\n' \"\$REPO\" > \"\$CHECKOUT_PTH\")$",
        hook,
        re.MULTILINE,
    )
    assert match is not None, "the hook no longer writes a recognisable checkout .pth"
    return match.group(1)


def test_session_hook_writes_the_checkout_pth_outside_the_env_file_guard() -> None:
    """A hand-run hook must still make the checkout importable.

    The env-file block cannot do this job at all: a hook is a subprocess and cannot
    export into the shell that started it, and the manual invocation documented in
    CLAUDE.md sets no CLAUDE_ENV_FILE, so anything inside that guard is skipped
    entirely. Placement is the whole fix, which is why it is asserted rather than
    assumed.
    """

    hook = SESSION_HOOK.read_text(encoding="utf-8")

    assert hook.index("CHECKOUT_PTH=") < hook.index('if [ -n "${CLAUDE_ENV_FILE:-}" ]')


def test_session_hook_checkout_pth_is_one_line_and_rewritten(tmp_path: Path) -> None:
    """Running the hook twice must leave one path, not two.

    The appended PATH export next to this one accumulated a duplicate per session
    until it was guarded, so the same hazard is checked here by running the real
    snippet twice against a real venv rather than by reading the redirection
    operator and trusting it.
    """

    import venv

    venv_dir = tmp_path / "venv"
    venv.create(venv_dir, with_pip=False)
    repo = tmp_path / "checkout"
    repo.mkdir()
    snippet = _emitted_checkout_pth_lines()
    script = f'PY="{venv_dir}/bin/python"\nREPO="{repo}"\n{snippet}\n'

    for _ in range(2):
        subprocess.run(["bash", "-euo", "pipefail", "-c", script], check=True)

    written = sorted(venv_dir.rglob("dutchbay-checkout.pth"))
    assert len(written) == 1
    assert written[0].read_text(encoding="utf-8").splitlines() == [str(repo)]


def test_session_hook_checkout_pth_lands_in_the_venv_not_the_checkout(
    tmp_path: Path,
) -> None:
    """The negative control on *where* it lands.

    A ``.pth`` written into the checkout does nothing — only ``site-packages`` is
    scanned at startup — and a path computed from the interpreter running the hook
    rather than from ``$PY`` would land in whichever environment launched it. Both
    mistakes would leave the test above green if it only checked the contents.

    The destination is asserted against the venv this test created, never against
    this runner's own ``site-packages``: in a container the hook has legitimately
    written that file there, so an assertion about it would pass or fail on how the
    machine was provisioned rather than on the hook.
    """

    import venv

    venv_dir = tmp_path / "venv"
    venv.create(venv_dir, with_pip=False)
    repo = tmp_path / "checkout"
    repo.mkdir()
    script = (
        f'PY="{venv_dir}/bin/python"\nREPO="{repo}"\n{_emitted_checkout_pth_lines()}\n'
    )

    subprocess.run(["bash", "-euo", "pipefail", "-c", script], check=True)

    written = sorted(venv_dir.rglob("dutchbay-checkout.pth"))
    assert len(written) == 1
    assert written[0].parent.name == "site-packages"
    assert written[0].is_relative_to(venv_dir)
    assert not (repo / "dutchbay-checkout.pth").exists()
    assert '"$PY" -c' in _emitted_checkout_pth_lines()


def _hook_line(prefix: str) -> str:
    """The hook's own line beginning *prefix*, so no test restates its wording."""

    hook = SESSION_HOOK.read_text(encoding="utf-8")
    matches = [
        line.strip() for line in hook.splitlines() if line.strip().startswith(prefix)
    ]
    assert len(matches) == 1, f"expected exactly one hook line starting {prefix!r}"
    return matches[0]


def _cached_start_region() -> str:
    """The hook's real bytes from the stamp decision through the ``.pth`` write."""

    hook = SESSION_HOOK.read_text(encoding="utf-8")
    start = hook.index(_hook_line("STAMP_VALUE="))
    tail = 'printf \'%s\\n\' "$REPO" > "$CHECKOUT_PTH"'
    assert hook.count(tail) == 1, "the hook no longer writes the checkout .pth once"
    end = hook.index(tail) + len(tail)
    assert start < end, "the .pth write now precedes the stamp decision"
    return hook[start:end]


def test_session_hook_writes_the_checkout_pth_on_a_cached_start(
    tmp_path: Path,
) -> None:
    """The write must be unconditional, not merely above the env-file guard.

    Most sessions are *warm*: the manifest stamp matches, the install branch is
    skipped entirely, and only the unconditional statements run. Asserting that the
    write appears before the ``CLAUDE_ENV_FILE`` guard does not establish that,
    because the whole install branch also lies above that guard -- move the write
    into it and every other test here still passes while a warm start writes
    nothing and imports fail from any directory but the checkout root (assurance
    C-1 on #1393).

    So this runs the hook's real bytes, from the stamp decision through the write,
    against a seeded stamp, and requires both that the cached branch was taken and
    that the file exists afterwards. The stamp is seeded with the hook's own two
    lines, so the stamp's format lives in one place.
    """

    import venv

    venv_dir = tmp_path / "venv"
    venv.create(venv_dir, with_pip=False)
    repo = tmp_path / "checkout"
    repo.mkdir()
    prelude = (
        "manifest_hash() { echo stub-manifest; }\n"
        f'PY="{venv_dir}/bin/python"\n'
        f'REPO="{repo}"\n'
        f'VENV="{venv_dir}"\n'
        f'STAMP="{venv_dir}/.session-start-stamp"\n'
        'DUTCHBAY_EXTRAS="dev"\n'
    )
    stamp_value_line = _hook_line("STAMP_VALUE=")
    stamp_write_line = _hook_line("printf '%s' ")
    seed = f"{prelude}{stamp_value_line}\n{stamp_write_line}\n"
    subprocess.run(["bash", "-euo", "pipefail", "-c", seed], check=True)

    completed = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", f"{prelude}{_cached_start_region()}"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "skipping install" in completed.stdout, (
        "the cached branch was not taken, so this run proves nothing about a warm "
        f"start: {completed.stdout!r}"
    )
    written = sorted(venv_dir.rglob("dutchbay-checkout.pth"))
    assert len(written) == 1
    assert written[0].read_text(encoding="utf-8").splitlines() == [str(repo)]
