- **Lender report: cost and storage (opt-in)**: the command-line lender report can now add six
  cost and storage analyses that were reachable only from their own modules. They are the
  scenario's AACE estimate class and accuracy band; a CAPEX Monte Carlo held to the lender
  guards (at least 1,000 trials, toy fallback off, a fixed seed, and a factor-1.0 trial that
  must reproduce the committed project IRR, project NPV and minimum DSCR); the chronological
  storage dispatch ledger; the levelised cost of storage of each battery at the run's own
  discount rate; and the battery-project economics and EPC construction margin the run
  already publishes. The CAPEX Monte Carlo takes the scenario's declared CAPEX uncertainty, or
  else the spread its declared estimate class implies, and says which. A part that does not
  apply, lacks an input or raises is listed with its reason, and the rest still renders. Off
  by default (`lender_report.cost_storage.enabled`). It sits beside the committed case: no
  KPI moves (#1825 slice iii).
