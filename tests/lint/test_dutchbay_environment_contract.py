"""Focused contract and refusal tests for the shared environment locator."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import dutchbay_environment as environment

ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "config" / "development_environment.json"
LOCK_PATH = ROOT / "requirements.txt"

#: The committed lock, keyed canonically.  Tests below describe a *healthy* environment
#: as "installed is exactly the lock" and then perturb one entry, so they exercise the
#: real 311-pin lock and need no edit when a pin is bumped.  Hard-coding a version here
#: would make every lock bump a test failure, which is how pins rot into fiction.
LOCK: dict[str, str] = {
    pin.canonical_name: pin.version
    for pin in environment.load_dependency_lock(LOCK_PATH)
}


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
        "dependency_lock": "requirements.txt",
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
    installed: dict[str, str] | None = None,
    import_path: Path | None = None,
    editable: bool = False,
    foreign: tuple[str, ...] = (),
) -> subprocess.CompletedProcess[str]:
    """Stand in for the in-venv probe, which reports state and judges nothing."""

    payload = {
        "python_version_info": list(version),
        "python_version": ".".join(str(item) for item in version),
        "python_executable": str(resolved.python),
        "python_prefix": str(resolved.path.resolve()),
        "import_path": str(import_path or ROOT / "analytics" / "__init__.py"),
        "installed_distributions": dict(LOCK) if installed is None else installed,
        "project_install_url": "file:///provisioning/checkout",
        "editable_project_install": editable,
        "foreign_checkout_paths": list(foreign),
    }
    return subprocess.CompletedProcess([], 0, stdout=json.dumps(payload), stderr="")


def _installed_except(*names: str) -> dict[str, str]:
    """Return the healthy installed set with ``names`` uninstalled."""

    return {name: version for name, version in LOCK.items() if name not in names}


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
        "numpy": LOCK["numpy"],
        "pytest": LOCK["pytest"],
    }
    assert receipt.dependency_lock == "requirements.txt"
    assert receipt.locked_distribution_count == len(LOCK)
    assert receipt.absent_locked_distributions == ()


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
            resolved, installed=_installed_except("pytest")
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


# --------------------------------------------------------------------------------
# Dependency drift between the installed environment and the committed lock.
#
# The contract used to assert only that the policy's required_distributions were
# PRESENT, so an environment whose versions had wandered still reported PASS.  The
# tests below pin both halves of the decision: a version disagreement is drift and is
# fatal for any locked distribution; an absent one is a capability question and is
# fatal only for the required set.
# --------------------------------------------------------------------------------


def test_drift_in_a_required_distribution_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A version disagreement fails even where presence alone would have passed."""

    resolved = _resolved(tmp_path)
    drifted = dict(LOCK)
    drifted["numpy"] = "0.0.1"
    monkeypatch.setattr(
        environment.subprocess,
        "run",
        lambda *args, **kwargs: _probe_result(resolved, installed=drifted),
    )

    with pytest.raises(environment.EnvironmentContractError) as failure:
        environment.validate_environment(resolved, environ={})

    message = str(failure.value)
    assert "drifted from requirements.txt" in message
    assert f"numpy 0.0.1 installed, {LOCK['numpy']} locked" in message
    assert "./setup_venv.sh" in message


def test_drift_outside_the_required_set_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The 2026-09-14 case: drift in a package no policy field and no test names.

    ``weasyprint`` was visible only because one integration test asserted its version;
    ``scipy-stubs`` and ``websocket-client`` drifted in the same environment unseen.
    Comparing the whole lock is what removes the dependence on someone having guessed
    in advance which package would matter.
    """

    resolved = _resolved(tmp_path)
    assert "websocket-client" not in resolved.policy.required_distributions
    drifted = dict(LOCK)
    drifted["websocket-client"] = "1.9.0"
    monkeypatch.setattr(
        environment.subprocess,
        "run",
        lambda *args, **kwargs: _probe_result(resolved, installed=drifted),
    )

    with pytest.raises(
        environment.EnvironmentContractError, match="websocket-client 1.9.0 installed"
    ):
        environment.validate_environment(resolved, environ={})


def test_every_locked_distribution_is_compared(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Guard the guard: drift in ANY locked pin is caught, not a curated subset."""

    resolved = _resolved(tmp_path)
    assert len(LOCK) > 300, f"lock parsed to only {len(LOCK)} pins"

    undetected = []
    for name in LOCK:
        drifted = dict(LOCK)
        drifted[name] = "0.0.0"
        monkeypatch.setattr(
            environment.subprocess,
            "run",
            lambda *args, _drifted=drifted, **kwargs: _probe_result(
                resolved, installed=_drifted
            ),
        )
        try:
            environment.validate_environment(resolved, environ={})
        except environment.EnvironmentContractError as exc:
            if "drifted from" not in str(exc):
                undetected.append(name)
        else:
            undetected.append(name)

    assert not undetected, f"drift went undetected for: {sorted(undetected)}"


def test_absent_optional_distribution_is_recorded_not_fatal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An uninstalled optional extra is a capability question, not environment drift.

    The deployed image is the reason: ``Dockerfile`` installs the full lock and then
    only ``.[api,jobs,report]``.  Which extras a host must carry is owned by the guard
    at the point of use -- ``require_dbpl_stack()`` under DBPL-01 -- so this contract
    surfaces the absence rather than deciding it.
    """

    resolved = _resolved(tmp_path)
    monkeypatch.setattr(
        environment.subprocess,
        "run",
        lambda *args, **kwargs: _probe_result(
            resolved, installed=_installed_except("geopandas", "contextily")
        ),
    )

    receipt = environment.validate_environment(resolved, environ={})

    assert receipt.status == "PASS"
    assert set(receipt.absent_locked_distributions) == {"geopandas", "contextily"}
    assert receipt.to_dict()["absent_locked_distributions"] == list(
        receipt.absent_locked_distributions
    )


def test_absence_is_never_silent_in_the_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A tolerated absence still has to be stated -- VERIFY-01 on a passing receipt."""

    resolved = _resolved(tmp_path)
    monkeypatch.setattr(
        environment.subprocess,
        "run",
        lambda *args, **kwargs: _probe_result(
            resolved, installed=_installed_except("weasyprint")
        ),
    )

    payload = environment.validate_environment(resolved, environ={}).to_dict()

    assert payload["absent_locked_distributions"] == ["weasyprint"]
    assert payload["locked_distribution_count"] == len(LOCK)


# --------------------------------------------------------------------------------
# Lock parsing.  A construct this parser cannot reduce to an exact pin must raise:
# a distribution missing from the parsed result is compared against nothing, so a
# lenient parser silently shrinks the check it feeds.
# --------------------------------------------------------------------------------


def test_the_committed_lock_parses_to_exact_pins() -> None:
    """The real lock parses whole, with the tricky names normalised correctly."""

    pins = environment.load_dependency_lock(LOCK_PATH)

    assert len(pins) > 300
    canonical = {pin.canonical_name for pin in pins}
    assert {"opendssdirect-py", "weasyprint", "scipy-stubs"} <= canonical
    declared = {pin.declared_name for pin in pins}
    assert "opendssdirect.py" in declared, "declared spelling must survive parsing"


@pytest.mark.parametrize(
    ("line", "reason"),
    [
        ("-r other-pins.txt", "option or include"),
        ("--index-url https://example.invalid", "option or include"),
        ("attrs", "exact name==version"),
        ("attrs>=26.1.0", "exact name==version"),
        ("attrs!=26.1.0", "exact name==version"),
        ("attrs==26.1.0,<27", "additional specifier"),
        ("attrs==26.1.0 ; python_version >= '3.12'", "marker"),
        ("celery[redis]==5.6.2", "extras group"),
        ("attrs==", "exact name==version"),
    ],
)
def test_unpinnable_lock_lines_are_refused(
    tmp_path: Path, line: str, reason: str
) -> None:
    path = tmp_path / "requirements.txt"
    path.write_text(f"attrs==26.1.0\n{line}\n", encoding="utf-8")

    with pytest.raises(environment.EnvironmentContractError, match=reason):
        environment.load_dependency_lock(path)


def test_empty_lock_is_refused(tmp_path: Path) -> None:
    """A lock that parses to nothing would pass every environment on earth."""

    path = tmp_path / "requirements.txt"
    path.write_text("# only a comment\n\n", encoding="utf-8")

    with pytest.raises(environment.EnvironmentContractError, match="no pins"):
        environment.load_dependency_lock(path)


def test_contradictory_duplicate_pins_are_refused(tmp_path: Path) -> None:
    path = tmp_path / "requirements.txt"
    path.write_text("attrs==26.1.0\nattrs==25.3.0\n", encoding="utf-8")

    with pytest.raises(environment.EnvironmentContractError, match="pinned twice"):
        environment.load_dependency_lock(path)


def test_hash_suffixes_do_not_defeat_the_parser(tmp_path: Path) -> None:
    """``--hash=`` binds to the requirement before it; keep the pin, drop the hash."""

    path = tmp_path / "requirements.txt"
    path.write_text("attrs==26.1.0 --hash=sha256:abc123\n", encoding="utf-8")

    assert environment.load_dependency_lock(path) == (
        environment.LockedDistribution("attrs", "attrs", "26.1.0"),
    )


def test_canonical_name_matches_packaging_over_the_real_corpus() -> None:
    """Pin the stdlib normalisation against ``packaging`` on every name in play.

    :mod:`dutchbay_environment` cannot import ``packaging`` -- it is imported under a
    bare bootstrap interpreter -- so the equivalence is asserted here, where the
    governed environment is available.  ``opendssdirect.py``, ``boolean.py``,
    ``pdfminer.six`` and ``svg.py`` are the names a ``replace("_", "-")`` spelling
    gets wrong.
    """

    from importlib.metadata import distributions

    from packaging.utils import canonicalize_name

    names = {pin.declared_name for pin in environment.load_dependency_lock(LOCK_PATH)}
    names.update(
        name
        for name in (distribution.metadata["Name"] for distribution in distributions())
        if name
    )
    assert len(names) > 300

    divergent = {
        name
        for name in names
        if environment.canonical_distribution_name(name) != canonicalize_name(name)
    }
    assert not divergent, f"stdlib normalisation diverges from packaging: {divergent}"


def test_governed_policy_names_the_committed_lock() -> None:
    """CESSPIT: the lock the contract compares against is config, not a literal."""

    policy = environment.load_environment_policy(POLICY_PATH)

    assert policy.dependency_lock == "requirements.txt"
    assert (ROOT / policy.dependency_lock).is_file()


@pytest.mark.parametrize("configured", ["/etc/requirements.txt", "../requirements.txt"])
def test_lock_outside_the_checkout_is_refused(tmp_path: Path, configured: str) -> None:
    """The lock must live in the checkout; an escape would compare against anything."""

    raw = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    raw["dependency_lock"] = configured
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(environment.EnvironmentContractError, match="relative path"):
        environment.load_environment_policy(path)
