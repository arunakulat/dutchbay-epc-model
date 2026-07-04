"""Tests for the config-first output-path resolver (#735, slice 1)."""

from __future__ import annotations

from pathlib import Path

from analytics.output_paths import (
    DEFAULT_PIPELINE_OUTPUT_ROOT,
    default_run_id,
    resolve_output_dir,
)


def test_default_pipeline_root_is_single_sourced() -> None:
    # Pin the pipeline default now centralised here (the #735 fragmentation this consolidates).
    assert DEFAULT_PIPELINE_OUTPUT_ROOT == "_out/run_full_pipeline_v14"


def test_resolve_default_is_identity_str() -> None:
    # Default (run_scoped=False) returns the root unchanged -> committed runs write the same paths.
    assert resolve_output_dir("_out/run_full_pipeline_v14") == Path(
        "_out/run_full_pipeline_v14"
    )


def test_resolve_default_is_identity_path() -> None:
    root = Path("_out/release_run")
    assert resolve_output_dir(root) == root


def test_resolve_run_scoped_appends_explicit_run_id() -> None:
    assert resolve_output_dir(
        "_out/run_full_pipeline_v14", run_scoped=True, run_id="v9.9.9_deadbeef"
    ) == Path("_out/run_full_pipeline_v14/v9.9.9_deadbeef")


def test_resolve_run_scoped_defaults_to_run_id() -> None:
    out = resolve_output_dir("_out/x", run_scoped=True)
    assert out.parent == Path("_out/x")
    assert out.name == default_run_id()


def test_default_run_id_carries_version_provenance() -> None:
    rid = default_run_id()
    # Reproducible within a run and shaped v<engine_version>_<git_sha12> (MRM-02 provenance).
    assert rid == default_run_id()
    assert rid.startswith("v")
    assert "_" in rid
