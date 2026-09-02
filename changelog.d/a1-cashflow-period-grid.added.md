Added `finance.period_grid_v14`, the single resolver for cashflow resolution and the first slice of
optional sub-annual cashflow (Sprint 20, dolphin A1). The engine is annual by construction —
`build_annual_cfads` / `build_annual_rows` produce one row per operating year — so an annual series
cannot show an intra-year DSCR trough, while lender convention is at least quarterly debt service.
This module lands the period arithmetic that a sub-annual layer needs, one dolphin ahead of the
sub-annual operating rows (A2) that will consume it, so the aggregation contract can be pinned before
any cashflow depends on it.

The new `cashflow.resolution` key accepts `annual` (the default) or `quarterly`, resolving to a
frozen `PeriodGrid` carrying the canonical name and its periods-per-year. Resolution and engine
support are deliberately two separate seams: `resolve_period_grid` validates that a resolution is
*describable*, while `require_engine_support` asserts it is *buildable*. `quarterly` passes the first
and fails the second today, because the dangerous failure mode here is not a crash but a scenario
labelled `quarterly` silently receiving annual rows — a config that lies. A2 widens
`ENGINE_SUPPORTED_RESOLUTIONS` rather than changing the resolver. An unrecognised, blank or
non-string value fails loud rather than falling back to annual, and the resolver never mutates the
caller's config.

Aggregation back to the annual axis is split by variable kind, because getting it wrong is a silent
value error rather than a crash: `aggregate_flows_to_annual` sums quantities measured over a period
(revenue, opex, CFADS, debt service) and `aggregate_balances_to_annual` takes the period-end value of
quantities measured at an instant (debt outstanding, reserve balances). There is deliberately no
generic `aggregate` — the caller must say which kind it holds. A series whose length is not a whole
number of operating years is rejected outright, since truncating or zero-padding a ragged tail would
misattribute or drop cash.

The module docstring names the three index spaces now in the model and the sanctioned two-hop
alignment chain between them. The operating sub-period space subdivides operating years *only* — it
carries no construction periods, no bridge and no padding — so aligning a sub-period to a debt period
goes through the operating row and then `annual_row_debt_period_map`, never directly onto a debt
series. This is stated explicitly because the debt layer already documents a live collision between
its compacted `dscr_series` and its positional `raw_dscr_series`, and a third axis added carelessly
would compound it.

The change is inert on every committed path: no scenario sets `cashflow.resolution` (pinned by a test
that reads the scenarios rather than asserting the claim), so every run resolves to the annual grid,
under which each helper is an identity or an order-preserving regrouping — asserted at float-object
identity, not merely at equal values. Nothing imports the module yet beyond its tests, and the
canonical lender KPI vector is unchanged. It confers no grade, release, lender or Board authority.
