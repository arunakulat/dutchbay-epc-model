- The Monte Carlo engine refuses a parameter named `capex` (any case or padding) before
  sampling on any scenario that has a capex section (#1793). Every trial of such a
  scenario refuses the name, so the run could only report toy KPIs or fail late. Sweep
  `capex.usd_total`, or `capex.input.amount` on a native-CAPEX scenario. The minimal
  smoke config, which has no capex section, keeps the name. The emitter plan lists the
  refusal with its reason.
