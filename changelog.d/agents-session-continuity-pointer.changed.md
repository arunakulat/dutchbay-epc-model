- **`AGENTS.md` session-continuity pointer is now resolved, not hardcoded** — the gateway
  asserted that one named file *was* the newest handover record, which went stale as soon as
  a successor was written (ten later records accumulated behind it). It now states the two
  record kinds — a repository startup record carrying `## Bootstrap — run this first`, and a
  scope-specific successor that names the startup record still governing startup — and tells
  the reader to resolve the pointer from the newest record's own declaration. The named file
  survives only as a dated illustration, and `tests/lint/test_codex_project_guidance.py` now
  fails if the stale-prone wording returns or the illustration stops naming a record that
  actually carries a bootstrap section.
