# Issue #1334 D4 implementation record

**Record date: 2026-10-25.** Sections below up to and including "Fourth corrective
verification" are the historical record of Codex's corrective candidates, each measured on
the host and the bytes current at its own time. Their figures are kept as written because a
superseded receipt is evidence of what was observed, not a claim about today. **The receipts
that describe the bytes this record ships with are in "Receipts restated at the committed
bytes (2026-10-25)" at the end of this file.** Read that section, not the earlier tables,
for the committed state. Raised as O-2 by the task-domain lane on #1381 and closed here.

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

The second corrective successor was rejected by assurance review in issue comment
`6346129597` as `D4-ASSURANCE-R3-001`; domain review accepted its exact object and finance
review passed its substantive controls but stopped on protected-main drift. Corrective lease
`L-1334-D4-007` in that comment is the sole implementation authority for this third
corrective successor. It authorizes rebasing the existing three D4 commits onto exact
`origin/main` `86ca5732535850c9ab47253d37cbee29ba9fa276` and editing only the same
three-path corrective allowlist. It grants no issue, pull-request, review, merge, release,
reliance, or HOLD authority.

The third corrective successor was accepted by the renewable-energy/domain and finance/KPI
reviewers but rejected by software assurance in issue comment `6359540946` as
`D4-ASSURANCE-R4-001`. The retained D2 boundary could hash the buffer of a `bytes` subclass
while dispatching CSV parsing through its overridden `decode()` method, so D4's transitive
D3 replay did not prove that the bytes named by the source digest were the measurements used.
Corrective lease `L-1334-D4-008` in that comment is the sole implementation authority for
this fourth corrective successor. Its exact allowlist is the D4 module, the D4 test, and
this record. Lower-layer D1/D2/D3/resource source and tests remain forbidden.

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
| OpenOA `openoa/analysis/eya_gap_analysis.py` | commit `35e8a52c4cd8f43223f8181153d4e3f083f090d2`; SHA-256 `e0c161a34f6c1534d5613ff3341d6c4c72cc13a41950e8eef2dd8313d098d307` | category vocabulary and equation comparator only |

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

Before third-corrective mutation, the writer freshly read the complete current 75-row GWTF
CSV (unchanged SHA-256 `4b0d4c91ea9fcf0b2b12e41b37d68f4786175ebad342bd3c3f4950ccc3b5b668`),
including the exact CASPER, CESSPIT, and CCCDIR rows; complete `AGENTS.md`, `CLAUDE.md`,
steward skill, and all four RECRUIT-01 modules; live issue #1334 and the controlling lease
comment; the D1-D4/resource sources, tests, and implementation records; and the
resolver-selected `docs/SESSION_HANDOVER_2026-10-22_AUDIT_GATE_CLEARED_ON_MERIT.md`
plus its declared D3, D2, work-list, capability-roadmap, v15.6.1 startup, platform-plan,
H08, and RECRUIT-01 recovery lineage. The resolver selected the 22 October record from
current `origin/main`; the GWTF bootstrap loaded 75/75 active rules. The governed
environment passed with Python 3.12.14, 311 locked distributions, non-editable package
metadata, active-worktree imports, and no foreign checkout paths.

The leased predecessor was clean at commit
`c8f2692b5c4d7c042bf28c1e437865469f6eb91b`, tree
`b2b1be295f467fd30e44ebb2b10e921437407204`. Its seven-path Git-blob manifest SHA-256
was `c8f047fff01074df670bba0ed4e1cd265a3ba37ae487c567127e3d7d507844a5`.
The authorized three-commit rebase onto `86ca5732535850c9ab47253d37cbee29ba9fa276`
completed without conflict and produced commit `be5896719a6bd454ff0ec89d4a970aab9759184b`,
tree `78406543c3b2ea5087c83c293bb31653cf5e1bf8`; every one of the seven D4
Git blobs and the complete manifest digest remained byte-identical. The merge base then
equalled the required protected base before any content edit.

Before fourth-corrective mutation, the writer independently repeated the complete current
governance, framework, steward, RECRUIT-01, resolver-selected handover-chain, live #1334 and
#1110, D1-D4/resource implementation-record, and relevant source/test ingress. The current
GWTF SHA-256 remained
`4b0d4c91ea9fcf0b2b12e41b37d68f4786175ebad342bd3c3f4950ccc3b5b668`; bootstrap loaded
75/75 active rules. The governed environment passed with Python 3.12.14, 311 locked
distributions, non-editable package metadata, active-worktree imports, and no foreign
checkout paths. The resolver selected the 22 October handover first and its complete
declared D3, D2, work-list, capability-roadmap, v15.6.1 startup, platform-plan, H08, and
RECRUIT-01 recovery lineage was read.

The leased predecessor was clean at commit
`7110fd213d08318fba2fcccaa23af018786f2f75`, tree
`9eaa8b266a54e75447796cead0f3dd57a60904b2`; local `origin/main`, its merge base, and
the first live remote observation all remained
`86ca5732535850c9ab47253d37cbee29ba9fa276`. Issue #1334 and the capability tracker
remained open, issue #1110 remained `OPEN` with its Board/lender `HOLD`, and the complete
open-PR sweep contained no D4 overlap.

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

The third corrective suite adds a tuple subclass whose indexed stored attribution is a
cross-project substitution while iteration exposes a valid attribution. D4 now requires
`type(attribution_evidence) is tuple` before defensive reconstruction at the shared build
and retained-result replay boundary, so the hostile object is rejected as `INVALID_INPUT`
before attribution digest construction, result retention, or serialization. The same audit
confirmed that D4-owned `category_components` and `proposed_updates` already require exact
built-in tuples. Retained source and method artifacts now likewise require exact built-in
`bytes`; representative tuple- and bytes-subclass controls pin each boundary.

The fourth corrective suite adds a full D2-to-D3-to-D4 hostile control whose retained source
is a `bytes` subclass with an invalid underlying buffer and an overridden `decode()` that
returns the valid annual meter CSV. D2 construction and D3 estimation deliberately succeed,
proving the negative control reaches the transitive boundary. Before either D4 claim
construction or bridge retention, D4 now reconstructs every retained D1-D3 container and
replays each D2 result from exact built-in bytes detached through the immutable buffer
protocol. Hashing and UTF-8 parsing therefore consume the same non-overridable byte value;
the hostile underlying buffer fails closed as `OPERATIONAL_PROVENANCE_MISMATCH`.

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
| `D4-ASSURANCE-R3-001` tuple-subclass attribution substitution | `CLOSED` in the third corrective candidate by requiring an exact built-in attribution tuple at both construction and retained replay, rejecting divergent indexed/iterated values before digest or retention, and pinning the other D4-owned retained-container boundaries |
| `D4-ASSURANCE-R4-001` transitive D2 source-buffer/decode substitution | `CLOSED` in the fourth corrective candidate by rebuilding exact D1-D3 containers, detaching retained source, lineage, derivation, TZif, boundary, and supplemental artifacts from their immutable buffers before D2/D3 replay, and rejecting the full hostile D2→D3→D4 control before claim construction or retention |

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

## Verification receipt (second corrective candidate, superseded)

> **Superseded, retained as history.** This table was measured on the owner's host against
> the second-corrective candidate's bytes, not against the bytes committed here. Four of its
> rows no longer describe the shipped artifact: the D1-D4/import focus, the D4
> independent/hostile focus, the D4 targeted coverage and the GWTF active-rule count. The
> current figures for all four are in "Receipts restated at the committed bytes
> (2026-10-25)". Do not cite this table as evidence about the committed module.

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

### Third corrective verification (`L-1334-D4-007`)

These receipts supersede earlier corrective results only where the third-corrective source,
test, record, or protected base changed. Hosted CI and fresh independent R3 review remain
coordinator-owned gates.

| Check | Exact command | Result |
|---|---|---|
| Governed environment | `DUTCHBAY_VENV=/workspace/dutchbay-epc-model/.venv bash check_venv.sh --no-bootstrap` | PASS; Python 3.12.14, 311 locked distributions, non-editable install, no foreign checkout paths, and imports from this worktree |
| GWTF bootstrap | `DUTCHBAY_FLOW_RULESET_CSV="$PWD/go_with_the_flow_rules_v3_0_clean.csv" PYTHONPATH="$PWD"` plus governed Python `dutchbay_bootstrap_rules.py` | 75/75 active v3.0 rules loaded |
| Resolver | governed Python `scripts/list_session_handover_records.py` after the authorized rebase | exit 0; selected the 22 October PERSIST-01 record first at protected commit `86ca5732535850c9ab47253d37cbee29ba9fa276` |
| Rebase continuity | compare the sorted seven-path `path<TAB>git-blob-SHA` manifest before and after `git rebase origin/main` | conflict-free; byte-identical manifest, SHA-256 `c8f047fff01074df670bba0ed4e1cd265a3ba37ae487c567127e3d7d507844a5`; merge base equals `86ca5732535850c9ab47253d37cbee29ba9fa276` |
| D4/import focus | governed Python `-m pytest -p no:cacheprovider --no-cov -q tests/contracts/test_eya_actual_bridge.py tests/contracts/test_contracts_v14_import_surface.py -x` | 48 passed in 10.59 s |
| D1-D4/resource/import focus | governed Python `-m pytest -p no:cacheprovider --no-cov -q` on the resource, D1, D2, D3, D4, and v14 import-surface modules | 309 passed in 11.65 s |
| D4 targeted coverage | governed Python `-m pytest -p no:cacheprovider -q tests/contracts/test_eya_actual_bridge.py --cov=analytics.operational.eya_bridge --cov-report=term-missing --cov-fail-under=95` | 42 passed in 82.29 s; 95.43% (634 statements, 29 missing) |
| Shared contract suite | governed Python `-m pytest -p no:cacheprovider --no-cov -q tests/contracts` | 1680 passed in 83.90 s |
| Strict source types | governed Python `-m mypy --no-incremental analytics/operational/eya_bridge.py` | success; no issues in one source file |
| Ruff lint/format | governed `ruff check` and `ruff format --check` over the D4 source and test | all checks passed; both files already formatted |
| Exact-file pre-commit | governed `pre-commit run --files` over the exact three-path third-corrective allowlist | every applicable hook passed; TOML and YAML hooks skipped because the allowlist contains neither file type |
| Protected-head and diff hygiene | `git ls-remote origin refs/heads/main`; `git diff --check`; exact corrective and branch allowlist comparisons | remote and local `origin/main` remain `86ca5732535850c9ab47253d37cbee29ba9fa276`; diff check passed; exactly three corrective paths and the expected seven total D4 paths |

### Fourth corrective verification (`L-1334-D4-008`)

These are writer-side checkpoint receipts, not independent acceptance, hosted CI, canonical
adoption, or authority to lift any `HOLD`.

| Check | Exact command | Result |
|---|---|---|
| Governed environment | `DUTCHBAY_VENV=/workspace/dutchbay-epc-model/.venv PYTHONPATH="$PWD" ./check_venv.sh` | PASS; Python 3.12.14, 311 locked distributions, non-editable install, active-worktree imports, and no foreign checkout paths |
| GWTF bootstrap | `DUTCHBAY_FLOW_RULESET_CSV="$PWD/go_with_the_flow_rules_v3_0_clean.csv" PYTHONPATH="$PWD"` plus governed Python `dutchbay_bootstrap_rules.py` | 75/75 active v3.0 rules loaded |
| Resolver | governed Python `scripts/list_session_handover_records.py` | exit 0; selected the 22 October PERSIST-01 record first at protected commit `86ca5732535850c9ab47253d37cbee29ba9fa276` |
| D4/import focus | governed Python `-m pytest -p no:cacheprovider --no-cov -q tests/contracts/test_eya_actual_bridge.py tests/contracts/test_contracts_v14_import_surface.py -x` | 50 passed in 20.16 s |
| D1-D4/resource/import focus | governed Python `-m pytest -p no:cacheprovider --no-cov -q` on the resource, D1, D2, D3, D4, and v14 import-surface modules | 311 passed in 20.55 s |
| D4 targeted coverage | governed Python `-m pytest -p no:cacheprovider -q tests/contracts/test_eya_actual_bridge.py --cov=analytics.operational.eya_bridge --cov-report=term-missing --cov-fail-under=95` | 44 passed in 132.88 s; 95.35% (710 statements, 33 missing) |
| Shared contract suite | governed Python `-m pytest -p no:cacheprovider --no-cov -q tests/contracts` | 1682 passed in 100.70 s |
| Strict source types | governed Python `-m mypy --no-incremental analytics/operational/eya_bridge.py` | success; no issues in one source file |
| Ruff lint/format | governed `ruff check` and `ruff format --check` over the D4 source and test | all checks passed; both files already formatted after one governed formatting pass |
| Transitive hostile control | focused D4 test constructs a D2 result from divergent buffer/`decode()` bytes, then constructs D3 and probes D4 claim/build | D2 and D3 accept the crafted object with `8395 kWh`; D4 claim construction and bridge construction both reject as `OPERATIONAL_PROVENANCE_MISMATCH` |
| Exact hostile regression | governed Python `-m pytest -p no:cacheprovider --no-cov -q tests/contracts/test_eya_actual_bridge.py::test_transitive_d2_bytes_decode_substitution_fails_before_d4_claim` | 1 passed in 1.08 s |
| Exact-file pre-commit | governed `pre-commit run --files` over the exact three-path fourth-corrective allowlist | the first pass normalized source imports with `isort`; focused tests, Ruff, and mypy were repeated after that import-only rewrite, and the second pass completed with every applicable hook passed |
| Changelog fragment compilation | governed Python `scripts/compile_changelog.py --dry-run` | exit 0; no file mutation |
| Protected-head and diff hygiene | `git ls-remote origin refs/heads/main`; `git diff --check`; exact corrective and branch allowlist comparisons | live and local `origin/main` remain `86ca5732535850c9ab47253d37cbee29ba9fa276`; merge base is the same protected commit; diff check passed; exactly three corrective paths and the expected seven total D4 paths |


## Receipts restated at the committed bytes (2026-10-25)

Raised as O-2 by #1381's task-domain lane: the tables above report figures the committed
bytes do not produce, which is exactly the receipt decay `VERIFY-01` exists to stop. Rather
than edit history, the four drifted rows are re-measured here against the artifact this
record ships with, and the earlier tables are labelled as superseded.

Subject these figures describe, by content digest rather than by commit, so the statement
stays true however the branch is later rebased or merged:

| Path | SHA-256 of the file bytes |
|---|---|
| `analytics/operational/eya_bridge.py` | `174e7a7ee753fdea8e70637725ec02a5449ec2c45f4742b2f236d055fe4bfda4` |
| `tests/contracts/test_eya_actual_bridge.py` | `17cb034c452dcfa896fb6b7fefb09a9e8f4eb30ebeb9b53c0b79591312fbcd32` |

Environment: Claude Code cloud container, checkout-local `.venv`, Python **3.12.3** — not the
owner's 3.12.14 host, which is unreachable from a container. The interpreter differs from the
one the tables above used, and that is stated rather than papered over.

| Check | Exact command | Result at these bytes |
|---|---|---|
| D1-D4/import focus | `.venv/bin/python -m pytest -p no:cacheprovider --no-cov -q` over `test_resource_assessment.py`, `test_operational_evidence_contract.py`, `test_operational_normalization.py`, `test_operational_aep.py`, `test_eya_actual_bridge.py`, `test_contracts_v14_import_surface.py` | `325 passed in 23.30s` (the superseded table said 285; the module set is named here because the earlier row did not name it) |
| D4 independent/hostile focus | `.venv/bin/python -m pytest -p no:cacheprovider --no-cov -q tests/contracts/test_eya_actual_bridge.py tests/contracts/test_contracts_v14_import_surface.py -x` | `64 passed in 21.84s` (superseded table: 46) |
| D4 targeted coverage | `.venv/bin/python -m pytest -p no:cacheprovider -q tests/contracts/test_eya_actual_bridge.py --cov=analytics.operational.eya_bridge --cov-report=term-missing --cov-fail-under=95` | `58 passed in 157.42s`; **95.92%**, 710 statements, 29 missed (superseded table: 40 passed, 95.27%, 634 statements, 30 missing) |
| GWTF bootstrap | `DUTCHBAY_FLOW_RULESET_CSV="$PWD/go_with_the_flow_rules_v3_0_clean.csv" PYTHONPATH="$PWD" .venv/bin/python dutchbay_bootstrap_rules.py` | `77 rules; versions: v3.0; latest = v3.0`, `Status breakdown: active=77`. The `75/75` figure stated in the prose above and in the superseded tables was true when observed and is superseded: the ruleset has since gained rows, `REVIEW-01` among them |
| Framework fence | `.venv/bin/python -m pytest -p no:cacheprovider --no-cov -q tests/lint/test_framework_expansions_match_csv.py` | `28 passed in 3.52s` |
| Public docstring ratchet | `.venv/bin/python -m pytest -p no:cacheprovider --no-cov -q tests/lint/test_docstring_coverage.py` | `12 passed in 1.68s` |
| Shared contract suite | `.venv/bin/python -m pytest -p no:cacheprovider --no-cov -q tests/contracts` | `1696 passed in 116.63s` (superseded table: 1678) |
| Strict source types | `.venv/bin/python -m mypy --no-incremental analytics/operational/eya_bridge.py analytics/operational/__init__.py` | `Success: no issues found in 2 source files` |
| Ruff lint and format | `.venv/bin/ruff check` and `.venv/bin/ruff format --check` over the D4 source and test | `All checks passed!`; both files already formatted |
| Changelog dry-run | `.venv/bin/python scripts/compile_changelog.py --dry-run` | exit 0 |
| Governed environment | `./check_venv.sh --no-bootstrap` | `PASS`; `editable_project_install: false`, `project_install_url: null`, no absent locked distribution, no foreign checkout path |
| Owner's host | — | not run — a cloud container cannot read `/Users/aruna/...`, so nothing about that host is asserted here |

### Controls added for #1381's review conditions

The assurance lane found that the module's refusal machinery carried no negative control: a
twelve-mutation battery left five mutants alive. Four controls were added to
`tests/contracts/test_eya_actual_bridge.py`. **No line of
`analytics/operational/eya_bridge.py` changed**, which the digest above lets any reader
confirm against the pre-condition head.

Each control was proved non-vacuous by mutating the committed module, running the suite, and
restoring and re-digesting the file. A mutation that did not change the file was reported as
such rather than as a pass.

| Condition | Mutation applied to the committed module | Test that fired | Result |
|---|---|---|---|
| A-1 (line 1353) | `_actual_net_energy`'s refusal on an unavailable D3 net-meter reading replaced by `return Fraction(0)` | `test_unavailable_d3_net_meter_energy_is_refused_and_never_zeroed` | `1 failed, 57 passed`; the intended control failed alone |
| A-1 (line 1368) | `_validate_category_actual`'s refusal on a category lacking an available D3 component replaced by a bare `return` | `test_category_without_an_available_d3_component_is_refused` | `1 failed, 57 passed`; fired alone |
| A-2 (domain separation) | `_claim_digest` drops `domain.encode("ascii") + b"\x00"` | `test_claim_digest_is_domain_separated_against_an_external_anchor` | `1 failed, 57 passed`; fired alone |
| A-2 (key ordering) | `_canonical_json` sets `sort_keys=False` | `test_canonical_json_sorts_keys_and_closes_separators` and the anchor test | `2 failed, 56 passed` |
| A-3 (digest length) | `_SHA256_RE` relaxed from `^[0-9a-f]{64}$` to `^[0-9a-f]+$` | `test_require_digest_enforces_length_and_lowercase_hex` | `4 failed, 54 passed`; the four short-hex cases |

Module digest before and after the whole battery:
`174e7a7ee753fdea8e70637725ec02a5449ec2c45f4742b2f236d055fe4bfda4`, unchanged.

One correction worth recording rather than hiding, since `VERIFY-01` is about the record
being true and not about it being flattering. The first push of these controls failed CI's
`Code Quality Checks`: `black --check` reformatted a conditional expression inside a
generator that `ruff format` had accepted. `make lint` describes `black` as advisory, but
`.github/workflows/test-suite.yml` runs `black --check --diff .` as a **mandatory** gate, so
the Makefile's comment is stale and running `ruff format` alone is not enough. The file was
reformatted with `black`, all four formatters now agree on it repo-wide (`black` 782 files
unchanged, `isort --check-only`, `ruff check`, `ruff format --check`), the suite still
reports `58 passed`, and the test-file digest above is the post-`black` one.

One finding about the shape of the A-1 control is worth recording, because the obvious test
would have been worthless. An end-to-end assertion through `build_eya_actual_bridge` does
raise `OPERATIONAL_PROVENANCE_MISMATCH` on a result whose components were edited — but for a
different reason: the deterministic replay rejects the edited result before the actual energy
is ever read (`"operational result differs from its deterministic replay"`). That test passes
with the line-1353 refusal deleted, so it is not a control at all. The real control is at the
helper, and `test_the_public_entry_point_cannot_be_the_control_for_that_refusal` pins the
interception order so the reason stays next to the code.

The task-domain lane's O-3 test was adopted as offered, closing the outermost fail-closed net
at lines 1654-1661 through a well-formed decimal whose reduced denominator exceeds
`_MAX_INTEGER_BITS`. Coverage moved from 33 missed / 95.35% to 29 missed / 95.92%; the four
statements closed are lines 1353, 1368 and the `except`/`raise` pair at 1654-1661.

Of the uncovered 29, the assurance lane's classification still holds: they are overwhelmingly
`raise` statements and the `except` clauses that lead to them. The decisive fail-open path it
identified is now controlled; the remainder are not, and this record does not claim they are.
