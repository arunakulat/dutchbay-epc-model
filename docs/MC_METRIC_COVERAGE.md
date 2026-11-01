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
The joint capital-risk report requires complete aligned observations and now refuses an
incomplete cohort before writing artifacts. It directs callers to the metric-wise MC
summary and coverage rather than selecting complete cases or imputing zero. This is an
explicit limitation: partial-cohort joint reports are not delivered by this change.

The public HTTP response model is unchanged: its existing extensible engine-result
mapping carries these additive fields. Raw internal arrays gain nullable entries and
consumers must preserve their positions. No release, lender, Board, evidence-grade or
HOLD authority follows from this reporting correction.

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
