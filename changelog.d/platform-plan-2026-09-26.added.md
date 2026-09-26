- **A platform development plan supplied by the project owner is now recorded** —
  `docs/source_materials/platform_strategy_2026/`, a new corpus area for owner-supplied strategy
  proposals. The plan proposes rebuilding this repository over five phases and twenty weeks as a
  multi-technology, multi-jurisdiction web platform. It is held in full, verbatim as received,
  as plain text so that it is never edited to fit this repository's style rules. Handling is
  stated once, at `PLATFORM-PLAN-HANDLING-2026-09-26` in the area manifest, and cited by the area
  README and the Sprint 21 bootstrap README.
- **The handling anchor is registered in the corpus guard**, the first to live in an area's
  parent manifest rather than a nested package manifest. Before registration
  `test_every_handling_note_in_the_tree_is_registered` failed on the new area; with a registered
  citation removed, `test_handling_notes_are_stated_once` failed; both pass once declared.
- **The plan is evaluated, not adopted** — `docs/SPRINT_21_BOOTSTRAP/`. Of 38 line items, 14 are
  already implemented and 11 partly. Nine technical corrections are recorded, the most
  consequential being that the plan's debt-capacity formula sizes at 1.00x coverage and oversizes
  debt by the target DSCR factor, checked against `finance/debt_v14.py`. Eleven items touch
  audit findings that block Board and lender release under #1110. The recommendation is to take
  the plan's goals into Sprint 21 as finding-mapped dolphins alongside Sprint 20 Lane A, with
  seven decisions left to the owner.
- **A scoped successor handover record**, `docs/SESSION_HANDOVER_2026-09-26_PLATFORM_PLAN.md`,
  carries the open items. It leaves H08 and the startup pointer unchanged.
- No finance code, configuration, scenario, KPI or `VERSION` changes. Not independently reviewed:
  the `RECRUIT-01` domain and assurance review is pending.
