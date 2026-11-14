- Blue Whale: the solar + BESS battery is optimised, not fixed. Owner, 7 Nov 2026, on PR 7's
  "Fix 5 MW / 20 MWh": "This should not be a fixed choice. It needs an MC run and a sensitivity
  analyze to optimize"; on the size to commit: "Whatever the optimiser picks". Work item: #1578
  lines L-6, L-10, L-11 and the pricing half of W-4 (#1353 comments 6715108541 and
  6872251348). KPIs applied under the owner's delegation of 7 Nov 2026. No VERSION bump (#1625).
  - `solar_resource/pv_bess_sizing.py`: one-at-a-time sensitivity cases
    (`sensitivities.one_at_a_time`: any trial input, tariff, priority term, RTE, BESS O&M rate or
    dotted scenario key) and break-even searches by bisection (`sensitivities.break_even`); a
    best-PV-per-battery profile with paired-trial comparisons in each reading's recommendation.
    A BESS O&M shift re-prices the `bess_om` component of #1646's scenario O&M basis, so it
    cannot be silently overridden. Every block is strict: unknown keys, duplicate names, empty
    or non-physical shifts are refused. The fixed-battery child config and its summary are
    retired.
  - `scripts/run_blue_whale_pv_bess_sizing_v14.py`: each summary records the code that ran by
    content (`spec.code_sha256`: a `sha256sum` listing of every repository module imported, its
    tree digest and any files that differed from `git_sha`), because a squash merge leaves the
    run's commit outside `main` (MRM-02).
  - Result (seed 20261101, 256 trials, 414 points, BESS 0.5-10 MW, on main after #1646): both
    readings of the 10 MW limit choose 107 tables (4.01464 MWp), 3.5 MW AC and 0.5 MW / 2.0 MWh,
    the smallest PV and battery on the grid. P50 after-tax project NPV USD -4,534,558 (P90
    -4,794,729); the chosen battery beats every larger one in 100% of paired trials (1 MW by
    USD 95,902; 5 MW / 20 MWh by 1,394,680). No one-at-a-time case changes the choice; 1 MW
    breaks even at BESS capex USD 114.7/kWh or a priority rate of LKR 55.22/kWh, and no BESS O&M
    rate from 0 to 5 USD/kWh-yr DC changes it. Every point loses money: this is the
    loss-minimising size, not a bankable one.
  - Solar + BESS scenario v0.9: project NPV USD -5,579,964 -> -4,518,152; equity NPV -6,167,137
    -> -4,628,675; min DSCR 0.8682 -> 0.8703; equity IRR stays undefined; capex 8,292,579 ->
    4,729,960. Wind and the hybrid do not move. PR 3's sizing summary is not regenerated here:
    a re-run on the #1646 basis moves its choice, which is outside this change.
  - Disclosed, not modelled: L-10 (a utility-scale per-kWh BESS price applied at 2 MWh flatters
    a small battery) and L-11 (no fade or augmentation; cycling after the priority term). L-6:
    `conf/blue_whale_solar_bess.yaml` keeps PR 2's illustrative 5 MW / 30 MWh, DC/AC 1.2 and 0.96
    inverter, now labelled, and a test shows the sizing ignores them. The PUCSL config's stale
    note on O&M indexation is corrected. W-4's pricing half is recorded in STATUS; the pricing
    config's own comments keep their wording until PR 3's summary, which pins its bytes, is
    regenerated.
