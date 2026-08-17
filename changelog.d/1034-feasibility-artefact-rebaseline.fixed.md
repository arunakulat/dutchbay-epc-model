- **F5-01 follow-through: `feasibility_reproduce/` re-baselined to the COD-aligned canon
  (#1034)** — the code correction landed in #1038, but the reproduce kit still pinned the
  superseded canon at full precision (`0.014551597740253388` / `−0.05841298678542661` /
  `1.285740985294611`, NPV −$79.27M), so any lender-facing document pulled from the kit
  reported the project ~1.6pp better on equity IRR and ~$12.5M better on NPV than the truth.
  Regenerated live at `v15.3.1`: the canon run, the 8-scenario suite (equity IRR
  −9.44%…+4.90%, every scenario NPV-negative), the 2,500-trial Monte-Carlo (equity IRR
  P10/P50/P90 −13.0/−9.1/−5.0%, NPV negative in 100% of trials, 0 toy-fallback
  substitutions), both optimizer modes (36 debt-mix candidates all negative; best −6.21%
  vs the committed −7.85%), and the study Markdown + rendered PDF. The two cache scenario
  YAMLs gain the explicit `Financing_Terms.construction_periods: 2` and the re-baselined
  `expected_results`. Wind/GIS/AEP/grid results are inputs to the finance layer, unaffected
  by an FX-timing correction, and are carried forward unchanged with that scope recorded in
  `MANIFEST.md`.
- **`.gitignore`: anchor the setuptools build-output ignores to the repo root** — the stock
  `lib/` and `lib64/` rules were unanchored, so they matched at ANY depth and silently
  swallowed `feasibility_reproduce/lib/`. That is why `run_all.sh` shipped calling helper
  scripts (`build_study_pdf.py`, `build_md_pdf.py`, `mc_run.py`, …) that were never
  committed — the "offline reproduce" kit could not actually run from a clean clone. Now
  `/lib/` and `/lib64/`, and the two PDF builders the study deliverable needs are committed.
- **`run_all.sh` / `HOWTO.md`: `mode=capex_contingency` requires `base_capex_usd`** — the
  documented command raises `ValueError` without it (`capex.usd_total` less the contingency
  line = `157206000`). `run_all.sh` also swallowed the failure via `>/dev/null 2>&1 &&`, so a
  broken step reported as a silent no-op; it now surfaces `ERR`.
