# Issue #1334 D4 implementation record

## Scope, authority, and fresh ingress

D4 adds one additive EYA-to-actual reconciliation boundary over the frozen
`ResourceAssessment` and replayed D3 `OperationalAEPResult`. It does not alter either
source artifact, estimate missing categories, annualize a partial period, or change any
canonical scenario, finance value, report, release state, or issue state. The emitted
finance proposal is structurally default-off and has no apply path. Issue #1110 remains
`OPEN_HOLD`; canonical-finance, bankability, lender, Board, and release eligibility all
remain false.

The controlling capability profile is issue-comment `6246195424`. The interrupted
writer lease was revoked by comment `6253522866`; recovery lease `L-1334-D4-002`, issue
comment `6253524354`, produced the first checkpoint. Finance and assurance review then
rejected that exact object, as reconciled in issue comment `6298875580`. Corrective lease
`L-1334-D4-003` in that comment produced the first corrective successor. Its exact
allowlist was the D4 module, the D4 test, and this record. No export facade,
environment, workflow, dependency, configuration, canonical-finance, or unrelated path is
in corrective scope.

The first successor was rejected by assurance and finance review in issue comment
`6305049619`. Corrective lease `L-1334-D4-004` was then revoked as `NO_EVIDENCE`; it
made no mutation. Replacement lease `L-1334-D4-005`, issue comment `6306366851`, is the
sole implementation authority for this second corrective successor. It retains the exact
three-path allowlist above and confers no issue, pull-request, merge, release, reliance, or
HOLD authority.

Before mutation, the recovery writer freshly read the complete current 75-row active
GWTF CSV (SHA-256
`4b0d4c91ea9fcf0b2b12e41b37d68f4786175ebad342bd3c3f4950ccc3b5b668`), including the
exact unabridged `FRAMEWORK-01` CASPER, `FRAMEWORK-02` CESSPIT, and `FRAMEWORK-03`
CCCDIR rows; complete `AGENTS.md` and `CLAUDE.md`; complete steward skill; all four
RECRUIT-01 modules; and the resolver-selected
`docs/SESSION_HANDOVER_2026-10-17_D3_OPERATIONAL_AEP.md` with its complete declared
handover chain. The complete live #1334 body and comments, parent #1330 body, D1-D3
operational source/tests/records, resource contract/tests, both affected export surfaces,
and the exact OpenOA comparator below were also freshly ingested. The handover resolver,
75/75 GWTF bootstrap, governed-environment preflight, clean-head/tree/merge-base checks,
and exact target hash/absence checks passed before the first edit.

| Fresh source | SHA-256 or identity | Governing use |
|---|---|---|
| `.claude/skills/steward/SKILL.md` | `cf19ad23f7d7cd93da2121a4041a098f5f2cd659f42d54e8a075d8e2a2838a28` | evidence, lease, review, and checkpoint controls |
| RECRUIT-01 module 1 | `32fb1ea5975713c7ab3d68bc7042484ad2a512f72021f281bf7e5df24343398e` | capability and risk boundaries |
| RECRUIT-01 module 2 | `3a3eb5b016ba32f14a5822aefcc287ea8e9b1d3a05e1d6f288974a231bc91406` | lease and recovery boundaries |
| RECRUIT-01 module 3 | `2374dc23a0b40eb194766bcff05fa56d53c7c914b2e9164d59eef85cf2cb88f7` | independent review and attestation boundaries |
| RECRUIT-01 module 4 | `15ba99012044709a9407a06161694a02a698d942dba27bb8d915e4b161a0d592` | staged delegation and ingress boundaries |
| OpenOA `openoa/analysis/eya_gap_analysis.py` | commit `35e8a52c4cd8f43223f8181153d4e3f083f090d2`; SHA-256 `e0c161a34f2c1534d5613ff3341d6c4c72cc13a41950e8eef2dd8313d098d307` | category vocabulary and equation comparator only |

OpenOA is a methodological comparator, not a runtime dependency, source-acceptance
authority, professional opinion, or bankability claim. D4 imports no OpenOA code.

Before corrective mutation, the corrective writer independently repeated the complete
governance, framework, steward, RECRUIT-01, resolver-selected handover-chain, live #1334,
D1-D4 implementation-record, and relevant contract/test ingress. The exact leased
predecessor was clean at commit `253b078474330a7032738de02607abdddb60c041`, tree
`c9a1bfab11772883a29e5cf75a40d711dfdbba1d`; `origin/main` and the merge base were both
`8c4d0761545d1c6073d92c45d7de989e12281a1b`. The governed environment passed with Python
3.12.14, a non-editable installation, active-worktree imports, and no foreign checkout
paths. GWTF bootstrap loaded 75/75 active rules. An initial bootstrap invocation omitted
the required `DUTCHBAY_FLOW_RULESET_CSV` environment variable and failed loudly; the
corrected exact invocation passed before any edit.

Before second-corrective mutation, the replacement writer independently repeated the same
complete current governance/framework/steward/RECRUIT-01 and resolver-selected handover
chain ingress, then read the complete current D1-D4/resource sources, tests, implementation
records, and live #1334 body and all ten comments. The governed environment again passed
with Python 3.12.14, a non-editable installation, active-worktree imports, and no foreign
checkout paths; GWTF bootstrap again loaded 75/75 active rules. The leased predecessor was
clean at commit `35bd90fefff2878813ba0190dbaeffb4f51f3507`, tree
`7bd971053a02693cfd49c5ae0cfdc01fff4e904c`; the local `origin/main` and merge base were
both `8c4d0761545d1c6073d92c45d7de989e12281a1b`. A read-only live GitHub observation also
showed that remote `main` had subsequently advanced to
`0255c1fd1bb7ec6ddc9a06cb90e8a3df1267a318`; no fetch or ref mutation was performed
because this corrective lease is pinned to the recorded predecessor and local base.

## Contract and exact equation

The factory defensively validates and snapshots an exact `ResourceAssessment`. Every
numeric field must be an actual finite `float` (not a boolean or permissive numeric
subclass); `n_turbines` must be an actual positive integer; `identity_rtol` cannot exceed
the canonical default. A bounded, cycle-safe canonical-JSON traversal deeply detaches the
otherwise mutable run manifest. The resource claim is domain-separated and binds every
snapshot field, the canonical manifest JSON and digest, the source and power-curve IDs,
the selected P-level, standard-year hours, and exact `float.hex()` strings.

D4 replays the complete D3 result from its retained D1-D3 inputs before use, compares the
replay byte-for-structure to the supplied result, and domain-separates a claim over the D3
specification and result. The D3 result must say `actual_calendar_year`, span exactly one
UTC Jan-1-to-Jan-1 year, and contain exactly as many rational hours as the frozen EYA
standard year. A partial observed period cannot be relabelled or annualized by D4. An 8784
hour leap-year actual therefore cannot be compared to a conventional 8760-hour EYA without
a separately governed temporal policy.

For the selected EYA P-level:

- `E` is the exact `Fraction.from_float(stored_binary64_GWh) * 1_000_000` kWh;
- `A` is the exact replayed D3 net-meter energy in kWh;
- each available category delta is `operational actual net effect - EYA expected net
  effect`, with positive meaning an increase in actual energy relative to EYA;
- `U = A - E - sum(available signed category deltas)`; and
- the receipt independently proves `A - E - sum(deltas) - U = 0` exactly.

No display rounding or decimal reconstruction is allowed in the EYA projection. This can
produce a rational value microscopically different from the apparent decimal; that is an
intentional preservation of the original stored binary64 artifact.

The closed, ordered category partition is:

1. measurement/boundary;
2. weather/resource;
3. availability;
4. curtailment;
5. electrical;
6. wake/performance; and
7. method/model.

A category is available only from a complete paired expected/actual comparison carrying
verified immutable source and method bytes and binding the common project, partition, EYA
claim, and D3 claim. Missing evidence is an explicit unavailable state and never zero.
Evidenced zero remains available with an exact zero value and evidence identity. Category
and evidence selectors must be unique. Availability, curtailment, electrical, and
wake/performance actual effects are additionally checked against the negative of the
corresponding replayed D3 positive-loss components, closing sign substitution and double
counting through duplicate named categories.

An independent common-boundary attestation binds the project, asset identity, common
net-export delivery boundary, temporal comparison, mutually exclusive partition
semantics, source claims, and verified source/method artifacts. All claim and receipt
hashes are domain-separated. Public model dumps omit retained provenance bytes and the
retained D3 source artifacts.

## Finance and authority fence

`FinanceUpdateProposal` is data only. It must retain the current canonical basis pending
a separate R3 re-baseline, is exactly `default_off=True`, carries an empty update tuple,
and exposes no target scenario, candidate capacity factor, P50, P90, debt, or tariff. It
has no apply method. Apply authorization and canonical-finance, bankability, lender,
Board, and release eligibility are exact false booleans. A separate R3 is exact true and
issue #1110 is exactly `OPEN_HOLD`. Construction and deterministic result replay reject
candidate-value, flag, or issue-state laundering. Authority-bearing and other closed
vocabulary text must be an exact built-in `str`, not a subclass whose equality or hashing
can impersonate an allowed literal while serializing different text.

Every D4-admitted `OperationalEnergyQuantity` must likewise be the exact built-in D3
contract, not a subclass. D4 validates its stored numerator, denominator, and exact `kWh`
unit directly, reconstructs the canonical quantity, and derives its `Fraction` without
calling an overridable method. Every public D4 `model_dump()` revalidates its object before
emitting. Complete-result serialization additionally rebuilds the bridge from retained
sources immediately before output, compares a canonical projection of every D4-owned
quantity, category component, proposal, and receipt against that replay, and rejects stale
or forged state.

## Independent fixture and hostile controls

The independent complete-2025 fixture uses 365 daily observations: meter energy is 23 kWh
per day (`A=8395 kWh`), one 1 kW complete turbine produces `8760 kWh`, availability is
`365 kWh`, curtailment is `182.5 kWh`, electrical loss is `365 kWh`, separately evidenced
resource gross is `10000 kWh`, and wake/performance loss is `500 kWh`. The EYA artifact
stores `0.009 GWh`; the oracle deliberately uses its exact binary64 fraction rather than
the tempting `9000 kWh` decimal. The focused suite proves the exact bridge equation and a
negative control proving those two EYA values differ.

Hostile controls cover resource/D3 digest substitution; forged D3 output; project,
partition, and claim-boundary substitution; duplicate categories and cross-project pairs;
loss sign/value substitution; observed-period relabelling; EYA/actual hours mismatch;
boolean, NaN, and permissive resource numerics; cyclic and over-deep manifests; provenance
digest substitution; source mutation and deep-snapshot independence; factory-only replay;
serialization without source bytes; missing versus evidenced zero; and finance/HOLD
authority laundering. The corrective suite additionally uses a hostile `str` subclass that
renders forbidden text while overriding equality, inequality, and hashing to impersonate an
allowed literal. Proposal, receipt, spec, boundary, attribution, component, snapshot, and
source-resource construction must reject it before `model_dump()` can serialize the forged
state.

The second corrective suite adds a hostile `OperationalEnergyQuantity` subclass whose
stored nonzero numerator disagrees with its overridden zero-valued `as_fraction()` method.
Both component and receipt construction and serialization reject that subclass. Additional
`object.__setattr__` controls mutate every public D4 value-object family after construction,
including category state and arithmetic, quantity denominator and substituted values,
proposal decision/HOLD/default/update/candidate/authority state, and receipt HOLD,
authority, mutation, and residual state. Direct nested mutation followed by complete-result
serialization must replay and fail closed.

## Predecessor and finding disposition

| Finding family | D4 disposition |
|---|---|
| D1 evidence schema, time, role, provenance, epistemic, and authority controls | `CLOSED` by consuming D1 only through the fully replayed D3 result; D4 does not loosen D1 |
| D2 normalization, timezone, row-byte replay, group completeness, and deterministic numeric parsing | `CLOSED` for selected data by full D3 replay, which independently replays D2; D4 performs no normalization |
| D3 matched energy identities, complete-year semantics, missing-data states, source binding, and authority fences | `CLOSED` by full deterministic D3 replay plus expected domain-separated D3 claim |
| Mutable `ResourceAssessment.run_manifest`, permissive identity tolerance, non-finite/bool numerics, and binary64 ambiguity | `CLOSED` by exact-type checks, canonical bounded deep snapshot, canonical-tolerance cap, and float-hex/Fraction projection |
| Missing gap-category comparison evidence | `CLOSED` by unavailable-not-zero states; D4 never derives weather/resource, measurement/boundary, or method/model effects from D3 presence |
| Temporal comparability and annualization | `CLOSED` for one complete actual calendar year with exact EYA-hour equality; all partial or mismatched periods fail |
| Canonical finance, scenario mutation, issue closure, lender/Board/release authority | `CLOSED` by the structurally inert proposal, no apply path, hard-false flags, separate-R3 requirement, and #1110 `OPEN_HOLD` |
| `D4-FIN-R1-01` hostile `str`-subclass decision/HOLD laundering | `CLOSED` in the corrective candidate by exact built-in-string validation across all D4 closed vocabularies plus serialization-path negative controls |
| `D4-ASSURANCE-R1-001` governed Ruff formatting failure | `CLOSED` by applying governed Ruff 0.14.14 formatting and rerunning both lint and format checks on the corrected source/test bytes |
| `D4-ASSURANCE-R1-002` false formatting and main-sync receipts | `CLOSED` by replacing both claims with the exact corrective results and distinguishing candidate HEAD from `origin/main`/merge base |
| `D4-ASSURANCE-R2-001` subclass-overridable energy validation | `CLOSED` in the second corrective candidate by requiring exact `OperationalEnergyQuantity`, validating canonical stored fields without method dispatch, and adding hostile subclass construction and serialization controls |
| `D4-FIN-R2-01` post-construction serialization laundering | `CLOSED` in the second corrective candidate by revalidating every public D4 dump, replaying retained sources immediately before complete-result output, and adding proposal, receipt, component, quantity, and complete-result mutation controls |

## Deliberate limitations

- Boundary and category evidence are caller attestations. D4 verifies their retained bytes,
  claims, consistency, and arithmetic, but does not authenticate their external authors.
- D3 has no separately comparable asset-identity field; the D4 common asset identity is
  therefore explicitly attested rather than inferred.
- Only availability, curtailment, electrical, and wake/performance actual effects can be
  independently cross-checked to named D3 components. Other categories require their own
  paired evidence and remain unavailable when it is absent.
- D4 performs no EYA recalculation, resource-model rerun, long-term correction,
  uncertainty analysis, imputation, allocation, tariff calculation, or finance update.
- The exact binary64 policy preserves source bits, not a human-intended decimal that was
  never stored in the source artifact.

## Verification receipt

All commands use the governed shared Python 3.12.14 environment, import from this worktree,
and run with no editable or foreign-worktree installation. Hosted CI and independent R3
review remain coordinator-owned gates. The rejected predecessor's receipts are not carried
forward as corrective-candidate evidence.

| Check | Exact command | Result |
|---|---|---|
| D1-D4/import focus | governed Python `-m pytest -p no:cacheprovider --no-cov -q` on D1, D2, D3, D4, and v14 import-surface modules | 285 passed in 10.98 s |
| D4 independent/hostile focus | governed Python `-m pytest -p no:cacheprovider --no-cov -q tests/contracts/test_eya_actual_bridge.py tests/contracts/test_contracts_v14_import_surface.py -x` | final rerun: 46 passed in 10.07 s on the second-corrective source/test bytes |
| D4 targeted coverage | governed Python `-m pytest -p no:cacheprovider -q tests/contracts/test_eya_actual_bridge.py --cov=analytics.operational.eya_bridge --cov-report=term-missing --cov-fail-under=95` | 40 passed in 72.06 s; 95.27% (634 statements, 30 missing) |
| Strict source types | governed Python `-m mypy --no-incremental analytics/operational/eya_bridge.py` | success; no issues in one source file |
| Ruff lint/format | governed `ruff check` and `ruff format --check` over the D4 source and test | all checks passed; both files formatted |
| Public docstring ratchet | governed Python `-m pytest -p no:cacheprovider --no-cov -q tests/lint/test_docstring_coverage.py` | 12 passed in 1.11 s |
| Shared contract suite | governed Python `-m pytest -p no:cacheprovider --no-cov -q tests/contracts` | 1678 passed in 77.91 s |
| Changelog dry-run | governed Python `scripts/compile_changelog.py --dry-run` | passed; pending fragments rendered without repository mutation |
| Framework fence and GWTF bootstrap | governed `pytest` on `test_framework_expansions_match_csv.py` plus governed bootstrap with the current CSV | 28 passed in 2.02 s; 75/75 active rules loaded |
| Governed environment | `DUTCHBAY_VENV=/workspace/dutchbay-epc-model/.venv bash check_venv.sh --no-bootstrap` | PASS; Python 3.12.14, non-editable install, no foreign checkout paths, imports from the D4 worktree |
| Exact-file pre-commit | governed `pre-commit run --files` over the exact three-path second-corrective allowlist | every applicable hook passed with no rewrite; TOML and YAML hooks skipped because the allowlist contains neither file type |
| Main synchronization | compare the leased predecessor, local `origin/main`, and merge base before second-corrective mutation; separately read live GitHub without mutating refs | predecessor `35bd90fefff2878813ba0190dbaeffb4f51f3507`; local `origin/main` and merge base both `8c4d0761545d1c6073d92c45d7de989e12281a1b`; live remote `main` observed at `0255c1fd1bb7ec6ddc9a06cb90e8a3df1267a318` |
| Diff/status hygiene | `git diff --check` and exact corrective-allowlist inspection immediately before freeze | passed; exactly the three leased allowlist paths differ from the predecessor |
