"""Tests for the AEP ↔ capacity-factor reconciliation guard.

Guards the invariant that a scenario's ``capacity_mw × capacity_factor × 8.760`` (the
basis the finance engine bills revenue off) reconciles with any bankable net AEP it also
declares. Covers: the config-driven tolerance, the canonical scenarios reconciling, the
fail-loud divergence (the #263 Mullikulam 3×-capacity class), the no-op skip paths, and
the pipeline-level wiring.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml

from analytics.aep_reconciliation import (
    AepReconciliationError,
    collect_bankable_net_aep_gwh,
    default_tolerance_pct,
    reconcile_capacity_factor_with_bankable_aep,
    resolve_tolerance_pct,
)
from analytics.scenario_loader import load_scenario_config

REPO_ROOT = Path(__file__).resolve().parents[2]

# Scenarios that carry BOTH a capacity_mw/capacity_factor AND a bankable net AEP.
BANKABLE_SCENARIOS = [
    "scenarios/dutchbay_lendercase_2025Q4.yaml",
    "scenarios/kalpitiya_lendercase_160m_fitted.yaml",
    "scenarios/mullikulam_2x50mw_mannar.yaml",
    "scenarios/dutchbay_lendercase_5usc_fixed_lkr.yaml",
]


# --- tolerance is config-first --------------------------------------------------------


def test_default_tolerance_comes_from_defaults_yaml() -> None:
    """The fallback tolerance is sourced from config/defaults.yaml, not a Python literal."""
    tol = default_tolerance_pct()
    assert tol == pytest.approx(2.0, abs=1e-9)
    # And it really is the value in the file (no hidden constant).
    data = yaml.safe_load((REPO_ROOT / "config" / "defaults.yaml").read_text())
    assert tol == float(data["defaults"]["aep_reconciliation"]["tolerance_pct"])


def test_scenario_can_override_tolerance() -> None:
    assert resolve_tolerance_pct({"aep_reconciliation": {"tolerance_pct": 7.5}}) == 7.5
    # Falls back to the default when not overridden.
    assert resolve_tolerance_pct({}) == default_tolerance_pct()


def test_non_numeric_tolerance_override_raises() -> None:
    with pytest.raises(ValueError, match="tolerance_pct must be numeric"):
        resolve_tolerance_pct({"aep_reconciliation": {"tolerance_pct": "loose"}})


# --- the canonical scenarios reconcile ------------------------------------------------


@pytest.mark.parametrize("scenario", BANKABLE_SCENARIOS)
def test_canonical_scenarios_reconcile(scenario: str) -> None:
    """Every shipped bankable scenario passes the guard (they agree within ~0.04%)."""
    cfg = load_scenario_config(str(REPO_ROOT / scenario))
    reconcile_capacity_factor_with_bankable_aep(cfg, scenario)  # must not raise


def test_both_bankable_sources_are_collected() -> None:
    """expected_results.net_aep_p50_gwh AND the aep_summary JSON are both picked up."""
    cfg = load_scenario_config(
        str(REPO_ROOT / "scenarios" / "mullikulam_2x50mw_mannar.yaml")
    )
    refs = collect_bankable_net_aep_gwh(cfg)
    assert any("expected_results" in k for k in refs)
    assert any("net_site_aep_gwh" in k for k in refs)
    # Both reference the same physical ~133.1 GWh.
    assert all(abs(v - 133.1) < 1.0 for v in refs.values())


# --- fail loud on divergence (the #263 Mullikulam class) ------------------------------


def test_divergent_capacity_raises() -> None:
    """A 3×-inflated capacity_mw (the old Mullikulam bug) fails loud."""
    cfg = load_scenario_config(
        str(REPO_ROOT / "scenarios" / "mullikulam_2x50mw_mannar.yaml")
    )
    cfg["project"]["capacity_mw"] = 159.6  # was the real 56.0
    with pytest.raises(AepReconciliationError, match="does not reconcile"):
        reconcile_capacity_factor_with_bankable_aep(cfg, "divergent")


def test_divergent_capacity_factor_raises() -> None:
    """A divergence driven by capacity_factor (not capacity_mw) also fails loud."""
    cfg = load_scenario_config(
        str(REPO_ROOT / "scenarios" / "mullikulam_2x50mw_mannar.yaml")
    )
    cfg["project"]["capacity_factor"] = 0.50  # implies ~245 GWh vs the bankable 133.1
    with pytest.raises(AepReconciliationError):
        reconcile_capacity_factor_with_bankable_aep(cfg, "divergent-cf")


def test_within_tolerance_does_not_raise() -> None:
    """A small (<2%) perturbation stays within tolerance."""
    cfg = load_scenario_config(
        str(REPO_ROOT / "scenarios" / "mullikulam_2x50mw_mannar.yaml")
    )
    cfg["project"]["capacity_factor"] = cfg["project"]["capacity_factor"] * 1.01  # +1%
    reconcile_capacity_factor_with_bankable_aep(cfg, "within-tol")  # must not raise


def test_widened_tolerance_admits_divergence() -> None:
    """An explicit wide tolerance lets an intentional gap through (documented escape)."""
    cfg = load_scenario_config(
        str(REPO_ROOT / "scenarios" / "mullikulam_2x50mw_mannar.yaml")
    )
    cfg["project"]["capacity_mw"] = 159.6
    cfg["aep_reconciliation"] = {"tolerance_pct": 300.0}
    reconcile_capacity_factor_with_bankable_aep(cfg, "wide-tol")  # must not raise


# --- no-op skip paths -----------------------------------------------------------------


def test_no_bankable_reference_is_noop() -> None:
    """With no bankable AEP present, the capacity_factor path stands alone (no raise)."""
    cfg = load_scenario_config(
        str(REPO_ROOT / "scenarios" / "mullikulam_2x50mw_mannar.yaml")
    )
    cfg.pop("expected_results", None)
    cfg.get("resource", {}).pop("aep_summary_path", None)
    cfg["project"][
        "capacity_mw"
    ] = 159.6  # would diverge, but nothing to reconcile against
    reconcile_capacity_factor_with_bankable_aep(cfg, "no-ref")  # must not raise


def test_declared_but_missing_aep_summary_path_raises() -> None:
    """WIND-7: a declared aep_summary_path that does not resolve must FAIL LOUD, not be
    silently skipped (which would disarm the AEP<->CF reconciliation guard)."""
    cfg = {"resource": {"aep_summary_path": "scenarios/does_not_exist_aep_summary.json"}}
    with pytest.raises(AepReconciliationError, match="aep_summary_path"):
        collect_bankable_net_aep_gwh(cfg)


def test_missing_capacity_is_noop() -> None:
    cfg = {
        "expected_results": {"net_aep_p50_gwh": 133.1},
        "project": {"capacity_factor": 0.27},
    }
    reconcile_capacity_factor_with_bankable_aep(cfg)  # no capacity_mw → no-op


def test_missing_project_block_is_noop() -> None:
    reconcile_capacity_factor_with_bankable_aep(
        {"expected_results": {"net_aep_p50_gwh": 1.0}}
    )


# --- pipeline-level wiring ------------------------------------------------------------


def test_pipeline_rejects_a_divergent_scenario_file() -> None:
    """run_v14_pipeline(path) fails loud at load when a scenario's AEP doesn't reconcile.

    The guard lives in load_scenario_config, so a divergent scenario FILE is rejected
    (wrapped as PipelineConfigError), while in-memory perturbed dicts from MC/sensitivity
    are never re-loaded and so are unaffected.
    """
    from analytics.pipeline_v14_enhanced import (
        PipelineConfigError,
        run_v14_pipeline,
    )

    cfg = load_scenario_config(
        str(REPO_ROOT / "scenarios" / "mullikulam_2x50mw_mannar.yaml")
    )
    cfg["project"]["capacity_mw"] = 159.6
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as fh:
        yaml.safe_dump(cfg, fh)
        path = fh.name
    try:
        with pytest.raises(PipelineConfigError, match="reconcile"):
            run_v14_pipeline(config=path)
    finally:
        Path(path).unlink()


def test_perturbed_dict_is_not_reguarded() -> None:
    """A perturbed in-memory dict (the MC/sensitivity path) is NOT re-checked.

    Mirrors how MC/sensitivity deliberately move capacity_factor away from the bankable
    point: they pass a dict to the engine, which does not re-load, so the guard (which
    lives at file-load time) does not fire on the intentional what-if.
    """
    from analytics.pipeline_v14_enhanced import run_v14_pipeline

    cfg = load_scenario_config(
        str(REPO_ROOT / "scenarios" / "mullikulam_2x50mw_mannar.yaml")
    )
    cfg["project"]["capacity_factor"] = cfg["project"]["capacity_factor"] * 1.5  # +50%
    # Passing the perturbed DICT must not raise a reconciliation error.
    result = run_v14_pipeline(config=cfg)
    assert "kpis" in result


# --- the guard resolves capacity/CF exactly like the engine (multi-path + pct) ---------


def _lender() -> dict:
    return load_scenario_config(
        str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")
    )


def test_percent_form_capacity_factor_does_not_false_positive() -> None:
    """project.capacity_factor authored as a percent (>1.0) is normalized like the engine."""
    cfg = _lender()
    cfg["project"]["capacity_factor"] = 33.2  # engine reads 0.332 via pct_to_decimal (post 2% AEP haircut)
    reconcile_capacity_factor_with_bankable_aep(cfg, "pct-cf")  # must NOT raise


def test_capacity_factor_pct_path_correct_does_not_raise() -> None:
    """The capacity_factor_pct authoring form (an established alias) resolves correctly."""
    cfg = _lender()
    del cfg["project"]["capacity_factor"]
    cfg["project"]["capacity_factor_pct"] = 33.2
    reconcile_capacity_factor_with_bankable_aep(cfg, "cf_pct-ok")  # must NOT raise


def test_capacity_factor_pct_divergence_raises() -> None:
    """A 3× stale capacity expressed via the capacity_factor_pct form still fails loud."""
    cfg = _lender()
    del cfg["project"]["capacity_factor"]
    cfg["project"]["capacity_factor_pct"] = 33.9
    cfg["project"]["capacity_mw"] = cfg["project"]["capacity_mw"] * 3
    with pytest.raises(AepReconciliationError):
        reconcile_capacity_factor_with_bankable_aep(cfg, "cf_pct-3x")


def test_resolve_billed_matches_engine_normalization() -> None:
    """resolve_billed_capacity_and_factor mirrors the engine's pct + path resolution."""
    from analytics.aep_reconciliation import resolve_billed_capacity_and_factor

    cap, cf = resolve_billed_capacity_and_factor(
        {"project": {"capacity_mw": 100.0, "capacity_factor_pct": 42.0}}
    )
    assert cap == 100.0
    assert cf == pytest.approx(0.42)  # percent → decimal, capacity_factor_pct preferred


# --- robustness: non-positive AEP, bool, JSON-only source -------------------------------


def test_non_positive_bankable_aep_raises() -> None:
    cfg = _lender()
    cfg["expected_results"]["net_aep_p50_gwh"] = 0.0
    with pytest.raises(AepReconciliationError, match="non-positive"):
        reconcile_capacity_factor_with_bankable_aep(cfg, "zero-aep")


def test_bool_is_not_admitted_as_aep() -> None:
    """A YAML true/false must not be coerced to 1.0/0.0 and treated as a reference."""
    refs = collect_bankable_net_aep_gwh({"expected_results": {"net_aep_p50_gwh": True}})
    assert refs == {}


def test_json_only_source_catches_divergence(tmp_path: Path) -> None:
    """With NO expected_results, a divergence is still caught via the aep_summary JSON."""
    import json as _json

    summary = tmp_path / "aep.json"
    summary.write_text(_json.dumps({"net_site_aep_gwh": 133.1}))
    cfg = {
        "project": {
            "capacity_mw": 159.6,
            "capacity_factor": 0.2713,
        },  # implies ~379 GWh
        "resource": {"aep_summary_path": str(summary)},
    }
    with pytest.raises(AepReconciliationError, match="net_site_aep_gwh"):
        reconcile_capacity_factor_with_bankable_aep(cfg, "json-only")


def test_config_default_missing_raises(tmp_path: Path, monkeypatch) -> None:
    """default_tolerance_pct fails loud when defaults.yaml lacks the key."""
    import analytics.aep_reconciliation as mod

    bad = tmp_path / "defaults.yaml"
    bad.write_text("defaults:\n  fx_reference:\n    start_lkr_per_usd: 1\n")
    monkeypatch.setattr(mod, "_DEFAULTS_PATH", bad)
    mod.default_tolerance_pct.cache_clear()
    try:
        with pytest.raises(ValueError, match="aep_reconciliation.tolerance_pct"):
            mod.default_tolerance_pct()
    finally:
        mod.default_tolerance_pct.cache_clear()  # don't leak the cached miss


# --- the API authored-config path is guarded -------------------------------------------


def test_api_inline_divergent_config_is_rejected() -> None:
    """POST /run-pipeline with an inline (dict) authored config still gets reconciled."""
    pytest.importorskip("fastapi")
    from fastapi import HTTPException

    from api.pipeline_api import RunPipelineRequest, run_pipeline

    cfg = _lender()
    cfg["project"]["capacity_mw"] = cfg["project"]["capacity_mw"] * 3  # stale 3×
    with pytest.raises(HTTPException) as exc_info:
        run_pipeline(RunPipelineRequest(config=cfg))
    assert exc_info.value.status_code == 422
    assert "reconcile" in str(exc_info.value.detail)


def test_api_capacity_override_breaking_reconciliation_is_rejected() -> None:
    """A capacity override applied after load is re-reconciled (stale injection caught)."""
    pytest.importorskip("fastapi")
    from fastapi import HTTPException

    from api.pipeline_api import RunPipelineRequest, run_pipeline

    req = RunPipelineRequest(
        config_path=str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"),
        overrides={"project.capacity_mw": 479.0},  # 3× — diverges from the bankable AEP
    )
    with pytest.raises(HTTPException) as exc_info:
        run_pipeline(req)
    assert exc_info.value.status_code == 422
