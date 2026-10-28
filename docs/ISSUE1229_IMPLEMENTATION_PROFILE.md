# Issue #1229 implementation and delivery profile — 2026-09-08

Status: IMPLEMENTATION_AUTHORIZED. This supersedes the diagnostic profile's R0-only restriction for task 01a08180-c2e0-71b1-b80d-54661c802b53. It is authorization to establish a fresh bounded writer lease and deliver one complete reversible PR; it is not an implementation acceptance or issue closure.

## Owner instructions — carry verbatim to every successor and reviewer

> Do not wait for approval. work autonomously. Take your best, considered and safe decision. Use the Recruit-01 and verify-01 rules to reconsider and confirm your decisions. Start all new worktrees ingressing the rulesets - GWTF, CESSPIT, CASPER and CCCDIR. Follow these rules rigorously. Copy this instruction to all new tasks, worktrees, PR's

> all new worktrees, PR's etc should also inherit the GPT-6 Astra Extra High setting from the coordinator

Use GPT-6 Astra Extra High: model `gpt-6-astra`, thinking `xhigh`; collaboration reviewers use model `gpt-6-astra`, reasoning_effort `xhigh` with supported fork arguments. Verify actual session settings and retain concise evidence. A worktree and PR record the settings of their authoring/reviewer tasks. Never silently substitute. Continue autonomous considered safe decisions without routine permission requests. Prioritize existing local worktrees.

Latest owner direction: check and ingress the bounded #1229 DIAGNOSTIC_CHECKPOINT.md, take suitable action now, and reinforce user context and instructions.

## Identity, ownership and evidence ingress

Coordinator 01a07ca9-86e2-79b2-a462-cab673d4ead5. Reuse existing task 01a08180-c2e0-71b1-b80d-54661c802b53 and existing clean worktree /Users/aruna/.codex/worktrees/defd/dutchbay-epc-model. Project DutchBay_EPC_Model, local-f59c59e1b0193682361ce364fadb27e0. Persistent Python is /Users/aruna/Downloads/Dutchbay_EPC_Model/.venv, verified Python 3.12.13. Active checkout must lead PYTHONPATH.

Freshly read the full current canonical GWTF CSV, applicable AGENTS.md, newest handover and controlling predecessors, unabridged canonical CESSPIT/CASPER/CCCDIR definitions, and all four RECRUIT-01 modules. Execute authoritative startup/bootstrap; fetch and independently reconcile current main, live issue1229/charter/comments, issue1110, ownership, worktree and dependency identities before substantive writing. Historical pins are receipts, not current authority.

Coordinator preflight: clean detached defd at 61c5956d0ec23d03b1ac472abf735d6172ef4dbd; diagnostic manifest 15/15 PASS; issue1229 OPEN. Checkpoint SHA256 07ba282d308eb930b94310a618721292f80e6be9d69222e7f99107e77259d5a9; MANIFEST.sha256 digest 0130cc11c62e48c45328a4e27f8862ea83bb1170056cfdece870dc21d72d842d. Reverify before use.

Read the entire immutable diagnostic package at /Users/aruna/Downloads/DutchBay_Oldest_First_Programme_2026-09-07/issue1229/DIAGNOSTIC_CHECKPOINT.md. Preserve that directory unchanged. Put implementation evidence in sibling issue1229_implementation, with its own manifest; do not edit shared coordinator ledgers. Copy this profile into the worktree's governed implementation record/brief when establishing the branch.

Original source reverent-chatterjee-e6191a at ef478a7dd5ad9857dd1cbe2287423f6201dd7471 remains preserved. LOCAL_OWNER_ACKS.json records old owner's stop/lease revocation. Diagnosis verified no unfinished patch, and preserved the untracked .codex files. Do not mutate or remove that original tree.

## Capability, decision and bounded writing authority

R3_CONSEQUENTIAL: principal Python/native-runtime engineer with pandapower/IEC60909 screening, Numba/LLVM call-path analysis, isolation/concurrency, process lifecycle, numerical invariance and test-oracle capability. You are the sole writer for this bounded candidate. Record a current SHA/tree/base-bound lease after fresh ingress; create one codex/ branch in your existing worktree. On interruption, drift or scope change, checkpoint and re-establish continuity as RECRUIT-01 requires; do not request routine owner approval.

Implement one call-time screening adapter used by analytics/grid/short_circuit.py, analytics/grid/reactive_screen.py and analytics/grid/harmonics.py. Allowed changes: these three consumers; narrowly necessary adapter/helper modules under analytics/grid; directly relevant tests; minimal lifecycle configuration if needed under the existing configuration architecture; one changelog fragment and governed implementation/review/receipt/handover records. Record exact paths in the lease before writing them. Use architectural judgment to refine this bounded path list with a recorded reason. No finance/F2F3 changes, shared environment/dependency upgrades, general test-hygiene cleanup, CI gate weakening or unrelated refactors.

The diagnostic counterexamples require coverage of auxiliary dispatchers and bound aliases PLUS short-circuit makeYbus_numba.gen_Ybus. Keep existing runpp(numba=False). Preserve vendor mathematics and screening contracts. Do not replace the IEC solver with the approximate fallback, disable JIT globally, reuse rejected cache-isolation workarounds, or ship broad probe namespace substitution without a production-safe design.

Decide and record the smallest defensible design. Transient in-process mutations require proof across every affected consumer, aliases, late imports, exceptions and concurrency; a lock respected by only this adapter is insufficient. If that safety cannot be established, use a fresh single-owner helper process per meaningful screening batch, with Python vendor helpers inside it, explicit timeout/death/error/cleanup/serialization semantics and measured end-to-end cost. Amortize imports without introducing unsafe shared lifetime. Process containment alone does not satisfy elimination of the targeted compilation. Keep optional imports safe and established dependency-absence behavior; a crashed worker must not yield silent success or an approximate result labeled IEC60909.

## Capacity and other work

F2F3 task 01a07e1b-a139-79e0-94fc-4a8d48c37b72 owns c971 and PR1243. Its source is frozen, final independent rebinds ACCEPT, and remaining work is hosted CI/merge/closeout plus read-only hygiene inventory. Coordinator verified no diff in the three screening consumers or app/reports/grid_screening_emit.py between main61c5956 and F2F3 final1a01c388e0750aea02f932d77c2634dd757365f3. Concurrent bounded writing in defd is authorized. Do not take over or modify F2F3.

No simultaneous local full-suite campaigns. F2F3 confirms no current new campaign or environment mutation. Begin focused implementation checks immediately. Before the five-run campaign, send the coordinator a start notice and verify no other local full campaign is active; reserve the campaign in your receipt, then proceed without waiting for user approval when capacity is clear. If F2F3 actually needs another full run, serialize using owner-to-owner coordination. Reconcile any main movement before final freeze/review; do not transfer old dispositions across changed candidate objects.

## Required acceptance and delivery

1. Fresh-process no-compilation guard fails on untouched baseline and passes through actual production adapter for SC min/max and both runpp consumers. Removing auxiliary adaptation and removing Ybus adaptation must independently fail the guard. Record actual completed counts.
2. Charter fixture bit identity against unmodified vendor control: SCR 0.9404814334303563; fault min150.10083677548485 MVA; max162.7411166572655 MVA. Use existing pre-change tests and independent scalar/Decimal oracle plus driver responsiveness. Exercise reactive/harmonic outputs, sparse indices, out-of-service elements and aliases as supported. Preserve method/provenance/bands/bankable=false and optional behavior.
3. Verify lifecycle/concurrency/error/timeout/death/cleanup and finite serialization appropriate to the design, with hostile controls. Unrelated JIT configuration/users remain unchanged. Measure realistic latency; cold diagnostic font/cache timings are not a benchmark.
4. At least FIVE CONSECUTIVE CLEAN FULL-SUITE RUNS on the same final substantive source/runtime envelope. Preserve the original user's criterion and historical_acceptance_provenance.json. Record every attempt, exit/counts/skips/warnings and scan for Fatal Python error, Segmentation, node down, replacing crashed worker even if exit0. Stop and reconcile any crash, then restart a truthful consecutive streak after a justified correction. Keep raw routine logs transient and concise structured evidence durable. No retries hidden from the denominator.
5. Freeze exact commit/tree/base plus sorted path/blob subject manifest. Recruit separate independent read-only grid-domain and assurance reviewers using explicit Astra/xhigh and both exact quotations. Recruit to written profiles with full normative ingress and independent controls. This is explicit authorization for staged reviewer delegation under RECRUIT-01. No self-approval or absent-review acceptance. Persist dispositions and final-head rebinds.
6. Carry both owner quotations/model settings into PR body and provenance. Supply truthful VERIFY-01 receipts, all required exact-head CI success and executed GitHub-hosted Grid Study, current conflict-free base, unchanged 95% coverage/fail-closed policy. Merge on independently accepted exact-head green under MERGE-01 without asking for per-PR approval. Notify MERGE_SUBMITTED immediately, then verify actual protected merge and only safe owned closeout.
7. Close issue1229 only when its actual acceptance is satisfied. Explain elimination/containment scope honestly: LLVM's underlying corruption cause and triggering test for the newer F2F3 incident are still OPEN unless independently established. No release, professional, lender, Board, feasibility or HOLD authority changes; issue1110 remains outside this implementation.

Return early identity/ingress/lease/design confirmation to coordinator, then meaningful freeze, test campaign, review and delivery signals. Continue to completion rather than stopping after a plan or diagnostic proposal.
