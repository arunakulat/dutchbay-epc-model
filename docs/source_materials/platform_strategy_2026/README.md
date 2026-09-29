# Platform strategy 2026 — owner-supplied planning inputs

This corpus area records planning inputs that the project owner supplies for evaluation. Its first
object is a proposed five-phase, twenty-week plan to rebuild this repository as a
multi-technology, multi-jurisdiction web platform, received on 26 September 2026.

The earlier areas under `docs/source_materials/` hold project evidence: OEM documentation,
tender material and commercial offers for named projects. This area holds strategy proposals.
A proposal is a source to be evaluated, not evidence of any fact about the model, a project or
the law.

**How this object is handled is stated once** — what it is, how faithfully it was recorded, why
it is published in full, and what status it has — in the header of
[`MANIFEST.sha256`](MANIFEST.sha256), under the identifier `PLATFORM-PLAN-HANDLING-2026-09-26`.
Read it there. It is deliberately not repeated here; the corpus guard fails if this file stops
citing it.

## Contents

| File | Holds |
|---|---|
| [`PLATFORM_DEVELOPMENT_PLAN_2026-09-26.txt`](PLATFORM_DEVELOPMENT_PLAN_2026-09-26.txt) | The plan text, as received (81 lines, 6,378 bytes, UTF-8) |
| `MANIFEST.sha256` | The handling note, and the SHA-256 of every file in this area |

The plan file is plain text rather than Markdown on purpose. It is a source object preserved
verbatim under `DATA-01`, including its errors, so it must not be edited to satisfy the
documentation style rules (`DOC-03`) that govern this repository's own prose.

## Status: recorded, not accepted

Nothing in the plan has been adopted, scheduled or authorized. The evaluation is in
[`docs/SPRINT_21_BOOTSTRAP/`](../../SPRINT_21_BOOTSTRAP/README.md): it maps every line item to
the code that already exists, records the technical corrections the plan needs, relates its
finance items to the open findings of audit programme #1110, and sets out the decisions the
owner must take before any of it becomes sprint scope.

## Integrity

`MANIFEST.sha256` records every file in this area. Verify with `sha256sum -c MANIFEST.sha256`
from this directory. `tests/lint/test_nso_corpus_manifest_integrity.py` runs that check in both
directions on every pull request, in the `fastlane` job, and fails if a registered citation of
the handling note goes stale.
