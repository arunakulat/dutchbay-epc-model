# PR1178: SciPy stubs and KS p-value typing

Status: implementation checkpoint prepared for independent review. This record is
not merge acceptance. The PR and external exact-head attestations determine delivery.

## Scope and controlling identities

The original Dependabot candidate was
`fe516af0e7a2cd0c0613f60bb0293d3a69c23184`, changing only scipy-stubs
1.18.0.1 to 1.18.1.0. Current protected base at implementation is
`dbd924a00dd4b29e23139da768a8f2603396dc17`. It was merged into the existing
PR branch without conflicts; this preserves the original candidate's ancestry.
The sole coordinator is task `01a07cb8-51de-72e3-b0cc-6f4d807df7c6`.
Its dedicated worktree is `/Users/aruna/.codex/worktrees/0fc6/dutchbay-epc-model`.

Fresh ingress covered AGENTS, the complete 74-rule current CSV (SHA-256
`0cc23891d3328d95e14031e07075d186b43545e4eb0d310303ff3c8d1c2148c1`), the four
RECRUIT-01 modules, pinned unabridged framework definitions, September 7 handover
and applicable predecessor HOLDs, dependency/type/runtime contracts, CI and
PR1174/PR1176 findings. R2 load-bearing type tooling requires separate dependency/type
and assurance reviewers. Neither independent initial disposition supports rejecting
the upgrade as intrinsically incompatible; both require a repair and fresh review.

## Problem and repair

Hosted job `99729301369` in run `33467161754` reports two strict mypy errors:
`float(ks_pvalue)` receives `object` after unpacking a `kstest` result in
`wind_resource/weibull_fit.py` and `wind_resource/wind_analyzer.py`.
The new stubs explicitly type the named `pvalue` property. Both consumers now retain
the result and call `float(ks_result.pvalue)`. KS inputs, filtering, fit mathematics,
SciPy runtime version and all other outputs remain unchanged. No cast, ignore or
type/CI relaxation is introduced. VERSION stays 15.4.0 because committed financial
behavior does not change.

The new regression test computes the two-sided KS statistic directly from empirical
CDF jumps and the Weibull formula, then obtains its finite-sample tail probability
through `scipy.stats.kstwo.sf`. It covers both public consumers and two seeded samples.
Existing wind tests remain intact. Independent reviewer runtime probes additionally
compared tuple and named-field access on different samples.

## Verification receipts

All local Python commands use `/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python`
with `DUTCHBAY_VENV` set to that persistent environment and the active worktree first on
`PYTHONPATH`. No package was installed or environment replaced. Evidence paths below
are relative to `/Users/aruna/Downloads/DutchBay_Oldest_First_Programme_2026-09-07/pr1178/`.
The original candidate is preserved in a verified complete Git bundle there.

| Check | Command or precise invocation | Result |
|---|---|---|
| Environment | `python -VV`; `./check_venv.sh --no-bootstrap` with governed environment | Python 3.12.13; PASS, active-checkout imports, no foreign or editable contamination |
| Governance | `python dutchbay_bootstrap_rules.py` with explicit canonical CSV path | 74 active v3.0 rules |
| Full lock resolution | `python -m pip install --dry-run --ignore-installed --disable-pip-version-check --no-cache-dir -r <candidate_requirements.txt> -c constraints.txt` | exit 0; `full_candidate_resolver.json`; includes target stubs and retained numerical pins |
| Composed extras | `python -m pip install --dry-run --disable-pip-version-check --no-cache-dir -r <candidate_requirements.txt> -c constraints.txt '.[dev,wind,micrositing,gis,report,grid,jobs,ingestion]'` | exit 0; would install project and target stubs; unchanged installed packages may satisfy pins, supplementary to full lock resolution |
| Target stub provenance | Version-specific PyPI metadata and SHA-256 verification of downloaded wheel | `fc1f00da3eb6bf1adf2138774b5e6a91dcf7c77039ff199577dc47929c10793e` |
| Type negative baseline | `python -m mypy --no-incremental --cache-dir=/dev/null` with 589 `--shadow-file` mappings to verified new stub sources, checking both original consumers | exit 1, exactly the two hosted errors; complete argv in `original_type_reproduction.json` |
| Library types | Same target-stub mapping and cache controls, full workflow library/entrypoint argv | exit 0, 269 source files; complete argv in `repaired_library_types.json` |
| Scripts types | Same mapping, `scripts/ --ignore-missing-imports --allow-untyped-defs --allow-untyped-calls --allow-any-generics` | exit 0, 67 source files; complete argv in `repaired_scripts_types.json` |
| Focused regression | `python -m pytest -p no:cacheprovider tests/wind/test_weibull_ks_pvalue.py tests/wind/test_wind_analyzer.py tests/wind/test_arco_wiring.py --no-cov -q` | 49 passed, 1 warning in 3.38s |
| Negative control | Same new test via `pytest.main`, session plugin substitutes KS statistic into the pvalue field in memory | expected exit 1; all four cases fail; `pvalue_negative_control.json` |
| Runtime equivalence | Both public functions, four seeded 256-point Weibull samples; exact complete output comparison against pre-edit capture | PASS, all eight outputs equal; seeds and distribution parameters in `baseline_runtime.json`, result in `runtime_equality.json` |
| Lint | `ruff check wind_resource/weibull_fit.py wind_resource/wind_analyzer.py tests/wind/test_weibull_ks_pvalue.py` | exit 0 |
| Mandatory format | `black --check` and `isort --check-only` on the same three paths | exit 0 for both |
| Advisory format | `ruff format --check` on the same three paths | exit 1: pre-existing adjacent string layout in wind_analyzer differs from Black; retained mandatory Black format |
| Whitespace | `git diff --check` | exit 0 |
| Full finance, QSTS, coverage, release qualification locally | not run | No local numerical-runtime upgrade; exact-head hosted suite and Grid Study remain required before merge. No qualification or release claim. |

Local target-stub shadow mapping substitutes existing stub paths without altering the
shared installation. It is supplementary to an actual target-package installation
and type check in final-head CI. Unused mypy section warnings occurred. The focused
NetCDF integration emitted a NumPy ndarray binary-size warning; its test passed.
There is no installed local Git pre-commit hook; direct lint, format, types and
diff checks were run, with no hook bypass. Hosted mandatory checks remain intact.

## Findings and boundaries

PR1176's mpmath/SymPy and NumPy-typing conflicts are not reproduced: those pins are
unchanged and this full candidate lock resolves. PR1174's consumer-ceiling review
method remains applicable. Stale explanatory comments in existing dependency policy
are outside this focused repair and are not used as dependency authority.

The original type failure is closed by local repaired type evidence, pending fresh
independent review and exact-head hosted confirmation. Base movement after review
requires the RECRUIT-01 proofs or fresh review; no earlier acceptance transfers.
Issue #1110 remains OPEN. The production assembly-authority catalogue remains empty.
No professional, publication, deployment, release, lender, Board or HOLD boundary changes.
