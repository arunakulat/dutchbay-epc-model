# RECRUIT-01 module 1 — capability profiles and semantic risk

**Status:** canonical operational sub-module of GWTF `RECRUIT-01`

## 1. Scope and applicability

This module applies to every relevant DutchBay task hereafter, regardless of subject, sprint,
workstream, repository area, named dolphin, worker implementation, or orchestration tool. It is not
limited to the Dolphin 0–3 feasibility-contract programme.

A task is relevant when either of these conditions holds:

1. analysis, implementation, review, or mutation is delegated to one or more workers; or
2. a charter, contract, risk classification, or other controlling rule requires independent review,
   even if the coordinator performs the implementation without a delegated writer.

A routine single-participant answer or read-only inspection that creates no governed deliverable does
not require a recruitment record. All other applicable tasks must be classified before a writer lease
or reviewer assignment is issued.

## 2. Written capability profile

The coordinator must recruit each worker to a written profile that states:

- worker identity and role;
- bounded mission and deliverable;
- required technical, domain, evidence, and assurance competencies;
- authorities the worker does not possess, including merge, release, lender, Board, professional,
  publication, issue-closure, and `HOLD` authority unless separately and explicitly granted;
- required ingress sources and their expected hierarchy;
- repository, worktree, branch, base, phase, and allowed mutation state;
- exact file allowlist for a writer, or an explicit read-only declaration for a reviewer;
- acceptance criteria, required independent oracles, and stop conditions;
- expected outcome receipt and persistence location; and
- task risk class and the reviewer roles it triggers.

A worker's self-description is a claim to verify, not proof of capability. Recruitment must match the
actual task profile. A general Python worker is not automatically a finance, renewable/hybrid,
security, regulatory, source-assurance, accessibility, or release-authority specialist.

## 3. Semantic risk classes

Classify the highest semantic consequence of the change; filename and language do not lower the
class. A Markdown or CSV change can be load-bearing governance, and a Python change can be a bounded
mechanical repair.

| Class | Typical work | Minimum independent review |
|---|---|---|
| `R0_READ_ONLY` | Inspection, inventory, diagnosis, or discussion with no governed mutation | No repository review; retain evidence for consequential claims under `VERIFY-01` |
| `R1_ROUTINE` | Non-authoritative prose, spelling, mechanical links, changelog-only summaries, or another clearly reversible change with no behavioral or authority effect | One role-appropriate independent reviewer |
| `R2_LOAD_BEARING` | Any code; contracts; schemas; tests that define an oracle; governance; charters; handovers; review records; provenance; security; data ingestion; deployment; report controls; release/HOLD wording; or other work capable of changing later action | Two independent reviewers: one task-domain reviewer and one separate assurance reviewer |
| `R3_CONSEQUENTIAL` | Finance/KPI behavior, lender or Board-facing evidence, grade/release logic, security boundary, regulated/professional act, production authority, destructive migration, or externally relied-on publication | At least the `R2` pair plus every specialist, independent oracle, human authority, and gate required by the specific controlling rules |

Load-bearing documentation is never downgraded merely because it changes no executable code.
Governance, a writer-authorizing handover, an acceptance ledger, or a release disposition changes
what later actors may do and is therefore `R2_LOAD_BEARING` unless a stricter rule applies.

## 4. Selecting reviewer roles

The domain reviewer must fit the subject actually changed. Examples include renewable/hybrid and
finance, grid, tax and regulatory, evidence/provenance, source licensing, DBPL/accessibility,
runtime/deployment, data engineering, or another named discipline. The assurance reviewer must be
separate and able to challenge contract boundaries, failure modes, verification quality, authority,
and unintended scope.

A specific charter may require a stricter chain. The stricter requirement wins. No reviewer count,
green check, or accepted engineering disposition confers achieved grade, release, lender, Board,
professional, deployment, publication, or `HOLD` authority.

## 5. Profile receipt

The coordinator records the profiles and risk decision before dispatch. A minimal receipt names the
task, risk class, coordinator, writer or no-writer state, reviewers, source hierarchy, worktree/base,
allowlist, acceptance criteria, and authority exclusions. If any of those fields changes, the
affected lease or review assignment must be reissued rather than silently broadened.
