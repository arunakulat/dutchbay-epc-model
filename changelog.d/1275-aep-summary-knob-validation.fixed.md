- Range-validate the four KPI-moving AEP-summary config knobs at config consumption
  (`resource.uncertainty.p50_haircut_pct`, `correlation`, `life_years` and the
  `resource.power_curve` air-density pair), so each fails loud instead of being applied
  out of band, silently clamped, or silently skipped. A negative `p50_haircut_pct`
  previously inflated the bankable P50 by 12.2%, an out-of-range `correlation` was clamped
  to rho=1.0 while the summary echoed the raw value into provenance, and a half-declared
  density pair skipped the IEC 61400-12-1 correction for a +4.33% headline move. The
  summary's reported `uncertainty` block is now by construction the values the maths used.
  Every committed scenario regenerates unchanged.
