"""A partial-KPI MC trial must degrade, not crash the whole run (audit D2, #571).

`MonteCarloResult` requires every trials[] array to share one length (row alignment).
`aggregate_trials` used to skip None PER KEY, so a single trial missing one KPI produced
ragged arrays and the frozen contract raised ValueError, aborting the entire run. The
nullable-row policy retains every trial position while each metric uses its own defined
observations. Undefined equity IRR must not remove the same draw's valid DSCR (#1474).
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


def test_single_partial_trial_keeps_defined_metrics_and_null_position() -> None:
    trials = [_complete(i) for i in range(9)]
    partial = _complete(99)
    partial["equity_irr"] = None  # one KPI failed on this draw
    trials.append(partial)

    res = _agg(trials)  # must NOT raise

    # Equal-length invariant holds without selecting a complete-case cohort.
    lengths = {m: len(v) for m, v in res.trials.items()}
    assert set(lengths.values()) == {10}
    assert res.trials["equity_irr"][-1] is None
    assert res.trials["dscr_min"][-1] == partial["dscr_min"]
    assert res.metadata["partial_trial_count"] == 1
    assert res.failed_iterations == 0
    assert res.iterations == 10


def test_trials_missing_different_keys_still_produce_equal_length_arrays() -> None:
    # The exact ragged-array trigger: different trials miss different KPIs.
    a, b, c = _complete(1), _complete(2), _complete(3)
    a["equity_irr"] = None
    b["project_npv"] = None
    res = _agg([a, b, c])  # previously crashed with ValueError

    lengths = {len(v) for v in res.trials.values()}
    assert lengths == {3}
    assert res.trials["equity_irr"] == [None, b["equity_irr"], c["equity_irr"]]
    assert res.trials["project_npv"] == [a["project_npv"], None, c["project_npv"]]
    assert res.metadata["partial_trial_count"] == 2
    assert res.failed_iterations == 0


def test_non_numeric_value_is_disclosed_as_invalid_without_erasing_other_metrics() -> (
    None
):
    bad = _complete(5)
    bad["project_irr"] = "n/a"  # malformed value must not raise
    res = _agg([_complete(1), bad])
    assert res.metadata["partial_trial_count"] == 1
    assert {len(v) for v in res.trials.values()} == {2}
    assert res.trials["project_irr"][1] is None
    assert res.trials["dscr_min"][1] == bad["dscr_min"]
    assert res.failed_iterations == 1
    assert res.metadata["metric_coverage"]["project_irr"]["invalid_count"] == 1
