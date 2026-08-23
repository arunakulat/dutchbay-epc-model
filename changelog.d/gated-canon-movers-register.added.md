- **Gated canon-movers register** — `docs/STANDARDS_WATCH.md` gains a hard-items section
  giving every gated KPI-moving change an owner, a gate and a **calendar review date**
  (2026-11-30), populated from a sweep of the open issue queue rather than from memory.
  `DELIVERY-01` governs how *big* an increment is; nothing governed how *hard* it is, and
  all five gated items were condition-gated with no calendar review — the state in which a
  live deferral quietly stops being asked about. The gates themselves are unchanged and
  remain correct; only the review dates are new. KPI-neutral.
- **n-sampling for generation** recorded in `docs/AGENTIC_DELIVERY_PRACTICE.md` §5.5 as an
  available technique rather than a rule, with its preconditions (declared scalar objective,
  explicit seed, whole sample set retained) and a hard boundary: never on finance logic,
  where correctness is not a scalar and "best of *k*" selects the most plausible-looking
  implementation.
