- **The handover resolver no longer fails closed on a Git older than 2.45.0.** The batched
  lineage timestamp guard added in #1358 accepted a zero UTC offset only when Git spelled it
  `Z`. Git writes `iso-strict` that way from 2.45.0 onwards and writes `+00:00` in every older
  release (upstream `69e2bee1`, released 2024-04-29), so on an older host the resolver rejected
  Git's own correct output and reported `malformed batched lineage ISO timestamp` before
  printing any record. Two tracked handover records are introduced by commits carrying `+00:00`,
  both squashed through the GitHub merge button, which stamps UTC; one such record was enough to
  make `AGENTS.md` "Session continuity" unavailable on that host.
  - `scripts/list_session_handover_records.py` now accepts a zero offset written `Z` **or**
    `+00:00`. This removes no control: the same function already requires the parsed instant to
    equal the `%ct` epoch, so a spelling that disagreed with the instant still fails closed, and
    ordering cannot change. `-00:00` stays rejected, because RFC 3339 reads it as an instant
    whose local offset is unknown and Git never emits it for UTC.
  - The resolver suite pinned the old assumption rather than testing it: its injected-header
    cases asserted `+00:00` was malformed, while its synthetic repositories committed every
    fixture at `+00:00` and asserted success — compatible only on Git 2.45.0 or newer. Both
    spellings are now pinned through injected headers, so the behaviour holds whichever Git is
    installed, and the `-00:00` rejection is kept with its reason recorded.
  - No repository control declares a Git version. CI runs `ubuntu-latest`, whose Git moves, and
    the guard's version dependency was never stated; `docs/ISSUE_1342_IMPLEMENTATION_RECORD.md`
    describes the control as admitting "the exact Git `%cI` form", which is what it now does.
