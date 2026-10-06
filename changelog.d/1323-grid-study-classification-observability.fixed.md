- **Grid Study CI now records how a run was classified, and names why evidence is missing (#1323).**
  - The `Classify changed paths` job summary records the event `pull_request.base.sha`, its
    merge base with the head, the head itself, `code_changed`, and the Grid Study classifier
    result. A reviewer can now see from CI evidence which base classified a run.
  - The classification semantics are unchanged. The workflow comment records that GitHub
    refreshes the payload base on every push, and that the result depends on it: an older
    base usually widens the diff, but can narrow it, for example when the head reverts a
    change `main` made.
  - `Validate complete Grid Study evidence` replaces its two bare `test -s` checks with named
    failures. A missing paired receipt now says whether its test was skipped (with the skip
    reason, for example andes not importable), absent, or passed without writing it.
  - `tests/lint/test_grid_ci_policy.py` runs the real classify step in throwaway repositories
    against fresh and stale bases, one where staleness widens the diff and one where it
    narrows it, and runs the real evidence validator against skipped, absent and complete
    receipts.
