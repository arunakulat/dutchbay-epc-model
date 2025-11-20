#!/usr/bin/env python3
"""
Smoke + behaviour tests for dutchbay_v14chat.finance.v14.epc_helper.

We rely only on invariants that are implied by the module's docstrings
and current FX resolution logic:

- The helper exposes `epc_breakdown_dict(config, default_fx_rate=...)`.
- It requires `capex.usd_total` > 0.
- It understands `capex.freight_pct`, `capex.contingency_pct` in [0, 1].
- It resolves an FX rate either from:
    - config["fx"]["base_rate"], or
    - config["fx"]["rate"], or
    - a bare numeric config["fx"], or
    - the default_fx_rate argument.
- It returns a dict with keys:
    base_cost_usd
    freight_pct
    contingency_pct
    fx_rate
    freight_usd
    contingency_usd
    total_usd
    base_cost_lcy
    freight_lcy
    contingency_lcy
    total_lcy
"""

from dutchbay_v14chat.finance.v14.epc_helper import epc_breakdown_dict


EXPECTED_KEYS = {
    "base_cost_usd",
    "freight_pct",
    "contingency_pct",
    "fx_rate",
    "freight_usd",
    "contingency_usd",
    "total_usd",
    "base_cost_lcy",
    "freight_lcy",
    "contingency_lcy",
    "total_lcy",
}


def test_epc_breakdown_basic_with_fx_in_config():
    """
    If FX and percentages are provided in the config, the helper should:

    - Return all documented keys.
    - Echo `capex.usd_total` into `base_cost_usd`.
    - Use the FX from config (fx.base_rate), not the default.
    - Produce a total_usd >= base_cost_usd when any percentage > 0.
    """
    config = {
        "capex": {
            "usd_total": 100_000_000.0,
            "freight_pct": 0.05,
            "contingency_pct": 0.10,
        },
        "fx": {
            "base_rate": 350.0,
        },
    }

    breakdown = epc_breakdown_dict(config)

    # Shape
    assert isinstance(breakdown, dict)
    missing = EXPECTED_KEYS - set(breakdown.keys())
    assert not missing, f"Missing expected keys in EPC breakdown: {missing}"

    # Structural invariants
    assert breakdown["base_cost_usd"] == 100_000_000.0
    assert 0.0 <= breakdown["freight_pct"] <= 1.0
    assert 0.0 <= breakdown["contingency_pct"] <= 1.0
    assert breakdown["fx_rate"] == 350.0

    # Totals should be at least the base cost when there are positive add-ons.
    assert breakdown["total_usd"] >= breakdown["base_cost_usd"]
    # We don't assert an exact FX formula; just sanity-check LKR totals are positive.
    assert breakdown["total_lcy"] > 0


def test_epc_breakdown_uses_default_fx_when_config_missing_fx():
    """
    If the config has no FX section, the helper should fall back to the
    provided `default_fx_rate`.
    """
    config = {
        "capex": {
            "usd_total": 80_000_000.0,
            "freight_pct": 0.0,
            "contingency_pct": 0.0,
        }
        # no "fx" key here
    }

    breakdown = epc_breakdown_dict(config, default_fx_rate=300.0)

    assert isinstance(breakdown, dict)
    missing = EXPECTED_KEYS - set(breakdown.keys())
    assert not missing, f"Missing expected keys in EPC breakdown: {missing}"

    assert breakdown["base_cost_usd"] == 80_000_000.0
    assert breakdown["fx_rate"] == 300.0

    # With zero percentages, total should not be less than base.
    assert breakdown["total_usd"] >= breakdown["base_cost_usd"]
