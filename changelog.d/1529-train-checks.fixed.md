- **The merge-train and merge checks now catch what #1515's reviewers showed they missed.** The
  steward skill's `TRAIN-01` blocks and its single pull-request merge check (`#1529`):
  - **Each train commit is checked against its car in full.** The pre-landing check now compares
    each train commit's message body and author with the car's recorded merge message and author.
    The author is the car pull request's author, as a squash merge would record it. The check
    also confirms that each car's reviewed head is still `refs/pull/<pr>/head`, and that the
    recorded `main` is `origin/main`.
  - **The pre-landing check runs twice.** It runs once before the train is opened ready, so a
    mis-built train never spends a full-suite run, and again just before landing.
  - **If `main` moves, the train is rebuilt, never refreshed with a merge commit.**
  - **The landing check is anchored to `main`.** It now confirms that the landed SHA equals the freshly fetched
    `origin/main` tip, that the landing has no merge commit, and that every landed author matches.
  - **The build is a fail-closed block.** It reads the same car records.
  - **A new KPI block compares the lender KPI vector** at the train head with the vector at the
    KPI car's reviewed head, or at `main`.
  - **The single pull-request merge check fails closed.** It opens with `set -euo pipefail`,
    prints an `OK` line, and confirms that the merge equals the freshly fetched `origin/main` tip with the stated parent
    count.
- The focused tests execute all five blocks, with faithful positive controls and hostile cases
  for incorrect car identity, metadata, history, preimages, counts, evaluator failure and scratch
  ownership. Specific deletion and old-mode mutants demonstrate that dropping the old diff
  columns loses protection. This is not an exhaustive mutation or full-suite claim.
- Both sides of each diff retain old/new modes and blob IDs, status and path bytes. Named
  environment inputs carry quoted paths and recorded message/author blob IDs. Failed KPI
  evaluation or malformed output cannot satisfy the comparator. Scratch worktrees are retained
  for owner inspection on success and failure; concealed index state and special files refuse
  the check. Object checks disable local replacement refs, grafts and the local commit-graph
  file, whose cached parents Git would otherwise trust. Specific destination-mode and
  issued-message tampering controls cover the later review findings. Standalone Bash conditionals
  explicitly exit on refusal, including on the governed Mac Bash where `set -e` alone did not stop
  them.
