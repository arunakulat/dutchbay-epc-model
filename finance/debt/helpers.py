"""Lookup, coercion, annuity and discounting helpers of the debt engine."""

from __future__ import annotations

import copy
import math
from typing import Any, Dict, List, Mapping, Optional, Sequence

from finance.utils import as_float, get_nested


def _lookup_case_insensitive(mapping: Mapping[str, Any], key: str) -> Any:
    if key in mapping:
        return mapping[key]
    key_lower = key.lower()
    for existing_key, value in mapping.items():
        if str(existing_key).lower() == key_lower:
            return value
    return None


def _section_case_insensitive(
    mapping: Mapping[str, Any], key: str
) -> Mapping[str, Any] | None:
    value = _lookup_case_insensitive(mapping, key)
    return value if isinstance(value, Mapping) else None


def _required_number(
    value: Any,
    path: str,
    *,
    minimum: Optional[float] = None,
    maximum: Optional[float] = None,
) -> float:
    """Return a required financing term as a finite float, or refuse naming ``path``.

    The debt engine used to fill an absent gearing, target DSCR, flat downside factor,
    tenor, capacity discount rate or construction-period count with Dutch Bay figures
    (0.70, 1.30, 0.80, 15 years, 8% and two periods). Those terms now come only from the
    scenario YAML; there is no code default (#1429).

    Args:
        value: The declared value, or ``None`` when the key is absent.
        path: The YAML path to name in the refusal, e.g. ``Financing_Terms.debt_ratio``.
        minimum: The smallest value the term may take, inclusive, or ``None`` for no bound.
        maximum: The largest value the term may take, inclusive, or ``None`` for no bound.
            A fraction bounded by 1 is not read as a percentage: ``10`` is refused, not
            taken to mean 10% (#1862).

    Returns:
        The declared value as a float.

    Raises:
        ValueError: If the value is absent, a boolean, not numeric, not finite, or outside
            ``[minimum, maximum]``.
    """
    # A YAML boolean is not a number: ``as_float`` would read ``true`` as 1.0.
    number = None if isinstance(value, bool) else as_float(value, None)
    if number is None or not math.isfinite(number):
        raise ValueError(
            f"{path} is required and must be a finite number (got {value!r}); "
            "there is no code default (#1429). Declare it in the scenario YAML."
        )
    if (minimum is not None and number < minimum) or (
        maximum is not None and number > maximum
    ):
        if maximum is None:
            bound = f"at least {minimum:g}"
        elif minimum is None:
            bound = f"at most {maximum:g}"
        else:
            bound = f"between {minimum:g} and {maximum:g} inclusive"
        raise ValueError(f"{path} must be {bound} (got {value!r}) (#1862).")
    return float(number)


def _get(d: Dict[str, Any], path: List[str], default: Any = None) -> Any:
    return get_nested(d, path, default)


def _as_float(v: Any, default: Optional[float] = None) -> float:
    base_default = 0.0 if default is None else default
    val = as_float(v, base_default)
    return float(val if val is not None else base_default)


def _truthy_flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _pmt(rate: float, nper: int, pv: float) -> float:
    """Level annuity payment for ``pv`` over ``nper`` periods at ``rate``.

    Defensive guard (#585): with ``rate != 0`` and ``nper <= 0`` the annuity
    factor ``(1+rate)**nper - 1`` is 0 (or nonsensical), so fail loud with a
    clear message instead of a raw ``ZeroDivisionError``. The sole engine
    caller (``_annuity_schedule``) already guards ``amort_years > 0``, so this
    never fires on a committed path. The ``rate == 0`` degenerate branch keeps
    its historical ``0.0`` return for ``nper <= 0``.
    """
    if rate == 0:
        return pv / nper if nper > 0 else 0.0
    if nper <= 0:
        raise ValueError(
            f"_pmt: nper={nper} is invalid with a non-zero rate — an annuity "
            "needs at least one amortisation period"
        )
    return pv * (rate * (1 + rate) ** nper) / ((1 + rate) ** nper - 1)


def _npv(cashflows: Sequence[float], rate: float) -> float:
    """Simple NPV helper (no IRR logic here - IRR stays in finance.irr)."""
    if not cashflows:
        return 0.0
    if rate <= -1.0:
        return 0.0

    df = 1.0 + rate
    pv = 0.0
    for t, cf in enumerate(cashflows, start=1):
        pv += float(cf) / (df**t)
    return pv


def _rate_decimal(value: Any, default: float = 0.0) -> float:
    """Normalize a percentage or decimal interest-rate input."""
    raw = _as_float(value, default)
    return raw / 100.0 if raw > 1.0 else raw


def _case_insensitive_key(mapping: Mapping[str, Any], key: str) -> Any:
    """The key :func:`_lookup_case_insensitive` would read for ``key``, or ``None``."""
    if key in mapping:
        return key
    key_lower = key.lower()
    for existing_key in mapping:
        if str(existing_key).lower() == key_lower:
            return existing_key
    return None


def _config_at_debt_ratio(config: Dict[str, Any], ratio: float) -> Dict[str, Any]:
    """``config`` with its gearing set to ``ratio``, sharing every object it does not change.

    The gearing solve and the balloon bisection run :func:`apply_debt_layer` once per trial
    gearing, up to ~180 times per sizing pass, and each trial used to deep-copy the whole
    scenario only to change one number. Since #1451 sizes debt as a fixed point over up to
    25 passes, that copy became most of a pipeline run's wall-clock (#1397's lender case:
    7 passes, ~920 copies, about 70% of the run). This copies only the top-level mapping and
    the ``Financing_Terms`` section, and writes ``debt_ratio`` exactly where the deep-copy
    version did: into a ``Financing_Terms`` dict when there is one, else at the top level.

    It is equivalent to the deep copy only because :func:`apply_debt_layer` reads its
    ``params`` and never mutates them; ``tests/finance/test_gearing_trial_config_copy.py``
    pins both that and the solved gearing against the deep-copy recipe.
    """
    cfg = copy.copy(config)
    fin_key = _case_insensitive_key(cfg, "Financing_Terms")
    fin = cfg.get(fin_key) if fin_key is not None else None
    if isinstance(fin, dict):
        fin = copy.copy(fin)
        fin["debt_ratio"] = ratio
        cfg[fin_key] = fin
    else:
        cfg["debt_ratio"] = ratio
    return cfg


def _finite_number(value: Any) -> bool:
    """True when ``value`` coerces to a finite float (``bool`` excluded)."""
    if isinstance(value, bool):
        return False
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False
