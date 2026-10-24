- **`SECDEP-01` — a suppressed advisory declares what would lift it.** A new canonical GWTF
  rule row plus its fence, `tests/lint/test_pip_audit_allowlist.py`: every `--ignore-vuln`
  entry in the `Makefile`'s `PIP_AUDIT_IGNORES` must declare the pinned package, the cap that
  forces it and the release that would lift it, and a declaration left behind after its entry
  goes now fails the build. `RELEASING.md` step 2 re-checks each cap against the index before
  the lock is regenerated. The allowlist is empty today, so the fence ships green and bites on
  the next entry; it is exercised against crafted allowlists with a positive control and one
  negative control per field. Scoped to suppressed advisories only — `dependabot.yml` ignore
  entries and `constraints.txt` pins share the failure mode and are tracked separately. No
  runtime, financial formula, scenario or KPI change.
