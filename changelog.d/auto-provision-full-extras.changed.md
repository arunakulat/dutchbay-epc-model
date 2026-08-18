- **Web sessions now provision FULLY and automatically** — `.claude/settings.json` gains an
  `env` block setting `DUTCHBAY_EXTRAS=dev,feasibility,jobs,solar,pareto`, which the harness
  injects before the SessionStart hook runs, so grid, micro-siting, redis, solar and pareto
  are present with no flag to remember and `redis-server` starts on :6379.
  The hook's own fallback is now the **same full set** rather than a bare `dev`: relying on
  the env alone would leave a silently under-provisioned session if injection ever failed,
  and that fails LATE (a missing import halfway through a run) instead of loudly at start.
  `DUTCHBAY_EXTRAS=dev` still selects the fast tests-and-linters path explicitly. All three
  paths verified — env-supplied, fallback, and explicit-fast.
  Cost of the full default is roughly a gigabyte (JAX/numba/openmdao via TopFarm) and a few
  minutes at session start, paid deliberately: this repo's work needs grid, micro-siting and
  the job path far more often than a fast start, and a half-provisioned environment is the
  more expensive failure. CI is unaffected — the hook is remote-session-only.
