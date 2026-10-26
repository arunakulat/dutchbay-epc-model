- **A `cashflow.within_year_profile` declared with no `cashflow.resolution` is now refused at
  pre-flight rather than ignored** (`F-03`, #1394). It is the one behaviour change the F-03 gate
  produces, recorded here rather than under Added because an operator holding such a file looks
  for it under Changed. Previously the config resolved to the default annual grid, whose single
  period per year never consulted the profile, so the run completed and returned an annual answer
  under a sub-annual label. It now fails before evaluation begins, naming the config path and the
  accepted values. No committed scenario declares either key -- no committed scenario has a
  `cashflow:` block at all -- so no committed KPI moves and every canonical figure is bit-identical
  across this change. What moves is a config held outside the repository: it gets a hard failure
  that names the fix instead of a plausible wrong answer. The same gate also refuses an unsupported
  `cashflow.resolution`, which previously reached evaluation before anything objected. `validation_mode="off"`
  still skips pre-flight entirely, as it did for every other check.
