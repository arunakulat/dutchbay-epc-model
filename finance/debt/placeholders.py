"""Placeholder WARN dedup and toy-capex gates (extracted from debt_v14)."""

from __future__ import annotations

import logging
from typing import Any, Mapping

from finance.debt.constants import _PLACEHOLDER_WARNS_EMITTED
from finance.debt.helpers import _lookup_case_insensitive, _section_case_insensitive

logger = logging.getLogger("finance.debt_v14")

def _warn_placeholder_once(dedup_key: str, message: str) -> None:
    """WARN the first time per process for ``dedup_key``; DEBUG thereafter."""
    if dedup_key in _PLACEHOLDER_WARNS_EMITTED:
        logger.debug("%s (deduplicated; warned once this process)", message)
        return
    _PLACEHOLDER_WARNS_EMITTED.add(dedup_key)
    logger.warning(message)


def reset_placeholder_warn_dedup() -> None:
    """Clear the placeholder warn-once state (test isolation hook, #683)."""
    _PLACEHOLDER_WARNS_EMITTED.clear()


_warned_decorative_tranches = False

_FORBID_TOY_FALLBACK_KEY = "_run_mode_forbids_toy_fallback"


def _truthy_flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _allow_toy_capex_fallback(params: Mapping[str, Any]) -> bool:
    """Return true only when toy fallback is explicitly enabled AND not forbidden."""
    if bool(params.get(_FORBID_TOY_FALLBACK_KEY)):
        return False
    if _truthy_flag(_lookup_case_insensitive(params, "allow_toy_fallback")):
        return True

    testing_cfg = _section_case_insensitive(params, "testing")
    if testing_cfg is not None:
        if _truthy_flag(_lookup_case_insensitive(testing_cfg, "allow_toy_fallback")):
            return True

    debt_cfg = _section_case_insensitive(params, "debt")
    if debt_cfg is not None:
        if _truthy_flag(_lookup_case_insensitive(debt_cfg, "allow_toy_fallback")):
            return True

    return False
