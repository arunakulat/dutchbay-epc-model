"""Contract tests for the operating-period grid (:mod:`finance.period_grid_v14`).

Dolphin A1. The grid is the resolver that answers "how many cashflow periods are in an
operating year, and which year owns period *p*?". It ships one dolphin ahead of the
sub-annual operating rows (A2) that will consume it, so the tests here carry two jobs
that matter more than the arithmetic:

1. :func:`test_annual_grid_is_the_identity_on_every_helper` — the byte-identity claim.
   Every committed scenario resolves to :data:`ANNUAL`, so if any helper is not an
   exact identity (or an order-preserving regrouping) under that grid, shipping this
   module could move canon. The test asserts identity on the *float objects*, not
   merely on equal values.

2. :func:`test_quarterly_resolves_but_the_engine_gate_rejects_it` — the fail-loud gate.
   ``quarterly`` is a describable resolution today but not a buildable one, and the
   dangerous failure mode is not a crash: it is a scenario labelled ``quarterly``
   silently receiving ANNUAL rows. The gate must reject rather than degrade, and it
   must reject at a DIFFERENT seam from config validation, since the config is
   genuinely valid. When A2 lands, this test flips to asserting acceptance.

The remaining tests pin the partition and inverse properties that A2 will rely on to
prove ``aggregate(quarterly) == annual``, and the hostile config cases that a committed
scenario can never reach because no committed scenario sets the key at all.
"""

from __future__ import annotations

import dataclasses

import pytest
from hypothesis import given
from hypothesis import strategies as st

from finance.period_grid_v14 import (
    ANNUAL,
    CASHFLOW_RESOLUTION_KEY,
    ENGINE_SUPPORTED_RESOLUTIONS,
    SUPPORTED_RESOLUTIONS,
    PeriodGrid,
    aggregate_balances_to_annual,
    aggregate_flows_to_annual,
    period_count,
    periods_for_year,
    require_engine_support,
    resolve_period_grid,
    year_index_for_period,
)

QUARTERLY = PeriodGrid(resolution="quarterly", periods_per_year=4)


# ---------------------------------------------------------------------------
# Resolution — the default-off contract
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "config",
    [
        None,
        {},
        {"project": {"life_years": 20}},
        {"cashflow": {}},
        {"cashflow": {"resolution": None}},
    ],
    ids=["none", "empty", "unrelated-keys", "empty-section", "explicit-null"],
)
def test_absent_resolution_defaults_to_annual(config) -> None:
    """No ``cashflow.resolution`` -> ANNUAL. This is the committed-canon path."""
    assert resolve_period_grid(config) == ANNUAL


def test_no_committed_scenario_sets_the_resolution_key() -> None:
    """The default-off claim, checked against the scenarios rather than asserted.

    If a committed scenario ever sets the key, the "every committed scenario resolves
    to ANNUAL" premise behind the byte-identity argument silently stops holding.
    """
    import pathlib

    import yaml

    scenarios = pathlib.Path(__file__).resolve().parents[2] / "scenarios"
    offenders = []
    for path in sorted(scenarios.glob("*.yaml")):
        try:
            loaded = yaml.safe_load(path.read_text()) or {}
        except yaml.YAMLError:
            continue  # deliberately-malformed fixtures exist; not this test's concern
        if isinstance(loaded, dict):
            section = loaded.get("cashflow")
            if isinstance(section, dict) and section.get("resolution") is not None:
                offenders.append(path.name)
    assert offenders == []


@pytest.mark.parametrize(
    ("raw", "expected_periods"),
    [("annual", 1), ("quarterly", 4), ("QUARTERLY", 4), ("  Annual  ", 1)],
)
def test_recognised_resolutions_normalise(raw: str, expected_periods: int) -> None:
    """Case and surrounding whitespace normalise to the canonical lower-case name."""
    grid = resolve_period_grid({"cashflow": {"resolution": raw}})
    assert grid.periods_per_year == expected_periods
    assert grid.resolution == raw.strip().lower()


@pytest.mark.parametrize(
    "raw",
    ["monthly", "daily", "weekly", "semiannual", "yearly", "1", "annual "[:-1] + "x"],
)
def test_unknown_resolution_fails_loud(raw: str) -> None:
    """An unrecognised name must raise, never fall back to annual.

    Silent demotion to annual is the failure this rejects: the run would produce
    annual numbers under a label promising something else.
    """
    with pytest.raises(ValueError, match=CASHFLOW_RESOLUTION_KEY):
        resolve_period_grid({"cashflow": {"resolution": raw}})


@pytest.mark.parametrize("raw", [4, 4.0, True, ["quarterly"], {"name": "quarterly"}])
def test_non_string_resolution_fails_loud(raw) -> None:
    """A non-string value names no resolution and must not be coerced into one."""
    with pytest.raises(ValueError, match="must be a string"):
        resolve_period_grid({"cashflow": {"resolution": raw}})


@pytest.mark.parametrize("raw", ["", "   ", "\t"])
def test_blank_resolution_fails_loud(raw: str) -> None:
    """Blank is distinct from absent: absent means default, blank means malformed."""
    with pytest.raises(ValueError, match="is empty"):
        resolve_period_grid({"cashflow": {"resolution": raw}})


def test_resolver_does_not_mutate_the_caller_config() -> None:
    """The resolver reads; it must not write back a normalised value."""
    config = {"cashflow": {"resolution": "QUARTERLY"}}
    resolve_period_grid(config)
    assert config == {"cashflow": {"resolution": "QUARTERLY"}}


# ---------------------------------------------------------------------------
# The engine gate — fail loud rather than silently degrade
# ---------------------------------------------------------------------------


def test_quarterly_now_resolves_and_passes_the_engine_gate() -> None:
    """``quarterly`` became buildable in A2, so the gate that rejected it now admits it.

    In A1 this test asserted the opposite half: ``quarterly`` resolved but
    ``require_engine_support`` raised, because no code could build sub-annual rows yet.
    A2 added :func:`finance.subannual_rows_v14.build_subannual_rows`, so the resolution
    joined ENGINE_SUPPORTED_RESOLUTIONS and the gate opened — exactly the seam the split
    was designed for. The resolver itself was not touched in either dolphin.
    """
    grid = resolve_period_grid({"cashflow": {"resolution": "quarterly"}})
    assert grid == QUARTERLY
    require_engine_support(grid)  # must not raise


def test_the_engine_gate_still_rejects_a_describable_but_unbuilt_resolution() -> None:
    """The gate must keep its teeth once quarterly passes it.

    The mechanism is what matters, not the one resolution that happened to be behind it:
    a resolution the grid can describe but the engine cannot build must still fail rather
    than be served as annual. Asserted against a synthetic grid so the test does not
    decay into a tautology the moment every named resolution is buildable.
    """
    unbuilt = PeriodGrid(resolution="fortnightly", periods_per_year=26)
    assert unbuilt.resolution not in ENGINE_SUPPORTED_RESOLUTIONS

    with pytest.raises(ValueError, match="does not yet build sub-annual rows"):
        require_engine_support(unbuilt)


def test_annual_passes_the_engine_gate() -> None:
    """The committed path must not be gated."""
    require_engine_support(ANNUAL)  # must not raise


def test_engine_support_is_a_subset_of_describable_resolutions() -> None:
    """The engine can never claim support for a resolution the grid cannot describe."""
    assert ENGINE_SUPPORTED_RESOLUTIONS <= set(SUPPORTED_RESOLUTIONS)


# ---------------------------------------------------------------------------
# The byte-identity claim
# ---------------------------------------------------------------------------


def test_annual_grid_is_the_identity_on_every_helper() -> None:
    """Under ANNUAL every helper is an identity or an order-preserving regroup.

    Asserted with ``is`` on the float objects rather than ``==`` on their values: an
    aggregation that reconstructed equal-but-new floats would still be a re-computation,
    and the point of this test is that the annual path performs none.
    """
    values = [1.5, -2.25, 0.0, 1e18, 3.3]

    assert ANNUAL.periods_per_year == 1
    assert ANNUAL.is_annual is True
    assert period_count(20, ANNUAL) == 20
    assert [year_index_for_period(i, ANNUAL) for i in range(5)] == [0, 1, 2, 3, 4]
    assert [periods_for_year(i, ANNUAL) for i in range(3)] == [[0], [1], [2]]

    flows = aggregate_flows_to_annual(values, ANNUAL)
    balances = aggregate_balances_to_annual(values, ANNUAL)
    assert flows == values
    assert balances == values
    # Order-preserving AND value-preserving at object identity.
    assert all(a is b for a, b in zip(balances, values, strict=True))


def test_helper_defaults_are_the_annual_grid() -> None:
    """A caller that never mentions a grid gets the committed behaviour."""
    assert period_count(7) == 7
    assert year_index_for_period(3) == 3
    assert periods_for_year(3) == [3]
    assert aggregate_flows_to_annual([1.0, 2.0]) == [1.0, 2.0]
    assert aggregate_balances_to_annual([1.0, 2.0]) == [1.0, 2.0]


# ---------------------------------------------------------------------------
# Sub-period arithmetic and the partition properties A2 will lean on
# ---------------------------------------------------------------------------


def test_quarterly_period_count_and_mapping() -> None:
    """20 operating years -> 80 quarters, four consecutive quarters per year."""
    assert period_count(20, QUARTERLY) == 80
    assert [year_index_for_period(p, QUARTERLY) for p in range(8)] == [
        0,
        0,
        0,
        0,
        1,
        1,
        1,
        1,
    ]
    assert periods_for_year(0, QUARTERLY) == [0, 1, 2, 3]
    assert periods_for_year(3, QUARTERLY) == [12, 13, 14, 15]


def test_period_count_of_zero_years_is_zero() -> None:
    assert period_count(0, QUARTERLY) == 0


@pytest.mark.parametrize(
    ("fn", "kwargs"),
    [
        (period_count, {"project_life_years": -1}),
        (year_index_for_period, {"period_index": -1}),
        (periods_for_year, {"year_index": -1}),
    ],
)
def test_negative_indices_fail_loud(fn, kwargs) -> None:
    """Negative indices are a caller bug, not a wrap-around."""
    with pytest.raises(ValueError, match=">= 0"):
        fn(**kwargs, grid=QUARTERLY)


@given(
    years=st.integers(min_value=0, max_value=60),
    per_year=st.sampled_from(sorted(set(SUPPORTED_RESOLUTIONS.values()))),
)
def test_periods_for_year_partitions_the_axis_exactly(
    years: int, per_year: int
) -> None:
    """The per-year period lists tile the axis with no gap, overlap or overrun.

    This is the property A2 needs: if the lists did not partition the axis, an
    aggregation could double-count or drop a sub-period while still summing to a
    plausible-looking annual figure.
    """
    grid = PeriodGrid(resolution="synthetic", periods_per_year=per_year)
    collected: list[int] = []
    for year in range(years):
        collected.extend(periods_for_year(year, grid))
    assert collected == list(range(period_count(years, grid)))


@given(
    period=st.integers(min_value=0, max_value=5000),
    per_year=st.sampled_from(sorted(set(SUPPORTED_RESOLUTIONS.values()))),
)
def test_year_index_and_periods_for_year_are_inverses(
    period: int, per_year: int
) -> None:
    """``periods_for_year(year_index_for_period(p))`` always contains ``p``."""
    grid = PeriodGrid(resolution="synthetic", periods_per_year=per_year)
    year = year_index_for_period(period, grid)
    assert period in periods_for_year(year, grid)


# ---------------------------------------------------------------------------
# Aggregation — flows sum, balances close, ragged series are rejected
# ---------------------------------------------------------------------------


def test_flows_sum_within_each_year() -> None:
    quarters = [1.0, 2.0, 3.0, 4.0, 10.0, 20.0, 30.0, 40.0]
    assert aggregate_flows_to_annual(quarters, QUARTERLY) == [10.0, 100.0]


def test_balances_take_the_period_end_value() -> None:
    """A balance closes the year at its last sub-period; summing it would be nonsense."""
    quarters = [100.0, 90.0, 80.0, 70.0, 60.0, 50.0, 40.0, 30.0]
    assert aggregate_balances_to_annual(quarters, QUARTERLY) == [70.0, 30.0]


def test_empty_series_aggregate_to_empty() -> None:
    assert aggregate_flows_to_annual([], QUARTERLY) == []
    assert aggregate_balances_to_annual([], QUARTERLY) == []


@pytest.mark.parametrize("length", [1, 2, 3, 5, 6, 7, 9])
def test_ragged_series_fail_loud(length: int) -> None:
    """A partial year means the caller's axis disagrees with the grid.

    Truncating or zero-padding here would silently misattribute or drop cash, so a
    length that is not a whole number of years is rejected outright.
    """
    values = [1.0] * length
    with pytest.raises(ValueError, match="not a whole number of operating years"):
        aggregate_flows_to_annual(values, QUARTERLY)
    with pytest.raises(ValueError, match="not a whole number of operating years"):
        aggregate_balances_to_annual(values, QUARTERLY)


@given(
    annual_values=st.lists(
        st.floats(min_value=-1e9, max_value=1e9, allow_nan=False, allow_infinity=False),
        min_size=0,
        max_size=40,
    )
)
def test_splitting_an_annual_flow_into_quarters_round_trips(
    annual_values: list[float],
) -> None:
    """Quarters that carry a year's whole flow in one period aggregate back to it.

    The A2 acceptance criterion in miniature: a sub-annual series whose within-year
    parts are known must re-aggregate to the annual figure exactly.
    """
    quarters: list[float] = []
    for value in annual_values:
        quarters.extend([value, 0.0, 0.0, 0.0])
    assert aggregate_flows_to_annual(quarters, QUARTERLY) == pytest.approx(
        annual_values, rel=0, abs=0
    )


# ---------------------------------------------------------------------------
# The grid value object
# ---------------------------------------------------------------------------


def test_period_grid_is_frozen_and_comparable() -> None:
    """Immutability keeps a mid-pipeline consumer from re-deriving a different grid."""
    assert PeriodGrid("annual", 1) == ANNUAL
    with pytest.raises(dataclasses.FrozenInstanceError):
        ANNUAL.periods_per_year = 4  # type: ignore[misc]
