# DutchBay August 2026 controlled audit successor

Status: **HOLD — not approved for Board or lender-due-diligence circulation.**

This directory is the repository-safe successor control pack for the August 2026 comprehensive audit. It publishes the corrected control surface without rewriting the immutable audit, which remains pinned to repository commit `7e99f34d75b9c3d44a5c5b260cedbe403d2f79e8`.

The authoritative live remediation queue and eventual release decision are tracked in [GitHub issue #1110](https://github.com/arunakulat/dutchbay-epc-model/issues/1110). Merging this pack publishes evidence and controls; it does not close #1110, resolve every finding, or lift HOLD.

## What is included

- controlled corrigendum v1.0.1;
- additive 2026-08-24 errata control for fixed GWTF rule-count instructions;
- 111-row findings register with audited-commit anchors, evidence links, dependencies and implementation state;
- 42-row claim-level source register;
- 72-pointer architecture register and active adjudication overlay;
- 34-row reproduction register plus concise machine-readable reproduction records;
- four independent refuter reports and the P3 register patch map;
- semantic-closure and structural-validation records;
- a SHA-256 publication manifest and fail-closed standard-library validator.

The latest controlled validation represented here reports:

- 111 findings, 299 audited-commit anchors, 367 evidence links and 187 typed dependencies;
- 42 source records and 74 externally retained source-manifest objects;
- 72 architecture pointers: 2 confirmed, 13 partially confirmed, 1 not a defect, 5 deferred and 51 not examined;
- 34 reproduction controls: 18 completed, 11 required-not-run and 5 unavailable;
- structural status `PASS`, release status `HOLD`.

## What is intentionally excluded

Third-party PDFs, publisher text conversions, rendered source-page images, temporary render trees and the 10,000-trial lossless Monte Carlo array are not republished in Git. The source register and `source-controls/SOURCE_ARCHIVE_MANIFEST.v2.sha256` retain their identities, URLs, access dates, hashes and limitations. Governed source copies remain in the separately retained evidence archive.

This exclusion is a publication and repository-size boundary, not a claim that the omitted evidence does not matter. The private/full-archive validator must still pass before any release decision.

Repository copies were normalized to LF line endings with trailing whitespace removed so they pass source-control hygiene gates. The publication manifest attests these normalized copies. Original/private-archive object identities remain separately preserved by the historical and source manifests. Absolute `/Users/aruna/...` paths inside historical records are frozen provenance pointers, not portable repository links; use the relative files in this directory and issue #1110 for the published control surface.

## Validation

From the repository root:

```bash
python docs/audit/2026-08-controlled-successor/scripts/validate_published_pack.py
```

The validator checks the publication manifest, JSON parsing, exact register populations, audited-commit identity, F5-01/F5-02 separation language, and HOLD controls. It does not replace independent semantic review.

## Release boundary

The HOLD can be lifted only through #1110 after all required-not-run, unavailable and not-examined items are explicitly resolved or governed; remaining code and evidence dolphins are complete or formally deferred; the final synthesis is regenerated from the controlled registers; rendered outputs pass calculation, citation, link, layout and accessibility review; and an independent reviewer records `RELEASED`.
