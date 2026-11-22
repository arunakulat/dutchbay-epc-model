- The Sri Lanka tax and levy code now refuses a scenario that declares another jurisdiction
  (#1882). `TaxConfig.from_yaml` and `resolve_indirect_taxes` raise a `ValueError` naming
  #1841 when `project.jurisdiction` is present and is not Sri Lanka (`Sri Lanka`, `LK` or
  `LKA`, any case), so a project elsewhere can no longer inherit Sri Lanka corporate tax,
  loss rules, WHT, SSCL or import levies by accident. Scenarios that say Sri Lanka, or do
  not set the key, run exactly as before; no KPI moves. Making the key required stays with
  #1841's PR 3. The Dolphin 2 charter's stale "no global `ProjectCase`" line now carries a
  dated status note naming #1191, #1842 and #1843.
