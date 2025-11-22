"""
Integration test: ScenarioAnalytics + schema_guard.

We create:
  * a minimal "good" config that includes corporate tax; and
  * a "bad" config missing the tax block.

With strict=True, ScenarioAnalytics.run() should raise ConfigValidationError
when it encounters the bad config, instead of silently pushing garbage
through the v14 pipeline.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from analytics.schema_guard import ConfigValidationError
from analytics.scenario_analytics import ScenarioAnalytics


def _make_good_config() -> dict:
    return {
        "Financing_Terms": {
            "tenor_years": 20,
        },
        "project": {
            "capacity_mw": 150.0,
            "capacity_factor_pct": 40.0,
        },
        "tariff": {
            "lkr_per_kwh": 20.30,
        },
        "opex": {
            "usd_per_year": 2_400_000.0,
        },
        "tax": {
            "corporate_tax_rate_pct": 24.0,
        },
    }


def _make_bad_config() -> dict:
    cfg = _make_good_config()
    cfg.pop("tax", None)
    return cfg


def test_scenario_analytics_stops_on_missing_corporate_tax(tmp_path: Path) -> None:
    """
    With strict=True, ScenarioAnalytics should raise ConfigValidationError
    when a scenario config is missing the corporate tax rate required by
    the v14 cashflow layer.
    """
    scenarios_dir = tmp_path / "scenarios"
    scenarios_dir.mkdir(parents=True, exist_ok=True)

    good_path = scenarios_dir / "good_case.json"
    bad_path = scenarios_dir / "bad_missing_tax.json"

    good_cfg = _make_good_config()
    bad_cfg = _make_bad_config()

    good_path.write_text(json.dumps(good_cfg), encoding="utf-8")
    bad_path.write_text(json.dumps(bad_cfg), encoding="utf-8")

    sa = ScenarioAnalytics(
        scenarios_dir=scenarios_dir,
        output_path=None,
        strict=True,
    )

    with pytest.raises(ConfigValidationError) as excinfo:
        sa.run()

    msg = str(excinfo.value)
    assert "corporate_tax_rate" in msg or "corporate_tax_rate_pct" in msg
    assert "bad_missing_tax.json" in msg
