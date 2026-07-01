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
