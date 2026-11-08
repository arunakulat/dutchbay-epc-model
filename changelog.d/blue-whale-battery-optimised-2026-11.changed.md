- Blue Whale: the solar + BESS battery is optimised, not fixed (15.23.0 -> 15.24.0). Owner, 7 Nov
  2026, on PR 7's "Fix 5 MW / 20 MWh": "This should not be a fixed choice. It needs an MC run and
  a sensitivity analyze to optimize"; on the size to commit: "Whatever the optimiser picks". Work
  item: #1353 comment 6715108541; #1578 lines L-6, L-10, L-11 and the pricing half of W-4. KPIs
  applied under the owner's delegation of 7 Nov 2026.
  - `solar_resource/pv_bess_sizing.py`: battery O&M priced on DC kWh (new `bess_opex` block, USD
    1.80/kWh-yr x 1.10 DC/nominal); one-at-a-time sensitivity cases (`sensitivities.one_at_a_time`:
    any trial input, tariff, priority term, RTE or dotted scenario key) and break-even searches by
    bisection (`sensitivities.break_even`); a best-PV-per-battery profile with paired-trial
    comparisons in each reading's recommendation. Every block is strict: unknown keys, duplicate
    names, empty or non-physical shifts are refused. The fixed-battery child config and its
    summary are retired.
  - `scripts/run_blue_whale_pv_bess_sizing_v14.py`: each summary records the code that ran by
    content (`spec.code_sha256`: a `sha256sum` listing of every repository module imported, its
    tree digest and any files that differed from `git_sha`), because a squash merge leaves the
    run's commit outside `main` (MRM-02; #1568's summaries cite f5b45904).
  - The sizing now prices the scenario's own basis (opex split by currency, one construction
    period, the indexed PUCSL O&M parts), answering #1568's assurance A-1 gate; the scenario
    reproduces the chosen point's base case with no override.
  - Result (seed 20261101, 256 trials, 414 points, BESS 0.5-10 MW): both readings choose 107
    tables (4.01464 MWp), 3.5 MW AC and 0.5 MW / 2.0 MWh, the smallest PV and battery on the
    grid. 152 tables was optimal only for the owner's 5 MW battery. P50 after-tax project NPV
    USD -3,817,369; the chosen battery beats every larger one in 100% of paired trials (1 MW by
    USD 60,964; 5 MW / 20 MWh by 936,502). Four of fifteen one-at-a-time cases favour 1.5-2.5 MW,
    by USD 6k-110k; break-even for 1 MW at BESS capex USD 128.3/kWh, priority rate LKR 52.25/kWh
    or BESS O&M USD 0.45/kWh-yr DC.
  - Solar + BESS v0.8: project NPV USD -4,440,000 -> -3,806,403; equity NPV -5,075,832 ->
    -3,948,909; equity IRR -5.00% -> undefined; min DSCR 0.8681 -> 0.8710; capex 8,292,579 ->
    4,729,960. PR 3's sizing is re-run and unchanged (DC/AC 1.1, 24 MWh). Wind and the hybrid do
    not move.
  - Disclosed, not modelled: L-10 (a utility-scale per-kWh BESS price applied at 2 MWh flatters
    a small battery) and L-11 (no fade or augmentation; cycling after the priority term). L-6:
    `conf/blue_whale_solar_bess.yaml` keeps PR 2's illustrative 5 MW / 30 MWh, DC/AC 1.2 and 0.96
    inverter, now labelled, and a test shows the sizing ignores them. The pricing config takes
    #1560's disclosure wording; the PUCSL config's stale note on O&M indexation is corrected.
