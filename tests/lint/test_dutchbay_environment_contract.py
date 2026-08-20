"""Focused contract and refusal tests for the shared environment locator."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import dutchbay_environment as environment

ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "config" / "development_environment.json"


def _policy(**overrides: object) -> environment.EnvironmentPolicy:
    values: dict[str, object] = {
        "schema": environment.POLICY_SCHEMA,
        "environment_variable": "DUTCHBAY_VENV",
        "portable_fallback": ".venv",
        "python_major": 3,
        "python_minor": 12,
        "required_distributions": ("numpy", "pytest"),
        "project_distribution": "dutchbay-epc-model",
        "import_probe": "analytics",
    }
    values.update(overrides)
    return environment.EnvironmentPolicy(**values)  # type: ignore[arg-type]


def _resolved(tmp_path: Path, **overrides: object) -> environment.ResolvedEnvironment:
    venv = tmp_path / "shared-venv"
    (venv / "bin").mkdir(parents=True)
    python = venv / "bin" / "python"
    python.write_text("#!/bin/sh\n", encoding="utf-8")
    python.chmod(0o755)
    values: dict[str, object] = {
        "path": venv,
        "source": "DUTCHBAY_VENV",
        "active_checkout": ROOT,
        "policy": _policy(),
    }
    values.update(overrides)
    return environment.ResolvedEnvironment(**values)  # type: ignore[arg-type]


def _probe_result(
    resolved: environment.ResolvedEnvironment,
    *,
    version: tuple[int, int, int] = (3, 12, 13),
    versions: dict[str, str | None] | None = None,
    import_path: Path | None = None,
    editable: bool = False,
    foreign: tuple[str, ...] = (),
) -> subprocess.CompletedProcess[str]:
    distributions = versions or {"numpy": "2.4.6", "pytest": "9.0.2"}
    payload = {
        "python_version_info": list(version),
        "python_version": ".".join(str(item) for item in version),
        "python_executable": str(resolved.python),
        "python_prefix": str(resolved.path.resolve()),
        "import_path": str(import_path or ROOT / "analytics" / "__init__.py"),
        "required_distributions": distributions,
        "project_install_url": "file:///provisioning/checkout",
        "editable_project_install": editable,
        "foreign_checkout_paths": list(foreign),
    }
    return subprocess.CompletedProcess([], 0, stdout=json.dumps(payload), stderr="")


def test_policy_is_strict_and_config_first() -> None:
    policy = environment.load_environment_policy(POLICY_PATH)

    assert policy.environment_variable == "DUTCHBAY_VENV"
    assert policy.portable_fallback == ".venv"
    assert (policy.python_major, policy.python_minor) == (3, 12)
    assert "opendssdirect.py" in policy.required_distributions
    assert policy.required_distributions == tuple(
        sorted(policy.required_distributions, key=str.casefold)
    )


def test_policy_refuses_unknown_fields(tmp_path: Path) -> None:
    raw = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    raw["hidden_default"] = "/tmp/venv"
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(environment.EnvironmentContractError, match="fields"):
        environment.load_environment_policy(path)


def test_configured_absolute_environment_wins(tmp_path: Path) -> None:
    configured = tmp_path / "persistent" / ".venv"

    resolved = environment.resolve_environment(
        ROOT,
        environ={"DUTCHBAY_VENV": str(configured)},
        policy=_policy(),
    )

    assert resolved.path == configured
    assert resolved.source == "DUTCHBAY_VENV"


def test_unset_environment_uses_portable_checkout_fallback() -> None:
    resolved = environment.resolve_environment(ROOT, environ={}, policy=_policy())

    assert resolved.path == ROOT / ".venv"
    assert resolved.source == "portable_fallback"


@pytest.mark.parametrize("configured", ["", "relative/.venv"])
def test_bad_configured_paths_are_refused(configured: str) -> None:
    with pytest.raises(environment.EnvironmentContractError, match="empty|absolute"):
        environment.resolve_environment(
            ROOT,
            environ={"DUTCHBAY_VENV": configured},
            policy=_policy(),
        )


def test_missing_environment_is_actionable(tmp_path: Path) -> None:
    resolved = environment.ResolvedEnvironment(
        path=tmp_path / "missing",
        source="DUTCHBAY_VENV",
        active_checkout=ROOT,
        policy=_policy(),
    )

    with pytest.raises(environment.EnvironmentContractError, match="does not exist"):
        environment.validate_environment(resolved)


def test_incomplete_environment_is_actionable(tmp_path: Path) -> None:
    resolved = environment.ResolvedEnvironment(
        path=tmp_path / "incomplete",
        source="DUTCHBAY_VENV",
        active_checkout=ROOT,
        policy=_policy(),
    )
    resolved.path.mkdir()

    with pytest.raises(
        environment.EnvironmentContractError, match="executable missing"
    ):
        environment.validate_environment(resolved)


def test_healthy_receipt_binds_environment_and_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    resolved = _resolved(tmp_path)
    monkeypatch.setattr(
        environment.subprocess,
        "run",
        lambda *args, **kwargs: _probe_result(resolved),
    )

    receipt = environment.validate_environment(resolved, environ={})

    assert receipt.status == "PASS"
    assert receipt.venv_path == str(resolved.path.resolve())
    assert receipt.active_checkout == str(ROOT)
    assert receipt.import_path == str(ROOT / "analytics" / "__init__.py")
    assert dict(receipt.required_distributions) == {
        "numpy": "2.4.6",
        "pytest": "9.0.2",
    }


def test_wrong_python_version_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    resolved = _resolved(tmp_path)
    monkeypatch.setattr(
        environment.subprocess,
        "run",
        lambda *args, **kwargs: _probe_result(resolved, version=(3, 11, 14)),
    )

    with pytest.raises(environment.EnvironmentContractError, match="Python 3.11.14"):
        environment.validate_environment(resolved, environ={})


def test_missing_distribution_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    resolved = _resolved(tmp_path)
    monkeypatch.setattr(
        environment.subprocess,
        "run",
        lambda *args, **kwargs: _probe_result(
            resolved, versions={"numpy": "2.4.6", "pytest": None}
        ),
    )

    with pytest.raises(environment.EnvironmentContractError, match="pytest"):
        environment.validate_environment(resolved, environ={})


def test_import_outside_active_checkout_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    resolved = _resolved(tmp_path)
    monkeypatch.setattr(
        environment.subprocess,
        "run",
        lambda *args, **kwargs: _probe_result(
            resolved, import_path=tmp_path / "other" / "analytics" / "__init__.py"
        ),
    )

    with pytest.raises(environment.EnvironmentContractError, match="outside"):
        environment.validate_environment(resolved, environ={})


def test_editable_project_install_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    resolved = _resolved(tmp_path)
    monkeypatch.setattr(
        environment.subprocess,
        "run",
        lambda *args, **kwargs: _probe_result(resolved, editable=True),
    )

    with pytest.raises(environment.EnvironmentContractError, match="editable"):
        environment.validate_environment(resolved, environ={})


def test_foreign_checkout_path_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    resolved = _resolved(tmp_path)
    monkeypatch.setattr(
        environment.subprocess,
        "run",
        lambda *args, **kwargs: _probe_result(
            resolved, foreign=("/tmp/other-dutchbay",)
        ),
    )

    with pytest.raises(environment.EnvironmentContractError, match="path-contaminated"):
        environment.validate_environment(resolved, environ={})


def test_cli_rejects_positional_configuration(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert environment.main(["--venv", "/tmp/venv"]) == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["status"] == "FAIL"
    assert "environment variables only" in payload["error"]
