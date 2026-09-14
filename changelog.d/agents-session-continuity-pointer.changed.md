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
  backdated descendants, ambiguous latest timestamps, repeated add events, and any matching
  path difference across HEAD, index and worktree stop resolution, including ignored files.
