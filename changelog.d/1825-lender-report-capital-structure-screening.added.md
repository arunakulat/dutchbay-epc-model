- **Lender report: capital-structure screening (opt-in)** — the command-line lender report can now
  run the debt tranche mix, capex contingency and gearing-ceiling optimizers around the committed
  case, each held to the scenario's own covenants (`constraints.min_dscr_covenant`, and
  `min_llcr_covenant` / `max_balloon_pct` where declared) and ranked on equity NPV (#1456). The
  section shows every candidate, the realised gearing behind each ceiling, the contingency
  headroom the covenants allow, and the infeasibility register (#741) when nothing clears. A
  declared covenant the committed case itself fails is shown and not screened on. Off by
  default (`lender_report.capital_structure.enabled`); when off or not buildable it is listed
  under "Sections not run" with its reason. Screening only: no KPI moves (#1825 slice i).
