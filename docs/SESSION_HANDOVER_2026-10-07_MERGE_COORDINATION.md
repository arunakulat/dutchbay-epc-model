# Session handover — 2026-10-07: merge coordination, the steward skill and the Grid Study observability fix

## Status and predecessor

This is a scoped successor to `docs/SESSION_HANDOVER_2026-10-06_MERGE_COORDINATION.md`. It records the
work that closed two of that record's open items:
- item 7, the steward-skill residuals, closed by #1322;
- item 6, the Grid Study `base.sha` dependence, closed by #1324 through issue #1323.

Every other open item in the 10-06 record stands unchanged. This record summarises them; the 10-06
record's wording, figures and gates govern them. Read the 10-06 record before acting on items 1 to 5.

**The 10-05 record stays the repository startup record.** It holds the startup routing, the release
snapshot and the surviving `HOLD`s. A session that reads this record first should:
1. read `docs/SESSION_HANDOVER_2026-10-05_RELEASE_15_6_1.md` next and follow its chain;
2. come back here only for the merge-coordination workstream.

At authoring, protected `main` was `7dce2a67b44c36e73c877a2572fe43f159e8637a` (#1327). This record is documentation
only. It changes no model, KPI, rule or release, and lifts no `HOLD`.

## Authority

- **Appointment.** The 2026-09-26 appointment of Claude session `session_01FEGL7MWRcTTqcwmkeRsf4J` as merge
  coordinator stands. It is recorded in the 10-06 record, together with the owner's revocation for #1231
  only. The appointment belongs to that session. It does not pass to a session that reads this record.
- **Owner instructions in this window.** All were given in that session's chat, not on GitHub, and this
  record was written by that session, which received them first-hand.
  - 2026-10-06: "yes. follow up please". It approved the follow-up the coordinator had proposed (6009319317;
    #1322's body; `93823d55`'s message) and waived no condition or review lane.
  - 2026-10-06: "open an issue for the Grid Study base.sha hazard (item 6) please and resolve it through a PR
    and merge process please". This produced #1323 and #1324.
  - 2026-10-07: "Do only one review per dependency PR please", for #1325 to #1329. It is recorded on each of
    those PRs (for example 6043929854). These are the first dependency bumps under the practice below.
    - #1325 and #1326 are blocked by lock conflicts.
    - #1327 merged as `7dce2a67` after one review.
    - #1328 and #1329 follow one at a time. Each records its own state.
  - 2026-10-07, for #1338 (Dependabot configuration), recorded on it in 6044254165: confirm ignoring
    `numpy-typing-compat` minor and patch bumps; add an `mpmath` ignore to the same PR; one review.

## What landed

| PR | Squash on `main` | Verified at the object |
|---|---|---|
| #1321, the 10-06 handover | `f4eea96cc7dbbeffe978b96bea94411185b2aa0a` | Recorded in the 10-06 record's own history |
| #1320, comparative renewables briefing | `93410d8843bcba79074ea1bf77cc84776be9f999` | Not coordinated by this session. #1322 merged it in as `dad7442c` |
| #1322, steward skill: merge conditions across review chains | `93823d55d60496a74936643c5038714b0df876f9` | Its tree `42585513` equals the reviewed head `201eaeba`, and its single parent is `93410d88`. Post-merge record: 6024401913 |
| #1324, Grid Study observability (closes #1323) | `3b352034f74254af8b8baeb4d8cf9181ad252cb2` | Its tree `5ee81810` equals the reviewed head `f75935fa`, and its single parent is `93823d55`. `cbcf83bc` is not an ancestor. Post-merge record: 6032667865. #1323 closed as completed |
| #1327, `ipython` 9.16.1 → 9.17.1 (Dependabot) | `7dce2a67b44c36e73c877a2572fe43f159e8637a` | Its tree `dfb78f76` equals the reviewed head `fe51c562`, and its single parent is `3b352034`. One review, on the owner's decision. Records: 6044276512, 6044281403. Post-merge record: 6044289644 |

## Practice changes now in force (#1322)

`.claude/skills/steward/SKILL.md` now makes three changes to merge practice. `93823d55`'s message quotes all
three, and #1322's body and fragment disclose the first two:
- **A required review lane that has not run is a stated blocker.** It stops being one only if the owner has
  waived that lane on record. The skill reads `RECRUIT-01` module 1 as classing handovers, review records,
  governance and any code, dependency bumps included, as `R2`. Module 1 itself says "any code" (S-A5-08(d)).
  That includes this record.
- **Some dispositions no longer support a merge until reissued:** one that states no content digest, or one
  whose durable record the merging session cannot read. The skill's other route is to merge from where the
  durable record is kept.
- **Dispositions go in issue comments.** A pull-request review shows no edit time, so it cannot pass the
  unedited check (S-A5-08(b)).

The skill also says the following:
- **Attribution and withdrawal.** A record is attributed to the session that posted it. Only the party whose
  finding it is, or the owner, can withdraw a condition. A record nobody can attribute can never clear
  anything.
- **Owner waivers.** An owner waiver names what it waives. "Merge on CI green" waives nothing.

## Review records (all are comments on the pull requests)

The SHA-256 is that of the reviewer's file transcribed between the `8<` markers. The skill's step-1
re-verification gives the byte recipe.

### #1322: three cycles

| Cycle, head | Domain | Assurance | Reconciliation |
|---|---|---|---|
| 1, `fce0191b` | 6009296270 REJECT, `64c180377f1ec9c808d83e5b3ef16908bb85c1b3da01ab1d7a50de8ffe9ce98c` | 6009296417 REJECT, `f8e0b8d76374067b141bc12c142ad3daf2cb1a6e9273d40807441109a525c462` | 6009319317 |
| 2, `dad7442c` | 6023840520 ACCEPT_WITH_RESIDUALS, `8d7daff438b4a3d8c8c9b1f770d95d0f889ae99b3145d420c7b91d109d8faf7b` | 6023840830 REJECT, `430ce0ae4846e1400e8734bd2c1edafe915a989635376b43de5219de665e0245` | 6023899104 |
| 3, `201eaeba` | 6024294677 ACCEPT_WITH_RESIDUALS, `5e2f304bfe17a70784e0997a583d1435203ee931d138f7b36a7a232d1e9509f8` | 6024295008 ACCEPT_WITH_RESIDUALS, `b8669fd09973b7012dc9198c24f5b9a685a3cfe1111b24f44c41ada1b7254ae9` | 6024313300 |

- **Merge-condition confirmation:** 6024387030, `935974bc5c9e58d3959118683eb277a7e536486ecc6920366bc6024822fbfe5b`.
- **Profile receipts:** 6009359447 (cycle 2) and 6023913632 (cycle 3). Cycle 1 has no on-PR receipt.

### #1324: two cycles

| Cycle, head | Domain | Assurance | Reconciliation |
|---|---|---|---|
| 1, `cbcf83bc` | 6032201500 ACCEPT_WITH_RESIDUALS, `52b0ca59be275964c0c94a32b6ff6c924de275814ebdd60214812425148c4123` | 6032201761 ACCEPT_WITH_RESIDUALS, `58fad4d3b679d441f0f2018d6c5537b05d76e96df0991d5ecf9e659190d0b9a6` | 6032275067 |
| 2, `f75935fa` | 6032585160 ACCEPT_WITH_RESIDUALS, `ac50f63054a44df3f8186ca7d7dbf8a30a1f87750f55b392c834f06f6517cc87` | 6032585398 ACCEPT_WITH_RESIDUALS, `5091e60ac012791c62c10ff8a7aa7e4cc1f59995c39de7e8ab2c68d53618f9cf` | 6032603037 |

- **Cycle 2.** Cycle 1 accepted, but the writer then changed the subject to meet #1323's criterion 1 in
  full. That lapsed cycle 1.
- **Merge-condition confirmation:** 6032656898, `ac19694c211431d7bb0a2e43c72c4d1776bc72cde694743472126704a057e3aa`.
- **Profile receipts:** 6024454655 and 6032286929.

### Where the durable records are (`PERSIST-01` mirror, S-D4-04)

- **Location.** The reviewers' files are in the coordinator session's container scratchpad, under
  `steward2/`, `steward3/`, `steward4/`, `pr1323/` and `pr1324c2/`.
- **Lifetime.** That container is ephemeral. Once it is reclaimed, the comment transcriptions above,
  together with the digests in this record, are the surviving copies.
- **What changes when the container is gone.** A digest match here detects an edited transcription. It does
  not restore a disposition's support for a merge, because under the skill's step 1 a disposition whose
  durable record cannot be read does not support one.
- **Scope.** This mirror covers the #1322 and #1324 records, as 6024313300 scoped it. S-D4-04 also named
  thirteen #1231 and #1295 records whose files are in `pod1231/` and `skillfix/`. They are not mirrored here.
  #1337's own review records are in `handover1007/`, and the next successor handover mirrors them.

## Open items

Items 1 to 5 summarise the 10-06 record's items, whose wording governs. Items 6 and 7 are new.

1. **#1231's PR body still carries C3-A-01** (10-06 item 1). The 10-06 record gives the three corrections.
   - **Owner:** the #1231 writer session, or the coordinator if the owner asks.
   - **Gate:** one body revision with a new `body_revision`, then a re-read by the coordinator chain's
     assurance lane.
2. **Two errors in `d3157e0d`'s squash message** (10-06 item 2). The 10-06 record remains the correction
   of record.
3. **C3-D-01 widens the reason for the F-5 `HOLD`** (10-06 item 3).
   - **Destination:** A3's acceptance gate.
   - **Effect:** F-5 stands as `d3157e0d`'s message states it: no quarterly CFADS or intra-year DSCR figure
     from A2 may support a covenant, lender or IC representation until A3/A4 land a within-year event
     calendar.
4. **F-03 is still open** (10-06 item 4).
   - **Destination:** A3.
   - **Gate:** `cashflow.resolution` and `cashflow.within_year_profile` registered in the v14 field specs,
     plus a negative-control test that shows the gate firing.
5. **Other A3 residuals** (10-06 item 5): C3-D-02; C3-D-08 / C3-A-04; and the one-sided `checked >= 40`
   floor.
6. **Follow-up steward-skill dolphin.**
   - **Owner:** the coordinator.
   - **Contents:** the residuals #1322's cycle 3 accepted, as reconciled in 6024313300. Each reviewer gave a
     one-sentence fix:
     - S-D5-01 to S-D5-05;
     - S-A5-01, S-A5-03, S-A5-04, S-A5-06, S-A5-07 and S-A5-08 (a), (b) and (d);
     - the S-D4-02 interested-relay limb, which #1322 did not adopt;
     - S-A5-02's fix: every reviewer recruited on record for a cycle must have a posted disposition
       (6024313300 answered it for #1322 only);
     - H-A1-06 from #1337's review: the skill's two-parent merge-commit route cannot run on `main`, whose
       ruleset requires linear history.
   - **Gate:** its own two-lane acceptance.
   - **`HOLD` effect:** none.
7. **Test-hardening dolphin for `tests/lint/test_grid_ci_policy.py`.**
   - **Owner:** the coordinator.
   - **Contents:**
     - G-A2-04, the surviving `test -s` → `test -e` mutant on the JUnit guard;
     - G-A2-05, five unpinned evidence checks: no testcases, only skipped, exact head, protected base, six
       cases;
     - G-D2-05, surviving mutants that cannot pass bad evidence;
     - G-D2-07, the untested non-PR classify branch. Its surviving R9 mutant fails open: scheduled runs
       could skip the test shards;
     - G-A2-06 and G-D2-04, the throwaway repositories inheriting the global git config;
     - G-D1-05 and G-A1-08, the remaining loose named-cause wording.
   - **Gate** (quoted in `3b352034`'s message): two-lane acceptance that also shows, by executed tests, that
     each deferred mutant is killed. That covers G-A2-05's five evidence-check deletions, and G-D2-07's
     non-PR branch rendered for push, schedule and `workflow_dispatch`, asserting `code_changed=true` and
     `qsts_execution_changed=false`.
   - **`HOLD` effect:** none.

## Closed since the 10-06 record

- **Item 6: the Grid Study gate's dependence on `base.sha`.** Closed through #1323 and #1324.
  - **The predicted failure does not occur.** GitHub refreshed `pull_request.base.sha` on every push sampled
    across #1231, #1295, #1322 and #1324. The ruleset requires an up-to-date branch, so the last push before a
    merge carries the current `main` tip. #1231's base-advance run classified against the refreshed base.
    `andes` is in the `[grid]` extra, so the receipt test does not skip on CI.
  - **How the 10-06 gate is met.** The gate is met at the merge boundary, by those two facts together. It is
    not met by removing the dependence (G-D1-06).
  - **What #1324 changed.** The dependence on the base remains, and it is now recorded. A labelled block
    records the base, merge base, head, `code_changed` and the classifier result, and the step writes it to
    both the job log and the job summary. The evidence step names the cause when evidence is missing.
  - **Correction.** An older base usually widens the diff, but it can also turn Grid Study off: when the head
    reverts a grid change `main` made, or when the head's own diff is empty. The earlier claim that it "only
    widens" was false. #1322's and #1324's records refuted it, and #1323's body carries the correction.
- **Item 7: the steward-skill residuals.** Closed by #1322. Its own residuals are open item 6 above.
- **The Grid Study prediction in the skill.** It now diffs `<base.sha>...HEAD` at the pushed head. The
  `Classify changed paths` job is the authority.

## Lessons worth keeping

- **Test reviewer-proposed wording before adopting it.** In two consecutive #1322 cycles the writer took a
  lane's suggested text unchanged, and the next cycle rejected it:
  - "count nothing you cannot attribute" dropped vetoes;
  - "a coordinator … withdraws it" let a writer-coordinator withdraw a reviewer's veto.

  A census of the real records on #1231 and #1295 would have caught both.
- **Mutation counts need well-formed mutants.** A deletion that leaves an `IndentationError` inflates the
  count. #1324's "6" was really "1".
- **Job summaries cannot be read through the REST API or MCP.** Anything an agent reviewer must see goes to
  the job log as well.
- **Squash merges need an explicit message here.** The repository's default squash message is
  `COMMIT_MESSAGES`, so the default would carry every branch commit message into `main`. Rebase merges are
  also allowed. The settings allow merge commits too, but `main`'s ruleset refuses them
  (`required_linear_history`). Compose the squash message and send it explicitly.
- **The handover resolver is near its limit.** `scripts/list_session_handover_records.py` took 71.0 s in a
  review container for #1337. That is over `AGENTS.md`'s 60-second threshold for owner-led optimisation.
  The container is not the canonical environment, so this is disclosed for the owner rather than settled
  (H-A1-08).
- **Usage limits stopped both lanes twice** in this window: #1322 cycle 2 and #1324 cycle 1. The same
  reviewer was resumed each time, told either that the subject was unchanged or that the base had advanced,
  in which case it ran the §7 checks itself. That kept each disposition valid.

## Hold and authority

- **This record confers nothing.** It gives no grade, release, lender, IC, Board or merge authority, and lifts
  no `HOLD`.
- **F-5 stands**, with its reason widened by C3-D-01 (open item 3).
- **Issue #1110 stays OPEN**, together with its Board and lender reliance `HOLD`.
