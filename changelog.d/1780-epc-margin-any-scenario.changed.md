- The EPC construction-margin model (`finance/epc_margin.py`) now works for any scenario
  (#1780). Before this, only a standalone script that read one site's scenario could reach
  it. This follows the owner's 2026-11-16 ruling that all code must be available to any
  scenario.
  - A scenario that declares an `epc` block gets `result["epc_margin"]` from the pipeline,
    beside its own figures. No scenario KPI moves.
  - Pre-flight checks a declared block strictly and refuses unknown keys.
  - With validation off, a bad block is listed with its reason and the scenario's figures
    are still written.
  - An EPC-only scenario, one with an `epc` block and no operating project, runs through
    `run_full_pipeline_v14.py` and prints its margin as JSON. It exits 1 when the block does
    not compute.
  - `scripts/run_epc_margin.py` is retired.
  - The module no longer names a site or a utility.
