Added the debt period taxonomy to `finance.debt_v14.plan_debt`'s public result, which previously
omitted it: `_resolve_construction_periods` returns 2 for the lender case while
`debt_result.get("construction_periods")` returned `None` — the key was absent and the value reached
callers only under the different name `construction_years` — the bridge index was reachable only as
`cfads_bridge_debt_period`, and the first operating period was not derivable at all without knowing
the engine's internal synthetic-bridge convention, so a consumer holding a `debt_result` could not
tell which debt periods are operating. The result now carries `construction_periods: int`,
`bridge_debt_period: int | None` and `first_operating_period: int` unconditionally, on every config
path, with an explicit `None` where a bridge does not exist rather than a plausible substitute. The
count is read from the value the engine already resolved through the shared resolver inside
`apply_debt_layer` rather than re-derived with a second default — the divergent defaults were the
cause of the omission — and is read after the balloon treatment, so an `amortize` resize is
reflected. `first_operating_period` takes the row-to-period map as its definitional source and falls
back to the timeline layout only where no operating row exists. The `plan_debt` docstring now states
the index space of every published series and warns that the compacted `dscr_series` and the
positional `raw_dscr_series` are in incompatible spaces while `annual_row_debt_period_map` indexes
the raw one, so `debt_result["dscr_series"][debt_period]` reads a different period than intended;
that collision is documented and pinned by a test, deliberately not fixed here. The change is purely
additive: the three keys are appended after every pre-existing key, so the existing 40-key mapping
survives untouched as a prefix, verified byte-identical across all 21 evaluable committed scenarios
with the canonical lender KPI vector unchanged. It confers no grade, release, lender or Board
authority.
