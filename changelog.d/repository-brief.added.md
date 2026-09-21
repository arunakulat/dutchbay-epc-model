- `docs/dutchbay-epc-model-brief.md`: a dated orientation brief for the repository — what the
  model is, how the tree is laid out, how it is run and tested, the GWTF conventions a
  contributor has to follow, what was in flight on 2026-09-21, and the standing maintenance
  chores with the cadence the project owner set.
- The brief is explicitly a snapshot rather than normative text: every count carries the command
  that produced it, and the header states that `go_with_the_flow_rules_v3_0_clean.csv` and
  `AGENTS.md` win wherever the brief disagrees. Its filename sits outside every handover family
  `scripts/list_session_handover_records.py` recognises, so it cannot enter the `PERSIST-01`
  chain.
- It records two traps that are silent when hit: the remote container clones shallow, so the
  handover resolver fails closed until `git fetch --unshallow` has run, and the repository
  ruleset rejects a merge once the branch is behind `main`, so batches serialize one CI cycle
  at a time.

- Financial impact: none. Documentation only; no engine, scenario, configuration or test
  behaviour is touched.
