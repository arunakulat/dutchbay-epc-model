- Interactive `scripts/venv_up.sh` activation now honors an optional
  `DUTCHBAY_VENV_LOCK` absolute path and fails before provisioning or activation when
  the resolved environment differs. Unconfigured developer and CI hosts retain the
  portable config-first fallback. No runtime, financial formula, scenario, or KPI
  change.
