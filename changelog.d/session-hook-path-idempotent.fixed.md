- **The session-start hook no longer grows `PATH` by one entry per resume** — the hook
  appends to `CLAUDE_ENV_FILE`, which every shell re-sources, so its unconditional
  `export PATH="$VENV/bin:$PATH"` accumulated a duplicate on each session start. A live
  session was observed carrying **18 copies** of `.venv/bin` (32 entries, 15 unique).
  First match wins, so the duplicates were harmless — but unbounded, and the hook is
  documented in `CHANGELOG.md` as "idempotent via a manifest-hash stamp", which guards the
  *install* and never guarded this export. The emitted line is now a `case` guard that
  prepends only when absent. Covered by two tests that source the real emitted line in a
  shell: one asserts five sourcings yield exactly one entry, the other is the negative
  control — it asserts the guard still **prepends when absent** (a guard collapsed to a
  no-op would look equally idempotent while silently breaking the venv resolution the
  export exists to provide) and that the unguarded form it replaced genuinely accumulates.
