# Validation record — met-mast export 617725

**Date:** 22 September 2026

**Initial validation base:** `071df78b7879af930558e211cb8112d54f690b4a`

**Current delivery base:** `9a374862c02dc4557fcb2282f136cd2f86699371`; all 17
subject blobs remained identical across the verified base update before the corrective review pass

**Scope:** `docs/source_materials/met_mast_617725_2025/**`

This is the concise validation receipt. Transient command output and repeated runtime logs are
not retained.

| Control | Result | Evidence |
|---|---|---|
| Governed runtime | PASS | Python 3.12.13 from `/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv` |
| Raw-copy identity | PASS | Attachment and private RAG source at commit `52ae2fecb05f84497a68d00affbd95f4b0c18986`, now delivered to private `main` by PR #9 as `f1666885bbad5382977e664ccc1f41912b9c5f5e`, both SHA-256 `a19963698f6d7e1085f8c66bb1810ecc1e8937e7f004ab25b81539bfd2e2cd46` |
| Generator assertions | PASS | Hash, 33,456 × 57 shape, record bounds, 98 missing intervals, assessment bounds/counts, null-channel counts and speed-order invariants |
| Independent oracle | PASS | A separate standard-library parser reproduced shape, timestamp gaps, five mean-speed counts/means, 2,146-row 120 m outage, 71.50568267% SW+WSW occurrence and 1.016455696203 median 120/100 ratio |
| Deterministic regeneration | PASS | Two consecutive generator runs produced byte-identical JSON, CSV and PNG outputs |
| Static Python checks | PASS | Ruff, format and explicitly scoped mypy checks; source compiled with Python `compile()` without writing bytecode |
| JSON syntax | PASS | Both JSON artifacts parsed successfully with Python's JSON parser |
| Visual QA | PASS | QC overview inspected at original 2418 × 1807 resolution; titles, legends, axes, partial-month marks, outage threshold, wind rose, profile labels and limitation footer are readable and consistent with the numeric files |
| Public/private repository boundary | PASS | Private RAG commit `52ae2fecb05f84497a68d00affbd95f4b0c18986` contains only the raw source under this tranche; the EPC package contains every generated artifact and no `raw/` directory |
| EPC/GWTF governance harness | PASS WITH INHERITED HOST LIMITATION | Governed Python 3.12.13 environment and 74-rule canonical bootstrap passed. Focused met-mast, global corpus-manifest and canonical-source tests: 48 passed. Remaining project-guidance tests: 14 passed; the one excluded macOS-impossible surrogate-filename fixture fails before exercising the resolver and reproduces unchanged on clean base `071df78` |
| Manifest integrity | PASS | `shasum -a 256 -c MANIFEST.sha256`; the focused EPC guard proves the manifest inventory equals every public package file except the manifest itself and independently validates every recorded digest |
| Whitespace check | PASS | Staged EPC candidate passes `git diff --cached --check` |

The independent oracle did not import or call the committed analysis generator. No derived
value was written into a model input, financial scenario, AEP result or lender output.
