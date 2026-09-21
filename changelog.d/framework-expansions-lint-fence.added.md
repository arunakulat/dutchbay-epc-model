- Add `tests/lint/test_framework_expansions_match_csv.py`, a guard binding every tracked file's
  spelling of CASPER, CESSPIT and CCCDIR to `go_with_the_flow_rules_v3_0_clean.csv`. Nothing
  guarded this direction before: `tests/lint/test_gwtf_canonical_source.py` checks the ruleset's
  own cells cell by cell, but a derived file could define the three acronyms however it liked and
  stay green. That is how the sprint workflow checklist filed two of them as sub-items of the
  third from December 2025 until #1283, and how five live-guidance files each carried a different
  invented triple until #1286.
- Two fences, because neither alone suffices. A regression guard over the exact strings #1283 and
  #1286 removed catches a copy-paste return. A general guard reads any phrase that follows one of
  the acronyms and whose word-initials SPELL it as a definition, and fails when the ruleset does
  not contain it -- which catches expansions nobody has seen yet. Keying on the initials is what
  makes the general fence safe to run repository-wide: the hundreds of inline compliance notes
  (`CASPER-guarded`, `CESSPIT - fail loud`) are usages, not definitions, and none of them spells
  the acronym out.
- The guard found two files the manual sweep behind #1283 and #1286 had missed, each carrying a
  further invented triple: `docs/INTERNAL_HARDENING_AUDIT_20251219.md` and
  `analytics/sensitivity/REORGANIZATION.md`. Both are dated records, so both join the thirteen
  audits, retrospectives and sprint completion reports the guard exempts by explicit path rather
  than by glob -- correcting a dated receipt would falsify it, and a new file cannot drift into
  the exemption without someone adding it. `changelog.d/` and `CHANGELOG.md` are exempt for a
  different reason: an entry recording that an expansion was removed has to name it.
- The regression guard matches an acronym and a retired expansion on the same LINE, not anywhere
  in the same file. Every occurrence #1283 and #1286 removed had them on one line, while a
  document that REPORTS the defect tabulates the filename in one column and the wrong wording in
  another. Checked against the compliance review on open PR #1285: five pairs match somewhere in
  that document and none on a shared line, so whole-file matching would have failed the write-up
  that corrects the problem. Both directions ship with controls that observe them firing and not
  firing. Tests only -- no production code, configuration or KPI is touched.
