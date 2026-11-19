- The three AEP helpers with live callers now live in the main wind engine (#1615 step A;
  owner ruling 2026-11-16). The Weibull-by-power-curve integral `gross_aep_farm_gwh` moved to
  `wind_resource/aep_integral.py`, and the AEP summary builder, including
  `build_aep_summary_from_config` and the wind-rose resolver, moved to
  `wind_resource/aep_summary.py`. Cross-validation, the ARCO assessment, the report wind rose,
  the met-mast transfer and the Blue Whale wind scripts import them from there.
  `analytics.wind.aep_tornado` and `analytics.wind.aep_summary_builder` re-export the moved
  names, so there is one implementation. The AEP cluster's boundary-guard allowlist is now
  empty, and the deprecation decision record carries both #1615 rulings. The code moved
  unchanged: AEP summaries, tornadoes and wind roses for every committed wind scenario hash
  identically before and after. No engine, scenario or KPI figure changes. The F-5 hold
  applies.
