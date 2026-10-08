# Issue #1339 implementation record

## Scope

The mandatory dependency audit began rejecting the reproducibility lock on 7 October 2026 because
`hydra-core==1.3.5` was newly associated with CVE-2026-106441 and CVE-2026-106442. Both advisories
identify 1.3.6 as the first stable fixed version. This dolphin changes only the abstract Hydra
security floor, exact lock pin, a regression guard, and its changelog/evidence records.

No advisory is allowlisted. No other dependency is refreshed. No application, scenario, model,
finance, report, configuration value or KPI path changes.

## Governance and authority

- Issue and lease: #1339 / `L-1339-SEC-001`.
- Worktree: `/workspace/dutchbay-hydra-security`.
- Branch: `fix/hydra-cves-1339`.
- Base: `3b352034f74254af8b8baeb4d8cf9181ad252cb2`.
- Risk: `R2_DEPENDENCY_SECURITY`; an independent dependency/security assurance review is required
  after freeze.

The audit establishes only that the governed lock has no advisory known to the audit database at
execution time. It is not a general supply-chain, release, lender, Board or bankability assurance.
Issue #1110 remains open and unaffected.

## Verification receipt

To be completed on the frozen candidate after all checks pass.
