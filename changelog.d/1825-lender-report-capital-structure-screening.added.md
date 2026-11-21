- **Lender report: capital-structure screening (opt-in)** — the command-line lender report can now
  run the debt tranche mix, capex contingency and gearing-ceiling optimizers around the committed
  case, each held to the scenario's own covenants (`constraints.min_dscr_covenant`, and
  `min_llcr_covenant`, `max_balloon_pct` and the refinancing cap
  `refinancing.max_refinance_pct` where declared) and ranked on equity NPV (#1456). The section
  shows every candidate with its headline minimum DSCR and sized debt, the realised gearing
  behind each ceiling, how the re-sized debt responds across the contingency range (it names no
  contingency), and the infeasibility register (#741) when nothing clears. When the debt is
  re-sized to the DSCR target, it says the DSCR screen holds by construction. A declared
  covenant the committed case itself fails is shown per candidate and not screened on. Off by
  default (`lender_report.capital_structure.enabled`); when off or not buildable it is listed
  under "Sections not run" with its reason. Screening only: no KPI moves (#1825 slice i).
