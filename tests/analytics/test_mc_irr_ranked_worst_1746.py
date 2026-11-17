"""A Monte Carlo trial with no defined IRR ranks below every defined trial (#1746 step 2).

Owner ruling on #1746 (2026-11-15 22:36Z): when a lower-tail percentile falls on the
undefined trials, it is reported as undefined, at or below the lowest defined IRR, rather
than as a number taken from the defined trials only. The rule stated for the rest of the
distribution: an upper percentile is read from the same full ranking, so it stays a
number and moves down a little; the mean and standard deviation stay over the defined
trials and say so; the maximum is unchanged. A run whose trials all have a defined IRR is
unchanged.
"""

from __future__ import annotations

import numpy as np
import pytest

from analytics.mc.aggregate import (
    DEFAULT_PERCENTILES,
    aggregate_trials,
    irr_ranked_note,
    ranked_worst_percentiles,
)
from analytics.mc.exports import build_lender_risk_table

N = 40
EXCLUDED = (0, 3, 7, 11, 19)  # equity IRR undefined on these trials


def _values() -> dict[str, np.ndarray]:
    rng = np.random.default_rng(11)
    return {
        "equity_irr": rng.normal(0.08, 0.03, N),
        "project_irr": rng.normal(0.07, 0.02, N),
        "equity_npv": rng.normal(-5e6, 4e6, N),
        "project_npv": rng.normal(-3e6, 4e6, N),
        "dscr_min": rng.normal(1.35, 0.05, N),
    }


def _aggregate(*, excluded: tuple[int, ...]):
    values = _values()
    rows = []
    for i in range(N):
        row = {k: float(v[i]) for k, v in values.items()}
        if i in excluded:
            # The evaluation gateway drops an IRR it cannot convert: an absent key.
            row.pop("equity_irr")
        rows.append(row)
    return aggregate_trials(
        trial_metrics=rows,
        base_config={},
        param_names=["capex.usd_total"],
        samples=np.zeros((N, 1)),
        meta={"seed": 1, "n_trials": N},
    )


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_with_nothing_excluded_the_ranking_is_np_percentile(seed: int) -> None:
    values = np.random.default_rng(seed).normal(0.07, 0.03, 37)
    ps = (1, 5, 10, 25, 50, 75, 90, 95, 99)
    got = ranked_worst_percentiles(values, 0, ps)
    for p in ps:
        assert got[p] == pytest.approx(float(np.percentile(values, p)), abs=1e-15)


def test_a_percentile_touching_an_excluded_trial_is_undefined() -> None:
    defined = np.arange(1.0, 9.0)  # 8 defined trials, 2 excluded: 10 in all
    got = ranked_worst_percentiles(defined, 2, (10, 20, 30, 50, 90))
    # Positions 0.9 and 1.8 touch the excluded ranks 0 and 1; 2.7 does not.
    assert got[10] is None and got[20] is None
    assert got[30] == pytest.approx(1.7)
    # Oracle: np.percentile with the excluded trials as values below every defined one.
    stand_in = np.concatenate([[-1e9, -1e9], defined])
    for p in (30, 50, 90):
        assert got[p] == pytest.approx(float(np.percentile(stand_in, p)))


def test_the_interpolation_boundary_counts_as_falling_on_an_excluded_trial() -> None:
    # Position 1.48 lies between the last excluded rank (1) and the lowest defined (2):
    # no number can be read there, so it is undefined rather than a blend.
    got = ranked_worst_percentiles(np.arange(1.0, 4.0), 2, (37,))
    assert list(got.values()) == [None]


def test_summary_ranks_undefined_irr_trials_worst() -> None:
    result = _aggregate(excluded=EXCLUDED)
    equity = result.summary["equity_irr"]
    defined = np.delete(_values()["equity_irr"], EXCLUDED)
    assert equity["percentile_basis"] == "excluded_trials_ranked_worst"
    assert equity["coverage_note"] == irr_ranked_note("equity_irr", len(EXCLUDED), N)
    # Lower tail: 5 of 40 excluded, so P1, P5 and P10 fall on them.
    for p in (1, 5, 10):
        assert equity["percentiles"][p] is None
        assert p not in result.percentiles or "equity_irr" not in result.percentiles[p]
    assert equity["percentile_bound"] == pytest.approx(float(defined.min()))
    assert equity["min"] is None
    assert equity["min_defined"] == pytest.approx(float(defined.min()))
    # Upper tail: still a number, read from the full ranking, so it moves down.
    for p in (50, 90, 95, 99):
        value = equity["percentiles"][p]
        assert value is not None
        assert value <= float(np.percentile(defined, p)) + 1e-15
        assert result.percentiles[p]["equity_irr"] == value
    assert equity["percentiles"][50] < float(np.percentile(defined, 50))
    # Mean, std and max stay over the defined trials, and say so.
    assert equity["mean"] == pytest.approx(float(defined.mean()))
    assert equity["std"] == pytest.approx(float(defined.std(ddof=1)))
    assert equity["max"] == pytest.approx(float(defined.max()))
    assert equity["mean_basis"] == "defined_trials"


def test_flat_project_irr_fields_follow_the_ranking() -> None:
    values = _values()
    rows = []
    for i in range(N):
        row = {k: float(v[i]) for k, v in values.items()}
        if i < 6:
            row.pop("project_irr")
        rows.append(row)
    result = aggregate_trials(
        trial_metrics=rows,
        base_config={},
        param_names=["capex.usd_total"],
        samples=np.zeros((N, 1)),
        meta={"seed": 1, "n_trials": N},
    )
    project = result.summary["project_irr"]
    assert result.project_irr_p10 is None
    assert result.project_irr_p50 == project["percentiles"][50]
    assert result.project_irr_p90 == project["percentiles"][90]
    assert result.project_irr_mean == pytest.approx(project["mean"])
    assert result.project_irr_excluded_count == 6


def test_a_run_with_every_irr_defined_is_unchanged() -> None:
    result = _aggregate(excluded=())
    equity = result.summary["equity_irr"]
    values = _values()["equity_irr"]
    for p in DEFAULT_PERCENTILES:
        assert equity["percentiles"][p] == pytest.approx(
            float(np.percentile(values, p)), abs=1e-15
        )
    assert equity["min"] == pytest.approx(float(values.min()))
    for key in ("percentile_basis", "percentile_bound", "min_defined", "mean_basis"):
        assert key not in equity


def test_non_irr_metrics_are_never_ranked() -> None:
    result = _aggregate(excluded=EXCLUDED)
    npv = result.summary["equity_npv"]
    assert "percentile_basis" not in npv
    assert npv["min"] is not None


def test_lender_table_reads_the_downside_tail_from_the_ranking() -> None:
    result = _aggregate(excluded=EXCLUDED)
    # The lender table shows project IRR; point it at the equity IRR, which has the gaps.
    frame = build_lender_risk_table(result, metric_map={"project_irr": "equity_irr"})
    row = frame[frame["metric"] == "Project IRR"].iloc[0]
    defined = np.delete(_values()["equity_irr"], EXCLUDED)
    # P90 and P95 (the 10th and 5th percentiles) fall on the excluded trials.
    assert row["P90"] is None or np.isnan(row["P90"])
    assert row["P95"] is None or np.isnan(row["P95"])
    expected_p50 = ranked_worst_percentiles(defined, len(EXCLUDED), (50,))[50]
    assert row["P50"] == pytest.approx(expected_p50)
    assert row["coverage_note"] == irr_ranked_note("equity_irr", len(EXCLUDED), N)
    # A clean run's table is the raw percentiles, as before.
    clean = build_lender_risk_table(
        _aggregate(excluded=()), metric_map={"project_irr": "equity_irr"}
    )
    clean_row = clean[clean["metric"] == "Project IRR"].iloc[0]
    values = _values()["equity_irr"]
    assert clean_row["P90"] == pytest.approx(float(np.percentile(values, 10)))
    assert "coverage_note" not in clean.columns
