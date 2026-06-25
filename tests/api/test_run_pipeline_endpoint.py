"""Tests for the FastAPI /run-pipeline endpoint (api.pipeline_api).

These call the endpoint FUNCTION directly (run_pipeline(RunPipelineRequest(...))) rather
than going through Starlette's TestClient, which would require httpx2 (not a project dep)
— so they run anywhere the finance suite runs. The HTTP wiring itself (router mounted on
the app, live 200) is verified manually; this locks the request/response contract and the
serialisation of KPIs + sculpted debt + AEP.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from api.pipeline_api import RunPipelineRequest, run_pipeline

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")


def test_run_pipeline_returns_full_report() -> None:
    resp = run_pipeline(RunPipelineRequest(config_path=LENDER))

    # KPIs reproduce the canonical lender case (FX 333.79 + fitted Weibull + the M3e
    # degradation re-baseline: projIRR 5.05%). The round-5 interest-tax-shield fix lifts
    # equity IRR -0.82% -> +2.42% (the levered equity path now bears levered tax).
    assert resp.kpis.project_irr == pytest.approx(0.0505, abs=0.005)
    assert resp.kpis.equity_irr == pytest.approx(0.0242, abs=0.005)
    assert resp.kpis.project_npv_usd is not None
    assert resp.kpis.min_dscr == pytest.approx(1.30, abs=0.02)

    # AEP (bankable, from the committed summary).
    assert resp.aep.net_p50_gwh == pytest.approx(473.8, abs=0.5)
    assert resp.aep.net_p90_gwh == pytest.approx(412.7, abs=1.0)
    assert resp.aep.capacity_factor == pytest.approx(0.339, abs=0.005)

    # Sculpted debt: DSCR-bound, three tranches, a per-period schedule.
    assert resp.debt.debt_total_usd == pytest.approx(100.1e6, rel=0.02)
    assert resp.debt.gearing == pytest.approx(0.6275, abs=0.01)
    assert resp.debt.binding_constraint == "P50"
    assert set(resp.debt.tranches) == {"lkr", "usd", "dfi"}
    assert resp.debt.tranches["usd"].principal_usd > 0
    assert len(resp.debt.schedule) > 15  # full project timeline
    assert all(row.year >= 1 for row in resp.debt.schedule)


def test_overrides_change_economics() -> None:
    """Dotted-key overrides flow into the run — a lower tariff lowers the IRR."""
    base = run_pipeline(RunPipelineRequest(config_path=LENDER))
    cut = run_pipeline(
        RunPipelineRequest(config_path=LENDER, overrides={"tariff.lkr_per_kwh": 16.69})
    )
    assert cut.kpis.project_irr is not None and base.kpis.project_irr is not None
    assert cut.kpis.project_irr < base.kpis.project_irr  # 5c/kWh is worse than 6.1c


def test_inline_config_runs() -> None:
    """A full inline config (no path) runs the same engine."""
    from analytics.scenario_loader import load_scenario_config

    cfg = dict(load_scenario_config(LENDER))
    resp = run_pipeline(RunPipelineRequest(config=cfg))
    assert resp.kpis.project_irr == pytest.approx(0.0505, abs=0.005)
    assert resp.config_path is None


def test_requires_exactly_one_source() -> None:
    with pytest.raises(ValidationError):
        RunPipelineRequest()  # neither
    with pytest.raises(ValidationError):
        RunPipelineRequest(config_path=LENDER, config={"x": 1})  # both


def test_bad_config_path_raises_http_400() -> None:
    with pytest.raises(HTTPException) as exc:
        run_pipeline(RunPipelineRequest(config_path="scenarios/does_not_exist.yaml"))
    assert exc.value.status_code == 400


def test_validation_mode_rejects_undocumented_value() -> None:
    """validation_mode is constrained to the engine's actual modes (strict|off). The
    previously-documented 'lenient' is not accepted by run_v14_pipeline, so it is now
    rejected at the API boundary with a Pydantic ValidationError (422), not deep in the
    engine."""
    with pytest.raises(ValidationError):
        RunPipelineRequest(config_path=LENDER, validation_mode="lenient")


def test_validation_mode_accepts_strict_and_off() -> None:
    assert RunPipelineRequest(config_path=LENDER, validation_mode="strict").validation_mode == "strict"
    assert RunPipelineRequest(config_path=LENDER, validation_mode="off").validation_mode == "off"


def test_inline_config_with_divergent_fx_spot_rejected() -> None:
    """An inline/API config that bypasses load_scenario_config still gets the FX spot
    cross-assert (round-2 gap): divergent fx.rates/start/pinned -> 422, not a
    self-inconsistent lender pack. (MC/sensitivity perturbations go straight to
    run_v14_pipeline and are intentionally NOT cross-asserted.)"""
    import yaml
    from fastapi import HTTPException

    cfg = yaml.safe_load(Path(LENDER).read_text())
    cfg["fx"]["rates"]["lkr_per_usd"] = 250.0  # diverge from start_lkr_per_usd
    with pytest.raises(HTTPException) as exc:
        run_pipeline(RunPipelineRequest(config=cfg))
    assert exc.value.status_code == 422
    assert "inconsistent LKR/USD spot" in str(exc.value.detail)


def test_single_fx_spot_override_fans_out_to_all_pinned_keys() -> None:
    """The documented single-lever fx.start_lkr_per_usd override is fanned out to
    fx.rates.lkr_per_usd and fx.source.pinned_rate, so it stays self-consistent and runs
    (it previously tripped the spot cross-assert -> 422). Round-3 fix."""
    resp = run_pipeline(
        RunPipelineRequest(config_path=LENDER, overrides={"fx.start_lkr_per_usd": 360.0})
    )
    assert resp.scenario_name  # ran to completion, no 422


def test_debt_schedule_dscr_aligns_with_outstanding_and_avg_dscr_nonnull() -> None:
    """Round-4: the debt schedule must align DSCR with debt_outstanding/service (use the
    full-timeline raw_dscr_series, not the compacted operating-only series) and avg_dscr must
    be derived (was structurally null — read a nonexistent dscr_mean key)."""
    resp = run_pipeline(RunPipelineRequest(config_path=LENDER))
    assert resp.debt.avg_dscr is not None and resp.debt.avg_dscr > 1.0
    # construction-period rows (no debt service yet) carry DSCR None — proving the per-row
    # DSCR shares the full timeline with outstanding/service (not the compacted operating
    # series, which would have put an operating DSCR on construction row 1).
    con = [r for r in resp.debt.schedule if (r.debt_service_usd or 0) == 0.0]
    assert con and all(r.dscr is None for r in con)
    op = [r for r in resp.debt.schedule if (r.debt_service_usd or 0) > 0]
    assert op and all(r.dscr is not None for r in op)


def test_contradictory_fx_spot_override_is_rejected_not_silently_collapsed() -> None:
    """Round-4: two FX-spot keys overridden to DIFFERENT values must NOT be silently
    collapsed to one — the contradiction reaches _assert_fx_spot_consistency -> 422."""
    import yaml
    from fastapi import HTTPException

    cfg = yaml.safe_load(Path(LENDER).read_text())
    with pytest.raises(HTTPException) as exc:
        run_pipeline(RunPipelineRequest(
            config=cfg,
            overrides={"fx.rates.lkr_per_usd": 350.0, "fx.source.pinned_rate": 400.0},
        ))
    assert exc.value.status_code == 422
