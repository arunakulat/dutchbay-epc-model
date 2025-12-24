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

# FIX: Replace star import with explicit imports to avoid F405 errors
from analytics.casper.casper_payload import (
    CASPER_CONTRACT_VERSION,
    build_casper_payload,
)

__all__ = [
    "CASPER_CONTRACT_VERSION",
    "build_casper_payload",
]
