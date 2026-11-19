---
"1810":
  changed:
    - Added opt-in CPU worker pool parallelization (`n_workers`, defaulting to `1` serial execution) via `ProcessPoolExecutor` in `solar_resource.pv_bess_sizing` and `solar_resource.pv_bess_sizing_runner`, preserving bit-exact seeded parity with single-core execution while calling `evaluate_with_overrides` unchanged.
