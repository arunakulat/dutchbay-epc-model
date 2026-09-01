# Dolphin 3C-1b successor handover independent review record

**Disposition:** ACCEPT — corrected successor candidate

**Review date:** 2026-09-01

**Accepted candidate commit:** `dc80ece2f6547e3cf9a0a1e18b8703366267d772`

**Accepted candidate tree:** `005b95bd0650f8c0c3b16f861a4f52fa16724a10`

**Protected base and merge base:** `009f2ff22ffc00cf375d563beca1bbe6d1914e72`

**Reviewed files:** `AGENTS.md` and `docs/SESSION_HANDOVER_2026-09-01_2.md`

**Reviewers:** independent renewable/hybrid feasibility-domain reviewer and independent
software-contract/assurance reviewer; both read-only

## 1. Exact-SHA disposition

Both reviewers independently ACCEPTED the corrected successor at the exact candidate commit, tree
and base above. The `AGENTS.md` continuity pointer names the new handover, and the handover
faithfully records D3C-1b's protected result while staging the next safe prerequisite. Acceptance
does not transfer to another implementation, tree or base.

The accepted candidate remained documentation-only and clean:

- `M AGENTS.md`;
- `A docs/SESSION_HANDOVER_2026-09-01_2.md`;
- no protected code, test, taxonomy, `VERSION` or D3C-1b blob changed; and
- `git diff --check origin/main...HEAD` passed.

This review record and the handover status line form a docs-only successor commit after the
accepted candidate. Both reviewers must rebind their dispositions to that exact final head before
push. No implementation receipt transfers if any non-documentation blob changes.

## 2. Rejected first successor candidate

The first successor candidate, commit `0ecde08129b357013d8e6e4c87f69a902ccbbea0`, tree
`7e07190dd0a53e7b8ccab2892eac322cb86ce441`, was accepted by the domain reviewer but REJECTED by
assurance before push or PR. One reviewer's acceptance could not override the other reviewer's
veto.

The rejected draft required all three of the following at once:

1. a freshly validated genuine D2 `FeasibilityReportPackage`;
2. zero filesystem I/O; and
3. an initial package-assembly lease forbidding edits to D2 package validation.

Assurance demonstrated that current `SectionRecord.section_id` and package section-order
validation call `load_feasibility_taxonomy()`, whose cold path reads
`config/feasibility_sections.yaml` through `Path.read_text()`. A warm cache, eager preload or
fixture monkeypatch would only hide the read. The draft also attributed all three skipped PR
qualification jobs to changed-path policy and did not precisely distinguish the authenticated
private test-catalogue seam from supported production ingress.

## 3. Corrected prerequisite and closure

The corrected successor places D3C-2 package assembly on explicit pre-lease `HOLD`. The immediate
next dolphin is a separate import-safe D2 taxonomy-validation prerequisite with exactly this
five-file lease:

1. `analytics/feasibility_report_contract/records.py`;
2. `analytics/feasibility_report_contract/package.py`;
3. `tests/contracts/test_d3c2_taxonomy_io_prerequisite.py`;
4. `docs/DOLPHIN_3C2_TAXONOMY_IO_PREREQUISITE_RECORD.md`; and
5. `changelog.d/d3c2-taxonomy-io-prerequisite.changed.md`.

The prerequisite uses the already delivered import-safe
`taxonomy_identity.FEASIBILITY_SECTION_IDS` for the two D2 validators that need only identity and
order. It leaves the authored YAML, the generated identity projection and the general taxonomy
loader outside the writer lease. Consumers that need statuses, groups and complete definitions
continue to use the general loader.

The authored YAML remains the taxonomy SSOT. Normative D1 permits a typed identity surface generated
from or strictly parity-tested against that SSOT. The prerequisite requires exact source path,
full-file SHA-256 and ordered-ID parity, so it does not create a competing taxonomy. The earlier
non-normative D2 charter's resolver-only wording is a provenance watchpoint: the future
implementation record must state that this import-safe remediation supersedes that implementation
detail while preserving the normative D1 ownership rule.

The required negative control starts with a cold taxonomy cache and intercepts `Path.read_text`
before genuine record/package construction. A sentinel applied after loading is not evidence. The
focused contract guard may deliberately read the YAML to verify source identity; that build-time
parity check is distinct from package-runtime I/O.

The private immutable D3C-1b test-catalogue seam is authenticated only inside the controlled test
harness and may later create the held positive plumbing fixture. Production package code may not
import, re-export or depend on underscore helpers. The seam remains unsupported for production or
downstream ingress and creates no production authority.

## 4. Domain disposition

The domain reviewer found no remaining renewable, hybrid, finance, provenance, non-financial or
HOLD blocker. The corrected sequencing preserves:

- all twenty ordered section identities and meanings, including wind, solar, BESS, shared
  infrastructure, resource/energy, grid, construction, E&S, climate, cost, tariff/revenue, debt,
  tax/FX/accounting, finance, sensitivities, stochastic, optimization, risk, decisions and
  provenance;
- unknown, missing, duplicate and reordered section fail-closed behavior;
- no change to ProjectCase, D3B execution, D3C projection/binding, annual rows, directed FX,
  costs, tariff, debt, tax, IRR, NPV, DSCR or any KPI;
- later D3C-2 duties for authenticated ingress, complete registers, six reconciliation families,
  four visibly unperformed human responsibilities, static mapping, exact manifest bridge and no
  recomputation; and
- D3D, evidence, professional, lender, Board, release, publication and non-reliance boundaries.

The reviewer independently confirmed that the live authored YAML SHA-256 is
`ee2987df5ef97ee16cc970d53d483c60026b6f80cd9866cc1f94a066c9a5174e`, exactly matching
`taxonomy_identity.py`, and that all twenty IDs match in order. Six targeted taxonomy/parity/
validation controls passed. The cold-path counterexample reproduced the current filesystem read.

## 5. Assurance disposition

The assurance reviewer found no remaining documentation, bootstrap, delivery or cleanup blocker.
The correction accurately targets both current reads, refuses warm-cache and monkeypatch evasions,
preserves the general loader, and requires fresh-process construction with a `Path.read_text`
sentinel. The five-file lease, source-digest parity, import isolation, private-test/public-production
boundary and pre-lease D3C-2 HOLD are exact.

The reviewer independently confirmed that a cold child-process package validation attempts the
expected YAML read, and rechecked the live source path, source digest, twenty-ID order, Python,
rules, protected main, merged PR, open PR, issue, `VERSION`, catalogue and cleanup facts.

## 6. Live receipts and authority boundary

At review:

- governed Python was `3.12.13`;
- `check_venv.sh --no-bootstrap` passed;
- the canonical GWTF bootstrap loaded `73/73` active v3.0 rules;
- rules CSV SHA-256 was
  `707ee9ba28a48536f3d145931afa87f2a053f234d6268c8cbebd5b385ead79d9`;
- protected `main` was D3C-1b merge `009f2ff22ffc00cf375d563beca1bbe6d1914e72`, tree
  `f06401410c635708d554308a0be8a0e63f6a2416`;
- PR `#1214` remained merged from reviewed head `1e557c0…`, with 18 successful checks;
- Grid Study was the changed-path-policy skip, while stochastic and report qualification were
  scheduled/manual skips;
- only dependency PRs `#1176` and `#1178` were open;
- issue `#1110` remained `OPEN` with its explicit Board/lender circulation `HOLD`;
- `VERSION` remained `15.4.0`; and
- the production assembly-authority catalogue remained an empty immutable mapping.

This ACCEPT grants no prerequisite implementation acceptance, D2 package, evidence sufficiency,
professional act, achieved grade, release, lender or Board reliance, deployment, publication or
circulation authority. D3C-2 remains on pre-lease `HOLD`; its later package candidate requires a
fresh exact-SHA review after the prerequisite is separately delivered.

## 7. Mutation attestation

Both reviewers made no file, index, ref, branch, worktree, remote, issue or pull-request mutation.
Their final read-only checks confirmed the accepted candidate commit/tree/base and a clean index and
worktree. Temporary probes used self-removing process state and created no durable runtime logs.
