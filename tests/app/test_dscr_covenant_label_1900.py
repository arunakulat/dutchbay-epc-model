"""Regression tests for #1900: DSCR covenant vs. lock-up covenant labeling.

The report labels a scenario DSCR threshold ``"lock-up covenant"`` only when the scenario
declares an active lock-up at that threshold; otherwise a scenario-declared threshold is
labeled ``"minimum DSCR covenant"`` and a solar-assessment fallback threshold names the
model's default minimum DSCR covenant rather than asserting a scenario lock-up covenant.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest
import yaml

from app.api.responses import CaseResult
from app.reports.renderer import render_report_html
from app.reports.report_config import (
    Covenants,
    declared_lockup_threshold,
    dscr_threshold_name,
    load_report_config,
)
from app.reports.report_model import _scenario_covenants, build_report_context
from app.reports.solar_assessment import (
    DSCR_TARGETS,
    _dscr_targets,
    dscr_target_caption,
)
from finance.equity_distribution_v14_hydra import _build_distribution_config

GENERATED_AT = "2026-11-23T00:00:00+00:00"
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _defaults() -> Covenants:
    return load_report_config().covenants


def test_declared_lockup_threshold_distinguishes_declared_vs_fallback() -> None:
    """Only authored positive thresholds count as declared; engine fallback does not."""
    assert declared_lockup_threshold(None) is None
    assert declared_lockup_threshold({}) is None
    assert declared_lockup_threshold(
        {"constraints": {"min_dscr_covenant": 1.30}}
    ) == pytest.approx(1.30)
    assert declared_lockup_threshold(
        {"equity_distribution": {"min_dscr_threshold": 1.25}}
    ) == pytest.approx(1.25)
    assert (
        declared_lockup_threshold(
            {
                "constraints": {"min_dscr_covenant": 1.30},
                "equity_distribution": {"min_dscr_threshold": 0.0},
            }
        )
        is None
    )
    assert (
        declared_lockup_threshold(
            {
                "constraints": {"min_dscr_covenant": 1.30},
                "equity_distribution": {"enabled": False},
            }
        )
        is None
    )


def test_declared_lockup_threshold_reconciles_with_equity_engine() -> None:
    """Independent oracle: matches equity_distribution_v14_hydra when declared."""
    declared_cfg: Dict[str, Any] = {
        "scenario_name": "declared",
        "constraints": {"min_dscr_covenant": 1.30},
    }
    explicit_cfg: Dict[str, Any] = {
        "scenario_name": "explicit",
        "constraints": {"min_dscr_covenant": 1.30},
        "equity_distribution": {"min_dscr_threshold": 1.18},
    }
    undeclared_cfg: Dict[str, Any] = {"scenario_name": "undeclared"}

    assert declared_lockup_threshold(declared_cfg) == pytest.approx(
        _build_distribution_config(declared_cfg).min_dscr_threshold
    )
    assert declared_lockup_threshold(explicit_cfg) == pytest.approx(
        _build_distribution_config(explicit_cfg).min_dscr_threshold
    )
    assert declared_lockup_threshold(undeclared_cfg) is None
    assert _build_distribution_config(
        undeclared_cfg
    ).min_dscr_threshold == pytest.approx(1.25)


def test_dscr_threshold_name_defaults_to_minimum_dscr_covenant_for_scenario() -> None:
    assert dscr_threshold_name("report_defaults") == "lender floor"
    assert dscr_threshold_name("report_defaults", is_lockup=True) == "lender floor"
    assert dscr_threshold_name("scenario") == "minimum DSCR covenant"
    assert dscr_threshold_name("scenario", is_lockup=False) == "minimum DSCR covenant"
    assert dscr_threshold_name("scenario", is_lockup=True) == "lock-up covenant"


@pytest.mark.parametrize(
    "equity_block",
    [
        {"min_dscr_threshold": 0.0},
        {"enabled": False},
        {"min_dscr_threshold": 1.15},
    ],
)
def test_report_uses_minimum_dscr_covenant_when_scenario_declares_no_matching_lockup(
    equity_block: Dict[str, Any],
) -> None:
    """When constraints.min_dscr_covenant is not the lock-up, render minimum DSCR covenant."""
    scenario: Dict[str, Any] = {
        "constraints": {"min_dscr_covenant": 1.30},
        "equity_distribution": equity_block,
    }
    covenants = _scenario_covenants(_defaults(), scenario)
    assert covenants.min_dscr_floor == pytest.approx(1.30)
    assert covenants.min_dscr_floor_source == "scenario"
    assert covenants.min_dscr_floor_is_lockup is False
    assert covenants.min_dscr_floor_name == "minimum DSCR covenant"

    case = CaseResult(
        status="success", scenario_variant="no-lockup", kpis={"min_dscr": 1.22}
    )
    ctx = build_report_context(
        case, generated_at=GENERATED_AT, scenario_config=scenario
    )
    assert any(
        "breaches the 1.30x minimum DSCR covenant (the scenario's covenant" in note
        for note in ctx.verdict.notes
    )
    assert ctx.ic_summary is not None
    flags = [
        flag.detail
        for flag in ctx.ic_summary.red_flags
        if flag.kind == "covenant_breach" and "Minimum DSCR" in flag.detail
    ]
    assert flags == ["Minimum DSCR 1.22x breaches the minimum DSCR covenant."]

    html = " ".join(render_report_html(ctx).split())
    assert "&ge; 1.30x minimum DSCR covenant (scenario)" in html
    assert "1.30x lock-up covenant" not in html


def test_report_uses_lockup_covenant_when_scenario_declares_matching_lockup() -> None:
    """When the scenario's lock-up uses the declared covenant, keep lock-up covenant."""
    scenario: Dict[str, Any] = {
        "constraints": {"min_dscr_covenant": 1.30},
        "equity_distribution": {"min_dscr_threshold": 1.30},
    }
    covenants = _scenario_covenants(_defaults(), scenario)
    assert covenants.min_dscr_floor_is_lockup is True
    assert covenants.min_dscr_floor_name == "lock-up covenant"

    case = CaseResult(
        status="success", scenario_variant="with-lockup", kpis={"min_dscr": 1.22}
    )
    ctx = build_report_context(
        case, generated_at=GENERATED_AT, scenario_config=scenario
    )
    html = " ".join(render_report_html(ctx).split())
    assert "&ge; 1.30x lock-up covenant (scenario)" in html
    assert "minimum DSCR covenant" not in html


def test_solar_assessment_caption_distinguishes_declared_vs_default_lockup() -> None:
    """solar_assessment says lock-up covenant only when declared; otherwise minimum DSCR covenant."""
    floor = DSCR_TARGETS[0]
    declared_caption = dscr_target_caption(
        {
            "best": {"target": floor, "obj": -1.0e8},
            "lockup_covenant": 1.30,
            "lockup_declared": True,
        }
    )
    assert "below the scenario's 1.30x lock-up covenant" in declared_caption

    undeclared_caption = dscr_target_caption(
        {
            "best": {"target": floor, "obj": -1.0e8},
            "lockup_covenant": 1.25,
            "lockup_declared": False,
        }
    )
    assert "below the model's 1.25x default minimum DSCR covenant" in undeclared_caption
    assert "lock-up covenant" not in undeclared_caption
    assert "scenario's" not in undeclared_caption


def test_solar_assessment_dscr_targets_records_lockup_declared_false_when_omitted(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """_dscr_targets marks lockup_declared=False for scenarios without lock-up keys."""
    from types import SimpleNamespace

    import analytics.optimization_v14 as opt_mod
    import app.reports.solar_assessment as sa

    cfg: Dict[str, Any] = {
        "capex": {"usd_total": 100_000_000.0},
        "Financing_Terms": {"target_dscr": 1.30},
    }

    monkeypatch.setattr(
        sa,
        "kpis",
        lambda _cfg: {
            "max_debt_usd": 50_000_000.0,
            "min_dscr": 1.25,
            "project_irr": 0.08,
            "equity_irr": 0.10,
            "equity_npv": 1_000_000.0,
            "equity_covenant_locked_years": 2,
            "lockup_threshold": 1.25,
        },
    )
    monkeypatch.setattr(
        opt_mod,
        "optimize_parameter",
        lambda *_args, **_kwargs: SimpleNamespace(
            best=SimpleNamespace(value=DSCR_TARGETS[0], objective=1_000_000.0)
        ),
    )

    dscr = _dscr_targets(cfg, tmp_path)
    assert dscr["lockup_covenant"] == pytest.approx(1.25)
    assert dscr["lockup_declared"] is False
    caption = dscr_target_caption(dscr)
    assert "minimum DSCR covenant" in caption
    assert "lock-up covenant" not in caption


def test_committed_scenarios_without_lockup_report_none_declared() -> None:
    """Committed scenarios that omit both lock-up keys do not claim a scenario lock-up."""
    sample = _REPO_ROOT / "scenarios" / "kolonnawa_epc_100mw.yaml"
    cfg = yaml.safe_load(sample.read_text(encoding="utf-8"))
    assert declared_lockup_threshold(cfg) is None
    covenants = _scenario_covenants(_defaults(), cfg)
    assert covenants.min_dscr_floor_source == "report_defaults"
    assert covenants.min_dscr_floor_name == "lender floor"
