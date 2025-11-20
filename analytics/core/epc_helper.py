"""
EPC breakdown helper for analytics layer.

This module provides a thin, analytics-facing helper that can derive a
structured EPC breakdown (EPC, freight, contingency, development, etc.)
from a scenario configuration dict.

Design notes
------------
- It is deliberately conservative: if only a total CAPEX is available,
  the full amount is treated as EPC and all sub-components default to 0.
- If a more detailed schema is present (e.g. capex.components.*), those
  numbers are used and any residual is tracked as "other_usd".
- The helper is *read-only* and side-effect free. It never mutates the
  incoming config and is safe to call from reporting, scenario_analytics,
  notebooks, or CLI tools.

Expected schema (flexible)
--------------------------
We support the following shapes, using best-effort fallbacks:

    capex:
      usd_total: 120_000_000
      lkr_total: 45_000_000_000        # ignored here
      components:
        epc:
          usd: 100_000_000
        freight:
          usd: 5_000_000
        contingency:
          usd: 10_000_000
        development:
          usd: 5_000_000

If "components" is absent, we simply expose total_usd and treat it as EPC
for downstream analytics that only care about the headline number.
"""

from __future__ import annotations

from typing import Any, Dict

from finance.utils import as_float, get_nested


def epc_breakdown_from_config(config: Dict[str, Any]) -> Dict[str, float]:
    """
    Derive a structured EPC breakdown from a scenario config.

    Parameters
    ----------
    config:
        Parsed scenario configuration (already loaded via
        analytics.scenario_loader.load_scenario_config). Must be a
        dict-like object with at least a ``capex.usd_total`` key.

    Returns
    -------
    Dict[str, float]
        A dict with the following keys (all floats, USD):

        - ``total_usd``: headline CAPEX in USD (capex.usd_total or 0.0).
        - ``epc_usd``: EPC contract amount; defaults to total_usd
          if not explicitly provided.
        - ``freight_usd``: freight / logistics cost (default 0.0).
        - ``contingency_usd``: contingency allowance (default 0.0).
        - ``development_usd``: development / soft costs (default 0.0).
        - ``other_usd``: residual = max(total - sum(components), 0.0).

    Notes
    -----
    - All lookups are performed via finance.utils.get_nested and
      finance.utils.as_float, so missing or non-numeric values are
      treated as 0.0 rather than raising.
    - This helper does *not* attempt any currency conversion. Inputs are
      assumed to already be USD.
    """
    capex_total_usd = as_float(get_nested(config, ["capex", "usd_total"]), 0.0)

    # Component-level breakdown (all optional)
    epc_usd = as_float(
        get_nested(config, ["capex", "components", "epc", "usd"]),
        capex_total_usd,
    )
    freight_usd = as_float(
        get_nested(config, ["capex", "components", "freight", "usd"]),
        0.0,
    )
    contingency_usd = as_float(
        get_nested(config, ["capex", "components", "contingency", "usd"]),
        0.0,
    )
    development_usd = as_float(
        get_nested(config, ["capex", "components", "development", "usd"]),
        0.0,
    )

    # Residual bucket if users specify only some components
    components_sum = epc_usd + freight_usd + contingency_usd + development_usd
    other_usd = capex_total_usd - components_sum
    if other_usd < 0:
        # Don't go negative; this is purely analytic, not an accounting ledger.
        other_usd = 0.0

    return {
        "total_usd": capex_total_usd,
        "epc_usd": epc_usd,
        "freight_usd": freight_usd,
        "contingency_usd": contingency_usd,
        "development_usd": development_usd,
        "other_usd": other_usd,
    }
