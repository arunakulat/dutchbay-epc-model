- `run_full_pipeline_v14.py` gains `emit_all` (#1756, owner ruling 2026-11-16): one switch
  that turns on every optional emitter (executive workbook, capital-risk report,
  interaction grid, technology comparison and grid screening).
  - An explicit switch wins, so `emit_all=true emit_grid_screen=false` runs everything
    except grid screening.
  - Under `emit_all`, an emitter whose inputs the run lacks is not run, and the run records
    why under `result['emitters']`. One that has its inputs and fails stops the run.
  - The emitters' lender guards are unchanged.
  - `conf/run_full_pipeline_v14.yaml` sets `emit_all: false` and every `emit_*` switch to
    `null`, which means off unless `emit_all` is on, so default runs are unchanged.
  - A switch must now be `true`, `false` or `null`; any other value is refused.
  - A lint test ties `emit_all` to every `emit_*` switch the CLI reads.
  - No engine, scenario or KPI figure changes. The F-5 hold applies.
