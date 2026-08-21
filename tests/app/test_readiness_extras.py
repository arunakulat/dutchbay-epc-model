"""Tests for the extras/runtime block on the readiness diagnostic.

The block exists so a deployed instance can be verified WITHOUT shell or deploy access. Two
properties matter: it must be additive (no existing caller's behaviour may change), and it must
never take the route down, because a health endpoint that can crash is worse than none.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)


def _body(deep: bool = False) -> dict:
    url = "/health/readiness" + ("?deep=true" if deep else "")
    resp = client.get(url)
    assert resp.status_code == 200, "the diagnostic always returns 200, it is not a gate"
    return resp.json()


# ── Additive: the pre-existing contract is untouched ─────────────────────────


def test_original_keys_are_all_still_present() -> None:
    body = _body()
    for key in ("status", "contract_version", "ready", "checks"):
        assert key in body


def test_ready_still_means_the_env_checks_only() -> None:
    """`ready` must not start depending on extras — that would move an existing gate."""
    body = _body()
    assert body["ready"] == all(body["checks"].values())


def test_checks_report_booleans_never_values() -> None:
    body = _body()
    assert set(body["checks"]) == {"cdsapi_url", "cdsapi_key"}
    assert all(isinstance(v, bool) for v in body["checks"].values())


# ── The new block ────────────────────────────────────────────────────────────


def test_extras_block_covers_every_extra_the_image_installs() -> None:
    from app.ops.extras import DEPLOYED_EXTRAS

    assert set(_body()["extras"]) == set(DEPLOYED_EXTRAS)


def test_report_extra_is_reported_with_its_declared_packages() -> None:
    report = _body()["extras"]["report"]
    names = {p["distribution"] for p in report["packages"]}
    assert {"weasyprint", "reportlab", "geopandas", "contextily"} <= names


def test_declared_spec_is_surfaced_so_a_pin_can_be_audited() -> None:
    report = _body()["extras"]["report"]
    weasy = next(p for p in report["packages"] if p["distribution"] == "weasyprint")
    assert weasy["declared_spec"], "the pin must be visible, not just the installed version"


def test_extras_available_is_the_and_of_every_extra() -> None:
    body = _body()
    assert body["extras_available"] == all(e["available"] for e in body["extras"].values())


def test_runtime_identity_is_reported() -> None:
    runtime = _body()["runtime"]
    assert runtime["python"]
    assert runtime["platform"]
    assert runtime["distribution"] == "dutchbay-epc-model"


def test_default_probe_does_not_import(monkeypatch: pytest.MonkeyPatch) -> None:
    """The default probe must stay cheap — no package imports on an unauthenticated route."""
    report = _body(deep=False)["extras"]["report"]
    assert report["deep_probed"] is False
    assert all(p["importable"] is None for p in report["packages"])


def test_deep_probe_reports_importability() -> None:
    report = _body(deep=True)["extras"]["report"]
    assert report["deep_probed"] is True
    for pkg in report["packages"]:
        if pkg["installed"]:
            assert pkg["importable"] is not None


def test_deep_probe_catches_a_broken_native_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    """The case this exists for: WeasyPrint installed, pango/cairo missing from the image."""
    from app.ops import extras as ops_extras

    real = ops_extras.importlib.import_module

    def selective(name: str, *a: object, **k: object) -> object:
        if name == "weasyprint":
            raise OSError("cannot load library 'libpango-1.0.so.0'")
        return real(name, *a, **k)

    monkeypatch.setattr(ops_extras.importlib, "import_module", selective)
    report = _body(deep=True)["extras"]["report"]
    assert report["available"] is False
    assert "weasyprint" in report["broken"]
    assert _body(deep=True)["extras_available"] is False


# ── CASPER: the route survives a probe failure ───────────────────────────────


def test_route_stays_up_when_the_probe_itself_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.api.main as main

    def boom(**_kw: object) -> tuple:
        raise RuntimeError("metadata store unreadable")

    monkeypatch.setattr(main, "probe_extras", boom)
    resp = client.get("/health/readiness")
    assert resp.status_code == 200, "readiness must not 500 when only the extras probe fails"
    body = resp.json()
    # The pre-existing contract still answers.
    assert body["ready"] == all(body["checks"].values())
    # A failed probe reports UNKNOWN, never a vacuous "all available" from an empty mapping.
    assert body["extras"] == {}
    assert body["extras_available"] is False
    assert "metadata store unreadable" in body["extras_error"]
