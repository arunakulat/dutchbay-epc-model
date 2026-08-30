# Dolphin 3B-0 standalone-policy basis-coherence remediation record

**Status:** implementation candidate; independent domain and assurance dispositions pending

**Base:** protected `main` at `9e1c6fae6220551754c23535caeaa86b37422230`

**Affected contract:** `dutchbay.v14_binding_policy.v1` / `1.0.0`

**Authority:** correctness remediation only; no grade, review, release, deployment or `HOLD`
authority

## 1. Why this remediation exists

Dolphin 3B-0 was squash-merged through PR `#1198` and received two later review records through
PRs `#1200` and `#1201`. Both reviews accepted the merged contract within their stated scope. A
fresh local reconciliation against protected `main` recovered one counterexample that neither
merged review exercised.

`V14BindingPolicy` is separately versioned, publicly exported and directly constructible. It owns
the complete tuple of compatibility assertions. The merged implementation enforced one
electrical/capacity basis per ProjectCase asset only in the outer
`EvaluationRequest._require_internal_request_graph` path. Therefore the outer request rejected an
internally contradictory policy while the standalone policy accepted the same object.

The historical reviews remain evidence of what they actually tested. This record does not rewrite
their dispositions or pretend the missed counterexample was part of them.

## 2. Exact pre-remediation counterexamples

All three probes ran on clean protected `main` at `9e1c6fae…`, against
`analytics/feasibility_report_contract/assessment_scope.py` SHA-256
`56c118e3334e981ef45b69b1540469a7d709f1cf2a16a7dd7fb76020a14f960a`.

| Policy mutation | Standalone `V14BindingPolicy` | Full `EvaluationRequest` |
|---|---|---|
| Same wind asset and `total_power_capacity`: `net` on one redundant target, `gross` on another | **ACCEPTED** | refused |
| Same unitized wind asset: net project/technology totals plus nameplate turbine count | **ACCEPTED** | refused |
| Same BESS: usable power/duration plus gross energy | **ACCEPTED** | refused |

These are not missing live-ProjectCase comparisons. They are contradictions wholly visible inside
the policy's own assertion graph. D3A gives one generation-capacity object a single
`electrical_basis` and `capacity_basis`; its storage contract likewise requires power, energy and
duration for one asset to share both bases.

## 3. Bounded correction

The per-asset generation and storage basis maps now live in
`V14BindingPolicy._policy_covers_every_material_category`, the lowest public root that owns every
required input. The duplicate implementation is removed from the outer request graph. Consequently:

- standalone and nested validation use one rule and one deterministic error surface;
- every generation assertion for one `asset_id` must share one
  `(electrical_basis, capacity_basis)` tuple across project, technology and unitized selectors;
- every storage assertion for one `asset_id` must share one tuple across power, energy and duration;
- a coherent five-route nameplate wind policy remains valid; and
- no ProjectCase, v14 evaluation, finance, D2 package, web/API, grade, release or `HOLD` surface is
  changed.

The focused controls validate the standalone `V14BindingPolicy` first and the containing
`EvaluationRequest` second. This prevents a future outer-model validator from masking a regression
in the public policy root.

## 4. Review and delivery gate

This record is not a self-acceptance. Before merge, two independent reviewers must bind their
domain and assurance dispositions to the exact candidate commit and replay:

1. the three standalone counterexamples above;
2. the coherent five-route nameplate wind positive;
3. wind, solar DC, storage-only and hybrid request positives;
4. both Draft 2020-12 schema modes and the D3B lexical/determinism controls; and
5. the D3A and D2 contract regressions.

The pull request may merge under `MERGE-01` only when those dispositions are durable, the topic is
current and conflict-free, and every required exact-head CI check is successful. That delivery
authority cannot lift issue `#1110`, whose Board/lender/release `HOLD` remains outside this change.

## 5. Local pre-review receipt

The implementation candidate was tested from the governed Python 3.12 environment with the active
worktree first on `PYTHONPATH`. No finance, application, API or D2 implementation file differs from
the protected-main base.

| Control | Result |
|---|---|
| Direct standalone-policy counterexamples and coherent positive | `5 passed, 131 deselected` |
| Complete D3B-0 assessment-scope contract | `136 passed` |
| Complete contract suite | `792 passed` |
| D3A ProjectCase predecessor regression | `330 passed` |
| D2 machine-contract predecessor regression | `298 passed` |
| Contract-package branch coverage | `94.18%` total; modified assessment-scope module `95.03%` |
| Ruff check and format check | passed |
| Black and isort checks | passed |
| Mypy `--no-incremental` on the assessment-scope export surface | passed |
| Draft 2020-12 validation and serialization schemas | valid |
| In-memory compilation, forbidden-import AST scan and `git diff --check` | passed |

These are local implementation controls, not independent acceptance and not a substitute for the
exact-head required GitHub checks.
