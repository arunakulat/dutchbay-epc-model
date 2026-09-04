"""Contract tests for the sub-annual operating rows (:mod:`finance.subannual_rows_v14`).

Dolphin A2 — the reconciliation firewall of Lane A. Nothing downstream in the lane is
trustworthy until a sub-annual series re-aggregates to the annual one, so four tests
carry the weight here:

1. :func:`test_lendercase_quarterly_rows_aggregate_back_to_the_annual_engine` — the
   firewall itself, run against the REAL committed lendercase rather than a fixture.
   Every allocated flow of every year must sum back to the annual engine's own figure
   within one ULP. A fixture could be built to pass; the live scenario cannot.

2. :func:`test_the_default_even_profile_reconciles_exactly` — the stronger guarantee on
   the path every run actually takes. The default even split reconciles at exact float
   equality, and that is asserted with ``==`` so it cannot silently degrade into the
   1-ULP bound the general case needs.

3. :func:`test_an_unclassified_key_fails_loud` — the module's strictness. An engine row
   key that is neither a declared flow nor year-level must raise, because silently
   dropping it loses cash and silently allocating it would divide a rate. Both produce
   plausible, wrong numbers, which is the one failure the output cannot reveal.

4. :func:`test_every_live_lendercase_row_key_is_classified` — the counterpart. The
   classification is only safe if it actually covers what the engine emits, so this reads
   the live row keys and asserts the two sets partition them exactly. Together with (3),
   an engine change either stays covered or fails visibly; it cannot drift silently.

A note on why the bound is 1 ULP and not zero: the first draft of this module claimed
exact reconciliation on every profile. The firewall test disproved it on its first run
against the live lendercase — year-2 CFADS straddles a rounding boundary that no closing
residual can reach, and an attempted correction merely oscillates. The contract was
narrowed to what is true rather than the test loosened to fit the claim;
:func:`test_the_known_straddle_case_is_within_one_ulp_but_not_exact` pins that case.

The remaining tests pin the allocation mechanism, the annual-grid identity, and the
profile validation.
"""

from __future__ import annotations

import math

import pytest

from finance.period_grid_v14 import (
    ANNUAL,
    PeriodGrid,
    aggregate_flows_to_annual,
    resolve_period_grid,
)
from finance.subannual_rows_v14 import (
    FLOW_KEYS,
    RECONCILIATION_ULP_TOLERANCE,
    WITHIN_YEAR_PROFILE_KEY,
    YEAR_LEVEL_KEYS,
    allocate_flow,
    build_subannual_rows,
    even_profile,
    resolve_within_year_profile,
)

QUARTERLY = PeriodGrid(resolution="quarterly", periods_per_year=4)

# A deliberately lopsided profile: seasonal wind, not an even split. An even profile
# would let a broken allocator pass several of these tests by symmetry.
SEASONAL = (0.35, 0.15, 0.15, 0.35)


@pytest.fixture(scope="module")
def lendercase_annual_rows():
    """The real committed lendercase's annual rows, straight from the engine."""
    import yaml

    from finance.cashflow_v14 import build_annual_rows

    with open("scenarios/dutchbay_lendercase_2025Q4.yaml") as handle:
        config = yaml.safe_load(handle)
    return build_annual_rows(config)


# ---------------------------------------------------------------------------
# The byte-identity firewall
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("profile", [None, SEASONAL], ids=["even", "seasonal"])
def test_lendercase_quarterly_rows_aggregate_back_to_the_annual_engine(
    lendercase_annual_rows, profile
) -> None:
    """Every allocated flow sums back to the annual engine's figure within 1 ULP.

    The bound is asserted in units-in-the-last-place, not as a relative tolerance. An
    ULP count is the tightest true statement available — exact equality is unreachable
    because independently rounded parts can straddle a rounding boundary (see
    ``allocate_flow``) — while a relative tolerance loose enough to pass would also pass
    a genuine allocation bug, which is the thing A3's debt service needs ruled out.
    """
    annual = lendercase_annual_rows
    assert len(annual) == 20  # the lendercase's project life; guards the fixture

    sub = build_subannual_rows(annual, QUARTERLY, profile)
    assert len(sub) == len(annual) * 4

    for key in sorted(FLOW_KEYS & set(annual[0])):
        quarterly_series = [row[key] for row in sub]
        reaggregated = aggregate_flows_to_annual(quarterly_series, QUARTERLY)
        expected = [float(row[key]) for row in annual]

        for year_index, (got, want) in enumerate(
            zip(reaggregated, expected, strict=True)
        ):
            slack = RECONCILIATION_ULP_TOLERANCE * math.ulp(want)
            assert abs(got - want) <= slack, (
                f"{key} year {year_index + 1}: re-aggregated {got!r} vs annual {want!r} "
                f"— off by more than {RECONCILIATION_ULP_TOLERANCE} ULP ({slack!r})"
            )


def test_the_default_even_profile_reconciles_exactly(lendercase_annual_rows) -> None:
    """The DEFAULT profile is exact at float equality — no tolerance at all.

    This is the guarantee that matters most, because it is the one every run gets unless
    a scenario deliberately opts into a shaped profile. An even split across a
    power-of-two period count is exact in binary, so the closing residual has nothing to
    absorb. Asserted with ``==`` deliberately: if a future change makes the default merely
    near-exact, that is a real regression and should fail here rather than be waved
    through by the 1-ULP bound the general case needs.
    """
    sub = build_subannual_rows(lendercase_annual_rows, QUARTERLY)  # default profile

    for key in sorted(FLOW_KEYS & set(lendercase_annual_rows[0])):
        reaggregated = aggregate_flows_to_annual([row[key] for row in sub], QUARTERLY)
        expected = [float(row[key]) for row in lendercase_annual_rows]
        assert reaggregated == expected, f"{key} is no longer exact on the even profile"


def test_reconciliation_drift_is_zero_or_one_ulp_never_more(
    lendercase_annual_rows,
) -> None:
    """Pin the drift distribution, so a regression that widens it cannot hide.

    The firewall test above would still pass if every figure drifted a full ULP. This
    records what actually happens on the seasonal profile — 510 of 540 exact, 30 at one
    ULP, none worse — so a change that degrades the allocation shows up as a shifted
    distribution rather than staying silently inside the bound.
    """
    sub = build_subannual_rows(lendercase_annual_rows, QUARTERLY, SEASONAL)
    exact = off_by_one = 0

    for key in sorted(FLOW_KEYS & set(lendercase_annual_rows[0])):
        reaggregated = aggregate_flows_to_annual([row[key] for row in sub], QUARTERLY)
        for got, want in zip(
            reaggregated,
            (float(row[key]) for row in lendercase_annual_rows),
            strict=True,
        ):
            if got == want:
                exact += 1
            else:
                assert abs(got - want) <= math.ulp(want)
                off_by_one += 1

    assert (exact, off_by_one) == (
        510,
        30,
    ), f"reconciliation drift distribution moved: exact={exact} off_by_one={off_by_one}"


def test_seasonal_profile_actually_varies_the_quarters(lendercase_annual_rows) -> None:
    """A lopsided profile must produce unequal quarters — not a disguised even split.

    Without this, every aggregation test above would still pass on an allocator that
    ignored the profile entirely and split evenly.
    """
    sub = build_subannual_rows(lendercase_annual_rows, QUARTERLY, SEASONAL)
    first_year = [row["cfads_final_lkr"] for row in sub[:4]]

    assert first_year[0] > first_year[1]
    assert first_year[3] > first_year[2]
    assert len({round(value, 6) for value in first_year}) > 1


# ---------------------------------------------------------------------------
# Classification — the strictness that keeps the allocation honest
# ---------------------------------------------------------------------------


def test_every_live_lendercase_row_key_is_classified(lendercase_annual_rows) -> None:
    """The two declared sets must partition what the engine actually emits.

    Asserted against live rows rather than a hand-written list, so the classification
    cannot quietly fall behind the engine.
    """
    live_keys = set(lendercase_annual_rows[0]) - {"year"}
    unclassified = live_keys - (FLOW_KEYS | YEAR_LEVEL_KEYS)
    assert unclassified == set()

    # And the two sets must not overlap — a key cannot be both allocated and carried.
    assert FLOW_KEYS & YEAR_LEVEL_KEYS == frozenset()


def test_an_unclassified_key_fails_loud() -> None:
    """An unknown row key raises rather than being dropped or guessed at."""
    row = {"year": 1.0, "cfads_final_lkr": 100.0, "some_new_engine_key": 7.0}
    with pytest.raises(ValueError, match="some_new_engine_key"):
        build_subannual_rows([row], QUARTERLY)


def test_year_level_keys_are_carried_not_divided() -> None:
    """A rate, flag or year-end stock must appear unchanged on every sub-period."""
    row = {
        "year": 3.0,
        "cfads_final_lkr": 400.0,
        "fx_rate": 374.27,
        "effective_tax_rate": 0.3,
        "risk_haircut_pct": 0.05,
        "tax_holiday_applied": 0.0,
        "carried_forward_losses": 1234.5,
    }
    sub = build_subannual_rows([row], QUARTERLY)

    for period in sub:
        assert period["fx_rate"] == 374.27
        assert period["effective_tax_rate"] == 0.3
        assert period["risk_haircut_pct"] == 0.05
        assert period["carried_forward_losses"] == 1234.5
        assert period["year"] == 3.0
    # ...while the flow was split.
    assert [period["cfads_final_lkr"] for period in sub] == [100.0, 100.0, 100.0, 100.0]


def test_positional_keys_locate_each_sub_period() -> None:
    """period_index is global and ascending; period_in_year and is_year_end are local."""
    rows = [
        {"year": 1.0, "cfads_final_lkr": 4.0},
        {"year": 2.0, "cfads_final_lkr": 8.0},
    ]
    sub = build_subannual_rows(rows, QUARTERLY)

    assert [r["period_index"] for r in sub] == [float(i) for i in range(8)]
    assert [r["period_in_year"] for r in sub] == [0.0, 1.0, 2.0, 3.0] * 2
    assert [r["is_year_end"] for r in sub] == [0.0, 0.0, 0.0, 1.0] * 2
    assert [r["year"] for r in sub] == [1.0] * 4 + [2.0] * 4


# ---------------------------------------------------------------------------
# Exactness mechanism
# ---------------------------------------------------------------------------


def test_the_residual_lands_in_the_closing_period() -> None:
    """Rounding is parked in the last period, not smeared across the year."""
    # 0.1 has no exact binary representation, so an even split cannot round cleanly.
    parts = allocate_flow(0.1, even_profile(QUARTERLY))
    assert parts[0] == parts[1] == parts[2] == 0.1 * 0.25
    # The earlier periods are untouched weighted shares; only the closing one absorbs.
    assert parts[3] != 0.1 * 0.25
    assert math.fsum(parts) == 0.1


@pytest.mark.parametrize(
    "value", [0.0, 1.0, 0.1, -12345.678, 1e-9, 1e18, 166083177.3168602]
)
def test_allocation_reconciles_within_one_ulp_for_awkward_values(value: float) -> None:
    for profile in (even_profile(QUARTERLY), SEASONAL):
        parts = allocate_flow(value, profile)
        assert abs(math.fsum(parts) - value) <= RECONCILIATION_ULP_TOLERANCE * math.ulp(
            value
        )


def test_the_known_straddle_case_is_within_one_ulp_but_not_exact() -> None:
    """The lendercase year-2 CFADS figure that disproved the exactness claim.

    Pinned as a regression so the 1-ULP contract is anchored to the real case that
    forced it, rather than to a tolerance someone later widens on a hunch.
    """
    value = 7175292510.270228
    parts = allocate_flow(value, SEASONAL)
    drift = math.fsum(parts) - value

    assert drift != 0.0  # exactness is genuinely unreachable here
    assert abs(drift) <= math.ulp(value)


def test_negative_flows_allocate(lendercase_annual_rows) -> None:
    """A negative flow (a net outflow year) splits like any other, sign preserved."""
    parts = allocate_flow(-1000.0, SEASONAL)
    assert sum(parts) == -1000.0
    assert all(part < 0.0 for part in parts)


# ---------------------------------------------------------------------------
# The annual grid stays the identity
# ---------------------------------------------------------------------------


def test_annual_grid_returns_one_row_per_year_with_values_untouched(
    lendercase_annual_rows,
) -> None:
    """Under ANNUAL the module is a pass-through: same count, same float objects.

    This is what lets the sub-annual layer sit in the pipeline without touching the
    committed path — the annual grid must cost nothing and change nothing.
    """
    annual = lendercase_annual_rows
    sub = build_subannual_rows(annual, ANNUAL)
    assert len(sub) == len(annual)

    for original, produced in zip(annual, sub, strict=True):
        for key in FLOW_KEYS & set(original):
            assert produced[key] is original[key]
        assert produced["is_year_end"] == 1.0
        assert produced["period_in_year"] == 0.0


def test_build_defaults_to_the_annual_grid() -> None:
    rows = [{"year": 1.0, "cfads_final_lkr": 5.0}]
    assert build_subannual_rows(rows) == [
        {
            "year": 1.0,
            "period_index": 0.0,
            "period_in_year": 0.0,
            "is_year_end": 1.0,
            "cfads_final_lkr": 5.0,
        }
    ]


def test_empty_rows_produce_empty_output() -> None:
    assert build_subannual_rows([], QUARTERLY) == []


# ---------------------------------------------------------------------------
# Profile resolution
# ---------------------------------------------------------------------------


def test_absent_profile_is_even() -> None:
    assert resolve_within_year_profile({}, QUARTERLY) == (0.25, 0.25, 0.25, 0.25)
    assert resolve_within_year_profile(None, QUARTERLY) == (0.25, 0.25, 0.25, 0.25)
    assert resolve_within_year_profile({}, ANNUAL) == (1.0,)


def test_explicit_profile_resolves() -> None:
    config = {"cashflow": {"within_year_profile": list(SEASONAL)}}
    assert resolve_within_year_profile(config, QUARTERLY) == SEASONAL


def test_profile_summing_to_one_via_decimal_literals_is_accepted() -> None:
    """0.3+0.3+0.2+0.2 does not sum to exactly 1.0 in binary; the tolerance admits it."""
    config = {"cashflow": {"within_year_profile": [0.3, 0.3, 0.2, 0.2]}}
    assert resolve_within_year_profile(config, QUARTERLY) == (0.3, 0.3, 0.2, 0.2)


@pytest.mark.parametrize(
    ("profile", "match"),
    [
        ([0.25, 0.25, 0.25], "4 periods per year"),
        ([0.25] * 5, "4 periods per year"),
        ([0.5, 0.5, 0.5, 0.5], "sum to"),
        ([0.25, 0.25, 0.25, 0.2], "sum to"),
        ([0.5, 0.6, -0.1, 0.0], ">= 0"),
        ([0.25, 0.25, 0.25, "0.25"], "must be a number"),
        ([0.25, 0.25, 0.25, True], "must be a number"),
        ([float("nan"), 0.25, 0.25, 0.25], "finite"),
        ([float("inf"), 0.25, 0.25, 0.25], "finite"),
    ],
)
def test_malformed_profiles_fail_loud(profile, match) -> None:
    config = {"cashflow": {"within_year_profile": profile}}
    with pytest.raises(ValueError, match=match):
        resolve_within_year_profile(config, QUARTERLY)


@pytest.mark.parametrize("raw", ["0.25,0.25,0.25,0.25", {"q1": 0.25}, 0.25])
def test_non_sequence_profile_fails_loud(raw) -> None:
    config = {"cashflow": {"within_year_profile": raw}}
    with pytest.raises(ValueError, match=WITHIN_YEAR_PROFILE_KEY):
        resolve_within_year_profile(config, QUARTERLY)


def test_profile_length_mismatch_at_build_fails_loud() -> None:
    """A caller passing a profile directly gets the same length check as config does."""
    with pytest.raises(ValueError, match="4 periods per year"):
        build_subannual_rows([{"year": 1.0}], QUARTERLY, [0.5, 0.5])


# ---------------------------------------------------------------------------
# The grid gate is honoured
# ---------------------------------------------------------------------------


def test_an_unsupported_grid_is_refused_before_any_allocation() -> None:
    """build_subannual_rows must not build rows on a grid the engine cannot serve."""
    unbuilt = PeriodGrid(resolution="fortnightly", periods_per_year=26)
    with pytest.raises(ValueError, match="does not yet build sub-annual rows"):
        build_subannual_rows([{"year": 1.0}], unbuilt)


def test_quarterly_config_now_resolves_end_to_end() -> None:
    """The A1 resolver and the A2 builder meet: a quarterly config builds rows."""
    config = {"cashflow": {"resolution": "quarterly"}}
    grid = resolve_period_grid(config)
    profile = resolve_within_year_profile(config, grid)
    rows = build_subannual_rows(
        [{"year": 1.0, "cfads_final_lkr": 100.0}], grid, profile
    )
    assert len(rows) == 4
    assert sum(row["cfads_final_lkr"] for row in rows) == 100.0
