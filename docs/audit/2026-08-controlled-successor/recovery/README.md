# P01 portable checkpoint recovery

This directory publishes the hash-only, repository-safe control surface for Issue
#1110 gate `P01`. It does not publish the checkpoint archive, Git bundle, immutable
received audit, third-party source files, rendered source-page images, or unrelated
workbook material retained by the historical checkpoint.

## Current disposition

- Structural implementation: candidate for protected delivery.
- Independent evidence-integrity review: pending.
- P01 programme gate: pending.
- Board/lender circulation: HOLD.
- Issue #1110: OPEN.

The historical convenience-expanded `remediation_workspace/` is intentionally not
modified. It is incomplete: 23 of its outer-manifest objects are absent. The retained tar
archive is the authoritative remediation payload and remains byte-bound at SHA-256
`13d5b7aca2f064b8f8b16224e366ce038e39a43cfeff85d5c6279916471c7a91`.

## Controlled recovery recipe

Use a clean DutchBay worktree and the governed Python 3.12 environment. The four private
or machine-local roots travel only through environment variables, so Hydra does not
persist them and the one-line public receipt contains no absolute paths.

```bash
export DUTCHBAY_VENV=/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv
export PYTHONPATH=/path/to/clean/dutchbay-epc-model
export DUTCHBAY_AUDIT_CHECKPOINT_ROOT=/path/to/DutchBay_Save_Checkpoint_2026-08-12_103431+0530
export DUTCHBAY_AUDIT_CORPUS_ROOT=/path/to/DutchBay_Comprehensive_Audit_2026-08
export DUTCHBAY_AUDIT_REPOSITORY_ROOT=/path/to/clean/dutchbay-epc-model
export DUTCHBAY_AUDIT_RECOVERY_OUTPUT_ROOT=/new/empty-parent/recovered-checkpoint
"$DUTCHBAY_VENV/bin/python" scripts/validate_audit_recovery.py
```

The output root must not already exist and must not overlap any input. The implementation
uses an internal staging directory and publishes the recovered root atomically. It writes
only the governed recovery payload, never a runtime log.

## What is verified

1. Exact descriptor schema and publication boundaries, with duplicate JSON keys refused.
2. Absolute, non-symlinked, non-overlapping input/output roots.
3. Outer payload manifest: 68 entries and exact SHA-256.
4. Remediation tar: 64 governed regular files plus 74 one-for-one macOS AppleDouble
   metadata companions (138 regular members total), all bound by the archive hash. The
   metadata companions are format-checked and never materialized; the archive still
   permits no traversal, duplicate, case/Unicode collision, link, special member, or
   unpaired payload/metadata name.
5. Recovered inner manifest: 63 entries and exact set/hash verification.
6. Recovered controlled-source manifest: 23 entries and exact set/hash verification;
   the one additional `IEC_CATALOGUE_QUERY_LOG.json` source file is explicitly excluded
   from that nested manifest and remains hash-bound by the exact 63-entry parent
   manifest.
7. Retained audit ingress manifest: 73 received entries and a 74-file ingress-scope
   digest including the manifest. The directory's one later
   `06_CODEX_INGRESS_EVALUATION.md` is separately classified and hash-attested as a
   derived evaluation, not received ingress evidence; the exact retained directory has
   75 files and its own root digest.
8. Git bundle hash, completeness verification, and exact four-ref mapping.
9. Repository origin identity, presence of audited commit `7e99f34`, clean worktree, and
   the current controlled-successor validator reporting `PASS` while retaining `HOLD`,
   23 pending programme gates, and 56 pending architecture examinations.
10. Materialized successor: 69 files and root digest
    `08e406ae8c5cc67f6f3780349592de9fad8a9d31febdfa8be31c1e0fa9f60208`.

The required P01 negative control removes one outer-manifest payload and must fail with
`MANIFEST_MISSING` and the exact missing relative path. Additional controls cover altered,
unexpected, duplicate, unsafe, colliding, symlinked, wrong-repository, wrong-commit,
wrong-bundle, overlapping-root, and nonempty-output cases.

## Trust boundary

Hash consistency proves byte identity against the descriptor; it does not authenticate
third-party authorship or prove any claim true. The protected Git merge is the external
attestation for the descriptor itself. A successful receipt is named `structural_pass`,
but keeps `gate_status=pending_independent_review` and `release_status=HOLD` until a
reviewer independent of the implementation records a hash-bound decision.
