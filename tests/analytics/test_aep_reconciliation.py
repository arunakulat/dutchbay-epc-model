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
