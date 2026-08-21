"""Regression guards for the Codex desktop local environment."""

from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
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
