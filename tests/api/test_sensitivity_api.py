"""Regression: the FastAPI sensitivity adapter must import and run (dod-4).

Before this, api/sensitivity_api.py imported names that no longer exist
(`analytics.sensitivity_v14.run`, `analytics.sensitivity_export.tornado_suite_to_dataframe`),
so the module was broken at import — invisible to CI because fastapi isn't a test
dependency and nothing imported it. It is now wired to the canonical engine
``analytics.core.sensitivity_runner.run_sensitivity_analysis``.

This test is skipped when fastapi is not installed (e.g. CI), and exercises the
endpoint function directly (no httpx/TestClient dependency) where it is.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from api.sensitivity_api import SensitivityInput, run_tornado  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
LENDER = str(REPO_ROOT / "scenarios" / "dutchbay_lendercase_2025Q4.yaml")


def test_run_tornado_returns_canonical_rows() -> None:
    payload = SensitivityInput(
        config_path=LENDER,
        parameters=[
            {
                "variable_name": "capex.usd_total",
                "base_value": 150_000_000.0,
                "low_pct": -20.0,
                "high_pct": 20.0,
            },
            {
                "variable_name": "tariff.lkr_per_kwh",
                "base_value": 20.3,
                "low_pct": -15.0,
                "high_pct": 15.0,
            },
        ],
        metric="project_irr",
    )

    rows = run_tornado(payload)

    # #841: run_tornado now returns typed SensitivityTornadoRow models (the frozen
    # public tornado contract), not loose dicts — assert via attribute access.
    assert len(rows) == 2
    params = {row.parameter for row in rows}
    assert params == {"capex.usd_total", "tariff.lkr_per_kwh"}
    for row in rows:
        assert row.metric == "project_irr"
        assert isinstance(row.base_metric, float)
        assert isinstance(row.impact_abs, float)
        assert isinstance(row.low_case, float)
        assert isinstance(row.high_case, float)
