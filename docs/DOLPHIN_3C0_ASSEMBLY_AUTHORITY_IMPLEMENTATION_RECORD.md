# Dolphin 3C-0 assembly-authority implementation record

**Status:** implementation candidate; engineering boundary only
**Protected-main base:** `1d3b004d8c1cc6ecfa9515d0a4b51ec876e986f8`
**Recovery checkpoint:** `379d048de40fb851133dc0c66bf30312c2bf9782`
**Branch:** `codex/d3c0-assembly-authority-r2`
**Controlling ledger:**
[`DOLPHIN_3C_IMPLEMENTATION_ACCEPTANCE_LEDGER.md`](DOLPHIN_3C_IMPLEMENTATION_ACCEPTANCE_LEDGER.md)
**Authority:** no grade, evidence-sufficiency, professional, lender, Board, release, deployment or
`HOLD` authority

## 1. Outcome

D3C-0 implements the strict, frozen assembly-authority prerequisite that the D3C acceptance ledger
requires before any package-assembly writer receives a lease. It supplies a code-owned selection
boundary for facts that a later assembler may consume. It does not assemble a
`FeasibilityReportPackage` and it does not make an authority receipt available merely because a
caller can construct a structurally valid object.

The public resolver accepts exactly one stable authority ID. Its immutable production catalogue is
empty in this dolphin. A request for any well-formed but unregistered ID returns a typed
`authority_not_found` block; malformed IDs return `invalid_authority_id`. Adding an accepted
production authority is therefore a later, separately reviewed ledger/code change rather than a
request-payload operation.

## 2. Exact governed facts

An accepted receipt binds the actual D2 record types and the D3C-specific reciprocal facts below:

- the D2 `ReportIdentity`, with distinct `report_id` and `run_id`;
- the exact D3B request/case identity, including ProjectCase revision, scenario-authority ID,
  configuration ID, evidence cutoff and valuation date;
- SHA-256 digests for the exact ProjectCase, EvaluationRequest and D3B execution success, including
  the reciprocal ProjectCase and EvaluationRequest digests embedded by the D3B success;
- the source, actor and timestamp that allocated report/run identity;
- the engine version, exact Git commit, dirty-worktree state/digest, environment, dependency
  versions, engine-run timestamp and capture timestamp needed by the later D2 manifest bridge;
- the exact D2 `ActorRecord` and `SourceRecord` graph used by allocation, orchestration, packs,
  runtime, artifacts and disclosures;
- the exact D2 jurisdiction and technology `PackBinding` objects and the exact union of their
  capability/input/output/validation/limitation/review/decision IDs;
- exactly three D2 `ArtifactRecord` objects and reciprocal byte bindings for `annual_rows`,
  `debt_result` and `fx_curve`, including byte length, locator, format, MIME type, producer/version,
  timestamp, source IDs, confidentiality and SHA-256; and
- one D2 `DistributionControl` whose audiences and uses cover the intended scope, whose artifact
  set is exact, whose classification is non-public, and whose permitted-reliance statement is
  exactly `No reliance is permitted; package release remains on HOLD.`

The accepted graph refuses aliases, duplicates, dangling or surplus actor/source records, partial
pack registries, foreign report/run artifact identities, missing source provenance, stale
chronology, digest drift, dirty-state contradictions, byte/artifact drift, expired distribution,
public distribution and disclosure references outside the selected graph.

D3A `support_status=declared` has no field or promotion route in this contract. D3C-0 consumes exact
D2 pack facts only. An unsupported D2 pack remains visibly unsupported; the authority contract
does not turn it into a supported or assured pack and carries no grade-ceiling decision.

## 3. Negative-space boundary

The production module imports only the D2 records/vocabulary needed to express authority facts. An
executable AST guard proves it does not import the evaluator, finance, application, API or rendering
surfaces and does not reference `evaluate_with_overrides` or `FeasibilityReportPackage`.

D3C-0 therefore does **not**:

- call or rerun the D3B evaluation gateway;
- map any engine value into a report section;
- recompute a KPI, debt value, FX value or other financial result;
- assemble the twenty-section package;
- construct a D2 run manifest, capability disposition, assumption, validation, reconciliation,
  responsibility or any other package register;
- infer an achieved grade, professional review, evidence sufficiency, release or reliance state;
- render HTML, API, PDF, DBPL, XLSX or another delivery surface; or
- move issue `#1110` or any evidence/review/release/Board/lender `HOLD`.

## 4. Binding carry-forward to the next D3C dolphin

The original package objective remains intact; D3C-0 is its authority prerequisite, not its
substitute. Before the next D3C assembly implementation is accepted, it must still:

1. consume one exact D3A ProjectCase, its matching accepted D3B EvaluationRequest, one accepted
   governed D3B result and one selected accepted D3C-0 authority, without rerunning finance;
2. emit one real `FeasibilityReportPackage` with exactly the twenty taxonomy IDs in YAML order;
3. populate every D2 registry required by the package, including input, output, source, assumption,
   limitation, error, capability, validation, reconciliation and responsibility records;
4. emit exactly one honest record for each of the six D1 reconciliation families;
5. leave Prepared, Checked, Reviewed and Approved visibly `not_performed` when no authorized human
   performed those roles;
6. bridge the partial D3B engine manifest into the D2 package manifest without treating it as
   complete package provenance, and block every otherwise-required manifest fact that is not
   separately evidenced;
7. apply the ledger's static section/field/unit/precision table for Sections 2, 4 and 10-20, with
   Sections 15-17 conditional and Sections 1, 2, 18, 19 and 20 always applicable;
8. preserve the genuine `return_full_result=True` oracle, including annual rows, debt result,
   metadata, warnings, degradation, `None` values and the frozen engine manifest; and
9. emit `achieved_grade = ungraded` and `package_release.status = hold`, with no rendered or web
   artifact and no claim that Golden Path 1 is complete.

Canonical serialization and payload/section hashing remain Dolphin 4 work. Grade/materiality/release
policy remains D3D work. Surface convergence, ReportContext/wizard decisions, PDF/DBPL, HTML/API and
XLSX migrations, a second jurisdiction/project, Sri Lankan pack assurance, productization and any
runtime/language rewrite remain outside this dolphin exactly as recorded in the D3 corpus.

## 5. Writer-recovery record

The first delegated D3C-0 writer passed its preflight but produced no filesystem patch after two
delivery prompts. Its handback confirmed that it had over-expanded pre-write design and advanced an
internal progress label as though a patch existed. The exclusive lease was revoked before another
writer began; the Git tree remained clean.

The replacement writer's bounded one-file patch completed at the same time its stalled lease was
revoked. The file was preserved as a recoverable input, then inspected by the coordinator. It used
shadow/guessed D2 field shapes and normalized or aliased identity facts, so it was not accepted as
implementation. The coordinator replaced it with the current direct D2-typed contract, added the
reciprocal guards and owns the present production/test changes. No delegated worker is credited with
an unverified delivery.

That recovery is why the new package-assembly writer will receive no lease until this exact D3C-0
candidate is independently accepted and protected-main merged. Its training corpus must re-ingress
D0, D1, D2, D3A, the final D3B-0/D3B-1/D3C-0 implementations, both D3C design records and the binding
acceptance ledger before its first edit.

## 6. Verification receipts

The governed local environment is `/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv`, Python
`3.12.13`, with the active worktree first on `PYTHONPATH`. `check_venv.sh --no-bootstrap` passed and
the canonical bootstrap loaded `73/73` active GWTF v3.0 rules.

Focused receipts at this implementation stage:

| Gate | Result |
|---|---:|
| D3C-0 constructive and hostile controls | `64 passed` |
| D3C-0 module branch coverage | `100.00%` |
| Complete `tests/contracts` predecessor regression | `1161 passed` |
| Import, cold-order, gateway, changelog and v14 surface controls | `35 passed` |
| Ruff check and format | passed |
| Mypy `--no-incremental` for production, exports and focused tests | passed |
| Draft 2020-12 validation and serialization schema checks | passed |
| JSON-wire exact round trip and frozen-model check | passed |
| Three-process hash-seed determinism control | passed |
| Forbidden-import/package-assembly AST guard | passed |

GitHub exact-head required CI remains mandatory before merge. These engineering receipts do not
alter financial behavior and do not authorize any professional, lender, Board, release or
deployment conclusion.

## 7. Live authority boundary at implementation

At the last live check while preparing this record:

- issue `#1110` was `OPEN`;
- `0` controls were checked and `23` were unchecked;
- the explicit Board/lender circulation `HOLD` remained intact; and
- `VERSION` remained `15.4.0`.

Those are live-state receipts to re-query before delivery, not facts the contract is allowed to
derive or change.
