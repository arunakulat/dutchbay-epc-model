# Session handover — 2026-10-06: merge coordination for #1231 and #1295

## Status and predecessor

This is a scoped successor to `docs/SESSION_HANDOVER_2026-10-05_RELEASE_15_6_1.md`. It adds one
workstream, the merge-coordination record for #1231 and #1295, and changes nothing else.

**The 10-05 record stays the repository startup record.** It holds the startup routing, the release
snapshot and the surviving `HOLD`s. A session that reads this record first should:
1. read the 10-05 record next and follow its chain;
2. come back here only for this workstream's open items.

At authoring, protected `main` was `15f36bd64f78e7be2680c8a30101433c5245397a`. This record is
documentation only. It changes no model, KPI, rule or release, and lifts no `HOLD`.

## Authority

- **Appointment.** On 2026-09-26 the project owner appointed Claude session
  `session_01FEGL7MWRcTTqcwmkeRsf4J` merge coordinator for this repository and `DutchBay_RAG`,
  under `RECRUIT-01` and `MERGE-01`. The owner's words were "You are now the merge coordinator
  under RECRUIT-01 and other merge rules."
- **One revocation.** On 2026-09-27 at 00:12:14 UTC the owner took the #1231 merge back from the
  coordinator and gave it to the #1231 writer session. The owner's words, as relayed by that
  writer on #1231, were "take back merge lease on my specific instructions for #1231 only from the
  coordinator. Merge on CI green". The revocation covered #1231 only.
- **Logins are not identities.** Every Claude session in this project posts and merges under the
  `arunakulat` login or as `claude[bot]`. A comment's author field does not tell the owner, the
  coordinator, a writer and a review thread apart. Attribute a record by the session it names.

## What landed

| PR | Squash on `main` | Verified at the object |
|---|---|---|
| #1231 A1 restore + A2 sub-annual rows | `d3157e0d733afc97c07348767a480276dafdf854` | Tree `509014967b1f3c00f1c1a1d9d48ad87fd2bd0534` equals head `fe4bb91d`. Single parent is `b87ee32f`. F-09 is met: the subject names the A1 restore, and the body cites #1225 and #1232. |
| #1295 steward-skill Merging section | `10eba6a87a…` | Tree equals the final head `0e0814a0`. The skill blob on `main` is `bf8ccc3184562fd7c7dd937598428cca3869e83a`, which is the reviewed blob. |
| #1290 met-mast 617725 evidence | `0ff4f74c7b…` | The 13 unrecorded manifest entries were fixed before the merge. On head `30f3ae6d`, `Test Results` reported 0 failed. `VERIFY-01` failed once, at 14:58Z, and passed on its later runs. |
| #1296 platform plan | `e35ea9f26c…` | Not coordinated by this session. |
| #1297 `fsum` claims withdrawn and pinned | `ef801561…` | Closes D3-1 and the A2 fragment's 509/31 claim. See "Closed since". |

## Review records (all are comments on the pull requests)

### #1231

Two independent cycle-3 review chains ran on the same candidate, `65ae8736`, each blind to the
other. Both chains reached ACCEPT_WITH_RESIDUALS. The operative position is the union of both
chains' conditions (comment 5849143748).

| Record | Coordinator chain | Review-thread chain |
|---|---|---|
| Domain | 5848969846 | 5849058327 |
| Assurance | 5848988618 | 5849096976 |
| Reconciliation | 5848996330 | 5849105095 |

**Base advance.** The base moved from `cc82d295` to `b87ee32f` as merge commit `fe4bb91d`, under
coordinator lease L-1231-C1 (5849176111). The §7 proofs are in 5851120218.

**Rebinds to `fe4bb91d`.** Every rebind landed after the 05:06:10 UTC merge, so none of them
gated it.
- Coordinator chain: assurance 5852851495, domain 5854888992.
- Review-thread chain: its two lanes rebound and posted their records after the merge. That chain
  records the late rebind as its own process finding, A-C4-03.

The merge message itself discloses the missing rebind. The coordinator's post-merge verification
is 5852855600. The assurance lane's post-merge note is 5854891978.

### #1295

| Cycle | Result | Records |
|---|---|---|
| Cycle 1 | REJECT on one domain blocker, S-D-01 | 5849104574, 5849111041, reconciliation 5849113675 |
| Cycle 2 | ACCEPT_WITH_RESIDUALS, no veto | 5854896434, 5854901771, reconciliation 5854904577 |

- **Base advance** to `ef318177`: §7 proofs in 5854916229. Domain rebind 5854945303. The assurance
  rebind did not complete, because a usage limit stopped it.
- **Final head.** Another session merged `main` into the branch again (`0e0814a0`, bringing in #1290
  and #1296) and merged at once. That head had no §7 proofs or rebind. The reviewed bytes are
  unchanged on `main` (`bf8ccc31`).
- **Squash message.** The squash used GitHub's default concatenated message, not the coordinator's
  message recording the accepted residuals. The residuals are carried in the open items below.

## Open items

Each item names an owner, a destination and the condition that closes it (its gate).

1. **#1231's PR body still carries C3-A-01** (`body_revision: 2026-09-26T19:17Z`). This is a defect
   in the record only; no shipped byte is affected. Three corrections are needed:
   - (a) "all of them negative cases": of the 30 added tests, 25 are negative and 5 are not.
   - (b) "imports three names": `finance/subannual_rows_v14.py` imports four.
   - (c) The delivery head is `fe4bb91d`, not `65ae8736`.

   The writer's comment 5852838666 corrects (c) and retracts (a), but gives a wrong replacement
   figure for (a) ("22 of 121") and leaves (b) untouched. **Owner:** the #1231 writer session, or the
   coordinator if the owner asks. **Gate:** one body revision with a new `body_revision`, then a
   re-read by the coordinator chain's assurance lane.
2. **Two errors in `d3157e0d`'s squash message.** `main`'s history cannot be amended, so this record
   is the correction of record.
   - The message says that across three cycles "no reviewer found an arithmetic, contract,
     API-surface or governance defect". Cycle 1's assurance F-02 was an interface defect, and the
     cycle-1 reconciliation called all five blockers contract or provenance defects.
   - The message describes #1225 as "the A1 review-chain work this restore answers to". #1225 is
     A1's original pull request, the one merged without the review chain. #1232 reverted it for
     that reason.
3. **C3-D-01 widens the reason for the F-5 `HOLD`.** The `d3157e0d` message quotes F-5 without the
   extension. Until A3 folds the bridge period into year-1 quarters, a year-1 quarterly coverage
   figure flatters the project:
   - the period `dscr` is 2.605 against a `covenant_dscr` of 1.302;
   - year-1 `debt_service_total` is USD 14,025,907.92 when enriched, against 7,012,953.96 for the
     unfolded period.

   **Destination:** A3's acceptance gate. **Effect:** the bar on quarterly DSCR in any lender, IC or
   covenant use stands as F-5 states it.
4. **F-03 is still open.** Neither `cashflow.resolution` nor `cashflow.within_year_profile` is
   registered in the v14 field specs, so `analytics/schema_guard.py::validate_config_for_v14` does
   not refuse a bad value at pre-flight. **Destination:** A3. **Gate:** both keys registered, plus a
   negative-control test that shows the gate firing.
5. **Other residuals carried to A3:**
   - C3-D-02;
   - C3-D-08 / C3-A-04;
   - the default-off test's `checked >= 40` floor is one-sided. It fires if the glob narrows, but
     not if the loader reverts.
6. **The Grid Study gate depends on `base.sha`.** The review-thread chain found this, and no issue
   exists yet.
   - `scripts/ci/classify_grid_study_paths.py` runs over `base.sha...HEAD`.
   - After a base-advance merge, an older `base.sha` pulls the merged-in workflow, `analytics/grid/`
     and `tests/grid/` paths into that diff and classifies the run as `True`.
   - #1255's evidence step then requires a receipt from a test gated on `importorskip("andes")`.
     When that test skips, no receipt is written and the step fails.

   **Owner:** a repository fix, which needs an issue opened first. **Gate:** the gate depends only
   on the pull request's own contents.
7. **Residuals in the steward skill.** These go to a follow-up dolphin that changes the steward
   skill. The coordinator owns it.
   - #1295's accepted cycle-2 residuals: S-D2-01 to S-D2-06 and S-A-C2-01 to S-A-C2-06. Both lanes
     rank first that the skill assumes a single review chain.
   - Its Grid Study prediction uses `origin/main...HEAD`, but CI uses `base.sha...HEAD` (the skill
     side of item 6).
   - `CLAUDE.md` and the skill say "five" sandbox failures. The count varies with timing: 3, 4 and 5
     have all been observed.

## Closed since the merges

- **D3-1, the false sentence in the `math.fsum` comment, and the missing pin test:** #1297.
- **The A2 fragment's claim that the builtin `sum` gives 509/31:** withdrawn by #1297. `CHANGELOG.md`
  carries the correction. On the pinned Python 3.12 the figure is 510/30 under both `fsum` and the
  builtin. 509/31 is a Python 3.11 figure.
- **#1290's incomplete area manifest:** fixed before its merge.

## Lessons worth keeping

- **Coordinate review chains before dispatch.** Two chains reviewed #1231 in parallel without
  knowing of each other. They agreed, but reconciling them cost a cycle, and the merge then
  followed one chain's wording and dropped the other's (item 3).
- **A base advance after the last rebind voids it.** Before merging, check that the head still
  equals the rebound head. Both #1231 and #1295 merged on heads their reviewers had not rebound.
- **Usage limits interrupt reviewers mid-record.** Persist each record to scratch on completion.
  Post it byte-for-byte with its SHA-256, then verify the posted copy through the public API.

## Hold and authority

- **This record confers nothing.** It gives no grade, release, lender, IC, Board or merge authority,
  and lifts no `HOLD`.
- **F-5 stands**, with its reason widened by C3-D-01 (item 3).
- **Issue #1110 stays OPEN**, together with its Board and lender reliance `HOLD`.
