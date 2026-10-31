"""Balloon, amortisation and tolerance constants of the debt engine."""

from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# Balloon treatment
# ─────────────────────────────────────────────────────────────────────────────
# A sculpted schedule pays principal = CFADS/DSCR − interest each year. Over a
# FIXED tenor this need not retire the whole loan; the residual is a BALLOON due
# at maturity. The equity waterfall MUST resolve it — otherwise equity collects
# post-maturity CFADS as a free pass and equity IRR is overstated. The treatment
# is config-selectable via ``Financing_Terms.balloon_treatment``:
#   - "cash_sweep" (default): trap post-maturity CFADS to retire the balloon
#       before any equity distribution (prudent-lender cash-sweep covenant).
#   - "refinance":  refinance the balloon over ``refinance_tenor_years`` at
#       ``avg_debt_rate + refinance_rate_premium``; the refi service reduces
#       equity (and may require a sponsor cash call if it exceeds CFADS). Both
#       terms are REQUIRED YAML inputs under ``constraints.refinancing`` (#1396):
#       there is no code fallback, and a refinance that would run past the
#       modelled timeline is refused rather than compressed into its last period.
#   - "bullet":     single lump repayment at maturity (cash call if > CFADS).
#   - "amortize":   resize debt DOWN so the sculpt fully amortises within tenor
#       (no balloon); reported == honest, lowest leverage.
#   - "legacy_ignore": historical (incorrect) behaviour — balloon flagged but
#       never serviced. Retained ONLY to reproduce pre-fix numbers.
_BALLOON_VALID_TREATMENTS = (
    "cash_sweep",
    "refinance",
    "bullet",
    "amortize",
    "legacy_ignore",
)


_BALLOON_DEFAULT_TREATMENT = "cash_sweep"


# ─────────────────────────────────────────────────────────────────────────────
# Amortization style
# ─────────────────────────────────────────────────────────────────────────────
# ``Financing_Terms.amortization_style`` (or compact ``debt.amortization_style``)
# selects the repayment schedule. Whitelisted values (#585, mirroring the
# balloon_treatment whitelist above):
#   - "annuity" / "fixed":  level-payment annuity per tranche.
#   - "sculpted":           DSCR-sculpted (principal = CFADS/target − interest).
#   - "auto":               alias for "sculpted" — the engine solves the sculpt
#       to the DSCR target; committed scenarios use it, so it is an EXPLICIT
#       whitelisted synonym, not a fall-through.
# Any other value previously fell through *silently* to sculpted; it still maps
# to sculpted (byte-identical) but now WARNs like an unknown balloon_treatment.
_AMORT_ANNUITY_STYLES = ("annuity", "fixed")


_AMORT_SCULPTED_STYLES = ("sculpted", "auto")


_AMORT_VALID_STYLES = _AMORT_ANNUITY_STYLES + _AMORT_SCULPTED_STYLES


_AMORT_DEFAULT_STYLE = "sculpted"


_BALLOON_TOL = 1.0  # USD; outstanding balances below this are treated as repaid


_SERVICE_TOL = 1.0  # USD; scheduled service above this marks an active debt period


#: Published label for the refinanced tranche's terms: they are a modelling
#: assumption read from YAML, not a lender term sheet (#1396, P3-COV-03).
REFINANCE_TERMS_BASIS = "assumption_no_term_sheet"
