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
#738 (2026-07-05) turned import levies + indirect taxes ON at the prudent posture and
reversed the revenue-SSCL statutory exemption; net projIRR 2.03% -> 1.46%,
eqIRR -4.99% -> -5.84%, NPV -70.95M -> -79.27M, CFADS 191.22M -> 191.11M.

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
LENDER_PROJECT_IRR: Final[float] = 0.014551597740253388
LENDER_EQUITY_IRR: Final[float] = -0.05841298678542661
LENDER_PROJECT_NPV: Final[float] = -79273039.20645273

# Debt-service coverage. ``min_dscr`` is the #790 conservative fold-corrected covenant
# minimum (the annual number covenants are tested on); ``min_dscr_period`` is the
# per-period sculpt floor, which the dual-DSCR sculpt re-pins at the 1.30 target.
LENDER_MIN_DSCR: Final[float] = 1.285740985294611
LENDER_MIN_DSCR_PERIOD: Final[float] = 1.2999999999999998

# Total cash available for debt service over the modelled life.
LENDER_TOTAL_CFADS_USD: Final[float] = 191111047.68242383

# Prudential (downside) NPV: CFADS discounted at the haircut WACC (prudential_rate =
# WACC + spread), strictly below the base NPV.
LENDER_PROJECT_NPV_PRUDENTIAL: Final[float] = -84724967.65444505
LENDER_PRUDENTIAL_RATE_USED: Final[float] = 0.110202604022396
