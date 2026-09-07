- **Corpus manifest verifies again** — `docs/source_materials/nso_bess_250mw_2026/MANIFEST.sha256`
  recorded `registers/__pycache__/build_ltl_comparative_recommendation_2026-09-03.cpython-312.pyc`,
  added by #1226. `__pycache__/` is gitignored, so that file has never been in the tree and never
  can be, and `sha256sum -c` has been failing on `main` ever since with `138 OK, 1 FAILED`, exit 1.
  The single entry is removed; the manifest verifies at `138/138 OK`, exit 0. Deletion is the only
  correct remedy: the cached source is a register held deliberately in the private corpus because
  it carries price tables as source literals, a `.pyc` retains those literals in `co_consts`, and a
  `.pyc` hash is not reproducible from its source anyway, so the entry was permanently
  unsatisfiable. Nothing leaked — the file was gitignored and never committed to any branch.
- **What a manifest gate would actually need** — **no test covers either corpus manifest**, so
  defects here reach `main` in silence. A `sha256sum -c` gate alone is **not** sufficient, and an
  earlier draft of this entry wrongly said it was: `-c` checks *recorded → present and matching*
  and is structurally blind to *tracked → unrecorded*. Demonstrated on this repository's own
  history — at `782c958` the manifest omitted **11 tracked files** and `sha256sum -c` still
  returned `119/119 OK`, exit 0. A useful gate therefore needs **two** checks: `sha256sum -c` for
  recorded entries, and a set comparison of tracked corpus files against recorded paths. The
  existing audit-pack manifest tests are a working precedent for both.
