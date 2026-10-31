"""Debt Planning Module for DutchBay V14 Project Finance.

Author: DutchBay V14 Team, Nov 2025
Version: 3.7 (Dynamic debt timeline + explicit CAPEX guard + balloon treatment)

The engine's code lives in the ``finance.debt`` package, moved there verbatim by
``scripts/refactor/split_debt_v14.py``. This module stays the public surface and
re-exports every name it defined before the move, so import from here.
"""

from __future__ import annotations

import logging

from finance.debt.balloon import (  # noqa: F401
    _balloon_resolution_path,
    _balloon_resolution_stream,
    _maturity_period_index,
    _refinance_disclosure,
    _resize_for_amortization,
    resolve_balloon_treatment,
    resolve_refinance_terms,
)
from finance.debt.capex import (  # noqa: F401
    _extract_capex_base_usd,
    _extract_capex_usd,
)
from finance.debt.constants import (  # noqa: F401
    _AMORT_ANNUITY_STYLES,
    _AMORT_DEFAULT_STYLE,
    _AMORT_SCULPTED_STYLES,
    _AMORT_VALID_STYLES,
    _BALLOON_DEFAULT_TREATMENT,
    _BALLOON_TOL,
    _BALLOON_VALID_TREATMENTS,
    _SERVICE_TOL,
    REFINANCE_TERMS_BASIS,
)
from finance.debt.construction import (  # noqa: F401
    calculate_construction_drawdowns,
    calculate_idc,
)
from finance.debt.dscr_contract import (  # noqa: F401
    _build_dscr_periods,
    _clean_public_dscr_series,
    _finite_dscr,
    _normalize_operating_year,
    _operating_dscr_minimum,
    deprecated_raw_dscr_series,
)
from finance.debt.funding import (  # noqa: F401
    _build_funding,
)
from finance.debt.helpers import (  # noqa: F401
    _as_float,
    _finite_number,
    _get,
    _lookup_case_insensitive,
    _npv,
    _pmt,
    _rate_decimal,
    _section_case_insensitive,
    _truthy_flag,
)
from finance.debt.layer import (  # noqa: F401
    _coverage_ratios,
    apply_debt_layer,
)
from finance.debt.placeholders import (  # noqa: F401
    _FORBID_TOY_FALLBACK_KEY,
    _PLACEHOLDER_WARNS_EMITTED,
    _allow_toy_capex_fallback,
    _warn_placeholder_once,
    reset_placeholder_warn_dedup,
)
from finance.debt.plan import (  # noqa: F401
    plan_debt,
)
from finance.debt.schedules import (  # noqa: F401
    Tranche,
    _annuity_schedule,
    _sculpted_schedule,
    _solve_mix,
)
from finance.debt.schema import (  # noqa: F401
    _register_debt_schema,
)
from finance.debt.sizing import (  # noqa: F401
    _maybe_autosolve_dscr,
    _resolve_downside_ratio,
    _solve_gearing_for_dscr,
    size_debt_with_dual_dscr,
)
from finance.debt.terms import (  # noqa: F401
    _build_cfads_timeline,
    _extract_financing_terms,
    _resolve_construction_periods,
    _resolve_first_operating_period,
    _warn_if_decorative_tranches,
)

logger = logging.getLogger(__name__)


try:  # pragma: no cover - registration must never break the finance engine
    _register_debt_schema()
except Exception:
    logger.exception("Failed to register debt schema; proceeding without it.")


# EOF
