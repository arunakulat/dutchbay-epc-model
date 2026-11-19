- The FX and tenor screening runs for any scenario that declares a `financing_screening`
  block (#1578 U4 of the owner's 2026-11-16 ruling that every scenario includes the site
  analyses; block contract #1754).
  - `analytics/finance/fx_tenor_screening.py` holds the arithmetic with no site name, path or
    figure, and no default scenario: capex, tariff, O&M, FX at close, timeline, tax and the
    gearing cap come from the scenario itself. A scenario whose tariff indexes its O&M part
    (`tariff.om_indexation`) is screened on that two-part tariff, year by year as the engine
    prices it; the block then leaves out its own O&M escalation, which only a flat-tariff
    scenario states.
  - `scripts/run_fx_tenor_screening_v14.py scenario=<path>` runs it, with the method text in
    `conf/fx_tenor_screening.yaml`. A scenario without the block reports "not applicable".
  - The block contract gains what the screening reads: the lender tail, the three screening
    thresholds, the tariff O&M escalation, the reference generation, and optional tenor
    variants, named sensitivities, a fixed-debt FX stress grid and dated FX history.
  - `scenarios/dutchbay_basecase_2025Q4.yaml` carries the block, moved from
    `conf/blue_whale_fx_tenor_screening.yaml`. The engine does not read it.
  - The single-site module re-exports the moved functions and keeps its entry point, which
    now needs its scenario named in its config. #1799 retires it with its config and script. Its script prints byte-identical output
    (stdout hash pinned by a test), and the block-driven run reproduces it exactly.
  - No engine, scenario KPI or committed figure changes. The F-5 hold applies.
