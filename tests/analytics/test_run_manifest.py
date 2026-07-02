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
    assert (
        engine_version() == (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    )
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


def test_git_sha_env_override_beats_populated_cache(monkeypatch) -> None:
    # The env override is deliberately OUTSIDE the subprocess cache (#577): even
    # after the cached probe has run, a later env injection must win per call.
    from analytics import run_manifest as rm

    rm._git_head_sha.cache_clear()
    monkeypatch.delenv("DUTCHBAY_GIT_SHA", raising=False)
    monkeypatch.delenv("GIT_COMMIT", raising=False)
    git_sha()  # populates the subprocess cache
    monkeypatch.setenv("DUTCHBAY_GIT_SHA", "deadbeefcafe")
    assert git_sha() == "deadbeefcafe"


def test_git_sha_subprocess_forked_at_most_once(monkeypatch) -> None:
    # MC/sensitivity stamp a manifest per trial via the engine (#577); the git
    # probe must therefore be process-cached, not forked per call.
    from analytics import run_manifest as rm

    calls = {"n": 0}
    real_run = rm.subprocess.run

    def _counting_run(*args, **kwargs):
        calls["n"] += 1
        return real_run(*args, **kwargs)

    rm._git_head_sha.cache_clear()
    monkeypatch.delenv("DUTCHBAY_GIT_SHA", raising=False)
    monkeypatch.delenv("GIT_COMMIT", raising=False)
    monkeypatch.setattr(rm.subprocess, "run", _counting_run)
    try:
        first = rm.git_sha()
        second = rm.git_sha()
    finally:
        # Drop the entry cached under the counting wrapper so later tests re-probe.
        rm._git_head_sha.cache_clear()
    assert first == second
    assert calls["n"] == 1


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


def test_engine_stamps_manifest_for_path_config() -> None:
    # Half 2 of #577: the ENGINE stamps result["run_manifest"] from the resolved
    # config it evaluated — no outer layer, no config re-load.
    from analytics.pipeline_v14_enhanced import run_v14_pipeline
    from analytics.scenario_loader import load_scenario_config

    result = run_v14_pipeline(config=LENDER)
    manifest = result["run_manifest"]
    resolved = dict(load_scenario_config(LENDER))
    assert manifest["config_sha256"] == config_sha256(resolved)
    assert manifest["engine_version"] == engine_version()
    assert manifest["validation_mode"] == "strict"
    assert manifest["manifest_schema_version"] == MANIFEST_SCHEMA_VERSION


def test_engine_stamps_manifest_for_inline_mapping_config() -> None:
    # The inline-Mapping branch (MC/sensitivity per-trial entry, web callers)
    # must bind the hash to the exact in-memory config evaluated.
    from analytics.pipeline_v14_enhanced import run_v14_pipeline
    from analytics.scenario_loader import load_scenario_config

    cfg = dict(load_scenario_config(LENDER))
    result = run_v14_pipeline(config=cfg)
    assert result["run_manifest"]["config_sha256"] == config_sha256(cfg)
    assert result["run_manifest"]["validation_mode"] == "strict"


def test_evaluation_gateway_receives_engine_manifest() -> None:
    # Direct evaluation_v14 gateway callers (ARCH-04) previously got NO manifest
    # because only the CLI/api/app outer layers stamped one.
    from analytics.evaluation_v14 import evaluate_with_overrides

    result = evaluate_with_overrides(config_path=LENDER, return_full_result=True)
    manifest = result["run_manifest"]
    assert len(manifest["config_sha256"]) == 64
    assert manifest["engine_version"] == engine_version()


def test_run_pipeline_response_carries_manifest() -> None:
    from analytics.scenario_loader import load_scenario_config
    from api.pipeline_api import RunPipelineRequest, run_pipeline

    resp = run_pipeline(RunPipelineRequest(config_path=LENDER))
    assert len(resp.manifest.config_sha256) == 64
    # The response manifest binds to the resolved config the engine evaluated.
    assert resp.manifest.config_sha256 == config_sha256(
        dict(load_scenario_config(LENDER))
    )
    assert resp.manifest.engine_version == engine_version()
    assert resp.manifest.validation_mode == resp.validation_mode
    assert resp.manifest.manifest_schema_version == MANIFEST_SCHEMA_VERSION
    # economics unaffected by the metadata addition
    assert resp.kpis.project_irr is not None


def test_run_pipeline_response_prefers_engine_manifest(monkeypatch) -> None:
    # With the engine stamping the manifest (#577), the API boundary must not
    # rebuild one: its build_run_manifest fallback is never called on this path.
    import api.pipeline_api as papi

    def _must_not_rebuild(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("engine manifest present -> api must not rebuild it")

    monkeypatch.setattr(papi, "build_run_manifest", _must_not_rebuild)
    resp = papi.run_pipeline(papi.RunPipelineRequest(config_path=LENDER))
    assert len(resp.manifest.config_sha256) == 64
