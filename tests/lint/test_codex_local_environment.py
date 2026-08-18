"""Regression guards for the Codex desktop local environment."""

from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENVIRONMENT_FILE = ROOT / ".codex" / "environments" / "environment.toml"
SETUP_SCRIPT = ROOT / "setup_venv.sh"
SESSION_HOOK = ROOT / ".claude" / "hooks" / "session-start.sh"
SOURCED_SETUP_SCRIPT = ROOT / "scripts" / "venv_up.sh"
VENV_CHECK_SCRIPT = ROOT / "check_venv.sh"
BOOTSTRAP_HELPER = ROOT / "dutchbay_bootstrap.py"
DOCKERFILE = ROOT / "Dockerfile"


def _environment() -> dict[str, object]:
    """Load the Codex-generated project environment configuration."""

    with ENVIRONMENT_FILE.open("rb") as stream:
        return tomllib.load(stream)


def test_codex_environment_uses_supported_location_and_version() -> None:
    """Keep the environment discoverable by Codex desktop worktrees."""

    environment = _environment()

    assert environment["version"] == 1
    assert environment["name"] == "DutchBay EPC"


def test_codex_environment_bootstraps_the_canonical_venv() -> None:
    """Fresh worktrees must use the maintained repository bootstrap."""

    environment = _environment()
    setup = environment["setup"]

    assert isinstance(setup, dict)
    assert setup["script"].strip() == "./setup_venv.sh"


def test_bootstrap_prefers_the_supported_ci_python() -> None:
    """Require the tested 3.12 minor instead of silently selecting a newer Python."""

    for path in (
        SETUP_SCRIPT,
        SESSION_HOOK,
        SOURCED_SETUP_SCRIPT,
        VENV_CHECK_SCRIPT,
    ):
        script = path.read_text(encoding="utf-8")

        assert "sys.version_info[:2] != (3, 12)" in script

    script = SETUP_SCRIPT.read_text(encoding="utf-8")
    assert (
        "for candidate in python3.12 /opt/homebrew/bin/python3.12 python3 python"
        in script
    )
    assert "Python 3.12 interpreter was not found" in script


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
    """Actions should use the worktree venv and current application entrypoint."""

    environment = _environment()
    actions = environment["actions"]

    assert isinstance(actions, list)
    by_name = {action["name"]: action for action in actions}
    assert set(by_name) == {"Fast validation", "Full tests", "Run API"}
    assert all(".venv/bin" in action["command"] for action in actions)
    assert by_name["Fast validation"]["command"].lstrip().startswith("set -e")
    assert "--reload" in by_name["Run API"]["command"]
    assert "app.api.main:app" in by_name["Run API"]["command"]
