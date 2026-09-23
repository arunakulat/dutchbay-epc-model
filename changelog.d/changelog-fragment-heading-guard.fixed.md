- Stop changelog fragments smuggling markdown headings into `CHANGELOG.md`, and reject them at
  the boundary rather than repairing them. `fold` splices every non-blank fragment line into
  `[Unreleased]` verbatim, so a heading in a fragment became a heading in the compiled changelog.
  Eight pending fragments carried eleven of them: four `# Added`, one `### Added`, and three pairs
  of `## Fixed` plus `## Financial impact` in the `python312-*` fragments. All eleven are removed;
  the `Financial impact` prose is kept as a bullet, and the category headings are dropped outright
  because the filename already carries the category.
- The damage was structural, not cosmetic. Compiling `main` put four `# Added` headings at the
  same level as the document's own `# Changelog` title, and the first `## Fixed` ended the
  `[Unreleased]` window at line 1258 as far as `_section_end` was concerned — so the ~110 lines of
  fragment content after it, including three more `## Fixed` and three `## Financial impact`
  headings, fell outside the block that every later compile inserts into. It also produced a
  duplicate `### Added` subsection. After this change the window runs to the real `## v15.4.0`
  boundary and holds exactly three subsections in Keep-a-Changelog order, with no duplicates.
- `validate_body` in `scripts/compile_changelog.py` now refuses any fragment whose body contains a
  heading, at every depth from `#` to `######`, and `_collect` calls it, so a fold fails loudly
  instead of corrupting the file. `changelog.d/README.md` states the rule it already implied.
- Nothing else about fragment bodies is constrained. Flush-left prose paragraphs and two-space
  continuation lines stay legal, because 841 continuation lines and 350 prose lines across the
  pending corpus already use them; only headings are rejected.
- Each control was observed to fail before being relied on. Reinstating a single `## Fixed` reds
  `tests/lint/test_compile_changelog.py` and makes `compile_changelog.py --dry-run` refuse to run;
  the negative control covers all six heading depths; a wiring control proves `_collect` itself
  raises rather than only the validator in isolation; and the repo-wide scan asserts it saw a
  non-zero number of fragments, so an empty or mis-globbed `changelog.d` cannot pass vacuously.
- Financial impact: none. This changes developer changelog tooling and its fragment prose only;
  financial logic, scenario inputs, and canonical KPI calculations are untouched.
