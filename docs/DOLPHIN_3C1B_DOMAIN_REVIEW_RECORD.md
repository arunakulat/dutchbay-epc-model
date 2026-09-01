# Dolphin 3C-1b independent domain review record

**Disposition:** ACCEPT

**Review date:** 2026-09-01

**Accepted implementation commit:** `875179fcae059ab3993a8bd1c7ebd2934949ff1b`

**Accepted tree:** `a8cbc90585547f22a620e4897fcc7d0520a3cc20`

**Protected base and merge base:** `e60ea866da6b77c1d9e39236c206140eae1af08d`

**Reviewer role:** independent renewable/hybrid feasibility-domain reviewer; read-only

## 1. Exact-SHA disposition

The reviewer freshly ingressed the final D3C-1b diff, current session handover and D3C acceptance
ledger. No blocking renewable, hybrid, energy, context-binding, provenance or HOLD finding remained
at the exact implementation SHA and tree above. Acceptance does not transfer to another commit,
tree or base.

The earlier candidates were not accepted. Commit
`2a377a5210bc045f7493f40f999146434d920cb5`, tree
`23fb6d3b425f395dac4b391ed1158767c7b05426`, failed exact FX timeline/date/provenance and complete
cost/conversion/MissingValue context. Commit
`8e28be915c5479b0cabeb5b2f1feb14d08795945`, tree
`2d718aea0a5b62fc906577bf466e916c85add999`, failed reciprocal request-to-success re-ingress. Both
were rejected before push or PR; their green test receipts did not override the semantic
counterexamples.

## 2. Previously blocking reciprocal-origin finding

The accepted implementation requires code-selected authority and freshly verified artifact-byte
context, reconstructs the retained accepted D3B success, freshly reproduces its D3C-1a projection,
and reruns the complete ProjectCase/request/success/projection/authority reconciliation during
authenticated re-ingress.

The reviewer independently replayed the previously successful coherent substitution for each
request-authoritative success-origin field:

1. scenario authority ID;
2. config ID;
3. source-file SHA-256;
4. resolved-config SHA-256;
5. evidence cutoff;
6. valuation date; and
7. validation modules.

For each field the success witness, witness digest, trusted test-selected authority digest and
fresh projection were changed together while the retained request stayed authoritative. Python and
JSON re-ingress refused all fourteen cases for the intended reciprocal reason: the authority-ID
pair stopped at the request-receipt mismatch and the other twelve stopped at
`success_origin_mismatch`. There was no parse/type failure masking the property.

## 3. Domain and record boundary

The candidate retains the complete exact ProjectCase without promoting unsupported scalars. The
review covered wind generation, BESS storage, a shared point of interconnection, shared-
infrastructure links and the directed BESS-to-wind charging edge. A separate solar-PV mapper probe
confirmed that `MWdc` aggregate capacity remains inside the ProjectCase and does not become a D3C-
1b scalar without an admitted precision receipt. BESS power, energy and duration and shared-
infrastructure capacity likewise remain ProjectCase/reference facts.

The admitted numeric candidate table remains limited to exact positive integral generation-unit
count, native and reporting cost amounts at their respective minor-unit precision, and one directed
currency-conversion rate at quote precision. Cost records preserve line identity, native/reporting
proposition, currency, periodicity, price basis, conversion edge and precision source. Missing
native amount, reporting amount and conversion rate retain exact missing ID, ProjectCase path,
expected unit, reason, consequence and remedy without a fabricated value or provenance edge.

The directed FX candidate requires the exact USD-to-LKR conversion quoted as `LKR/USD`, one
governed source, matching source-observation/request/conversion dates, matching request price basis,
successful non-degraded FX integration, a complete finite statistic set, exact positive integer
timeline count, equal annual-row cardinality and every annual binary64 FX identity. Reversed
direction, quote/date/basis/source/statistic/rate drift and coherent timeline expansion were all
refused.

All twenty taxonomy sections were present exactly once in SSOT order. Every section retained:

- `completeness_status = unresolved`;
- `evidence_status = unresolved`;
- `review_status = not_performed`;
- `professional_act_status = not_performed`;
- `achieved_grade = ungraded`; and
- `release_status = hold`.

No resource, grid, tariff, tax, permit, legal, E&S, climate, sensitivity, Monte Carlo,
optimization, investment, lender or Board conclusion was inferred from a technology declaration,
topology edge, capacity, finance row or successful base-case evaluation.

## 4. Independent evidence

The reviewer used the governed Python 3.12.13 environment with the exact candidate worktree first
on `PYTHONPATH` and reported:

| Check | Independent result |
|---|---:|
| Focused D3C-1b suite | `73 passed` |
| Complete contracts regression | `1399 passed` |
| Import/hygiene/scope/D3C-0 selection | `429 passed` |
| Seven-field Python/JSON coherent substitutions | `14/14 rejected`; `0 accepted` |
| Same-length artifact-byte change | `artifact_digest_mismatch` |
| Production bind and re-ingress | `authority_not_found` |
| Exact sections/HOLD probe | PASS |
| Independent success-identity oracle and loss witnesses | PASS |
| Changed-file Ruff and format | PASS |
| `git diff --check origin/main...HEAD` | PASS |

Fresh-process import controls loaded all historical lazy public exports (`35/35` from `analytics`,
`29/29` from `analytics.core`) without evaluator, finance, filesystem, environment, network,
persistence, renderer or clock work. The reviewer found no annual-row summation or IRR, NPV, DSCR,
debt, tariff, tax, FX-statistic or other KPI recomputation. `VERSION` remained `15.4.0`.

## 5. Residual limitations and HOLD

The production assembly-authority catalogue remains intentionally empty, so no production
candidate can yet succeed. The constructive end-to-end fixture is wind/BESS/shared rather than a
separate solar-success fixture; inherited contract tests and the independent solar mapper probe
cover the relevant no-promotion boundary, and D3C-1b does not branch on technology names.

The reviewer did not independently repeat the coordinator's ten-minute full-suite, coverage,
complete mypy, Black, isort, Bandit or dependency-audit receipts. Exact-head CI and the separate
assurance disposition remain independent delivery gates.

This ACCEPT grants no D2 package, evidence sufficiency, professional act, achieved grade, release,
lender or Board reliance, deployment, publication or circulation authority. Issue `#1110` and all
stated HOLD/non-reliance controls remain unchanged. D3C-2 remains a separate later dolphin.

## 6. Mutation attestation

The reviewer made no file, index, ref, branch, worktree or remote mutation. Final read-only checks
confirmed the accepted commit, tree, base and merge base above, a clean worktree, no staged diff and
no working-tree diff. Temporary independent probes used self-removing OS temporary directories
with bytecode and pytest cache disabled.
