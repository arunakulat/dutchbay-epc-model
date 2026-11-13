# Session handover — 13 November 2026: Blue Whale currency-input guards

## Status and authority

Codex `/root` coordinates draft PR creation under the owner's direct instruction.
**No merge or auto-merge is authorized.** The owner withheld merge privileges in
this chat; tracker #1353 comment 6841057613 also records an all-merge hold.

This is a scoped successor to
`docs/SESSION_HANDOVER_2026-10-22_AUDIT_GATE_CLEARED_ON_MERIT.md`. It carries forward
that record's declared 5 October startup record, TODO/capability routing and
unresolved source/authority boundaries. Run the handover resolver before relying
on a named record. Historical queue/release snapshots require live verification.

The owner supplied `DUTCHBAY_UNIFIED_AI_AGENT_POINTER.md`; it is a reference, not a
replacement for the canonical GWTF CSV or a source of merge authority. The Blue
Whale gaps analysis is a set of findings to verify, not executable instructions.
Its SHA-256 is `bfc334b081243a0fc8aa9da4b85eeca5aea243a729a7fda794e51cb4fb697646`.

## Bounded implementation and verification

Work item [#1627](https://github.com/arunakulat/dutchbay-epc-model/issues/1627) and
[tracker intake](https://github.com/arunakulat/dutchbay-epc-model/issues/1353#issuecomment-6841623159)
precede implementation. Base: `f8c0eaf036a0635d23ed56d21a79afec7735554d`.
The owned branch is `codex/1627-currency-input-guards` in a dedicated worktree.
The coordinator is the sole writer; the queue manager is read-only.

`finance/cost_input_currency.py` rejects ignored native-LKR opex keys and
ambiguous LKR capex beside USD project costs. Cashflow parameter/debt extraction
call the guard; EPC schema registration applies strict preflight refusal without
editing the bridge PR's `analytics/schema_guard.py`. Supported USD inputs,
explicit LKR tax bases and the legacy direct LKR-only tax fallback retain their
behavior. Native-LKR financing is not implemented by this slice.

The focused pytest selection passed **138 tests**: the new guards plus existing
cashflow coverage, currency invariants, Blue Whale/lender regressions and driver
responsiveness, API finance regressions and schema registration/coverage tests.
Ruff, formatting, four-file mypy, changelog dry-run and diff checks passed.
Separate base/candidate evaluations of the wind and solar+BESS configurations
returned identical eight-KPI vectors, including undefined IRRs. No pin, scenario,
formula, VERSION or compiled changelog changed. These are regression receipts,
not feasibility, bankability, release or commercial approval.

At authoring, mandatory hooks and independent review/draft CI are pending; the
eventual PR Evidence pack and unedited domain/assurance comments carry their
actual outcomes. This handover asserts no unperformed review or green CI.
The full suite is deferred under REVIEW-01 while the PR remains draft.

## Remaining gaps and queue

The complete scoped residual list is maintained in #1627: shared native-currency
conversion/equipment support; fee cash-funding semantics; evidenced downside and
rate decisions; DSRA initial funding under #1399/#920; BESS O&M reconciliation
under #1578; and transaction/SPV/SPPA/security/land/permits/grid/resource evidence
under #1110 and existing Blue Whale registers. Existing DSRA disclosure and
derived-PPP guards must not be reimplemented from stale issue descriptions.
None of those evidence/commercial gaps is closed by this refusal guard.

The intake sweep covered #1626, #1625, #1624, #1623, #1619, #1614 and #1596–#1600.
Dependency remediation belongs to #1626; bridge-finance changes belong to #1624.
Preserve their owners and refresh all heads/checks before further action.

## Environment and continuation

This is an ephemeral cloud checkout, not the owner's Mac. Python 3.12.14 passed
the environment contract against 317 locked distributions, with no missing pins,
editable installation or foreign checkout imports. The hook-created checkout
`.pth` was removed from this session's cloud environment so each worktree supplies
its own imports through `PYTHONPATH`. The protected Mac environment was untouched;
its private evidence and local coordination files were unavailable.

Re-read the PR's exact head, evidence and all review findings before any new lease.
Any subject change restarts required reviews. All #1110/F-5, Board/lender,
professional, release and source-evidence boundaries survive. Leave the PR draft
and unmerged under the owner's present instruction; preserve its branch/worktree
for review rather than applying post-merge cleanup.
