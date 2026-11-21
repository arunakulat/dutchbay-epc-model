- The Monte Carlo engine's toy fallback is now off by default (#962, owner decision
  2026-11-21). A config that does not declare `monte_carlo.allow_toy_fallback` stops at the
  first trial whose full evaluation fails, with that trial's error, instead of reporting a
  fabricated toy metric. A smoke config that exercises the toy path opts in with
  `allow_toy_fallback: true`; declared lender and IC run modes refuse it even then. No
  committed scenario's trials fail, so no committed KPI or Monte Carlo trial moves; only
  the recorded `metadata.allow_toy_fallback` of the twelve committed scenarios that did not
  declare the key changes from true to false.
