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
    so smoke configs behave as before. Every committed list-form Monte Carlo scenario passes
    except the 5 US-cent fixed-LKR variant, whose trials all failed already (below).
    The hand-kept native guard list stays as the first, more specific check.
  - Breakdown reconciliation (#1762, engine half). A `capex.usd_total` sweep on a
    `capex.derive_from_breakdown` scenario failed the breakdown cross-check on every trial.
    A parameter can now declare `reconcile_breakdown: pro_rata`: each breakdown line scales
    with the sampled total, a uniform overrun or underrun. The engine refuses the key on
    any other parameter, without `derive_from_breakdown`, with a QRA contingency, or with
    an empty breakdown. No committed scenario declares it yet, so the 5 US-cent fixed-LKR
    variant's sweep is now refused before sampling, with the fix named, instead of
    stopping at trial 0; declaring it on that lender scenario is a separate R3 change.
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
    The lender case's comment and the web job's docstring that called the stress basis
    unfolded are corrected.
