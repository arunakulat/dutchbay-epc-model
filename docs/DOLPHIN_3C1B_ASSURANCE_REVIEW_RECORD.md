# Dolphin 3C-1b independent assurance review record

**Disposition:** ACCEPT

**Review date:** 2026-09-01

**Accepted implementation commit:** `875179fcae059ab3993a8bd1c7ebd2934949ff1b`

**Accepted tree:** `a8cbc90585547f22a620e4897fcc7d0520a3cc20`

**Protected base and merge base:** `e60ea866da6b77c1d9e39236c206140eae1af08d`

**Reviewer role:** independent software-contract and assurance reviewer; read-only

## 1. Exact-SHA disposition

The reviewer freshly ingressed the final remediation diff, current handover, D3C acceptance
ledger, implementation and test bodies, implementation record and changelog. Within the reviewed
software-contract boundary, the earlier authority, byte-provenance, reciprocal-origin and bounded-
ingress findings were closed at the exact implementation SHA and tree above. Acceptance does not
transfer to another commit, tree or base.

The first candidate, commit `2a377a5210bc045f7493f40f999146434d920cb5`, tree
`23fb6d3b425f395dac4b391ed1158767c7b05426`, and the second candidate, commit
`8e28be915c5479b0cabeb5b2f1feb14d08795945`, tree
`2d718aea0a5b62fc906577bf466e916c85add999`, were both rejected before push or PR. Green local
tests on either rejected tree were not acceptance evidence.

## 2. Authority and byte-provenance closure

The accepted implementation makes authenticated candidate validation depend on a separately code-
selected D3C-0 authority and receipts freshly computed from all three supplied artifact payloads.
The reviewer confirmed:

- direct `D3CContextBindingCandidate(...)`, `model_validate(...)` and
  `model_validate_json(...)` cannot authenticate a serialized candidate;
- empty or arbitrary caller Pydantic context is refused;
- production bind and both public re-ingress paths resolve only by stable authority ID and return
  `authority_not_found` while the production catalogue remains an empty immutable mapping;
- coherent caller copies of authority, report, pack and artifact graphs cannot replace the
  separately selected authority;
- coherent artifact digest/length metadata without matching bytes is refused before candidate
  validation by fresh byte-length and SHA-256 reconciliation;
- accepted-success witness/digest/projection changes and coordinated FX/output changes are checked
  against selected authority, reconstructed success, fresh projection and fresh derivation; and
- all seven request-authoritative success-origin fields are reconciled in both Python and JSON.

The earlier equal-projection counterexamples remain load-bearing: different opaque metadata and a
different annual `fx_rate` change the complete-success digest even when the D3C-1a projection is
equal. An unchanged selected authority refuses both substitutions.

## 3. Bounded ingress and isolation

The reviewer confirmed that raw `bytes` and `bytearray` length is checked before decode or copy,
while string UTF-8 length is counted in bounded chunks before JSON parsing. `1e999` and explicit
non-finite values produce deterministic `non_finite_json_number` refusal. Duplicate and long
duplicate keys, surrogates, malformed UTF-8, hostile `repr`, oversized integers, excessive depth,
container/scalar/text volume, cycles and unsupported types retain negative controls.

Validation and serialization schemas validate as Draft 2020-12. Canonical equality and exact
round-trip hold only through authenticated re-ingress with reselected authority and freshly
supplied bytes, not through raw type-shaped model ingress.

Fresh-process controls showed no evaluator, finance, application or API import and no `Path` I/O.
No locator following, evaluation rerun, finance call, annual-row sum or KPI recomputation surface
was found.

## 4. Private/test-only API boundary

The private capability object, authenticated-context type/helper and test-catalogue bind/re-ingress
functions all use leading-underscore names. They are absent from `context_binding.__all__`, absent
from package-root exports, referenced outside their implementation only by the focused contract
test, and absent from production consumers.

As with Pydantic's unsafe `model_construct`, unvalidated `model_copy(update=...)`, monkeypatching or
direct object mutation, a caller that deliberately imports and invokes underscore internals can
step outside the supported model contract. Downstream code must use `bind_d3c_context`,
`reingress_d3c_context_candidate` or `reingress_d3c_context_candidate_json` and must not treat a
merely type-shaped instance as authenticated. The reviewer classified this ordinary Python privacy
limitation as a residual unsupported-use constraint, not an accidental public injection seam or a
blocker within the reviewed software-contract boundary.

## 5. Independent evidence

The reviewer used the governed Python 3.12.13 environment and reported:

| Check | Independent result |
|---|---:|
| Focused D3C-1b suite | `73 passed` |
| D3C-0 and assessment-scope regression | `406 passed` |
| Changed-file Ruff and format | PASS |
| `git diff --check origin/main...HEAD` | PASS |
| Scanner refusal matrix | PASS |
| Fresh import and `Path` I/O sentinels | PASS |
| Private export audit | no private names exported |
| Production catalogue | empty `mappingproxy` |

The scanner matrix returned the intended bounded codes for exponent overflow, explicit non-finite
values, duplicate keys, escaped surrogates, oversized integers and oversized invalid byte/bytearray
inputs. The reviewer did not independently repeat the coordinator's complete contracts, ten-minute
full suite, coverage, complete mypy, Black, isort, Bandit or dependency-audit receipts; exact-head
CI remains separate merge authority.

## 6. HOLD and mutation attestation

Root and all sections remain unresolved, unperformed, ungraded, held, non-reliant and unpublished.
This ACCEPT grants no D2 package, evidence sufficiency, professional act, achieved grade, release,
lender or Board reliance, deployment, publication or circulation authority. Issue `#1110` and all
stated HOLD/non-reliance controls remain unchanged. D3C-2 remains outside this dolphin.

The reviewer made no file, index, ref, branch, worktree or remote mutation. Final read-only checks
confirmed the accepted implementation commit, tree, base and merge base above, a clean worktree
ahead by three commits, and no staged or working-tree diff.
