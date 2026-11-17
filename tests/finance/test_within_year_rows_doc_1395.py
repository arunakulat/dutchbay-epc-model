"""The within-year rows document must describe the engine's keys as they are (#1395 (d)).

``docs/finance/WITHIN_YEAR_ROWS_ALLOCATED_VERSUS_COMPUTED_1395.md`` classifies every annual
row key as allocated, placed, re-derived, year-level or positional. A document like that
goes stale silently when the engine gains a key or the calendar starts writing another
line, so these tests read its table and compare it with the code:

1. The table lists exactly the keys A2 classifies, plus ``year``.
2. Year-level and allocated rows match :data:`YEAR_LEVEL_KEYS` and :data:`FLOW_KEYS`.
3. Placed rows are the calendar's row keys (:data:`EVENT_KINDS`).
4. Re-derived rows are the keys the calendar rewrites beyond the placed ones, observed by
   running it on the committed lender case under its default dates.
5. The worked example's counts in section 3 still hold on that case.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest
import yaml

from finance.event_calendar_v14 import (
    EVENT_KINDS,
    apply_event_calendar,
    resolve_event_calendar,
)
from finance.period_grid_v14 import PeriodGrid
from finance.subannual_rows_v14 import (
    FLOW_KEYS,
    YEAR_LEVEL_KEYS,
    build_subannual_rows,
)

DOC = Path("docs/finance/WITHIN_YEAR_ROWS_ALLOCATED_VERSUS_COMPUTED_1395.md")
LENDER_CASE = "scenarios/dutchbay_lendercase_2025Q4.yaml"
_Placed = Tuple[List[Dict[str, float]], List[Dict[str, float]]]
QUARTERLY = PeriodGrid(resolution="quarterly", periods_per_year=4)

_ROW = re.compile(
    r"^\| `([a-z_]+)` \| (Allocated|Placed|Re-derived|Year-level|Positional) \|"
)


def _doc_table() -> Dict[str, str]:
    table: Dict[str, str] = {}
    for line in DOC.read_text(encoding="utf-8").splitlines():
        match = _ROW.match(line)
        if match:
            key, treatment = match.groups()
            assert key not in table, f"{key} is listed twice"
            table[key] = treatment
    return table


def _keys_with(treatment: str) -> set[str]:
    return {key for key, value in _doc_table().items() if value == treatment}


@pytest.fixture(scope="module")
def lender_rows() -> List[Dict[str, Any]]:
    from finance.cashflow_v14 import build_annual_rows

    with open(LENDER_CASE) as handle:
        return build_annual_rows(yaml.safe_load(handle))


@pytest.fixture(scope="module")
def placed_rows(
    lender_rows: List[Dict[str, Any]],
) -> tuple[List[Dict[str, float]], List[Dict[str, float]]]:
    calendar = resolve_event_calendar(
        {"cashflow": {"resolution": "quarterly"}}, QUARTERLY
    )
    assert calendar is not None
    logging.disable(logging.WARNING)
    try:
        spread = build_subannual_rows(lender_rows, QUARTERLY)
        placed = apply_event_calendar(spread, lender_rows, calendar)
    finally:
        logging.disable(logging.NOTSET)
    return spread, placed


def test_the_table_lists_every_engine_key_once(
    lender_rows: List[Dict[str, Any]],
) -> None:
    listed = set(_doc_table())
    assert listed == FLOW_KEYS | YEAR_LEVEL_KEYS | {"year"}
    assert set(lender_rows[0]) <= listed


def test_year_level_and_positional_rows_match_the_code() -> None:
    assert _keys_with("Year-level") == YEAR_LEVEL_KEYS
    assert _keys_with("Positional") == {"year"}


def test_placed_rows_are_the_calendars_row_keys() -> None:
    assert _keys_with("Placed") == {key for key in EVENT_KINDS.values() if key}


def test_re_derived_rows_are_what_the_calendar_rewrites(placed_rows: _Placed) -> None:
    spread, placed = placed_rows
    changed = {
        key
        for before, after in zip(spread, placed, strict=True)
        for key in before
        if before[key] != after[key]
    }
    placed_keys = _keys_with("Placed")
    assert changed - placed_keys == _keys_with("Re-derived")
    assert _keys_with("Allocated") == FLOW_KEYS - placed_keys - _keys_with("Re-derived")


def test_the_worked_example_still_holds(
    lender_rows: List[Dict[str, Any]], placed_rows: _Placed
) -> None:
    taxed = [int(row["year"]) for row in lender_rows if row["tax_lkr"] > 0]
    assert taxed[0] == 7 and len(taxed) == 14
    assert [int(r["year"]) for r in lender_rows if r["carried_forward_losses"] > 0] == [
        1,
        2,
        3,
        4,
        5,
        6,
    ]
    _, placed = placed_rows
    negative = sorted(
        {int(row["year"]) for row in placed if row["posttax_cfads_lkr"] < 0}
    )
    assert negative == list(range(8, 21))
    assert all(
        row["period_in_year"] == 3.0 for row in placed if row["posttax_cfads_lkr"] < 0
    )
    year_5 = {row["carried_forward_losses"] for row in placed if row["year"] == 5.0}
    assert year_5 == {lender_rows[4]["carried_forward_losses"]}
