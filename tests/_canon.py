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
#1397 (2026-10-27) sizes the facility, and reports DSCR/LLCR/PLCR, on CFADS bearing the
levered tax the SPV actually pays. Prior: F5-01 (2026-08-16) aligned the first operating cashflow row to COD after the
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
LENDER_PROJECT_IRR: Final[float] = -0.0014208847210721192
LENDER_EQUITY_IRR: Final[float] = -0.09989917555530214
LENDER_PROJECT_NPV: Final[float] = -91574282.40505882

# Debt-service coverage. ``min_dscr`` is the #790 conservative fold-corrected covenant
# minimum (the annual number covenants are tested on); ``min_dscr_period`` is the
# per-period sculpt floor, which the dual-DSCR sculpt re-pins at the 1.30 target.
#
# #1397 separated the two. The sculpt still re-pins every period at 1.30, but the
# conservative annual fold now reads 1.2196 in operating year 1, which also carries the
# orphaned bridge service. ``_solve_gearing_for_dscr`` targets ``min_dscr_period`` and
# does not bind the ``dscr_by_year`` fold, so the nine 0.0025 gearing steps the larger
# levered-CFADS capacity buys all clear the per-period floor while pushing year 1 below
# it.
#
# The steps are only half the account, and a four-way control says so. At the pre-change
# 59,590,051.50 facility WITH the credit-support fee the fold reads 1.30; at this
# change's larger 63,366,885.75 facility with the guarantee and PRI rates zeroed it reads
# 1.30 again, at BOTH trees. Only the larger facility TOGETHER WITH the fee it costs
# drops the fold below the floor. The mechanism is the RS-A8 pre-fee/post-fee seam: the
# solve sculpts on pre-fee coverage CFADS, while the year-1 fold nets that year's senior
# fee out of the cash and divides by the year's service PLUS the orphaned bridge period's
# (see ``finance/debt_v14.py``'s ``dscr_by_year``), so a fee that scales with the facility
# eats the slack that fold had. The hole is pre-existing and #1397 made it visible rather
# than created it -- ``tests/finance/test_senior_fees.py`` already recorded year 1 reading
# ~1.288 for the same reason -- and it is tracked as its own work item (#1353,
# issuecomment-6433557550). Owner decision 2026-10-27: correct the CFADS basis and report
# the year-1 figure honestly rather than hold 1.30 by constraining the solver.
LENDER_MIN_DSCR: Final[float] = 1.2196047509679255
LENDER_MIN_DSCR_PERIOD: Final[float] = 1.3

# Total cash available for debt service over the modelled life, on the PROJECT basis
# (unlevered tax, after the senior credit-support fee) -- the same series project NPV and
# IRR are discounted from. #1397 moved it DOWN, not up, and the reason is the fee, not
# the tax: the larger facility (USD 59.59M -> 63.37M) costs a larger credit-support fee,
# and the project rows bear it. The COVERAGE basis the facility was sized and covenanted
# on moves the other way and is published per row as ``cfads_coverage_usd``: USD 191.99M
# against USD 175.55M for the same rows unlevered, so the interest shield is worth USD
# 16.44M of coverage CFADS. That is the figure audit P2-F4-01 is about; the register's
# USD 17.32M was measured at its own commit. Emitting the coverage total as a KPI of its
# own would change the KPI contract and is deliberately not done here.
LENDER_TOTAL_CFADS_USD: Final[float] = 165691601.54616684

# Prudential (downside) NPV: CFADS discounted at the haircut WACC (prudential_rate =
# WACC + spread), strictly below the base NPV.
LENDER_PROJECT_NPV_PRUDENTIAL: Final[float] = -96233745.9476691
LENDER_PRUDENTIAL_RATE_USED: Final[float] = 0.1117719098011085
