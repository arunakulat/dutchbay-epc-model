- **Async wind jobs: deterministic Weibull screening mode + genuine shear override
  (#993 / #994)** — `WindJobRequest` gains `resource_mode` (`era5` | `weibull`),
  `weibull_a` / `weibull_k`, and `shear_exponent` (CESSPIT-strict: a `weibull` job must
  carry BOTH A and k, a 422 at request time). In `weibull` mode the async job
  synthesises a deterministic, RNG-free hub-height wind series (an inverse-CDF Weibull
  quantile lattice) and feeds the SAME `WindPipeline` assessment seam — no ERA5 fetch,
  no network — so the result is identical in shape to the live path (the pipeline's MLE
  fit recovers the input A/k to ~4 significant figures). For the ERA5 path,
  `shear_exponent` now REPLACES the data-derived per-hour shear for every hour of the
  100m→hub extrapolation (`ERA5RequestConfig.shear_exponent_override`). NB: #994 as
  literally specified (`alpha_default`) only fills NaN hours and would not move AEP for a
  covered site, so the genuine per-hour override was implemented instead. All existing
  paths are byte-identical — the override defaults to `None` and `era5` mode is unchanged.
