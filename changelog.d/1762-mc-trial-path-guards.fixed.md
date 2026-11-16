- Monte Carlo trial-path guards (bundle F4; #1762, #1728, and the #1629 dry-run item). No
  deterministic KPI and no committed figure changes.
  - Pre-sampling dry run (#1629). `analytics/mc/engine.py` merges the base config with each
    parameter's low and then high bound, as a trial builds its overrides, and runs the trial
    path's own checks: the strict pre-flight (native CAPEX normalisation and
    `validate_config_for_v14`) and the CAPEX resolution (`_extract_capex_usd`). A sweep they
    refuse is refused before sampling with the parameter, bound and reason named, instead of
    failing at trial 0 or falling back to toy trials. It catches the six native names the
    #1695 domain lane listed (M-1), a bare `capex` sweep on a USD scenario, and
    `capex.input.amount` on an already resolved native config (with a message to start from
    the authored config). A base config that does not itself resolve is left to the trials,
    so smoke configs behave as before. Every committed list-form Monte Carlo scenario passes.
    The hand-kept native guard list stays as the first, more specific check.
  - 5 US-cent fixed-LKR variant (#1762). Its CAPEX derives from `capex.breakdown`, so a
    sampled `capex.usd_total` failed the breakdown cross-check on every trial and the
    capital-risk Monte Carlo stopped at trial 0. A parameter can now declare
    `reconcile_breakdown: pro_rata`: each breakdown line scales with the sampled total, a
    uniform overrun or underrun. The engine refuses the key on any other parameter, without
    `derive_from_breakdown`, with a QRA contingency, or with an empty breakdown.
    `scenarios/dutchbay_lendercase_5usc_fixed_lkr.yaml` declares it on its CAPEX sweep, and
    the variant's Monte Carlo now runs its trials. Its deterministic run does not read the
    key.
  - Fixed-debt stress on the covenant basis (#1728). `metadata.fixed_debt_stress` now divides
    each trial's operating-row CFADS, net of the base (committed-debt) senior fee, by the base
    debt service, with the bridge period's service folded into operating year 1 as
    `dscr_by_year` does. With trial = base it reproduces the base `dscr_by_year` minimum
    exactly. It reads `annual_row_debt_period_map` and no longer the deprecated
    `raw_dscr_series`. The block gains `status` and `basis` keys. A run with the toy fallback
    off (the lender scenarios, lender and IC modes, the capital-risk report) raises when the
    stress is on and the base has no covenant period or a trial publishes no CFADS for one; a
    permissive run records `status: unavailable` with the reason and a warning, instead of
    leaving the key silently absent. Stated limits: a trial's CFADS is its own pipeline's, so
    a CFADS term that depends on its re-sized debt is not re-based, and the refinanced balloon
    falls outside the stress (its coverage is disclosed separately). The lender case's
    stress figures move onto the stricter basis; they remain metadata under F-5 and support no
    covenant, lender or IC representation. Monte Carlo summaries and trials are unchanged.
