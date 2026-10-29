"""Debt result schema registration (extracted from debt_v14)."""

from __future__ import annotations

import logging
from typing import Any

from finance.debt.helpers import _finite_number

logger = logging.getLogger("finance.debt_v14")


def _register_debt_schema() -> None:
    """Register debt config specs so ``['cashflow','debt']`` strict validation guards them."""
    from analytics.config_schema import RequiredFieldSpec, register_required_fields

    def _opt_positive(v: Any) -> bool:
        return v is None or (_finite_number(v) and float(v) > 0.0)

    def _opt_nonneg(v: Any) -> bool:
        return v is None or (_finite_number(v) and float(v) >= 0.0)

    def _opt_fraction(v: Any) -> bool:
        return v is None or (_finite_number(v) and 0.0 <= float(v) <= 1.0)

    specs = [
        RequiredFieldSpec(
            module="debt",
            name="debt_tenor_years",
            paths=(
                ("Financing_Terms", "tenor_years"),
                ("Financing_Terms", "term_years"),
                ("debt", "tenor_years"),
                ("debt", "term_years"),
                ("financing", "tenor_years"),
            ),
            required=False,
            severity="error",
            description="Senior-debt tenor in years (positive when declared).",
            validator=_opt_positive,
        ),
        RequiredFieldSpec(
            module="debt",
            name="debt_interest_rate",
            paths=(
                ("Financing_Terms", "interest_rate_nominal"),
                ("Financing_Terms", "interest_rate"),
                ("Financing_Terms", "interest_rate_pct"),
                ("debt", "interest_rate_nominal"),
                ("debt", "interest_rate"),
                ("debt", "interest_rate_pct"),
                ("debt", "coupon"),
            ),
            required=False,
            severity="error",
            description=(
                "Nominal senior-debt interest rate (finite, non-negative when declared)."
            ),
            validator=_opt_nonneg,
        ),
        RequiredFieldSpec(
            module="debt",
            name="debt_gearing_ratio",
            paths=(
                ("Financing_Terms", "debt_ratio"),
                ("debt", "debt_ratio"),
                ("debt", "gearing"),
            ),
            required=False,
            severity="error",
            description="Max gearing / debt ratio, a fraction in [0, 1] when declared.",
            validator=_opt_fraction,
        ),
    ]
    register_required_fields("debt", specs)
