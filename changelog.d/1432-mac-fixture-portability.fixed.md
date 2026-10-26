- Stage the invalid-byte handover record with `git update-index` instead of writing it
  into the worktree, so
  `test_handover_resolver_rejects_control_character_filenames` builds on Darwin —
  which rejects a non-UTF-8 filename with `EILSEQ` — as well as on Linux. The
  resolver is still proven to reject the invalid-byte name itself; no test is skipped
  or weakened, and no model, scenario, KPI, release or HOLD behaviour changes.
