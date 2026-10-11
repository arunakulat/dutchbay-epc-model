- **`llvmlite` 0.50.0 lands with the `numba` bump that allows it** — `numba 0.67.0` requires
  `llvmlite<0.50,>=0.49.0dev0`, so the standalone bump proposed in #1326 was an unconditional
  `ResolutionImpossible` at `pip install` (every shard died in under 45s with 0 tests run).
  `numba 0.68.0` requires `llvmlite<0.51,>=0.50.0dev0` and `numpy<2.6,>=1.22`, which this lock's
  `numpy 2.4.6` satisfies, so the two move together. Every other pinned consumer of `numba` states
  a lower bound only, or is extra-gated (`pandapower[performance]` wants `numba~=0.66`); cp312
  manylinux wheels exist for both releases. Suppressing the bump with a `dependabot.yml` ignore
  rule was considered and rejected: the ceiling is liftable today, so holding `llvmlite` back
  would have hidden a resolvable upgrade.
