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
*describable*, while `require_engine_support` asserts it is *buildable*. The dangerous failure mode
here is not a crash but a scenario labelled with a resolution it silently does not receive — a config
that lies. `quarterly` sat behind that gate in A1 alone; it ships buildable here, because A2 widened
`ENGINE_SUPPORTED_RESOLUTIONS` in the same change. That is the two-seam split working as designed:
opening the gate required no change to how a resolution name is validated or normalised. The claim is
about that seam only — the resolver body itself *is* touched here, to call the shared container guard
described next. (An earlier revision said the resolver "was not touched in either dolphin", which the
same paragraph then contradicted.) An unrecognised, blank or non-string value fails loud rather than
falling back to annual; so does a `cashflow` node that is present but is not a `dict`, which would
otherwise be read as an absent key and demoted to the annual grid. That guard walks the config with
`get_nested` itself rather than re-implementing the walk, because its first version did
re-implement it and drifted: it matched keys exactly where the read matches case-insensitively, and
accepted any `Mapping` where the read requires a `dict`. Each gap reinstated the silent demotion the
guard exists to stop, and the second was the worse one — a non-`dict` mapping such as
`omegaconf.DictConfig`, carrying a well-formed value, resolved to annual with nothing about the
config looking wrong. The resolver never mutates the caller's config, and `PeriodGrid` enforces its own
documented `periods_per_year >= 1` invariant rather than relying on the resolver being its only
caller.

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
series. The section is written against the debt layer as it stands: there is now exactly one DSCR
index space, `dscr_periods` is the canonical labelled surface, and `raw_dscr_series` is a deprecated
alias new code must not use. An earlier revision of this text described a live collision between a
compacted and a positional series, which `finance.debt_v14` has since unified; it is corrected here
rather than shipped, because a docstring the next dolphin is told to follow is the one artefact in
this change that future work obeys.

The change is inert on every committed path: no scenario sets `cashflow.resolution` (pinned by a test
that reads the scenarios rather than asserting the claim), so every run resolves to the annual grid,
under which each helper is an identity or an order-preserving regrouping. The identity claim is
asserted on the float objects themselves wherever a helper returns its input unchanged, and on equal
values where a regrouping rebuilds the list. Outside this lane nothing imports the module —
`finance.subannual_rows_v14`, which ships alongside it here, does — and the canonical lender KPI
vector is unchanged. It confers no grade, release, lender or Board authority.
