"""#1578 L-12 (D-5): each factor of a per-unit opex component is refused when negative.

``opex.currency_split.components`` lets a component state ``usd_per_unit_year`` and
``units``. Before this guard only their product was checked (``amount >= 0``), so a
negative rate times negative units passed as a positive cost. These tests pin each
factor's own sign check and keep the accepted shapes accepted.
"""

from __future__ import annotations

from typing import Any, Dict

import pytest

from finance.cashflow_v14_params import (
    _resolve_opex_currency_split,
    opex_component_amounts_usd,
)


def _cfg(rate: float, units: float) -> Dict[str, Any]:
    return {
        "opex": {
            "currency_split": {
                "usd_escalation_pct": 2.5,
                "lkr_escalation_pct": 5.0,
                "components": [
                    {
                        "name": "per_unit",
                        "usd_per_unit_year": rate,
                        "units": units,
                        "usd_share": 1.0,
                    },
                    {"name": "flat", "usd_per_year": 400.0, "usd_share": 0.0},
                ],
            }
        }
    }


@pytest.mark.parametrize(
    ("rate", "units", "field"),
    [
        # Both negative: the product is positive, so only a per-factor check sees it.
        (-2.0, -300.0, "usd_per_unit_year"),
        (-2.0, 300.0, "usd_per_unit_year"),
        (2.0, -300.0, "units"),
    ],
)
def test_a_negative_factor_is_refused(rate: float, units: float, field: str) -> None:
    cfg = _cfg(rate, units)
    with pytest.raises(ValueError, match=rf"components\[0\]\.{field} must be >= 0"):
        _resolve_opex_currency_split(cfg)
    # The reporting helper validates through the same function.
    with pytest.raises(ValueError, match=rf"components\[0\]\.{field} must be >= 0"):
        opex_component_amounts_usd(cfg)


@pytest.mark.parametrize(
    ("rate", "units", "share"),
    [
        # Closed form: USD share = (rate * units * 1.0 + 400 * 0.0) / (rate * units + 400).
        (2.0, 300.0, 600.0 / 1000.0),
        (0.0, 300.0, 0.0),
        (2.0, 0.0, 0.0),
    ],
)
def test_non_negative_factors_are_accepted(
    rate: float, units: float, share: float
) -> None:
    split = _resolve_opex_currency_split(_cfg(rate, units))
    assert split is not None
    assert split.usd_share == pytest.approx(share, rel=0.0, abs=1e-15)
    assert opex_component_amounts_usd(_cfg(rate, units))["per_unit"] == rate * units
