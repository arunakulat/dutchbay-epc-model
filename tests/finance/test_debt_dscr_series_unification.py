"""Contract tests for the unified DSCR series and the covenant year labels.

Dolphin F-2 + F-3.

**F-2.** ``plan_debt`` published TWO DSCR series in incompatible index spaces:
``dscr_series``, compacted by ``_clean_public_dscr_series`` (which drops the ``None``
sentinels), and ``raw_dscr_series``, positional. ``annual_row_debt_period_map[*]
["debt_period"]`` indexes the POSITIONAL space, so the natural reading
``debt_result["dscr_series"][debt_period]`` silently returned a different period — on the
lender case row 0 maps to period 3, where the positional series holds
``2.604704706563112`` and the compacted series held ``1.3``. There is now ONE positional
series, plus ``dscr_periods``, which labels every entry with the operating year it
belongs to so a consumer FILTERS rather than indexing blindly.

**F-3.** ``_build_debt_covenant_snapshot`` consumed the compacted series and labelled
positions with ``enumerate(..., start=1)``. The compaction dropped the leading
construction ``None``s but NOT the unmapped bridge period, so operating year N was
reported as ``N + (non-operating periods before it)`` — a config-dependent off-by-one no
consumer could correct downstream. Years now come from the row->period map.

Where the weight sits
---------------------

1. :func:`test_min_dscr_is_the_operating_minimum_folded_with_dscr_by_year` and
   :func:`test_ceb_bess_headline_is_the_fold_and_is_pinned` are THE hard gate. The
   headline ``min_dscr`` on both CEB BESS scenarios (0.9069 / 0.8724) is driven entirely
   by the ``dscr_by_year`` FOLD, while the operating-period minimum is 1.3000. Any change
   that "restricts to operating periods" in a way that discards the fold RAISES reported
   coverage and overstates lender protection — a canon move in the flattering direction
   wearing a KPI-neutral cleanup's clothes. These two tests fail loudly if it happens.
2. The covenant tests assert at ``_build_debt_covenant_snapshot``, the published boundary
   a consumer actually observes, and use hostile inputs the committed scenarios cannot
   produce: a breaching bridge period, and a year whose folded coverage breaches while
   its bare period DSCR does not.
3. The sweeps assert the partition — mapped periods carry a year, construction, bridge
   and post-tenor padding carry ``None`` — over every evaluable committed scenario.
"""

from __future__ import annotations

import copy
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from analytics.pipeline_v14_enhanced import (
    PipelineValidationError,
    _build_debt_covenant_snapshot,
)
from analytics.run_modes import POLICIES, resolve_run_mode
from analytics.scenario_loader import load_scenario_config
from finance.cashflow_v14 import build_annual_rows
from finance.debt_v14 import deprecated_raw_dscr_series, plan_debt

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIO_DIR = REPO_ROOT / "scenarios"
SCENARIOS = sorted(SCENARIO_DIR.glob("*.yaml"))
LENDER_CONFIG = SCENARIO_DIR / "dutchbay_lendercase_2025Q4.yaml"

# Mirrors ``tests/finance/test_debt_period_taxonomy.py``: files under scenarios/ that are
# NOT evaluable whole-scenario configs, listed explicitly with a reason rather than caught
# by a blanket ``except``, so a scenario that silently stops evaluating fails here.
NON_EVALUABLE: Dict[str, str] = {
    "bad_missing_tax.yaml": "deliberately invalid fixture (missing corporate_tax_rate)",
    "contracts_edgecase_base_v14.yaml": "contract edge-case fragment, not a full scenario",
    "dscr_sensitivity_example.yaml": "sensitivity parameter file, not a full scenario",
    "dutchbay_mc_enhanced_2025Q4.yaml": "Monte-Carlo parameter file, not a full scenario",
    "dutchbay_sprint17_enhanced.yaml": "partial enhancement overlay, not a full scenario",
    "example_fx_structured_blocks.yaml": "multi-document YAML example, not a single config",
    "kolonnawa_epc_100mw.yaml": "EPC cost fragment without project life or generation",
    "sensitivity_parameters_examples.yaml": "sensitivity parameter file, not a full scenario",
}

EVALUABLE = [p for p in SCENARIOS if p.name not in NON_EVALUABLE]

DSCR_PERIOD_FIELDS = frozenset(
    {"period", "dscr", "operating_year", "annual_row_index", "covenant_dscr"}
)


def _plan_for(path: Path) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """Run the engine exactly as ``run_v14_pipeline`` does, returning (cfg, result)."""
    cfg = load_scenario_config(str(path))
    annual_rows = build_annual_rows(cfg)
    mode = resolve_run_mode(cfg)
    forbid = mode is not None and not POLICIES[mode].allow_toy_capex
    return cfg, plan_debt(
        annual_rows=annual_rows, config=cfg, forbid_toy_fallback=forbid
    )


def _operating_minimum(debt_result: Dict[str, Any]) -> Optional[float]:
    """Minimum period DSCR over OPERATING periods, computed from the PUBLISHED surface."""
    values = [
        entry["dscr"]
        for entry in debt_result["dscr_periods"]
        if entry["operating_year"] is not None and entry["dscr"] is not None
    ]
    return min(values) if values else None


def _fold_minimum(debt_result: Dict[str, Any]) -> Optional[float]:
    """Minimum of the per-year covenant table, computed from the PUBLISHED surface."""
    values = [
        float(v)
        for v in (debt_result.get("dscr_by_year") or {}).values()
        if v is not None and math.isfinite(float(v))
    ]
    return min(values) if values else None


def test_non_evaluable_list_matches_the_committed_scenarios() -> None:
    """The exclusion list may not drift away from what is actually committed."""
    committed = {p.name for p in SCENARIOS}
    unknown = set(NON_EVALUABLE) - committed
    assert not unknown, f"NON_EVALUABLE names files that no longer exist: {unknown}"
    assert EVALUABLE, "no evaluable scenarios found — the sweep would be vacuous"


# ---------------------------------------------------------------------------
# F-2 — one positional series
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("scenario", EVALUABLE, ids=lambda p: p.name)
def test_dscr_series_is_positional_and_indexable_by_debt_period(
    scenario: Path,
) -> None:
    """``dscr_series[debt_period]`` is finally the DSCR of ``debt_period``.

    The compaction is what made it something else. Pinning the LENGTH against
    ``timeline_periods`` is what kills a re-compaction: the compacted series was strictly
    shorter (15 against 23 on the lender case) on every scenario that has an undefined
    period, so restoring it fails here rather than silently downstream.
    """
    _cfg, debt_result = _plan_for(scenario)
    series = debt_result["dscr_series"]
    timeline = int(debt_result["timeline_periods"])

    assert isinstance(series, list)
    assert len(series) == timeline, (
        "dscr_series is no longer positional: it must carry one entry per debt period, "
        f"got {len(series)} for {timeline} periods"
    )
    assert all(v is None or math.isfinite(float(v)) for v in series)

    # The map indexes THIS series. Every mapped period must be in range and must be the
    # value ``dscr_periods`` reports for that same period — one index space, one answer.
    periods = debt_result["dscr_periods"]
    assert len(periods) == timeline
    for entry in debt_result["annual_row_debt_period_map"]:
        period = int(entry["debt_period"])
        assert 0 <= period < len(series)
        assert periods[period]["dscr"] == series[period]


@pytest.mark.parametrize("scenario", EVALUABLE, ids=lambda p: p.name)
def test_raw_dscr_series_is_an_exact_alias_of_dscr_series(scenario: Path) -> None:
    """The deprecated alias carries the SAME series — there is only one left."""
    _cfg, debt_result = _plan_for(scenario)
    assert debt_result["raw_dscr_series"] == debt_result["dscr_series"]


def test_deprecated_accessor_warns_and_returns_the_unified_series() -> None:
    """``REFACTOR-04``: the shim's warning is raised, and it is a DeprecationWarning."""
    _cfg, debt_result = _plan_for(LENDER_CONFIG)
    with pytest.warns(DeprecationWarning, match="raw_dscr_series"):
        values = deprecated_raw_dscr_series(debt_result)
    assert values == debt_result["dscr_series"]


@pytest.mark.parametrize("scenario", EVALUABLE, ids=lambda p: p.name)
def test_dscr_periods_partitions_the_timeline_by_the_row_period_map(
    scenario: Path,
) -> None:
    """Exactly the mapped periods carry an operating year; nothing else does.

    This is the F-3 fix at its source: the labels come from the row->period map, so
    construction periods, the synthetic bridge and post-tenor padding are all ``None`` and
    cannot be mistaken for a covenant observation.
    """
    _cfg, debt_result = _plan_for(scenario)
    periods = debt_result["dscr_periods"]
    row_map = debt_result["annual_row_debt_period_map"]
    first_operating = int(debt_result["first_operating_period"])
    bridge = debt_result["bridge_debt_period"]

    mapped = {int(m["debt_period"]): m for m in row_map}
    labelled = {
        entry["period"] for entry in periods if entry["operating_year"] is not None
    }
    assert labelled == set(mapped), (
        "the set of periods carrying an operating year must be exactly the set the "
        "row->period map names"
    )

    for entry in periods:
        assert set(entry) == DSCR_PERIOD_FIELDS
        period = entry["period"]
        if period in mapped:
            assert entry["operating_year"] == int(float(mapped[period]["year"]))
            assert entry["annual_row_index"] == int(mapped[period]["annual_row_index"])
            assert period >= first_operating
        else:
            assert entry["operating_year"] is None
            assert entry["annual_row_index"] is None
            assert entry["covenant_dscr"] is None

    # Positional identity: entry i describes period i.
    assert [entry["period"] for entry in periods] == list(range(len(periods)))

    # The bridge bears scheduled service but is NOT a covenant observation.
    if bridge is not None:
        assert periods[int(bridge)]["operating_year"] is None
        assert int(bridge) < first_operating

    # Every period before the operating window is non-operating.
    for entry in periods[:first_operating]:
        assert entry["operating_year"] is None


@pytest.mark.parametrize("scenario", EVALUABLE, ids=lambda p: p.name)
def test_covenant_dscr_restates_the_per_year_fold(scenario: Path) -> None:
    """``covenant_dscr`` is ``dscr_by_year``, carried per period rather than re-derived."""
    _cfg, debt_result = _plan_for(scenario)
    by_year = debt_result["dscr_by_year"]
    for entry in debt_result["dscr_periods"]:
        if entry["operating_year"] is None:
            continue
        row = debt_result["annual_row_debt_period_map"][entry["annual_row_index"]]
        expected = by_year.get(row["year"])
        if expected is None:
            assert entry["covenant_dscr"] is None
        else:
            assert entry["covenant_dscr"] == float(expected)


# ---------------------------------------------------------------------------
# THE HARD GATE — min_dscr, and the fold that drives it
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("scenario", EVALUABLE, ids=lambda p: p.name)
def test_min_dscr_is_the_operating_minimum_folded_with_dscr_by_year(
    scenario: Path,
) -> None:
    """``min_dscr`` = min(operating-period minimum, per-year fold minimum). Exactly.

    Both terms are load-bearing and this is asserted with ``==``, not ``approx``:

    * dropping the FOLD raises the headline wherever the bridge's service pushes a year
      below the period floor (both CEB BESS scenarios), overstating lender protection;
    * dropping the OPERATING restriction lets a period that maps to no operating row set
      a lender-facing floor.
    """
    _cfg, debt_result = _plan_for(scenario)
    operating_min = _operating_minimum(debt_result)
    fold_min = _fold_minimum(debt_result)
    published = float(debt_result["min_dscr"])

    assert (
        operating_min is not None
    ), "an evaluable scenario must have operating periods"
    assert fold_min is not None, "an evaluable scenario must have a per-year table"

    assert published == min(operating_min, fold_min)
    # Neither view may be bypassed: the headline can never sit ABOVE either of them.
    assert published <= fold_min
    assert published <= operating_min


@pytest.mark.parametrize(
    ("scenario_name", "expected_min_dscr", "expected_fold_min"),
    [
        ("ceb_bess_10mw_capacity_charge.yaml", 0.9069456485322224, 0.9069456485322224),
        (
            "ceb_solar_bess_nightpeak_10mw.yaml",
            0.8724193845452927,
            0.8724193845452927,
        ),
    ],
)
def test_ceb_bess_headline_is_the_fold_and_is_pinned(
    scenario_name: str, expected_min_dscr: float, expected_fold_min: float
) -> None:
    """The two scenarios where discarding the fold would flatter the headline.

    On both, every OPERATING period sits on the 1.30 sculpt floor while the folded
    year-1 coverage is ~0.87-0.91, because the orphaned bridge period's scheduled
    service is genuinely borne by operating year 1. The published headline is the
    FOLDED figure. If a future change reports the operating-period minimum instead,
    ``min_dscr`` jumps to 1.30 — a ~43% overstatement of the binding covenant ratio —
    and this test fails.
    """
    _cfg, debt_result = _plan_for(SCENARIO_DIR / scenario_name)

    assert float(debt_result["min_dscr"]) == expected_min_dscr
    assert _fold_minimum(debt_result) == expected_fold_min

    operating_min = _operating_minimum(debt_result)
    assert operating_min is not None
    assert operating_min == pytest.approx(1.30, abs=1e-12)
    assert float(debt_result["min_dscr"]) < operating_min, (
        "the fold must still be the binding view on this scenario; if it is not, the "
        "fold has been bypassed and reported coverage has been raised"
    )


def _hostile_negative_year_one_config() -> Dict[str, Any]:
    """A config where the BRIDGE period holds the strict minimum of every view.

    No committed scenario can reach this: on all 21 the bridge DSCR sits comfortably
    above both the operating-period minimum and the fold, so restricting the period
    minimum to operating periods is unobservable there. It becomes observable when
    operating year 1 has NEGATIVE CFADS under an annuity schedule with one
    interest-only year: the bridge carries half of that negative CFADS against a full
    annuity payment, taking it BELOW both the operating minimum and the folded year-1
    figure. Found by sweeping the engine, not by assuming the exclusion could not matter.
    """
    return {
        "project": {"capacity_mw": 100.0, "life_years": 15},
        "capex": {"usd_total": 100_000_000.0},
        "Financing_Terms": {
            "debt_ratio": 0.7,
            "target_dscr": 1.3,
            "interest_only_years": 1,
            "amortization_style": "annuity",
            "construction_periods": 2,
            "tenor_years": 10,
            "mix": {"lkr": 0.0, "usd": 1.0, "dfi": 0.0},
            "rates": {"lkr_nominal": 0.12, "usd_nominal": 0.07, "dfi_nominal": 0.05},
        },
    }


def _hostile_negative_year_one_rows() -> List[Dict[str, Any]]:
    profile = [-4_000_000.0] + [16_000_000.0] * 14
    return [
        {"year": float(i + 1), "cfads_usd": v, "revenue_usd": max(v, 0.0) * 1.4}
        for i, v in enumerate(profile)
    ]


def test_a_bridge_period_below_every_view_still_cannot_set_min_dscr() -> None:
    """HOSTILE: the bridge is the strict minimum of the whole timeline. It is excluded.

    This is the case that discriminates. The bridge period's DSCR is
    ``-0.36856134841854926``, strictly below BOTH the operating-period minimum
    (``-0.33617678960277536``) and the folded minimum (``-0.23088014565999476``), so a
    ``min_dscr`` taken over all defined periods would report the bridge's figure. The
    bridge maps to no operating row; its coverage ratio is not a covenant observation and
    must not become the lender-facing floor.
    """
    debt_result = plan_debt(
        annual_rows=_hostile_negative_year_one_rows(),
        config=_hostile_negative_year_one_config(),
    )
    bridge = debt_result["bridge_debt_period"]
    assert bridge is not None
    bridge_dscr = debt_result["dscr_periods"][int(bridge)]["dscr"]
    operating_min = _operating_minimum(debt_result)
    fold_min = _fold_minimum(debt_result)
    assert operating_min is not None and fold_min is not None

    # The case is only discriminating if the bridge really is below both views.
    assert bridge_dscr == -0.36856134841854926
    assert bridge_dscr < operating_min == -0.33617678960277536
    assert bridge_dscr < fold_min == -0.23088014565999476

    assert float(debt_result["min_dscr"]) == min(operating_min, fold_min)
    assert float(debt_result["min_dscr"]) == -0.33617678960277536
    assert float(debt_result["min_dscr"]) > bridge_dscr


def test_the_hostile_bridge_period_carries_no_covenant_observation() -> None:
    """The same hostile case at the covenant boundary: the bridge dates no breach."""
    config = _hostile_negative_year_one_config()
    debt_result = plan_debt(
        annual_rows=_hostile_negative_year_one_rows(), config=config
    )
    snapshot = _build_debt_covenant_snapshot(config, debt_result)

    assert debt_result["dscr_periods"][2]["operating_year"] is None
    assert snapshot.first_breach_year == 1
    assert snapshot.last_breach_year == 1
    assert snapshot.years_below_threshold == 1


def test_lender_case_min_dscr_and_series_shape_are_pinned() -> None:
    """Canonical lender case: the F-2 receipt, inverted.

    Before F-2 ``dscr_series`` had 15 entries against a 23-period timeline and
    ``dscr_series[3]`` read ``1.3`` while the row-0 period actually held
    ``2.604704706563112``. Both series are now the same positional list.
    """
    _cfg, debt_result = _plan_for(LENDER_CONFIG)

    assert debt_result["timeline_periods"] == 23
    assert len(debt_result["dscr_series"]) == 23
    assert debt_result["first_operating_period"] == 3
    assert debt_result["dscr_series"][3] == 2.604704706563112
    assert debt_result["dscr_periods"][3]["operating_year"] == 1
    assert float(debt_result["min_dscr"]) == 1.3


# ---------------------------------------------------------------------------
# F-3 — the covenant snapshot, at its published boundary
# ---------------------------------------------------------------------------


def _period(
    period: int,
    dscr: Optional[float],
    operating_year: Optional[int] = None,
    covenant_dscr: Optional[float] = None,
    annual_row_index: Optional[int] = None,
) -> Dict[str, Any]:
    return {
        "period": period,
        "dscr": dscr,
        "operating_year": operating_year,
        "annual_row_index": annual_row_index,
        "covenant_dscr": covenant_dscr,
    }


def _covenant_config(threshold: float = 1.30) -> Dict[str, Any]:
    return {"Financing_Terms": {"target_dscr": threshold}}


def _debt_result(periods: List[Dict[str, Any]], min_dscr: float) -> Dict[str, Any]:
    return {
        "dscr_periods": periods,
        "dscr_series": [entry["dscr"] for entry in periods],
        "annual_row_debt_period_map": [
            {
                "debt_period": entry["period"],
                "annual_row_index": entry["annual_row_index"],
                "year": entry["operating_year"],
            }
            for entry in periods
            if entry["operating_year"] is not None
        ],
        "dscr_by_year": {
            entry["operating_year"]: entry["covenant_dscr"]
            for entry in periods
            if entry["operating_year"] is not None
        },
        "min_dscr": min_dscr,
        "balloon_remaining": 0.0,
    }


def test_breach_years_are_operating_years_not_list_positions() -> None:
    """HOSTILE: two construction periods and a bridge sit before operating year 1.

    Position-based labelling reported the breach at operating year 3 as year 4 (its
    position in the compacted series, which retained the bridge) or year 6 (its position
    in the positional series). Only the row->period map gives 3.
    """
    periods = [
        _period(0, None),
        _period(1, None),
        _period(2, 1.4998, None),  # bridge — maps to no operating row
        _period(3, 1.50, 1, 1.50, 0),
        _period(4, 1.45, 2, 1.45, 1),
        _period(5, 1.10, 3, 1.10, 2),
        _period(6, 1.40, 4, 1.40, 3),
    ]
    snapshot = _build_debt_covenant_snapshot(
        _covenant_config(), _debt_result(periods, 1.10)
    )

    assert snapshot.first_breach_year == 3
    assert snapshot.last_breach_year == 3
    assert snapshot.years_below_threshold == 1
    assert snapshot.audit_status == "REVIEW"


def test_a_breaching_non_operating_period_cannot_create_or_date_a_breach() -> None:
    """HOSTILE: the bridge period breaches badly; no operating year does.

    A coverage ratio at a period that maps to no operating row is not a covenant
    observation. Before F-3 the compacted series carried this value at position 1 and it
    was reported as a breach in "year 1".
    """
    periods = [
        _period(0, None),
        _period(1, None),
        _period(2, 0.42, None),  # bridge, deep below the threshold
        _period(3, 1.50, 1, 1.50, 0),
        _period(4, 1.45, 2, 1.45, 1),
    ]
    snapshot = _build_debt_covenant_snapshot(
        _covenant_config(), _debt_result(periods, 0.42)
    )

    assert snapshot.years_below_threshold == 0
    assert snapshot.first_breach_year is None
    assert snapshot.last_breach_year is None
    assert snapshot.audit_status == "PASS"


def test_the_folded_per_year_coverage_is_what_is_tested() -> None:
    """HOSTILE: year 1's bare period DSCR clears the threshold; its FOLD does not.

    This is the CEB BESS shape. Testing the bare period DSCR would report "all covenant
    requirements met" while ``dscr_min`` sat at 0.91 — the flattering contradiction F-3
    removes.
    """
    periods = [
        _period(0, None),
        _period(1, None),
        _period(2, 1.50, None),
        _period(3, 1.30, 1, 0.91, 0),  # period clears; folded coverage breaches
        _period(4, 1.30, 2, 1.30, 1),
        _period(5, 1.30, 3, 1.30, 2),
    ]
    snapshot = _build_debt_covenant_snapshot(
        _covenant_config(), _debt_result(periods, 0.91)
    )

    assert snapshot.first_breach_year == 1
    assert snapshot.last_breach_year == 1
    assert snapshot.years_below_threshold == 1
    assert snapshot.dscr_min == 0.91


def test_covenant_years_survive_a_map_that_does_not_start_at_year_one() -> None:
    """The labels are whatever the map says, not a re-derived ordinal."""
    periods = [
        _period(0, None),
        _period(1, 0.90, None),
        _period(2, 1.20, 7, 1.20, 0),
        _period(3, 1.10, 8, 1.10, 1),
    ]
    snapshot = _build_debt_covenant_snapshot(
        _covenant_config(), _debt_result(periods, 1.10)
    )

    assert snapshot.first_breach_year == 7
    assert snapshot.last_breach_year == 8
    assert snapshot.years_below_threshold == 2


@pytest.mark.parametrize(
    ("scenario_name", "years_below", "first_year", "last_year", "status"),
    [
        ("dutchbay_lendercase_2025Q4.yaml", 0, None, None, "PASS"),
        ("ceb_bess_10mw_capacity_charge.yaml", 3, 1, 7, "FAIL"),
        ("ceb_solar_bess_nightpeak_10mw.yaml", 2, 1, 4, "REVIEW"),
    ],
)
def test_covenant_snapshot_end_to_end_against_the_real_engine(
    scenario_name: str,
    years_below: int,
    first_year: Optional[int],
    last_year: Optional[int],
    status: str,
) -> None:
    """The snapshot built from a REAL ``plan_debt`` result, pinned.

    The CEB BESS rows are the substantive change: their year 1 now breaches, because the
    orphaned bridge service folded into it takes coverage to ~0.87-0.91. Before F-3 both
    reported a first breach several years later and ``ceb_bess`` reported REVIEW while
    its own ``dscr_min`` was 0.9069.
    """
    cfg, debt_result = _plan_for(SCENARIO_DIR / scenario_name)
    snapshot = _build_debt_covenant_snapshot(cfg, debt_result)

    assert snapshot.years_below_threshold == years_below
    assert snapshot.first_breach_year == first_year
    assert snapshot.last_breach_year == last_year
    assert snapshot.audit_status == status
    assert snapshot.dscr_min == float(debt_result["min_dscr"])


def test_a_legacy_shaped_debt_result_fails_loudly_not_silently() -> None:
    """CASPER: no ``dscr_periods`` means the years cannot be labelled — so raise.

    A result carrying only the old ``dscr_series`` has no operating-year labels. Reading
    an absent key and reporting "all covenant requirements met" from an empty list would
    be a silent full-compliance verdict on a result this function cannot assess.
    """
    legacy = {"dscr_series": [1.0, 1.1, 1.2], "min_dscr": 1.0, "balloon_remaining": 0.0}
    with pytest.raises(PipelineValidationError, match="dscr_periods"):
        _build_debt_covenant_snapshot(_covenant_config(), legacy)


def test_breach_years_are_plain_integers() -> None:
    """The map carries float years (``1.0``); the covenant contract types them ``int``."""
    _cfg, debt_result = _plan_for(SCENARIO_DIR / "ceb_bess_10mw_capacity_charge.yaml")
    snapshot = _build_debt_covenant_snapshot(_covenant_config(), debt_result)

    assert type(snapshot.first_breach_year) is int
    assert type(snapshot.last_breach_year) is int
    for entry in debt_result["dscr_periods"]:
        if entry["operating_year"] is not None:
            assert type(entry["operating_year"]) is int


@pytest.mark.parametrize(
    "year", [None, True, 0, -1, 1.5, "missing", float("nan"), float("inf")]
)
def test_plan_debt_rejects_invalid_explicit_operating_year(year: Any) -> None:
    """Invalid input labels cannot silently become a plausible covenant year."""
    rows = _hostile_negative_year_one_rows()
    rows[0]["year"] = year
    with pytest.raises(ValueError, match="operating year"):
        plan_debt(annual_rows=rows, config=_hostile_negative_year_one_config())


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_key",
        "mapped_none",
        "missing_list",
        "truncated",
        "invalid_year",
        "duplicate_year",
    ],
)
def test_real_engine_labels_fail_loudly_when_corrupted(mutation: str) -> None:
    """Replay corrupt published labels against a genuine public debt plan."""
    cfg, debt = _plan_for(LENDER_CONFIG)
    first = debt["first_operating_period"]
    if mutation == "missing_key":
        del debt["dscr_periods"][first]["operating_year"]
    elif mutation == "mapped_none":
        debt["dscr_periods"][first]["operating_year"] = None
    elif mutation == "missing_list":
        debt["dscr_periods"] = None
    elif mutation == "truncated":
        debt["dscr_periods"] = []
    elif mutation == "invalid_year":
        debt["dscr_periods"][first]["operating_year"] = 1.5
    else:
        debt["dscr_periods"][first + 1]["operating_year"] = 1
    with pytest.raises(PipelineValidationError):
        _build_debt_covenant_snapshot(cfg, debt)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_period",
        "missing_dscr",
        "missing_covenant_dscr",
        "missing_annual_row_index",
        "missing_operating_year",
        "erase_all_coverage",
        "null_fold",
        "nonfinite_fold",
        "nonnumeric_fold",
        "replace_fold_with_period",
        "null_period_coverage",
        "shift_year",
        "label_bridge",
        "wrong_row",
        "duplicate_period",
        "float_period",
        "bool_period",
        "bool_row",
        "bool_year",
        "reverse_periods",
        "missing_source_map",
        "missing_source_series",
        "missing_source_fold",
        "missing_fold_year",
        "malformed_map_entry",
        "missing_map_year",
        "invalid_map_year",
        "wrong_map_row_index",
        "duplicate_map_period",
        "wrong_series_length",
        "wrong_timeline_length",
    ],
)
def test_real_covenant_rejects_incomplete_or_contradictory_observations(
    mutation: str,
) -> None:
    """Replay independent DOM/ASR findings with genuine CEB plan controls.

    The source table and map are independent of the corrupted redundant observation.
    A missing/null fold must not substitute the higher bare-period ratio or turn the
    three-breach FAIL into REVIEW/PASS. Dates must still belong to the mapped row.
    """
    cfg, original = _plan_for(SCENARIO_DIR / "ceb_bess_10mw_capacity_charge.yaml")
    before = _build_debt_covenant_snapshot(cfg, original)
    assert (
        before.years_below_threshold,
        before.first_breach_year,
        before.last_breach_year,
        before.audit_status,
    ) == (3, 1, 7, "FAIL")
    debt = copy.deepcopy(original)
    first = debt["first_operating_period"]
    entry = debt["dscr_periods"][first]
    if mutation in {
        "missing_period",
        "missing_dscr",
        "missing_covenant_dscr",
        "missing_annual_row_index",
        "missing_operating_year",
    }:
        del entry[mutation.removeprefix("missing_")]
    elif mutation == "erase_all_coverage":
        for observation in debt["dscr_periods"]:
            del observation["dscr"]
            del observation["covenant_dscr"]
    elif mutation == "null_fold":
        entry["covenant_dscr"] = None
    elif mutation == "nonfinite_fold":
        entry["covenant_dscr"] = float("inf")
    elif mutation == "nonnumeric_fold":
        entry["covenant_dscr"] = "n/a"
    elif mutation == "replace_fold_with_period":
        entry["covenant_dscr"] = entry["dscr"]
    elif mutation == "null_period_coverage":
        entry["dscr"] = None
    elif mutation == "shift_year":
        entry["operating_year"] = 99
    elif mutation == "label_bridge":
        debt["dscr_periods"][debt["bridge_debt_period"]]["operating_year"] = 100
    elif mutation == "wrong_row":
        entry["annual_row_index"] = 999
    elif mutation == "duplicate_period":
        debt["dscr_periods"][0]["period"] = 1
    elif mutation == "float_period":
        entry["period"] = float(first)
    elif mutation == "bool_period":
        debt["dscr_periods"][0]["period"] = False
    elif mutation == "bool_row":
        entry["annual_row_index"] = False
    elif mutation == "bool_year":
        entry["operating_year"] = True
    elif mutation == "reverse_periods":
        debt["dscr_periods"].reverse()
    elif mutation == "missing_source_map":
        del debt["annual_row_debt_period_map"]
    elif mutation == "missing_source_series":
        del debt["dscr_series"]
    elif mutation == "missing_source_fold":
        del debt["dscr_by_year"]
    elif mutation == "missing_fold_year":
        del debt["dscr_by_year"][1]
    elif mutation == "malformed_map_entry":
        debt["annual_row_debt_period_map"][0] = None
    elif mutation == "missing_map_year":
        del debt["annual_row_debt_period_map"][0]["year"]
    elif mutation == "invalid_map_year":
        debt["annual_row_debt_period_map"][0]["year"] = -1
        debt["dscr_by_year"][-1] = debt["dscr_by_year"].pop(1)
    elif mutation == "wrong_map_row_index":
        debt["annual_row_debt_period_map"][0]["annual_row_index"] = 999
    elif mutation == "duplicate_map_period":
        debt["annual_row_debt_period_map"][1]["debt_period"] = first
    elif mutation == "wrong_series_length":
        debt["dscr_series"].pop()
    else:
        debt["timeline_periods"] += 1
    with pytest.raises(PipelineValidationError):
        _build_debt_covenant_snapshot(cfg, debt)
    assert _build_debt_covenant_snapshot(cfg, original) == before


@pytest.mark.parametrize("construction_periods", [0, 3])
def test_no_operating_rows_preserves_explicit_absence(
    construction_periods: int,
) -> None:
    """Exercise no bridge and unmapped padding through plan_debt itself."""
    cfg = _hostile_negative_year_one_config()
    cfg["Financing_Terms"]["construction_periods"] = construction_periods
    debt = plan_debt(annual_rows=[], config=cfg)
    assert debt["bridge_debt_period"] is None
    assert debt["first_operating_period"] == construction_periods
    assert debt["dscr_periods"]
    assert len(debt["dscr_periods"]) == debt["timeline_periods"]
    assert all(p["operating_year"] is None for p in debt["dscr_periods"])
    assert _build_debt_covenant_snapshot(cfg, debt).years_below_threshold == 0


def test_fold_headline_responds_to_cashflow_driver() -> None:
    """The fold-dominated headline is derived, rather than returned from a pin."""
    cfg, baseline = _plan_for(SCENARIO_DIR / "ceb_bess_10mw_capacity_charge.yaml")
    rows = build_annual_rows(cfg)
    rows[0]["cfads_usd"] *= 0.8
    perturbed = plan_debt(annual_rows=rows, config=cfg)
    assert perturbed["min_dscr"] != baseline["min_dscr"]
    assert perturbed["min_dscr"] == _fold_minimum(perturbed)
    assert perturbed["min_dscr"] < baseline["min_dscr"]
