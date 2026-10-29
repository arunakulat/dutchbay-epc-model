"""Public DSCR series / period contract (F2/F3) — extracted from debt_v14."""

from __future__ import annotations

import math
import warnings
from typing import Any, Dict, List, Mapping, Optional, Sequence

from finance.debt.helpers import _as_float, _finite_dscr

def _clean_public_dscr_series(values: Sequence[Any]) -> List[float]:
    """Drop the undefined sentinels from a PERIOD-indexed DSCR series."""
    clean: List[float] = []
    for value in values:
        numeric = _finite_dscr(value)
        if numeric is not None:
            clean.append(numeric)
    return clean


def _normalize_operating_year(year_raw: Any, annual_row_index: int) -> int:
    """Require an explicit positive integral year from the engine's row map."""
    try:
        numeric = float(year_raw)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(
            f"annual row {annual_row_index}: operating year must be a positive integer"
        ) from exc
    if (
        isinstance(year_raw, bool)
        or not math.isfinite(numeric)
        or not numeric.is_integer()
        or numeric <= 0
    ):
        raise ValueError(
            f"annual row {annual_row_index}: operating year must be a positive integer"
        )
    return int(numeric)


def _build_dscr_periods(
    dscr_series: Sequence[Any],
    annual_row_debt_period_map: Sequence[Mapping[str, Any]],
    dscr_by_year: Mapping[Any, Any],
) -> List[Dict[str, Any]]:
    """Build the single positional DSCR series, each entry labelled with its year."""
    labels: Dict[int, Dict[str, Any]] = {}
    for mapping in annual_row_debt_period_map:
        try:
            period = int(mapping["debt_period"])
            row_index = int(mapping["annual_row_index"])
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise ValueError(
                "DSCR row map requires debt_period and annual_row_index"
            ) from exc
        if period < 0 or period >= len(dscr_series) or period in labels:
            raise ValueError("DSCR row map has an invalid or duplicate debt period")
        if "year" not in mapping:
            raise ValueError("DSCR row map is missing its operating year")
        year_raw = mapping["year"]
        operating_year = _normalize_operating_year(year_raw, row_index)
        if any(label["operating_year"] == operating_year for label in labels.values()):
            raise ValueError("DSCR row map has a duplicate operating year")
        folded = dscr_by_year.get(year_raw)
        labels[period] = {
            "operating_year": operating_year,
            "annual_row_index": row_index,
            "covenant_dscr": _finite_dscr(folded),
        }

    periods: List[Dict[str, Any]] = []
    for period, value in enumerate(dscr_series):
        label = labels.get(period)
        periods.append(
            {
                "period": period,
                "dscr": _finite_dscr(value),
                "operating_year": None if label is None else label["operating_year"],
                "annual_row_index": (
                    None if label is None else label["annual_row_index"]
                ),
                "covenant_dscr": None if label is None else label["covenant_dscr"],
            }
        )
    return periods


def _operating_dscr_minimum(
    dscr_periods: Sequence[Mapping[str, Any]],
) -> Optional[float]:
    """Minimum DSCR over OPERATING periods only, or ``None`` when there are none."""
    values = [
        entry["dscr"]
        for entry in dscr_periods
        if entry.get("operating_year") is not None and entry.get("dscr") is not None
    ]
    return min(values) if values else None


def deprecated_raw_dscr_series(debt_result: Mapping[str, Any]) -> List[Any]:
    """Read ``raw_dscr_series`` from a ``plan_debt`` result, with the deprecation notice."""
    warnings.warn(
        "debt_result['raw_dscr_series'] is deprecated; removal requires a separate "
        "reviewed migration after at least one release and two completed sprints. "
        "It is now an exact alias of "
        "debt_result['dscr_series']; use 'dscr_series' for the positional series or "
        "'dscr_periods' for the same series labelled by operating year.",
        DeprecationWarning,
        stacklevel=2,
    )
    return list(debt_result.get("raw_dscr_series") or [])
