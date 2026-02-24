# BACKWARD COMPATIBILITY SHIM
# =========================
#
# This module has been moved to analytics.casper.casper_v14
# This shim will be removed in v15.
#
# Migration Guide:
#   OLD: from analytics.casper_v14 import evaluate_with_casper_tail_risk_and_payload
#   NEW: from analytics.casper import evaluate_with_casper_tail_risk_and_payload
#   OR:  from analytics.casper.casper_v14 import evaluate_with_casper_tail_risk_and_payload
#
# Sprint 9 Migration: CASPER modules consolidated to analytics.casper/
#

from analytics.casper.casper_v14 import (
    evaluate_with_casper_tail_risk_and_payload,
)

__all__ = [
    "evaluate_with_casper_tail_risk_and_payload",
]
