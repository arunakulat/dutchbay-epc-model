- The Blue Whale wind scenario now carries a Monte Carlo block (#1822), so a default run
  of it emits the capital-risk report and the P10/P50/P90 IRR with trial coverage. Four
  drivers are swept, each band taken from the scenario's own inputs or the summaries it
  cites, and a test re-derives each one: yield (the met-mast lifetime 1-sigma, a normal
  95% interval), capex (the blend's low, mode and high cases, triangular), opex (the
  3-4% O&M benchmark band, a placeholder) and the FX spot (the declared 5% move). The
  tariff and curtailment have no declared band and are not swept. The toy fallback is
  off and the fixed-debt covenant stress is on. Screening only: the met-mast HOLD stands
  and no P90 from this block is a lender P90. The deterministic result is unchanged.
