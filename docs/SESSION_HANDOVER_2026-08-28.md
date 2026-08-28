# Session handover — 2026-08-28

Durable PERSIST-01 successor to
[`docs/SESSION_HANDOVER_2026-08-24_8.md`](SESSION_HANDOVER_2026-08-24_8.md).
Successor 8 remains authoritative for the historical P01/P02/P03 candidate
artifact hashes, protected-delivery receipts and frozen programme populations.
This record supersedes its repository, worktree, ruleset-population,
cloud-sandbox, issue and continuation state.

## 1. Exact live cutoff

**Protected main:**
`14e7091fa3a3a5a028b1f8968ca619380c32f2fc`.

**Protected-merged cloud-sandbox PR:**
[#1165](https://github.com/arunakulat/dutchbay-epc-model/pull/1165),
`codex/1110-cloud-sandbox-runtime-fix` at exact head
`5599ff6a31644fdbfb5e689cba163b6c01d64d6b`, squash-merged as
`14e7091fa3a3a5a028b1f8968ca619380c32f2fc` on 2026-08-28. The reviewed topic
tree and protected merge tree were independently compared with `git diff
--exit-code` and are identical. Protected `main` was then fast-forwarded and
verified clean and synchronized at the merge commit.

**Cloud-sandbox worktree:**
`/Users/aruna/Downloads/dutchbay-wt-1110-cloud-sandbox-runtime-fix`.

**This PERSIST dolphin:**

- worktree:
  `/Users/aruna/Downloads/dutchbay-wt-persist-1110-cloud-sandbox-5599`;
- branch: `codex/persist-1110-cloud-sandbox-5599`;
- delivery PR:
  [#1182](https://github.com/arunakulat/dutchbay-epc-model/pull/1182);
- base after rebase: exact `origin/main` at
  `14e7091fa3a3a5a028b1f8968ca619380c32f2fc`.

At this cutoff, `git worktree list` contains only protected main, the #1165
worktree and this PERSIST worktree. The open-PR path scan found no other PR
touching `AGENTS.md` or a `SESSION_HANDOVER_*` path. Apart from this PERSIST PR,
other open PRs are #1176, #1178 and draft #1181. Re-run all ownership, worktree,
lock, process, open-PR and branch-currency checks before every mutation boundary;
this snapshot is not a permanent lock.

The data volume had approximately 14 GiB free (93% used) immediately before this
worktree was created. Do not create another full worktree without rechecking
capacity and ownership.

## 2. Governed environment and canonical ruleset

The mandatory shared environment remains
`/Users/aruna/Downloads/Dutchbay_EPC_Model/.venv`, verified from this worktree as
Python 3.12.13 with the active checkout first on `PYTHONPATH`.

The canonical bootstrap against
`go_with_the_flow_rules_v3_0_clean.csv` passed with **72 rules, all 72 active,
version v3.0**. Any historical note that reports 70/72 or another smaller live
GWTF population is a stale capture-time count and must not be used as current
state. No checkout-local, temporary, Python 3.11 or system replacement
environment was created.

## 3. PR #1165 protected-merge evidence

The merged PR repairs the #1110 GitHub Codespaces SSH lifecycle and publishes a
fail-closed, P03-empty execution environment. It is infrastructure and structural
evidence only. Its protected merge did not alter the release decision.

At exact head `5599ff6a31644fdbfb5e689cba163b6c01d64d6b`:

- focused cloud-sandbox controls: **33 passed**;
- complete `tests/lint` control population: **448 passed**;
- Bash syntax, Ruff, Ruff formatting, Black and `git diff --check`: passed;
- GitHub rollup after the final receipt-body edit: **23 terminal check records,
  20 success, three governed skips, zero pending and zero failure**;
- all four active branch-protection-required contexts passed: `Test Summary`,
  `fastlane`, `smoke` and `Verification receipts (VERIFY-01)`;
- the visible `build and boot audit review image` job passed, but it is advisory
  under the live ruleset. The promote-or-retain-advisory owner decision is now
  tracked by [#1183](https://github.com/arunakulat/dutchbay-epc-model/issues/1183);
- two narrow read-only code-review lenses were clean after their real findings
  were folded. They are code review, not formal P01/P02/P03 audit independence.

The final real GitHub Codespaces candidate receipt is
[#1165 comment 5448834731](https://github.com/arunakulat/dutchbay-epc-model/pull/1165#issuecomment-5448834731).
It records:

- clean exact remote checkout and API repository/ref identity;
- P03 private source root empty and P03 not executed;
- authenticated SSH, copy transport, stop/resume and post-resume SSH attestation
  passed;
- candidate `db1110-5599ff6a3164-4qrggqqpx3764g` API-confirmed absent;
- local candidate/create locks and matching helper processes absent;
- local controller branch/head bound before GitHub mutation; and
- controller SHA-256
  `0a1e3acd96f8ea535f9ec2cbc4730112a426b2bd3e5dd281ad5714adb87e75a2`,
  independently equal for the working file and committed blob.

The final two-lens receipt is
[#1165 comment 5448881479](https://github.com/arunakulat/dutchbay-epc-model/pull/1165#issuecomment-5448881479).
The accepted corrections include:

- 30-second per-SSH-attempt allowance under absolute transport/bootstrap
  deadlines;
- TERM-resistant descendant reaping, process-group `SIGKILL`, EPERM fallback and
  fail-loud cleanup across candidate, reusable-create and outer-verifier paths;
- local branch/head/controller digest binding;
- candidate and reusable-create ambiguity recovery with exact
  display/repository/ref identity;
- filesystem-backed monotonic status `125`, so unproved local cleanup survives
  subshells and cannot be erased by remote API absence; and
- accurate advisory wording for the hosted audit job.

Older PR receipts at `d0f1255`, `26f4036`, `83f5d47`, `7457a78` and `412f80c`
are historical troubleshooting evidence only. They do not authorize the current
head.

## 4. Programme state remains OPEN and HOLD

[Issue #1110](https://github.com/arunakulat/dutchbay-epc-model/issues/1110)
remains OPEN. The controlled pack remains structurally `PASS` and release
`HOLD`; `completion_authorized=false`. No independent `RELEASED` decision,
canonical re-baseline or Board/lender circulation authorization exists.

PR #1165 did **not**:

- execute or independently decide P01;
- semantically adjudicate any of the 111 P02 findings;
- upload private P03 material or review any of the 42 claims / 74 retained
  objects;
- authenticate F5-02 lender/legal/tax/authorized-dealer transaction evidence;
- clear P04, P05 or a downstream release gate; or
- authorize publication, lender use or circulation.

The exact child state is:

1. [#1158](https://github.com/arunakulat/dutchbay-epc-model/issues/1158) —
   OPEN; independent P01 clean-room checkpoint recovery has not been executed.
2. [#1159](https://github.com/arunakulat/dutchbay-epc-model/issues/1159) —
   OPEN; portable manifests and evidence integrity have not been independently
   attested.
3. [#1160](https://github.com/arunakulat/dutchbay-epc-model/issues/1160) —
   OPEN; blocked on additive, hash-bound results from #1158 and #1159.
4. [#1161](https://github.com/arunakulat/dutchbay-epc-model/issues/1161) —
   OPEN; no authorized independent reviewer has adjudicated all 111 findings in
   the private sandbox.
5. [#1162](https://github.com/arunakulat/dutchbay-epc-model/issues/1162) —
   OPEN; blocked on #1161, private evidence authority and independent review of
   all 42 claims and 74 retained objects.

Exact-head status comments were posted to all five children and
[#1110](https://github.com/arunakulat/dutchbay-epc-model/issues/1110#issuecomment-5448888191).
They deliberately leave every evidence-dependent issue open.

F5-01 and F5-02 remain separate evidence and decision surfaces. Synthetic lender
terms, QSTS path success, compile-only outputs and synthetic resource inputs do
not supply F5-02 evidence or bankable wind-resource evidence.

## 5. Controlled continuation sequence

1. PR #1165 is protected-merged as `14e7091fa3a3a5a028b1f8968ca619380c32f2fc`;
   its reviewed and merged trees are identical. Preserve its receipts and do not
   reinterpret this infrastructure delivery as an audit-gate decision.
2. The user authorized PR #1182 to merge only on terminal-green CI. Before that
   merge, prove the rebased topic head and remote branch match, prove zero-behind
   currency and clean worktree/index, re-query all required and aggregate checks,
   and preserve the review receipt. Merge without administrative bypass and
   independently verify the protected merge tree before retirement.
3. After verified delivery of #1182, retire only the two merged task
   worktrees/branches. Preserve every branch with an open PR, predecessor
   handovers, PR comments, CI URLs and controlled evidence receipt.
4. Issue #1161 owns the independent P02 review that requires creation of the
   protected-main reusable Codespace with
   `scripts/create_1110_cloud_review_codespace.sh`; issue #1162 governs its
   later P03 reuse. Create it only when the authorized independent P02 reviewer
   is ready to execute. Treat an `UNRESOLVED` lock as a stop condition requiring
   exact API/process reconciliation; never delete an uncertain resource by
   guess.
5. Execute #1158, then #1159, then record #1160 as separate additive dolphins
   with genuinely independent reviewer identity and exact result hashes. Same-
   implementer reruns and code-review agents cannot authorize these gates.
6. Execute #1161 over all 111 finding IDs only with private evidence authority
   and a genuinely independent reviewer. Preserve every HOLD and F5 boundary.
7. Execute #1162 only after its P02 dependency is satisfied, over all 42 claims
   and 74 retained objects, including semantic support, limitations and
   publication rights.
8. Start P04 only after P01/P02/P03 are complete. Start P05 only after P01/P02
   are complete. Preserve the frozen denominators and require additive
   hash-bound results plus independent oracles/review.
9. Keep F5-02 and release blocked until authenticated external evidence and the
   final authorized decision exist. Only the governed terminal release gate may
   lift `HOLD`.

## 6. Deletion and retention boundary

PR #1165 is merged, but its worktree and branch may be removed only after proving
the protected merge tree equals the reviewed head, the worktree/index is clean,
no unique WIP or unresolved review thread remains, and every residual obligation
is represented by an open GitHub issue. Do not delete a Codespace or lifecycle
lock merely because a note says it is stale: re-query the exact API identity,
process group, lock metadata and owner first. Preserve PR comments, check URLs,
candidate receipts, controller hashes and predecessor handovers as evidence.

This PERSIST worktree may be retired only after its own reviewed PR is protected-
delivered and its merged tree is verified. Local user-history branches and
unrelated open PRs remain outside this programme's cleanup authority.
