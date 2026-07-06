"""Finance-layer grid interconnection helpers (issue #873, D2).

Config-first, KPI-neutral: this package holds only TYPE discriminators and opt-in
gates for the design-stage grid-strength study (:mod:`analytics.grid`). Nothing here
is imported by the finance cashflow engine, so committed scenarios stay byte-identical.

Public surface:
    - :mod:`finance.grid.grid_types` — converter-topology / modelled-grid-tech frozensets
      (the single source of truth for grid classification, CCCDIR) plus the
      ``allow_unvalidated_grid`` opt-in gate (mirrors ``allow_unvalidated_flat_cf`` in
      :mod:`finance.tech_types`).
"""

from __future__ import annotations

__all__ = ["grid_types"]
