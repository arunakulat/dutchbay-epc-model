- **Steward skill honours merge-boundary conditions set by review.** The Merging section of
  `.claude/skills/steward/SKILL.md` no longer tells a merging session to squash with the
  pull-request title alone. A session now first collects every condition that review records and
  reconciled dispositions put on the merge itself. It reads these from the pull-request body,
  comments, review threads and cited records, and counts only the owner, the coordinator and the
  recruited reviewers. Conditions carried forward from earlier cycles count, and so do the
  requirements that no veto is outstanding and that each required disposition is bound to the
  exact head. The session honours these conditions over the default, and does not merge if one
  cannot be met or its record cannot be read.
  - The merge message quotes every `HOLD` that survives the merge. A `HOLD` that cites withheld or
    restricted material is stated abstractly instead, with the record's URL and SHA-256, because
    `main`'s history cannot be redacted.
  - Verification now runs against the returned merge SHA. It checks the tree, the first parent
    recorded before merging and, for a two-parent merge commit, the second parent, and it fails
    closed on any mismatch.
  - The cycle-3 assurance review of #1231 found (C3-A-10) that the previous default, followed
    literally, would have broken that pull request's F-09 condition. F-09 requires one of two
    routes: a squash message that names the A1 restore and references #1225 and #1232, or a merge
    commit.
