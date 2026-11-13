# Session handover — 13 November 2026: Blue Whale currency-input guards

## Status and authority

Codex `/root` authored the initial `#1627` draft (`a13cd918`) and the alias/null
remediation (`e0048650`) on `codex/1627-currency-input-guards`. Subsequent base
refresh onto post-`#1614` `origin/main` (`67734269`), full verification, fresh
two-lane `RECRUIT-01` reviews, and delivery proceed under the owner's explicit
2026-11-13 merge/delivery authorization recorded in the active session and
tracker `#1353` (superseding the earlier draft-only/all-merge hold for PR `#1628`).

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
precede implementation. Initial base: `f8c0eaf036a0635d23ed56d21a79afec7735554d`;
current base: `67734269b49db15f83072b95f658d160e7b994b2` (post-`#1614` `origin/main`).
The owned branch is `codex/1627-currency-input-guards` in a dedicated worktree.

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

Both initial independent lanes rejected the first frozen candidate (`a13cd918`)
after hostile case-collision probes (`ASSURANCE-1628-01`, `FD-1628-01`,
`FD-1628-02`) bypassed direct-path refusal. The writer corrected lookup
precedence and null-alias handling in `e0048650`, with new controls observed to
fail before the fix. Those initial dispositions remain on the PR; fresh
independent finance-domain and assurance reviews bind to the frozen post-`#1614`
candidate head before transitioning PR `#1628` to Ready under `REVIEW-01`. No
prior acceptance carries forward.

## Remaining gaps and queue

The residual queue is maintained in #1629, following scoped #1627: shared native-currency
conversion/equipment support; fee cash-funding semantics; evidenced downside and
rate decisions; DSRA initial funding under #1399/#920; BESS O&M reconciliation
under #1578; and transaction/SPV/SPPA/security/land/permits/grid/resource evidence
under #1110 and existing Blue Whale registers. Existing DSRA disclosure and
derived-PPP guards must not be reimplemented from stale issue descriptions.
None of those evidence/commercial gaps is closed by this refusal guard.

The pre-merge open PR sweep covers `#1628` (active here) plus Dependabot PRs
`#1599`, `#1597`, and `#1596` (separately gated on protected environment/constraint
policy). `#1626`, `#1625`, `#1624`, `#1623`, `#1619`, and `#1614` have landed on
`origin/main` (`67734269`). Preserve base/owner isolation and refresh all
heads/checks before transition and merge.

## Environment and continuation

This is an ephemeral cloud checkout, not the owner's Mac. Python 3.12.14 passed
the environment contract against 317 locked distributions, with no missing pins,
editable installation or foreign checkout imports. The hook-created checkout
`.pth` was removed from this session's cloud environment so each worktree supplies
its own imports through `PYTHONPATH`. The protected Mac environment was untouched;
its private evidence and local coordination files were unavailable at initial
authoring. The owner subsequently restored read-only Mac access and directed a
RAG-first, then local/primary-bank evidence search before requesting missing
inputs. That source search is separate from this software-refusal scope.

Re-read the PR's exact head, evidence and all review findings before transition.
Any subject change restarts required reviews. All `#1110`/F-5, Board/lender,
professional, release and source-evidence boundaries survive. Complete `REVIEW-01`
(both fresh independent acceptances on frozen draft -> Ready CI -> `MERGE-01`),
then apply `CLEANUP-01` (close `#1627`, post `#1353` receipt, sync `main`, and retire
this worktree/branch) without modifying `/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv`.
