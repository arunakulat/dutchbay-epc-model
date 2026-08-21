"""Tests for the external deployment verifier.

The script is a post-deploy gate, so the property that matters is that its EXIT CODE is right:
a broken deployment must not exit 0. Network access is mocked throughout — these tests never
reach out.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "verify_deployment.py"
_spec = importlib.util.spec_from_file_location("verify_deployment", _SCRIPT)
assert _spec and _spec.loader
verify = importlib.util.module_from_spec(_spec)
sys.modules["verify_deployment"] = verify
_spec.loader.exec_module(verify)


HEALTH = {"status": "ok", "contract_version": "1.2"}


def _readiness(**over: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "status": "ok",
        "contract_version": "1.2",
        "ready": True,
        "checks": {"cdsapi_url": True, "cdsapi_key": True},
        "extras_error": None,
        "runtime": {
            "python": "3.12.13",
            "platform": "linux",
            "distribution": "dutchbay-epc-model",
            "version": "15.4.0",
        },
        "extras": {
            "report": {
                "available": True,
                "deep_probed": False,
                "missing": [],
                "broken": [],
                "packages": [
                    {
                        "distribution": "weasyprint",
                        "declared_spec": "<70,>=69",
                        "installed_version": "69.0",
                        "installed": True,
                        "importable": None,
                        "import_error": None,
                        "satisfies_spec": True,
                    }
                ],
            }
        },
    }
    body.update(over)
    return body


@pytest.fixture()
def stub(monkeypatch: pytest.MonkeyPatch):
    """Route fetch() to canned bodies keyed by URL suffix."""

    def install(health: Any = HEALTH, readiness: Any = None) -> None:
        ready = _readiness() if readiness is None else readiness

        def fake_fetch(url: str, timeout: float) -> Any:
            if "readiness" in url:
                if isinstance(ready, Exception):
                    raise ready
                return ready
            if isinstance(health, Exception):
                raise health
            return health

        monkeypatch.setattr(verify, "fetch", fake_fetch)
        monkeypatch.setattr(verify, "expected_contract_version", lambda: "1.2")

    return install


def _run(*argv: str) -> int:
    return verify.main(["verify_deployment.py", *argv])


# ── Exit codes ───────────────────────────────────────────────────────────────


def test_healthy_deployment_exits_zero(
    stub, capsys: pytest.CaptureFixture[str]
) -> None:
    stub()
    assert _run("https://example.test") == verify.OK
    assert "All checks passed" in capsys.readouterr().out


def test_missing_config_fails(stub) -> None:
    stub(readiness=_readiness(checks={"cdsapi_url": True, "cdsapi_key": False}))
    assert _run("https://example.test") == verify.FAILED


def test_unreachable_host_exits_two(stub) -> None:
    stub(health=RuntimeError("cannot reach https://example.test/health: refused"))
    assert _run("https://example.test") == verify.UNREACHABLE


def test_non_json_body_exits_two(stub) -> None:
    stub(health=RuntimeError("did not return JSON"))
    assert _run("https://example.test") == verify.UNREACHABLE


def test_contract_version_mismatch_fails(stub) -> None:
    stub(health={"status": "ok", "contract_version": "9.9"})
    assert _run("https://example.test") == verify.FAILED


def test_no_args_is_a_usage_failure() -> None:
    assert _run() == verify.FAILED


def test_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    assert _run("--help") == verify.OK
    assert "Verify a DEPLOYED instance" in capsys.readouterr().out


# ── The failures this exists to catch ────────────────────────────────────────


def test_broken_native_dependency_fails_the_gate(
    stub, capsys: pytest.CaptureFixture[str]
) -> None:
    """WeasyPrint installed but pango/cairo missing — must not pass."""
    body = _readiness()
    report = body["extras"]["report"]
    report.update(available=False, deep_probed=True, broken=["weasyprint"])
    report["packages"][0].update(
        importable=False,
        import_error="OSError: cannot load library 'libpango-1.0.so.0'",
    )
    stub(readiness=body)
    assert _run("https://example.test", "--deep") == verify.FAILED
    out = capsys.readouterr().out
    assert "libpango" in out


def test_missing_package_fails_the_gate(
    stub, capsys: pytest.CaptureFixture[str]
) -> None:
    body = _readiness()
    body["extras"]["report"].update(available=False, missing=["contextily"])
    stub(readiness=body)
    assert _run("https://example.test") == verify.FAILED
    assert "missing=contextily" in capsys.readouterr().out


def test_pin_violation_fails_the_gate(stub, capsys: pytest.CaptureFixture[str]) -> None:
    body = _readiness()
    report = body["extras"]["report"]
    report.update(available=False, broken=["weasyprint"])
    report["packages"][0].update(satisfies_spec=False, installed_version="71.0")
    stub(readiness=body)
    assert _run("https://example.test") == verify.FAILED
    assert "violates" in capsys.readouterr().out


def test_probe_error_on_the_instance_fails(stub) -> None:
    stub(readiness=_readiness(extras={}, extras_error="RuntimeError: unreadable"))
    assert _run("https://example.test") == verify.FAILED


def test_instance_predating_the_diagnostic_fails_loudly(
    stub, capsys: pytest.CaptureFixture[str]
) -> None:
    """An old image with no extras block must not silently pass as healthy."""
    body = _readiness()
    del body["extras"]
    stub(readiness=body)
    assert _run("https://example.test") == verify.FAILED
    assert "predates" in capsys.readouterr().out


def test_deep_requested_but_not_performed_fails(
    stub, capsys: pytest.CaptureFixture[str]
) -> None:
    stub()  # deep_probed is False in the canned body
    assert _run("https://example.test", "--deep") == verify.FAILED
    assert "did not perform" in capsys.readouterr().out


def test_expected_extra_absent_fails(stub, capsys: pytest.CaptureFixture[str]) -> None:
    stub()
    assert _run("https://example.test", "--expect-extra=grid") == verify.FAILED
    assert "not reported by the instance" in capsys.readouterr().out


# ── Output modes ─────────────────────────────────────────────────────────────


def test_json_mode_emits_parseable_output(
    stub, capsys: pytest.CaptureFixture[str]
) -> None:
    stub()
    assert _run("https://example.test", "--json") == verify.OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert any(row["check"] == "liveness" for row in payload["checks"])


def test_json_mode_reports_unreachable_as_json(
    stub, capsys: pytest.CaptureFixture[str]
) -> None:
    stub(health=RuntimeError("refused"))
    assert _run("https://example.test", "--json") == verify.UNREACHABLE
    assert json.loads(capsys.readouterr().out)["ok"] is False


def test_bare_hostname_gets_https(stub, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def spy(url: str, timeout: float) -> Any:
        seen.append(url)
        return HEALTH if "readiness" not in url else _readiness()

    stub()
    monkeypatch.setattr(verify, "fetch", spy)
    _run("example.test")
    assert all(u.startswith("https://") for u in seen)


def test_all_checks_run_even_after_one_fails(
    stub, capsys: pytest.CaptureFixture[str]
) -> None:
    """The exit code must reflect everything, so a later check is not skipped by an earlier one."""
    stub(readiness=_readiness(checks={"cdsapi_url": False, "cdsapi_key": False}))
    assert _run("https://example.test") == verify.FAILED
    out = capsys.readouterr().out
    assert "cdsapi_url" in out and "cdsapi_key" in out and "extra: report" in out
