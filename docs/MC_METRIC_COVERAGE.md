# Monte Carlo metric coverage

Work item: [#1474](https://github.com/arunakulat/dutchbay-epc-model/issues/1474).
This corrects O-5's complete-case selection bias. It changes reported distributions
when a trial has an unavailable metric; it does not change trial evaluation or finance
mathematics. The internal `MonteCarloResult` raw-array contract now permits `None`.

## Aligned observations and metric-wise statistics

Every declared canonical metric retains one position for every input trial, in input
order. `None` is an unavailable observation, never a zero return. Each metric's mean,
standard deviation and percentiles use that metric's finite defined observations.
Two metrics can therefore have different statistical denominators while their raw
arrays retain equal lengths and original trial identity. Never zip separately filtered
arrays for a joint calculation.

`metadata.metric_coverage_schema` is `dutchbay.mc.metric_coverage.v1`.
`metadata.metric_coverage[metric]` records `total_count`, `defined_count`,
`undefined_count` (explicit `None`), `missing_count` (absent key), `invalid_count`
(malformed or non-finite value) and `status`. The four observation counts sum to the
total. Status is `defined`, `partial`, `undefined` or `invalid`.
`metadata.trial_alignment` is `input_order_null_placeholders`.

A declared metric with no defined observations remains in `summary` with null mean,
standard deviation, minimum and maximum, an empty percentile map and explicit status.
No quantile is invented. A metric never declared by any trial remains absent.

An undefined or missing metric alone does not mean evaluation failed. Empty evaluation
results, malformed metric values and toy fallbacks still count as failed iterations;
their independently defined observations remain visible, accompanied by failure and
coverage disclosures. `partial_trial_count` counts rows with an unavailable declared
metric, and `invalid_trial_count` counts malformed rows. Evaluation success and metric
coverage are separate facts. The CLI reports partial coverage as `degraded` even when
all evaluations succeeded. Toy provenance and the lender/IC fallback ceiling are unchanged.

## Consumer behavior and limitations

Lender tables select each metric's finite observations and show `defined_trials`,
`total_trials` and `unavailable_trials`. Covenant blocks disclose both the defined DSCR
denominator (`n_trials`) and the original total (`n_total_trials`). A breach fraction with
missing DSCR is conditional on defined DSCR; unknown DSCR is never a non-breach.
The shared breach primitive refuses non-finite arrays with an actionable coverage error.
An empty sample still has no probability estimate. CASPER's JSON conversion emits null
for unavailable table cells, and its lean Monte Carlo block includes metric coverage.

Convergence diagnostics and engine tail estimates use each metric's defined sample.
Small-sample qualification remains in force; coverage is not evidence of convergence.
The joint capital-risk report requires complete aligned observations for NPV, DSCR, LLCR
and PLCR, and refuses an incomplete cohort of those before writing artifacts. An IRR is
the exception: see "IRR coverage" below.

The public HTTP response model is unchanged: its existing extensible engine-result
mapping carries these additive fields. Raw internal arrays gain nullable entries and
consumers must preserve their positions. No release, lender, Board, evidence-grade or
HOLD authority follows from this reporting correction.

## IRR coverage (#1746 step 1, #1763)

A trial whose cash flow changes sign more than once has no unique IRR, and one whose NPV
never reaches zero has none (#1525). Its IRR is unavailable while every other metric of
the trial is real. The evaluation gateway drops a KPI it cannot convert, so such a trial
usually reaches the aggregate as a `missing` observation rather than an `undefined` one.

Every IRR statistic is taken over that metric's defined trials, and every surface that
shows one says how many trials it leaves out:

- **Summary.** Each `summary[metric]` carries `defined_count` and `excluded_count`
  (total minus defined). An IRR metric (`project_irr`, `equity_irr`) that excludes any
  trial also carries `coverage_note`, the same text is listed under
  `metadata.irr_coverage_notes`, and a warning is logged. `project_irr_excluded_count`
  sits beside the flat `project_irr_*` fields. An MC job's API `engine_result` carries
  all of these.
- **Lender risk table.** An IRR row that excludes trials gains a `coverage_note` column
  beside its existing `defined_trials`, `total_trials` and `unavailable_trials`.
- **Capital-risk report** (owner ruling 2026-11-16, "Report with coverage"). The report is
  built rather than refused. Each IRR metric's VaR/CVaR, mean, percentiles and the
  probability below the equity hurdle are taken over its defined trials.
  `CapitalRiskReport.irr_coverage` records the counts and the note, and the snapshot's
  IRR rows carry them. The rendered report and the web results state each note before the
  figures, show "defined of total" trials beside every return metric, and state the
  trial count behind the hurdle probability. The API surface carries the same fields
  (contract 2.3). An IRR metric with fewer than 20 defined trials is still refused,
  because the VaR/CVaR tail needs at least 20 observations.

The capital-risk note says the excluded trials may be the worst outcomes, because a
lower-tail figure over the defined trials can then read better than the full
distribution. This disclosure moves no figure for a run in which every trial has a
defined IRR.

## Undefined IRR trials ranked worst (#1746 step 2)

Owner ruling on #1746 (2026-11-15): a Monte Carlo trial whose IRR is undefined ranks
below every defined trial. When a lower-tail percentile falls on those trials, it is
reported as undefined, at or below the lowest defined IRR, rather than as a number taken
from the defined trials only.

The Monte Carlo summary and the lender risk table apply it to `project_irr` and
`equity_irr` when any trial is excluded and at least one is defined
(`ranked_worst_percentiles` in `analytics/mc/aggregate.py`):

- **Percentiles.** The excluded trials take the lowest ranks of all trials, and each
  percentile is read at its position in that full ranking with `np.percentile`'s linear
  interpolation. A percentile whose position touches an excluded rank, including one that
  would interpolate between the last excluded and the lowest defined trial, is `None`.
  `percentile_bound` gives the lowest defined IRR that it lies at or below, and
  `percentile_basis` is `excluded_trials_ranked_worst`. Such a percentile is left out of
  `MonteCarloResult.percentiles`, and the flat `project_irr_p10` / `_p50` / `_p90` follow
  the ranking.
- **Upper tail.** An upper percentile is read from the same ranking, so it stays a number
  and moves down a little, because the excluded trials count in its denominator.
- **Mean and standard deviation.** A trial ranked worst has no value to average, so the
  mean and standard deviation stay over the defined trials; `mean_basis` is
  `defined_trials` and the note says so.
- **Minimum and maximum.** `min` is `None`, because the worst trial has no defined IRR;
  `min_defined` keeps the lowest defined value. `max` is unchanged.
- **Lender risk table.** P50, P90 (10th percentile) and P95 (5th percentile) of an IRR
  row are read from the ranking; an undefined one is a missing cell. The row's
  `coverage_note` gives the ranked note.

With no trial excluded the ranking is `np.percentile` exactly, so a run whose trials all
have a defined IRR is unchanged. The capital-risk report keeps the step 1 behaviour, per
the owner's 2026-11-16 ruling on #1763 ("Report with coverage"): its IRR VaR/CVaR,
percentiles and hurdle probability are over the trials that define each IRR, with the
excluded count stated. It does not rank undefined trials and gives them no hurdle
treatment.

## Independent oracle and impact

The pre-existing O-5 measurement is
[#1353 comment6422196112](https://github.com/arunakulat/dutchbay-epc-model/issues/1353#issuecomment-6422196112).
Its three trials have DSCR `[1.05, 1.31, 1.35]`, project IRR `[0.02, 0.09, 0.10]`
and equity IRR `[None, 0.11, 0.12]`. The earlier complete-case policy discarded the
first trial from every metric, raising DSCR minimum/P10 to `1.31/1.314` and project
IRR minimum/P10 to `0.09/0.091`. Metric-wise aggregation restores `1.05/1.102` and
`0.02/0.034`. Equity IRR retains its two defined observations, P10 `0.111`, with
coverage `2/3`; no equity IRR is fabricated for the first trial.

These are synthetic reporting deltas, not a canonical lender-case rebaseline. Tests
pair that independent oracle with responsiveness, null/zero distinction, all-undefined
serialization, trial alignment, failure provenance and consumer controls. Before/after
healthy seeded comparisons and exact candidate/base identities belong in the PR receipts.
Owner disposition is required before final freeze of this consequential reporting change.
