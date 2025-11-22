"""
Unit tests for analytics.config_schema + analytics.schema_guard.

These tests are deliberately light-touch: they prove that

- dutchbay_v14chat.finance.cashflow has registered core required fields
  into the global registry; and
- validate_config_for_v14() catches a missing required field with a clear error.
"""

from __future__ import annotations

import pytest

# Import cashflow to trigger its module-level schema registration
from dutchbay_v14chat.finance import cashflow as cashflow_mod  # noqa: F401

from analytics.config_schema import build_schema_dataframe, get_required_fields
from analytics.schema_guard import ConfigValidationError, validate_config_for_v14


def test_cashflow_fields_are_registered():
    """
    The cashflow module should have registered core required fields
    (including corporate_tax_rate) into the schema registry.
    """
    # Touch the module to make it explicit for readers/tools
    _ = cashflow_mod  # noqa: F841

    specs = get_required_fields("cashflow")
    assert specs, "Expected at least one registered spec for cashflow"

    names = {s.name for s in specs}
    assert "project_life_years" in names
    assert "capacity_mw" in names
    assert "tariff_lkr_per_kwh" in names
    assert "corporate_tax_rate" in names

    df = build_schema_dataframe()
    assert not df.empty
    assert {"module", "name", "path_candidates"}.issubset(df.columns)
    assert (df["module"] == "cashflow").any()


def test_schema_guard_detects_missing_corporate_tax_rate():
    """
    validate_config_for_v14() should raise ConfigValidationError when the
    corporate tax rate is missing for cashflow.

    We build two configs:
      - a 'good' config that passes; and
      - a 'bad' config that omits tax and should fail.
    """
    # Ensure registration has happened
    _ = cashflow_mod  # noqa: F841

    # Minimal "good" config with all cashflow-required fields present
    good_cfg = {
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

    # Should not raise
    validate_config_for_v14(
        raw_config=good_cfg,
        config_path="good_unit_test.yaml",
        modules=["cashflow"],
    )

    # "Bad" config: identical but without tax block
    bad_cfg = dict(good_cfg)
    bad_cfg.pop("tax", None)

    with pytest.raises(ConfigValidationError) as excinfo:
        validate_config_for_v14(
            raw_config=bad_cfg,
            config_path="bad_unit_test.yaml",
            modules=["cashflow"],
        )

    msg = str(excinfo.value)
    # We expect the corporate_tax_rate logical name to be mentioned
    assert "corporate_tax_rate" in msg
