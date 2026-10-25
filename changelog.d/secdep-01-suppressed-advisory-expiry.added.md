- **`SECDEP-01` — a suppressed advisory declares what would lift it.** A new canonical GWTF
  rule row plus its fence, `tests/lint/test_pip_audit_allowlist.py`. The Makefile permits one
  literal `PIP_AUDIT_IGNORES :=` assignment: computed assignment names, includes, `eval`, Make
  expansion, later assignments and appends fail closed. Only exact `--ignore-vuln` spellings
  are accepted; pip-audit option abbreviations and every other token are rejected. The
  abbreviation grammar is read from pip-audit's own parser rather than from an option
  spelling, because argparse resolves any unambiguous prefix: `--ig` and `--ign` suppress
  exactly as `--ignore-v` does while containing no literal `ignore` text. Literal ignore
  options outside that assignment, including direct recipe flags, also fail. Live
  `make -n audit` and `make -n security` oracles read every emitted command rather than the
  ones that look like an audit, and require each command on its own to carry exactly the
  declared set or nothing — the mandatory target passes the allowlist to two audit passes, so
  pooling their tokens would make one correct declaration look like two suppressions. Every
  entry must declare a valid exact package pin, a valid named
  cap requirement, the release that would lift it and a defensible reason; a malformed
  declaration or one left behind after its entry now fails the build. `RELEASING.md` step 2
  re-checks each cap against the index before `make lock`, so a lifted cap changes dependency
  input before regeneration. The empty live allowlist is backed by a populated positive
  control, hostile effective-Make and pip-audit parser oracles, the observed security-only
  recipe suppression, and control-loss, displacement and reordering negatives. Scoped to
  suppressed advisories only — `dependabot.yml` ignores and `constraints.txt` pins remain
  tracked separately. Each abbreviation is proven effective, against pip-audit's parser and
  against a live recipe, before the fence is asked to reject it, and one declaration carried
  by both audit passes is a positive control, so neither guard passes only because the live
  allowlist is empty. Stated limit: the rule binds what is suppressed, not that the gate runs;
  whether the governed recipes really invoke the audits, and whether a failing audit really
  fails the target, is a separate property delivered on its own. No runtime, financial
  formula, scenario or KPI change.
