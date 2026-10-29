"""Shared constants for the debt engine (extracted from debt_v14)."""

from __future__ import annotations

# Balloon treatment
_BALLOON_VALID_TREATMENTS = (
    "cash_sweep",
    "refinance",
    "bullet",
    "amortize",
    "legacy_ignore",
)
_BALLOON_DEFAULT_TREATMENT = "cash_sweep"

_AMORT_ANNUITY_STYLES = ("annuity", "fixed")
_AMORT_SCULPTED_STYLES = ("sculpted", "auto")
_AMORT_VALID_STYLES = _AMORT_ANNUITY_STYLES + _AMORT_SCULPTED_STYLES
_AMORT_DEFAULT_STYLE = "sculpted"
_BALLOON_TOL = 1.0
_SERVICE_TOL = 1.0
REFINANCE_TERMS_BASIS = "assumption_no_term_sheet"
_PLACEHOLDER_WARNS_EMITTED: set[str] = set()
