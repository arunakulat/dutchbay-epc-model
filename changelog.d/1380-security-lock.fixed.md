- Raise `black` from `26.5.1` to `26.10.1`, `brotli` from `1.2.0` to `1.2.1`,
  `filelock` from `3.32.3` to `4.2.1`, and `setuptools` from `84.0.0` to `84.1.0`
  in the reproducibility lock. These fixed versions clear seven advisory records from the
  mandatory `pip-audit` gate without adding an allowlist exception; no model, scenario, KPI,
  release, or HOLD behavior changes.
