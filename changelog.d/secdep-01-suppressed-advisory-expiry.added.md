- **`SECDEP-01` — a suppressed advisory declares what would lift it.** A new canonical GWTF
  rule row plus its fence, `tests/lint/test_pip_audit_allowlist.py`. The Makefile permits one
  literal `PIP_AUDIT_IGNORES :=` assignment: computed assignment names, includes, `eval`, Make
  expansion, later assignments and appends fail closed. Only exact `--ignore-vuln` spellings
  are accepted; pip-audit option abbreviations and every other token are rejected. Literal ignore
  options outside that assignment, including direct recipe flags, also fail. The complete
  `audit` and `security` command sequences are exact; `.ONESHELL`, shell overrides, preambles,
  aliases, functions, wrappers and extra commands fail rather than being filtered out, and
  controlled runtime sentinels prove the expected binaries receive the exact arguments. Every
  entry must declare a valid exact package pin, a valid named cap requirement, the release that
  would lift it and a defensible reason; a malformed declaration or one left behind after its
  entry now fails the build. `RELEASING.md` step 2 re-checks each cap against the index before
  `make lock`, so a lifted cap changes dependency input before regeneration. The empty live
  allowlist is backed by a populated positive control, hostile effective-Make and pip-audit
  parser oracles, live `make -n security` and `make -n audit` comparisons, the observed
  security-only recipe suppression and `.ONESHELL` alias-interception controls, and control-loss,
  displacement and reordering negatives. Scoped to suppressed advisories only —
  `dependabot.yml` ignores and `constraints.txt` pins remain tracked separately. No runtime,
  financial formula, scenario or KPI change.
