"""Tests for report sensitivity undefined-point outcome reporting (#1488)."""

from __future__ import annotations

from typing import Any, Mapping

from analytics.contracts_v14 import SensitivitySuite, ShockResult, TornadoResult
from app.models.inputs import WindFarmInputs
from app.reports.report_orchestration import (
    ORDINARY_REPORT_SENSITIVITY_PROFILE,
    compute_report_sensitivity,
)
from app.services.report_global_sa import GlobalSABlock, GlobalSADriver
from app.services.report_tornado import compute_report_tornado


def _scenario() -> Mapping[str, Any]:
    return WindFarmInputs(
        site_name="Dutch Bay",
        location="Kalpitiya",
        capacity_mw=150.0,
        capacity_factor=0.339,
        project_life_years=20,
        ppa_price_lkr_per_kwh=26.0,
        ppa_term_years=20,
        capex_total_usd=195_000_000,
        opex_annual_usd=6_000_000,
        fx_start_lkr_per_usd=333.79,
    ).to_scenario_config()


def _global_sa(method: str, n_runs: int) -> GlobalSABlock:
    return GlobalSABlock(
        method=method,
        metric="project_irr",
        n_runs=n_runs,
        drivers=[
            GlobalSADriver(
                name="Tariff",
                mu_star=0.5 if method == "morris" else None,
                sigma=0.1 if method == "morris" else None,
                median_ks=0.5 if method == "pawn" else None,
                ks_cv=0.1 if method == "pawn" else None,
            )
        ],
    )


def _partial_tornado_suite() -> SensitivitySuite:
    nan = float("nan")
    return SensitivitySuite(
        tornado_results=[
            TornadoResult(
                metric_name="project_irr",
                base_metric=0.05,
                impact_abs=0.02,
                shock_results=[
                    ShockResult(
                        label="Tariff",
                        low_case=0.04,
                        high_case=0.06,
                        base_case=0.05,
                        impact_abs=0.02,
                    )
                ],
            ),
            TornadoResult(
                metric_name="project_irr",
                base_metric=0.05,
                impact_abs=nan,
                shock_results=[
                    ShockResult(
                        label="Debt Tenor",
                        low_case=nan,
                        high_case=0.055,
                        base_case=0.05,
                        impact_abs=nan,
                    )
                ],
            ),
        ],
        metadata={
            "undefined_base": False,
            "undefined_points": 1,
            "undefined_drivers": ["Debt Tenor"],
        },
    )


def test_partial_undefined_tornado_records_partial_outcome_not_completed() -> None:
    scenario = _scenario()
    bundle = compute_report_sensitivity(
        scenario,
        profile=ORDINARY_REPORT_SENSITIVITY_PROFILE,
        tornado_computer=lambda sc: compute_report_tornado(
            sc, runner=lambda _path, *, metric: _partial_tornado_suite()
        ),
        morris_computer=lambda _sc, **_kw: _global_sa("morris", 28),
        pawn_computer=lambda _sc, **_kw: _global_sa("pawn", 128),
    )

    assert bundle.tornado is not None
    assert bundle.tornado.undefined_points == 1
    assert bundle.tornado.undefined_drivers == ["Debt Tenor"]
    assert bundle.tornado.has_undefined is True

    by_method = {row.method: row for row in bundle.methods}
    assert by_method["tornado"].outcome == "partial"
    assert by_method["morris"].outcome == "completed"
    assert by_method["pawn"].outcome == "completed"


def test_all_undefined_tornado_records_degraded_outcome() -> None:
    nan = float("nan")
    empty_suite = SensitivitySuite(
        tornado_results=[
            TornadoResult(
                metric_name="project_irr",
                base_metric=nan,
                impact_abs=nan,
                shock_results=[
                    ShockResult(
                        label="Tariff",
                        low_case=nan,
                        high_case=nan,
                        base_case=nan,
                        impact_abs=nan,
                    )
                ],
            )
        ],
        metadata={
            "undefined_base": True,
            "undefined_points": 3,
            "undefined_drivers": ["Tariff"],
        },
    )
    bundle = compute_report_sensitivity(
        _scenario(),
        profile=ORDINARY_REPORT_SENSITIVITY_PROFILE,
        tornado_computer=lambda sc: compute_report_tornado(
            sc, runner=lambda _path, *, metric: empty_suite
        ),
        morris_computer=lambda _sc, **_kw: _global_sa("morris", 28),
        pawn_computer=lambda _sc, **_kw: _global_sa("pawn", 128),
    )
    by_method = {row.method: row for row in bundle.methods}
    assert by_method["tornado"].outcome == "degraded"
