- **Factual corrections to uncompiled changelog fragments and to two config comments, made
  before the next compile publishes them** (#1405). Each item was verified against the
  repository rather than against the wording being corrected. In `.github/dependabot.yml`: the
  `mpmath` entry claimed #1325 reported "two install conflicts rather than one", but #1325's
  logs name only the `numpy-typing-compat` conflict -- `pip` reported that one and stopped --
  so one conflict was observed, and `mpmath`'s unmergeability rests on `sympy`'s published cap
  instead; the `numpy-typing-compat` entry credited #986/#988 with adding the major-only rule,
  which #990 added (commit `f6075686`) after that post-mortem; the same entry attributed "well
  under a minute" to whole jobs rather than to the install step that failed; and the `numpy`
  entry's lift instruction now cross-references `numpy-typing-compat`, which must move in the
  same step because its patch segment carries the `numpy` range it requires. In the `Makefile`,
  the comment above `lint` called `black --check` advisory and "non-blocking by design"; CI runs
  it with no `|| true` in the `Code Quality Checks` job and the `Test Summary` gate blocks the
  merge on that job, so it is mandatory, and the 210-file style-drift backlog that made it
  advisory was cleared by the repo-wide reformat. Three pending fragments were corrected in
  place and so carry no separate entry of their own: the `mpmath` fragment repeated the
  "major-only default" claim although `mpmath` had no ignore entry at all before #1343; the
  environment-probe fragment did not declare that the correction can turn a previously passing
  environment into a failing one, that this is intended, and that the remedy is to recreate the
  environment; and the `SECDEP-01` fragment lumped the environment channel in with `make -i` and
  a command-line override, where the `SECDEP-01` row distinguishes it -- an environment-selected
  vulnerability service changes what an audit finds rather than its arguments or exit status, so
  the argument pinning, dry-run comparison and forced-fail sentinels are blind to it by
  construction, while the direct suppression channel through the environment is closed. No
  runtime, financial formula, scenario, model input or KPI change.
