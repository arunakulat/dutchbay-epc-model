Added `finance.subannual_rows_v14`, which allocates the annual cashflow rows onto the sub-annual
operating grid A1 introduced (Sprint 20, dolphin A2). `cashflow.resolution: quarterly` now builds
rows rather than being refused: A2 widened `ENGINE_SUPPORTED_RESOLUTIONS` exactly as A1's two-seam
split anticipated, and the resolver itself was not touched in either dolphin. An optional
`cashflow.within_year_profile` shapes the split; absent, it is an even one.

These rows are the annual engine's output **allocated**, not an independent sub-annual computation,
and the module docstring says so rather than leaving a reader to assume otherwise. Degradation, opex
escalation and FX are annual series in the engine, so every sub-period of a year inherits that
year's single rate; tax, depreciation and the loss carry-forward are computed annually and then
spread, which A4 will formalise; and `bess_augmentation_capex_lkr` is a discrete event that spreads
like any other flow, so its within-year dip is smoothed and therefore understated. What the
allocation does buy is a shaped within-year series that A3 can lay quarterly debt service onto to
expose an intra-year DSCR trough the annual series structurally cannot show.

Every one of the engine's 33 row keys is classified as either a FLOW (allocated across the year) or
YEAR-LEVEL (a rate, flag or year-end stock, carried unchanged), and a key in neither set raises
rather than being guessed at. Silently dropping an unclassified key loses cash and silently
allocating one would divide a rate; both yield plausible, wrong numbers, which is the single failure
this module's output could not reveal. A companion test reads the live lendercase's row keys and
asserts the two sets partition them, so the classification cannot quietly fall behind the engine.

Reconciliation is **exact under the default even profile** — 540 of 540 allocated flow-years on the
committed lendercase — and **within one unit in the last place** for an arbitrary profile (510 of
540 exact, 30 at one ULP, never worse, on a 0.35/0.15/0.15/0.35 seasonal split). The first draft
claimed exactness unconditionally; the firewall test disproved it on its first run against the live
scenario, where year-2 CFADS straddles a rounding boundary that no closing residual reaches and an
attempted correction merely oscillates between the two neighbouring floats. The contract was
narrowed to what is true rather than the test loosened to fit the claim, the bound is asserted as an
ULP count rather than a relative tolerance that could absorb a genuine allocation bug, and the
straddle case is pinned as a regression.

`finance.period_grid_v14.aggregate_flows_to_annual` now sums with `math.fsum` instead of the builtin
`sum`. Exact rounding makes the aggregate independent of summation order, which is what lets the
1-ULP bound be a real bound rather than an artefact of accumulation sequence; under the annual grid
each chunk holds one value and the result is unchanged.

The change is inert on every committed path: no scenario sets `cashflow.resolution`, so nothing
builds sub-annual rows, and the canonical lender KPI vector is unchanged. It confers no grade,
release, lender or Board authority.
