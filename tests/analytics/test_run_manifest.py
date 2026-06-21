"""Auditable run manifest — reproducibility stamp over the resolved config.

Roadmap gap #3. Binds every pipeline output to its inputs (config hash), engine
version (read from VERSION, not a literal), and commit, for the ICAEW audit posture.
"""

from __future__ import annotations

from pathlib import Path

from analytics.run_manifest import (
    MANIFEST_SCHEMA_VERSION,
    build_run_manifest,
    config_sha256,
    engine_version,
    git_sha,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")


def test_config_sha256_is_stable_and_override_sensitive() -> None:
    base = {"capex": {"usd_total": 159_600_000}, "name": "x"}
    assert config_sha256(base) == config_sha256(dict(base))  # deterministic
    bumped = {"capex": {"usd_total": 170_000_000}, "name": "x"}
    assert config_sha256(base) != config_sha256(bumped)  # an override moves the hash
    assert len(config_sha256(base)) == 64  # full SHA-256 hex


def test_engine_version_reads_version_file() -> None:
    assert engine_version() == (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert engine_version() != "v14.3.0"  # the old hardcoded literal is gone


def test_pipeline_metrics_version_is_no_longer_hardcoded() -> None:
    from analytics.pipeline_v14_enhanced import PipelineMetrics

    factory = PipelineMetrics.__dataclass_fields__["pipeline_version"].default_factory
    assert factory is not None
    assert factory() == engine_version()
    assert factory() != "v14.3.0"


def test_git_sha_env_override(monkeypatch) -> None:
    monkeypatch.setenv("DUTCHBAY_GIT_SHA", "deadbeefcafe")
    assert git_sha() == "deadbeefcafe"


def test_build_run_manifest_fields() -> None:
    m = build_run_manifest(
        {"name": "lender"},
        seed=12345,
        validation_mode="strict",
        generated_at="2026-06-21T00:00:00+00:00",  # injected -> deterministic
    )
    d = m.as_dict()
    assert d["config_sha256"] == config_sha256({"name": "lender"})
    assert d["engine_version"] == engine_version()
    assert d["seed"] == 12345
    assert d["validation_mode"] == "strict"
    assert d["generated_at"] == "2026-06-21T00:00:00+00:00"
    assert d["manifest_schema_version"] == MANIFEST_SCHEMA_VERSION


def test_run_pipeline_response_carries_manifest() -> None:
    from api.pipeline_api import RunPipelineRequest, run_pipeline

    resp = run_pipeline(RunPipelineRequest(config_path=LENDER))
    assert len(resp.manifest.config_sha256) == 64
    assert resp.manifest.engine_version == engine_version()
    assert resp.manifest.validation_mode == resp.validation_mode
    assert resp.manifest.manifest_schema_version == MANIFEST_SCHEMA_VERSION
    # economics unaffected by the metadata addition
    assert resp.kpis.project_irr is not None
