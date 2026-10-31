"""#1457 real-engine reproduction: the web tornado over an undefined equity IRR.

The 22.8% assessed lender case with its balloon refinanced (the #1396 part B treatment)
has no equity IRR at the base or at most driver points (#1456). On ``main`` before #1457,
``default_analysis`` raised ``KeyError: 'equity_irr'`` here and the ``/analysis`` job
failed. It now returns a tornado whose undefined points are ``nan`` and disclosed. The
engine-level cases are pinned in ``tests/analytics/test_sensitivity_undefined_metric.py``.
"""

from __future__ import annotations

import json
import math

from app.api.responses import AnalysisResult
from app.jobs.analysis_runner import _build_assessed_scenario, default_analysis
from app.jobs.models import AnalysisJobRequest, WindJobRequest
from app.models.inputs import WindFarmInputs


def _wind() -> WindJobRequest:
    return WindJobRequest(
        inputs=WindFarmInputs(
            site_name="Dutch Bay",
            capacity_mw=150.0,
            capacity_factor=0.339,
            project_life_years=20,
            ppa_price_lkr_per_kwh=26.0,
            ppa_term_years=20,
            capex_total_usd=195_000_000,
            opex_annual_usd=6_000_000,
            fx_start_lkr_per_usd=333.79,
        ),
        site_lat=8.33,
        site_lon=79.76,
        turbine_model="iea_reference_10mw",
        num_turbines=15,
        hub_height_m=119.0,
        resource_mode="weibull",
        weibull_a=8.199,
        weibull_k=2.665,
    )


_EXPORT = {
    "scenario": "P75",
    "annual_generation_mwh": 300_000.0,
    "capacity_factor_percent": 22.8,
    "revenue_annual_usd": 20_000_000.0,
    "revenue_cumulative_usd": 400_000_000.0,
    "project_capacity_mw": 150.0,
    "num_turbines": 15,
    "rated_capacity_per_turbine_kw": 10_000.0,
    "ppa_years": 20,
    "tariff_lkr_per_kwh": 20.3,
    "exchange_rate_lkr_usd": 300.0,
}


# A weaker resource than _EXPORT. Until #1504 the refinance case above had no
# solvable equity IRR at the 22.8% export, because the senior fee stayed charged on
# the repaid balloon to the horizon. With the fee on the balance actually
# outstanding it solves (about -97%), so the undefined base this test needs comes
# from a 20% capacity factor instead.
_UNDEFINED_EXPORT = {
    **_EXPORT,
    "capacity_factor_percent": 20.0,
    "annual_generation_mwh": 300_000.0 * 20.0 / 22.8,
}


def test_tornado_over_undefined_equity_irr_reports_it_instead_of_raising() -> None:
    assessed = _build_assessed_scenario(_wind(), _UNDEFINED_EXPORT)
    assessed["Financing_Terms"]["balloon_treatment"] = "refinance"

    out = default_analysis(
        AnalysisJobRequest(analysis_type="tornado", metric="equity_irr", wind=_wind()),
        assessed,
        lambda _step, _message: None,
    )
    result = out["engine_result"]
    meta = result["metadata"]
    bars = result["tornado_results"]
    assert len(bars) >= 7
    assert meta["undefined_base"] is True
    assert all(math.isnan(bar["base_metric"]) for bar in bars)
    assert 0 < meta["undefined_points"] < 1 + 3 * len(bars)
    # Some driver points do solve, and none is reported as 0.0.
    defined = [
        case
        for bar in bars
        for shock in bar["shock_results"]
        for case in (shock["low_case"], shock["high_case"])
        if math.isfinite(case)
    ]
    assert defined and all(case < 0.0 for case in defined)
    # Over the wire the undefined values travel as JSON null, never as NaN.
    wire = json.loads(AnalysisResult(**out).model_dump_json())
    assert wire["engine_result"]["tornado_results"][0]["base_metric"] is None
