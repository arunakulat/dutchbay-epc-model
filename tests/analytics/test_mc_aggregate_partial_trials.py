"""A partial-KPI MC trial must degrade, not crash the whole run (audit D2, #571).

`MonteCarloResult` requires every trials[] array to share one length (row alignment).
`aggregate_trials` used to skip None PER KEY, so a single trial missing one KPI produced
ragged arrays and the frozen contract raised ValueError, aborting the entire run. The
complete-case policy drops partial trials (counting them as failed) and keeps the run alive.
"""

from __future__ import annotations

import numpy as np

from analytics.mc.aggregate import aggregate_trials

_KEYS = [
    "dscr_min",
    "project_irr",
    "project_npv",
    "llcr",
    "plcr",
    "equity_irr",
    "equity_npv",
]


def _complete(i: int) -> dict:
    return {k: 1.0 + 0.001 * i + 0.01 * j for j, k in enumerate(_KEYS)}


def _agg(trial_metrics):
    return aggregate_trials(
        trial_metrics=trial_metrics,
        base_config={},
        param_names=["capex.usd_total"],
        samples=np.zeros((len(trial_metrics), 1)),
        meta={"seed": 1, "n_trials": len(trial_metrics)},
    )


def test_all_complete_trials_are_fully_aggregated() -> None:
    res = _agg([_complete(i) for i in range(10)])
    assert res.failed_iterations == 0
    assert res.metadata["partial_trial_count"] == 0
    lengths = {m: len(v) for m, v in res.trials.items()}
    assert set(lengths.values()) == {10}  # every metric array full length


def test_single_partial_trial_does_not_crash_and_is_dropped() -> None:
    trials = [_complete(i) for i in range(9)]
    partial = _complete(99)
    partial["equity_irr"] = None  # one KPI failed on this draw
    trials.append(partial)

    res = _agg(trials)  # must NOT raise

    # equal-length invariant holds and the partial trial is excluded from every metric
    lengths = {m: len(v) for m, v in res.trials.items()}
    assert set(lengths.values()) == {9}
    assert res.metadata["partial_trial_count"] == 1
    assert res.failed_iterations == 1
    assert res.iterations == 10


def test_trials_missing_different_keys_still_produce_equal_length_arrays() -> None:
    # The exact ragged-array trigger: different trials miss different KPIs.
    a, b, c = _complete(1), _complete(2), _complete(3)
    a["equity_irr"] = None
    b["project_npv"] = None
    res = _agg([a, b, c])  # previously crashed with ValueError

    lengths = {len(v) for v in res.trials.values()}
    assert lengths == {
        1
    }  # only the one fully-complete trial survives, all arrays len 1
    assert res.metadata["partial_trial_count"] == 2


def test_non_numeric_value_is_treated_as_missing_not_a_crash() -> None:
    bad = _complete(5)
    bad["project_irr"] = "n/a"  # malformed value must not raise
    res = _agg([_complete(1), bad])
    assert res.metadata["partial_trial_count"] == 1
    assert set(len(v) for v in res.trials.values()) == {1}
