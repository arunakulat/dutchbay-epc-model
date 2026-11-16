- `run_full_pipeline_v14.py` gains `emit_all` (#1756), one switch for every optional emitter
  (executive workbook, capital-risk report, interaction grid, technology comparison and grid
  screening). By the owner's rulings of 2026-11-16 it is **on by default**, so every run
  produces the analyses its scenario has inputs for.
  - An explicit switch wins, so `emit_all=true emit_grid_screen=false` runs everything
    except grid screening, and `emit_all=false` runs no emitter, as before.
  - An emitter whose inputs the run lacks is not run. The run records why under
    `result['emitters']`, which every default run now carries. One that has its inputs and
    fails stops the run.
  - Default runs change. They now write the executive workbook, and they write the
    capital-risk report for any scenario with `monte_carlo.parameters`. The report runs its
    2,000-trial Monte Carlo, which takes about 1 min 40 s on the lender case (the run took
    2 s before). `summary.json` gains `emitters`, `executive_workbook_path` and
    `capital_risk_report_path`.
  - KPIs, `debt_result`, the equity distribution and `annual_rows.csv` are byte-identical
    with `emit_all` on and off.
  - The emitters' lender guards are unchanged.
  - A switch must now be `true`, `false` or `null`; any other value is refused.
  - A lint test ties `emit_all` to every `emit_*` switch the CLI reads.
  - No engine, scenario or KPI figure changes. The F-5 hold applies.
