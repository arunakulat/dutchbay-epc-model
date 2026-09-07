# Dolphin RECRUIT-01 governance modules — implementation and PERSIST-01 record

**Status:** recovered and reconciled candidate; fresh independent review required

Sections 1–7 preserve the September 1 checkpoint. Section 8 supersedes its live status.

**Date:** 2026-09-01

**Protected base:** `6fa3fb506bf4d426c25f4517f8f50a32390e9739`

**Branch/worktree:** `codex/recruit01-governance-modules` /
`/Users/aruna/Downloads/dutchbay-wt-recruit01-governance`

## 1. Purpose and global scope

This single governance dolphin retains `RECRUIT-01` as the canonical GWTF pointer and moves its
operational detail into four repository-controlled sub-modules. The rule and modules apply to every
relevant task hereafter, regardless of subject, sprint, workstream, or named dolphin. D0–D3 provides
the failure evidence that motivated the controls; it is not their product boundary.

The change is runtime-neutral but operationally load-bearing. It changes no model, schema, finance
calculation, KPI, production catalogue, issue, `VERSION`, release state, or `HOLD`.

## 2. Writer lease and exact allowlist

The root coordinator is the sole lease-holder for the implementation checkpoint. Base and starting
HEAD are the protected SHA above. The initial allowlist is:

1. `go_with_the_flow_rules_v3_0_clean.csv`;
2. `AGENTS.md`;
3. `docs/governance/recruit_01/01_capability_and_risk.md`;
4. `docs/governance/recruit_01/02_writer_lease_and_recovery.md`;
5. `docs/governance/recruit_01/03_independent_review_and_attestation.md`;
6. `docs/governance/recruit_01/04_staged_delegation_and_ingress.md`;
7. `tests/lint/test_gwtf_canonical_source.py`;
8. `tests/lint/test_codex_project_guidance.py`;
9. `changelog.d/recruit-01-governance-modules.changed.md`; and
10. this implementation/PERSIST-01 record.

No other file is leased. The unrelated dirty F6 worktree and every other branch/worktree remain
outside this dolphin.

## 3. Four canonical modules

The modules separate concerns that were compressed into one CSV row:

1. capability profiles and semantic risk, including load-bearing documentation;
2. one-active-writer leases, recovery, persistence-only rescue, and closure;
3. reviewer independence, independent challenge, exact subject manifests, findings, receipt rebind,
   base movement, and squash-merge continuity; and
4. global ingress, capacity admission, staged waves, `NO_EVIDENCE`, and handoff.

The pointer yields to stricter task-specific rules and confers no non-engineering authority.

## 4. Acceptance criteria

The dolphin is acceptable only if:

- `RECRUIT-01` explicitly applies globally to all relevant future tasks and points to exactly the four
  tracked modules;
- coordinator and active lease-holder are no longer conflated;
- semantic risk, not file extension, determines review depth;
- load-bearing documentation receives two independent reviews;
- independence, review method, subject manifests, review-record rebind, base movement, and squash
  continuity are explicit;
- interruption, dead-worker takeover, persistence rescue, complete lifecycle, staged capacity, and
  `NO_EVIDENCE` are explicit;
- the repository gateway points agents to the canonical global policy;
- focused policy tests fail if the pointer or required module controls drift;
- the current rules bootstrap and repository guidance gates pass; and
- separate workflow/domain and assurance reviewers accept the exact frozen subject and final head.

## 5. PERSIST-01 checkpoint protocol

After the allowlisted patch, the coordinator records the exact candidate commit/tree/base, sorted
subject blob manifest and digest, dirty state, checks, and limitations here before reviewers are
dispatched. Reviewer dispositions are persisted through allowlisted review records in a later
documentation-only receipt commit. Both reviewers then rebind to the final head through immutable PR
evidence after proving subject-blob identity. Any substantive blob change restarts review.

## 6. Verification and review status

The coordinator obtained these fresh local receipts from this worktree with the checkout first on
`PYTHONPATH`:

| Gate | Exact result |
|---|---:|
| Persistent governed environment | Python `3.12.13`; `check_venv.sh --no-bootstrap` PASS; active checkout is this worktree |
| Canonical GWTF bootstrap | `74` rules; `74` active; version `v3.0`; PASS |
| Candidate GWTF CSV SHA-256 | `1ff239357a49f3d0017ec5cd72afdba5cb55c6be4540d928a47820adace1027b` |
| Focused canonical-source and gateway policy tests | `13 passed in 0.66s` |
| Complete `tests/lint` suite | `449 passed in 97.92s` |
| Ruff check and format check on changed Python tests | PASS; `2 files already formatted` |
| Four-module path/content integrity probe | PASS; `4` modules, `393` lines |
| `git diff --check` | PASS |
| `AGENTS.md` bounded-size guard | `14,387` bytes; below the existing `32 KiB` limit |

The first focused run exposed a brittle case-sensitive raw-Markdown phrase assertion; the second
exposed the same assertion crossing a line wrap. Both were test defects, not policy defects. A fresh
one-file lease replaced the raw check with whitespace-normalized, case-insensitive module matching;
the complete focused and lint suites then passed. These failures are retained here rather than
silently erased.

Independent workflow/domain and assurance dispositions remain pending until the committed candidate
is frozen. The receipts above are implementation delivery evidence only, not self-approval.

## 7. Authority boundary

This governance dolphin grants no achieved grade, evidence sufficiency, professional conclusion,
release, lender or Board reliance, deployment, publication, issue closure, or `HOLD` removal. It
changes how relevant future work is recruited and reviewed, not what any model output means.

## 8. September 7 takeover and reconciliation

The owner explicitly authorized this task to take over and deliver the existing worktree. The
original task `01a05a9c-cb6f-7dd1-b179-f32a10e9a7a5` acknowledged lease revocation and strictly
read-only status for itself and all workers, with no live subagents remaining. Its two reviews
returned no usable dispositions: both are `NO_EVIDENCE`, not acceptance.

Preserved checkpoint: `a822586bdf73ff26410d87a69a83d1c4f53de9ba`, tree
`ee0e072f0abca9a0a12b577cba3b1df7048f0e1e`. The takeover coordinator is task
`01a07c84-d0ec-7821-8f88-797a9bbeab2f`. It is the sole writer; reviewers receive no mutation lease.
The new protected base is `93aefbb7400287126060b1846b8cd83078fb6ac8`.

Lease `RECRUIT-RECOVERY-20260907` covers the original ten paths, this record, and the successor
handover `docs/SESSION_HANDOVER_2026-09-07.md`; a later receipt-only lease may add the two named
`docs/RECRUIT01_WORKFLOW_REVIEW_2026-09-07.md` and
`docs/RECRUIT01_ASSURANCE_REVIEW_2026-09-07.md` records. No application, finance, source-corpus or
other task's work is leased. The merge of current base preserves all its changes. The expected CSV
conflict stopped the update lease; a new bounded reconciliation lease retained the pointer and
carried the September 2 amendment into module 3. Original history remains recoverable.

The repair preserves all three base-update proofs (reviewed-file blob identity, bidirectional import
isolation and complete diff), makes substantive documentation part of the frozen manifest, orders
PR creation before final attestation, and replaces the false premise that a PR comment is inherently
immutable with content-hashed, durably preserved evidence checked again at merge.

Fresh receipts, from this worktree with the governed venv and active checkout on `PYTHONPATH`:

| Check | Command | Result |
|---|---|---|
| Environment | `DUTCHBAY_VENV=/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv ./check_venv.sh --no-bootstrap` | PASS, Python 3.12.13, imports from this worktree |
| Bootstrap | `DUTCHBAY_FLOW_RULESET_CSV="$PWD/go_with_the_flow_rules_v3_0_clean.csv" PYTHONPATH="$PWD" /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python dutchbay_bootstrap_rules.py` | 74 active v3.0 rules |
| Focused policy | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv/bin/python -m pytest -o addopts='' -n 0 --no-cov -p no:cacheprovider tests/lint/test_gwtf_canonical_source.py tests/lint/test_codex_project_guidance.py tests/lint/test_pr_receipts_policy.py -q` | 33 passed in 0.94s, including four firing policy-removal negative controls |
| Ruff lint/format | governed `ruff check` and `ruff format --check` on the two changed Python tests | PASS; 2 files already formatted |
| Black/isort | governed `black --check` and `isort --check-only` on the two changed Python tests | PASS |
| Whitespace | `git diff --check` | PASS |
| Full finance/QSTS/deployment | not run | No implementation or runtime change in this governance dolphin |

The initial format check requested one reformat; the allowlisted formatter was run and its check
then passed. Full lint and exact-head CI results belong in the PR receipts and review records;
no inherited test count is used as fresh evidence. Independent reviews must challenge the current
candidate, including the September 2 predecessor amendment, before delivery. These are author-side
receipts, not self-approval.


### Rejected first recovery candidate and repair lease

Candidate `7f10c067057abffa537ad0bca5f2509485527487` was independently rejected by both reviewers
for two mypy `arg-type` errors in the new test wrapper. The initial full lint gate nevertheless
passed `462 tests in 110.13s`; passing tests did not override the type finding. Lease
`RECRUIT-TYPED-REPAIR-20260907` permits only the wrapper signature, AGENTS handover pointer and this
record, followed by checks and a replacement freeze. The wrapper now matches Python 3.12
`Path.read_text(encoding, errors)` rather than forwarding untyped argument collections.

Assurance independently showed that the keyword policy guard can accept a semantically inverted
sentence when required phrases still occur. Its checks enforce textual presence and routing,
not semantic equivalence or actual worker compliance. That limitation is accepted within scope:
independent source review remains mandatory, and no green keyword test is semantic acceptance.
A machine-enforced lease or attestation service is outside this documentation/control-test dolphin.
