- `run_full_pipeline_v14.py` gains `emit_all` (#1756), one switch for every optional emitter
  (executive workbook, capital-risk report, interaction grid, technology comparison and grid
  screening). By the owner's rulings of 2026-11-16 it is **on by default**, so every run
  produces the analyses its scenario has inputs for.
  - An explicit switch wins, so `emit_all=true emit_grid_screen=false` runs everything
    except grid screening, and `emit_all=false` runs no emitter, as before.
  - An emitter whose inputs the run lacks is not run. The run records why under
    `result['emitters']`, which every default run now carries. Monte Carlo parameters are
    read with the engine's own parser before the run, so a block the engine cannot read,
    including a non-numeric bound such as `low: null`, is listed with the parser's error.
    A malformed `tech_comparison` block is listed the same way, with its reason, rather than
    stopping the run: a block that is not a mapping (a list, a number), a `scenarios` value
    that is not a list, or an entry without a `label`, without a `config` or naming a file
    that does not exist. The check applies the emitter's own rules. Any other error while
    reading an emitter's inputs, such as an interpolation that cannot resolve, is listed with
    its reason too. After the figures are written, a config value read only to decide which
    earlier files to clear (an emitter's `path`, the capital-risk `npv_metric`) that cannot
    be read is logged and its default used, so it never stops the run; an emitter that runs
    reads the same key itself and fails as before.
  - `emit_all` writes files only in a run that writes its figures. With
    `write_artifacts=false` it switches no emitter on: each one not switched on by name is
    listed as not run with that reason, and the run writes nothing into the export
    directory, as before. A switch set by name still runs. The committed conf sets
    `write_artifacts: true`, as on main, so this is not what a plain CLI run does (below).
  - The default export directory is shared between runs, so one rule decides what a run
    does with an emitter's earlier output at its default path. While `emit_all` is on and
    the run writes its figures, every default path is the run's own: all are cleared before
    any emitter runs, so an earlier run's report never sits beside this run's figures, even
    when an emitter switched on by name fails and stops the run. An emitter that ends
    without writing its default path (not run, failed, switched off by name such as
    `emit_capital_risk_report=false` for a fast run, or writing to a configured path) names
    the removed files, relative to the export directory, under `removed_stale_outputs`; one that fails is cleared again of
    anything it wrote before failing. Otherwise (`emit_all=false`, or no figures written),
    an emitter attempted at its default path clears its own earlier output first and
    nothing else is touched. A configured path is never touched; an earlier default-path
    file beside it is cleared like any other, and a companion file the emitter writes again
    there (the capital-risk PNG) is not listed as removed. A
    run that writes its figures removes an earlier `summary.json` first and writes its own
    last, so a run that stops early leaves none.
  - The run writes `kpis.json`, `debt_result.json`, `equity_distribution.json` and
    `annual_rows.csv` before it plans or runs any emitter. An emitter switched on by `emit_all` that
    fails is recorded as `failed` with its error and logged; the run completes. An emitter
    switched on explicitly still stops the run when it fails.
  - **Every plain CLI run changes.** The committed conf sets `write_artifacts: true`, as on
    main, and the `feasibility_reproduce` kits and the release run use it, so a run with no
    extra switches now writes the executive workbook, and it writes the capital-risk report
    for any scenario whose Monte Carlo parameters the engine can read.
    The report runs its 2,000-trial Monte Carlo, which takes about 1 min 40 s on the lender
    case (the run took 2 s before). The export directory gains `executive_workbook.xlsx`,
    `capital_risk_report.html` and `npv_distribution_equity_npv.png`. `summary.json` gains
    `emitters`, `executive_workbook_path` and `capital_risk_report_path`.
  - Other effects of the default: such a run's stdout grows from about 0.2 MB to about
    58 MB on the lender case, because the Monte Carlo writes a log line per trial. The
    `feasibility_reproduce` kits use the default command, so they now run the 2,000-trial
    Monte Carlo for each scenario that has readable parameters, and the
    `run_all_NOV26.sh` workbook and capital-risk step repeats what the default already
    wrote. The release asset gains the three files above.
  - The executive workbook carries the F-5 non-reliance notice in cell A1 of its first
    sheet ("Summary"), so it shows on opening; the KPI table follows from row 3, unchanged
    (owner ruling, 2026-11-16 07:19Z). The
    capital-risk report carries the same notice on its cover. Other reports are unchanged.
  - KPIs, `debt_result`, the equity distribution and `annual_rows.csv` are byte-identical
    with `emit_all` on and off.
  - The emitters' lender guards are unchanged.
  - A switch must now be `true`, `false` or `null`; any other value is refused.
  - A lint test ties `emit_all` to every `emit_*` switch the CLI reads.
  - The report's model-limitations text no longer calls the Monte Carlo surface opt-in,
    because a default run now writes it.
  - No engine, scenario or KPI figure changes. The F-5 hold applies.
