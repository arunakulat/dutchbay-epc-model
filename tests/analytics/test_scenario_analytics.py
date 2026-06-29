#!/usr/bin/env python3
"""Tests for the analytics.scenario_analytics batch orchestrator.

ScenarioAnalytics backs the run_scenario_analytics_v14.py entry point. These
tests exercise the public surface against the canonical lender scenario
(scenarios/dutchbay_lendercase_2025Q4.yaml, which reads mocked AEP, no network):

- constructor coercions and defaults
- discover_scenarios (filtering, missing-dir raise, over-broad glob)
- _effective_discount_rate precedence (override > wacc > top-level > default)
- _run_single happy path and graceful per-scenario failure
- run() DataFrame/metadata shape, mixed/all-fail batches, empty-dir raise
- JSON and Excel exports

The orchestrator rglobs a directory, so each test stages an isolated dir under
pytest's tmp_path to control exactly which configs participate in the batch.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from analytics.scenario_analytics import (
    BatchResultSummary,
    ScenarioAnalytics,
    ScenarioResult,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIOS_DIR = REPO_ROOT / "scenarios"
LENDER_YAML = SCENARIOS_DIR / "dutchbay_lendercase_2025Q4.yaml"
EXAMPLE_A_YAML = SCENARIOS_DIR / "example_a.yaml"
BAD_TAX_YAML = SCENARIOS_DIR / "bad_missing_tax.yaml"
LENDER_STEM = "dutchbay_lendercase_2025Q4"


# ---------------------------------------------------------------------------
# Fixtures: stage isolated scenario directories under tmp_path
# ---------------------------------------------------------------------------
@pytest.fixture
def lender_dir(tmp_path: Path) -> Path:
    """A directory containing only the canonical lender scenario."""
    shutil.copy(LENDER_YAML, tmp_path / LENDER_YAML.name)
    return tmp_path


@pytest.fixture
def lender_analytics(lender_dir: Path) -> ScenarioAnalytics:
    """A ScenarioAnalytics rooted at a single-scenario lender directory."""
    return ScenarioAnalytics(scenarios_dir=lender_dir)


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------
def test_constructor_coerces_and_defaults(tmp_path: Path) -> None:
    """str inputs become Path; flags are coerced; output_path defaults to None."""
    sa = ScenarioAnalytics(
        scenarios_dir=str(tmp_path),
        output_path=str(tmp_path / "out.xlsx"),
        parallel=1,
        global_default_discount_rate=5,
        strict=0,
    )
    assert isinstance(sa.scenarios_dir, Path)
    assert isinstance(sa.output_path, Path)
    assert sa.parallel is True
    assert sa.strict is False
    assert isinstance(sa.global_default_discount_rate, float)
    assert sa.global_default_discount_rate == 5.0


def test_constructor_output_path_defaults_none(tmp_path: Path) -> None:
    """output_path is None unless explicitly provided."""
    sa = ScenarioAnalytics(scenarios_dir=tmp_path)
    assert sa.output_path is None
    assert sa.strict is True  # strict defaults to True
    assert sa.parallel is False
    assert sa.global_default_discount_rate == pytest.approx(0.10)


# ---------------------------------------------------------------------------
# Scenario discovery
# ---------------------------------------------------------------------------
def test_discover_missing_dir_raises() -> None:
    """A non-existent scenarios_dir raises FileNotFoundError."""
    sa = ScenarioAnalytics(scenarios_dir=Path("/nonexistent/dutchbay/xyz"))
    with pytest.raises(FileNotFoundError, match="Scenarios directory not found"):
        sa.discover_scenarios()


def test_discover_empty_dir_returns_empty(tmp_path: Path) -> None:
    """An existing but empty directory yields no scenarios."""
    sa = ScenarioAnalytics(scenarios_dir=tmp_path)
    assert sa.discover_scenarios() == []


def test_discover_sorted_and_finds_yaml(tmp_path: Path) -> None:
    """Discovery returns sorted Paths across yaml/yml/json extensions."""
    shutil.copy(LENDER_YAML, tmp_path / "dutchbay_lendercase_2025Q4.yaml")
    shutil.copy(EXAMPLE_A_YAML, tmp_path / "example_a.yaml")
    sa = ScenarioAnalytics(scenarios_dir=tmp_path)
    found = sa.discover_scenarios()
    stems = [p.stem for p in found]
    assert stems == sorted(stems)
    assert "dutchbay_lendercase_2025Q4" in stems
    assert "example_a" in stems


def test_discover_applies_scenario_filter(tmp_path: Path) -> None:
    """scenario_filter narrows discovery by stem."""
    shutil.copy(LENDER_YAML, tmp_path / "dutchbay_lendercase_2025Q4.yaml")
    shutil.copy(EXAMPLE_A_YAML, tmp_path / "example_a.yaml")
    sa = ScenarioAnalytics(
        scenarios_dir=tmp_path,
        scenario_filter=lambda stem: "lender" in stem,
    )
    found = sa.discover_scenarios()
    assert [p.stem for p in found] == ["dutchbay_lendercase_2025Q4"]


def test_discover_globs_non_scenario_json(tmp_path: Path) -> None:
    """Discovery is over-broad: any .json/.yaml/.yml is picked up.

    # BUG/NOTE: discover_scenarios rglobs every *.json/*.yaml/*.yml, so files
    # like AEP-summary JSONs that are not scenario configs are also discovered.
    # The batch tolerates this (they fail at validation), but the discovery set
    # itself is not restricted to true scenarios.
    """
    shutil.copy(LENDER_YAML, tmp_path / "dutchbay_lendercase_2025Q4.yaml")
    shutil.copy(
        SCENARIOS_DIR / "aep_summary_mullikulam.json",
        tmp_path / "aep_summary_mullikulam.json",
    )
    sa = ScenarioAnalytics(scenarios_dir=tmp_path)
    stems = {p.stem for p in sa.discover_scenarios()}
    assert "aep_summary_mullikulam" in stems


def test_scenario_name_from_path() -> None:
    """The scenario name is the file stem."""
    assert ScenarioAnalytics._scenario_name_from_path(Path("/a/b/foo.yaml")) == "foo"


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------
def test_load_config_returns_dict_with_meta(
    lender_analytics: ScenarioAnalytics,
) -> None:
    """load_config delegates to the shared loader and attaches meta breadcrumb."""
    cfg = lender_analytics.load_config(LENDER_YAML)
    assert isinstance(cfg, dict)
    assert "source_path" in cfg.get("meta", {})


# ---------------------------------------------------------------------------
# Discount-rate precedence
# ---------------------------------------------------------------------------
def test_discount_rate_default(tmp_path: Path) -> None:
    """An empty config falls back to the global default."""
    sa = ScenarioAnalytics(scenarios_dir=tmp_path, global_default_discount_rate=0.123)
    assert sa._effective_discount_rate({}) == pytest.approx(0.123)


def test_discount_rate_top_level(tmp_path: Path) -> None:
    """A top-level discount_rate is used when no override/wacc present."""
    sa = ScenarioAnalytics(scenarios_dir=tmp_path, global_default_discount_rate=0.123)
    assert sa._effective_discount_rate({"discount_rate": 0.07}) == pytest.approx(0.07)


def test_discount_rate_wacc_beats_top_level(tmp_path: Path) -> None:
    """wacc.project_discount_rate outranks a top-level discount_rate."""
    sa = ScenarioAnalytics(scenarios_dir=tmp_path)
    cfg = {"wacc": {"project_discount_rate": 0.085}, "discount_rate": 0.07}
    assert sa._effective_discount_rate(cfg) == pytest.approx(0.085)


def test_discount_rate_override_wins(tmp_path: Path) -> None:
    """scenario.override.discount_rate has highest precedence."""
    sa = ScenarioAnalytics(scenarios_dir=tmp_path)
    cfg = {
        "scenario": {"override": {"discount_rate": 0.05}},
        "wacc": {"project_discount_rate": 0.085},
        "discount_rate": 0.07,
    }
    assert sa._effective_discount_rate(cfg) == pytest.approx(0.05)


def test_discount_rate_invalid_override_falls_through(tmp_path: Path) -> None:
    """An unparseable override falls through to the wacc block."""
    sa = ScenarioAnalytics(scenarios_dir=tmp_path)
    cfg = {
        "scenario": {"override": {"discount_rate": "not-a-number"}},
        "wacc": {"project_discount_rate": 0.085},
    }
    assert sa._effective_discount_rate(cfg) == pytest.approx(0.085)


def test_discount_rate_invalid_all_falls_to_default(tmp_path: Path) -> None:
    """An unparseable top-level value falls back to the global default."""
    sa = ScenarioAnalytics(scenarios_dir=tmp_path, global_default_discount_rate=0.123)
    assert sa._effective_discount_rate({"discount_rate": "xyz"}) == pytest.approx(0.123)


# ---------------------------------------------------------------------------
# Single-scenario execution
# ---------------------------------------------------------------------------
def test_run_single_happy_path(lender_analytics: ScenarioAnalytics) -> None:
    """A valid scenario produces populated KPIs, annual rows, and debt result."""
    path = lender_analytics.discover_scenarios()[0]
    res = lender_analytics._run_single(path)
    assert isinstance(res, ScenarioResult)
    assert res.fail_reason is None
    assert res.name == LENDER_STEM
    assert res.config_path == path
    # 20-year project life -> 20 annual rows.
    assert len(res.annual_rows) == 20
    assert isinstance(res.debt_result, dict) and res.debt_result
    # Default discount rate (no override/wacc block selected for this surface).
    assert res.discount_rate == pytest.approx(0.10)
    # Canonical KPIs are present and finite.
    assert "dscr_min" in res.kpis
    assert "equity_irr" in res.kpis
    assert res.kpis["dscr_min"] > 0


def test_run_single_failure_is_graceful(tmp_path: Path) -> None:
    """A schema-invalid scenario yields a ScenarioResult with fail_reason set.

    _run_single never raises; it records the failure and leaves the result
    surfaces empty so the batch can skip it.
    """
    shutil.copy(BAD_TAX_YAML, tmp_path / "bad_missing_tax.yaml")
    sa = ScenarioAnalytics(scenarios_dir=tmp_path)
    res = sa._run_single(tmp_path / "bad_missing_tax.yaml")
    assert res.fail_reason is not None
    assert "corporate_tax_rate" in res.fail_reason
    assert res.kpis == {}
    assert res.annual_rows == []
    assert res.debt_result == {}
    # On failure the discount rate falls back to the configured default.
    assert res.discount_rate == pytest.approx(0.10)


# ---------------------------------------------------------------------------
# Full run(): DataFrames and metadata
# ---------------------------------------------------------------------------
def test_run_returns_dataframes_and_metadata(
    lender_analytics: ScenarioAnalytics,
) -> None:
    """run() returns (summary_df, timeseries_df, BatchResultSummary)."""
    summary_df, timeseries_df, meta = lender_analytics.run()

    assert isinstance(summary_df, pd.DataFrame)
    assert isinstance(timeseries_df, pd.DataFrame)
    assert isinstance(meta, BatchResultSummary)

    # Summary is indexed by scenario name; one row for one scenario.
    assert list(summary_df.index) == [LENDER_STEM]
    assert "discount_rate_used" in summary_df.columns
    assert summary_df.loc[LENDER_STEM, "discount_rate_used"] == pytest.approx(0.10)

    # Timeseries has one row per year, tagged with the scenario name.
    assert len(timeseries_df) == 20
    assert (timeseries_df["scenario_name"] == LENDER_STEM).all()
    # A dscr column is present (either native or derived/back-filled).
    assert "dscr" in timeseries_df.columns

    # Metadata reflects the single successful scenario.
    assert meta.successful == [LENDER_STEM]
    assert meta.failed == []
    assert meta.n_success == 1
    assert meta.n_failed == 0
    assert meta.batch_summary["n_scenarios_found"] == 1
    assert meta.batch_summary["n_scenarios_run"] == 1
    assert meta.batch_summary["failed_scenarios"] == []


def test_run_empty_dir_raises(tmp_path: Path) -> None:
    """run() on a directory with no configs raises RuntimeError."""
    sa = ScenarioAnalytics(scenarios_dir=tmp_path)
    with pytest.raises(RuntimeError, match="No scenario configs found"):
        sa.run()


def test_run_all_failures_raises(tmp_path: Path) -> None:
    """A batch where every scenario is invalid raises RuntimeError."""
    shutil.copy(BAD_TAX_YAML, tmp_path / "bad_missing_tax.yaml")
    sa = ScenarioAnalytics(scenarios_dir=tmp_path)
    with pytest.raises(RuntimeError, match="All scenarios failed"):
        sa.run()


def test_run_mixed_batch_excludes_failures(tmp_path: Path) -> None:
    """A good + bad batch keeps the good one and reports the bad one in metadata."""
    shutil.copy(LENDER_YAML, tmp_path / "dutchbay_lendercase_2025Q4.yaml")
    shutil.copy(BAD_TAX_YAML, tmp_path / "bad_missing_tax.yaml")
    sa = ScenarioAnalytics(scenarios_dir=tmp_path)
    summary_df, _timeseries_df, meta = sa.run()

    assert meta.successful == [LENDER_STEM]
    assert meta.failed == ["bad_missing_tax"]
    assert meta.n_success == 1
    assert meta.n_failed == 1
    # Failed scenario is excluded from the result frame but kept in metadata.
    assert list(summary_df.index) == [LENDER_STEM]
    failed_entries = meta.batch_summary["failed_scenarios"]
    assert len(failed_entries) == 1
    assert failed_entries[0]["name"] == "bad_missing_tax"
    assert failed_entries[0]["reason"] is not None


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------
def test_run_writes_summary_json(lender_dir: Path, tmp_path: Path) -> None:
    """output_summary_json serialises BatchResultSummary, creating parent dirs."""
    out = tmp_path / "nested" / "batch_meta.json"
    sa = ScenarioAnalytics(scenarios_dir=lender_dir)
    _summary_df, _timeseries_df, meta = sa.run(output_summary_json=out)

    assert out.exists()
    with out.open(encoding="utf-8") as fh:
        payload = json.load(fh)
    assert payload["successful"] == [LENDER_STEM]
    assert payload["n_success"] == 1
    assert payload["n_failed"] == 0
    assert payload["successful"] == meta.successful


def test_run_export_excel(lender_dir: Path) -> None:
    """export_excel=True with an output_path writes an .xlsx workbook."""
    out = lender_dir / "report.xlsx"
    sa = ScenarioAnalytics(scenarios_dir=lender_dir, output_path=out)
    sa.run(export_excel=True)
    assert out.exists()
    assert out.stat().st_size > 0


def test_run_export_excel_noop_without_output_path(lender_dir: Path) -> None:
    """export_excel=True with no output_path is a safe no-op (no crash)."""
    sa = ScenarioAnalytics(scenarios_dir=lender_dir, output_path=None)
    summary_df, _timeseries_df, _meta = sa.run(export_excel=True)
    # Run still succeeds and returns a populated summary.
    assert list(summary_df.index) == [LENDER_STEM]


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------
def test_scenario_result_fail_reason_optional() -> None:
    """ScenarioResult.fail_reason defaults to None."""
    res = ScenarioResult(
        name="x",
        config_path=Path("x.yaml"),
        kpis={},
        annual_rows=[],
        debt_result={},
        discount_rate=0.1,
    )
    assert res.fail_reason is None


def test_scenario_result_lcos_defaults_empty() -> None:
    """ScenarioResult.lcos defaults to an empty list (non-storage scenarios)."""
    res = ScenarioResult(
        name="x",
        config_path=Path("x.yaml"),
        kpis={},
        annual_rows=[],
        debt_result={},
        discount_rate=0.1,
    )
    assert res.lcos == []


# ---------------------------------------------------------------------------
# Read-only LCOS surfacing (finance.bess_lcos) — batch artifacts
# ---------------------------------------------------------------------------
BESS_YAML = SCENARIOS_DIR / "ceb_bess_10mw_capacity_charge.yaml"


@pytest.fixture
def bess_dir(tmp_path: Path) -> Path:
    """A directory containing only the standalone capacity-charge BESS scenario."""
    shutil.copy(BESS_YAML, tmp_path / BESS_YAML.name)
    return tmp_path


def test_bess_scenario_surfaces_lcos_in_summary_and_metadata(bess_dir: Path) -> None:
    """A type: bess scenario surfaces LCOS in both batch artifacts (read-only)."""
    summary_df, _ts, meta = ScenarioAnalytics(scenarios_dir=bess_dir).run()

    # At-a-glance summary column (Excel surface).
    assert "bess_lcos_usd_per_mwh" in summary_df.columns
    lcos_glance = summary_df["bess_lcos_usd_per_mwh"].iloc[0]
    assert isinstance(lcos_glance, float) and lcos_glance > 0.0

    # Full per-BESS breakdown (summary_json surface).
    block = meta.batch_summary["bess_lcos"]
    assert len(block) == 1
    entry = block[0]
    assert entry["scenario"] == "ceb_bess_10mw_capacity_charge"
    result = entry["results"][0]
    assert result["revenue_model"] == "capacity_charge"
    assert result["lcos_usd_per_mwh"] == pytest.approx(lcos_glance)
    assert result["pv_costs_usd"] > 0.0 and result["pv_discharged_mwh"] > 0.0


def test_lcos_metadata_is_json_serialisable(bess_dir: Path) -> None:
    """The enriched batch_summary (incl. bess_lcos) round-trips through JSON."""
    _summary_df, _ts, meta = ScenarioAnalytics(scenarios_dir=bess_dir).run()
    dumped = json.dumps(meta.batch_summary)  # raises if any value is non-serialisable
    assert "bess_lcos" in dumped


def test_wind_scenario_has_no_lcos(lender_analytics: ScenarioAnalytics) -> None:
    """A wind-only batch adds no LCOS column and an empty bess_lcos block."""
    summary_df, _ts, meta = lender_analytics.run()
    assert "bess_lcos_usd_per_mwh" not in summary_df.columns
    assert meta.batch_summary["bess_lcos"] == []


# ---------------------------------------------------------------------------
# Reproducibility manifest (analytics.run_manifest) — batch metadata
# ---------------------------------------------------------------------------
def test_scenario_result_run_manifest_defaults_none() -> None:
    """ScenarioResult.run_manifest defaults to None (pre-manifest failures)."""
    res = ScenarioResult(
        name="x",
        config_path=Path("x.yaml"),
        kpis={},
        annual_rows=[],
        debt_result={},
        discount_rate=0.1,
    )
    assert res.run_manifest is None


def test_batch_stamps_per_scenario_run_manifest(
    lender_analytics: ScenarioAnalytics,
) -> None:
    """Each successful scenario carries a manifest in batch_summary["run_manifests"]."""
    from analytics.run_manifest import engine_version

    _summary_df, _ts, meta = lender_analytics.run()
    manifests = meta.batch_summary["run_manifests"]
    assert len(manifests) == 1
    entry = manifests[0]
    assert entry["scenario"] == LENDER_STEM
    manifest = entry["manifest"]
    assert len(manifest["config_sha256"]) == 64  # full SHA-256 hex
    assert manifest["engine_version"] == engine_version()
    assert len(manifest["git_sha"]) > 0
    assert manifest["validation_mode"] == "strict"


def test_run_manifest_config_hash_is_per_scenario(tmp_path: Path) -> None:
    """Distinct scenario configs get distinct manifest config hashes."""
    shutil.copy(LENDER_YAML, tmp_path / LENDER_YAML.name)
    shutil.copy(EXAMPLE_A_YAML, tmp_path / EXAMPLE_A_YAML.name)
    _summary_df, _ts, meta = ScenarioAnalytics(scenarios_dir=tmp_path).run()
    hashes = {
        e["scenario"]: e["manifest"]["config_sha256"]
        for e in meta.batch_summary["run_manifests"]
    }
    assert len(hashes) == 2
    assert len(set(hashes.values())) == 2  # the two configs hash differently


def test_run_manifests_metadata_is_json_serialisable(
    lender_analytics: ScenarioAnalytics,
) -> None:
    """The enriched batch_summary (incl. run_manifests) round-trips through JSON."""
    _summary_df, _ts, meta = lender_analytics.run()
    dumped = json.dumps(meta.batch_summary)
    assert "run_manifests" in dumped


def test_batch_result_summary_fields() -> None:
    """BatchResultSummary stores success/failure lists and a summary mapping."""
    summary = BatchResultSummary(
        successful=["a"],
        failed=["b"],
        n_success=1,
        n_failed=1,
        batch_summary={"n_scenarios_found": 2},
    )
    assert summary.successful == ["a"]
    assert summary.failed == ["b"]
    assert summary.n_success == 1
    assert summary.n_failed == 1
    assert summary.batch_summary["n_scenarios_found"] == 2
