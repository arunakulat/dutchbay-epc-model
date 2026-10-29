"""Debt Planning Module for DutchBay V14 Project Finance.

Behaviour-preserving façade over ``finance.debt.*`` (decomposition of the
former monolithic ``debt_v14.py``). Public import paths are unchanged.

Author: DutchBay V14 Team
"""

from __future__ import annotations

import logging as _logging

from finance.debt.constants import (  # noqa: F401
    REFINANCE_TERMS_BASIS,
    _AMORT_ANNUITY_STYLES,
    _AMORT_DEFAULT_STYLE,
    _AMORT_SCULPTED_STYLES,
    _AMORT_VALID_STYLES,
    _BALLOON_DEFAULT_TREATMENT,
    _BALLOON_TOL,
    _BALLOON_VALID_TREATMENTS,
    _PLACEHOLDER_WARNS_EMITTED,
    _SERVICE_TOL,
)
from finance.debt.helpers import (  # noqa: F401
    _as_float,
    _finite_dscr,
    _finite_number,
    _get,
    _lookup_case_insensitive,
    _npv,
    _pmt,
    _rate_decimal,
    _section_case_insensitive,
)
from finance.debt.placeholders import (  # noqa: F401
    _allow_toy_capex_fallback,
    _truthy_flag,
    _warn_placeholder_once,
    reset_placeholder_warn_dedup,
)
from finance.debt.capex import (  # noqa: F401
    _extract_capex_base_usd,
    _extract_capex_usd,
)
from finance.debt.dscr_contract import (  # noqa: F401
    _build_dscr_periods,
    _clean_public_dscr_series,
    _normalize_operating_year,
    _operating_dscr_minimum,
    deprecated_raw_dscr_series,
)
from finance.debt.terms import (  # noqa: F401
    _build_cfads_timeline,
    _extract_financing_terms,
    _resolve_construction_periods,
    _resolve_first_operating_period,
)
from finance.debt.construction import (  # noqa: F401
    calculate_construction_drawdowns,
    calculate_idc,
)
from finance.debt.schedules import (  # noqa: F401
    Tranche,
    _annuity_schedule,
    _sculpted_schedule,
    _solve_mix,
)
from finance.debt.layer import apply_debt_layer  # noqa: F401
from finance.debt.sizing import (  # noqa: F401
    _maybe_autosolve_dscr,
    _resolve_downside_ratio,
    _solve_gearing_for_dscr,
    size_debt_with_dual_dscr,
)
from finance.debt.balloon import (  # noqa: F401
    _balloon_resolution_stream,
    _maturity_period_index,
    _refinance_disclosure,
    _resize_for_amortization,
    resolve_balloon_treatment,
    resolve_refinance_terms,
)
from finance.debt.funding import (  # noqa: F401
    _build_funding,
    _warn_if_decorative_tranches,
)
from finance.debt.plan import plan_debt  # noqa: F401
from finance.debt.schema import _register_debt_schema  # noqa: F401

_logger = _logging.getLogger(__name__)
try:  # pragma: no cover - registration must never break the finance engine
    _register_debt_schema()
except Exception:
    _logger.exception("Failed to register debt schema; proceeding without it.")

__all__ = [
    "plan_debt",
    "apply_debt_layer",
    "size_debt_with_dual_dscr",
    "resolve_balloon_treatment",
    "resolve_refinance_terms",
    "calculate_construction_drawdowns",
    "calculate_idc",
    "deprecated_raw_dscr_series",
    "reset_placeholder_warn_dedup",
    "REFINANCE_TERMS_BASIS",
    "Tranche",
]
