"""Single source of truth for the canonical lender-case KPI vector (#955).

These eight values are the canonical economics of the ``dutchbay_lendercase_2025Q4``
scenario. They are pinned by the oracle
``tests/finance/test_multitech_generation.py::test_canonical_lendercase_economics_unchanged``
and were previously echoed as bare literals across a dozen unit tests, so that a
re-baseline had to hand-edit every copy or the echoes silently diverged from the oracle.

This module centralises the full-precision values. Consumers import the named
constants (aliasing to their local name where they already had one) instead of
repeating the literal, so a re-baseline updates this file alone.

Values are the exact ``float`` repr of the pipeline output; keep them at full
precision. When the canon legitimately re-baselines, update the number here and the
one-line "Re-baselined by ..." note in the oracle docstring — nothing else.

Provenance of the current vector (see the oracle docstring for the full history):
F5-01 (2026-08-16) aligned the first operating cashflow row to COD after the
two-period construction window while preserving financial-close FX for capex,
levies and IDC tax basis; reports now reuse those exact annual-row FX rates.

Scope note (#955): this is the *unit-test byte-vector* single source of truth. It is
deliberately kept separate from the *scenario-oracle* JSON fixtures introduced by D3/D3b
(``tests/fixtures/finance/*_expected_kpis.json``), which pin whole-scenario
``expected_results`` for several scenarios. The two share the single-source-of-truth
spirit but are distinct artifacts (Python constants for the lender KPI vector vs
multi-scenario JSON); reconciling them, if ever wanted, is a separate deliberate step.
"""

from __future__ import annotations

from typing import Final

# Base-case (undiscounted / as-modelled) economics.
LENDER_PROJECT_IRR: Final[float] = -0.001166233356501311
LENDER_EQUITY_IRR: Final[float] = -0.07853839579881439
LENDER_PROJECT_NPV: Final[float] = -91810995.06051566

# Debt-service coverage. ``min_dscr`` is the #790 conservative fold-corrected covenant
# minimum (the annual number covenants are tested on); ``min_dscr_period`` is the
# per-period sculpt floor, which the dual-DSCR sculpt re-pins at the 1.30 target.
LENDER_MIN_DSCR: Final[float] = 1.3
LENDER_MIN_DSCR_PERIOD: Final[float] = 1.3

# Total cash available for debt service over the modelled life.
LENDER_TOTAL_CFADS_USD: Final[float] = 166083177.3168602

# Prudential (downside) NPV: CFADS discounted at the haircut WACC (prudential_rate =
# WACC + spread), strictly below the base NPV.
LENDER_PROJECT_NPV_PRUDENTIAL: Final[float] = -96435848.53558263
LENDER_PRUDENTIAL_RATE_USED: Final[float] = 0.11285835226329409
