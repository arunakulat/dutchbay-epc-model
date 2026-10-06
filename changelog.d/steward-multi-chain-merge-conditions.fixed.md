- **Steward skill: merge conditions across multiple review chains, and a Grid Study prediction
  that matches CI after a push.** This answers the residuals both review lanes accepted on
  #1295, and the skill side of the Grid Study `base.sha` finding from #1231's review (#1323).
  #1322's review records say which of those residuals remain partly open.
  - The Merging section now:
    - takes the union of every review chain's conditions and `HOLD`s, with one veto in any
      chain blocking. `HOLD`s and carried gates come from each chain's latest reconciliation
      and from any later record in that chain;
    - attributes a record to the session that posted it rather than to a login or a role. A
      reviewer's record stays the reviewer's when a coordinator posts it. Attribution only
      limits what can clear a condition: a veto, `HOLD` or condition in a record nobody can
      attribute still blocks;
    - says who may withdraw a condition (the party whose finding it is, or the owner) and who
      may discharge it (that party, or a reviewer other than whoever made the fix). Nobody
      discharges a condition on their own fix;
    - says how an owner decision counts: on record, relayed first-hand, and naming each
      condition or lane it waives. "Merge on CI green" waives nothing;
    - defines a required disposition as one from each reviewer role `RECRUIT-01` module 1
      requires for the risk class. **This changes merge practice.** A pull request whose
      required review lane has not run now gets a stated blocker instead of a merge, unless the
      owner has waived the lane on record. Handovers, code and dependency bumps are `R2` under
      module 1, and some have merged with that review declared `not run`;
    - requires the merged head to equal the rebound head, names the module 3 proofs each kind of
      later push needs, and re-verifies at merge every disposition the merge relies on: the
      comment unedited, its transcribed record matching its digest and its durable record, and
      its identity named. **This also changes practice:** a disposition that states no content
      digest, or whose durable record cannot be read, no longer supports a merge until it is
      reissued;
    - extends the restricted-material check to the title and the whole message, defaults to
      treating uncertain text as restricted, and keeps a review condition from overriding it;
    - excludes merge commits from the `R18` subject check.
  - The Grid Study prediction now diffs against the pull request's own `base.sha`, as the
    workflow does, and refuses to run unless the checkout is at the pull request's head. Before
    a push that merges `main` in, an older base usually over-predicts but can under-predict. The
    `Classify changed paths` job remains the authority.
  - The cloud sandbox failure count in `CLAUDE.md` is now "up to five, timing-dependent", and
    the skill cites it there instead of repeating it.
