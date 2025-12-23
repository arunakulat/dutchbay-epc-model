# BACKWARD COMPATIBILITY SHIM
# =========================
#
# This module has been moved to analytics.casper.casper_payload
# This shim will be removed in v15.
#
# Migration Guide:
#   OLD: from analytics.casper_payload import build_casper_payload, CASPER_CONTRACT_VERSION
#   NEW: from analytics.casper import build_casper_payload, CASPER_CONTRACT_VERSION
#   OR:  from analytics.casper.casper_payload import build_casper_payload
#
# Sprint 9 Migration: CASPER modules consolidated to analytics.casper/
#

from analytics.casper.casper_payload import *  # noqa: F401, F403

__all__ = [
    "CASPER_CONTRACT_VERSION",
    "build_casper_payload",
]
