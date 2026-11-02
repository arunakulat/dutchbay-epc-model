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
  - **The landing check is anchored to `main`.** It now confirms that the landed SHA is on
    `origin/main`, that the landing has no merge commit, and that every landed author matches.
  - **The build is a fail-closed block.** It reads the same car records.
  - **A new KPI block compares the lender KPI vector** at the train head with the vector at the
    KPI car's reviewed head, or at `main`.
  - **The single pull-request merge check fails closed.** It opens with `set -euo pipefail`,
    prints an `OK` line, and confirms that the merge is on `origin/main` with the stated parent
    count.
- **Every comparison is load-bearing.** `tests/lint/test_train_policy.py` executes all five blocks,
  and gives every comparison a negative control that only it stops. Deleting any check line now
  fails a test.
