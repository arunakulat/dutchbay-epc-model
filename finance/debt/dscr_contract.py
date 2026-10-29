"""Public DSCR series / period contract (F2/F3) — extracted from debt_v14."""

from __future__ import annotations

import math
import warnings
from typing import Any, Dict, List, Mapping, Optional, Sequence

from finance.debt.helpers import _as_float, _finite_dscr

def _clean_public_dscr_series(values: Sequence[Any]) -> List[float]:
    """Drop the undefined sentinels from a PERIOD-indexed DSCR series.

    .. deprecated:: F-2
       This is no longer the public ``dscr_series`` compactor — that compaction WAS the
       F-2 index-space collision, and :func:`plan_debt` now publishes one positional
       series (see its docstring). Two callers remain:

       * :func:`_solve_gearing_for_dscr`, whose target metric is deliberately the minimum
         over every DEFINED period (bridge included) and is held byte-identical here so
         the gearing solve — and therefore canon — does not move; and
       * ``analytics.pipeline_v14_enhanced.run_v14_pipeline_enhanced``, which compacts
         the positional series for ``ScenarioResult.dscr_series``, a ``list[float]``
         contract that the D3B/D3C accepted-origin protocols reject ``None`` from.

       Do not use it for a lender-facing minimum: ``min_dscr`` is taken over OPERATING
       periods folded with ``dscr_by_year`` (see :func:`_operating_dscr_minimum`).

    Only the undefined sentinel is dropped; see :func:`_finite_dscr` for the contract.
    Because the result is compacted, its positions carry NO period or year meaning and it
    is safe for ``min``/``max`` aggregation only.
    """
    clean: List[float] = []
    for value in values:
        numeric = _finite_dscr(value)
        if numeric is not None:
            clean.append(numeric)
    return clean


def _normalize_operating_year(year_raw: Any, annual_row_index: int) -> int:
    """Require an explicit positive integral year from the engine's row map.

    Invalid labels must not become plausible row ordinals on a covenant surface.
    The timeline builder's existing default for an omitted input-row year remains
    explicit in its published map; an invalid supplied label is never substituted.
    """
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
    """Build the single positional DSCR series, each entry labelled with its year.

    This is the F-2/F-3 unification: ONE series in ONE index space (the PERIOD space),
    with every entry carrying the operating year it belongs to, so a consumer FILTERS
    rather than indexing blindly into a compacted list whose positions mean nothing.

    One entry per debt period ``p`` of ``dscr_series``, in period order:

    - ``period`` (``int``) — the debt-period index; equals the list position.
    - ``dscr`` (``float | None``) — that period's DSCR, ``None`` when undefined.
    - ``operating_year`` (``int | None``) — the covenant year label taken from the
      row->period map, or ``None`` when the period maps to NO operating row
      (construction, the synthetic bridge, post-tenor padding). A DSCR at such a period
      is not a covenant observation.
    - ``annual_row_index`` (``int | None``) — the operating row this period serves.
    - ``covenant_dscr`` (``float | None``) — the PER-YEAR coverage from ``dscr_by_year``,
      which folds the orphaned bridge period's scheduled service into operating year 1.
      This is the figure a covenant is actually tested on and it can sit materially BELOW
      the period DSCR (both CEB BESS scenarios: ~0.87-0.91 folded against a 1.3000 period
      floor). Carrying it here is what keeps the fold explicit at the point of use.

    The row->period map is the DEFINITIONAL source of the operating labels — never list
    position, which is what produced the F-3 off-by-one.
    """
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
        # Use the engine's original year key to preserve its per-year fold.
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
    """Minimum DSCR over OPERATING periods only, or ``None`` when there are none.

    A period with no ``operating_year`` maps to no operating row, so its coverage ratio
    is not a covenant observation and must not set the lender-facing floor. Note this is
    only the PERIOD half of the minimum: :func:`plan_debt` folds it against the per-year
    ``dscr_by_year`` table, which carries the bridge service into operating year 1.
    """
    values = [
        entry["dscr"]
        for entry in dscr_periods
        if entry.get("operating_year") is not None and entry.get("dscr") is not None
    ]
    return min(values) if values else None


def deprecated_raw_dscr_series(debt_result: Mapping[str, Any]) -> List[Any]:
    """Read ``raw_dscr_series`` from a ``plan_debt`` result, with the deprecation notice.

    .. deprecated:: F-2
       ``raw_dscr_series`` is now an exact alias of ``dscr_series`` and is retained for
       at least one release and two completed sprints under ``REFACTOR-04``. Read ``dscr_series``
       (positional, one entry per debt period) or ``dscr_periods`` (the same series with
       each entry labelled by ``operating_year``) instead. Removal requires a separate
       reviewed migration after that minimum; see ``docs/DEPRECATIONS.md``.

    The alias key itself CANNOT raise on access: ``plan_debt`` returns a plain ``dict``
    and the D3B/D3C result freezers dispatch on ``type(value) is dict`` /
    ``type(value) in {list, tuple}`` (``analytics/feasibility_execution._freeze_json``),
    so returning a ``dict``/``list`` subclass that warns on ``__getitem__`` would make the
    published result fail the exact-freeze contract outright. This accessor is therefore
    the warning-raising surface, per ``REFACTOR-04``'s ``warnings.warn`` requirement.
    """
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
