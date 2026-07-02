"""The run manifest must warn loudly, not silently, when its config hash degrades.

Audit D8 (#577): the CLI re-loaded the config to hash it under a bare ``except`` with
NO log line, so a successful run could ship a manifest whose ``config_sha256`` binds to
the file path rather than the resolved contents — tamper-evidence void, unnoticed. The
``_load_manifest_config`` helper now logs the degrade at WARNING with the traceback.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

import run_full_pipeline_v14 as rfp

LENDER = (
    Path(__file__).resolve().parents[2]
    / "scenarios"
    / "dutchbay_lendercase_2025Q4.yaml"
)


def test_load_manifest_config_happy_path_returns_resolved_config() -> None:
    cfg = rfp._load_manifest_config(str(LENDER))
    assert isinstance(cfg, dict)
    # The real resolved config, not the {config_path: ...} fallback.
    assert "fx" in cfg
    assert cfg.get("config_path") != str(LENDER) or len(cfg) > 1


def test_load_manifest_config_degrade_warns_loudly(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def _boom(_path: object) -> dict:
        raise RuntimeError("cannot resolve config")

    monkeypatch.setattr(rfp, "load_scenario_config", _boom)

    with caplog.at_level(logging.WARNING, logger=rfp.logger.name):
        cfg = rfp._load_manifest_config("scenarios/does_not_matter.yaml")

    # Still returns the non-binding fallback (run is not aborted)...
    assert cfg == {"config_path": "scenarios/does_not_matter.yaml"}
    # ...but the degrade is now visible, not silent.
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("manifest degraded" in r.getMessage().lower() for r in warnings)


def test_stamp_manifest_if_absent_defers_to_engine_manifest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Half 2 of #577: the engine stamps the manifest from the RESOLVED config it
    # evaluated; the CLI fallback must not re-load the config nor overwrite it.
    sentinel = {"config_sha256": "e" * 64}
    result: dict = {"status": "success", "run_manifest": sentinel}

    def _must_not_reload(_path: object) -> dict:
        raise AssertionError("engine manifest present -> CLI must not re-load config")

    monkeypatch.setattr(rfp, "_load_manifest_config", _must_not_reload)
    rfp._stamp_manifest_if_absent(result, "scenarios/does_not_matter.yaml", "strict")
    assert result["run_manifest"] is sentinel


def test_stamp_manifest_if_absent_falls_back_when_missing() -> None:
    # A result without a manifest (e.g. an error-shaped dict or a patched engine)
    # still gets the CLI stamp, via the retained _load_manifest_config path.
    result: dict = {"status": "error"}
    rfp._stamp_manifest_if_absent(result, str(LENDER), "strict")
    manifest = result["run_manifest"]
    assert len(manifest["config_sha256"]) == 64
    assert manifest["validation_mode"] == "strict"
