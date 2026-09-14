- **`AGENTS.md` session-continuity pointer is now resolved, not hardcoded** — the gateway
  asserted that one named file *was* the newest handover record, which went stale as soon as
  a successor was written (eleven later records accumulated behind it). It now states the two
  record kinds — a repository startup record carrying the `## Bootstrap — run this first`
  checklist, and a scope-specific successor that names the record still governing startup —
  uses one executable resolver ordered by each record's introduction commit, and tells the
  reader to follow the newest record's own declaration. The resolver fails loudly for staged
  or untracked successors. The named files survive within one bounded, dated illustration.
  Structural tests reject concrete record names outside that paragraph, require every record
  named inside it to exist, and require the stated startup target to carry the bootstrap
  heading with a nonempty section body. Hostile temporary-repository tests prove that
  correcting an older record does not outrank a newer successor and that shallow history,
  backdated descendants, incomparable histories, ambiguous latest timestamps, repeated
  family entries, and any matching path difference across HEAD, index and worktree stop
  resolution, including ignored files. File lineage is dated when it first enters a
  supported handover family, while later renames within that family retain the entry date.
  Git path inventories, followed-commit metadata and per-commit changes use NUL framing;
  control-bearing near-family names fail before history interpretation. Independently
  bounded prose candidates ensure a rejected glob cannot mask a later concrete reference.
  The display-safe suffix grammar is explicit, and the model product owner must optimize
  and review the resolver before runtime exceeds 60 seconds or the corpus reaches 100 records.
