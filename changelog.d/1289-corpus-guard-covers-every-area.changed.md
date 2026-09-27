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
  reports it. `test_every_guard_has_a_negative_control` fails if a guard is ever added without
  one, if a control no guard claims is left behind, or if the mapping names something that no
  longer exists. No count is stated here on purpose: the first draft of this entry claimed six
  controls for eight guards and three guards had none, so `GUARD_CONTROLS` is the mapping and
  the test is the count. A guard whose two halves fail independently carries one control per
  half.
- **The declaration tables are now forced complete, not trusted.** Nested-manifest
  classification was already forced; the single-source handling note and the restricted-clause
  check were keyed by hand-maintained tables that nothing checked, so a new corpus area's
  manifests were gated in both directions while its handling note was gated by nothing, silently.
  Both tables are now checked against the tree: a `HANDLING NOTE` or a verbatim quotation block
  that no entry claims fails by name. Two independent reviewers found this gap; one built the
  next corpus area with its anchor unregistered, stripped every citation and added a sixth
  restated copy of the handling statement, and the suite stayed green.
- **A restricted clause could reach a public CI log through a failing assertion.** `addopts`
  carries `--showlocals`, which prints every frame local on a failing stack into GitHub Actions,
  and this repository's logs are public. The module reasoned about that for the span search and
  stopped one function short: a reviewer forced the assertion and measured three of four clause
  lines printed, against a docstring claiming the text never left. The parse now returns its
  defects from a frame that has been popped before anything raises, failures name line numbers
  and never quote the line, and the clause guards drop their own frames. Verified with a
  synthetic sentinel: zero occurrences in a forced failure.
- **The module keeps its `nso` filename deliberately.** Four things name it: the `fastlane` job
  invokes it by literal path, `AGENTS.md` cites it by path, the offers manifest cites it by
  filename — so a rename would also mean editing a nested manifest and refreshing the parent pin
  in the same commit — and two `RECRUIT-01` review records discuss it by path. Those two records
  are **both REJECT** and both bind only to the superseded `3e4b79f`; they are bindings to break,
  not endorsement. An earlier draft of this entry called them "accepted", which was false.
- **A second corpus area would have switched off the first area's clause guard, silently.**
  The restricted-clause registry was keyed by the quotation heading — a section number and a
  clause name that every offers manifest carries, which is boilerplate and not an identifier.
  A second area quoting its own clause 6 under the same heading evicted the first entry, and
  the tree scan meant to catch an unregistered quotation was keyed the same way and collapsed
  with it, so the two cancelled out and alphabetical order decided which area kept its guard.
  Both are now keyed by `(heading, manifest)`, the pair that is actually unique, and the check
  reports every occurrence rather than one per identifier. The guard this would have dropped is
  the one that already caught a confidentiality leak into a public Actions log.
- **Discovery could be defeated by not being a directory.** An area is the first path segment
  below `docs/source_materials`, so a tracked entry with no segment beneath it belonged to no
  area and was checked, and reported, by nothing. Three shapes land that way and all three are
  plausible in an evidence corpus: a loose file at the root, an area held as a **symlink**, and
  an area vendored as a **submodule** — the last two being the obvious shapes for material held
  elsewhere, which is what this corpus is for. `_loose_entries` now names all three and
  distinguishes them by index mode.
- **The clause guard's search half had never been observed to fire.** Its control covered
  reading the spans out of the manifest and said nothing about whether the search then finds a
  copy; narrowing its pathspec to the manifest alone left it unable to detect a duplicate
  anywhere while every test in the module stayed green. The search is now a separate helper
  with its own control that plants a span in two tracked files and requires both to come back.
  Its `git grep` also passes `-z`, so a path with a space or a non-ASCII character is returned
  unquoted instead of C-escaped, which would have made the home-path comparison fail to match.
