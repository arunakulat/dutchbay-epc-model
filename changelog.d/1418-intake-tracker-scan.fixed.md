- The PR intake check no longer fails every pull request once tracker #1353 passes 1,000
  comments (#1418). `scripts/ci/check_pr_intake.py` used to read the tracker's comments oldest
  page first and fail closed after ten 100-comment pages. It now reads newest page first and
  stops at the first passing verdict, which for a new PR is usually the newest page. Otherwise
  it reads every page that the tracker's own comment count names before failing. Every tracker
  test in the check asks whether some comment qualifies, so a verdict that passes on part of the
  comments also passes on all of them. A missing or invalid comment count, or a page that is not
  a list, still fails closed. The open-PR sweep keeps its ten-page bound (1,000 open PRs).
