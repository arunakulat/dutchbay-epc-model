"""Regression guards for the Codex desktop local environment."""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PROJECT_CONFIG = ROOT / ".codex" / "config.toml"
ENVIRONMENT_FILE = ROOT / ".codex" / "environments" / "environment.toml"
ENVRC = ROOT / ".envrc"
SETUP_SCRIPT = ROOT / "setup_venv.sh"
SESSION_HOOK = ROOT / ".claude" / "hooks" / "session-start.sh"
CODEX_SESSION_HOOK = ROOT / ".codex" / "hooks" / "session-start.sh"
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
    as a reviewed diff. H02, H05, H06 and H08 recorded the earlier config before
    the shell environment policy was added. The digest below pins this reviewed
    configuration, including that policy, rather than the historical bytes.
    """

    with PROJECT_CONFIG.open("rb") as stream:
        config = tomllib.load(stream)

    assert config == {
        "approval_policy": "never",
        "sandbox_mode": "danger-full-access",
        "model_verbosity": "medium",
        "model_reasoning_summary": "concise",
        "shell_environment_policy": {
            "inherit": "core",
            "set": {
                "DUTCHBAY_EXTRAS": "dev,feasibility,jobs,solar,pareto",
            },
        },
    }
    assert (
        hashlib.sha256(PROJECT_CONFIG.read_bytes()).hexdigest()
        == "50969ca101a1d4f5a8315ee3bc38c078461d651e3e5240294290c05090a44ad1"
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
        CODEX_SESSION_HOOK,
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


def _extract_venv_provisioning_branches(script: str) -> tuple[str, str]:
    """Extract (existing_branch, created_branch) from setup_venv.sh.

    Bounds the venv-existence conditional by tracking bash if/fi nesting
    so nested conditionals or subsequent blocks (such as pre-commit hooks)
    do not leak into or truncate the isolated branches (#1265).
    """
    marker = 'if [ -e "$VENV_DIR" ]; then'
    start_idx = script.find(marker)
    if start_idx == -1:
        raise ValueError(f"setup script missing conditional: {marker!r}")

    lines = script[start_idx + len(marker) :].splitlines(keepends=True)
    depth = 0
    existing_lines: list[str] = []
    created_lines: list[str] = []
    found_else = False
    found_fi = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            if not found_else:
                existing_lines.append(line)
            else:
                created_lines.append(line)
            continue

        if re.match(r"^if\b", stripped):
            depth += 1
        elif stripped == "fi":
            if depth > 0:
                depth -= 1
            else:
                found_fi = True
                break
        elif stripped == "else" and depth == 0:
            if found_else:
                raise ValueError(
                    "duplicate top-level 'else' in venv provisioning conditional"
                )
            found_else = True
            continue

        if not found_else:
            existing_lines.append(line)
        else:
            created_lines.append(line)

    if not found_else:
        raise ValueError(
            "setup script missing outer 'else' in venv provisioning conditional"
        )
    if not found_fi:
        raise ValueError(
            "setup script missing outer 'fi' in venv provisioning conditional"
        )

    return "".join(existing_lines), "".join(created_lines)


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

    existing_branch, created_branch = _extract_venv_provisioning_branches(setup)

    # Both paths must land the committed lock, not just the freshly-created one.
    assert install in existing_branch
    assert install in created_branch

    # created_branch must be bounded to the provisioning block, not absorbing downstream steps (#1265)
    assert "-m pre_commit install" not in created_branch
    assert "Environment ready" not in created_branch

    # The reconcile must precede the health check, or a drifted environment is
    # still judged on its pre-reconcile state.
    assert existing_branch.index(install) < existing_branch.index(
        "dutchbay_validate_venv"
    )


def test_venv_provisioning_branches_negative_controls() -> None:
    """Negative controls for venv provisioning branch isolation (#1265, VERIFY-01).

    Proves the extractor rejects malformed scripts, ignores nested and downstream
    else/fi tokens, and proves the guard assertions fail when either branch is mutated.
    """
    setup = SETUP_SCRIPT.read_text(encoding="utf-8")
    install = '-m pip install --quiet -r "$REQUIREMENTS"'
    existing_branch, created_branch = _extract_venv_provisioning_branches(setup)

    # 1. Missing outer conditional
    with pytest.raises(ValueError, match="missing conditional"):
        _extract_venv_provisioning_branches("echo hello\n")

    # 2. Missing outer else
    broken_no_else = setup.replace("\nelse\n", "\n# no else\n", 1)
    with pytest.raises(ValueError, match="missing outer 'else'"):
        _extract_venv_provisioning_branches(broken_no_else)

    # 3. Missing outer fi
    broken_no_fi = setup.replace("\nfi\n", "\n# no fi\n", 1)
    with pytest.raises(ValueError, match="missing outer 'fi'"):
        _extract_venv_provisioning_branches(broken_no_fi)

    # 4. Mutation negative control: removing install from existing branch fails assertion
    mutated_existing = existing_branch.replace(install, "# omitted install")
    with pytest.raises(AssertionError):
        assert install in mutated_existing

    # 5. Mutation negative control: removing install from created branch fails assertion
    mutated_created = created_branch.replace(install, "# omitted install")
    with pytest.raises(AssertionError):
        assert install in mutated_created

    # 6. Mutation negative control: reversing reconcile and validation order fails assertion
    reconcile_idx = existing_branch.index(install)
    validate_idx = existing_branch.index("dutchbay_validate_venv")
    assert reconcile_idx < validate_idx
    with pytest.raises(AssertionError):
        assert validate_idx < reconcile_idx

    # 7. Immunity to nested else inside existing branch
    nested_else_script = setup.replace(
        'if [ -L "$VENV_DIR" ] || [ ! -d "$VENV_DIR" ]; then',
        'if [ -L "$VENV_DIR" ] || [ ! -d "$VENV_DIR" ]; then\n'
        '    echo "symlink"\n'
        "  else\n"
        '    echo "real"',
    )
    ex_nested, cr_nested = _extract_venv_provisioning_branches(nested_else_script)
    assert install in ex_nested
    assert install in cr_nested
    assert "-m pre_commit install" not in cr_nested
    assert "Environment ready" not in cr_nested


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


def _emitted_pythonpath_line() -> str:
    """The PYTHONPATH export the hook appends to CLAUDE_ENV_FILE, with a repo substituted."""

    hook = SESSION_HOOK.read_text(encoding="utf-8")
    match = re.search(
        r"printf '(case \":\$\{PYTHONPATH:-\}:\".*?esac)\\n' \"\$REPO\" \"\$REPO\"",
        hook,
    )
    assert (
        match is not None
    ), "the hook no longer emits a recognisable PYTHONPATH export"
    return match.group(1).replace("%s", "/tmp/probe-repo")


def _pythonpath_after_sourcing(
    line: str, times: int, *, initial: str | None = None
) -> str:
    """Source *line* *times* times in one shell and return the resulting PYTHONPATH."""

    setup = (
        "unset PYTHONPATH\n" if initial is None else f'export PYTHONPATH="{initial}"\n'
    )
    script = setup + (line + "\n") * times + 'printf "%s" "${PYTHONPATH:-}"'
    return subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, check=True
    ).stdout


def test_session_hook_pythonpath_export_is_idempotent() -> None:
    """Re-sourcing the env file must not accumulate duplicate PYTHONPATH entries (#1417)."""

    line = _emitted_pythonpath_line()

    from_unset = _pythonpath_after_sourcing(line, 5, initial=None)
    assert from_unset == "/tmp/probe-repo"
    assert from_unset.split(":").count("/tmp/probe-repo") == 1

    from_existing = _pythonpath_after_sourcing(line, 5, initial="/tmp/existing")
    assert from_existing == "/tmp/probe-repo:/tmp/existing"
    assert from_existing.split(":").count("/tmp/probe-repo") == 1


def test_session_hook_pythonpath_export_still_prepends_when_absent() -> None:
    """Negative control (#1417): a no-op guard would look idempotent but drop the repo."""

    line = _emitted_pythonpath_line()

    assert _pythonpath_after_sourcing(line, 1, initial=None) == "/tmp/probe-repo"
    entries = _pythonpath_after_sourcing(line, 1, initial="/tmp/existing").split(":")
    assert entries == ["/tmp/probe-repo", "/tmp/existing"]

    unguarded = 'export PYTHONPATH="/tmp/probe-repo${PYTHONPATH:+:$PYTHONPATH}"'
    assert (
        _pythonpath_after_sourcing(unguarded, 5, initial="/tmp/existing")
        .split(":")
        .count("/tmp/probe-repo")
        == 5
    )


def test_session_hook_stamp_carries_no_project_suffix_and_invalidates_legacy_stamps(
    tmp_path: Path,
) -> None:
    """Pin the ``|no-project`` stamp suffix and verify pre-#1376 stamps miss cache (#1417)."""

    stamp_line = _hook_line("STAMP_VALUE=")
    assert stamp_line == 'STAMP_VALUE="$(manifest_hash)|$DUTCHBAY_EXTRAS|no-project"'

    condition_line = _hook_line('if [ -f "$STAMP" ]')
    probe_body = (
        "manifest_hash() { echo stub-manifest; }\n"
        f'STAMP="{tmp_path / ".session-start-stamp"}"\n'
        'DUTCHBAY_EXTRAS="dev"\n'
        f"{stamp_line}\n"
        f"{condition_line}\n"
        '  echo "CACHE_HIT"\n'
        "else\n"
        '  echo "CACHE_MISS"\n'
        "fi\n"
    )

    stamp_file = tmp_path / ".session-start-stamp"
    # Legacy stamp without |no-project must force a refresh (negative control).
    stamp_file.write_text("stub-manifest|dev", encoding="utf-8")
    legacy = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", probe_body],
        capture_output=True,
        text=True,
        check=True,
    )
    assert legacy.stdout.strip() == "CACHE_MISS"

    # Current stamp with |no-project must hit cache.
    stamp_file.write_text("stub-manifest|dev|no-project", encoding="utf-8")
    current = subprocess.run(
        ["bash", "-euo", "pipefail", "-c", probe_body],
        capture_output=True,
        text=True,
        check=True,
    )
    assert current.stdout.strip() == "CACHE_HIT"


def _extract_extras_expansion_script() -> str:
    """Extract the embedded Python extras-expansion heredoc from the SessionStart hook."""

    hook = SESSION_HOOK.read_text(encoding="utf-8")
    match = re.search(
        r'"\$PY" - "\$DUTCHBAY_EXTRAS" > "\$EXTRA_REQS" <<\'PYEOF\'\n(.*?)\nPYEOF\n',
        hook,
        re.DOTALL,
    )
    assert (
        match is not None
    ), "the hook no longer contains the extras-expansion Python heredoc"
    return match.group(1)


def test_session_hook_extras_expansion_resolves_self_references_without_project() -> (
    None
):
    """Extras expansion follows self-references and never installs the project itself (#1417)."""

    from packaging.requirements import Requirement
    from packaging.utils import canonicalize_name

    hook = SESSION_HOOK.read_text(encoding="utf-8")
    active_lines = [
        line.strip()
        for line in hook.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert not any("pip install -e" in line for line in active_lines)
    assert not any(re.search(r"pip install\b.*\s\.", line) for line in active_lines)
    assert any('pip install --quiet -r "$EXTRA_REQS"' in line for line in active_lines)

    script = _extract_extras_expansion_script()
    completed = subprocess.run(
        [sys.executable, "-c", script, "dev,feasibility"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    assert lines, "extras expansion produced no requirements"
    assert len(lines) == len(set(lines)), "extras expansion emitted duplicate lines"

    names = {canonicalize_name(Requirement(line).name) for line in lines}
    assert "dutchbay-epc-model" not in names
    assert {"pytest", "weasyprint", "pandapower"} <= names


def test_session_hook_extras_expansion_fails_loudly_on_unknown_extra() -> None:
    """Negative control (#1417): an unknown extra must fail loudly instead of silently skipping."""

    script = _extract_extras_expansion_script()
    completed = subprocess.run(
        [sys.executable, "-c", script, "dev,nonexistent_extra_1417"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode != 0
    assert "unknown extra 'nonexistent_extra_1417'" in completed.stderr


def _extract_project_cleanup_snippet() -> str:
    """Extract the project-uninstall and egg-info-removal block from the hook."""

    hook = SESSION_HOOK.read_text(encoding="utf-8")
    match = re.search(
        r'(  if "\$PY" -m pip show --quiet dutchbay-epc-model >/dev/null 2>&1; then\n'
        r'    "\$PY" -m pip uninstall --quiet --yes dutchbay-epc-model\n'
        r"  fi\n"
        r'  rm -rf "\$REPO/dutchbay_epc_model\.egg-info")',
        hook,
    )
    assert (
        match is not None
    ), "the hook no longer contains the project uninstall and egg-info cleanup block"
    return match.group(1)


def test_session_hook_uninstalls_legacy_project_and_removes_egg_info(
    tmp_path: Path,
) -> None:
    """Pin ordering and behaviour of legacy project uninstall and egg-info removal (#1417)."""

    hook = SESSION_HOOK.read_text(encoding="utf-8")
    install_idx = hook.index('"$PY" -m pip install --quiet -r "$EXTRA_REQS"')
    show_idx = hook.index('"$PY" -m pip show --quiet dutchbay-epc-model')
    uninstall_idx = hook.index(
        '"$PY" -m pip uninstall --quiet --yes dutchbay-epc-model'
    )
    egg_idx = hook.index('rm -rf "$REPO/dutchbay_epc_model.egg-info"')
    stamp_idx = hook.index('printf \'%s\' "$STAMP_VALUE" > "$STAMP"')
    assert install_idx < show_idx < uninstall_idx < egg_idx < stamp_idx

    snippet = _extract_project_cleanup_snippet()
    log_file = tmp_path / "pip-calls.log"
    stub_py = tmp_path / "stub-python"
    stub_py.write_text(
        "#!/bin/bash\n"
        'printf "%s\\n" "$*" >> "$STUB_LOG"\n'
        'if [ "${1:-}" = "-m" ] && [ "${2:-}" = "pip" ] && [ "${3:-}" = "show" ]; then\n'
        '  exit "${STUB_SHOW_RC}"\n'
        "fi\n"
        "exit 0\n",
        encoding="utf-8",
    )
    stub_py.chmod(0o755)

    # Case 1: legacy project distribution present -> uninstall runs AND egg-info removed.
    repo_present = tmp_path / "repo-present"
    egg_present = repo_present / "dutchbay_epc_model.egg-info"
    egg_present.mkdir(parents=True)
    (egg_present / "PKG-INFO").write_text(
        "Name: dutchbay-epc-model\n", encoding="utf-8"
    )
    log_file.write_text("", encoding="utf-8")
    subprocess.run(
        ["bash", "-euo", "pipefail", "-c", snippet],
        env={
            **os.environ,
            "PY": str(stub_py),
            "REPO": str(repo_present),
            "STUB_LOG": str(log_file),
            "STUB_SHOW_RC": "0",
        },
        check=True,
    )
    calls_present = log_file.read_text(encoding="utf-8").splitlines()
    assert "-m pip show --quiet dutchbay-epc-model" in calls_present
    assert "-m pip uninstall --quiet --yes dutchbay-epc-model" in calls_present
    assert not egg_present.exists()

    # Case 2 (negative control): project absent -> uninstall skipped, egg-info still removed.
    repo_absent = tmp_path / "repo-absent"
    egg_absent = repo_absent / "dutchbay_epc_model.egg-info"
    egg_absent.mkdir(parents=True)
    (egg_absent / "PKG-INFO").write_text("Name: dutchbay-epc-model\n", encoding="utf-8")
    log_file.write_text("", encoding="utf-8")
    subprocess.run(
        ["bash", "-euo", "pipefail", "-c", snippet],
        env={
            **os.environ,
            "PY": str(stub_py),
            "REPO": str(repo_absent),
            "STUB_LOG": str(log_file),
            "STUB_SHOW_RC": "1",
        },
        check=True,
    )
    calls_absent = log_file.read_text(encoding="utf-8").splitlines()
    assert "-m pip show --quiet dutchbay-epc-model" in calls_absent
    assert "-m pip uninstall --quiet --yes dutchbay-epc-model" not in calls_absent
    assert not egg_absent.exists()
