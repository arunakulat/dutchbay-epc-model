- `run_full_pipeline_v14.py` gains `emit_all` (#1756), one switch for every optional emitter
  (executive workbook, capital-risk report, interaction grid, technology comparison and grid
  screening). By the owner's rulings of 2026-11-16 it is **on by default**, so every run
  produces the analyses its scenario has inputs for.
  - An explicit switch wins, so `emit_all=true emit_grid_screen=false` runs everything
    except grid screening, and `emit_all=false` runs no emitter, as before.
  - An emitter whose inputs the run lacks is not run. The run records why under
    `result['emitters']`, which every default run now carries. Monte Carlo parameters are
    read with the engine's own parser before the run, so a block the engine cannot read is
    listed with the engine's reason.
  - The run writes `kpis.json`, `debt_result.json`, `equity_distribution.json` and
    `annual_rows.csv` before any emitter runs. An emitter switched on by `emit_all` that
    fails is recorded as `failed` with its error and logged; the run completes. An emitter
    switched on explicitly still stops the run when it fails.
  - Default runs change. They now write the executive workbook, and they write the
    capital-risk report for any scenario whose Monte Carlo parameters the engine can read.
    The report runs its 2,000-trial Monte Carlo, which takes about 1 min 40 s on the lender
    case (the run took 2 s before). The export directory gains `executive_workbook.xlsx`,
    `capital_risk_report.html` and `npv_distribution_equity_npv.png`. `summary.json` gains
    `emitters`, `executive_workbook_path` and `capital_risk_report_path`.
  - Other effects of the default: a default run's stdout grows from about 0.2 MB to about
    58 MB on the lender case, because the Monte Carlo writes a log line per trial. The
    `feasibility_reproduce` kits use the default command, so they now run the 2,000-trial
    Monte Carlo for each scenario that has readable parameters, and the
    `run_all_NOV26.sh` workbook and capital-risk step repeats what the default already
    wrote. The release asset gains the three files above.
  - The executive workbook carries the F-5 non-reliance notice on its first sheet
    ("Summary"), one blank row below the KPI table (owner ruling, 2026-11-16 07:19Z).
  - KPIs, `debt_result`, the equity distribution and `annual_rows.csv` are byte-identical
    with `emit_all` on and off.
  - The emitters' lender guards are unchanged.
  - A switch must now be `true`, `false` or `null`; any other value is refused.
  - A lint test ties `emit_all` to every `emit_*` switch the CLI reads.
  - No engine, scenario or KPI figure changes. The F-5 hold applies.
