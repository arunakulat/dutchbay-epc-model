- **`AGENTS.md` session-continuity pointer is now resolved, not hardcoded** — the gateway
  asserted that one named file *was* the newest handover record, which went stale as soon as
  a successor was written (eleven later records accumulated behind it). It now states the two
  record kinds — a repository startup record carrying the `## Bootstrap — run this first`
  checklist, and a scope-specific successor that names the record still governing startup —
  gives a committer-date ordering command, and tells the reader to resolve the pointer from
  the newest record's own declaration. The named file survives only as a dated illustration.
  `tests/lint/test_codex_project_guidance.py` ratchets against the wording this replaced: it
  fails if a `SESSION_HANDOVER_*` or `H<n>_*` record name reappears above the illustration
  marker, or if the illustration stops naming a record that actually carries a bootstrap
  section. It is a positional regression ratchet over prose — not a proof that no hardcoded
  pointer can return, and not a check on whether the illustration's claim is still true.
