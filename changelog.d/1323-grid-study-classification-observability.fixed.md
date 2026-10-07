- **Grid Study CI now records how a run was classified, and names why evidence is missing (#1323).**
  - The `Classify changed paths` step writes a labelled block to its log and to its job summary.
    The block records the event `pull_request.base.sha`, its merge base with the head, the head
    itself, `code_changed` and the Grid Study classifier result. The log already showed the base
    and the result; the merge base and the labelled block are new. Through the API only the log
    can be read, so it carries the block too.
  - The classification semantics are unchanged. The workflow comment records that GitHub
    refreshes the payload base on every push, and that the result depends on it. An older base
    usually widens the diff and turns Grid Study on, but it can turn it off: when the head
    reverts a grid change `main` made, or when the head's own diff is empty.
  - `Validate complete Grid Study evidence` replaces its two bare `test -s` checks with named
    failures. A missing paired receipt now says whether its test was skipped (with the skip
    reason, for example andes not importable), absent, passed without writing the file, or left
    an empty or irregular file.
  - `tests/lint/test_grid_ci_policy.py` runs both steps as the runner does (`bash -e` on the
    step's own script, with the test interpreter's `python`) in throwaway workspaces. The
    classify step runs against widening, narrowing, unmerged and empty-diff bases, and against
    a classifier crash. The evidence step runs against a missing JUnit file, a failed grid test,
    and skipped, absent, unwritten, empty and complete receipts.
