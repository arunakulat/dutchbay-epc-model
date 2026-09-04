- **Corpus manifest verifies again** — `docs/source_materials/nso_bess_250mw_2026/MANIFEST.sha256`
  recorded `registers/__pycache__/build_ltl_comparative_recommendation_2026-09-03.cpython-312.pyc`,
  added by #1226. `__pycache__/` is gitignored, so that file has never been in the tree and never
  can be, and `sha256sum -c` has been failing on `main` ever since with `138 OK, 1 FAILED`, exit 1.
  The single entry is removed; the manifest verifies at `138/138 OK`, exit 0. This is the fourth
  manifest defect in this programme to reach `main` unnoticed, because **no test covers either
  corpus manifest** — a stale, incomplete or impossible entry passes CI in silence. A
  `sha256sum -c` gate over both manifests would have caught all four, and is worth adding.
