"""Regression guards for the Codex desktop local environment."""

from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENVIRONMENT_FILE = ROOT / ".codex" / "environments" / "environment.toml"
SETUP_SCRIPT = ROOT / "setup_venv.sh"


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
    """Avoid selecting a broken or unsupported generic Python ahead of 3.12."""

    script = SETUP_SCRIPT.read_text(encoding="utf-8")

    assert "for candidate in python3.12 python3 python" in script
    assert "sys.version_info < (3, 12)" in script


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
