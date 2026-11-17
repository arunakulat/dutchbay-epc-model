- The debt engine's gearing, target DSCR and flat P99 downside factor have no code default
  (#1429, owner decision 2026-11-14). The engine used to fill an absent `debt_ratio`,
  `target_dscr` or `dscr_p99_downside_factor` with Dutch Bay figures (0.70, 1.30, 0.80).
  Strict pre-flight (`validate_config_for_v14` with the `debt` module) now refuses a scenario
  that omits one, naming its YAML path, through the new engine resolver
  `finance.debt_v14.resolve_debt_sizing_terms`; the engine refuses again at each point of
  use. The downside factor is required only where the DSCR autosolve reads it: always
  without `bind_downside`, and with it only when neither `downside_cfads_factor` nor a
  P50/P90 AEP pair resolves. A declared value that is not a finite number is refused rather
  than replaced.
- No figure moves. Every committed engine scenario already declares these terms: all 33
  scenarios that run on `main` give byte-identical KPIs, debt and equity results. Test
  fixtures that leaned on the fallbacks now declare the values they were given, the solar
  assessment script declares the 0.80 factor when it switches the base case to DSCR sizing,
  and the D3C success digest is re-pinned because its fixture now echoes `debt.debt_ratio`
  (main's engine gives the same digest with that fixture).
- The balloon bisection now takes its upper bound from the config's own gearing when the
  config has no `Financing_Terms` section, instead of 0.70.
- The standalone `size_debt_with_dual_dscr` API keeps its keyword defaults (inventory row
  D12). The compact `debt:` schema passes an absent gearing or target through to the debt
  layer, so callers that read only its rates (the FX hedge's CIP forwards) are unaffected.
