# Issue #1339 implementation record

## Scope

The mandatory dependency audit began rejecting the reproducibility lock on 7 October 2026 because
`hydra-core==1.3.5` was newly associated with CVE-2026-106441 and CVE-2026-106442. The first
candidate used their stated stable fix, 1.3.6; the exact audit then identified CVE-2026-106439 in
that release. Hydra 1.3.7 is the smallest stable release reported to fix all three advisories.
Across all three advisories, the later 1.4.0.dev0 through 1.4.0.dev9 prereleases are affected too,
so the abstract dependency excludes their union explicitly rather than relying on pip's default
stable-release preference. This dolphin changes only the abstract Hydra security floor, exact lock
pin, a regression guard, and its changelog/evidence records.

No advisory is allowlisted. No other dependency is refreshed. No application, scenario, model,
finance, report, configuration value or KPI path changes.

## Governance and authority

- Issue and leases: #1339 / `L-1339-SEC-001` (initial implementation) / `L-1339-SEC-002`
  (prerelease exclusion repair).
- Worktree: `/workspace/dutchbay-hydra-security`.
- Branch: `fix/hydra-cves-1339`.
- Original lease base: `3b352034f74254af8b8baeb4d8cf9181ad252cb2`.
- Current protected base and merge base: `7dce2a67b44c36e73c877a2572fe43f159e8637a`.
- Risk: `R2_DEPENDENCY_SECURITY`; RECRUIT-01 requires distinct dependency/package-domain and
  assurance/security reviews after freeze.

The audit establishes only that the governed lock has no advisory known to the audit database at
execution time. It is not a general supply-chain, release, lender, Board or bankability assurance.
Issue #1110 remains open and unaffected.

## Verification receipt

| Check | Exact surface | Result |
|---|---|---|
| Governed environment | `DUTCHBAY_VENV=/workspace/dutchbay-epc-model/.venv ./check_venv.sh` on the frozen branch | PASS on Python 3.12.14 with the complete 311-distribution lock, including Hydra 1.3.7 and IPython 9.17.1 |
| Dependency policy | `tests/lint/test_extra_pin_consistency.py` under governed Python 3.12 | 26 passed in 4.51 s; the exact lock must satisfy the abstract requirement; 1.3.5, 1.3.6 and 1.4.0.dev0-dev9 fail that same lock-admissibility predicate |
| Hostile prerelease oracle | parse the project requirement with `packaging` and enable prerelease matching explicitly | affected 1.4.0.dev0-dev9 rejected; stable 1.3.7 and fixed 1.4.0.dev10 admitted and pinned as positive test boundaries |
| Mandatory security gate | governed `PATH` + `make security` | Bandit: no medium/high findings over 92,354 lines; `pip-audit`: `No known vulnerabilities found` |
| Hydra runtime | reconciled governed environment plus a prior isolated `--target` probe of `hydra-core==1.3.7` | both selected and imported Hydra 1.3.7 exactly |
| Hydra CLI composition | reconciled governed environment, `tests/integration/test_sensitivity_cli_smoke.py` | passed together with the 26 policy tests (27 passed in 47.04 s); canonical sensitivity CLI completed successfully |
| Complete lock resolution | governed pip, `--dry-run --ignore-installed --no-cache-dir -r requirements.txt` | exit 0; resolved Hydra 1.3.7, retained IPython 9.17.1 from current main and produced no conflict |
| Changed-file hooks | pre-commit over all six implementation paths | all applicable hooks passed on the final 1.3.7 candidate |
| Changelog / whitespace | changelog dry run and `git diff --check` | both passed on the final 1.3.7 candidate |

The first candidate, Hydra 1.3.6, was explicitly rejected when the mandatory audit identified
CVE-2026-106439. This record retains that failed attempt so 1.3.6 cannot later be mistaken for an
audit-clean floor. The next candidate's simple `>=1.3.7` abstract floor was superseded after an
independent hostile constraint demonstrated that an explicit affected 1.4 prerelease could satisfy
it; the final abstract requirement therefore excludes every affected development release named by
the advisory.
