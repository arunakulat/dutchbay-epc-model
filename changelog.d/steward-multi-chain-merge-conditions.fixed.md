- **Steward skill: merge conditions across multiple review chains, and a Grid Study prediction
  that matches CI after a push.** This answers the residuals both review lanes accepted on
  #1295, and the skill side of the Grid Study `base.sha` finding from #1231's review (#1323).
  #1322's review records say which of those residuals remain partly open.
  - The Merging section now:
    - takes the union of every review chain's conditions and `HOLD`s, with one veto in any
      chain blocking. `HOLD`s and carried gates come from each chain's latest reconciliation
      and from any later record in that chain;
    - attributes a record to the session that posted it rather than to a login or a role.
      Attribution only limits what can clear a condition: a veto, `HOLD` or condition in a
      record nobody can attribute still blocks;
    - says who may discharge a condition, that nobody discharges one on their own fix, and how
      an owner decision counts;
    - defines a required disposition as one from each reviewer role `RECRUIT-01` module 1
      requires for the risk class. **This changes merge practice.** A pull request whose
      required review lane has not run now gets a stated blocker instead of a merge, unless the
      owner has waived the lane on record. Handovers and code are `R2` under module 1, and some
      have merged with that review declared `not run`;
    - requires the merged head to equal the rebound head, names the module 3 proofs each kind of
      later push needs, and re-verifies at merge every disposition the merge relies on: the
      comment unedited, its transcribed record matching its digest, and its identity named;
    - extends the restricted-material check to the title and the whole message, defaults to
      treating uncertain text as restricted, and keeps a review condition from overriding it;
    - excludes merge commits from the `R18` subject check.
  - The Grid Study prediction now diffs against the pull request's own `base.sha`, as the
    workflow does, and is meant to run after a push. Before a push that merges `main` in, it can
    only over-predict. The `Classify changed paths` job remains the authority.
  - The cloud sandbox failure count in `CLAUDE.md` is now "up to five, timing-dependent", and
    the skill cites it there instead of repeating it.
