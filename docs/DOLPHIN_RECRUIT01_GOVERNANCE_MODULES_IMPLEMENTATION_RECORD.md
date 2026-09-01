# Dolphin RECRUIT-01 governance modules — implementation and PERSIST-01 record

**Status:** verified implementation candidate; exact-object independent review pending

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
