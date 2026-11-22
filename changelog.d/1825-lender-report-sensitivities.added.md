- **Lender report: lender sensitivities (opt-in)**: the command-line lender report can now add
  five sensitivity analyses of the committed case that were reachable only from their own
  scripts. They are one-at-a-time tornadoes on the per-period minimum DSCR and on the sized debt,
  a cost-of-equity band on the build-up WACC, LKR/USD rate, hedge-ratio and hedge-spread sweeps,
  and a financing Pareto screen around the scenario's own tenor and DSCR target. Sobol indices
  sit behind their own flag. Every point goes through the canonical evaluation gateway, and
  the tornadoes and Sobol go through the coupled-input seam (`coherent_overrides`). The Pareto
  screen refuses a coupled input instead of making its own copy of the coupling. Each part shows
  the committed figure it is measured from, and says so when its own base point does not
  reproduce that figure. A part that lacks an input, or raises, is listed with its reason, and
  the rest still renders. Off by default (`lender_report.sensitivities.enabled`). It is a
  sensitivity only: no KPI moves (#1825 slice ii).
