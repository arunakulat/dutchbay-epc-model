"""Contract tests for the debt period taxonomy published by ``plan_debt``.

Dolphin F-6. ``plan_debt``'s public result used to omit the period taxonomy the
engine resolves internally: ``_resolve_construction_periods(cfg)`` returned 2 for
the lender case while ``debt_result.get("construction_periods")`` returned ``None``
(the key was absent — the value reached callers only under the different name
``construction_years``), and the bridge index was reachable only as
``cfads_bridge_debt_period``. ``first_operating_period`` was not derivable at all
without knowing the engine's internal bridge convention. A consumer holding a
``debt_result`` therefore could not tell which debt periods are operating.

Three tests carry the weight here:

1. :func:`test_scenario_sweep_is_additive_and_taxonomy_is_consistent` — the
   byte-identity sweep, run over every evaluable committed scenario. It pins the
   exact set of pre-existing published keys, so a rename or removal fails, and
   asserts the three additive keys agree with the pre-existing surface they
   restate. Because each new key is *derived from* an existing published key, that
   agreement is what makes the change provably additive rather than merely
   green: nothing else can have moved.
2. The hostile cases the committed scenarios cannot reach — every committed
   scenario has ``construction_periods == 2`` and a bridge, so
   ``construction_periods == 0``, a bridge-less timeline and a first mapped period
   of 0 are only reachable synthetically.
3. :func:`test_dscr_index_space_collision_is_still_present` — an executable pin on
   the hazard the ``plan_debt`` docstring warns about, so the warning cannot go
   stale silently.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, cast

import pytest

from analytics.evaluation_v14 import evaluate_with_overrides
from analytics.run_modes import POLICIES, resolve_run_mode
from analytics.scenario_loader import load_scenario_config
from finance.cashflow_v14 import build_annual_rows
from finance.debt_v14 import (
    _build_cfads_timeline,
    _resolve_construction_periods,
    _resolve_first_operating_period,
    plan_debt,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIO_DIR = REPO_ROOT / "scenarios"
SCENARIOS = sorted(SCENARIO_DIR.glob("*.yaml"))
LENDER_CONFIG = str(SCENARIO_DIR / "dutchbay_lendercase_2025Q4.yaml")

# The three keys this dolphin adds.
TAXONOMY_KEYS = frozenset(
    {"construction_periods", "bridge_debt_period", "first_operating_period"}
)

# Every key ``plan_debt`` published BEFORE the taxonomy was added, captured from
# the pre-change engine across all evaluable scenarios (the set is identical for
# each). This is the additive-only guard: the sweep asserts that the published
# surface is exactly this set plus TAXONOMY_KEYS, so a removal, a rename or an
# unreviewed extra key fails here rather than downstream in a consumer.
PRE_EXISTING_KEYS = frozenset(
    {
        "annual_row_debt_period_map",
        "audit_status",
        "avg_debt_rate",
        "balloon_covenant_breach",
        "balloon_pct",
        "balloon_remaining",
        "balloon_residual",
        "balloon_resolution",
        "balloon_treatment",
        "cfads_bridge_debt_period",
        "construction_years",
        "debt_outstanding",
        "debt_schedules",
        "debt_service_total",
        "debt_total",
        "dfi",
        "dscr_by_year",
        "dscr_series",
        "dual_dscr",
        "funding",
        "fx_avg",
        "fx_max",
        "fx_min",
        "idc_by_tranche",
        "interest_total",
        "lkr",
        "llcr",
        "max_balloon_pct",
        "min_dscr",
        "plcr",
        "principal_by_tranche",
        "raw_dscr_series",
        "senior_fee_rate",
        "senior_fee_usd",
        "tenor_years",
        "timeline_periods",
        "total_idc",
        "total_idc_m",
        "total_service",
        "usd",
    }
)

# Files under scenarios/ that are NOT evaluable whole-scenario configs, with the
# reason each is excluded. Listed EXPLICITLY rather than caught with a blanket
# ``except``: a bare try/skip would silently absorb a genuine regression that made
# a working scenario stop evaluating. A new file must either evaluate or be added
# here deliberately.
NON_EVALUABLE: dict[str, str] = {
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


def _plan_for(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run the engine exactly as ``run_v14_pipeline`` does, returning (cfg, result)."""
    cfg = load_scenario_config(str(path))
    annual_rows = build_annual_rows(cfg)
    mode = resolve_run_mode(cfg)
    forbid = mode is not None and not POLICIES[mode].allow_toy_capex
    return cfg, plan_debt(
        annual_rows=annual_rows, config=cfg, forbid_toy_fallback=forbid
    )


def _mapped_periods(debt_result: dict[str, Any]) -> list[int]:
    return [
        int(entry["debt_period"])
        for entry in (debt_result.get("annual_row_debt_period_map") or [])
    ]


def test_non_evaluable_list_matches_the_committed_scenarios() -> None:
    """The exclusion list may not drift away from what is actually committed."""
    committed = {p.name for p in SCENARIOS}
    unknown = set(NON_EVALUABLE) - committed
    assert not unknown, f"NON_EVALUABLE names files that no longer exist: {unknown}"
    assert EVALUABLE, "no evaluable scenarios found — the sweep would be vacuous"


@pytest.mark.parametrize("scenario", EVALUABLE, ids=lambda p: p.name)
def test_scenario_sweep_is_additive_and_taxonomy_is_consistent(scenario: Path) -> None:
    """Additive-only sweep + taxonomy consistency, over every evaluable scenario.

    Every assertion below ties a new key to a value the engine already published,
    which is what makes the change provably additive: the taxonomy restates the
    existing surface under the engine's own names and introduces no new number.
    """
    cfg, debt_result = _plan_for(scenario)
    published = set(debt_result)

    # 1. Nothing removed or renamed; exactly the three taxonomy keys added.
    missing = PRE_EXISTING_KEYS - published
    assert not missing, f"plan_debt dropped pre-existing keys: {sorted(missing)}"
    assert published - PRE_EXISTING_KEYS == set(TAXONOMY_KEYS), (
        "plan_debt published unexpected keys: "
        f"{sorted(published - PRE_EXISTING_KEYS - TAXONOMY_KEYS)}"
    )

    # 2. Present UNCONDITIONALLY with the declared types (CASPER).
    construction_periods = debt_result["construction_periods"]
    bridge_debt_period = debt_result["bridge_debt_period"]
    first_operating_period = debt_result["first_operating_period"]
    assert isinstance(construction_periods, int)
    assert bridge_debt_period is None or isinstance(bridge_debt_period, int)
    assert isinstance(first_operating_period, int)
    assert construction_periods >= 0
    assert first_operating_period >= 0

    # 3. CESSPIT: one resolver, one answer. The published count must equal both the
    #    shared resolver's answer and the legacy `construction_years` key.
    assert construction_periods == _resolve_construction_periods(cfg)
    assert construction_periods == debt_result["construction_years"]

    # 4. The bridge index restates the legacy key exactly.
    assert bridge_debt_period == debt_result["cfads_bridge_debt_period"]

    # 5. first_operating_period is the earliest period carrying an operating row,
    #    and equals the timeline layout: construction + (bridge, if any).
    mapped = _mapped_periods(debt_result)
    assert mapped, "an evaluable scenario must map at least one operating row"
    assert first_operating_period == min(mapped)
    assert first_operating_period == construction_periods + (
        0 if bridge_debt_period is None else 1
    )

    # 6. The taxonomy actually partitions the timeline: no operating row may land
    #    on a construction or bridge period.
    assert min(mapped) >= first_operating_period
    if bridge_debt_period is not None:
        assert bridge_debt_period < first_operating_period
        assert bridge_debt_period not in set(mapped)
    assert construction_periods <= first_operating_period


def test_taxonomy_survives_the_amortize_balloon_resize() -> None:
    """The ``amortize`` treatment REBINDS ``core`` — the taxonomy must follow it.

    ``plan_debt`` re-solves the whole core through ``_resize_for_amortization``
    when ``balloon_treatment`` is ``amortize``. Reading the taxonomy from a
    pre-resize core would publish a stale answer on exactly this path, so it is
    pinned separately from the sweep (which exercises the default treatment).
    """
    result = evaluate_with_overrides(
        LENDER_CONFIG,
        overrides={"Financing_Terms.balloon_treatment": "amortize"},
        return_full_result=True,
    )
    debt_result: dict[str, Any] = cast(Dict[str, Any], result["debt_result"])
    assert debt_result["construction_periods"] == debt_result["construction_years"]
    assert debt_result["bridge_debt_period"] == debt_result["cfads_bridge_debt_period"]
    assert debt_result["first_operating_period"] == min(_mapped_periods(debt_result))


def test_lender_case_taxonomy_values_are_pinned() -> None:
    """Stable pins for the canonical lender case (TEST-01).

    Two construction periods, the synthetic bridge at period 2, and operating year
    1 at period 3 — the layout the F-6 defect made unreadable from the result.
    """
    _cfg, debt_result = _plan_for(Path(LENDER_CONFIG))
    assert debt_result["construction_periods"] == 2
    assert debt_result["bridge_debt_period"] == 2
    assert debt_result["first_operating_period"] == 3
    assert debt_result["annual_row_debt_period_map"][0]["debt_period"] == 3


# ---------------------------------------------------------------------------
# Hostile cases — unreachable from any committed scenario, which all carry
# construction_periods == 2 and a bridge period.
# ---------------------------------------------------------------------------


def _synthetic_config(construction_periods: int) -> dict[str, Any]:
    """Minimal engine config with an explicit construction-period count."""
    return {
        "Financing_Terms": {
            "construction_periods": construction_periods,
            "construction_schedule": [100.0] * max(1, construction_periods),
            "debt_drawdown_pct": [1.0 / max(1, construction_periods)]
            * max(1, construction_periods),
            "debt_ratio": 0.70,
            "tenor_years": 5,
            "interest_only_years": 0,
            "amortization_style": "sculpted",
            "target_dscr": 1.30,
            "mix": {"usd_commercial_min": 1.0},
            "rates": {"usd_nominal": 0.08},
        },
        "capex": {"usd_total": 100_000_000.0},
    }


def _synthetic_rows(count: int = 5) -> list[dict[str, Any]]:
    return [
        {"year": i + 1, "cfads_usd": 12_000_000.0, "fx_rate": 300.0}
        for i in range(count)
    ]


def test_zero_construction_periods_puts_the_bridge_at_period_zero() -> None:
    """HOSTILE: ``construction_periods == 0``.

    With no construction window the synthetic bridge occupies period 0 and
    operating year 1 lands at period 1 — so ``first_operating_period`` must be 1,
    not 0. Nothing may fall back to a "plausible" 2-period default here.
    """
    debt_result = plan_debt(annual_rows=_synthetic_rows(), config=_synthetic_config(0))
    assert debt_result["construction_periods"] == 0
    assert debt_result["bridge_debt_period"] == 0
    assert debt_result["first_operating_period"] == 1
    assert min(_mapped_periods(debt_result)) == 1


def test_taxonomy_is_published_for_a_config_that_omits_the_field() -> None:
    """CASPER: the keys are emitted unconditionally, including on the default path.

    The engine's documented default is two construction periods; the taxonomy must
    report that resolved default rather than omitting the keys.
    """
    config = _synthetic_config(2)
    del config["Financing_Terms"]["construction_periods"]
    config["Financing_Terms"]["construction_schedule"] = [50.0, 50.0]
    config["Financing_Terms"]["debt_drawdown_pct"] = [0.5, 0.5]
    debt_result = plan_debt(annual_rows=_synthetic_rows(), config=config)
    assert TAXONOMY_KEYS <= set(debt_result)
    assert debt_result["construction_periods"] == 2
    assert debt_result["construction_periods"] == _resolve_construction_periods(config)
    assert debt_result["first_operating_period"] == 3


def test_no_bridge_period_yields_none_not_a_substitute_value() -> None:
    """HOSTILE: a timeline with no bridge period.

    ``_build_cfads_timeline`` creates the bridge only when CFADS is non-empty.
    Absent must be an explicit ``None`` (CASPER), never a plausible 0, and the
    operating window must then open at the first post-construction period.
    """
    _cfads_ext, row_map, _periods, bridge = _build_cfads_timeline(
        annual_rows=[], cfads=[], construction_periods=3, tenor=5
    )
    assert bridge is None
    assert row_map == []
    assert _resolve_first_operating_period(row_map, 3, bridge) == 3


def test_first_mapped_period_zero_is_reported_as_zero() -> None:
    """HOSTILE: the first mapped period is 0.

    Unreachable through ``apply_debt_layer`` today — any timeline with operating
    rows also has a bridge, so the earliest mapped period is at least 1. The
    resolver must still report 0 honestly rather than clamping to the layout
    formula, because the row->period map is the definitional source.

    The second assertion is the discriminating one: it hands the resolver a
    taxonomy whose layout formula would answer 3 and a map that says 0. A resolver
    that quietly preferred the formula would pass the first assertion by
    coincidence and fail this one.
    """
    row_map = [
        {"annual_row_index": 0, "year": 1, "debt_period": 0},
        {"annual_row_index": 1, "year": 2, "debt_period": 1},
    ]
    assert _resolve_first_operating_period(row_map, 0, None) == 0
    assert _resolve_first_operating_period(row_map, 2, 2) == 0


def test_resolver_takes_the_earliest_mapped_period_not_the_first_listed() -> None:
    """Order of the map must not decide the answer; the earliest period does.

    Construction and bridge are chosen so the layout fallback would answer 0 —
    a resolver ignoring the map cannot pass this by coincidence.
    """
    row_map = [
        {"annual_row_index": 2, "year": 3, "debt_period": 7},
        {"annual_row_index": 0, "year": 1, "debt_period": 5},
    ]
    assert _resolve_first_operating_period(row_map, 0, None) == 5


@pytest.mark.parametrize(
    "row_map",
    [
        [{"annual_row_index": 0}],
        [{"annual_row_index": 0, "debt_period": None}],
        [{"annual_row_index": 0, "debt_period": "not-a-period"}],
    ],
)
def test_unusable_map_entries_fall_back_to_the_timeline_layout(
    row_map: list[dict[str, Any]],
) -> None:
    """A malformed map must not raise, and must not invent an operating period."""
    assert _resolve_first_operating_period(row_map, 2, 2) == 3


@pytest.mark.parametrize(
    ("construction_periods", "bridge", "expected"),
    [
        (0, None, 0),
        (0, 0, 1),
        (2, 2, 3),
        (5, 5, 6),
        (5, None, 5),
        (-3, None, 0),
    ],
)
def test_layout_fallback_matches_the_timeline_construction(
    construction_periods: int, bridge: Optional[int], expected: int
) -> None:
    """The empty-map fallback is the documented layout, clamped at zero."""
    assert _resolve_first_operating_period([], construction_periods, bridge) == expected


# ---------------------------------------------------------------------------
# Documented hazard (F-2) — pinned, not fixed.
# ---------------------------------------------------------------------------


def test_dscr_index_space_collision_is_still_present() -> None:
    """Executable pin on the collision the ``plan_debt`` docstring warns about.

    ``dscr_series`` is compacted by ``_clean_public_dscr_series`` while
    ``raw_dscr_series`` is positional, and ``annual_row_debt_period_map`` indexes
    the RAW space — so ``debt_result["dscr_series"][debt_period]`` reads a
    different period than a caller would expect. F-6 documents this; it does not
    fix it.

    This test asserts the DEFECT, deliberately, so the docstring warning cannot go
    stale unnoticed. The dolphin that unifies the two series MUST update or delete
    it — a failure here means the hazard changed, which is exactly when the
    docstring needs rewriting.
    """
    _cfg, debt_result = _plan_for(Path(LENDER_CONFIG))
    public = debt_result["dscr_series"]
    raw = debt_result["raw_dscr_series"]
    period = debt_result["first_operating_period"]

    assert len(public) < len(raw), "the compaction that causes the collision is gone"
    assert period < len(public)
    assert public[period] != pytest.approx(raw[period]), (
        "dscr_series and raw_dscr_series now agree at the first operating period; "
        "the index-space collision documented in plan_debt's docstring has changed"
    )
