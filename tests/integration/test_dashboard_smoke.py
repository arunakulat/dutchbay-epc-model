"""Guards for the Streamlit sensitivity dashboard against import rot.

The dashboard (analytics/dashboard/streamlit_app.py) had decayed to importing five
symbols from analytics.sensitivity that no longer exist (SensitivityRequest,
plot_spider_chart, run_multi_metric_tornado, run_tornado_sensitivity,
tornado_suite_to_dataframe) — so `streamlit run` only showed a traceback. These tests
lock the dashboard to the LIVE engine (the same one the FastAPI /run-tornado/ uses) so
the rot cannot silently return. They do not import streamlit (the engine layer is what
rotted), so they run wherever the finance suite runs.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD = REPO_ROOT / "analytics" / "dashboard" / "streamlit_app.py"

# Names the OLD dashboard imported that no longer exist — must never reappear.
_DEAD_SYMBOLS = (
    "SensitivityRequest",
    "plot_spider_chart",
    "run_multi_metric_tornado",
    "run_tornado_sensitivity",
    "tornado_suite_to_dataframe",
)


def test_dashboard_does_not_reference_removed_api() -> None:
    src = DASHBOARD.read_text()
    offenders = [s for s in _DEAD_SYMBOLS if re.search(rf"\b{s}\b", src)]
    assert not offenders, (
        "Dashboard references removed sensitivity API symbols (the rot returned): "
        + ", ".join(offenders)
    )


def test_dashboard_engine_imports_resolve() -> None:
    """The exact import targets the dashboard relies on must exist."""
    from analytics.contracts_v14 import ParameterRangeConfig
    from analytics.core.sensitivity_runner import run_sensitivity_analysis
    from analytics.sensitivity.export import suite_to_records

    assert ParameterRangeConfig is not None
    assert callable(run_sensitivity_analysis)
    assert callable(suite_to_records)


def test_dashboard_data_pipeline_produces_tornado_rows() -> None:
    """The dashboard's default drivers run through the live engine end-to-end."""
    from analytics.contracts_v14 import ParameterRangeConfig
    from analytics.core.sensitivity_runner import run_sensitivity_analysis
    from analytics.sensitivity.export import suite_to_records

    params = [
        ParameterRangeConfig(
            variable_name="tariff.lkr_per_kwh", base_value=20.3, low_value=16.0, high_value=24.0
        ),
        ParameterRangeConfig(
            variable_name="project.capacity_factor", base_value=0.339, low_value=0.30, high_value=0.37
        ),
    ]
    suite = run_sensitivity_analysis(
        str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml"),
        metric="project_irr",
        parameters=params,
    )
    rows = suite_to_records(suite).get("tornado_rows", [])
    assert len(rows) == 2
    needed = {"parameter", "base_value", "low_value", "high_value", "impact_abs"}
    assert needed.issubset(rows[0].keys())
    # tariff is the dominant driver for project IRR (largest absolute impact)
    top = max(rows, key=lambda r: r["impact_abs"])
    assert top["parameter"] == "tariff.lkr_per_kwh"
