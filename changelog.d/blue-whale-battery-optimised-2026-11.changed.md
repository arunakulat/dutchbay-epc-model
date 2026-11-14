- Blue Whale: the solar + BESS battery is searched, not fixed, and the committed size is the
  search grid's floor, not an optimum. Owner, 7 Nov 2026, on PR 7's "Fix 5 MW / 20 MWh": "This
  should not be a fixed choice. It needs an MC run and a sensitivity analyze to optimize"; on
  the size to commit: "Whatever the optimiser picks"; 14 Nov 2026, after the review lanes found
  the first floor (0.5 MW) beaten by a smaller battery: "Battery floor 0.1 MW, PV unchanged".
  Work item: #1578 lines L-6, L-10, L-11 and the pricing half of W-4 (#1353 comments 6715108541
  and 6872251348). KPIs applied under the owner's delegation of 7 Nov 2026. No VERSION bump
  (#1625).
  - `solar_resource/pv_bess_sizing.py`: one-at-a-time sensitivity cases
    (`sensitivities.one_at_a_time`: any trial input, tariff, priority term, RTE, BESS O&M rate or
    dotted scenario key) and break-even searches by bisection (`sensitivities.break_even`); a
    best-PV-per-battery profile with paired-trial comparisons in each reading's recommendation;
    an `at_grid_edge` flag for the PV tables, PV AC and battery power of each choice. A BESS O&M
    shift re-prices the `bess_om` component of #1646's scenario O&M basis, so it cannot be
    silently overridden. Every block is strict: unknown keys, duplicate names, empty or
    non-physical shifts are refused. The fixed-battery child config and its summary are retired.
  - `scripts/run_blue_whale_pv_bess_sizing_v14.py`: each summary records the code that ran by
    content (`spec.code_sha256`: a `sha256sum` listing of every repository module imported, its
    tree digest and any files that differed from `git_sha`), because a squash merge leaves the
    run's commit outside `main` (MRM-02). A repository module imported from outside the
    checkout is refused rather than dropped.
  - Result (seed 20261101, 256 trials, 514 points, BESS 0.1-10 MW, on main after #1646): both
    readings of the 10 MW limit choose 107 tables (4.01464 MWp), 3.5 MW AC and 0.1 MW / 0.4 MWh,
    the lowest value of all three decision variables on the grid. P50 after-tax project NPV
    USD -4,441,537 (P90 -4,721,153). Every extra unit of battery, PV DC or PV AC lowers the NPV,
    so a smaller battery, or none, would lose less; the minimum admissible battery (input B18)
    is reopened as an owner decision. The comparisons are against larger batteries only: 14 of
    15 one-at-a-time cases stay on the floor (a 10% higher priority rate picks 0.5 MW, a near
    tie); 0.2 MW overtakes 0.1 MW at BESS capex USD 118.9/kWh or a priority rate of LKR
    54.14/kWh.
  - Solar + BESS scenario v0.9: project NPV USD -5,579,964 -> -4,477,787; equity NPV -6,167,137
    -> -4,557,056; min DSCR 0.8682 -> 0.8717; equity multiple 0.427 -> -0.099; discount rate
    11.49% -> 11.79%; equity and project IRR stay undefined; capex 8,292,579 -> 4,504,776. No
    corporate tax is paid at this size. Wind and the hybrid do not move. PR 3's sizing summary
    is not regenerated here: a re-run on the #1646 basis moves its choice, which is outside this
    change.
  - Disclosed, not modelled: L-10 (a utility-scale per-kWh BESS price applied at 0.4 MWh
    flatters a small battery) and L-11 (no fade or augmentation; cycling after the priority
    term). L-6: `conf/blue_whale_solar_bess.yaml` keeps PR 2's illustrative 5 MW / 30 MWh,
    DC/AC 1.2 and 0.96 inverter, now labelled, and a test shows the sizing ignores them. The
    PUCSL config's stale note on O&M indexation is corrected. W-4's pricing half is recorded in
    STATUS; the pricing config's own comments keep their wording until PR 3's summary, which
    pins its bytes, is regenerated, so it stays open on #1578.
