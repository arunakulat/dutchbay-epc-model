"""#785: SILENT FX fallbacks must be disclosed, not just logged.

#736/#784 surfaced the FX *failure* path as a report banner. These tests pin the
complementary SILENT path: ``analytics/fx/fx_builder.py`` can fall back and
*succeed* on stale/default data (malformed ``fx`` block coerced to ``{}``,
missing curve -> flat at spot, empty/zero debt -> degenerate risk profile).
Each fallback now appends a reason to a caller-owned ``degraded`` collector,
the pipeline publishes ``result['fx_integration'].degraded/degraded_reasons``,
and the report renders a render-when-present "FX fallback notice".

Byte-identity guarantee pinned here: the committed lender case takes NO
fallback (empty reasons, ``degraded: False``, no banner), and the collector
default (``None``) preserves legacy behaviour exactly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import pytest

from analytics.fx.fx_builder import (
    compute_fx_curve,
    compute_fx_risk_profile,
    compute_fx_structured_block,
)
from analytics.scenario_loader import load_scenario_config

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")

# Minimal well-formed rows/debt for direct builder calls.
_ROWS: List[Dict[str, Any]] = [
    {"year": 1, "fx_rate": 300.0, "revenue_lkr": 1.0e9, "cfads_usd": 1.0e6},
    {"year": 2, "fx_rate": 310.0, "revenue_lkr": 1.0e9, "cfads_usd": 1.0e6},
]
_ROWS_NO_FX: List[Dict[str, Any]] = [
    {"year": 1, "revenue_lkr": 1.0e9, "cfads_usd": 1.0e6},
    {"year": 2, "revenue_lkr": 1.0e9, "cfads_usd": 1.0e6},
]
_DEBT: Dict[str, Any] = {
    "principal_by_tranche": {"lkr": 0.0, "usd": 50.0e6, "dfi": 0.0},
    "debt_outstanding": [50.0e6, 40.0e6],
}


def test_malformed_fx_block_discloses_on_both_builders() -> None:
    """A present-but-non-mapping fx block degrades to defaults AND says so."""
    cfg: Dict[str, Any] = {"fx": "not-a-mapping", "project": {"life_years": 2}}
    degraded: List[str] = []
    compute_fx_structured_block(
        config=cfg, debt_result=_DEBT, annual_rows=_ROWS, degraded=degraded
    )
    compute_fx_curve(config=cfg, annual_rows=_ROWS_NO_FX, degraded=degraded)
    joined = " | ".join(degraded)
    assert "not a mapping" in joined
    assert "structured block" in joined or "FX structured block" in joined
    assert "curve" in joined.lower()
    assert len(degraded) >= 2


def test_flat_curve_fallback_disclosed() -> None:
    """No explicit or parametric curve -> flat-at-spot substitution is disclosed."""
    # fx block present (well-formed) but with neither curve nor annual_depr:
    # the parametric derivation cannot resolve -> flat fallback.
    cfg: Dict[str, Any] = {"fx": {"rates": {"lkr_per_usd": 300.0}}}
    degraded: List[str] = []
    compute_fx_curve(config=cfg, annual_rows=_ROWS_NO_FX, degraded=degraded)
    assert any("FLAT curve" in r for r in degraded), degraded


def test_degenerate_risk_profile_disclosed() -> None:
    """No volumetry -> minimal placeholder profile is disclosed, not silent."""
    cfg: Dict[str, Any] = {"fx": {"start_lkr_per_usd": 300.0}}
    degraded: List[str] = []
    block = compute_fx_structured_block(
        config=cfg,
        debt_result={"principal_by_tranche": {}, "debt_outstanding": []},
        annual_rows=[],
        degraded=degraded,
    )
    curve = compute_fx_curve(config=cfg, annual_rows=_ROWS, degraded=degraded)
    profile = compute_fx_risk_profile(fx_block=block, fx_curve=curve, degraded=degraded)
    assert profile.var_95_usd_million == pytest.approx(0.0)
    assert any("degenerate minimal placeholder" in r for r in degraded), degraded


def test_zero_peak_debt_arm_disclosed() -> None:
    """Non-empty volumetry but zero peak debt -> the SECOND degenerate arm fires."""
    cfg: Dict[str, Any] = {"fx": {"start_lkr_per_usd": 300.0}}
    degraded: List[str] = []
    block = compute_fx_structured_block(
        config=cfg,
        debt_result={
            "principal_by_tranche": {"lkr": 0.0, "usd": 0.0, "dfi": 0.0},
            "debt_outstanding": [0.0, 0.0],
        },
        annual_rows=_ROWS,
        degraded=degraded,
    )
    curve = compute_fx_curve(config=cfg, annual_rows=_ROWS, degraded=degraded)
    profile = compute_fx_risk_profile(fx_block=block, fx_curve=curve, degraded=degraded)
    assert profile.var_95_usd_million == pytest.approx(0.0)
    # Either degenerate arm discloses; with rows present and zero principal the
    # zero-peak-debt arm is the one that must have fired if volumetry existed.
    assert any("degenerate minimal placeholder" in r for r in degraded), degraded


def test_curve_shape_and_uncertainty_and_strategy_fallbacks_disclosed() -> None:
    """The review-surfaced trio: non-mapping fx.curve, non-positive
    uncertainty_pct, unknown strategy — all disclosed (#785 round 2)."""
    degraded: List[str] = []
    # (a) fx.curve as a bare list loses the explicit curve silently.
    compute_fx_curve(
        config={"fx": {"rates": {"lkr_per_usd": 300.0}, "curve": [300.0, 310.0]}},
        annual_rows=_ROWS,
        degraded=degraded,
    )
    assert any("fx.curve is not a mapping" in r for r in degraded), degraded
    # (b) unknown strategy token -> label-only 'blended' substitution.
    degraded2: List[str] = []
    compute_fx_structured_block(
        config={"fx": {"strategy": "yolo_hedge"}},
        debt_result=_DEBT,
        annual_rows=_ROWS,
        degraded=degraded2,
    )
    assert any("fx.strategy" in r and "blended" in r for r in degraded2), degraded2
    # (c) declared-but-non-positive uncertainty_pct replaced by the 0.05 default
    # (VaR-moving) — via the integration layer that owns the shock resolution.
    from analytics.contracts_v14 import ScenarioResult
    from analytics.fx.fx_integration import integrate_fx_into_scenario_result

    base = ScenarioResult(
        scenario_name="t",
        config_path="<memory>",
        project_npv=0.0,
        project_irr=0.0,
        dscr_series=[],
        min_dscr=0.0,
        max_debt_usd=0.0,
    )
    degraded3: List[str] = []
    integrate_fx_into_scenario_result(
        scenario_result=base,
        config={"fx": {"start_lkr_per_usd": 300.0, "uncertainty_pct": 0.0}},
        debt_result=_DEBT,
        annual_rows=_ROWS,
        degraded_out=degraded3,
    )
    assert any(
        "uncertainty_pct" in r and "0.05 default" in r for r in degraded3
    ), degraded3


def test_default_none_collector_is_legacy_identical() -> None:
    """degraded=None (the default) must not change ANY output value — all three
    builders (review MINOR-2: pin the full set, not just the curve)."""
    import dataclasses

    cfg: Dict[str, Any] = {"fx": {"rates": {"lkr_per_usd": 300.0}}}
    curve_none = compute_fx_curve(config=cfg, annual_rows=_ROWS_NO_FX)
    collector: List[str] = []
    curve_list = compute_fx_curve(
        config=cfg, annual_rows=_ROWS_NO_FX, degraded=collector
    )
    assert dataclasses.asdict(curve_none) == dataclasses.asdict(curve_list)
    assert collector  # the fallback fired and was recorded

    bad_cfg: Dict[str, Any] = {"fx": "garbage"}
    blk_none = compute_fx_structured_block(
        config=bad_cfg, debt_result=_DEBT, annual_rows=_ROWS
    )
    blk_list = compute_fx_structured_block(
        config=bad_cfg, debt_result=_DEBT, annual_rows=_ROWS, degraded=[]
    )
    assert dataclasses.asdict(blk_none) == dataclasses.asdict(blk_list)

    prof_none = compute_fx_risk_profile(fx_block=blk_none, fx_curve=curve_none)
    prof_list = compute_fx_risk_profile(
        fx_block=blk_none, fx_curve=curve_none, degraded=[]
    )
    assert dataclasses.asdict(prof_none) == dataclasses.asdict(prof_list)


def test_lendercase_pipeline_is_clean_and_block_carries_new_keys() -> None:
    """The committed lender case takes NO silent fallback; block keys additive."""
    from analytics.pipeline_v14_enhanced import run_v14_pipeline

    result = run_v14_pipeline(config=load_scenario_config(LENDER))
    fx = result["fx_integration"]
    assert fx["succeeded"] is True
    assert fx["warning"] is None
    assert fx["degraded"] is False
    assert fx["degraded_reasons"] == []


def test_pipeline_discloses_degraded_run() -> None:
    """A VaR-moving silent substitution flows through to the pipeline block.

    The FX overlay is reporting-only, so the run still SUCCEEDS — that is
    exactly why the disclosure matters. Uses fx.uncertainty_pct: 0.0 (declared,
    non-positive, silently replaced by the 0.05 default) — schema-valid, so the
    whole pipeline runs and the disclosure must surface in fx_integration.
    """
    from analytics.pipeline_v14_enhanced import run_v14_pipeline

    cfg = dict(load_scenario_config(LENDER))
    fx_cfg = dict(cfg["fx"])
    fx_cfg["uncertainty_pct"] = 0.0
    cfg["fx"] = fx_cfg
    result = run_v14_pipeline(config=cfg)
    fx = result["fx_integration"]
    assert fx["succeeded"] is True
    assert fx["degraded"] is True
    assert any("uncertainty_pct" in r for r in fx["degraded_reasons"])

    # Integration-level proof of the malformed-block flow as well:
    from analytics.contracts_v14 import ScenarioResult
    from analytics.fx.fx_integration import integrate_fx_into_scenario_result

    base = ScenarioResult(
        scenario_name="t",
        config_path="<memory>",
        project_npv=0.0,
        project_irr=0.0,
        dscr_series=[],
        min_dscr=0.0,
        max_debt_usd=0.0,
    )
    reasons: List[str] = []
    integrate_fx_into_scenario_result(
        scenario_result=base,
        config={"fx": "garbage"},
        debt_result={"principal_by_tranche": {}, "debt_outstanding": []},
        annual_rows=_ROWS,
        degraded_out=reasons,
    )
    assert reasons, "malformed fx block must be disclosed via degraded_out"


def test_report_note_renders_when_degraded_and_omitted_when_clean() -> None:
    """_build_fx_fallback_note: render-when-present semantics."""
    from app.reports.report_model import _build_fx_fallback_note

    clean = {
        "fx_integration": {
            "attempted": True,
            "succeeded": True,
            "warning": None,
            "degraded": False,
            "degraded_reasons": [],
        }
    }
    assert _build_fx_fallback_note(clean) is None
    assert _build_fx_fallback_note(None) is None
    assert _build_fx_fallback_note({}) is None
    # Legacy result without the #785 keys (old runs): no note, no crash.
    assert (
        _build_fx_fallback_note(
            {"fx_integration": {"attempted": True, "succeeded": True}}
        )
        is None
    )

    degraded = {
        "fx_integration": {
            "attempted": True,
            "succeeded": True,
            "warning": None,
            "degraded": True,
            "degraded_reasons": ["fx config block is not a mapping (got str)"],
        }
    }
    note = _build_fx_fallback_note(degraded)
    assert note is not None
    assert "FALLBACK" in note
    assert "not a mapping" in note

    # R-4: a FAILED integration must NOT render the "completed on fallback
    # inputs" note (the #736 failure banner owns that run) even when reasons
    # were collected before the failure.
    failed = {
        "fx_integration": {
            "attempted": True,
            "succeeded": False,
            "warning": "FX integration failed: boom",
            "degraded": True,
            "degraded_reasons": ["flat curve substituted before the failure"],
        }
    }
    assert _build_fx_fallback_note(failed) is None
