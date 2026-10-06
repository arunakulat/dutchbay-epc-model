- **Steward skill: merge conditions across multiple review chains, and a Grid Study prediction
  that matches CI.** This closes the residuals both review lanes accepted on #1295, and the
  Grid Study `base.sha` finding from #1231's review.
  - The Merging section now:
    - takes the union of every review chain's conditions and `HOLD`s, with one veto in any
      chain blocking;
    - attributes records by the session they name rather than by login;
    - says who may discharge a condition;
    - requires the merged head to equal the rebound head, and re-verifies each rebind at merge
      (module 3 §6);
    - extends the restricted-material check to the title and the whole message, and defaults
      to treating uncertain text as restricted;
    - excludes merge commits from the `R18` subject check.
  - The Grid Study prediction now diffs against the pull request's own `base.sha`, as the
    workflow does, instead of `origin/main`.
  - The cloud sandbox failure count in `CLAUDE.md` and the skill is now "up to five,
    timing-dependent".
