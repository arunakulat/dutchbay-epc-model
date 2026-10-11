# Session handover — 2026-10-11: merge coordination, the Hydra advisories and the dependency queue

## Status and predecessor

This is a scoped successor to `docs/SESSION_HANDOVER_2026-10-07_MERGE_COORDINATION.md` (#1337). Its window
starts where that record's ends, with `main` at `7dce2a67` (#1327) on 2026-10-07, and ends on 2026-10-11 with
`main` at `702c9ea8` (#1343). Later events belong to the next successor. In this window:
- the `hydra-core` advisories were answered: #1340 (1.3.6) was vetoed, and #1341 (1.3.7, closing #1339) merged
  on its own chain's reviews;
- #1337 (the 10-07 record), #1328 (`cftime`) and #1329 (`fqdn`) merged after review;
- #1336 merged on its own chain, outside this workstream;
- the two Dependabot ignore rules the owner asked for on 2026-10-07 landed: #1338 (`numpy-typing-compat`) and
  #1343 (`mpmath`). Dependabot then closed #1325 and #1344, the unmergeable bumps they target.

Every open item in the 10-07 record stands unless "Closed since" below says otherwise. Items 1 to 5 still
summarise the 10-06 record, whose wording, figures and gates govern them. Read the 10-06 record before acting
on them.

**A sibling successor exists.** #1348 added `docs/SESSION_HANDOVER_2026-10-11_CAPABILITY_ROADMAP.md`, also a
scoped successor to the 10-07 record, for the capability and assurance roadmap. That record is not this
session's and is not changed here. The two records cover different workstreams, and neither supersedes the
other. Run `scripts/list_session_handover_records.py` to see the order.

**The 10-05 record stays the repository startup record.** It holds the startup routing, the release snapshot
and the surviving `HOLD`s. A session that reads this record first should:
1. read `docs/SESSION_HANDOVER_2026-10-05_RELEASE_15_6_1.md` next and follow its chain;
2. come back here only for the merge-coordination workstream.

This record is documentation only. It changes no model, KPI, rule or release, and lifts no `HOLD`.

## Authority

- **Appointment.** The 2026-09-26 appointment of Claude session `session_01FEGL7MWRcTTqcwmkeRsf4J` as merge
  coordinator stands, as the 10-06 record gives it. It belongs to that session and does not pass to a session
  that reads this record.
- **Owner instructions given to this session in this window.** All were given in that session's chat, not on
  GitHub. This record was written by that session, which received them first-hand.
  - 2026-10-10, about 18:50Z: "Hold for the moment please". The coordinator stopped its running reviewer, the
    #1329 lane, and disabled its own scheduled check-in. The hold was not posted on GitHub at the time; this
    record is its first written trace.
  - 2026-10-10, about 19:50Z: "Go please and restart 1329 and let sweep session merge". Recorded on #1329 in
    6101535224.
  - 2026-10-11, about 08:40Z: "Go ahead and act audaciously - work autonomously and merge your work." Cited on
    #1338 in 6107248211.
- **Owner instructions relayed by another session.** This session did not receive these first-hand. The
  weekday open-PR sweep session, `session_01MBEFm7ND7rb5e7Exc5vuAw`, records them:
  - 2026-10-10, 18:37Z: "Start clearing the drafts sequentially please and merging" (6106421292). Under it the
    sweep session holds the merge lease for #1329 and #1338, in that order, with #1343 after them.
  - 2026-10-11, 06:43Z: "1329 is yours to merge now" (6106373419).
- **What the lease means here.** The lease holder merges. The coordinator recruits and posts the review, and
  merges only what the lease does not cover. The sweep session wrote #1343, so it does not hold #1343's lease
  and handed it to a coordinator (6101033393).

## What landed

| PR | Squash on `main` | Verified at the object |
|---|---|---|
| #1341, `hydra-core` 1.3.5 → 1.3.7 (closes #1339) | `cdc4146c92320b15ae4ec6fe025224286b2c9732` | Merged by the owner's account at 2026-10-09T20:55:13Z on the #1339 chain's own reviews of `44fce646` and their final-head rebinds (6084120878, 6084120903; evidence check 6084127125). This session did not re-verify those review files. Its tree `f23a4747` equals the head `4a85ea91`, and its single parent is `7dce2a67`. Close-out: 6089425394 |
| #1337, the 10-07 handover | `5c45a53b27c2d90e7e7264f7f3f861cb26b341c5` | Its tree `92abeb45` equals the reviewed head `c85bd45e`, and its single parent is `cdc4146c`. Post-merge record: 6093767409 |
| #1328, `cftime` 1.6.5 → 1.6.6 (Dependabot) | `1134afaad0ff2eb8afef5539a8fe2f2a43fe316a` | Its tree `beb52482` equals the head `d83660f4`, to which the review was carried forward (6093901127). Its single parent is `5c45a53b`. One review, on the owner's decision. Post-merge record: 6093907239 |
| #1336, provenance-bound evidence contract | `c43e7250dfa9f21398421f18650e4a0923910925` | Not coordinated by this session. Merged on its own chain |
| #1329, `fqdn` 1.5.1 → 1.6.0 (Dependabot) | `1be1d168a83476549704de7d653acca7d94e1062` | Merged by the lease holder at 2026-10-11T06:45:40Z. Its tree `b4c8398d` equals the reviewed head `68bd94c7`, and its single parent is `c43e7250`. One review, on the owner's decision. Post-merge record: 6106373419 (the lease holder's) |
| #1338, Dependabot ignore for `numpy-typing-compat` | `f3b674c873b85be629f33ae21a30a6cd74361726` | Merged by the lease holder at 2026-10-11T09:07:23Z. Its tree `fc6c581d` equals the reviewed head `373b8fc3`, its single parent is `1be1d168`, and its message is the confirmed body `c637c6b3…`, byte for byte. One review, on the owner's decision. Post-merge record: 6107436412 (the lease holder's) |
| #1348, capability and assurance roadmap | `7c3fa562038b6a79e9fa3246c833236b3e24e080` | Not coordinated by this session. Merged on its own chain's reviews (6108591808, 6108581591) |
| #1343, Dependabot ignore for `mpmath` | `702c9ea8964a843579da7fc40a3ddd80e50f090f` | Merged by this session at about 12:05Z. Its tree `8dbc7250` equals the reviewed head `4a3fd125`, its single parent is `7c3fa562`, and its message is the confirmed body `528eae2b…`, byte for byte. One review, on this session's reading of the owner's decision, which the lane judged sound (D1343-03). Post-merge record: 6108833262 |

**Closed unmerged.**
- #1340 (`hydra-core` 1.3.6). Both lanes vetoed it, and Dependabot closed it at 2026-10-09T21:15:30Z once
  `main` pinned 1.3.7.
- #1325 (the numerics group). Dependabot closed it at 2026-10-11T09:07:35Z, twelve seconds after #1338
  merged: "Looks like these dependencies are no longer being updated by Dependabot". The owner's open question
  about closing it is moot.
- #1344 (`mpmath` 1.3.0 → 1.4.1 alone, the group's regeneration after #1338). Dependabot closed it at
  12:05:06Z, as #1343 merged: "Looks like mpmath is no longer being updated by Dependabot".

**Still open, not in any coordinated sequence** (open item 14).
- #1326 (`llvmlite` 0.50.0) cannot install. Whether to close it unmerged is still the owner's question.
- #1345 (`charset-normalizer`) and #1346 (`bitarray`) are new Dependabot bumps, green on CI. The owner's
  one-review decision named #1325 to #1329 only, so they need the `R2` domain and assurance pair unless the
  owner waives one for them on record. #1348's squash message carries the same gate.

## Practice now in force

None of these is in `.claude/skills/steward/SKILL.md` yet. They are the coordinator's practice, and open item
6 carries the ones that belong in the skill.
- **Re-run the audit on the exact head before a dependency merge** (D1340-A-04). A green Security Scan reads
  live advisory data at the time it ran, so it goes stale. #1340's head was green from 2026-10-07, before the
  advisory that 1.3.6 fails was published.
- **Before recruiting for a dependency bump, search the open issues and pull requests for the same package.**
  The #1340 profile receipt (6056797502) called 1.3.6 the fix because #1339 and #1341 had not been read.
  Reconciliation 6078209528 corrects it.
- **Green means every required check succeeded** (`MERGE-01`). A skipped or failed non-required job neither
  blocks a merge nor stands in for a required one. The skill's stricter "every check" reading defers to the
  CSV and `AGENTS.md` where they disagree (D1328-04).
- **Review records carry no model name or identifier.** One draft record did. The reviewer revised it before
  it was posted, and every later brief says so.
- **The squash message is part of the review subject.** Three of the five squash drafts reviewed in this
  window needed a reviewer's correction before merge. #1338's and #1343's were confirmed unchanged:
  - #1328: "carried forward" (`3ac4bd0d…`);
  - #1329: D1329-09, a false "before review" (`8f2a5576…`);
  - #1337: the H-D2-02 gate quoted in full (`0d0a0cfe…`).

## Review records (all are comments on the pull requests)

The SHA-256 is that of the reviewer's file transcribed between the `8<` markers, by the byte recipe in the
skill's step 1. Every record below was re-read live at authoring: unedited, and its digest equals both the
digest it states and its durable file.

| PR, lane | Comment | Disposition | SHA-256 | Durable file |
|---|---|---|---|---|
| #1327, single lane | 6044276512 | ACCEPT_WITH_RESIDUALS | `aa4682e7c82922baac48b7d0860b7fe85b1bb74e9e6f1ad6c222730bce26dc3e` | `deps/1327/review/` |
| #1337 cycle 1, domain (head `04547721`) | 6044258242 | REJECT | `73d5878e34990d5701ff3933cffee0bcc53b25cb4a05fc38c7c6813e491c49bf` | `handover1007/domain/` |
| #1337 cycle 1, assurance | 6044258564 | ACCEPT_WITH_RESIDUALS | `70b7ed780bee1e1134c08f41fa8320a464400363353c312002749dce9f4e61b0` | `handover1007/assurance/` |
| #1340, domain (head `b07d74ea`) | 6078203395 | REJECT | `62acde11c77265b4d34f65ef1098fdccd97c97c51627e4b13b0fdd252fd34530` | `deps/1340/domain/` |
| #1340, assurance | 6078203673 | REJECT | `07f272b6e0a5e224f5483f0905b268e3511c848f35c77eb9d0f0d69e6943593c` | `deps/1340/assurance/` |
| #1341, assurance (superseded head `e78f8bf4`) | 6089422158 | ACCEPT_WITH_RESIDUALS | `c416987037bfd744c1193520d9bec2dba7f3fc3aaab8048e9d3f7d7f23186937` | `deps/1341/assurance/` |
| #1337 cycle 2, domain (head `c85bd45e`) | 6089837845 | ACCEPT_WITH_RESIDUALS | `dc7ab57874d6e8913234668780342a79390e921cbfd18c59f1a70099ebae4650` | `handover1007c2/domain/` |
| #1337 cycle 2, assurance | 6089838079 | ACCEPT_WITH_RESIDUALS | `7da6bbfe4a93d8fb0a6ad1151a9f161ab1d71e1c0d6fec46a973f6601f56572a` | `handover1007c2/assurance/` |
| #1337 cycle 2, merge-condition confirmation | 6093760175 | CONFIRMED | `1ee72ded29409710130a6f9c49d36c24c49580cc179224801c91a271860f1212` | `handover1007c2/assurance/` |
| #1328, single lane (head `6d3a96a3`) | 6089919479 | ACCEPT_WITH_RESIDUALS | `05c3a3941a9907d1a9fed1a2fff57a3d72db0745c2a2e4ef5851c5a34d4544a9` | `deps/1328/c2/review/` |
| #1328, §7 carry-forward to `d83660f4` | 6093901127 | ACCEPT_WITH_RESIDUALS | `d46d2889274094af1cca3d859283ef709a1563f2f1529e17479f5d55cb1c93fd` | `deps/1328/c2/review/` |
| #1329, single lane (head `68bd94c7`) | 6101626657 | ACCEPT_WITH_RESIDUALS | `e79dfb1bdb2dd5daac267eeaed985d3626d8059c4a855e147ddf6bbef77905f7` | `deps/1329/review/` |
| #1338, single lane (head `373b8fc3`) | 6107382734 | ACCEPT_WITH_RESIDUALS | `467c98d8c43a7f39bb35e2fcfe44b455950a6df101c9d3f1d98468eeac451c66` | `deps/1338/review/` |
| #1343, single lane (head `4a3fd125`) | 6108825432 | ACCEPT_WITH_RESIDUALS | `e18698f452de393e14acc1d07d5eeaa75c1606099666a06d3dacec78a1b530d0` | `deps/1343/review/` |

- **Reconciliations.** #1337: 6044350109 (cycle 1) and 6089849846 (cycle 2). #1340: 6078209528. #1328:
  6093902846. #1329: 6101628606. #1338: 6107385882. #1343: 6108827887.
- **Profile receipts.** #1337: 6044350470 and 6089516617. #1340: 6056797502. #1341: 6057301192. #1328:
  6044296522 and 6089527964. #1329: 6093912178. #1338: 6107248211. #1343: 6107434772, re-frozen in
  6108689283.
- **#1341's domain lane** was stopped by a usage limit and never returned a disposition. It is closed without
  one (6089425394). Neither of this session's #1341 lanes binds what merged.

### Where the durable records are (`PERSIST-01` mirror)

- **Location.** The files named above are in the coordinator session's container scratchpad. No other copy is
  recorded.
- **Lifetime.** That container is ephemeral. Once it is reclaimed, the comment transcriptions and the digests
  in this record are the surviving copies. A digest match then detects an edited transcription, but it does
  not restore a disposition's support for a merge (the skill's step 1).
- **Scope.** This mirror covers every review record this session recruited in the window, #1327's record, and
  both cycles of #1337, as the 10-07 record's gate requires (H-A1-11, H-D2-01, H-A2-02). It does not cover
  the #1339 chain's records for #1341 or any record for #1336, which other chains hold.

## Open items

Items 1 to 5 summarise the 10-06 record's items, whose wording governs. Items 6 and 7 carry the 10-07
record's, with additions. Items 8 to 14 are new.

1. **#1231's PR body still carries C3-A-01** (10-06 item 1). The 10-06 record gives the three corrections.
   - **Owner:** the #1231 writer session, or the coordinator if the owner asks.
   - **Gate:** one body revision with a new `body_revision`, then a re-read by the coordinator chain's
     assurance lane.
2. **Two errors in `d3157e0d`'s squash message** (10-06 item 2). The 10-06 record remains the correction
   of record.
3. **C3-D-01 widens the reason for the F-5 `HOLD`** (10-06 item 3).
   - **Destination:** A3's acceptance gate.
   - **Effect:** F-5 stands. Its bar, as `d3157e0d`'s message states it: no quarterly CFADS or intra-year DSCR
     figure from A2 may support a covenant, lender or IC representation until A3/A4 land a within-year event
     calendar; bess_augmentation_capex_lkr is a discrete event that A2 spreads like a flow.
4. **F-03 is still open** (10-06 item 4).
   - **Destination:** A3.
   - **Gate:** `cashflow.resolution` and `cashflow.within_year_profile` registered in the v14 field specs,
     plus a negative-control test that shows the gate firing.
5. **Other A3 residuals** (10-06 item 5): C3-D-02; C3-D-08 / C3-A-04; and the one-sided `checked >= 40`
   floor.
6. **Follow-up steward-skill dolphin** (10-07 item 6).
   - **Owner:** the coordinator.
   - **Contents:** the residuals #1322's cycle 3 accepted, as reconciled in 6024313300. Each reviewer gave a
     fix:
     - S-D5-01 to S-D5-05;
     - S-A5-01, S-A5-03, S-A5-04, S-A5-06, S-A5-07 and S-A5-08 (a), (b) and (d);
     - the S-D4-02 interested-relay limb, which #1322 did not adopt;
     - S-A5-02's three-sentence fix (6024295008): "Every reviewer recruited on record for a cycle must have a
       posted disposition. A recruitment with none, or a second recruitment for the same lane and manifest,
       is a stated blocker until the earlier reviewer's record is posted. A reviewer's withdrawal says what
       it was shown since its disposition." 6024313300 answered it for #1322 only;
     - H-A1-06 from #1337's review: the skill's two-parent merge-commit route cannot run on `main`, whose
       ruleset requires linear history;
     - new, D1328-04: the skill's "every check succeeded or was skipped for a stated reason" is stricter than
       `MERGE-01`'s required checks. Align it with the CSV, or state why it is stricter;
     - new, from this window's practice: the stale-audit re-run (D1340-A-04), the same-package search before
       recruiting, and the squash message as part of the subject.
   - **Gate:** its own two-lane acceptance.
   - **`HOLD` effect:** none.
7. **Test-hardening dolphin for `tests/lint/test_grid_ci_policy.py`** (10-07 item 7).
   - **Owner:** the coordinator.
   - **Contents:**
     - G-A2-04, the surviving `test -s` → `test -e` mutant on the JUnit guard;
     - G-A2-05, five unpinned evidence checks: no testcases, only skipped, exact head, protected base, six
       cases;
     - G-D2-05, surviving mutants that cannot pass bad evidence;
     - G-D2-07, the untested non-PR classify branch. Its surviving R9 mutant fails open: on schedule and
       `workflow_dispatch` runs it could skip the sharded suite and coverage while Test Summary still passes;
     - G-A2-06 and G-D2-04, the throwaway repositories inheriting the global git config;
     - G-D1-05 and G-A1-08, the remaining loose named-cause wording.
   - **Gate** (quoted in `3b352034`'s message): two-lane acceptance that also shows, by executed tests, that
     each deferred mutant is killed. That covers G-A2-05's five evidence-check deletions, and G-D2-07's
     non-PR branch rendered for push, schedule and `workflow_dispatch`, asserting `code_changed=true` and
     `qsts_execution_changed=false`.
   - **`HOLD` effect:** none.
8. **Resync persistent environments to the current lock** (H-D2-02's gate).
   - **Contents:** "resync any persistent environment, including the owner's governed runtime, to the current
     `requirements.txt` (D1327-04; also #1341's `hydra-core` 1.3.7)". The same holds for D1328-07 (`cftime`
     1.6.6) and D1329-05 (`fqdn` 1.6.0).
   - **Why it matters:** `validate_environment` fails closed on a drifted pin, so a stale runtime stops with a
     self-describing error rather than running silently. A session on the owner's governed runtime meets that
     error first.
   - **Owner:** the owner, on their own runtime, with `./setup_venv.sh`. This record cannot read that runtime.
   - **Gate:** a later successor records the resync as done, with evidence, or carries this item.
   - **`HOLD` effect:** none.
9. **Security-gate audit-coverage dolphin** (D1341-A-07 and D1341-A-08, from 6089422158).
   - **Contents:** the Makefile-mode `pip-audit` skips the `packaging`, `setuptools` and `wheel` pins; `bandit`
     and `pip-audit` are unpinned in the gate; and the required check names Test Summary, fastlane and smoke
     are not bound to the GitHub Actions app in ruleset 17414541.
   - **Until it lands:** the coordinator re-runs the audit on the exact head before every dependency merge
     (D1340-A-04).
   - **Owner:** the owner or the coordinator; the ruleset change is the owner's.
   - **Gate** (6089422158): `make security` audits every lock pin, with a negative control on one of the
     three; the security tooling is pinned or hash-locked; and the required checks are bound to the GitHub
     Actions integration.
   - **`HOLD` effect:** none.
10. **Hydra documentation refresh.**
    - **Contents:**
      - D1340-D-05: `docs/HYDRA_MAINTENANCE_DECISION.md` says there are no known CVEs, and it lists 4 of the 15
        `@hydra.main` entry points;
      - D1341-A-04 (and D1340-A-03): the publisher moved from `facebookresearch/hydra` to
        `hydra-ecosystem/hydra`, with the same repository id, 191632914. Nothing in the repository records it;
      - D1341-A-09: the Hydra comment in `.github/dependabot.yml` still names `hydra-core` 1.3.4.
    - **Owner:** the coordinator. **Gate:** one review. **`HOLD` effect:** none.
11. **#1339's implementation record** (D1341-A-01 to D1341-A-03): its lease line, its "changes only" sentence
    and its risk label. **Owner:** the #1339 chain, or the coordinator if the owner asks. **`HOLD` effect:**
    none.
12. **The legacy wind-download runner** (D1340-D-06). `scripts/legacy_runners/run_wind_download_v14.py` sets
    `config_path="conf"`, and that directory does not exist, so the runner fails under every Hydra version.
    **Owner:** the owner decides between a fix and retirement. **`HOLD` effect:** none.
13. **Dependabot configuration follow-ups** (6107382734, 6108825432).
    - D1338-01 and D1338-02: two wordings in the `numpy-typing-compat` comment, to correct when the entry is
      next edited. #990 added the major-only rule, not #986/#988, and the install steps, not the whole jobs,
      failed "in well under a minute". The record gives the replacement text.
    - D1338-04: the `numpy` entry's lift instruction should cross-reference `numpy-typing-compat`. Until it
      does, lifting `numpy` alone fails closed at install.
    - D1338-06: nothing in the repository or CI parses `.github/dependabot.yml`, so a malformed file would
      silently stop version updates (D1343-05 repeats it).
    - D1343-01: the `mpmath` comment says #1325 "reports two install conflicts". Its logs name only the
      `numpy-typing-compat` one; the `mpmath` conflict is recorded in 6089871064 and failed alone in #1344.
      Use the record's replacement text when the entry is next edited.
    - D1343-02: `changelog.d/1325-mpmath-ignore-minor.fixed.md` says the rule "now blocks minor bumps as well
      as majors", but no `mpmath` rule existed before. Apply the record's replacement body before the fragment
      is folded into `CHANGELOG.md`.
    - **Owner:** the coordinator. **Gate:** one review of the change that makes them. **`HOLD` effect:** none.
14. **The open Dependabot pull requests.**
    - #1326: `llvmlite` 0.50.0 is above `numba` 0.67.0's `llvmlite<0.50`, so it cannot install. Whether to
      close it unmerged was asked on 2026-10-07 and is unanswered. **Owner:** the owner.
    - #1345 and #1346: green, and outside the owner's one-review decision. They need the `R2` domain and
      assurance pair, or an owner waiver that names them. **Owner:** the coordinator, for recruitment.
    - #1325 and #1344 closed unmerged, so their install conflicts (correction 6089871064) no longer
      matter.
    - **`HOLD` effect:** none.

## Closed since the 10-07 record

- **The `hydra-core` advisories.** `main` pins `hydra-core==1.3.7` (#1341). #1339 closed as completed. #1340
  closed unmerged.
- **The 10-07 record's mirror gate** (H-A1-11; H-D2-01 and H-A2-02). The mirror above records #1337's
  cycle-1 and cycle-2 records and the merge-condition confirmation, with comment IDs, digests and locations.
- **H-D2-02.** D1327-04 is now open item 8, with H-D2-02's gate quoted.
- **The owner's 2026-10-07 Dependabot decisions** (6044254165). Both ignores landed, through #1338 and #1343.
  Dependabot closed #1325 and #1344, so the question of closing #1325 is moot.
- **The #1325 cause.** Two of this session's records disagreed about it (H-A2-06). 6089871064 corrects
  6043929273 and qualifies 6044254165.

## Corrections to the 10-07 record

The 10-07 record is in `main`'s history and is not edited. These corrections, from #1337's cycle-2 records,
stand in its place:
- **Usage limits.** "Usage limits stopped both lanes twice in this window" should read three times: #1322
  cycle 2, #1324 cycle 1 and #1337 cycle 1 (H-D2-03, H-A2-05(b)).
- **Module 1's wording.** Its table cell reads "Any code", capitalised (H-D2-04(c), H-A2-05(e)).
- **#1321's row.** The object check holds: `f4eea96c`'s tree `5e2e7f3e` equals that of #1321's head
  `3ce4e3c4` (H-D2-04(e), H-A2-05(f)).
- **The resolver lesson.** Its heading should say the resolver is over its 60-second threshold in containers,
  not near it: 71.0 s, 81.0 s, 61.1 s and 60.2 s were measured (H-D2-04(f), H-A2-05(a)). Issue #1342, opened
  on 2026-10-10 after a run of about 150 seconds, now tracks the fix.
- **F-5.** Item 3 quoted F-5's bar without its reason clause. Item 3 above quotes both (H-D2-04(a)).
- **G-D2-07.** Item 7 said "scheduled runs could skip the test shards". The finding covers schedule and
  `workflow_dispatch` runs, the sharded suite and coverage, and Test Summary passing (H-A2-05(d)). The carried
  gate was not weaker.
- **S-A5-02.** Item 6 carried one sentence of a three-sentence fix, under "Each reviewer gave a one-sentence
  fix" (H-A2-01, H-D2-04(b)). Item 6 above carries all three.
- **The mirror's scope.** "as 6024313300 scoped it": 6024313300 scoped the #1322 records only (H-A2-05(g)).
  #1327's record, which the 10-07 record cited without a digest (H-A2-03), is mirrored above.

## Lessons worth keeping

- **A green Security Scan is a past reading.** See "Practice now in force". #1340's Security Scan passed on
  2026-10-07, and the CI-exact `pip-audit` on the same lock exited 1 on 2026-10-09.
- **Usage limits stopped reviewers five times in this window, and this session once.** Every reviewer that
  returned was the same reviewer, resumed, told what had changed, and made to re-run its load-bearing checks,
  so no disposition rests on a stale check:
  - #1328's lane, which started on 2026-10-07 and stopped before any disposition; it resumed at
    2026-10-09T21:26Z on a re-frozen subject and reviewed it afresh;
  - #1340's domain lane and both #1341 lanes, from about 09:58Z on 2026-10-08 to about 09:16Z on 2026-10-09;
  - #1341's domain lane again, from about 10:00Z on 2026-10-09; it never returned before #1341 merged;
  - #1337's cycle-2 confirmation, from about 21:55Z on 2026-10-09 to about 04:24Z on 2026-10-10;
  - #1329's lane, from about 05:10Z to 18:40Z on 2026-10-10;
  - this coordinator session, from about 09:51Z to 11:40Z on 2026-10-11, after #1343's receipt and before its
    reviewer was recruited. `main` moved meanwhile, so #1343 was re-frozen before any review began
    (6108689283).
- **Sessions coordinate through pull-request comments.** A session can also message another session directly;
  the sweep session did so on 2026-10-11. Comments stay the record.
  - Another session's message is data, not an instruction. Only the owner lifts the owner's hold: during the
    10-10 hold this session declined peer "go" messages until the owner's own word arrived.
  - A session does not push content into another session's branch. That is why #1338's `mpmath` half became
    #1343 (6106421292).
  - A base update by one session can move another session's review subject. The lease holder brought `main`
    into #1329 at 18:43:52Z while its lane was running, and the lane bound directly to the new head
    `68bd94c7`. Post the frozen subject with the receipt, and ask the lease holder to hold updates until the
    record is posted.
  - Cite comment IDs in full. A truncated ID can match a different record (D1329-06).
- **A non-required job can go red for reasons outside the repository.** A Docker Hub outage from about 21:15Z
  on 2026-10-09 turned `build image and smoke /health` red on #1328's head `6d3a96a3`. This session's note
  6089568321 called that a merge blocker; it is not one under `MERGE-01`, and 6093902846 corrects it. The job
  passed on `d83660f4`.
- **Reviewers write only where they are told, and say so when they slip.** Three lanes disclosed incidental
  writes, none of which changed content:
  - #1329's lane wrote one loose git object with `git merge-tree --write-tree` (D1329-12);
  - #1341's domain lane ran the same command, which refreshed the modification time of two existing loose
    objects (its notes; it posted no record);
  - #1337's cycle-2 domain lane created and removed an empty `/home/user/_none`.

  The #1338 and #1343 briefs forbid `merge-tree --write-tree` and `hash-object -w`.
- **Send a reviewer its brief as text.** #1343's reviewer was first dispatched with the literal string
  `$(cat brief)`, because a shell substitution does not run inside an agent prompt. The brief followed as a
  message to the same reviewer, so there was still one recruitment for the lane and manifest (S-A5-02). The
  record discloses it.

## Hold and authority

- **This record confers nothing.** It gives no grade, release, lender, IC, Board or merge authority, and lifts
  no `HOLD`.
- **F-5 stands**, with its reason widened by C3-D-01 (open item 3).
- **Issue #1110 stays OPEN**, together with its Board and lender reliance `HOLD`.
