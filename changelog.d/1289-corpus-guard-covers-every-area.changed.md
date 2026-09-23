- **The corpus manifest guard now covers every corpus area, not one hard-coded path** —
  `tests/lint/test_nso_corpus_manifest_integrity.py`. Every path in it named
  `docs/source_materials/nso_bess_250mw_2026`, so the *next* corpus area would have landed
  covered by nothing at all: the exact condition that let manifest defects reach `main` six
  times, reproduced one directory across. A **corpus area** is now derived from the tree —
  any immediate child of `docs/source_materials` holding tracked files — and both directions
  of the gate, the parent pins and the classification completeness check run per area.
- **An area with no manifest is a finding, not a skip.** Discovery reads `git ls-files`, so an
  area with no `MANIFEST.sha256` has nothing to disagree with and every other check would pass
  it in silence. `test_every_corpus_area_has_a_parent_manifest` fails on it by name and says
  how to write one. What stays **declared** is the one thing that must not be inferred: whether
  a nested manifest's subject lives in this repository or outside it.
- **Each guard now ships the negative control that proves it fires**, per `VERIFY-01` clause 5.
  The checks are helpers returning what they found; each has a paired `test_negative_control_*`
  that builds a small valid corpus in a throwaway git repository, asserts the helper reports
  nothing, introduces exactly one defect, and asserts the same helper the live tests call
  reports it. Eight guards, eight controls, and a ninth test that fails if a guard is ever
  added without one — the count is enforced, not written down. Still about a second in
  `fastlane`.
- **The module keeps its `nso` filename deliberately.** The `fastlane` job invokes it by path,
  `AGENTS.md` cites it and two accepted `RECRUIT-01` review records bind to it; renaming would
  trade a real risk — the step silently not running — for a cosmetic gain.
