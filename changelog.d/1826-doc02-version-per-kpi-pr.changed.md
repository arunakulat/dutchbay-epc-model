- **`DOC-02` states the owner's 2026-11-21 ruling on `VERSION` (#1826, option B).** A change
  that can affect IRR, DSCR, NPV or covenant logic adds its `changelog.d/` fragment and bumps
  `VERSION` in the same PR; no PR edits `CHANGELOG.md`, which release cuts compile from the
  fragments. The CSV row is amended, and `CLAUDE.md`, `AGENTS.md`, `Rules to follow.md` and
  `RELEASING.md` now restate it. `tests/lint/test_doc02_reconciliation.py` pins all four to the
  row, with a negative control for each way they can drift. No model code; no KPI changes.
