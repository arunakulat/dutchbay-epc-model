- The standalone battery-project economics (`finance/bess_project_economics.py`: landed capex,
  the capacity-charge effective-cost curve, the charging-cost lever, and the battery's own
  cashflow with IRR, NPV and LCOS) now run for any scenario that declares
  `bess_economics.enabled: true` (#1774, after the owner's 2026-11-16 ruling that all code
  must be available to any scenario). Until now nothing called the module. The canonical
  pipeline returns the result under `bess_project_economics`, at the scenario's own project
  discount rate and project life. A scenario that opts in without a capacity-charge battery
  gets a `not_applicable` entry with the reason. A declared block is checked strictly in
  pre-flight, naming the path. `bess_economics.discharge_cycles_per_year` is now a required
  input: the code no longer defaults it to one tender's figure. The module names no supplier,
  quote or tender, and `ceb_effective_cost_curve` is renamed
  `capacity_charge_effective_cost_curve`. The battery's IRR and NPV are reported in USD:
  each year's LKR flow is translated at the scenario's operating FX curve (with its
  construction offset) and discounted at the project rate, on a nominal, pre-tax, unlevered
  basis the result states; the LKR series and its IRR are kept for reference. The block
  describes one battery, so a scenario with two capacity-charge batteries is refused, and
  the unused `charging.cycles_per_year` input is removed. No committed scenario declares the block, so no
  engine, scenario or KPI figure moves. The F-5 hold applies.
